from typing import Dict, List, Optional

from excel_parser import SOWData
from sow_types import get_sow_type
from currencies import convert_to_currency, DEFAULT_CURRENCY, DEFAULT_EXCHANGE_RATES


def _rates_or_default(rates: Optional[Dict[str, float]]) -> Dict[str, float]:
    return rates if rates else dict(DEFAULT_EXCHANGE_RATES)


def _convert_sow_monthly(
    sow: SOWData,
    target_currency: str,
    rates: Dict[str, float],
    extra_monthly_vals: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    converted = {}
    for month, value in sow.monthly_values.items():
        converted[month] = convert_to_currency(value, sow.currency, target_currency, rates)
    if extra_monthly_vals:
        extra_currency = getattr(extra_monthly_vals, '_currency', sow.currency)
        for month, value in extra_monthly_vals.items():
            converted[month] = converted.get(month, 0.0) + convert_to_currency(value, extra_currency, target_currency, rates)
    return converted


def compute_monthly_totals(
    sow_list: List[SOWData],
    extra_monthly: Dict[str, Dict[str, float]] = None,
    display_currency: str = DEFAULT_CURRENCY,
    currency_rates: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    rates = _rates_or_default(currency_rates)
    totals: Dict[str, float] = {}

    for sow in sow_list:
        for month, value in sow.monthly_values.items():
            converted = convert_to_currency(value, sow.currency, display_currency, rates)
            totals[month] = totals.get(month, 0.0) + converted

    if extra_monthly:
        for sow_name, months_data in extra_monthly.items():
            sow_currency = DEFAULT_CURRENCY
            for sow in sow_list:
                if sow.name == sow_name:
                    sow_currency = sow.currency
                    break
            for month, value in months_data.items():
                converted = convert_to_currency(value, sow_currency, display_currency, rates)
                totals[month] = totals.get(month, 0.0) + converted

    return {m: round(v, 2) for m, v in totals.items()}


def compute_percentage_breakdown(
    sow_list: List[SOWData],
    target_months: List[str],
    extra_monthly: Dict[str, Dict[str, float]] = None,
    display_currency: str = DEFAULT_CURRENCY,
    currency_rates: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    rates = _rates_or_default(currency_rates)
    sow_values: Dict[str, Dict[str, float]] = {}

    for sow in sow_list:
        sow_values[sow.name] = {}
        for month, value in sow.monthly_values.items():
            sow_values[sow.name][month] = convert_to_currency(value, sow.currency, display_currency, rates)

    if extra_monthly:
        for sow_name, months_data in extra_monthly.items():
            sow_currency = DEFAULT_CURRENCY
            for sow in sow_list:
                if sow.name == sow_name:
                    sow_currency = sow.currency
                    break
            if sow_name not in sow_values:
                sow_values[sow_name] = {}
            for month, value in months_data.items():
                sow_values[sow_name][month] = sow_values[sow_name].get(month, 0.0) + convert_to_currency(value, sow_currency, display_currency, rates)

    month_totals: Dict[str, float] = {}
    for sow_name, months_data in sow_values.items():
        for month, value in months_data.items():
            month_totals[month] = month_totals.get(month, 0.0) + value

    percentage: Dict[str, Dict[str, float]] = {}

    for month in target_months:
        month_total = month_totals.get(month, 0.0)
        if month_total == 0:
            continue

        for sow_name, months_data in sow_values.items():
            if sow_name not in percentage:
                percentage[sow_name] = {}
            val = months_data.get(month, 0.0)
            percentage[sow_name][month] = round(
                (val / month_total) * 100, 2
            )

    return percentage


def compute_type_breakdown(
    sow_list: List[SOWData],
    target_months: List[str],
    extra_monthly: Dict[str, Dict[str, float]] = None,
    display_currency: str = DEFAULT_CURRENCY,
    currency_rates: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    rates = _rates_or_default(currency_rates)
    sow_name_to_type = {s.name: s.sow_type for s in sow_list}

    type_totals: Dict[str, Dict[str, float]] = {}

    for sow in sow_list:
        stype = sow.sow_type
        if stype not in type_totals:
            type_totals[stype] = {}

        for month, value in sow.monthly_values.items():
            converted = convert_to_currency(value, sow.currency, display_currency, rates)
            type_totals[stype][month] = (
                type_totals[stype].get(month, 0.0) + converted
            )

    if extra_monthly:
        for sow_name, months_data in extra_monthly.items():
            stype = sow_name_to_type.get(sow_name, "other")
            sow_currency = DEFAULT_CURRENCY
            for sow in sow_list:
                if sow.name == sow_name:
                    sow_currency = sow.currency
                    break
            if stype not in type_totals:
                type_totals[stype] = {}
            for month, value in months_data.items():
                converted = convert_to_currency(value, sow_currency, display_currency, rates)
                type_totals[stype][month] = (
                    type_totals[stype].get(month, 0.0) + converted
                )

    grand_totals: Dict[str, float] = {}
    for stype, months_data in type_totals.items():
        for month, value in months_data.items():
            grand_totals[month] = grand_totals.get(month, 0.0) + value

    result: Dict[str, Dict[str, float]] = {}
    for stype, months_data in type_totals.items():
        result[stype] = {}
        for month in target_months:
            month_total = grand_totals.get(month, 0.0)
            if month_total > 0:
                result[stype][month] = round(
                    (months_data.get(month, 0.0) / month_total) * 100, 2
                )
            else:
                result[stype][month] = 0.0

    return result


def compute_asset_vs_liability(
    sow_list: List[SOWData],
    target_months: List[str],
    extra_monthly: Dict[str, Dict[str, float]] = None,
    display_currency: str = DEFAULT_CURRENCY,
    currency_rates: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    rates = _rates_or_default(currency_rates)
    sow_name_to_type = {s.name: s.sow_type for s in sow_list}

    result: Dict[str, Dict[str, float]] = {
        "assets": {},
        "liabilities": {},
        "net_worth": {},
    }

    for month in target_months:
        assets = 0.0
        liabilities = 0.0

        for sow in sow_list:
            val = sow.get_value(month)
            converted = convert_to_currency(val, sow.currency, display_currency, rates)
            is_asset = get_sow_type(sow.sow_type).is_asset
            if is_asset:
                assets += converted
            else:
                liabilities += abs(converted)

        if extra_monthly:
            for sow_name, months_data in extra_monthly.items():
                val = months_data.get(month, 0.0)
                if val == 0:
                    continue
                stype = sow_name_to_type.get(sow_name, "investment")
                sow_currency = DEFAULT_CURRENCY
                for sow in sow_list:
                    if sow.name == sow_name:
                        sow_currency = sow.currency
                        break
                converted = convert_to_currency(val, sow_currency, display_currency, rates)
                is_asset = get_sow_type(stype).is_asset
                if is_asset:
                    assets += converted
                else:
                    liabilities += abs(converted)

        result["assets"][month] = round(assets, 2)
        result["liabilities"][month] = round(liabilities, 2)
        result["net_worth"][month] = round(assets - liabilities, 2)

    return result


def compute_net_worth_growth(
    sow_list: List[SOWData],
    target_months: List[str],
    extra_monthly: Dict[str, Dict[str, float]] = None,
    display_currency: str = DEFAULT_CURRENCY,
    currency_rates: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    result = compute_asset_vs_liability(
        sow_list, target_months, extra_monthly,
        display_currency=display_currency,
        currency_rates=currency_rates,
    )

    net_worth_series = result["net_worth"]
    sorted_months = sorted(net_worth_series.keys())

    if len(sorted_months) < 2:
        return {}

    start_month = sorted_months[0]
    end_month = sorted_months[-1]
    start_val = net_worth_series[start_month]
    end_val = net_worth_series[end_month]

    if start_val == 0:
        total_growth_pct = 0.0
    else:
        total_growth_pct = round(
            ((end_val - start_val) / abs(start_val)) * 100, 2
        )

    months_count = len(sorted_months) - 1
    if months_count > 0 and start_val != 0:
        cagr = round(
            ((end_val / abs(start_val)) ** (1 / months_count) - 1) * 100, 2
        )
    else:
        cagr = 0.0

    return {
        "start_month": start_month,
        "end_month": end_month,
        "start_net_worth": start_val,
        "end_net_worth": end_val,
        "total_growth_pct": total_growth_pct,
        "monthly_cagr_pct": cagr,
    }