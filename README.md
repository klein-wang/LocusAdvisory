# LocusAdvisory

Personal wealth dashboard with forward-looking projections. Consolidate your assets, visualize your net worth, and forecast your financial future — with deterministic projections, Monte Carlo simulations, and scenario analysis.

## Features

- **Deterministic + Stochastic Forecasting** — Fixed-rate projection, Monte Carlo simulation (P5/P50/P95), linear trend extrapolation, and conservative/moderate/aggressive scenario analysis.
- **Multi-user Database** — SQLite-backed per-user asset management with strict access control. Each user's data is fully isolated.
- **Unified Net Worth View** — Consolidate 9 asset classes into a single dashboard.
- **Interactive Web App** — Single-page app with dark/light theme, dashboard, forecast engine, SOW data import/export, and currency conversion.
- **Email Auth Flow** — Registration via email verification code, username or email login, password reset via email, and feedback submission.
- **Dev-mode Fallbacks** — Email verification codes print to the browser console when no SMTP is configured, so local development is zero-config.

## Project Structure

```
LocusAdvisory/
├── .env.example                # Environment variable template
├── .gitignore
├── Procfile                    # Railway / Heroku entry (gunicorn)
├── gunicorn.conf.py
├── requirements.txt
│
├── src/                        # All library + app code
│   ├── config.py               # Centralized env var configuration
│   ├── web.py                  # Flask web app + API entry point
│   ├── main.py                 # CLI entry point (forecast, DB mgmt, sample gen)
│   ├── db.py                   # SQLite / Turso multi-user DB + auth
│   ├── emailer.py              # SMTP / dev-mode email sending
│   ├── sow_types.py            # 9 SOW type registry + default rates
│   ├── currencies.py           # Currency registry + default exchange rates
│   ├── excel_parser.py         # Excel → SOWData model
│   ├── db_loader.py            # Bridge: Database ↔ SOWData
│   ├── forecast_engine.py      # Deterministic + stochastic forecasting core
│   ├── breakdown.py            # Forecast result helpers (monthly totals, %, etc.)
│   ├── visualize.py            # HTML dashboard generation
│   ├── generate_sample.py      # Sample Excel generator (called by CLI)
│   ├── frontend.html           # Single-page app (served by web.py)
│   ├── __init__.py
│   ├── static/
│   │   └── logo.jpg
│   └── sample_data/
│       ├── sample_assets.xlsx
│       └── template_assets.xlsx
│
├── scripts/                    # One-off standalone utilities
│   └── generate_user_assets.py
│
├── tests/                      # Unit tests
│   └── test_pipeline.py
│
├── docs/                       # Product docs
│   ├── prd.md
│   └── MVP 产品设计文档.docx
│
├── data/                       # SQLite DB (auto-created, gitignored)
│   └── locus.db
└── output/                     # Generated files (gitignored)
    └── forecast_dashboard.html, *.xlsx, *.json
```

## Quick Start — Web App

```bash
cp .env.example .env            # then edit values as needed
pip install -r requirements.txt
python3 src/web.py              # http://127.0.0.1:5001
```

The web app provides:

| Tab | What it does |
|-----|-------------|
| **Welcome** | Guidance on using the platform, live stats overview, feedback form |
| **Dashboard** | Net worth trend, allocation doughnut, asset/liability bar charts |
| **Forecast** | Deterministic projection, Monte Carlo simulation, scenario analysis |
| **SOW Data** | Import from sample, add/edit/delete assets, record monthly values |
| **Currency** | Display currency selection + manual exchange rate overrides |
| **Settings** | Custom growth rate and contribution overrides per SOW type |

### Authentication

- **Register** — Choose username + email + password, enter a 6-digit verification code emailed to you.
- **Sign In** — Use **either** username or email as the identifier, plus password.
- **Forgot Password** — Request a verification code by email to reset.
- **Dev mode** — Without SMTP configured, verification codes appear in the browser console instead of being emailed.

## Quick Start — CLI

```bash
# Generate a sample Excel file
python3 src/main.py generate-sample

# Run forecast on an Excel file
python3 src/main.py run \
    --excel output/sample_wealth_data.xlsx \
    --stochastic \
    --monte-carlo-runs 500 \
    --visualize

# User management
python3 src/main.py user-create --username alice --email alice@example.com --password secret123
python3 src/main.py user-list

# Import Excel → DB, then forecast from DB
python3 src/main.py db-import --user-id 1 --excel output/sample_wealth_data.xlsx
python3 src/main.py run-db --user-id 1 --stochastic --visualize
```

## Stochastic Forecasting

```bash
python3 src/main.py run \
    --excel output/sample_wealth_data.xlsx \
    --stochastic \
    --min-growth investment=0.04 savings=0.02 \
    --max-growth investment=0.10 savings=0.05 \
    --monte-carlo-runs 500 \
    --forecast-months 36 \
    --visualize
```

| Flag | Description |
|------|-------------|
| `--stochastic` | Enable Monte Carlo + trend + scenario forecasting |
| `--min-growth` | Min growth rate per SOW type: `type=rate` |
| `--max-growth` | Max growth rate per SOW type: `type=rate` |
| `--monte-carlo-runs` | Number of simulation runs (default: 500) |
| `--forecast-months` | Months to forecast (default: 12) |
| `--visualize` | Generate HTML dashboard |
| `--output` | Output JSON path (default: stdout) |

## CLI Reference

### Forecast commands (`run` / `run-db`)

| Flag | Description |
|------|-------------|
| `--excel` | Path to Excel file (`run` only) |
| `--user-id` | User ID (`run-db` only) |
| `--forecast-months` | Months to forecast (default: 12) |
| `--growth` | Growth overrides: `type=rate type=rate` |
| `--contribution` | Monthly contribution overrides: `type=amount` |
| `--sow-contribution` | Per-SOW contribution: `name=amount name=amount` |
| `--min-growth` | Min growth for stochastic |
| `--max-growth` | Max growth for stochastic |
| `--stochastic` | Enable stochastic forecasting |
| `--monte-carlo-runs` | Simulation count (default: 500) |
| `--output` | Output JSON path |
| `--visualize` | Generate HTML dashboard |

### Database commands

| Command | Flags | Description |
|---------|-------|-------------|
| `user-create` | `--username --email --password` | Create user |
| `user-list` | | List all users |
| `db-import` | `--user-id --excel` | Import Excel into DB |
| `asset-list` | `--user-id` | List user's assets |
| `asset-add` | `--user-id --name --sow-type` | Add asset |
| `asset-delete` | `--user-id --asset-id` | Delete asset |
| `mv-add` | `--user-id --asset-id --month --value` | Add monthly value |

## Excel Format

| SOW Name | SOW Type | 2025-01 | 2025-02 | ... |
|----------|----------|---------|---------|-----|
| Primary Salary | income | 8500 | 8700 | ... |
| Index Fund | investment | 25000 | 26250 | ... |

**SOW Types** (9 total): `cash`, `savings`, `income`, `investment`, `retirement`, `real_estate`, `crypto`, `personal_property`, `credit`

## Environment Variables

All configuration lives in one place — `src/config.py`. Copy `.env.example` to `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | `dev-secret-change-in-production` | Flask session secret |
| `CORS_ORIGINS` | `*` | Allowed origins for web API |
| `PORT` | `5001` | Web server port |
| `DB_PATH` | `./data/locus.db` | SQLite file path |
| `TURSO_URL` | *(unset)* | Turso REST URL (enables cloud DB) |
| `TURSO_AUTH_TOKEN` | *(unset)* | Turso auth token |
| `SMTP_HOST` | *(unset)* | SMTP server — unset → dev mode (codes print to console) |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | *(unset)* | SMTP username |
| `SMTP_PASSWORD` | *(unset)* | SMTP password |
| `SMTP_USE_TLS` | `true` | Whether to use STARTTLS |
| `SMTP_FROM_EMAIL` | *(falls back to SMTP_USER)* | `From:` address for verification emails |
| `FEEDBACK_TO_EMAIL` | *(falls back to SMTP_USER)* | Where feedback submissions are forwarded |

### Dev-mode email

When `SMTP_HOST` or `SMTP_USER` is missing, the email system runs in dev mode:
- Verification codes are returned in the API response as `dev_code` and shown in the browser console
- Feedback submissions are logged to the console instead of emailed
- Verification is auto-approves email-verified accounts (no SMTP needed to register)

## Database

- **SQLite** (default) — stored at `data/locus.db` (auto-created)
- **Turso** — set `TURSO_URL` + `TURSO_AUTH_TOKEN` to switch to cloud-hosted SQLite

Schema (auto-created on first run):
- `users` — accounts with hashed passwords, optional email verification
- `assets` — per-user SOW definitions
- `monthly_values` — per-asset monthly balance history
- `verification_codes` — 6-digit codes with 15-min TTL for register/reset flows
- `feedback` — user-submitted comments + star ratings

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Deployment

This project is pre-configured for Railway or Heroku-style deployments:

```bash
git push origin main      # Procfile + gunicorn.conf.py handle the rest
```

Set env vars in the platform dashboard (`SECRET_KEY`, `DB_PATH`/Turso vars, SMTP vars, etc.).