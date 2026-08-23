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
    net_worth_growth = forecast_data.get("net_worth_growth", {})
    type_summary = forecast_data.get("type_summary", {})

    sow_names = [s["name"] for s in sow_summaries]
    sow_type_map = {s["name"]: s["sow_type"] for s in sow_summaries}

    all_months_set = set()
    for sow_name in sow_names:
        for m in forecasts.get(sow_name, {}).keys():
            all_months_set.add(m)
    all_months = sorted(all_months_set)
    months_json = json.dumps(all_months)

    colors = [
        "#2ecc71", "#3498db", "#e74c3c", "#f39c12", "#9b59b6",
        "#1abc9c", "#e67e22", "#2980b9", "#27ae60", "#c0392b",
        "#16a085", "#d35400", "#8e44ad", "#2c3e50", "#f1c40f",
    ]

    datasets = []
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

    datasets_json = json.dumps(datasets)

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

    rows_html = ""
    for sow in sow_summaries:
        spct = sow.get("forecast_growth_pct", 0)
        spct_class = "positive" if spct >= 0 else "negative"
        rows_html += f"""
      <tr>
        <td>{sow['name']}</td>
        <td>{sow.get('type_label', '')}</td>
        <td>${sow.get('latest_historical_value', 0):,.2f}</td>
        <td>${sow.get('forecast_end_value', 0):,.2f}</td>
        <td class="{spct_class}">{spct:+.2f}%</td>
      </tr>"""

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