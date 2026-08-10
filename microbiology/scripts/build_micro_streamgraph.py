"""Standalone Interactive 7 — Microbiology Organism Prevalence Streamgraph.

Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_streamgraph.py
Out:  microbiology/reports/microbiology_streamgraph.html
"""
from __future__ import annotations
import base64
import json
from pathlib import Path
import pandas as pd

from build_classification_table import classify, _val
from build_dashboard_combined import (
    derive_sector_5, normalize_organism, load_test_classification,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "microbiology_streamgraph.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"


def build():
    records = []
    for y in (2024, 2025):
        df = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in df.to_dict("records"):
            ym = r.get("year_month")
            inv = r.get("invalid_tests")
            failed = [normalize_organism(t) for t in inv if t] if inv is not None else []
            if ym and failed:
                records.append({
                    "year_month": str(ym),
                    "failed": failed,
                })

    logo_uri = ("data:image/jpeg;base64," +
                base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""

    html = TEMPLATE.replace("__DATA__", json.dumps(records, ensure_ascii=False)).replace("__LOGO__", logo_uri)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, {len(records)} failure records)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>أمانة منطقة الرياض · Interactive 7 — Microbe Streamgraph</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root {
  --green-900:#0a3d24; --green-700:#0e5c36; --gold-500:#c8a85a; --gold-200:#f0e3bf;
  --sand-50:#faf6ee; --sand-100:#f4ecde; --sand-200:#e8dcc4; --ink-900:#1a1f2c; --ink-500:#6c6f7e;
}
* { box-sizing: border-box; }
body { background: var(--sand-50); color: var(--ink-900); margin: 0; font-family: 'IBM Plex Sans Arabic', 'Tajawal', sans-serif; font-size: 14px; }
.masthead { background: linear-gradient(180deg, var(--green-900) 0%, var(--green-700) 100%); color: #faf6ee; padding: 20px 30px; border-bottom: 4px solid var(--gold-500); display: flex; align-items: center; gap: 20px; }
.logo { width: 64px; height: 64px; border-radius: 50%; background: url("__LOGO__") center/cover no-repeat #fffdf8; border: 2px solid var(--gold-500); flex-shrink: 0; }
.title-ar { font-family: 'Tajawal', sans-serif; font-weight: 700; font-size: 20px; margin: 0; }
.title-en { font-family: 'Tajawal', sans-serif; font-size: 12px; letter-spacing: 3px; text-transform: uppercase; color: var(--gold-200); margin-top: 4px; }
.wrap { max-width: 1400px; margin: 24px auto; padding: 0 24px; }
.card { background: #fffdf8; border: 1px solid var(--sand-200); border-radius: 8px; padding: 20px; box-shadow: 0 4px 12px rgba(10,61,36,0.06); }
</style>
</head>
<body>
<header class="masthead">
  <div class="logo"></div>
  <div>
    <div class="title-ar">أمانة منطقة الرياض · Interactive 7</div>
    <div class="title-en">Organism Prevalence Trends Over Time (Streamgraph)</div>
  </div>
</header>

<div class="wrap">
  <div class="card">
    <div id="streamgraph" style="width:100%; height:520px"></div>
  </div>
</div>

<script>
const DATA = __DATA__;

function render() {
  const monthsSet = new Set();
  const orgTotal = new Map();

  DATA.forEach(r => {
    monthsSet.add(r.year_month);
    r.failed.forEach(t => orgTotal.set(t, (orgTotal.get(t) || 0) + 1));
  });

  const topOrgs = Array.from(orgTotal.entries()).sort((a, b) => b[1] - a[1]).slice(0, 8).map(e => e[0]);
  const months = Array.from(monthsSet).sort();

  const orgMonthCounts = new Map();
  topOrgs.forEach(org => orgMonthCounts.set(org, new Map(months.map(m => [m, 0]))));

  DATA.forEach(r => {
    r.failed.forEach(t => {
      if (orgMonthCounts.has(t)) {
        const m = orgMonthCounts.get(t);
        m.set(r.year_month, (m.get(r.year_month) || 0) + 1);
      }
    });
  });

  const colors = ['#22853f', '#c8a85a', '#a8331a', '#7a2616', '#9a7b2a', '#0e5c36', '#b91c1c', '#3b82f6'];

  const traces = topOrgs.map((org, idx) => {
    const countsMap = orgMonthCounts.get(org);
    const yValues = months.map(m => countsMap.get(m) || 0);
    return {
      name: org,
      x: months,
      y: yValues,
      type: 'scatter',
      mode: 'lines',
      stackgroup: 'one',
      line: { shape: 'spline', width: 1.5 },
      fillcolor: colors[idx % colors.length] + 'c0',
      marker: { color: colors[idx % colors.length] }
    };
  });

  Plotly.react('streamgraph', traces, {
    font: { family: "'IBM Plex Sans Arabic', 'Tajawal', sans-serif", size: 12, color: '#3d4256' },
    margin: { l: 50, r: 20, t: 20, b: 60 },
    xaxis: { title: 'Year-Month' },
    yaxis: { title: 'Failed Tests Volume' },
    legend: { orientation: 'h', y: 1.12 }
  }, { responsive: true, displayModeBar: false });
}

render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
