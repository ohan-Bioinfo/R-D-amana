"""Standalone DEMO: a zoomable micro sunburst rendered as a cultured agar plate.

Rings (outward): Year -> Sector -> GSO Category -> Organism, where each category
splits into a '✓ Compliant' wedge plus one wedge per non-compliant sample's
MOST-SEVERE failed organism (pathogen beats indicator). Wedge angle = sample
count; colour = contamination (% non-compliance), green -> red. Click any wedge
to zoom; a specimen "report slip" panel updates with that segment's reading.

Completely separate from the main dashboard.
Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_demo.py
Out:  microbiology/reports/micro_sunburst_demo.html
"""
from __future__ import annotations
import json
from collections import defaultdict, Counter
from pathlib import Path
import pandas as pd

from build_classification_table import classify, _val
from build_dashboard_combined import (
    derive_sector_5, normalize_organism, load_test_classification,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "micro_sunburst_demo.html"
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]


def build():
    tc = load_test_classification()
    pathogen_set = {normalize_organism(t) for t in tc["pathogen"]}

    # node accumulator: id -> {label, parent, depth, n, nc, np, orgs, months}
    nodes: dict[str, dict] = {}

    def touch(nid, label, parent, depth):
        nd = nodes.get(nid)
        if nd is None:
            nd = nodes[nid] = {"label": label, "parent": parent, "depth": depth,
                               "n": 0, "nc": 0, "np": 0,
                               "orgs": Counter(), "months": Counter()}
        return nd

    total = 0
    for y in (2024, 2025):
        d = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in d.to_dict("records"):
            total += 1
            sector = derive_sector_5(_val(r.get("municipality")), _val(r.get("sector"))) or "Unspecified"
            cat = classify(r)[0]
            is_fail = r.get("is_failure") is True
            has_path = r.get("has_pathogen_failure") is True
            inv = r.get("invalid_tests")
            failed = [normalize_organism(t) for t in inv if t] if inv is not None else []
            if is_fail:
                severe = next((t for t in failed if t in pathogen_set), failed[0] if failed else "Other")
                leaf_label = severe
            else:
                severe = None
                leaf_label = "✓ Compliant"
            month = str(r.get("year_month") or "")

            path = [
                ("ALL", "All samples", "", 0),
                (f"Y·{y}", str(y), "ALL", 1),
                (f"Y·{y}|S·{sector}", sector, f"Y·{y}", 2),
                (f"Y·{y}|S·{sector}|C·{cat}", cat, f"Y·{y}|S·{sector}", 3),
                (f"Y·{y}|S·{sector}|C·{cat}|L·{leaf_label}", leaf_label,
                 f"Y·{y}|S·{sector}|C·{cat}", 4),
            ]
            for nid, label, parent, depth in path:
                nd = touch(nid, label, parent, depth)
                nd["n"] += 1
                if is_fail:
                    nd["nc"] += 1
                    if severe:
                        nd["orgs"][severe] += 1
                if has_path:
                    nd["np"] += 1
                if month:
                    nd["months"][month] += 1

    # emit arrays sorted by depth so parents precede children
    ordered = sorted(nodes.items(), key=lambda kv: (kv[1]["depth"], kv[0]))
    ids, labels, parents, values, ns, ncs, nps = [], [], [], [], [], [], []
    stats = {}
    for nid, nd in ordered:
        ids.append(nid); labels.append(nd["label"]); parents.append(nd["parent"])
        values.append(nd["n"]); ns.append(nd["n"]); ncs.append(nd["nc"]); nps.append(nd["np"])
        top = [[o, c] for o, c in nd["orgs"].most_common(3)]
        spark = [nd["months"].get(m, 0) for m in MONTHS]
        stats[nid] = {"n": nd["n"], "nc": nd["nc"], "np": nd["np"], "top": top, "spark": spark}

    NODES = {"ids": ids, "labels": labels, "parents": parents, "values": values,
             "n": ns, "nc": ncs, "np": nps}

    html = TEMPLATE
    html = html.replace("__NODES__", json.dumps(NODES, ensure_ascii=False))
    html = html.replace("__STATS__", json.dumps(stats, ensure_ascii=False))
    html = html.replace("__MONTHS__", json.dumps(MONTHS))
    html = html.replace("__TOTAL__", f"{total:,}")
    OUT.write_text(html, encoding="utf-8")
    root = nodes["ALL"]
    print(f"wrote {OUT}")
    print(f"  root n={root['n']} (expect {total}); nodes={len(nodes)}; "
          f"overall NC={100*root['nc']/root['n']:.1f}%")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Culture Plate — Microbiology Sunburst</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Arabic:wght@300;400;500;600&family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root{
  --enamel:#e7ece6; --enamel-2:#f3f6f1; --panel:#fbfcfa;
  --ink:#22282a; --muted:#727b76; --hair:#d3dad2;
  --gold:#b3892b; --rim:#c7cfc6;
  --cul-0:#2f9e6b; --cul-1:#e0a53a; --cul-2:#c0392b;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--enamel);color:var(--ink);
  font-family:'IBM Plex Sans Arabic','Space Grotesk',system-ui,sans-serif;
  font-size:14px;-webkit-font-smoothing:antialiased}
body{min-height:100vh;
  background-image:radial-gradient(120% 80% at 50% -10%, #eef2ec 0%, var(--enamel) 55%);}
.wrap{max-width:1320px;margin:0 auto;padding:0 26px 48px}

/* masthead */
header.mast{display:flex;align-items:baseline;gap:16px;padding:22px 2px 14px;
  border-bottom:1px solid var(--hair);position:relative}
header.mast::after{content:"";position:absolute;left:0;bottom:-1px;width:112px;height:2px;
  background:linear-gradient(90deg,var(--gold),transparent)}
.mast .glyph{color:var(--gold);font-size:20px;line-height:1}
.mast h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:17px;
  letter-spacing:2.5px;text-transform:uppercase;margin:0}
.mast .ar{font-family:'Tajawal',sans-serif;font-weight:500;color:var(--muted);
  font-size:14px;direction:rtl;margin-inline-start:auto}
.mast .tag{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);
  letter-spacing:1px}

.lede{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:500;
  line-height:1.35;max-width:56ch;margin:22px 2px 4px;letter-spacing:-.2px}
.lede b{color:var(--cul-2);font-weight:700}
.sub{color:var(--muted);font-size:12.5px;margin:0 2px 18px;max-width:60ch}

/* stage: plate + slip */
.stage{display:grid;grid-template-columns:1fr 340px;gap:22px;align-items:start}
@media(max-width:900px){.stage{grid-template-columns:1fr}}

.plate-card{position:relative;padding:14px;border-radius:18px;
  border:1px solid var(--hair);
  background:radial-gradient(circle at 50% 46%, #fbfdfb 0%, #eef2ec 62%, #e2e8e0 100%);}
/* the dish: a round glass plate, centred, with an agar-striation texture */
.dish{position:relative;aspect-ratio:1/1;max-width:560px;margin:0 auto;border-radius:999px;
  box-shadow:inset 0 0 0 1px var(--rim), inset 0 0 44px rgba(60,80,64,.12),
             0 18px 40px -22px rgba(40,60,44,.45);
  background:
    repeating-radial-gradient(circle at 50% 50%, rgba(120,140,124,.05) 0 2px, transparent 2px 15px),
    radial-gradient(circle at 50% 42%, #fcfefc 0%, #eef3ec 72%);
  overflow:hidden}
#plate{width:100%;height:100%}
.plate-cap{display:flex;justify-content:space-between;align-items:center;
  padding:2px 8px 8px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted)}
.breadcrumb{letter-spacing:.5px}
.breadcrumb b{color:var(--ink)}
.metrics{display:flex;gap:6px}
.metric{border:1px solid var(--hair);background:var(--panel);border-radius:999px;
  padding:4px 12px;font-size:11px;cursor:pointer;color:var(--muted);
  font-family:'Space Grotesk',sans-serif;letter-spacing:.4px;transition:.15s}
.metric.on{background:var(--ink);color:#f3f6f1;border-color:var(--ink)}

/* specimen slip */
.slip{background:var(--panel);border:1px solid var(--hair);border-radius:14px;
  padding:0;overflow:hidden;position:sticky;top:16px}
.slip .head{padding:14px 16px 12px;border-bottom:1px dashed var(--hair);
  background:linear-gradient(180deg,#fbfdfb,var(--panel))}
.slip .eyebrow{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;
  text-transform:uppercase;color:var(--gold)}
.slip .title{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:16px;
  margin:4px 0 0;line-height:1.2;unicode-bidi:plaintext}
.slip .body{padding:14px 16px 16px}
.big{display:flex;align-items:baseline;gap:8px;margin-bottom:12px}
.big .n{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:30px;letter-spacing:-1px}
.big .u{color:var(--muted);font-size:12px}
.readout{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.cell{border:1px solid var(--hair);border-radius:9px;padding:8px 10px;background:#fdfefd}
.cell .k{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}
.cell .v{font-family:'IBM Plex Mono',monospace;font-size:17px;margin-top:2px}
.cell.hot .v{color:var(--cul-2)}
.orgs{margin:2px 0 12px}
.orgs .lab{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px}
.org{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12.5px;unicode-bidi:plaintext}
.org .bar{height:7px;border-radius:4px;background:var(--cul-2);opacity:.85;flex:0 0 auto}
.org .cnt{font-family:'IBM Plex Mono',monospace;color:var(--muted);margin-inline-start:auto;font-size:11px}
.spark{margin-top:6px}
.spark .lab{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:4px}

footer{margin-top:24px;display:flex;gap:16px;align-items:center;color:var(--muted);
  font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.5px;flex-wrap:wrap}
.key{display:inline-flex;align-items:center;gap:7px}
.grad{width:120px;height:8px;border-radius:5px;
  background:linear-gradient(90deg,var(--cul-0),var(--cul-1),var(--cul-2))}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head>
<body><div class="wrap">
<header class="mast">
  <span class="glyph">۞</span>
  <h1>Culture Plate</h1>
  <span class="tag">RIYADH MUNICIPALITY · MICROBIOLOGY LAB</span>
  <span class="ar">أمانة منطقة الرياض · زراعة العينات</span>
</header>

<div class="lede">Every sample, plated and cultured — <b>__TOTAL__</b> readings blooming from the lab's core outward through year, sector, food category, and the organism that spoiled it.</div>
<div class="sub">Angle is how many samples. Colour is contamination — green reads clean, red reads spoiled. Click any colony to zoom into it; the center resets the plate.</div>

<div class="stage">
  <div class="plate-card">
    <div class="dish"><div id="plate"></div></div>
    <div class="plate-cap">
      <span class="breadcrumb" id="crumb">All samples</span>
      <span class="metrics">
        <span class="metric on" data-m="nc">contamination</span>
        <span class="metric" data-m="path">pathogen</span>
      </span>
    </div>
  </div>

  <aside class="slip">
    <div class="head">
      <div class="eyebrow">Specimen reading</div>
      <div class="title" id="s_title">All samples</div>
    </div>
    <div class="body">
      <div class="big"><span class="n" id="s_n">—</span><span class="u">samples cultured</span></div>
      <div class="readout">
        <div class="cell"><div class="k">Compliant</div><div class="v" id="s_ok">—</div></div>
        <div class="cell hot"><div class="k">Non-compliant</div><div class="v" id="s_nc">—</div></div>
        <div class="cell"><div class="k">% contaminated</div><div class="v" id="s_rate">—</div></div>
        <div class="cell"><div class="k">% pathogen</div><div class="v" id="s_prate">—</div></div>
      </div>
      <div class="orgs"><div class="lab">Top organisms</div><div id="s_orgs"></div></div>
      <div class="spark"><div class="lab">Monthly volume · 2024–2025</div><div id="s_spark"></div></div>
    </div>
  </aside>
</div>

<footer>
  <span class="key"><span class="grad"></span> clean → contaminated</span>
  <span>angle = sample volume</span>
  <span>click to zoom · center to reset</span>
</footer>
</div>
<script>
const NODES=__NODES__, STATS=__STATS__, MONTHS=__MONTHS__;
const CULTURE=[[0,'#2f9e6b'],[0.35,'#8fb24a'],[0.6,'#e0a53a'],[0.8,'#e07b2f'],[1,'#c0392b']];
let metric='nc';

function colorsFor(m){
  return NODES.ids.map((id,i)=>{
    const n=NODES.n[i]||1;
    if(m==='path') return 100*(NODES.np[i]||0)/n;
    return 100*(NODES.nc[i]||0)/n;
  });
}
const layout={margin:{l:6,r:6,t:6,b:6},paper_bgcolor:'rgba(0,0,0,0)',
  font:{family:"'IBM Plex Sans Arabic','Space Grotesk',sans-serif",color:'#22282a',size:12},
  sunburstcolorway:['#2f9e6b'],extendsunburstcolorway:true};
const config={displayModeBar:false,responsive:true};

function draw(){
  Plotly.react('plate',[{
    type:'sunburst',
    ids:NODES.ids,labels:NODES.labels,parents:NODES.parents,values:NODES.values,
    branchvalues:'total',
    customdata:colorsFor(metric),
    marker:{colors:colorsFor(metric),colorscale:CULTURE,cmin:0,cmax:60,
      line:{color:'#eef3ec',width:1}},
    leaf:{opacity:0.95},
    insidetextorientation:'radial',
    hovertemplate:'<b>%{label}</b><br>%{value:,} samples<br>'+
      '%{customdata:.1f}% '+(metric==='path'?'pathogen':'contaminated')+'<extra></extra>',
    hoverlabel:{bgcolor:'#fbfcfa',bordercolor:'#d3dad2',
      font:{family:"'IBM Plex Sans Arabic',sans-serif",color:'#22282a'}},
  }],layout,config);
}

const fmt=n=>n.toLocaleString();
function sparkline(vals){
  const w=300,h=38,max=Math.max(1,...vals),n=vals.length;
  const pts=vals.map((v,i)=>[6+i*(w-12)/(n-1),h-4-(h-8)*v/max]);
  const d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
  const area=d+` L ${(w-6).toFixed(1)} ${h-4} L 6 ${h-4} Z`;
  return `<svg width="100%" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="display:block">
    <path d="${area}" fill="rgba(47,158,107,.14)"/>
    <path d="${d}" fill="none" stroke="#2f9e6b" stroke-width="1.6"/></svg>`;
}
function showStats(id){
  const s=STATS[id]||STATS['ALL']; const lbl=labelFor(id);
  document.getElementById('s_title').textContent=lbl;
  const n=s.n,nc=s.nc,ok=n-nc;
  document.getElementById('s_n').textContent=fmt(n);
  document.getElementById('s_ok').textContent=fmt(ok);
  document.getElementById('s_nc').textContent=fmt(nc);
  document.getElementById('s_rate').textContent=(100*nc/n).toFixed(1)+'%';
  document.getElementById('s_prate').textContent=(100*s.np/n).toFixed(1)+'%';
  const maxc=Math.max(1,...s.top.map(t=>t[1]));
  document.getElementById('s_orgs').innerHTML= s.top.length
    ? s.top.map(([o,c])=>`<div class="org"><span class="bar" style="width:${8+70*c/maxc}px"></span>
        <span>${o}</span><span class="cnt">${fmt(c)}</span></div>`).join('')
    : '<div class="org" style="color:var(--muted)">no contamination in this culture</div>';
  document.getElementById('s_spark').innerHTML=sparkline(s.spark);
}
function labelFor(id){
  if(id==='ALL') return 'All samples';
  const seg=id.split('|').pop(); return seg.replace(/^[YSCL]·/,'');
}
function crumb(id){
  const parts=id==='ALL'?['All samples']:['All',...id.split('|').map(s=>s.replace(/^[YSCL]·/,''))];
  document.getElementById('crumb').innerHTML=parts.map((p,i)=>
    i===parts.length-1?`<b>${p}</b>`:p).join(' <span style="color:var(--gold)">‹</span> ');
}

draw();
showStats('ALL'); crumb('ALL');
const gd=document.getElementById('plate');
gd.on('plotly_sunburstclick',ev=>{const p=ev.points[0]; const id=p.id||'ALL';
  showStats(id); crumb(id);});
document.querySelectorAll('.metric').forEach(el=>el.addEventListener('click',()=>{
  document.querySelectorAll('.metric').forEach(x=>x.classList.remove('on'));
  el.classList.add('on'); metric=el.dataset.m; draw();
}));
</script>
</body></html>"""


if __name__ == "__main__":
    build()
