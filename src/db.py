import os
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sow_types import SOW_TYPES


class Database:
    def __init__(self, db_path: Optional[str] = None):
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
        self._init_schema()

    @contextmanager
    def _connect(self):
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
            """)

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, username: str, email: str, password: str) -> int:
        now = datetime.utcnow().isoformat()
        pw_hash = self._hash_password(password)
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (username, email, pw_hash, now, now),
            )
            return cursor.lastrowid

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
            cursor = conn.execute(
                "INSERT INTO assets (user_id, name, sow_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, sow_type, now, now),
            )
            return cursor.lastrowid

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
            for month, value in values.items():
                conn.execute(
                    "INSERT INTO monthly_values (asset_id, month, value, created_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(asset_id, month) DO UPDATE SET value = excluded.value",
                    (asset_id, month, value, now),
                )

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
            cursor = conn.execute(
                "INSERT INTO forecast_configs (user_id, name, sow_type, growth_rate, min_growth_rate, max_growth_rate, monthly_contribution, is_default, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, sow_type, growth_rate, min_growth_rate, max_growth_rate, monthly_contribution, int(is_default), now),
            )
            return cursor.lastrowid

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
            except sqlite3.IntegrityError:
                existing = conn.execute(
                    "SELECT id FROM assets WHERE user_id = ? AND name = ?",
                    (user_id, sow.name),
                ).fetchone()
                if existing:
                    self.batch_set_monthly_values(user_id, existing["id"], sow.monthly_values)
                    imported += 1

        return imported