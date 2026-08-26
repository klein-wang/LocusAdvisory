import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sow_types import get_sow_type
from excel_parser import SOWData, get_month_range


@dataclass
class ForecastConfig:
    growth_rate: Optional[float] = None
    min_growth_rate: Optional[float] = None
    max_growth_rate: Optional[float] = None
    monthly_contribution: Optional[float] = None
    volatility: Optional[float] = None
    monte_carlo_runs: int = 500
    seed: Optional[int] = None


def _extract_params(
    sow: SOWData,
    config: Optional[ForecastConfig] = None,
) -> Tuple[float, float, float, float, Optional[float]]:
    sow_type = get_sow_type(sow.sow_type)

    if config:
        growth_rate = config.growth_rate if config.growth_rate is not None else sow_type.default_annual_growth
        monthly_contribution = config.monthly_contribution if config.monthly_contribution is not None else sow_type.default_monthly_contribution
        min_growth_rate = config.min_growth_rate if config.min_growth_rate is not None else growth_rate
        max_growth_rate = config.max_growth_rate if config.max_growth_rate is not None else growth_rate
        volatility = config.volatility
    else:
        growth_rate = sow_type.default_annual_growth
        monthly_contribution = sow_type.default_monthly_contribution
        min_growth_rate = growth_rate
        max_growth_rate = growth_rate
        volatility = None

    return growth_rate, monthly_contribution, min_growth_rate, max_growth_rate, volatility


def _get_last_value(sow: SOWData, start_month: str) -> float:
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
    return last_value


def _compute_monthly_returns(sow: SOWData) -> List[float]:
    sorted_months = sow.months
    if len(sorted_months) < 2:
        return []

    returns = []
    for i in range(1, len(sorted_months)):
        prev_val = sow.monthly_values.get(sorted_months[i - 1], 0)
        curr_val = sow.monthly_values.get(sorted_months[i], 0)
        if prev_val != 0:
            returns.append((curr_val - prev_val) / abs(prev_val))
    return returns


def _compute_volatility(sow: SOWData) -> float:
    returns = _compute_monthly_returns(sow)
    if len(returns) < 2:
        return 0.02

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


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

    last_value = _get_last_value(sow, start_month)

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


def forecast_sow_monte_carlo(
    sow: SOWData,
    forecast_months: int = 12,
    config: Optional[ForecastConfig] = None,
    start_month: Optional[str] = None,
) -> Dict[str, Dict[str, float]]:
    if not sow.monthly_values:
        return {}

    if start_month is None:
        start_month = sow.latest_month

    growth_rate, monthly_contribution, min_gr, max_gr, _ = _extract_params(sow, config)

    volatility = (config.volatility if config else None) or _compute_volatility(sow)

    if config and config.seed is not None:
        rng = random.Random(config.seed)
    else:
        rng = random.Random()

    num_runs = config.monte_carlo_runs if config else 500

    all_future_months = get_month_range(start_month, forecast_months + 1)
    try:
        start_idx = all_future_months.index(start_month)
    except ValueError:
        start_idx = 0

    future_months = all_future_months[start_idx + 1:]

    if not future_months:
        return {}

    last_value = _get_last_value(sow, start_month)

    simulation_results: List[Dict[str, float]] = []
    for _ in range(num_runs):
        sim_values: Dict[str, float] = {}
        current_value = last_value
        for month in future_months:
            sampled_rate = rng.uniform(min_gr, max_gr)
            monthly_rate = (1 + sampled_rate) ** (1 / 12) - 1
            shock = rng.gauss(0, volatility)
            current_value = (
                current_value * (1 + monthly_rate + shock) + monthly_contribution
            )
            sim_values[month] = current_value
        simulation_results.append(sim_values)

    result: Dict[str, Dict[str, float]] = {}
    for month in future_months:
        month_values = sorted([sim[month] for sim in simulation_results])
        n = len(month_values)
        p5 = month_values[max(0, int(n * 0.05))]
        p50 = month_values[max(0, int(n * 0.50))]
        p95 = month_values[min(n - 1, int(n * 0.95))]
        result[month] = {
            "p5": round(p5, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
        }

    return result


def forecast_sow_trend(
    sow: SOWData,
    forecast_months: int = 12,
    start_month: Optional[str] = None,
) -> Dict[str, float]:
    if not sow.monthly_values:
        return {}

    if start_month is None:
        start_month = sow.latest_month

    sorted_months = sow.months
    if len(sorted_months) < 2:
        return {}

    n = len(sorted_months)
    xs = list(range(n))
    ys = [sow.monthly_values[m] for m in sorted_months]

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return {}

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    all_future_months = get_month_range(start_month, forecast_months + 1)
    try:
        start_idx = all_future_months.index(start_month)
    except ValueError:
        start_idx = 0

    future_months = all_future_months[start_idx + 1:]

    last_value = _get_last_value(sow, start_month)
    last_x = xs[-1] if xs else 0

    forecasted: Dict[str, float] = {}
    for i, month in enumerate(future_months):
        future_x = last_x + i + 1
        predicted = intercept + slope * future_x
        forecasted[month] = round(predicted, 2)

    return forecasted


def forecast_sow_scenarios(
    sow: SOWData,
    forecast_months: int = 12,
    config: Optional[ForecastConfig] = None,
    start_month: Optional[str] = None,
) -> Dict[str, Dict[str, float]]:
    if not sow.monthly_values:
        return {}

    if start_month is None:
        start_month = sow.latest_month

    growth_rate, monthly_contribution, min_gr, max_gr, _ = _extract_params(sow, config)

    conservative_rate = min_gr
    aggressive_rate = max_gr
    moderate_rate = (min_gr + max_gr) / 2

    scenarios = {
        "conservative": conservative_rate,
        "moderate": moderate_rate,
        "aggressive": aggressive_rate,
    }

    result: Dict[str, Dict[str, float]] = {}
    for scenario_name, rate in scenarios.items():
        values = forecast_sow(
            sow=sow,
            forecast_months=forecast_months,
            growth_rate=rate,
            monthly_contribution=monthly_contribution,
            start_month=start_month,
        )
        result[scenario_name] = values

    return result


def forecast_sow_stochastic(
    sow: SOWData,
    forecast_months: int = 12,
    config: Optional[ForecastConfig] = None,
    start_month: Optional[str] = None,
) -> Dict[str, any]:
    if not sow.monthly_values:
        return {}

    if start_month is None:
        start_month = sow.latest_month

    growth_rate, monthly_contribution, min_gr, max_gr, _ = _extract_params(sow, config)

    deterministic = forecast_sow(
        sow=sow,
        forecast_months=forecast_months,
        growth_rate=growth_rate,
        monthly_contribution=monthly_contribution,
        start_month=start_month,
    )

    monte_carlo = forecast_sow_monte_carlo(
        sow=sow,
        forecast_months=forecast_months,
        config=config,
        start_month=start_month,
    )

    trend = forecast_sow_trend(
        sow=sow,
        forecast_months=forecast_months,
        start_month=start_month,
    )

    scenarios = forecast_sow_scenarios(
        sow=sow,
        forecast_months=forecast_months,
        config=config,
        start_month=start_month,
    )

    return {
        "deterministic": deterministic,
        "monte_carlo": monte_carlo,
        "trend": trend,
        "scenarios": scenarios,
    }


def forecast_portfolio(
    sow_list: List[SOWData],
    forecast_months: int = 12,
    growth_overrides: Optional[Dict[str, float]] = None,
    contribution_overrides: Optional[Dict[str, float]] = None,
    sow_contribution_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    growth_overrides = growth_overrides or {}
    contribution_overrides = contribution_overrides or {}
    sow_contribution_overrides = sow_contribution_overrides or {}

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

        if sow.name in sow_contribution_overrides:
            override_contribution = sow_contribution_overrides[sow.name]
        else:
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


def forecast_portfolio_stochastic(
    sow_list: List[SOWData],
    forecast_months: int = 12,
    growth_overrides: Optional[Dict[str, float]] = None,
    contribution_overrides: Optional[Dict[str, float]] = None,
    sow_contribution_overrides: Optional[Dict[str, float]] = None,
    min_growth_overrides: Optional[Dict[str, float]] = None,
    max_growth_overrides: Optional[Dict[str, float]] = None,
    monte_carlo_runs: int = 500,
) -> Dict[str, Dict[str, any]]:
    growth_overrides = growth_overrides or {}
    contribution_overrides = contribution_overrides or {}
    sow_contribution_overrides = sow_contribution_overrides or {}
    min_growth_overrides = min_growth_overrides or {}
    max_growth_overrides = max_growth_overrides or {}

    all_months: set = set()
    for sow in sow_list:
        all_months.update(sow.monthly_values.keys())

    if not all_months:
        return {}

    sorted_months = sorted(all_months)
    start_month = sorted_months[-1]

    forecasted: Dict[str, Dict[str, any]] = {}
    for sow in sow_list:
        override_growth = growth_overrides.get(sow.sow_type)

        if sow.name in sow_contribution_overrides:
            override_contribution = sow_contribution_overrides[sow.name]
        else:
            override_contribution = contribution_overrides.get(sow.sow_type)

        override_min = min_growth_overrides.get(sow.sow_type)
        override_max = max_growth_overrides.get(sow.sow_type)

        config = ForecastConfig(
            growth_rate=override_growth,
            min_growth_rate=override_min,
            max_growth_rate=override_max,
            monthly_contribution=override_contribution,
            monte_carlo_runs=monte_carlo_runs,
        )

        result = forecast_sow_stochastic(
            sow=sow,
            forecast_months=forecast_months,
            config=config,
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