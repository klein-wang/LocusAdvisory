import argparse
import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from excel_parser import load_excel, SOWData, get_month_range
from forecast_engine import (
    forecast_portfolio,
    get_forecast_months,
)
from breakdown import (
    compute_monthly_totals,
    compute_percentage_breakdown,
    compute_type_breakdown,
    compute_asset_vs_liability,
    compute_net_worth_growth,
)
from sow_types import SOW_TYPES, get_sow_type


def run_pipeline(
    excel_path: str,
    forecast_months: int = 12,
    growth_overrides: Optional[Dict[str, float]] = None,
    contribution_overrides: Optional[Dict[str, float]] = None,
    sow_contribution_overrides: Optional[Dict[str, float]] = None,
) -> dict:
    sow_list = load_excel(excel_path)

    if not sow_list:
        return {"error": "No SOW data found in the Excel file."}

    forecasts = forecast_portfolio(
        sow_list=sow_list,
        forecast_months=forecast_months,
        growth_overrides=growth_overrides,
        contribution_overrides=contribution_overrides,
        sow_contribution_overrides=sow_contribution_overrides,
    )

    forecast_month_labels = get_forecast_months(sow_list, forecast_months)

    target_months = sorted(set(forecast_month_labels))

    monthly_totals = compute_monthly_totals(sow_list, forecasts)
    sow_pct = compute_percentage_breakdown(sow_list, target_months, forecasts)
    type_pct = compute_type_breakdown(sow_list, target_months, forecasts)
    asset_liability = compute_asset_vs_liability(sow_list, target_months, forecasts)
    net_worth_growth = compute_net_worth_growth(sow_list, target_months, forecasts)

    sow_summaries = []
    for sow in sow_list:
        stype_info = get_sow_type(sow.sow_type)
        sow_forecast = forecasts.get(sow.name, {})
        latest_val = sow.latest_value
        forecast_end_val = 0.0
        if sow_forecast:
            sorted_fm = sorted(sow_forecast.keys())
            forecast_end_val = sow_forecast[sorted_fm[-1]]

        type_pct_map = type_pct.get(sow.sow_type, {})
        latest_type_pct = 0.0
        if target_months:
            latest_type_pct = type_pct_map.get(target_months[-1], 0.0)

        sow_summaries.append({
            "name": sow.name,
            "sow_type": sow.sow_type,
            "type_label": stype_info.label,
            "is_asset": stype_info.is_asset,
            "latest_historical_month": sow.latest_month,
            "latest_historical_value": latest_val,
            "forecast_end_value": round(forecast_end_val, 2),
            "forecast_growth_pct": round(
                ((forecast_end_val - latest_val) / abs(latest_val) * 100)
                if latest_val != 0 else 0.0, 2
            ),
            "type_pct_of_total_forecast": latest_type_pct,
        })

    used_types = set(s.sow_type for s in sow_list)
    type_summary = {}
    for stype_key, stype_info in SOW_TYPES.items():
        if stype_key not in used_types:
            continue

        pct_data = type_pct.get(stype_key, {})
        values_by_month = {}
        for m in target_months:
            pct = pct_data.get(m, 0.0)
            values_by_month[m] = round(pct, 2)

        type_total = 0.0
        for sow in sow_list:
            if sow.sow_type == stype_key:
                forecast_sow = forecasts.get(sow.name, {})
                if target_months:
                    latest_tm = target_months[-1]
                    type_total += forecast_sow.get(latest_tm, sow.latest_value)

        if values_by_month:
            latest_pct = values_by_month[target_months[-1]]
        else:
            latest_pct = 0.0

        type_summary[stype_key] = {
            "label": stype_info.label,
            "is_asset": stype_info.is_asset,
            "forecast_end_value": round(type_total, 2),
            "forecast_end_pct": latest_pct,
            "monthly_pct_breakdown": values_by_month,
        }

    return {
        "sow_summaries": sow_summaries,
        "type_summary": type_summary,
        "forecast_months": forecast_month_labels,
        "monthly_totals": monthly_totals,
        "sow_percentage": sow_pct,
        "type_percentage": type_pct,
        "asset_vs_liability": asset_liability,
        "net_worth_growth": net_worth_growth,
        "forecasts": forecasts,
        "assumptions": _build_assumptions(sow_list, growth_overrides, contribution_overrides, sow_contribution_overrides),
    }


def _build_assumptions(
    sow_list: List[SOWData],
    growth_overrides: Optional[Dict[str, float]],
    contribution_overrides: Optional[Dict[str, float]],
    sow_contribution_overrides: Optional[Dict[str, float]] = None,
) -> dict:
    growth_overrides = growth_overrides or {}
    contribution_overrides = contribution_overrides or {}
    sow_contribution_overrides = sow_contribution_overrides or {}

    used_types = set(s.sow_type for s in sow_list)
    assumptions = {}

    for stype in used_types:
        info = get_sow_type(stype)
        assumptions[stype] = {
            "label": info.label,
            "growth_rate": growth_overrides.get(
                stype, info.default_annual_growth
            ),
            "monthly_contribution": contribution_overrides.get(
                stype, info.default_monthly_contribution
            ),
            "source": "override"
            if stype in growth_overrides or stype in contribution_overrides
            else "default",
        }

    for sow_name, amount in sow_contribution_overrides.items():
        for sow in sow_list:
            if sow.name == sow_name:
                stype = sow.sow_type
                if stype not in assumptions:
                    info = get_sow_type(stype)
                    assumptions[stype] = {
                        "label": info.label,
                        "growth_rate": growth_overrides.get(
                            stype, info.default_annual_growth
                        ),
                        "monthly_contribution": info.default_monthly_contribution,
                        "source": "default",
                    }
                assumptions[stype].setdefault("sow_overrides", {})
                assumptions[stype]["sow_overrides"][sow_name] = amount
                break

    return assumptions


def main():
    parser = argparse.ArgumentParser(
        description="LocusAdvisory - Wealth Forecast & Breakdown Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser(
        "generate-sample",
        help="Generate a sample Excel file with wealth data",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run the forecast pipeline on an Excel file",
    )
    run_parser.add_argument(
        "--excel",
        required=True,
        help="Path to the Excel file",
    )
    run_parser.add_argument(
        "--forecast-months",
        type=int,
        default=12,
        help="Number of months to forecast (default: 12)",
    )
    run_parser.add_argument(
        "--growth",
        type=str,
        default="",
        help="Growth rate overrides: type=rate,type=rate (e.g., investment=0.08,cash=0.05)",
    )
    run_parser.add_argument(
        "--contribution",
        type=str,
        default="",
        help="Monthly contribution overrides by type: type=amount,type=amount (e.g., investment=500)",
    )
    run_parser.add_argument(
        "--sow-contribution",
        type=str,
        default="",
        help="Monthly contribution overrides by SOW name: name=amount,name=amount (e.g., 'HSBC Savings=35000')",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output file path for JSON results (default: print to stdout)",
    )
    run_parser.add_argument(
        "--visualize",
        action="store_true",
        default=False,
        help="Generate an interactive HTML dashboard with charts",
    )

    args = parser.parse_args()

    if args.command == "generate-sample":
        from generate_sample import generate_sample_excel

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(project_root, "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "sample_wealth_data.xlsx")
        result_path = generate_sample_excel(path)
        print(f"Sample Excel generated: {result_path}")
        return

    elif args.command == "run":
        growth_overrides = {}
        if args.growth:
            for pair in args.growth.split(","):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    growth_overrides[key.strip()] = float(val.strip())

        contribution_overrides = {}
        if args.contribution:
            for pair in args.contribution.split(","):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    contribution_overrides[key.strip()] = float(val.strip())

        sow_contribution_overrides = {}
        if args.sow_contribution:
            for pair in args.sow_contribution.split(","):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    sow_contribution_overrides[key.strip()] = float(val.strip())

        result = run_pipeline(
            excel_path=args.excel,
            forecast_months=args.forecast_months,
            growth_overrides=growth_overrides or None,
            contribution_overrides=contribution_overrides or None,
            sow_contribution_overrides=sow_contribution_overrides or None,
        )

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Results saved to: {args.output}")
        else:
            print(json.dumps(result, indent=2, default=str))

        if args.visualize:
            from visualize import generate_visualizations
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_out_dir = os.path.join(project_root, "output")
            out_dir = os.path.dirname(os.path.abspath(args.output)) if args.output else default_out_dir
            os.makedirs(out_dir, exist_ok=True)
            viz_files = generate_visualizations(result, out_dir)
            for vf in viz_files:
                print(f"Visualization generated: {vf}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()