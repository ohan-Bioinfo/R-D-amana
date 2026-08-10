"""Standalone Interactive 4 — Microbiology Treemap & Hierarchy Explorer.
Hierarchy: Sector → Food Category → Subtype → Organism.

Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_treemap.py
Out:  microbiology/reports/microbiology_treemap.html
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
OUT = ROOT / "reports" / "microbiology_treemap.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"


def build():
    tc = load_test_classification()
    records = []
    for y in (2024, 2025):
        df = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in df.to_dict("records"):
            sec = derive_sector_5(_val(r.get("municipality")), _val(r.get("sector"))) or "Unspecified Sector"
            cat = classify(r)[0]
            sub = r.get("sample_name") or cat
            inv = r.get("invalid_tests")
            failed = [normalize_organism(t) for t in inv if t] if inv is not None else []
            is_fail = r.get("is_failure") is True

            records.append({
                "year": y,
                "sector": sec,
                "category": cat,
                "subtype": str(sub),
                "is_fail": is_fail,
                "failed": failed,
            })

    logo_uri = ("data:image/jpeg;base64," +
                base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""

    html = TEMPLATE.replace("__DATA__", json.dumps(records, ensure_ascii=False)).replace("__LOGO__", logo_uri)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, {len(records)} rows)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>أمانة منطقة الرياض · Interactive 4 — Treemap &amp; Hierarchy</title>
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
.badge { padding: 4px 10px; background: var(--gold-200); color: #7a5c10; border-radius: 999px; font-size: 11px; font-weight: 600; font-family: 'DM Mono', monospace; }
</style>
</head>
<body>
<header class="masthead">
  <div class="logo"></div>
  <div>
    <div class="title-ar">أمانة منطقة الرياض · Interactive 4</div>
    <div class="title-en">Hierarchy Volume &amp; Contamination Treemap</div>
  </div>
</header>

<div class="wrap">
  <div class="card">
    <div class="controls">
      <span style="font-weight:600; font-family:'Tajawal',sans-serif">Scope:</span>
      <button class="btn active" data-year="ALL">All Years</button>
      <button class="btn" data-year="2024">2024</button>
      <button class="btn" data-year="2025">2025</button>
      <span style="width:20px"></span>
      <span style="font-weight:600; font-family:'Tajawal',sans-serif">Metric:</span>
      <button class="btn active" data-metric="fail">Non-compliant Samples</button>
      <button class="btn" data-metric="all">Total Samples</button>
      <span class="badge" id="stats-badge">Loading...</span>
    </div>
    <div id="treemap" style="width:100%; height:620px"></div>
  </div>
</div>

<script>
const DATA = __DATA__;
let selectedYear = 'ALL';
let selectedMetric = 'fail';

function render() {
  const filtered = DATA.filter(d => (selectedYear === 'ALL' || d.year === parseInt(selectedYear)) && (selectedMetric === 'all' || d.is_fail));

  const ids = ['ROOT'];
  const labels = ['Riyadh Microbiology'];
  const parents = [''];
  const values = [0];

  const secCounts = new Map();
  const catCounts = new Map();
  const subCounts = new Map();

  let total = 0;
  filtered.forEach(r => {
    total++;
    secCounts.set(r.sector, (secCounts.get(r.sector) || 0) + 1);
    const kCat = r.sector + '||' + r.category;
    catCounts.set(kCat, (catCounts.get(kCat) || 0) + 1);
    const kSub = r.sector + '||' + r.category + '||' + r.subtype;
    subCounts.set(kSub, (subCounts.get(kSub) || 0) + 1);
  });

  values[0] = total || 1;

  secCounts.forEach((count, sec) => {
    ids.push('SEC:' + sec); labels.push(sec); parents.push('ROOT'); values.push(count);
  });

  catCounts.forEach((count, kCat) => {
    const [sec, cat] = kCat.split('||');
    ids.push('CAT:' + kCat); labels.push(cat); parents.push('SEC:' + sec); values.push(count);
  });

  subCounts.forEach((count, kSub) => {
    const [sec, cat, sub] = kSub.split('||');
    const kCat = sec + '||' + cat;
    ids.push('SUB:' + kSub); labels.push(sub); parents.push('CAT:' + kCat); values.push(count);
  });

  document.getElementById('stats-badge').textContent = `${total.toLocaleString()} total nodes`;

  const trace = {
    type: 'treemap',
    ids: ids,
    labels: labels,
    parents: parents,
    values: values,
    branchvalues: 'total',
    hoverinfo: 'label+value+percent parent',
    marker: { colorscale: 'Viridis' }
  };

  Plotly.react('treemap', [trace], {
    font: { family: "'IBM Plex Sans Arabic', 'Tajawal', sans-serif", size: 12, color: '#3d4256' },
    margin: { l: 10, r: 10, t: 10, b: 10 }
  }, { responsive: true, displayModeBar: false });
}

document.querySelectorAll('.btn[data-year]').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.btn[data-year]').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); selectedYear = b.dataset.year; render();
  });
});

document.querySelectorAll('.btn[data-metric]').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.btn[data-metric]').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); selectedMetric = b.dataset.metric; render();
  });
});

render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
