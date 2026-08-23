# LocusAdvisory

Personal wealth dashboard with forward-looking projections. See your net worth, track your goals, and forecast your financial future.

## Highlights

- **Unified net worth view** — Consolidate 9 asset classes (cash, savings, investments, retirement, real estate, crypto, personal property, income, credit) into a single, clear dashboard.
- **Goal-aware projections** — 12-month deterministic forecasting shows whether you're on track for retirement, a home purchase, or other life milestones.
- **User-controllable assumptions** — Adjust growth rates, inflation, and contribution plans to stress-test your financial future.
- **Interactive visualizations** — Generate an HTML dashboard with trend lines, bar charts, and allocation pie charts to visualize your forecast at a glance.
- **Per-SOW contribution targeting** — Allocate monthly contributions to specific assets (e.g., "HSBC Savings=25000") in addition to type-level overrides.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate Sample Data

Creates `output/sample_wealth_data.xlsx` with 11 SOWs across the system-defined types, spanning 12 months of historical data (2025-01 through 2025-12).

```bash
python3 src/main.py generate-sample
```

### 3. Run the Forecast Pipeline

Reads the Excel, projects 12 months forward, and outputs a JSON report with forecasts, percentage breakdowns, and net worth growth.

```bash
python3 src/main.py run --excel output/sample_wealth_data.xlsx --forecast-months 12
```

### 4. View the Dashboard

Add `--visualize` to generate an interactive HTML dashboard with Chart.js:

```bash
python3 src/main.py run --excel output/sample_wealth_data.xlsx --output output/forecast.json --visualize
```

This creates `output/forecast_dashboard.html`. Open it in any browser to see:
- **KPI cards** — Start/End net worth, total growth %, monthly CAGR
- **Trend line chart** — Each SOW asset as its own colored line (liabilities on a separate axis)
- **Bar chart** — Forecast end values by SOW name
- **Doughnut chart** — Asset allocation by type
- **Detail table** — Per-SOW latest value, forecast end, and growth %

Serve it locally:
```bash
cd output && python3 -m http.server 8000
# then open http://localhost:8000/forecast_dashboard.html
```

> **Troubleshooting "Address already in use"**: If the port is occupied, kill the process first:
> ```bash
> lsof -ti:8000 | xargs kill -9
> ```
> Or use a different port: `python3 -m http.server 9000`

### 5. Run Tests

```bash
python3 -m unittest test_pipeline -v
```

## Usage Examples

```bash
# Output results to a file
python3 src/main.py run --excel output/sample_wealth_data.xlsx --output output/results.json

# Override growth rates per SOW type
python3 src/main.py run --excel output/sample_wealth_data.xlsx \
    --growth investment=0.08,retirement=0.06,cash=0.05

# Override monthly contributions per SOW type
python3 src/main.py run --excel output/sample_wealth_data.xlsx \
    --contribution investment=200,retirement=1500

# Target contributions to specific SOWs by name
python3 src/main.py run --excel output/my_assets.xlsx \
    --sow-contribution "HSBC Savings=25000,Longbridge Investment=10000"

# Combine all overrides with visualization
python3 src/main.py run --excel output/my_assets.xlsx \
    --growth savings=0.035,investment=0.045,credit=0.0 \
    --sow-contribution "HSBC Savings=25000" \
    --forecast-months 12 \
    --output output/forecast.json \
    --visualize

# Note: Monthly expenses (rent, credit card, etc.) are deducted from net
# savings before allocating to assets. In the example above, $25,000 is
# the net after income - rent ($7k) - expenses ($10k credit card).
# If you do NOT pay off a credit card monthly, use a negative
# --sow-contribution to model accumulating debt, e.g.:
#   --sow-contribution "HS Travel Credit=-10000"
```

## CLI Flags

| Flag | Description |
|------|-------------|
| `--excel` | Path to the Excel file (required) |
| `--forecast-months` | Number of months to forecast (default: 12) |
| `--growth` | Growth rate overrides by type: `type=rate,type=rate` |
| `--contribution` | Monthly contribution overrides by type: `type=amount,type=amount` |
| `--sow-contribution` | Monthly contribution overrides by SOW name: `name=amount,name=amount` |
| `--output` | Output path for JSON results (prints to stdout if omitted) |
| `--visualize` | Generate `forecast_dashboard.html` with interactive charts |

## Excel Format

The Excel file must follow this structure:

| SOW Name | SOW Type | 2025-01 | 2025-02 | 2025-03 | ... |
|----------|----------|---------|---------|---------|-----|
| Primary Salary | income | 8500 | 8700 | 8900 | ... |
| Index Fund | investment | 25000 | 26250 | 27563 | ... |
| Credit Card Balance | credit | -3500 | -3200 | -2900 | ... |

- **SOW Name** (Column A): User-defined label for each source of wealth
- **SOW Type** (Column B): System-defined category — must be one of the 9 types below
- **Monthly Columns** (Columns C+): Each column is a month in `YYYY-MM` format; values are dollar amounts (use negative for debts)

### System-Defined SOW Types

| Type | Label | Asset? | Default Annual Growth |
|------|-------|--------|----------------------|
| `cash` | Cash & Equivalents | Yes | 0% |
| `savings` | Savings Accounts | Yes | 3.5% |
| `income` | Stable Income | Yes | 4% |
| `investment` | Investments | Yes | 7% |
| `retirement` | Retirement Accounts | Yes | 7% |
| `real_estate` | Real Estate | Yes | 4% |
| `crypto` | Crypto Assets | Yes | 10% |
| `personal_property` | Personal Property | Yes | 2% |
| `credit` | Credit & Debt | **No** (liability) | 5% |

## Project Structure

```
LocusAdvisory/
├── src/                    # All source code
│   ├── sow_types.py
│   ├── excel_parser.py
│   ├── forecast_engine.py
│   ├── breakdown.py
│   ├── visualize.py
│   ├── main.py             # CLI entry point
│   ├── generate_sample.py
│   ├── generate_user_assets.py
│   └── test_pipeline.py
├── output/                 # All generated outputs
│   ├── sample_wealth_data.xlsx
│   ├── user_hkd_assets.xlsx
│   ├── forecast_final.json
│   └── forecast_dashboard.html
├── requirements.txt
├── prd.md
└── README.md
```

## Target User

- **Core**: Ages 28–42, household income $80K–$200K, multiple asset types — needs consolidation and retirement confidence.
- **Secondary**: New homeowners, new parents, career changers — needs scenario planning for major life transitions.
- **Future**: High-net-worth individuals — uses as a diagnostic tool alongside advisory relationships.