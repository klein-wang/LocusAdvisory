import argparse
import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from excel_parser import load_excel, SOWData, get_month_range
from forecast_engine import (
    forecast_portfolio,
    forecast_portfolio_stochastic,
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
    stochastic: bool = False,
    min_growth_overrides: Optional[Dict[str, float]] = None,
    max_growth_overrides: Optional[Dict[str, float]] = None,
    monte_carlo_runs: int = 500,
) -> dict:
    sow_list = load_excel(excel_path)

    if not sow_list:
        return {"error": "No SOW data found in the Excel file."}

    return run_pipeline_from_sow_list(
        sow_list=sow_list,
        forecast_months=forecast_months,
        growth_overrides=growth_overrides,
        contribution_overrides=contribution_overrides,
        sow_contribution_overrides=sow_contribution_overrides,
        stochastic=stochastic,
        min_growth_overrides=min_growth_overrides,
        max_growth_overrides=max_growth_overrides,
        monte_carlo_runs=monte_carlo_runs,
    )


def run_pipeline_from_sow_list(
    sow_list: List[SOWData],
    forecast_months: int = 12,
    growth_overrides: Optional[Dict[str, float]] = None,
    contribution_overrides: Optional[Dict[str, float]] = None,
    sow_contribution_overrides: Optional[Dict[str, float]] = None,
    stochastic: bool = False,
    min_growth_overrides: Optional[Dict[str, float]] = None,
    max_growth_overrides: Optional[Dict[str, float]] = None,
    monte_carlo_runs: int = 500,
) -> dict:
    growth_overrides = growth_overrides or {}
    contribution_overrides = contribution_overrides or {}
    sow_contribution_overrides = sow_contribution_overrides or {}
    min_growth_overrides = min_growth_overrides or {}
    max_growth_overrides = max_growth_overrides or {}

    if stochastic:
        forecasts = forecast_portfolio_stochastic(
            sow_list=sow_list,
            forecast_months=forecast_months,
            growth_overrides=growth_overrides or None,
            contribution_overrides=contribution_overrides or None,
            sow_contribution_overrides=sow_contribution_overrides or None,
            min_growth_overrides=min_growth_overrides or None,
            max_growth_overrides=max_growth_overrides or None,
            monte_carlo_runs=monte_carlo_runs,
        )

        deterministic_forecasts = {}
        for name, stoch_data in forecasts.items():
            deterministic_forecasts[name] = stoch_data.get("deterministic", {})
        forecasts_for_breakdown = deterministic_forecasts
    else:
        forecasts = forecast_portfolio(
            sow_list=sow_list,
            forecast_months=forecast_months,
            growth_overrides=growth_overrides or None,
            contribution_overrides=contribution_overrides or None,
            sow_contribution_overrides=sow_contribution_overrides or None,
        )
        forecasts_for_breakdown = forecasts

    forecast_month_labels = get_forecast_months(sow_list, forecast_months)
    target_months = sorted(set(forecast_month_labels))

    monthly_totals = compute_monthly_totals(sow_list, forecasts_for_breakdown)
    sow_pct = compute_percentage_breakdown(sow_list, target_months, forecasts_for_breakdown)
    type_pct = compute_type_breakdown(sow_list, target_months, forecasts_for_breakdown)
    asset_liability = compute_asset_vs_liability(sow_list, target_months, forecasts_for_breakdown)
    net_worth_growth = compute_net_worth_growth(sow_list, target_months, forecasts_for_breakdown)

    sow_summaries = []
    for sow in sow_list:
        stype_info = get_sow_type(sow.sow_type)
        sow_forecast = forecasts_for_breakdown.get(sow.name, {})
        latest_val = sow.latest_value
        forecast_end_val = 0.0
        if sow_forecast:
            sorted_fm = sorted(sow_forecast.keys())
            forecast_end_val = sow_forecast[sorted_fm[-1]]

        type_pct_map = type_pct.get(sow.sow_type, {})
        latest_type_pct = 0.0
        if target_months:
            latest_type_pct = type_pct_map.get(target_months[-1], 0.0)

        sow_summary = {
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
        }

        if stochastic and sow.name in forecasts:
            stoch_data = forecasts[sow.name]
            monte_carlo = stoch_data.get("monte_carlo", {})
            if monte_carlo:
                sorted_mc_months = sorted(monte_carlo.keys())
                if sorted_mc_months:
                    last_mc = monte_carlo[sorted_mc_months[-1]]
                    sow_summary["monte_carlo_end"] = last_mc
            trend = stoch_data.get("trend", {})
            if trend:
                sorted_trend_months = sorted(trend.keys())
                if sorted_trend_months:
                    sow_summary["trend_end_value"] = round(trend[sorted_trend_months[-1]], 2)
            scenarios = stoch_data.get("scenarios", {})
            if scenarios:
                sow_summary["scenario_end_values"] = {
                    k: round(v[sorted(v.keys())[-1]], 2) if v and sorted(v.keys()) else 0.0
                    for k, v in scenarios.items()
                }

        sow_summaries.append(sow_summary)

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
                forecast_sow = forecasts_for_breakdown.get(sow.name, {})
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

    result = {
        "sow_summaries": sow_summaries,
        "type_summary": type_summary,
        "forecast_months": forecast_month_labels,
        "monthly_totals": monthly_totals,
        "sow_percentage": sow_pct,
        "type_percentage": type_pct,
        "asset_vs_liability": asset_liability,
        "net_worth_growth": net_worth_growth,
        "forecasts": forecasts,
        "assumptions": _build_assumptions(
            sow_list, growth_overrides, contribution_overrides,
            sow_contribution_overrides, min_growth_overrides, max_growth_overrides,
            stochastic,
        ),
    }

    if stochastic:
        result["forecasts"] = forecasts_for_breakdown
        result["stochastic_forecasts"] = forecasts
        result["stochastic_summary"] = _build_stochastic_summary(forecasts, sow_list)

    return result


def _build_assumptions(
    sow_list: List[SOWData],
    growth_overrides: Optional[Dict[str, float]],
    contribution_overrides: Optional[Dict[str, float]],
    sow_contribution_overrides: Optional[Dict[str, float]] = None,
    min_growth_overrides: Optional[Dict[str, float]] = None,
    max_growth_overrides: Optional[Dict[str, float]] = None,
    stochastic: bool = False,
) -> dict:
    growth_overrides = growth_overrides or {}
    contribution_overrides = contribution_overrides or {}
    sow_contribution_overrides = sow_contribution_overrides or {}
    min_growth_overrides = min_growth_overrides or {}
    max_growth_overrides = max_growth_overrides or {}

    used_types = set(s.sow_type for s in sow_list)
    assumptions = {}

    for stype in used_types:
        info = get_sow_type(stype)
        entry = {
            "label": info.label,
            "growth_rate": growth_overrides.get(stype, info.default_annual_growth),
            "monthly_contribution": contribution_overrides.get(stype, info.default_monthly_contribution),
            "source": "override" if stype in growth_overrides or stype in contribution_overrides else "default",
        }
        if stochastic:
            entry["min_growth_rate"] = min_growth_overrides.get(stype, entry["growth_rate"])
            entry["max_growth_rate"] = max_growth_overrides.get(stype, entry["growth_rate"])
        assumptions[stype] = entry

    for sow_name, amount in sow_contribution_overrides.items():
        for sow in sow_list:
            if sow.name == sow_name:
                stype = sow.sow_type
                if stype not in assumptions:
                    info = get_sow_type(stype)
                    assumptions[stype] = {
                        "label": info.label,
                        "growth_rate": growth_overrides.get(stype, info.default_annual_growth),
                        "monthly_contribution": info.default_monthly_contribution,
                        "source": "default",
                    }
                    if stochastic:
                        assumptions[stype]["min_growth_rate"] = min_growth_overrides.get(stype, info.default_annual_growth)
                        assumptions[stype]["max_growth_rate"] = max_growth_overrides.get(stype, info.default_annual_growth)
                assumptions[stype].setdefault("sow_overrides", {})
                assumptions[stype]["sow_overrides"][sow_name] = amount
                break

    return assumptions


def _build_stochastic_summary(forecasts: dict, sow_list: List[SOWData]) -> dict:
    summary = {"portfolio": {}, "by_sow": {}}

    p5_totals = {}
    p50_totals = {}
    p95_totals = {}

    for sow in sow_list:
        stoch_data = forecasts.get(sow.name, {})
        monte_carlo = stoch_data.get("monte_carlo", {})
        trend = stoch_data.get("trend", {})
        scenarios = stoch_data.get("scenarios", {})

        sow_summary = {}
        if monte_carlo:
            sorted_months = sorted(monte_carlo.keys())
            if sorted_months:
                sow_summary["monte_carlo"] = monte_carlo[sorted_months[-1]]

                for month, vals in monte_carlo.items():
                    p5_totals[month] = p5_totals.get(month, 0.0) + vals["p5"]
                    p50_totals[month] = p50_totals.get(month, 0.0) + vals["p50"]
                    p95_totals[month] = p95_totals.get(month, 0.0) + vals["p95"]

        if trend:
            sorted_trend = sorted(trend.keys())
            if sorted_trend:
                sow_summary["trend_end"] = round(trend[sorted_trend[-1]], 2)

        if scenarios:
            sow_summary["scenarios_end"] = {}
            for name, vals in scenarios.items():
                if vals:
                    sorted_v = sorted(vals.keys())
                    sow_summary["scenarios_end"][name] = round(vals[sorted_v[-1]], 2)

        summary["by_sow"][sow.name] = sow_summary

    portfolio_mc = {}
    all_months = set(p50_totals.keys()) | set(p5_totals.keys()) | set(p95_totals.keys())
    for month in sorted(all_months):
        portfolio_mc[month] = {
            "p5": round(p5_totals.get(month, 0.0), 2),
            "p50": round(p50_totals.get(month, 0.0), 2),
            "p95": round(p95_totals.get(month, 0.0), 2),
        }
    summary["portfolio"]["monte_carlo"] = portfolio_mc

    return summary


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
        help="Monthly contribution overrides by SOW name: name=amount,name=amount",
    )
    run_parser.add_argument(
        "--min-growth",
        type=str,
        default="",
        help="Min growth rate overrides (stochastic mode): type=rate,type=rate",
    )
    run_parser.add_argument(
        "--max-growth",
        type=str,
        default="",
        help="Max growth rate overrides (stochastic mode): type=rate,type=rate",
    )
    run_parser.add_argument(
        "--stochastic",
        action="store_true",
        default=False,
        help="Enable stochastic forecasting (Monte Carlo + trend + scenarios)",
    )
    run_parser.add_argument(
        "--monte-carlo-runs",
        type=int,
        default=500,
        help="Number of Monte Carlo simulations (default: 500)",
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

    run_db_parser = subparsers.add_parser(
        "run-db",
        help="Run the forecast pipeline using user data from the database",
    )
    run_db_parser.add_argument(
        "--user-id",
        type=int,
        required=True,
        help="User ID to load data from",
    )
    run_db_parser.add_argument(
        "--forecast-months",
        type=int,
        default=12,
        help="Number of months to forecast (default: 12)",
    )
    run_db_parser.add_argument(
        "--growth",
        type=str,
        default="",
        help="Growth rate overrides: type=rate,type=rate",
    )
    run_db_parser.add_argument(
        "--contribution",
        type=str,
        default="",
        help="Monthly contribution overrides by type",
    )
    run_db_parser.add_argument(
        "--sow-contribution",
        type=str,
        default="",
        help="Monthly contribution overrides by SOW name",
    )
    run_db_parser.add_argument(
        "--min-growth",
        type=str,
        default="",
        help="Min growth rate overrides (stochastic mode)",
    )
    run_db_parser.add_argument(
        "--max-growth",
        type=str,
        default="",
        help="Max growth rate overrides (stochastic mode)",
    )
    run_db_parser.add_argument(
        "--stochastic",
        action="store_true",
        default=False,
        help="Enable stochastic forecasting",
    )
    run_db_parser.add_argument(
        "--monte-carlo-runs",
        type=int,
        default=500,
        help="Number of Monte Carlo simulations (default: 500)",
    )
    run_db_parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output file path for JSON results",
    )
    run_db_parser.add_argument(
        "--visualize",
        action="store_true",
        default=False,
        help="Generate an interactive HTML dashboard",
    )

    user_create_parser = subparsers.add_parser(
        "user-create",
        help="Create a new user account in the database",
    )
    user_create_parser.add_argument("--username", required=True)
    user_create_parser.add_argument("--email", required=True)
    user_create_parser.add_argument("--password", required=True)

    user_list_parser = subparsers.add_parser(
        "user-list",
        help="List all users in the database",
    )

    import_parser = subparsers.add_parser(
        "db-import",
        help="Import Excel data into a user's database account",
    )
    import_parser.add_argument("--user-id", type=int, required=True)
    import_parser.add_argument("--excel", required=True)

    asset_list_parser = subparsers.add_parser(
        "asset-list",
        help="List all assets for a user",
    )
    asset_list_parser.add_argument("--user-id", type=int, required=True)

    asset_add_parser = subparsers.add_parser(
        "asset-add",
        help="Add an asset for a user",
    )
    asset_add_parser.add_argument("--user-id", type=int, required=True)
    asset_add_parser.add_argument("--name", required=True)
    asset_add_parser.add_argument("--sow-type", required=True)

    asset_delete_parser = subparsers.add_parser(
        "asset-delete",
        help="Delete an asset for a user",
    )
    asset_delete_parser.add_argument("--user-id", type=int, required=True)
    asset_delete_parser.add_argument("--asset-id", type=int, required=True)

    mv_add_parser = subparsers.add_parser(
        "mv-add",
        help="Add a monthly value for an asset",
    )
    mv_add_parser.add_argument("--user-id", type=int, required=True)
    mv_add_parser.add_argument("--asset-id", type=int, required=True)
    mv_add_parser.add_argument("--month", required=True, help="Format: YYYY-MM")
    mv_add_parser.add_argument("--value", type=float, required=True)

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

        min_growth_overrides = {}
        if args.min_growth:
            for pair in args.min_growth.split(","):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    min_growth_overrides[key.strip()] = float(val.strip())

        max_growth_overrides = {}
        if args.max_growth:
            for pair in args.max_growth.split(","):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    max_growth_overrides[key.strip()] = float(val.strip())

        result = run_pipeline(
            excel_path=args.excel,
            forecast_months=args.forecast_months,
            growth_overrides=growth_overrides or None,
            contribution_overrides=contribution_overrides or None,
            sow_contribution_overrides=sow_contribution_overrides or None,
            stochastic=args.stochastic,
            min_growth_overrides=min_growth_overrides or None,
            max_growth_overrides=max_growth_overrides or None,
            monte_carlo_runs=args.monte_carlo_runs,
        )

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"Results saved to: {args.output}")
        else:
            print(json.dumps(result, indent=2, default=str))

        if args.visualize:
            _generate_visualizations(result, args.output)

    elif args.command == "run-db":
        from db import Database
        from db_loader import load_user_sow_data

        db = Database()
        sow_list = load_user_sow_data(db, args.user_id)

        if not sow_list:
            print(f"No asset data found for user {args.user_id}.")
            return

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

        min_growth_overrides = {}
        if args.min_growth:
            for pair in args.min_growth.split(","):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    min_growth_overrides[key.strip()] = float(val.strip())

        max_growth_overrides = {}
        if args.max_growth:
            for pair in args.max_growth.split(","):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    max_growth_overrides[key.strip()] = float(val.strip())

        result = run_pipeline_from_sow_list(
            sow_list=sow_list,
            forecast_months=args.forecast_months,
            growth_overrides=growth_overrides or None,
            contribution_overrides=contribution_overrides or None,
            sow_contribution_overrides=sow_contribution_overrides or None,
            stochastic=args.stochastic,
            min_growth_overrides=min_growth_overrides or None,
            max_growth_overrides=max_growth_overrides or None,
            monte_carlo_runs=args.monte_carlo_runs,
        )

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"Results saved to: {args.output}")
        else:
            print(json.dumps(result, indent=2, default=str))

        if args.visualize:
            _generate_visualizations(result, args.output)

    elif args.command == "user-create":
        from db import Database
        db = Database()
        try:
            user_id = db.create_user(args.username, args.email, args.password)
            print(f"User created: id={user_id}, username={args.username}")
        except Exception as e:
            print(f"Error creating user: {e}")

    elif args.command == "user-list":
        from db import Database
        db = Database()
        users = db.list_users()
        if not users:
            print("No users found.")
        else:
            for u in users:
                print(f"  [{u['id']}] {u['username']} ({u['email']}) - created: {u['created_at']}")

    elif args.command == "db-import":
        from db import Database
        db = Database()
        try:
            count = db.import_excel_to_user(args.user_id, args.excel)
            print(f"Imported/updated {count} assets for user {args.user_id}")
        except Exception as e:
            print(f"Error importing: {e}")

    elif args.command == "asset-list":
        from db import Database
        db = Database()
        assets = db.list_assets(args.user_id)
        if not assets:
            print(f"No assets found for user {args.user_id}")
        else:
            for a in assets:
                print(f"  [{a['id']}] {a['name']} ({a['sow_type']})")

    elif args.command == "asset-add":
        from db import Database
        db = Database()
        try:
            asset_id = db.create_asset(args.user_id, args.name, args.sow_type)
            print(f"Asset added: id={asset_id}, name={args.name}, type={args.sow_type}")
        except Exception as e:
            print(f"Error adding asset: {e}")

    elif args.command == "asset-delete":
        from db import Database
        db = Database()
        db.delete_asset(args.user_id, args.asset_id)
        print(f"Asset {args.asset_id} deleted for user {args.user_id}")

    elif args.command == "mv-add":
        from db import Database
        db = Database()
        db.set_monthly_value(args.user_id, args.asset_id, args.month, args.value)
        print(f"Monthly value added: asset={args.asset_id}, month={args.month}, value={args.value}")

    else:
        parser.print_help()


def _generate_visualizations(result: dict, output_path: str = ""):
    from visualize import generate_visualizations
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_out_dir = os.path.join(project_root, "output")
    out_dir = os.path.dirname(os.path.abspath(output_path)) if output_path else default_out_dir
    os.makedirs(out_dir, exist_ok=True)
    viz_files = generate_visualizations(result, out_dir)
    for vf in viz_files:
        print(f"Visualization generated: {vf}")


if __name__ == "__main__":
    main()