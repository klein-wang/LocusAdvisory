# LocusAdvisory

Personal wealth dashboard with forward-looking projections. See your net worth, track your goals, and forecast your financial future.

## Highlights

- **Unified net worth view** — Consolidate 6 asset classes (cash, investments, retirement, real estate, crypto, personal property) into a single, clear dashboard.
- **Goal-aware projections** — 12-month deterministic forecasting shows whether you're on track for retirement, a home purchase, or other life milestones.
- **User-controllable assumptions** — Adjust growth rates, inflation, and contribution plans to stress-test your financial future.
- **Clean, distraction-free UI** — No cluttered ads or unnecessary complexity. Designed for clarity, not engagement metrics.
- **Free to start, Premium to grow** — Core dashboard is free; Premium unlocks advanced projections and scenario planning.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate Sample Data

Creates `sample_wealth_data.xlsx` with 11 SOWs across 8 system-defined types, spanning 12 months of historical data (2025-01 through 2025-12).

```bash
python3 main.py generate-sample
```

### 3. Run the Forecast Pipeline

Reads the Excel, projects 12 months forward, and outputs a JSON report with forecasts, percentage breakdowns, and net worth growth.

```bash
python3 main.py run --excel sample_wealth_data.xlsx --forecast-months 12
```

### 4. Run Tests

```bash
python3 -m pytest test_pipeline.py -v
```

### Usage Examples

```bash
# Output results to a file
python3 main.py run --excel sample_wealth_data.xlsx --output results.json

# Override growth rates per SOW type
python3 main.py run --excel sample_wealth_data.xlsx \
    --growth investment=0.08,retirement=0.06,cash=0.05

# Override monthly contributions per SOW type
python3 main.py run --excel sample_wealth_data.xlsx \
    --contribution investment=200,retirement=1500

# Combine both overrides
python3 main.py run --excel sample_wealth_data.xlsx \
    --growth investment=0.08 \
    --contribution retirement=1500 \
    --forecast-months 24
```

## Excel Format

The Excel file must follow this structure:

| SOW Name | SOW Type | 2025-01 | 2025-02 | 2025-03 | ... |
|----------|----------|---------|---------|---------|-----|
| Primary Salary | income | 8500 | 8700 | 8900 | ... |
| Index Fund | investment | 25000 | 26250 | 27563 | ... |
| Credit Card Balance | credit | -3500 | -3200 | -2900 | ... |

- **SOW Name** (Column A): User-defined label for each source of wealth
- **SOW Type** (Column B): System-defined category — must be one of the 8 types below
- **Monthly Columns** (Columns C+): Each column is a month in `YYYY-MM` format; values are dollar amounts (use negative for debts)

### System-Defined SOW Types

| Type | Label | Asset? | Default Annual Growth |
|------|-------|--------|----------------------|
| `cash` | Cash & Equivalents | Yes | 3% |
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
├── sow_types.py          # System-defined SOW types & defaults
├── excel_parser.py       # Excel → SOWData parsing (pandas + openpyxl fallback)
├── forecast_engine.py    # 12-month deterministic forecasting
├── breakdown.py          # Percentage breakdowns & net worth analysis
├── main.py               # CLI entry point & pipeline orchestration
├── generate_sample.py    # Sample Excel generator
├── test_pipeline.py      # Unit tests
├── requirements.txt      # Dependencies
└── README.md
```

## Target User

- **Core**: Ages 28–42, household income $80K–$200K, multiple asset types — needs consolidation and retirement confidence.
- **Secondary**: New homeowners, new parents, career changers — needs scenario planning for major life transitions.
- **Future**: High-net-worth individuals — uses as a diagnostic tool alongside advisory relationships.