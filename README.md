# LocusAdvisory

Personal wealth dashboard with forward-looking projections. See your net worth, track your goals, and forecast your financial future.

## Highlights

- **Deterministic + Stochastic Forecasting** — Fixed-rate projection, Monte Carlo simulation (P5/P50/P95), linear trend extrapolation, and conservative/moderate/aggressive scenario analysis.
- **Multi-user Database** — SQLite-backed per-user asset management with access control. Each user's data is isolated.
- **Unified net worth view** — Consolidate 9 asset classes into a single dashboard.
- **Interactive visualizations** — HTML dashboard with trend lines, bar charts, doughnut allocation, and stochastic confidence bands.

## Quick Start

```bash
pip install -r requirements.txt
python3 src/main.py generate-sample          # Create sample Excel
python3 src/main.py run --excel output/sample_wealth_data.xlsx --visualize
```

## Start the Server
```bash
python3 src/web.py
```

## Stochastic Forecasting

```bash
python3 src/main.py run \
    --excel output/sample_wealth_data.xlsx \
    --stochastic \
    --min-growth investment=0.04,savings=0.02 \
    --max-growth investment=0.10,savings=0.05 \
    --monte-carlo-runs 500 \
    --visualize
```

| Flag | Description |
|------|-------------|
| `--stochastic` | Enable Monte Carlo + trend + scenario forecasting |
| `--min-growth` | Min growth rate per SOW type: `type=rate` |
| `--max-growth` | Max growth rate per SOW type: `type=rate` |
| `--monte-carlo-runs` | Number of simulation runs (default: 500) |

## Database Usage

```bash
# 1. Create a user
python3 src/main.py user-create --username alice --email alice@example.com --password secret123

# 2. Import Excel data into the user's account
python3 src/main.py db-import --user-id 1 --excel output/sample_wealth_data.xlsx

# 3. List, add, or delete assets
python3 src/main.py asset-list --user-id 1
python3 src/main.py asset-add --user-id 1 --name "Vanguard ETF" --sow-type investment
python3 src/main.py mv-add --user-id 1 --asset-id 3 --month 2025-12 --value 35000

# 4. Run forecast from database
python3 src/main.py run-db --user-id 1 --stochastic --visualize
```

All data is stored per-user in `data/locus.db`. Each user can only access their own assets and monthly values.

## CLI Flags

### `run` / `run-db` command flags

| Flag | Description |
|------|-------------|
| `--excel` | Path to Excel file (`run` only) |
| `--user-id` | User ID to load data from (`run-db` only) |
| `--forecast-months` | Months to forecast (default: 12) |
| `--growth` | Growth overrides: `type=rate,type=rate` |
| `--contribution` | Monthly contribution overrides: `type=amount` |
| `--sow-contribution` | Per-SOW contribution: `name=amount,name=amount` |
| `--min-growth` | Min growth for stochastic: `type=rate` |
| `--max-growth` | Max growth for stochastic: `type=rate` |
| `--stochastic` | Enable stochastic forecasting |
| `--monte-carlo-runs` | Simulation count (default: 500) |
| `--output` | Output JSON path (default: stdout) |
| `--visualize` | Generate HTML dashboard |

### Database command flags

| Command | Flags | Description |
|---------|-------|-------------|
| `user-create` | `--username --email --password` | Create user account |
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

SOW Types: `cash`, `savings`, `income`, `investment`, `retirement`, `real_estate`, `crypto`, `personal_property`, `credit`

## Project Structure

```
LocusAdvisory/
├── src/
│   ├── sow_types.py
│   ├── excel_parser.py
│   ├── forecast_engine.py    # Deterministic + stochastic forecasting
│   ├── breakdown.py
│   ├── visualize.py
│   ├── db.py                 # SQLite multi-user DB with access control
│   ├── db_loader.py          # Bridge between DB and SOWData
│   ├── main.py               # CLI entry point
│   ├── generate_sample.py
│   └── test_pipeline.py
├── data/                     # SQLite database (auto-created)
├── output/                   # Generated outputs
└── requirements.txt
```

## Tests

```bash
PYTHONPATH=src python3 -m unittest test_pipeline -v
```