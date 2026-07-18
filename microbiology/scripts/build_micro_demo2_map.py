"""Standalone DEMO 2: a time-lapse surveillance map of Riyadh sectors, drawn as a
cyanotype municipal blueprint. Press play (or scrub) through 2024-2025; each
sector-station pulses — size = samples that month, colour = contamination rate
(calm cyan -> red alert). Click a station for its reading.

Self-contained (no map tiles): sectors are plotted at their real lon/lat on a
schematic grid, animated with Plotly frames. Separate from the main dashboard.

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
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  months={len(MONTHS)} sectors={len(centroids)} samples={total}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Surveillance — Riyadh Micro Time-lapse</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500;600&family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root{
  --blue-900:#08213d; --blue-800:#0c2c50; --blue-700:#123a66; --line:#2f5c8a;
  --cyan:#8fd3e8; --ink:#dbe9f5; --muted:#7fa2c4; --gold:#d7b45a;
  --alert:#ff5a4d; --amber:#ffb03a;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--blue-900);color:var(--ink);
  font-family:'IBM Plex Mono','Space Grotesk',monospace;font-size:14px;
  -webkit-font-smoothing:antialiased}
body{min-height:100vh;background-image:
  linear-gradient(rgba(47,92,138,.16) 1px,transparent 1px),
  linear-gradient(90deg,rgba(47,92,138,.16) 1px,transparent 1px),
  radial-gradient(120% 90% at 50% -10%, #0d2c52 0%, var(--blue-900) 60%);
  background-size:34px 34px,34px 34px,100% 100%;}
.wrap{max-width:1200px;margin:0 auto;padding:0 26px 44px}

header.mast{display:flex;align-items:baseline;gap:16px;padding:22px 2px 12px;
  border-bottom:1px solid var(--line)}
.mast .glyph{color:var(--gold);font-size:19px}
.mast h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:16px;
  letter-spacing:3px;text-transform:uppercase;margin:0;color:var(--ink)}
.mast .tag{font-size:11px;color:var(--muted);letter-spacing:1.5px}
.mast .ar{font-family:'Tajawal',sans-serif;color:var(--cyan);font-size:14px;
  direction:rtl;margin-inline-start:auto}
.lede{font-family:'Space Grotesk',sans-serif;font-size:19px;font-weight:500;
  line-height:1.4;max-width:60ch;margin:20px 2px 4px;color:var(--ink)}
.lede b{color:var(--amber)}
.sub{color:var(--muted);font-size:12px;margin:0 2px 16px;max-width:64ch;letter-spacing:.3px}

.board{position:relative;border:1px solid var(--line);border-radius:6px;
  background:linear-gradient(180deg,var(--blue-800),var(--blue-900));
  box-shadow:inset 0 0 60px rgba(0,0,0,.35)}
.board .corner{position:absolute;width:12px;height:12px;border:1px solid var(--cyan);opacity:.5}
.corner.tl{top:8px;left:8px;border-right:0;border-bottom:0}
.corner.tr{top:8px;right:8px;border-left:0;border-bottom:0}
.corner.bl{bottom:8px;left:8px;border-right:0;border-top:0}
.corner.br{bottom:8px;right:8px;border-left:0;border-top:0}
#map{width:100%;height:520px}

.hud{display:flex;align-items:center;gap:16px;margin-top:14px;flex-wrap:wrap}
.clock{font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:600;
  letter-spacing:1px;color:var(--ink);min-width:150px}
.clock .yr{color:var(--gold)}
.stat{font-size:12px;color:var(--muted)}
.stat b{color:var(--ink);font-weight:600;font-size:15px;font-family:'IBM Plex Mono'}
.stat.hot b{color:var(--alert)}
.legend{margin-inline-start:auto;display:flex;gap:16px;align-items:center;font-size:11px;color:var(--muted)}
.grad{width:120px;height:8px;border-radius:5px;
  background:linear-gradient(90deg,var(--cyan),var(--amber),var(--alert))}
footer{margin-top:20px;color:var(--muted);font-size:11px;letter-spacing:.5px}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}
</style></head>
<body><div class="wrap">
<header class="mast">
  <span class="glyph">۞</span>
  <h1>Surveillance</h1>
  <span class="tag">RIYADH MICRO · SECTOR TIME-LAPSE · 2024–2025</span>
  <span class="ar">الرصد الميكروبي · حسب القطاع</span>
</header>

<div class="lede">Two years of the city, one month at a time — <b>__TOTAL__</b> samples pulsing across six sectors as contamination rises and falls.</div>
<div class="sub">Each station sits at its sector's real coordinates. Bubble size = samples that month · colour = % contaminated. Press play, or drag the timeline. Click a station for its reading.</div>

<div class="board">
  <span class="corner tl"></span><span class="corner tr"></span>
  <span class="corner bl"></span><span class="corner br"></span>
  <div id="map"></div>
</div>

<div class="hud">
  <div class="clock" id="clock">—</div>
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
const SCALE=[[0,'#8fd3e8'],[0.3,'#bfe0c0'],[0.55,'#ffb03a'],[0.78,'#ff7a3a'],[1,'#ff5a4d']];
let MAXN=1; MONTHS.forEach(m=>SECTORS.forEach(s=>{const v=(MONTHLY[m]||{})[s]; if(v)MAXN=Math.max(MAXN,v.n);}));

function frameFor(m){
  const size=[],color=[],cust=[];
  SECTORS.forEach(s=>{const v=(MONTHLY[m]||{})[s]||{n:0,nc:0,np:0};
    size.push(v.n?12+50*Math.sqrt(v.n/MAXN):7);
    color.push(v.n?100*v.nc/v.n:0);
    cust.push([v.n,v.nc,v.n?100*v.nc/v.n:0,v.np]);});
  return {size,color,cust};
}
const monLabel=m=>{const [y,mm]=m.split('-');
  return ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+mm]+" '"+y.slice(2);};
const fmt=n=>(+n).toLocaleString();

function totals(m){let n=0,nc=0; SECTORS.forEach(s=>{const v=(MONTHLY[m]||{})[s]; if(v){n+=v.n;nc+=v.nc;}}); return {n,nc};}
function setHud(m){
  const t=totals(m),[y,mm]=m.split('-');
  document.getElementById('clock').innerHTML=monLabel(m).replace(/'(\d\d)/,"<span class='yr'>'$1</span>");
  document.getElementById('s_n').textContent=fmt(t.n);
  document.getElementById('s_nc').textContent=fmt(t.nc);
  document.getElementById('s_rate').textContent=t.n?(100*t.nc/t.n).toFixed(1)+'%':'—';
}

const f0=frameFor(MONTHS[0]);
const trace={type:'scatter',mode:'markers+text',x:LON,y:LAT,text:SECTORS,
  textposition:'top center',textfont:{family:"'IBM Plex Mono',monospace",size:11,color:'#dbe9f5'},
  marker:{size:f0.size,color:f0.color,colorscale:SCALE,cmin:0,cmax:60,
    line:{color:'#0c2c50',width:1.5},opacity:.92,
    sizemode:'diameter',
    colorbar:{thickness:0,len:0,showticklabels:false}},
  customdata:f0.cust,
  hovertemplate:'<b>%{text}</b><br>%{customdata[0]:,} samples · %{customdata[1]:,} non-compliant<br>%{customdata[2]:.1f}% contaminated<extra></extra>',
  hoverlabel:{bgcolor:'#0c2c50',bordercolor:'#2f5c8a',font:{family:"'IBM Plex Mono',monospace",color:'#dbe9f5'}},
  cliponaxis:false};
const pad=0.06;
const layout={margin:{l:10,r:10,t:10,b:10},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
  xaxis:{visible:false,range:[Math.min(...LON)-pad,Math.max(...LON)+pad],fixedrange:true},
  yaxis:{visible:false,range:[Math.min(...LAT)-pad,Math.max(...LAT)+pad],fixedrange:true,
    scaleanchor:'x',scaleratio:1.15},
  showlegend:false,
  updatemenus:[{type:'buttons',showactive:false,x:0.01,y:0.02,xanchor:'left',yanchor:'bottom',
    bgcolor:'#123a66',bordercolor:'#2f5c8a',font:{color:'#dbe9f5',family:"'IBM Plex Mono'",size:12},
    buttons:[
      {label:'▶  play',method:'animate',args:[null,{fromcurrent:true,frame:{duration:520,redraw:true},transition:{duration:280}}]},
      {label:'❙❙',method:'animate',args:[[null],{mode:'immediate',frame:{duration:0,redraw:false}}]}]}],
  sliders:[{active:0,x:0.12,y:0.02,len:0.85,xanchor:'left',yanchor:'bottom',
    pad:{b:6},currentvalue:{visible:false},
    bgcolor:'#123a66',bordercolor:'#2f5c8a',tickcolor:'#2f5c8a',
    font:{color:'#7fa2c4',family:"'IBM Plex Mono'",size:9},
    steps:MONTHS.map(m=>({label:m.slice(5)==='01'?"'"+m.slice(2,4):'',method:'animate',
      args:[[m],{mode:'immediate',frame:{duration:280,redraw:true},transition:{duration:220}}]}))}]};
const config={displayModeBar:false,responsive:true};

const frames=MONTHS.map(m=>{const f=frameFor(m);
  return {name:m,data:[{marker:{size:f.size,color:f.color},customdata:f.cust}]};});

const gd=document.getElementById('map');
Plotly.newPlot('map',[trace],layout,config).then(()=>{
  Plotly.addFrames('map',frames);
  setHud(MONTHS[0]);
  gd.on('plotly_animatingframe',e=>{if(e&&e.name)setHud(e.name);});
  gd.on('plotly_sliderchange',e=>{if(e&&e.step&&e.step.label!==undefined){} });
});
// keep the HUD synced when the slider is dragged
gd.on('plotly_sliderchange',e=>{const m=MONTHS[e.slider.active]; if(m)setHud(m);});
gd.on('plotly_click',e=>{const i=e.points[0].pointNumber,s=SECTORS[i],c=e.points[0].customdata;
  document.getElementById('reading').innerHTML=
    `◦ <b style="color:#dbe9f5">${s}</b> — ${fmt(c[0])} samples · ${fmt(c[1])} non-compliant · `+
    `${(+c[2]).toFixed(1)}% contaminated · ${fmt(c[3])} pathogen failures &nbsp;<span style="color:#7fa2c4">(this month)</span>`;});
</script>
</body></html>"""


if __name__ == "__main__":
    build()
