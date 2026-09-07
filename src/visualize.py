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
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LocusAdvisory - Wealth Forecast Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root, [data-theme="light"] {{
    --bg: #f4f6fb;
    --bg-elevated: #eef1f7;
    --card: #ffffff;
    --card-hover: #fafbfd;
    --text: #111827;
    --text-secondary: #374151;
    --muted: #6b7280;
    --border: #e5e7eb;
    --border-strong: #d1d5db;
    --accent: #1e40af;
    --accent-hover: #1e3a8a;
    --accent-subtle: #dbeafe;
    --accent-glow: rgba(30, 64, 175, 0.15);
    --pos: #059669;
    --pos-subtle: #d1fae5;
    --neg: #dc2626;
    --neg-subtle: #fee2e2;
    --shadow-sm: 0 1px 2px rgba(16, 24, 40, 0.04);
    --shadow-md: 0 4px 16px rgba(16, 24, 40, 0.06);
    --shadow-lg: 0 12px 32px rgba(16, 24, 40, 0.08);
    --radius: 14px;
    --chart-grid: #e5e7eb;
    --chart-text: #6b7280;
  }}
  [data-theme="dark"] {{
    --bg: #0b1120;
    --bg-elevated: #111a2e;
    --card: #131c33;
    --card-hover: #1a2540;
    --text: #f1f5f9;
    --text-secondary: #cbd5e1;
    --muted: #94a3b8;
    --border: #1e2a48;
    --border-strong: #2a3a5e;
    --accent: #60a5fa;
    --accent-hover: #93c5fd;
    --accent-subtle: #1e3a5f;
    --accent-glow: rgba(96, 165, 250, 0.2);
    --pos: #34d399;
    --pos-subtle: rgba(52, 211, 153, 0.15);
    --neg: #f87171;
    --neg-subtle: rgba(248, 113, 113, 0.15);
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.35);
    --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.45);
    --chart-grid: #1e2a48;
    --chart-text: #94a3b8;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    background: var(--bg);
    margin: 0; padding: 28px 32px;
    color: var(--text);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    transition: background-color 0.3s ease, color 0.3s ease;
  }}
  .container {{ max-width: 1240px; margin: 0 auto; }}

  .header {{
    background: var(--card);
    border-radius: var(--radius);
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: var(--shadow-sm);
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid var(--border);
  }}
  .header-brand {{ display: flex; align-items: center; gap: 16px; }}
  .brand-logo {{
    width: 44px; height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 700; font-size: 18px;
    box-shadow: 0 4px 14px var(--accent-glow);
  }}
  .header h1 {{ margin: 0 0 4px 0; font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }}
  .header .subtitle {{ color: var(--muted); font-size: 13px; }}

  .theme-toggle {{
    width: 40px; height: 40px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--muted);
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s ease;
    font-size: 18px;
  }}
  .theme-toggle:hover {{
    background: var(--bg-elevated);
    color: var(--accent);
    border-color: var(--border-strong);
  }}
  .theme-toggle .icon-sun, .theme-toggle .icon-moon {{ display: none; }}
  [data-theme="light"] .theme-toggle .icon-moon {{ display: inline; }}
  [data-theme="dark"] .theme-toggle .icon-sun {{ display: inline; }}

  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 18px;
    margin-bottom: 24px;
  }}
  .kpi {{
    background: var(--card);
    border-radius: var(--radius);
    padding: 22px 24px;
    border: 1px solid var(--border);
    position: relative;
    overflow: hidden;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.3s ease, background-color 0.3s ease;
  }}
  .kpi:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-md); border-color: var(--border-strong); }}
  .kpi::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--accent), var(--accent-hover));
    opacity: 0.9;
  }}
  .kpi .label {{
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
    margin-bottom: 10px;
  }}
  .kpi .value {{
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }}
  .kpi .sub {{ font-size: 12px; color: var(--muted); margin-top: 6px; }}

  .card {{
    background: var(--card);
    border-radius: var(--radius);
    padding: 28px 30px;
    margin-bottom: 24px;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border);
  }}
  .card h2 {{
    margin: 0 0 20px 0;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.005em;
    color: var(--text);
  }}
  .chart-wrap {{ position: relative; height: 460px; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 380px; gap: 24px; margin-bottom: 24px; }}
  @media (max-width: 900px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}

  table {{ width: 100%; border-collapse: separate; border-spacing: 0; }}
  th, td {{
    padding: 14px 16px;
    text-align: right;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
  }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{
    font-weight: 600;
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    background: transparent;
    border-bottom: 1px solid var(--border-strong);
  }}
  tbody tr {{ transition: background-color 0.15s ease; }}
  tbody tr:hover {{ background: var(--card-hover); }}
  tbody tr:last-child td {{ border-bottom: none; }}

  .positive {{ color: var(--pos); }}
  .negative {{ color: var(--neg); }}

  .section-label {{
    display: inline-block;
    background: var(--accent-subtle);
    color: var(--accent);
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 8px;
    vertical-align: middle;
    letter-spacing: 0.3px;
  }}

  @media (max-width: 768px) {{
    body {{ padding: 16px; }}
    .header {{ flex-direction: column; gap: 16px; align-items: flex-start; padding: 20px; }}
    .card {{ padding: 20px; }}
    .kpi .value {{ font-size: 24px; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-brand">
      <div class="brand-logo">LA</div>
      <div>
        <h1>LocusAdvisory</h1>
        <div class="subtitle">Wealth Forecast Dashboard</div>
      </div>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">
      <span class="icon-sun">&#9728;</span>
      <span class="icon-moon">&#9790;</span>
    </button>
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

const allCharts = [];

function getThemeVars() {{
  const cs = getComputedStyle(document.documentElement);
  return {{
    grid: cs.getPropertyValue('--chart-grid').trim() || '#e5e7eb',
    text: cs.getPropertyValue('--chart-text').trim() || '#6b7280',
    card: cs.getPropertyValue('--card').trim() || '#ffffff',
    border: cs.getPropertyValue('--border').trim() || '#e5e7eb',
    textMain: cs.getPropertyValue('--text').trim() || '#111827',
  }};
}}

function toggleTheme() {{
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('locus-theme', next);
  updateAllCharts();
}}

function initTheme() {{
  const saved = localStorage.getItem('locus-theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
}}

function baseTooltip(tv) {{
  return {{
    backgroundColor: tv.card,
    titleColor: tv.textMain,
    bodyColor: tv.text,
    borderColor: tv.border,
    borderWidth: 1,
    padding: 12,
    cornerRadius: 8,
  }};
}}

function createTrendChart() {{
  const tv = getThemeVars();
  const chart = new Chart(document.getElementById('trendChart').getContext('2d'), {{
    type: 'line',
    data: {{ labels: months, datasets: datasets }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      scales: {{
        x: {{
          title: {{ display: true, text: 'Month', color: tv.text }},
          grid: {{ color: tv.grid }},
          ticks: {{ color: tv.text, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }}
        }},
        pos: {{
          position: 'left',
          title: {{ display: true, text: 'Asset Value (HKD)', color: tv.text }},
          grid: {{ color: tv.grid }},
          ticks: {{ color: tv.text, callback: v => '$' + v.toLocaleString() }}
        }},
        neg: {{
          position: 'right',
          title: {{ display: true, text: 'Liability (HKD)', color: tv.text }},
          grid: {{ display: false }},
          ticks: {{ color: tv.text, callback: v => '$' + v.toLocaleString() }}
        }}
      }},
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ color: tv.text, usePointStyle: true, padding: 14, font: {{ size: 11 }} }} }},
        tooltip: Object.assign(baseTooltip(tv), {{ callbacks: {{ label: c => c.dataset.label + ': $' + (c.parsed.y == null ? 0 : c.parsed.y).toLocaleString() }} }})
      }}
    }}
  }});
  return chart;
}}

function createBandCharts() {{
  if (!hasStochastic || datasetsWithBands.length === 0) return [];
  const charts = [];
  const tv = getThemeVars();
  datasetsWithBands.forEach(ds => {{
    if (ds.p5 && ds.p95) {{
      const ctx = document.createElement('canvas').getContext('2d');
      charts.push(new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: months,
          datasets: [
            {{ label: ds.label + ' (P95)', data: ds.p95, borderColor: ds.borderColor + '44', backgroundColor: 'transparent', fill: '+1', tension: 0.3, pointRadius: 0, spanGaps: false, yAxisID: ds.yAxisID, borderWidth: 1 }},
            {{ label: ds.label + ' (P5)', data: ds.p5, borderColor: ds.borderColor + '44', backgroundColor: ds.borderColor + '22', fill: '-1', tension: 0.3, pointRadius: 0, spanGaps: false, yAxisID: ds.yAxisID, borderWidth: 1 }},
            {{ label: ds.label + ' (P50)', data: ds.data, borderColor: ds.borderColor, backgroundColor: 'transparent', tension: 0.35, pointRadius: 3, pointHoverRadius: 5, spanGaps: false, yAxisID: ds.yAxisID, borderWidth: 2.5 }}
          ]
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          interaction: {{ mode: 'index', intersect: false }},
          scales: {{
            x: {{ grid: {{ color: tv.grid }}, ticks: {{ color: tv.text }} }},
            pos: {{ position: 'left', grid: {{ color: tv.grid }}, ticks: {{ color: tv.text, callback: v => '$' + v.toLocaleString() }} }},
            neg: {{ position: 'right', grid: {{ display: false }}, ticks: {{ color: tv.text, callback: v => '$' + v.toLocaleString() }} }}
          }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: Object.assign(baseTooltip(tv), {{ callbacks: {{ label: c => c.dataset.label + ': $' + (c.parsed.y == null ? 0 : c.parsed.y).toLocaleString() }} }})
          }}
        }}
      }}));
    }}
  }});
  return charts;
}}

function createBarChart() {{
  const tv = getThemeVars();
  const barColors = datasets.map(d => d.borderColor);
  return new Chart(document.getElementById('barChart').getContext('2d'), {{
    type: 'bar',
    data: {{ labels: datasets.map(d => d.label), datasets: [{{
      label: 'Forecast End Value (HKD)',
      data: datasets.map(d => {{ const v = d.data.filter(x => x != null); return v.length ? v[v.length - 1] : 0; }}),
      backgroundColor: barColors,
      borderRadius: 6
    }}] }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {{
        legend: {{ display: false }},
        tooltip: Object.assign(baseTooltip(tv), {{ callbacks: {{ label: c => '$' + c.parsed.x.toLocaleString() }} }})
      }},
      scales: {{
        x: {{ grid: {{ color: tv.grid }}, ticks: {{ color: tv.text, callback: v => '$' + v.toLocaleString() }}, border: {{ color: tv.border }} }},
        y: {{ grid: {{ display: false }}, ticks: {{ color: tv.text }}, border: {{ color: tv.border }} }}
      }}
    }}
  }});
}}

function createPieChart() {{
  const tv = getThemeVars();
  return new Chart(document.getElementById('pieChart').getContext('2d'), {{
    type: 'doughnut',
    data: {{
      labels: {pie_labels_json},
      datasets: [{{
        data: {pie_values_json},
        backgroundColor: {pie_colors_json},
        borderWidth: 3,
        borderColor: tv.card
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      cutout: '62%',
      plugins: {{
        legend: {{ position: 'right', labels: {{ color: tv.text, font: {{ size: 12 }}, padding: 12 }} }},
        tooltip: Object.assign(baseTooltip(tv), {{ callbacks: {{ label: c => c.label + ': $' + c.parsed.toLocaleString() }} }})
      }}
    }}
  }});
}}

function updateAllCharts() {{
  const tv = getThemeVars();
  allCharts.forEach(chart => {{
    if (!chart.options.scales) return;
    Object.values(chart.options.scales).forEach(scale => {{
      if (scale.grid && scale.grid.color !== undefined) scale.grid.color = tv.grid;
      if (scale.ticks && scale.ticks.color !== undefined) scale.ticks.color = tv.text;
      if (scale.title && scale.title.color !== undefined) scale.title.color = tv.text;
      if (scale.border && scale.border.color !== undefined) scale.border.color = tv.border;
    }});
    if (chart.options.plugins.legend && chart.options.plugins.legend.labels) {{
      chart.options.plugins.legend.labels.color = tv.text;
    }}
    if (chart.options.plugins.tooltip) {{
      chart.options.plugins.tooltip.backgroundColor = tv.card;
      chart.options.plugins.tooltip.titleColor = tv.textMain;
      chart.options.plugins.tooltip.bodyColor = tv.text;
      chart.options.plugins.tooltip.borderColor = tv.border;
    }}
    if (chart.data.datasets && chart.data.datasets.length > 0 && chart.data.datasets[0].borderColor !== undefined) {{
      chart.data.datasets.forEach(ds => {{
        if (ds.borderWidth !== undefined && chart.config.type === 'doughnut') {{
          ds.borderColor = tv.card;
        }}
      }});
    }}
    chart.update('none');
  }});
}}

initTheme();
allCharts.push(createTrendChart());
createBandCharts().forEach(c => allCharts.push(c));
allCharts.push(createBarChart());
allCharts.push(createPieChart());
</script>
</body>
</html>"""

    output_path = os.path.join(output_dir, "forecast_dashboard.html")
    with open(output_path, "w") as f:
        f.write(html)
    return output_path