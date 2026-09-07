import os
import sqlite3
import hashlib
import re
import json
import requests
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sow_types import SOW_TYPES


class _TursoConn:
    """SQLite-like connection wrapper around Turso REST API."""

    def __init__(self, db_url: str, auth_token: str):
        self._api_url = self._normalize_url(db_url)
        self._headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        self._last_rowid = None

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.replace("libsql://", "https://")
        if not url.startswith("https://"):
            url = "https://" + url
        url = url.rstrip("/")
        if not url.endswith("/v2/pipeline"):
            url = url + "/v2/pipeline"
        return url

    @staticmethod
    def _encode_arg(val):
        if val is None:
            return {"type": "null"}
        if isinstance(val, bool):
            return {"type": "integer", "value": "1" if val else "0"}
        if isinstance(val, int):
            return {"type": "integer", "value": str(val)}
        if isinstance(val, float):
            return {"type": "float", "value": val}
        if isinstance(val, (bytes, bytearray)):
            return {"type": "blob", "value": val.hex()}
        return {"type": "text", "value": str(val)}

    def _send(self, statements: List[Tuple[str, list]]) -> list:
        payload = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": [self._encode_arg(a) for a in args]}}
                for sql, args in statements
            ]
        }
        resp = requests.post(self._api_url, headers=self._headers, json=payload, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        results = []
        for item in body.get("results", []):
            response = item.get("response", {})
            if response.get("type") == "error":
                raise RuntimeError(f"Turso error: {response.get('message', response)}")
            results.append(response.get("result") or {})
        return results

    def execute(self, sql: str, params=()):
        results = self._send([(sql, params)])
        result = results[0] if results else {}
        cursor = _TursoCursor(result, self)
        rid = result.get("last_insert_rowid")
        cursor.lastrowid = int(rid) if rid is not None else None
        return cursor

    def executemany(self, sql: str, seq_of_params):
        statements = [(sql, p) for p in seq_of_params]
        self._send(statements)
        return _TursoCursor({}, self)

    def executescript(self, script: str):
        statements = self._split_sql(script)
        self._send(statements)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    @staticmethod
    def _split_sql(script: str) -> List[Tuple[str, list]]:
        parts = []
        current = []
        in_single = False
        in_double = False
        for ch in script:
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            if ch == ";" and not in_single and not in_double:
                stmt = "".join(current).strip()
                if stmt:
                    parts.append((stmt, []))
                current = []
            else:
                current.append(ch)
        stmt = "".join(current).strip()
        if stmt:
            parts.append((stmt, []))
        return parts


class _TursoCursor:
    def __init__(self, result: dict, conn: _TursoConn):
        self._result = result or {}
        self._conn = conn
        self.lastrowid = None

    @staticmethod
    def _decode_cell(cell):
        if isinstance(cell, dict):
            t = cell.get("type")
            v = cell.get("value")
            if t == "integer":
                return int(v) if v is not None else None
            if t == "float":
                return float(v) if v is not None else None
            if t == "null":
                return None
            if t == "blob":
                return bytes.fromhex(v) if v else b""
            return v
        return cell

    def _row_to_dict(self, row):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c)
                for i, c in enumerate(self._result.get("cols", []))]
        if isinstance(row, dict):
            return {cols[i]: self._decode_cell(row[i]) for i in range(len(cols))}
        return {cols[i]: self._decode_cell(row[i]) for i in range(len(cols))}

    def fetchone(self):
        rows = self._result.get("rows", [])
        if not rows:
            return None
        return self._row_to_dict(rows[0])

    def fetchall(self):
        rows = self._result.get("rows", [])
        return [self._row_to_dict(r) for r in rows]


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self._conn = None

        turso_url = os.environ.get("TURSO_URL")
        turso_token = os.environ.get("TURSO_AUTH_TOKEN")

        if turso_url and turso_token:
            self._conn = _TursoConn(turso_url, turso_token)
            self._backend = "turso"
        else:
            if db_path is None:
                db_path = os.environ.get("DB_PATH")
            if db_path is None:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_dir = os.path.join(project_root, "data")
                os.makedirs(db_dir, exist_ok=True)
                db_path = os.path.join(db_dir, "locus.db")
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self.db_path = db_path
            self._backend = "sqlite"

        self._init_schema()

    @contextmanager
    def _connect(self):
        if self._backend == "turso":
            yield self._conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    sow_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE(user_id, name)
                );

                CREATE TABLE IF NOT EXISTS monthly_values (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    value REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (asset_id) REFERENCES assets(id),
                    UNIQUE(asset_id, month)
                );

                CREATE TABLE IF NOT EXISTS forecast_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    sow_type TEXT,
                    growth_rate REAL,
                    min_growth_rate REAL,
                    max_growth_rate REAL,
                    monthly_contribution REAL,
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_assets_user_id ON assets(user_id);
                CREATE INDEX IF NOT EXISTS idx_monthly_values_asset_id ON monthly_values(asset_id);
                CREATE INDEX IF NOT EXISTS idx_forecast_configs_user_id ON forecast_configs(user_id);

                CREATE TABLE IF NOT EXISTS user_sow_overrides (
                    user_id INTEGER NOT NULL,
                    sow_type TEXT NOT NULL,
                    annual_growth REAL,
                    monthly_contribution REAL,
                    min_growth REAL,
                    max_growth REAL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, sow_type),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _insert_and_get_id(self, conn, sql, params) -> int:
        result = conn.execute(sql, params)
        if self._backend == "turso":
            rid = getattr(result, "lastrowid", None)
            if rid is None:
                raise RuntimeError(f"Failed to get rowid after insert: {sql}")
            return rid
        else:
            return result.lastrowid

    def create_user(self, username: str, email: str, password: str) -> int:
        now = datetime.utcnow().isoformat()
        pw_hash = self._hash_password(password)
        with self._connect() as conn:
            return self._insert_and_get_id(
                conn,
                "INSERT INTO users (username, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (username, email, pw_hash, now, now),
            )

    def authenticate_user(self, username: str, password: str) -> Optional[dict]:
        pw_hash = self._hash_password(password)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, email FROM users WHERE (username = ? OR email = ?) AND password_hash = ?",
                (username, username, pw_hash),
            ).fetchone()
            if row:
                return {"id": row["id"], "username": row["username"], "email": row["email"]}
            return None

    def get_user(self, user_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, email, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row:
                return dict(row)
            return None

    def list_users(self) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, username, email, created_at FROM users ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]

    def create_asset(self, user_id: int, name: str, sow_type: str) -> int:
        if sow_type not in SOW_TYPES:
            raise ValueError(f"Invalid SOW type: {sow_type}. Available: {list(SOW_TYPES.keys())}")
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            return self._insert_and_get_id(
                conn,
                "INSERT INTO assets (user_id, name, sow_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, sow_type, now, now),
            )

    def get_asset(self, user_id: int, asset_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, user_id, name, sow_type FROM assets WHERE id = ? AND user_id = ?",
                (asset_id, user_id),
            ).fetchone()
            if row:
                return dict(row)
            return None

    def list_assets(self, user_id: int) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, sow_type, created_at FROM assets WHERE user_id = ? ORDER BY name",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_asset(self, user_id: int, asset_id: int, name: Optional[str] = None, sow_type: Optional[str] = None):
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if sow_type is not None:
            if sow_type not in SOW_TYPES:
                raise ValueError(f"Invalid SOW type: {sow_type}")
            updates.append("sow_type = ?")
            params.append(sow_type)
        if not updates:
            return
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(asset_id)
        params.append(user_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE assets SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )

    def delete_asset(self, user_id: int, asset_id: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM monthly_values WHERE asset_id IN (SELECT id FROM assets WHERE id = ? AND user_id = ?)",
                (asset_id, user_id),
            )
            conn.execute(
                "DELETE FROM assets WHERE id = ? AND user_id = ?",
                (asset_id, user_id),
            )

    def set_monthly_value(self, user_id: int, asset_id: int, month: str, value: float):
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO monthly_values (asset_id, month, value, created_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(asset_id, month) DO UPDATE SET value = excluded.value",
                (asset_id, month, value, now),
            )

    def batch_set_monthly_values(self, user_id: int, asset_id: int, values: Dict[str, float]):
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            statements = [
                (
                    "INSERT INTO monthly_values (asset_id, month, value, created_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(asset_id, month) DO UPDATE SET value = excluded.value",
                    [asset_id, month, value, now],
                )
                for month, value in values.items()
            ]
            if self._backend == "turso":
                conn._send(statements)
            else:
                for sql, params in statements:
                    conn.execute(sql, params)

    def delete_monthly_value(self, user_id: int, asset_id: int, month: str):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM monthly_values WHERE asset_id = ? AND month = ? "
                "AND asset_id IN (SELECT id FROM assets WHERE id = ? AND user_id = ?)",
                (asset_id, month, asset_id, user_id),
            )

    def get_asset_monthly_values(self, user_id: int, asset_id: int) -> Dict[str, float]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT m.month, m.value FROM monthly_values m "
                "JOIN assets a ON m.asset_id = a.id "
                "WHERE a.id = ? AND a.user_id = ? "
                "ORDER BY m.month",
                (asset_id, user_id),
            ).fetchall()
            return {row["month"]: row["value"] for row in rows}

    def load_user_sow_data(self, user_id: int) -> List[dict]:
        with self._connect() as conn:
            assets = conn.execute(
                "SELECT id, name, sow_type FROM assets WHERE user_id = ? ORDER BY name",
                (user_id,),
            ).fetchall()

            result = []
            for asset in assets:
                monthly_rows = conn.execute(
                    "SELECT month, value FROM monthly_values WHERE asset_id = ? ORDER BY month",
                    (asset["id"],),
                ).fetchall()
                result.append({
                    "name": asset["name"],
                    "sow_type": asset["sow_type"],
                    "monthly_values": {r["month"]: r["value"] for r in monthly_rows},
                })
            return result

    def save_forecast_config(
        self,
        user_id: int,
        name: str,
        sow_type: Optional[str] = None,
        growth_rate: Optional[float] = None,
        min_growth_rate: Optional[float] = None,
        max_growth_rate: Optional[float] = None,
        monthly_contribution: Optional[float] = None,
        is_default: bool = False,
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            return self._insert_and_get_id(
                conn,
                "INSERT INTO forecast_configs (user_id, name, sow_type, growth_rate, min_growth_rate, max_growth_rate, monthly_contribution, is_default, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, sow_type, growth_rate, min_growth_rate, max_growth_rate, monthly_contribution, int(is_default), now),
            )

    def list_forecast_configs(self, user_id: int) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, sow_type, growth_rate, min_growth_rate, max_growth_rate, monthly_contribution, is_default "
                "FROM forecast_configs WHERE user_id = ? ORDER BY name",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_forecast_config(self, user_id: int, config_id: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM forecast_configs WHERE id = ? AND user_id = ?",
                (config_id, user_id),
            )

    def import_excel_to_user(self, user_id: int, excel_path: str) -> int:
        from excel_parser import load_excel

        sow_list = load_excel(excel_path)
        imported = 0

        for sow in sow_list:
            try:
                asset_id = self.create_asset(user_id, sow.name, sow.sow_type)
                self.batch_set_monthly_values(user_id, asset_id, sow.monthly_values)
                imported += 1
            except Exception:
                with self._connect() as conn:
                    existing = conn.execute(
                        "SELECT id FROM assets WHERE user_id = ? AND name = ?",
                        (user_id, sow.name),
                    ).fetchone()
                if existing:
                    self.batch_set_monthly_values(user_id, existing["id"], sow.monthly_values)
                    imported += 1
        return imported

    def get_user_sow_overrides(self, user_id: int) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT sow_type, annual_growth, monthly_contribution, min_growth, max_growth "
                "FROM user_sow_overrides WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {
            r["sow_type"]: {
                "annual_growth": r["annual_growth"],
                "monthly_contribution": r["monthly_contribution"],
                "min_growth": r["min_growth"],
                "max_growth": r["max_growth"],
            }
            for r in rows
        }

    def set_user_sow_overrides(self, user_id: int, overrides: dict) -> None:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            for sow_type, fields in overrides.items():
                conn.execute(
                    "INSERT INTO user_sow_overrides "
                    "(user_id, sow_type, annual_growth, monthly_contribution, min_growth, max_growth, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(user_id, sow_type) DO UPDATE SET "
                    "annual_growth=excluded.annual_growth, "
                    "monthly_contribution=excluded.monthly_contribution, "
                    "min_growth=excluded.min_growth, "
                    "max_growth=excluded.max_growth, "
                    "updated_at=excluded.updated_at",
                    (
                        user_id,
                        sow_type,
                        fields.get("annual_growth"),
                        fields.get("monthly_contribution"),
                        fields.get("min_growth"),
                        fields.get("max_growth"),
                        now,
                    ),
                )

    def delete_user_sow_override(self, user_id: int, sow_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM user_sow_overrides WHERE user_id = ? AND sow_type = ?",
                (user_id, sow_type),
            )