"""Standalone DEMO 2: a time-lapse survey map of Riyadh's sectors on a light
field-operations sheet. Press play (or drag the timeline) through 2024-2025;
each sector-station pulses — size = samples that month, colour = contamination
rate (green clean -> red spoiled). Click a station for its monthly reading.

Self-contained (no map tiles): sectors are plotted at their real lon/lat and
animated with a plain Plotly scatter driven by a custom slider (robust — no
Plotly frames/scaleanchor). Separate from the main dashboard.

Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_demo2_map.py
Out:  microbiology/reports/micro_demo2_map.html
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import pandas as pd

from build_classification_table import _val
from build_dashboard_combined import derive_sector_5, SECTOR_CENTROIDS
from demo_assets import inline_offline

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "micro_demo2_map.html"
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]


def build():
    agg = defaultdict(lambda: {"n": 0, "nc": 0, "np": 0})   # (month, sector)
    total = 0
    for y in (2024, 2025):
        d = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in d.to_dict("records"):
            total += 1
            sector = derive_sector_5(_val(r.get("municipality")), _val(r.get("sector"))) or "Special"
            if sector not in SECTOR_CENTROIDS:
                sector = "Special"
            month = str(r.get("year_month") or "")
            if not month:
                continue
            a = agg[(month, sector)]
            a["n"] += 1
            if r.get("is_failure") is True:
                a["nc"] += 1
            if r.get("has_pathogen_failure") is True:
                a["np"] += 1

    monthly = defaultdict(dict)
    for (month, sector), a in agg.items():
        monthly[month][sector] = a
    centroids = {s: list(c) for s, c in SECTOR_CENTROIDS.items()}

    html = TEMPLATE
    html = html.replace("__MONTHLY__", json.dumps(monthly, ensure_ascii=False))
    html = html.replace("__CENTROIDS__", json.dumps(centroids))
    html = html.replace("__MONTHS__", json.dumps(MONTHS))
    html = html.replace("__TOTAL__", f"{total:,}")
    html = inline_offline(html)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  months={len(MONTHS)} sectors={len(centroids)} samples={total}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Field Survey — Riyadh Micro Time-lapse</title>
__FONTS__
__PLOTLY__
<style>
:root{
  --paper:#eaefec; --paper-2:#f5f8f6; --panel:#fbfdfc;
  --ink:#243035; --muted:#6c7a7d; --grid:#d5ded9; --rule:#cdd8d2;
  --gold:#a8842c; --cul-0:#2f9e6b; --cul-1:#e0a53a; --cul-2:#c0392b;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper);color:var(--ink);
  font-family:'IBM Plex Mono','Space Grotesk',system-ui,sans-serif;font-size:14px;
  -webkit-font-smoothing:antialiased}
body{min-height:100vh;background-image:
  linear-gradient(rgba(120,150,135,.10) 1px,transparent 1px),
  linear-gradient(90deg,rgba(120,150,135,.10) 1px,transparent 1px),
  radial-gradient(120% 90% at 50% -10%, var(--paper-2) 0%, var(--paper) 58%);
  background-size:32px 32px,32px 32px,100% 100%;}
.wrap{max-width:1180px;margin:0 auto;padding:0 26px 44px}

header.mast{display:flex;align-items:baseline;gap:16px;padding:22px 2px 12px;
  border-bottom:1px solid var(--rule);position:relative}
header.mast::after{content:"";position:absolute;left:0;bottom:-1px;width:108px;height:2px;
  background:linear-gradient(90deg,var(--gold),transparent)}
.mast .glyph{color:var(--gold);font-size:19px}
.mast h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:16px;
  letter-spacing:3px;text-transform:uppercase;margin:0}
.mast .tag{font-size:11px;color:var(--muted);letter-spacing:1.5px}
.mast .ar{font-family:'Tajawal',sans-serif;color:var(--muted);font-size:14px;
  direction:rtl;margin-inline-start:auto}
.lede{font-family:'Space Grotesk',sans-serif;font-size:19px;font-weight:500;
  line-height:1.4;max-width:60ch;margin:20px 2px 4px}
.lede b{color:var(--cul-2)}
.sub{color:var(--muted);font-size:12px;margin:0 2px 16px;max-width:64ch;letter-spacing:.2px}

.board{position:relative;border:1px solid var(--rule);border-radius:8px;
  background:linear-gradient(180deg,var(--panel),var(--paper-2));
  box-shadow:0 12px 30px -20px rgba(40,60,50,.35)}
.board .corner{position:absolute;width:12px;height:12px;border:1px solid var(--muted);opacity:.4}
.corner.tl{top:8px;left:8px;border-right:0;border-bottom:0}
.corner.tr{top:8px;right:8px;border-left:0;border-bottom:0}
.corner.bl{bottom:8px;left:8px;border-right:0;border-top:0}
.corner.br{bottom:8px;right:8px;border-left:0;border-top:0}
#map{width:100%;height:500px}

.controls{display:flex;align-items:center;gap:14px;margin-top:14px;flex-wrap:wrap}
.play{width:44px;height:44px;border-radius:50%;border:1px solid var(--rule);
  background:var(--ink);color:var(--panel);font-size:15px;cursor:pointer;flex:0 0 auto;
  display:flex;align-items:center;justify-content:center;transition:.15s}
.play:hover{transform:scale(1.05)}
.clock{font-family:'IBM Plex Mono',monospace;font-size:24px;font-weight:600;
  letter-spacing:.5px;min-width:130px}
.clock .yr{color:var(--gold)}
#scrub{flex:1;min-width:220px;accent-color:var(--cul-2);height:4px}
.hud{display:flex;gap:18px;margin-top:12px;flex-wrap:wrap;align-items:center}
.stat{font-size:12px;color:var(--muted)}
.stat b{color:var(--ink);font-weight:600;font-size:15px;font-family:'IBM Plex Mono'}
.stat.hot b{color:var(--cul-2)}
.legend{margin-inline-start:auto;display:flex;gap:10px;align-items:center;font-size:11px;color:var(--muted)}
.grad{width:120px;height:8px;border-radius:5px;
  background:linear-gradient(90deg,var(--cul-0),var(--cul-1),var(--cul-2))}
footer{margin-top:16px;color:var(--muted);font-family:'IBM Plex Mono',monospace;
  font-size:11px;letter-spacing:.4px}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head>
<body><div class="wrap">
<header class="mast">
  <span class="glyph">۞</span>
  <h1>Field Survey</h1>
  <span class="tag">RIYADH MICRO · SECTOR TIME-LAPSE · 2024–2025</span>
  <span class="ar">الرصد الميكروبي · حسب القطاع</span>
</header>

<div class="lede">Two years of the city, one month at a time — <b>__TOTAL__</b> samples pulsing across six sectors as contamination rises and falls.</div>
<div class="sub">Each station sits at its sector's real coordinates. Bubble size = samples that month · colour = % contaminated. Press play, or drag the timeline; click a station for its reading.</div>

<div class="board">
  <span class="corner tl"></span><span class="corner tr"></span>
  <span class="corner bl"></span><span class="corner br"></span>
  <div id="map"></div>
</div>

<div class="controls">
  <button class="play" id="play" aria-label="Play">▶</button>
  <div class="clock" id="clock">—</div>
  <input type="range" id="scrub" min="0" value="0" step="1">
</div>
<div class="hud">
  <div class="stat">samples <b id="s_n">—</b></div>
  <div class="stat hot">non-compliant <b id="s_nc">—</b></div>
  <div class="stat">contamination <b id="s_rate">—</b></div>
  <div class="legend"><span>clean</span><span class="grad"></span><span>contaminated</span></div>
</div>
<footer id="reading">◦ click a station to inspect a single sector · press ▶ to run the two-year sweep</footer>
</div>
<script>
const MONTHLY=__MONTHLY__, CENTROIDS=__CENTROIDS__, MONTHS=__MONTHS__;
const SECTORS=Object.keys(CENTROIDS);
const LON=SECTORS.map(s=>CENTROIDS[s][1]), LAT=SECTORS.map(s=>CENTROIDS[s][0]);
const SCALE=[[0,'#2f9e6b'],[0.3,'#8fb24a'],[0.55,'#e0a53a'],[0.78,'#e07b2f'],[1,'#c0392b']];
let MAXN=1; MONTHS.forEach(m=>SECTORS.forEach(s=>{const v=(MONTHLY[m]||{})[s]; if(v)MAXN=Math.max(MAXN,v.n);}));
const fmt=n=>(+n).toLocaleString();
const MN=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function frameFor(m){
  const size=[],color=[],cust=[];
  SECTORS.forEach(s=>{const v=(MONTHLY[m]||{})[s]||{n:0,nc:0,np:0};
    size.push(v.n?14+52*Math.sqrt(v.n/MAXN):8);
    color.push(v.n?100*v.nc/v.n:0);
    cust.push([v.n,v.nc,v.n?100*v.nc/v.n:0,v.np]);});
  return {size,color,cust};
}
function totals(m){let n=0,nc=0;SECTORS.forEach(s=>{const v=(MONTHLY[m]||{})[s];if(v){n+=v.n;nc+=v.nc;}});return{n,nc};}
function setHud(m){const t=totals(m),[y,mm]=m.split('-');
  document.getElementById('clock').innerHTML=MN[+mm]+" <span class='yr'>'"+y.slice(2)+"</span>";
  document.getElementById('s_n').textContent=fmt(t.n);
  document.getElementById('s_nc').textContent=fmt(t.nc);
  document.getElementById('s_rate').textContent=t.n?(100*t.nc/t.n).toFixed(1)+'%':'—';}

const f0=frameFor(MONTHS[0]);
const pad=0.05;
Plotly.newPlot('map',[{
  type:'scatter',mode:'markers+text',x:LON,y:LAT,text:SECTORS,
  textposition:'top center',
  textfont:{family:"'IBM Plex Mono',monospace",size:12,color:'#243035'},
  marker:{size:f0.size,color:f0.color,colorscale:SCALE,cmin:0,cmax:60,sizemode:'diameter',
    line:{color:'#ffffff',width:2},opacity:0.92,showscale:false},
  customdata:f0.cust,
  hovertemplate:'<b>%{text}</b><br>%{customdata[0]:,} samples · %{customdata[1]:,} non-compliant<br>%{customdata[2]:.1f}% contaminated<extra></extra>',
  hoverlabel:{bgcolor:'#fbfdfc',bordercolor:'#cdd8d2',font:{family:"'IBM Plex Mono',monospace",color:'#243035'}},
  cliponaxis:false}],
{margin:{l:12,r:12,t:16,b:12},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
  xaxis:{visible:false,range:[Math.min(...LON)-pad,Math.max(...LON)+pad],fixedrange:true,zeroline:false},
  yaxis:{visible:false,range:[Math.min(...LAT)-pad,Math.max(...LAT)+pad],fixedrange:true,zeroline:false},
  showlegend:false},
{displayModeBar:false,responsive:true});

const gd=document.getElementById('map');
const scrub=document.getElementById('scrub'); scrub.max=MONTHS.length-1;
let idx=0, timer=null;
function render(i){idx=((i%MONTHS.length)+MONTHS.length)%MONTHS.length;
  const f=frameFor(MONTHS[idx]);
  Plotly.restyle('map',{'marker.size':[f.size],'marker.color':[f.color],'customdata':[f.cust]},[0]);
  setHud(MONTHS[idx]); scrub.value=idx;}
scrub.addEventListener('input',e=>{stop();render(+e.target.value);});
function stop(){if(timer){clearInterval(timer);timer=null;document.getElementById('play').textContent='▶';}}
function play(){if(timer){stop();return;}
  document.getElementById('play').textContent='❙❙';
  timer=setInterval(()=>render(idx+1),620);}
document.getElementById('play').addEventListener('click',play);
gd.on('plotly_click',e=>{const i=e.points[0].pointNumber,s=SECTORS[i],c=e.points[0].customdata;
  document.getElementById('reading').innerHTML=
    `◦ <b style="color:#243035">${s}</b> — ${fmt(c[0])} samples · ${fmt(c[1])} non-compliant · `+
    `${(+c[2]).toFixed(1)}% contaminated · ${fmt(c[3])} pathogen failures `+
    `<span style="color:#6c7a7d">(${MN[+MONTHS[idx].split('-')[1]]} '${MONTHS[idx].slice(2,4)})</span>`;});

render(0);
</script>
</body></html>"""


if __name__ == "__main__":
    build()
