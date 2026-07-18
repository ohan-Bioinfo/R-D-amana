"""Standalone DEMO 3: a contamination-flow Sankey drawn as a paper chromatogram —
the lab technique where a mixture separates into bands as it travels the paper.
Non-compliant samples flow Sector -> GSO Category -> the organism that spoiled
them (most-severe: pathogen beats indicator). Band width = contaminated samples;
hover a band to trace its whole path.

Self-contained. Separate from the main dashboard.
Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_demo3_flow.py
Out:  microbiology/reports/micro_demo3_flow.html
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import pandas as pd

from build_classification_table import classify, _val
from build_dashboard_combined import (
    derive_sector_5, normalize_organism, load_test_classification,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "micro_demo3_flow.html"
KEEP_CATS = 11   # top categories by contamination; rest fold into "Other foods"


def build():
    tc = load_test_classification()
    pathogen_set = {normalize_organism(t) for t in tc["pathogen"]}

    l1 = Counter()   # (sector, cat)
    l2 = Counter()   # (cat, organism)
    cat_nc, org_nc, sec_nc = Counter(), Counter(), Counter()
    total_nc = 0
    for y in (2024, 2025):
        d = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in d.to_dict("records"):
            if r.get("is_failure") is not True:
                continue
            total_nc += 1
            sector = derive_sector_5(_val(r.get("municipality")), _val(r.get("sector"))) or "Special"
            cat = classify(r)[0]
            inv = r.get("invalid_tests")
            failed = [normalize_organism(t) for t in inv if t] if inv is not None else []
            org = next((t for t in failed if t in pathogen_set), failed[0] if failed else "Other")
            cat_nc[cat] += 1
            l1[(sector, cat)] += 1
            l2[(cat, org)] += 1
            org_nc[org] += 1
            sec_nc[sector] += 1

    keep = {c for c, _ in cat_nc.most_common(KEEP_CATS)}
    catkey = lambda c: c if c in keep else "Other foods"
    L1, L2 = Counter(), Counter()
    for (s, c), v in l1.items():
        L1[(s, catkey(c))] += v
    for (c, o), v in l2.items():
        L2[(catkey(c), o)] += v

    # node ordering: sectors, categories, organisms — each by contamination volume
    sectors = [s for s, _ in sec_nc.most_common()]
    _cat_folded = Counter()
    for c, n in cat_nc.items():
        _cat_folded[catkey(c)] += n
    cats = [c for c, _ in _cat_folded.most_common()]
    orgs = [o for o, _ in org_nc.most_common()]

    labels, colors, groups = [], [], []
    idx = {}
    SEPIA_N, TAN_N = "#6f5c3c", "#a98a52"
    PATH_N, IND_N = "#a83224", "#3f7f52"

    def add(name, color, group):
        idx[(group, name)] = len(labels)
        labels.append(name); colors.append(color); groups.append(group)

    for s in sectors:
        add(s, SEPIA_N, "sector")
    for c in cats:
        add(c, TAN_N, "cat")
    for o in orgs:
        add(o, PATH_N if o in pathogen_set else IND_N, "org")

    def hexa(h, a):
        h = h.lstrip("#")
        return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"

    src, tgt, val, lcol = [], [], [], []
    for (s, c), v in L1.items():
        src.append(idx[("sector", s)]); tgt.append(idx[("cat", c)]); val.append(v)
        lcol.append(hexa(SEPIA_N, 0.22))
    for (c, o), v in L2.items():
        src.append(idx[("cat", c)]); tgt.append(idx[("org", o)]); val.append(v)
        lcol.append(hexa(PATH_N if o in pathogen_set else IND_N, 0.28))

    SANKEY = {"label": labels, "color": colors,
              "source": src, "target": tgt, "value": val, "lcol": lcol}

    html = TEMPLATE
    html = html.replace("__SANKEY__", json.dumps(SANKEY, ensure_ascii=False))
    html = html.replace("__TOTALNC__", f"{total_nc:,}")
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  nodes={len(labels)} (sec {len(sectors)}, cat {len(cats)}, org {len(orgs)}); "
          f"links={len(src)}; contaminated samples flowed={total_nc}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chromatogram — Contamination Flow</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root{
  --paper:#e7dcc4; --paper-2:#efe7d5; --fiber:#ded1b4;
  --ink:#3a3020; --muted:#7c6f52; --rule:#cfc09c;
  --gold:#9a7b2b; --path:#a83224; --ind:#3f7f52;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper);color:var(--ink);
  font-family:'IBM Plex Sans Arabic','Fraunces',serif;font-size:14px;-webkit-font-smoothing:antialiased}
body{min-height:100vh;background-image:
  repeating-linear-gradient(90deg,rgba(180,160,120,.10) 0 1px,transparent 1px 7px),
  radial-gradient(130% 90% at 50% -10%, var(--paper-2) 0%, var(--paper) 55%);}
.wrap{max-width:1200px;margin:0 auto;padding:0 26px 44px}

header.mast{display:flex;align-items:baseline;gap:16px;padding:22px 2px 12px;
  border-bottom:1px solid var(--rule)}
.mast .glyph{color:var(--gold);font-size:19px}
.mast h1{font-family:'Fraunces',serif;font-weight:600;font-size:20px;letter-spacing:.3px;margin:0}
.mast .tag{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);letter-spacing:1px}
.mast .ar{font-family:'IBM Plex Sans Arabic',sans-serif;color:var(--muted);font-size:14px;
  direction:rtl;margin-inline-start:auto}
.lede{font-family:'Fraunces',serif;font-size:23px;font-weight:500;line-height:1.34;
  max-width:56ch;margin:22px 2px 4px}
.lede b{color:var(--path)}
.sub{color:var(--muted);font-size:12.5px;margin:0 2px 16px;max-width:64ch}
.cols{display:flex;justify-content:space-between;max-width:960px;margin:0 2px 6px;
  font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;
  text-transform:uppercase;color:var(--muted)}
.strip{border:1px solid var(--rule);border-radius:6px;background:
  linear-gradient(180deg,#f1ead8,#e7dcc4);box-shadow:inset 0 1px 0 #f7f1e2}
#flow{width:100%;height:600px}
footer{margin-top:18px;display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);
  font-family:'IBM Plex Mono',monospace;font-size:11px}
.k{display:inline-flex;align-items:center;gap:7px}
.dot{width:10px;height:10px;border-radius:3px}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}
</style></head>
<body><div class="wrap">
<header class="mast">
  <span class="glyph">۞</span>
  <h1>Chromatogram</h1>
  <span class="tag">CONTAMINATION · SEPARATED BY SOURCE</span>
  <span class="ar">مسار التلوث · من القطاع إلى الكائن</span>
</header>

<div class="lede">Let the contamination run up the paper and it separates into bands — <b>__TOTALNC__</b> spoiled samples resolving from sector, into food category, down to the organism at fault.</div>
<div class="sub">Band width = number of contaminated samples. Hover a band to trace its full path. Red bands are pathogens; green are indicator organisms.</div>

<div class="cols"><span>Sector</span><span>Food category</span><span>Organism</span></div>
<div class="strip"><div id="flow"></div></div>

<footer>
  <span class="k"><span class="dot" style="background:#a83224"></span> pathogen</span>
  <span class="k"><span class="dot" style="background:#3f7f52"></span> indicator</span>
  <span>band width = contaminated samples</span>
  <span>hover to trace a path</span>
</footer>
</div>
<script>
const S=__SANKEY__;
Plotly.newPlot('flow',[{
  type:'sankey',orientation:'h',arrangement:'snap',
  node:{label:S.label,color:S.color,pad:14,thickness:15,
    line:{color:'#e7dcc4',width:1},
    hovertemplate:'<b>%{label}</b><br>%{value:,} contaminated<extra></extra>'},
  link:{source:S.source,target:S.target,value:S.value,color:S.lcol,
    hovertemplate:'%{source.label} → %{target.label}<br>%{value:,} samples<extra></extra>'},
  textfont:{family:"'IBM Plex Sans Arabic','IBM Plex Mono',sans-serif",size:11,color:'#3a3020'},
}],{
  margin:{l:8,r:8,t:8,b:8},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
  font:{family:"'IBM Plex Sans Arabic',sans-serif",color:'#3a3020',size:11},
  hoverlabel:{bgcolor:'#efe7d5',bordercolor:'#cfc09c',font:{family:"'IBM Plex Mono',monospace",color:'#3a3020'}},
},{displayModeBar:false,responsive:true});
</script>
</body></html>"""


if __name__ == "__main__":
    build()
