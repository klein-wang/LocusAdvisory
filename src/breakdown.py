from typing import Dict, List

from excel_parser import SOWData
from sow_types import get_sow_type


def compute_monthly_totals(
    sow_list: List[SOWData],
    extra_monthly: Dict[str, Dict[str, float]] = None,
) -> Dict[str, float]:
    totals: Dict[str, float] = {}

    for sow in sow_list:
        for month, value in sow.monthly_values.items():
            totals[month] = totals.get(month, 0.0) + value

    if extra_monthly:
        for sow_name, months_data in extra_monthly.items():
            for month, value in months_data.items():
                totals[month] = totals.get(month, 0.0) + value

    return totals


def compute_percentage_breakdown(
    sow_list: List[SOWData],
    target_months: List[str],
    extra_monthly: Dict[str, Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    sow_values: Dict[str, Dict[str, float]] = {}

    for sow in sow_list:
        sow_values[sow.name] = {}
        for month, value in sow.monthly_values.items():
            sow_values[sow.name][month] = value

    if extra_monthly:
        for sow_name, months_data in extra_monthly.items():
            if sow_name not in sow_values:
                sow_values[sow_name] = {}
            for month, value in months_data.items():
                sow_values[sow_name][month] = value

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
) -> Dict[str, Dict[str, float]]:
    sow_name_to_type = {s.name: s.sow_type for s in sow_list}

    type_totals: Dict[str, Dict[str, float]] = {}

    for sow in sow_list:
        stype = sow.sow_type
        if stype not in type_totals:
            type_totals[stype] = {}

        for month, value in sow.monthly_values.items():
            type_totals[stype][month] = (
                type_totals[stype].get(month, 0.0) + value
            )

    if extra_monthly:
        for sow_name, months_data in extra_monthly.items():
            stype = sow_name_to_type.get(sow_name, "other")
            if stype not in type_totals:
                type_totals[stype] = {}
            for month, value in months_data.items():
                type_totals[stype][month] = (
                    type_totals[stype].get(month, 0.0) + value
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
) -> Dict[str, Dict[str, float]]:
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
            is_asset = get_sow_type(sow.sow_type).is_asset
            if is_asset:
                assets += val
            else:
                liabilities += abs(val)

        if extra_monthly:
            for sow_name, months_data in extra_monthly.items():
                val = months_data.get(month, 0.0)
                if val == 0:
                    continue
                stype = sow_name_to_type.get(sow_name, "investment")
                is_asset = get_sow_type(stype).is_asset
                if is_asset:
                    assets += val
                else:
                    liabilities += abs(val)

        result["assets"][month] = round(assets, 2)
        result["liabilities"][month] = round(liabilities, 2)
        result["net_worth"][month] = round(assets - liabilities, 2)

    return result


def compute_net_worth_growth(
    sow_list: List[SOWData],
    target_months: List[str],
    extra_monthly: Dict[str, Dict[str, float]] = None,
) -> Dict[str, float]:
    result = compute_asset_vs_liability(
        sow_list, target_months, extra_monthly
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