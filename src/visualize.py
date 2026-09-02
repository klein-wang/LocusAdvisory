import json
import os
from typing import Dict, List


def generate_visualizations(forecast_data: dict, output_dir: str = ".") -> List[str]:
    files = []
    files.append(_write_trend_html(forecast_data, output_dir))
    return files


def _write_trend_html(forecast_data: dict, output_dir: str) -> str:
    from sow_types import SOW_TYPES

    sow_summaries = forecast_data.get("sow_summaries", [])
    forecasts = forecast_data.get("forecasts", {})
    stochastic_forecasts = forecast_data.get("stochastic_forecasts", {})
    stochastic_summary = forecast_data.get("stochastic_summary", {})
    net_worth_growth = forecast_data.get("net_worth_growth", {})
    type_summary = forecast_data.get("type_summary", {})
    assumptions = forecast_data.get("assumptions", {})

    sow_names = [s["name"] for s in sow_summaries]
    sow_type_map = {s["name"]: s["sow_type"] for s in sow_summaries}

    all_months_set = set()
    for sow_name in sow_names:
        for m in forecasts.get(sow_name, {}).keys():
            all_months_set.add(m)
    all_months = sorted(all_months_set)
    months_json = json.dumps(all_months)

    has_stochastic = bool(stochastic_forecasts)

    colors = [
        "#2ecc71", "#3498db", "#e74c3c", "#f39c12", "#9b59b6",
        "#1abc9c", "#e67e22", "#2980b9", "#27ae60", "#c0392b",
        "#16a085", "#d35400", "#8e44ad", "#2c3e50", "#f1c40f",
    ]

    datasets = []
    datasets_with_bands = []
    for idx, sow_name in enumerate(sow_names):
        fc_data = forecasts.get(sow_name, {})
        data_points = []
        for m in all_months:
            v = fc_data.get(m)
            data_points.append(round(v, 2) if v is not None else None)
        color = colors[idx % len(colors)]
        is_neg = sow_type_map.get(sow_name, "") == "credit"
        datasets.append({
            "label": sow_name,
            "data": data_points,
            "borderColor": color,
            "backgroundColor": color + "33",
            "yAxisID": "neg" if is_neg else "pos",
            "tension": 0.3,
            "pointRadius": 3,
            "spanGaps": False,
        })

        if has_stochastic and sow_name in stochastic_forecasts:
            stoch = stochastic_forecasts[sow_name]
            monte_carlo = stoch.get("monte_carlo", {})
            if monte_carlo:
                p5_data = []
                p95_data = []
                for m in all_months:
                    if m in monte_carlo:
                        p5_data.append(monte_carlo[m]["p5"])
                        p95_data.append(monte_carlo[m]["p95"])
                    else:
                        p5_data.append(None)
                        p95_data.append(None)
                datasets_with_bands.append({
                    "label": f"{sow_name} (P50)",
                    "data": data_points,
                    "borderColor": color,
                    "yAxisID": "neg" if is_neg else "pos",
                    "tension": 0.3,
                    "pointRadius": 3,
                    "spanGaps": False,
                    "p5": p5_data,
                    "p95": p95_data,
                    "isBand": True,
                })

    datasets_json = json.dumps(datasets)
    datasets_with_bands_json = json.dumps(datasets_with_bands)

    pie_labels = []
    pie_values = []
    pie_colors = []
    default_color_map = {
        "cash": "#f1c40f", "savings": "#3498db", "investment": "#2ecc71",
        "retirement": "#9b59b6", "real_estate": "#e67e22", "crypto": "#e74c3c",
        "personal_property": "#1abc9c", "credit": "#c0392b", "income": "#2980b9",
    }
    for st_key, st_info in type_summary.items():
        pie_labels.append(st_info["label"])
        pie_values.append(st_info["forecast_end_value"])
        pie_colors.append(default_color_map.get(st_key, "#95a5a6"))

    pie_labels_json = json.dumps(pie_labels)
    pie_values_json = json.dumps(pie_values)
    pie_colors_json = json.dumps(pie_colors)

    growth = net_worth_growth or {}
    total_growth = growth.get("total_growth_pct", 0)
    g_class = "positive" if total_growth >= 0 else "negative"
    g_arrow = "&#9650;" if total_growth >= 0 else "&#9660;"

    assumptions_html = ""
    for stype_key, asmp in assumptions.items():
        min_gr = asmp.get("min_growth_rate", "")
        max_gr = asmp.get("max_growth_rate", "")
        range_str = f" ({min_gr:.1%} - {max_gr:.1%})" if min_gr != "" else ""
        assumptions_html += f"""
      <tr>
        <td>{asmp['label']}</td>
        <td>{asmp['growth_rate']:.1%}{range_str}</td>
        <td>${asmp['monthly_contribution']:,.0f}</td>
        <td>{asmp.get('source', 'default')}</td>
      </tr>"""

    scenario_rows_html = ""
    if has_stochastic:
        for sow in sow_summaries:
            scenarios = sow.get("scenario_end_values", {})
            if scenarios:
                cons = scenarios.get("conservative", 0)
                mod = scenarios.get("moderate", 0)
                agg = scenarios.get("aggressive", 0)
                scenario_rows_html += f"""
              <tr>
                <td>{sow['name']}</td>
                <td>${cons:,.2f}</td>
                <td>${mod:,.2f}</td>
                <td>${agg:,.2f}</td>
              </tr>"""

    portfolio_mc = {}
    sorted_mc_months = []
    mc_portfolio_html = ""
    if has_stochastic:
        portfolio_mc = stochastic_summary.get("portfolio", {}).get("monte_carlo", {})
        if portfolio_mc:
            sorted_mc_months = sorted(portfolio_mc.keys())
            if sorted_mc_months:
                last_mc = portfolio_mc[sorted_mc_months[-1]]
                mc_portfolio_html = f"""
              <tr>
                <td>{sorted_mc_months[-1]}</td>
                <td>${last_mc['p5']:,.2f}</td>
                <td>${last_mc['p50']:,.2f}</td>
                <td>${last_mc['p95']:,.2f}</td>
              </tr>"""

    rows_html = ""
    for sow in sow_summaries:
        spct = sow.get("forecast_growth_pct", 0)
        spct_class = "positive" if spct >= 0 else "negative"

        mc_end = sow.get("monte_carlo_end", {})
        mc_str = ""
        if mc_end:
            mc_str = f'<br><span style="font-size:11px;color:#95a5a6">P5: ${mc_end.get("p5",0):,.0f} | P95: ${mc_end.get("p95",0):,.0f}</span>'

        trend_val = sow.get("trend_end_value")
        trend_str = ""
        if trend_val is not None:
            trend_str = f'<br><span style="font-size:11px;color:#95a5a6">Trend: ${trend_val:,.0f}</span>'

        rows_html += f"""
      <tr>
        <td>{sow['name']}</td>
        <td>{sow.get('type_label', '')}</td>
        <td>${sow.get('latest_historical_value', 0):,.2f}</td>
        <td>${sow.get('forecast_end_value', 0):,.2f}{mc_str}{trend_str}</td>
        <td class="{spct_class}">{spct:+.2f}%</td>
      </tr>"""

    stochastic_section = ""
    if has_stochastic and sorted_mc_months:
        last_mc_data = portfolio_mc.get(sorted_mc_months[-1], {})
        stochastic_section = f"""
  <div class="card">
    <h2>Stochastic Analysis <span class="section-label">Monte Carlo Simulation</span></h2>
    <p style="color:var(--muted);font-size:13px;margin:0 0 16px 0;">
      Forecasts use range-based growth rates with Monte Carlo simulation (500 runs) and historical volatility to produce confidence intervals.
    </p>
    <div class="kpi-row">
      <div class="kpi">
        <div class="label">Portfolio P5 (Bear Case)</div>
        <div class="value">${last_mc_data.get('p5', 0):,.0f}</div>
        <div class="sub">5th percentile forecast</div>
      </div>
      <div class="kpi">
        <div class="label">Portfolio P50 (Median)</div>
        <div class="value">${last_mc_data.get('p50', 0):,.0f}</div>
        <div class="sub">50th percentile forecast</div>
      </div>
      <div class="kpi">
        <div class="label">Portfolio P95 (Bull Case)</div>
        <div class="value">${last_mc_data.get('p95', 0):,.0f}</div>
        <div class="sub">95th percentile forecast</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Scenario Analysis</h2>
    <table>
      <thead><tr><th>SOW Name</th><th>Conservative (Min Growth)</th><th>Moderate (Mid Growth)</th><th>Aggressive (Max Growth)</th></tr></thead>
      <tbody>{scenario_rows_html}
      </tbody>
    </table>
  </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LocusAdvisory - Wealth Forecast Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #f5f6fa; --card: #ffffff; --text: #2c3e50; --muted: #7f8c8d;
    --border: #ecf0f1; --accent: #3498db; --pos: #27ae60; --neg: #e74c3c;
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); margin: 0; padding: 24px; color: var(--text); }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  .header {{ background: var(--card); border-radius: 12px; padding: 28px 32px; margin-bottom: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
  .header h1 {{ margin: 0 0 4px 0; font-size: 26px; }}
  .header .subtitle {{ color: var(--muted); font-size: 14px; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .kpi {{ background: var(--card); border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
  .kpi .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }}
  .kpi .value {{ font-size: 26px; font-weight: 700; }}
  .kpi .sub {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}
  .card {{ background: var(--card); border-radius: 12px; padding: 24px 28px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
  .card h2 {{ margin: 0 0 16px 0; font-size: 17px; }}
  .chart-wrap {{ position: relative; height: 460px; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 380px; gap: 24px; margin-bottom: 24px; }}
  @media (max-width: 900px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ padding: 11px 14px; text-align: right; border-bottom: 1px solid var(--border); font-size: 13px; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #f8f9fa; font-weight: 600; color: var(--text); }}
  .positive {{ color: var(--pos); }}
  .negative {{ color: var(--neg); }}
  .section-label {{ display: inline-block; background: var(--accent); color: #fff; padding: 2px 10px; border-radius: 10px; font-size: 11px; margin-left: 8px; vertical-align: middle; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; }}
  .tab {{ padding: 8px 16px; border-radius: 8px; cursor: pointer; background: #f0f2f5; font-size: 13px; font-weight: 500; }}
  .tab.active {{ background: var(--accent); color: #fff; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>LocusAdvisory - Wealth Forecast Dashboard</h1>
    <div class="subtitle">Projected 12-month growth & allocation across all SOW assets</div>
  </div>

  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Start Net Worth</div>
      <div class="value">${growth.get('start_net_worth', 0):,.0f}</div>
      <div class="sub">{growth.get('start_month', '')}</div>
    </div>
    <div class="kpi">
      <div class="label">Forecast End Net Worth</div>
      <div class="value">${growth.get('end_net_worth', 0):,.0f}</div>
      <div class="sub">{growth.get('end_month', '')}</div>
    </div>
    <div class="kpi">
      <div class="label">Total Growth</div>
      <div class="value {g_class}">{g_arrow} {total_growth:+.2f}%</div>
      <div class="sub">Over {growth.get('start_month','')} → {growth.get('end_month','')}</div>
    </div>
    <div class="kpi">
      <div class="label">Monthly CAGR</div>
      <div class="value">{growth.get('monthly_cagr_pct', 0):+.4f}%</div>
      <div class="sub">Compound monthly rate</div>
    </div>
  </div>

  {stochastic_section}

  <div class="card">
    <h2>Growth Trend by SOW Name <span class="section-label">Historical + Forecast</span></h2>
    <div class="chart-wrap"><canvas id="trendChart"></canvas></div>
  </div>

  <div class="chart-row">
    <div class="card" style="margin-bottom:0">
      <h2>Forecast End Value by SOW</h2>
      <div class="chart-wrap"><canvas id="barChart"></canvas></div>
    </div>
    <div class="card" style="margin-bottom:0">
      <h2>Asset Allocation</h2>
      <div class="chart-wrap" style="height:360px"><canvas id="pieChart"></canvas></div>
    </div>
  </div>

  <div class="card">
    <h2>Assumptions</h2>
    <table>
      <thead><tr><th>SOW Type</th><th>Growth Rate</th><th>Monthly Contribution</th><th>Source</th></tr></thead>
      <tbody>{assumptions_html}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>SOW Detail</h2>
    <table>
      <thead><tr><th>SOW Name</th><th>Type</th><th>Latest Value</th><th>Forecast End</th><th>Growth</th></tr></thead>
      <tbody>{rows_html}
      </tbody>
    </table>
  </div>
</div>

<script>
const months = {months_json};
const datasets = {datasets_json};
const datasetsWithBands = {datasets_with_bands_json};
const hasStochastic = {str(has_stochastic).lower()};

new Chart(document.getElementById('trendChart').getContext('2d'), {{
  type: 'line',
  data: {{ labels: months, datasets: datasets }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    interaction: {{ mode: 'index', intersect: false }},
    scales: {{
      x: {{ title: {{ display: true, text: 'Month' }}, grid: {{ color: '#ecf0f1' }} }},
      pos: {{ position: 'left', title: {{ display: true, text: 'Asset Value (HKD)' }}, grid: {{ color: '#ecf0f1' }}, ticks: {{ callback: v => '$' + v.toLocaleString() }} }},
      neg: {{ position: 'right', title: {{ display: true, text: 'Liability (HKD)' }}, grid: {{ display: false }}, ticks: {{ callback: v => '$' + v.toLocaleString() }} }}
    }},
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ usePointStyle: true, padding: 14, font: {{ size: 11 }} }} }},
      tooltip: {{ callbacks: {{ label: c => c.dataset.label + ': $' + (c.parsed.y == null ? 0 : c.parsed.y).toLocaleString() }} }}
    }}
  }}
}});

if (hasStochastic && datasetsWithBands.length > 0) {{
  const bandCtx = document.createElement('canvas').getContext('2d');
  datasetsWithBands.forEach(ds => {{
    if (ds.p5 && ds.p95) {{
      new Chart(bandCtx, {{
        type: 'line',
        data: {{
          labels: months,
          datasets: [
            {{
              label: ds.label + ' (P95 Upper)',
              data: ds.p95,
              borderColor: ds.borderColor + '44',
              backgroundColor: 'transparent',
              fill: '+1',
              tension: 0.3,
              pointRadius: 0,
              spanGaps: false,
              yAxisID: ds.yAxisID,
              borderWidth: 1,
            }},
            {{
              label: ds.label + ' (P5 Lower)',
              data: ds.p5,
              borderColor: ds.borderColor + '44',
              backgroundColor: ds.borderColor + '22',
              fill: '-1',
              tension: 0.3,
              pointRadius: 0,
              spanGaps: false,
              yAxisID: ds.yAxisID,
              borderWidth: 1,
            }},
            {{
              label: ds.label + ' (P50)',
              data: ds.data,
              borderColor: ds.borderColor,
              backgroundColor: 'transparent',
              tension: 0.3,
              pointRadius: 3,
              spanGaps: false,
              yAxisID: ds.yAxisID,
              borderWidth: 2,
            }}
          ]
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          interaction: {{ mode: 'index', intersect: false }},
          scales: {{
            x: {{ grid: {{ color: '#ecf0f1' }} }},
            pos: {{ position: 'left', grid: {{ color: '#ecf0f1' }}, ticks: {{ callback: v => '$' + v.toLocaleString() }} }},
            neg: {{ position: 'right', grid: {{ display: false }}, ticks: {{ callback: v => '$' + v.toLocaleString() }} }}
          }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{ callbacks: {{ label: c => c.dataset.label + ': $' + (c.parsed.y == null ? 0 : c.parsed.y).toLocaleString() }} }}
          }}
        }}
      }});
    }}
  }});
}}

const barColors = datasets.map(d => d.borderColor);
new Chart(document.getElementById('barChart').getContext('2d'), {{
  type: 'bar',
  data: {{ labels: datasets.map(d => d.label), datasets: [{{
    label: 'Forecast End Value (HKD)',
    data: datasets.map(d => {{ const v = d.data.filter(x => x != null); return v.length ? v[v.length - 1] : 0; }}),
    backgroundColor: barColors,
    borderRadius: 4
  }}] }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: c => '$' + c.parsed.x.toLocaleString() }} }} }},
    scales: {{ x: {{ ticks: {{ callback: v => '$' + v.toLocaleString() }} }} }}
  }}
}});

new Chart(document.getElementById('pieChart').getContext('2d'), {{
  type: 'doughnut',
  data: {{
    labels: {pie_labels_json},
    datasets: [{{
      data: {pie_values_json},
      backgroundColor: {pie_colors_json},
      borderWidth: 2, borderColor: '#fff'
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ position: 'right', labels: {{ font: {{ size: 11 }}, padding: 10 }} }},
      tooltip: {{ callbacks: {{ label: c => c.label + ': $' + c.parsed.toLocaleString() }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    output_path = os.path.join(output_dir, "forecast_dashboard.html")
    with open(output_path, "w") as f:
        f.write(html)
    return output_path