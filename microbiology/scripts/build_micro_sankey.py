"""Standalone Interactive 3 — Microbiology Sankey Flow Diagram.
Location (Sector) → Food Category → Organism → Severity Outcome.

Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_sankey.py
Out:  microbiology/reports/microbiology_sankey.html
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
OUT = ROOT / "reports" / "microbiology_sankey.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"


def build():
    tc = load_test_classification()
    pathogen_set = {normalize_organism(t) for t in tc["pathogen"]}

    records = []
    for y in (2024, 2025):
        df = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in df.to_dict("records"):
            sec = derive_sector_5(_val(r.get("municipality")), _val(r.get("sector"))) or "Unspecified Sector"
            cat = classify(r)[0]
            is_fail = r.get("is_failure") is True
            has_path = r.get("has_pathogen_failure") is True
            inv = r.get("invalid_tests")
            failed = [normalize_organism(t) for t in inv if t] if inv is not None else []

            if is_fail:
                sev = "Multi-pathogen" if (len([t for t in failed if t in pathogen_set]) > 1) else ("Pathogen" if has_path else "Indicator only")
            else:
                sev = "Compliant / Pass"

            records.append({
                "year": y,
                "sector": sec,
                "category": cat,
                "severity": sev,
                "failed": failed if failed else (["Non-compliant (General)"] if is_fail else []),
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
<title>أمانة منطقة الرياض · Interactive 3 — Sankey Flow</title>
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
    <div class="title-ar">أمانة منطقة الرياض · Interactive 3</div>
    <div class="title-en">Microbiology Contamination Flow (Sankey Diagram)</div>
  </div>
</header>

<div class="wrap">
  <div class="card">
    <div class="controls">
      <span style="font-weight:600; font-family:'Tajawal',sans-serif">Year Scope:</span>
      <button class="btn active" data-year="ALL">All (2024–2025)</button>
      <button class="btn" data-year="2024">2024</button>
      <button class="btn" data-year="2025">2025</button>
      <span class="badge" id="stats-badge">Loading...</span>
    </div>
    <div id="sankey" style="width:100%; height:620px"></div>
  </div>
</div>

<script>
const DATA = __DATA__;
let selectedYear = 'ALL';

function render() {
  const filtered = selectedYear === 'ALL' ? DATA : DATA.filter(d => d.year === parseInt(selectedYear));
  const nodeNames = [];
  const nodeMap = new Map();
  function getNode(name, group) {
    const key = group + ':' + name;
    if (!nodeMap.has(key)) {
      nodeMap.set(key, nodeNames.length);
      nodeNames.push({ name: name, group: group });
    }
    return nodeMap.get(key);
  }

  const flows = new Map();
  let totalFailures = 0;

  filtered.forEach(r => {
    if (r.severity === 'Compliant / Pass') return;
    totalFailures++;
    const secIdx = getNode(r.sector, 'sector');
    const catIdx = getNode(r.category, 'category');
    flows.set(secIdx + '->' + catIdx, (flows.get(secIdx + '->' + catIdx) || 0) + 1);

    if (r.failed.length > 0) {
      r.failed.forEach(t => {
        const orgIdx = getNode(t, 'organism');
        flows.set(catIdx + '->' + orgIdx, (flows.get(catIdx + '->' + orgIdx) || 0) + 1);
        const sevIdx = getNode(r.severity, 'severity');
        flows.set(orgIdx + '->' + sevIdx, (flows.get(orgIdx + '->' + sevIdx) || 0) + 1);
      });
    }
  });

  document.getElementById('stats-badge').textContent = `${totalFailures.toLocaleString()} failure links`;

  const sources = [], targets = [], values = [];
  flows.forEach((count, key) => {
    const [s, t] = key.split('->').map(Number);
    sources.push(s); targets.push(t); values.push(count);
  });

  const colors = nodeNames.map(n => {
    if (n.group === 'sector') return '#c8a85a';
    if (n.group === 'category') return '#22853f';
    if (n.group === 'organism') return '#a8331a';
    if (n.group === 'severity') return n.name.includes('Pathogen') ? '#b91c1c' : '#facc15';
    return '#6c6f7e';
  });

  const trace = {
    type: 'sankey',
    orientation: 'h',
    valueformat: '.0f',
    valuesuffix: ' failures',
    node: {
      pad: 16,
      thickness: 20,
      line: { color: '#e8dcc4', width: 0.5 },
      label: nodeNames.map(n => n.name),
      color: colors
    },
    link: { source: sources, target: targets, value: values, color: 'rgba(200, 168, 90, 0.25)' }
  };

  Plotly.react('sankey', [trace], {
    font: { family: "'IBM Plex Sans Arabic', 'Tajawal', sans-serif", size: 12, color: '#3d4256' },
    margin: { l: 20, r: 20, t: 20, b: 20 }
  }, { responsive: true, displayModeBar: false });
}

document.querySelectorAll('.btn').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    selectedYear = b.dataset.year;
    render();
  });
});

render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
