from typing import Dict, List, Optional

from sow_types import get_sow_type
from excel_parser import SOWData, get_month_range


def forecast_sow(
    sow: SOWData,
    forecast_months: int = 12,
    growth_rate: Optional[float] = None,
    monthly_contribution: Optional[float] = None,
    start_month: Optional[str] = None,
) -> Dict[str, float]:
    if not sow.monthly_values:
        return {}

    if start_month is None:
        start_month = sow.latest_month

    if growth_rate is None:
        growth_rate = get_sow_type(sow.sow_type).default_annual_growth

    if monthly_contribution is None:
        monthly_contribution = (
            get_sow_type(sow.sow_type).default_monthly_contribution
        )

    monthly_growth_rate = (1 + growth_rate) ** (1 / 12) - 1

    last_value = sow.get_value(start_month)
    if last_value == 0:
        prev_months = [m for m in sow.months if m <= start_month]
        if prev_months:
            last_value = sow.get_value(prev_months[-1])
        if last_value == 0:
            valid_months = [
                (m, v)
                for m, v in sorted(sow.monthly_values.items())
                if v != 0
            ]
            if valid_months:
                last_value = valid_months[-1][1]

    forecasted: Dict[str, float] = {}
    current_value = last_value

    all_future_months = get_month_range(start_month, forecast_months + 1)
    try:
        start_idx = all_future_months.index(start_month)
    except ValueError:
        start_idx = 0

    for i in range(start_idx + 1, len(all_future_months)):
        month = all_future_months[i]
        current_value = (
            current_value * (1 + monthly_growth_rate) + monthly_contribution
        )
        forecasted[month] = round(current_value, 2)

    return forecasted


def forecast_portfolio(
    sow_list: List[SOWData],
    forecast_months: int = 12,
    growth_overrides: Optional[Dict[str, float]] = None,
    contribution_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    growth_overrides = growth_overrides or {}
    contribution_overrides = contribution_overrides or {}

    all_months: set = set()
    for sow in sow_list:
        all_months.update(sow.monthly_values.keys())

    if not all_months:
        return {}

    sorted_months = sorted(all_months)
    start_month = sorted_months[-1]

    forecasted: Dict[str, Dict[str, float]] = {}
    for sow in sow_list:
        override_growth = growth_overrides.get(sow.sow_type)
        override_contribution = contribution_overrides.get(sow.sow_type)

        result = forecast_sow(
            sow=sow,
            forecast_months=forecast_months,
            growth_rate=override_growth,
            monthly_contribution=override_contribution,
            start_month=start_month,
        )
        forecasted[sow.name] = result

    return forecasted


def get_forecast_months(
    sow_list: List[SOWData],
    forecast_months: int = 12,
) -> List[str]:
    all_months: set = set()
    for sow in sow_list:
        all_months.update(sow.monthly_values.keys())

    if not all_months:
        return []

    sorted_months = sorted(all_months)
    start_month = sorted_months[-1]
    return get_month_range(start_month, forecast_months + 1)[1:]