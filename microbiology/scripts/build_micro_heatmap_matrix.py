"""Standalone Interactive 5 — Microbiology Sector Location × Pathogen Matrix Heatmap.

Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_heatmap_matrix.py
Out:  microbiology/reports/microbiology_heatmap_matrix.html
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
OUT = ROOT / "reports" / "microbiology_heatmap_matrix.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"


def build():
    tc = load_test_classification()
    records = []
    for y in (2024, 2025):
        df = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in df.to_dict("records"):
            sec = derive_sector_5(_val(r.get("municipality")), _val(r.get("sector"))) or "Unspecified Sector"
            inv = r.get("invalid_tests")
            failed = [normalize_organism(t) for t in inv if t] if inv is not None else []
            if failed:
                records.append({
                    "year": y,
                    "sector": sec,
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
<title>أمانة منطقة الرياض · Interactive 5 — Sector Risk Heatmap Matrix</title>
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
.controls { display: flex; gap: 10px; margin-bottom: 18px; align-items: center; flex-wrap: wrap; }
.btn { padding: 6px 14px; background: var(--sand-100); border: 1px solid var(--sand-200); border-radius: 4px; font-family: 'Tajawal', sans-serif; font-weight: 500; cursor: pointer; transition: all 0.15s; }
.btn:hover, .btn.active { background: var(--green-700); color: #fff; border-color: var(--green-700); }
</style>
</head>
<body>
<header class="masthead">
  <div class="logo"></div>
  <div>
    <div class="title-ar">أمانة منطقة الرياض · Interactive 5</div>
    <div class="title-en">Sector Location × Pathogen Matrix Heatmap</div>
  </div>
</header>

<div class="wrap">
  <div class="card">
    <div class="controls">
      <span style="font-weight:600; font-family:'Tajawal',sans-serif">Year:</span>
      <button class="btn active" data-year="ALL">All Years</button>
      <button class="btn" data-year="2024">2024</button>
      <button class="btn" data-year="2025">2025</button>
    </div>
    <div id="heatmap" style="width:100%; height:520px"></div>
  </div>
</div>

<script>
const DATA = __DATA__;
let selectedYear = 'ALL';

function render() {
  const filtered = selectedYear === 'ALL' ? DATA : DATA.filter(d => d.year === parseInt(selectedYear));
  const orgCounts = new Map();
  filtered.forEach(r => r.failed.forEach(t => orgCounts.set(t, (orgCounts.get(t) || 0) + 1)));

  const topOrgs = Array.from(orgCounts.entries()).sort((a, b) => b[1] - a[1]).slice(0, 12).map(e => e[0]);
  const sectors = ['East', 'North', 'West', 'Central', 'South'];
  const z = sectors.map(() => topOrgs.map(() => 0));

  filtered.forEach(r => {
    const sIdx = sectors.indexOf(r.sector);
    if (sIdx === -1) return;
    r.failed.forEach(t => {
      const oIdx = topOrgs.indexOf(t);
      if (oIdx !== -1) z[sIdx][oIdx]++;
    });
  });

  const textMatrix = z.map((row, i) =>
    row.map((val, j) => `${sectors[i]}<br>${topOrgs[j]}<br>Failed Samples: ${val}`)
  );

  const trace = {
    type: 'heatmap',
    x: topOrgs,
    y: sectors,
    z: z,
    text: textMatrix,
    hoverinfo: 'text',
    colorscale: [
      [0, '#faf6ee'],
      [0.2, '#f0e3bf'],
      [0.5, '#c8a85a'],
      [0.8, '#a8331a'],
      [1.0, '#7a2616']
    ]
  };

  Plotly.react('heatmap', [trace], {
    font: { family: "'IBM Plex Sans Arabic', 'Tajawal', sans-serif", size: 12, color: '#3d4256' },
    margin: { l: 120, r: 20, t: 30, b: 100 },
    xaxis: { tickangle: -30 }
  }, { responsive: true, displayModeBar: false });
}

document.querySelectorAll('.btn').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); selectedYear = b.dataset.year; render();
  });
});

render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
