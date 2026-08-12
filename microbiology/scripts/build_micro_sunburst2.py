"""Microbiology sunburst — ALTERNATE design ("Interactive 2"), rendered with the
D3-based `sunburst-chart` package (vasturiano), at full feature parity with the
Plotly version: metric toggle (contamination / pathogen / volume), live colorbar,
clickable breadcrumb, centre readout, ring legend, and a shareable deep-link —
plus sunburst-chart's smooth native click-zoom.

Same data & hierarchy as the Plotly version (Year -> Sector -> GSO Category ->
most-severe Organism). Self-contained (library + fonts + emblem inlined).

Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_sunburst2.py
Out:  microbiology/reports/microbiology_sunburst2.html
Package: sunburst-chart (D3) — https://github.com/vasturiano/sunburst-chart
"""
from __future__ import annotations
import base64
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import pandas as pd

from build_classification_table import classify, _val
from build_dashboard_combined import (
    derive_sector_5, normalize_organism, load_test_classification,
)

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
OUT = ROOT / "reports" / "microbiology_sunburst2.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"
LIB = VENDOR / "sunburst-chart-1.21.4.min.js"
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]


def build():
    tc = load_test_classification()
    pathogen_set = {normalize_organism(t) for t in tc["pathogen"]}
    nodes: dict[str, dict] = {}

    def touch(nid, label, parent, depth):
        nd = nodes.get(nid)
        if nd is None:
            nd = nodes[nid] = {"label": label, "parent": parent, "depth": depth,
                               "n": 0, "nc": 0, "nu": 0, "np": 0,
                               "orgs": Counter(), "months": Counter()}
        return nd

    total = 0
    unknown_total = 0
    for y in (2024, 2025):
        d = pd.read_parquet(ROOT / "cleaned" / f"data{y}.parquet")
        for r in d.to_dict("records"):
            total += 1
            sector = derive_sector_5(_val(r.get("municipality")), _val(r.get("sector"))) or "Unspecified"
            cat = classify(r)[0]
            is_fail_raw = r.get("is_failure")
            is_fail = is_fail_raw is True
            is_unknown = is_fail_raw is None or (isinstance(is_fail_raw, float) and pd.isna(is_fail_raw))
            if is_unknown:
                unknown_total += 1
            has_path = r.get("has_pathogen_failure") is True
            inv = r.get("invalid_tests")
            failed = [normalize_organism(t) for t in inv if t] if inv is not None else []
            if is_fail:
                severe = next((t for t in failed if t in pathogen_set), failed[0] if failed else "Other")
                leaf = severe
            elif is_unknown:
                severe = None
                leaf = "Unknown validity"
            else:
                severe = None
                leaf = "✓ Compliant"
            month = str(r.get("year_month") or "")
            path = [
                ("ALL", "All samples", "", 0),
                (f"Y·{y}", str(y), "ALL", 1),
                (f"Y·{y}|S·{sector}", sector, f"Y·{y}", 2),
                (f"Y·{y}|S·{sector}|C·{cat}", cat, f"Y·{y}|S·{sector}", 3),
                (f"Y·{y}|S·{sector}|C·{cat}|L·{leaf}", leaf, f"Y·{y}|S·{sector}|C·{cat}", 4),
            ]
            for nid, label, parent, depth in path:
                nd = touch(nid, label, parent, depth)
                nd["n"] += 1
                if is_fail:
                    nd["nc"] += 1
                    if severe:
                        nd["orgs"][severe] += 1
                if is_unknown:
                    nd["nu"] += 1
                if has_path:
                    nd["np"] += 1
                if month:
                    nd["months"][month] += 1

    children = defaultdict(list)
    for nid, nd in nodes.items():
        if nid != "ALL":
            children[nd["parent"]].append(nid)
    for k in children:
        children[k].sort(key=lambda i: -nodes[i]["n"])

    def to_tree(nid):
        nd = nodes[nid]
        node = {"id": nid, "name": nd["label"], "n": nd["n"], "nc": nd["nc"], "nu": nd["nu"], "np": nd["np"],
                "top": [[o, c] for o, c in nd["orgs"].most_common(3)],
                "spark": [nd["months"].get(m, 0) for m in MONTHS]}
        kids = children.get(nid)
        if kids:
            node["children"] = [to_tree(k) for k in kids]
        else:
            node["value"] = nd["n"]
        return node

    tree = to_tree("ALL")
    mids = sorted(nd["n"] for nd in nodes.values() if nd["depth"] >= 2)
    volmax = mids[int(0.92 * (len(mids) - 1))] if mids else 1

    lib = LIB.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
    fonts = (VENDOR / "fonts_inline.css").read_text(encoding="utf-8")
    logo = ("data:image/jpeg;base64," +
            base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""

    # headline numbers for the quick-stats strip (same definitions as the
    # Plotly version: known-validity NC rate, unknown count, top NC category)
    root_nd = nodes["ALL"]
    known_total = root_nd["n"] - root_nd["nu"]
    nc_pct = 100 * root_nd["nc"] / max(known_total, 1)
    cat_nc = Counter()
    for nd in nodes.values():
        if nd["depth"] == 3:
            cat_nc[nd["label"]] += nd["nc"]
    top_cat, top_cat_nc = cat_nc.most_common(1)[0] if cat_nc else ("—", 0)

    html = (TEMPLATE
            .replace("__DATA__", json.dumps(tree, ensure_ascii=False))
            .replace("__MONTHS__", json.dumps(MONTHS))
            .replace("__VOLMAX__", str(int(volmax)))
            .replace("__TOTAL__", f"{total:,}")
            .replace("__STAT_NC_PCT__", f"{nc_pct:.1f}%")
            .replace("__STAT_UNK__", f"{root_nd['nu']:,}")
            .replace("__STAT_TOPCAT__", top_cat)
            .replace("__STAT_TOPCAT_N__", f"{top_cat_nc:,}")
            .replace("__FONTS__", f"<style>{fonts}</style>")
            .replace("__LIB__", f"<script>{lib}</script>")
            .replace("__LOGO__", logo)
            .replace("__STAMP__", datetime.now().strftime("%d %b %Y · %H:%M")))
    OUT.write_text(html, encoding="utf-8")
    root = nodes["ALL"]
    known = root['n'] - root['nu']
    print(f"wrote {OUT}")
    print(f"  root n={root['n']} (expect {total}); unknown={root['nu']}; nodes={len(nodes)}; "
          f"NC={100*root['nc']/known:.1f}% (known-validity only); volmax={int(volmax)}; "
          f"lib={'yes' if lib else 'MISSING'}; logo={'yes' if logo else 'MISSING'}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>أمانة منطقة الرياض · Culture Plate II — Microbiology (D3 sunburst-chart)</title>
__FONTS__
__LIB__
<style>
:root{
  --green:#006040; --green-2:#004d33; --green-tint:#e4ede9; --green-line:#bcd3c7;
  --peri:#8e9fc7; --peri-2:#5f70a2; --white:#f7f8f5; --field:#e7e8e0; --panel:#fbfcfa; --panel-2:#f4f6f1;
  --ink:#1b2320; --muted:#6a736d; --hair:#d5dbd2; --gold:#b08a2e;
  /* data (contamination) scale anchors - Clinical Tune */
  --c0:#0ea5e9; --c1:#6366f1; --c2:#a855f7; --c3:#ec4899; --c4:#e11d48;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--field);color:var(--ink);
  font-family:'IBM Plex Sans Arabic','Space Grotesk',system-ui,sans-serif;font-size:14px;-webkit-font-smoothing:antialiased}
body{min-height:100vh;background-image:radial-gradient(120% 80% at 50% -10%,#eef1ea,var(--field) 58%)}
.wrap{max-width:1320px;margin:0 auto;padding:0 26px 48px}
header.mast{display:flex;align-items:center;gap:18px;padding:20px 2px 16px;border-bottom:2px solid var(--green);position:relative}
header.mast::after{content:"";position:absolute;left:0;bottom:-2px;width:130px;height:2px;background:linear-gradient(90deg,var(--gold),transparent)}
.mast .emblem{width:66px;height:66px;border-radius:50%;flex:0 0 auto;background:#fff center/90% no-repeat;box-shadow:0 3px 10px -4px rgba(0,60,40,.4),inset 0 0 0 1px var(--green-line)}
.mast .tblock{display:flex;flex-direction:column;gap:2px;min-width:0}
.mast .ar{font-family:'Tajawal','IBM Plex Sans Arabic',sans-serif;font-weight:700;font-size:20px;color:var(--green);direction:rtl;line-height:1.15}
.mast .en{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:12px;letter-spacing:2.5px;text-transform:uppercase;color:var(--ink)}
.mast .tag{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--muted);letter-spacing:1px;margin-inline-start:auto;text-align:end;line-height:1.5}
.pkg{display:inline-flex;align-items:center;gap:6px;background:var(--panel);border:1px solid var(--hair);border-radius:999px;padding:3px 10px;font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--peri-2)}
.pkg b{color:var(--ink)}
.lede{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:500;line-height:1.35;max-width:62ch;margin:20px 2px 4px;letter-spacing:-.2px}
.lede b{color:var(--green)} .lede .r{color:var(--c4)}
.sub{color:var(--muted);font-size:12.5px;margin:0 2px 6px;max-width:64ch}
.sub .ar{font-family:'Tajawal',sans-serif;direction:rtl;unicode-bidi:isolate}

/* ── quick-stats strip ───────────────────────────────────────── */
.statline{display:flex;gap:8px 22px;flex-wrap:wrap;align-items:center;margin:10px 2px 4px;
  padding:9px 14px;background:var(--panel);border:1px solid var(--hair);border-radius:12px;
  font-size:12.5px;color:var(--muted)}
.statline .st b{color:var(--green-2);font-family:'IBM Plex Mono',monospace;font-weight:600}
.statline .st.hot b{color:var(--c4)}
.statline .st.ar{font-family:'Tajawal',sans-serif;direction:rtl;margin-inline-start:auto}
.rings{display:flex;gap:8px;flex-wrap:wrap;margin:12px 2px 16px;align-items:center}
.rings .rl{display:inline-flex;align-items:center;gap:7px;background:var(--panel);border:1px solid var(--hair);border-radius:999px;padding:4px 11px 4px 5px;font-size:11.5px}
.rings .num{width:18px;height:18px;border-radius:50%;display:grid;place-items:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:#fff;font-weight:600}
.rings .rl .ar{font-family:'Tajawal',sans-serif;color:var(--muted);direction:rtl;font-size:11px}
.rings .arrow{color:var(--green-line)}
.stage{display:grid;grid-template-columns:1fr 380px;gap:22px;align-items:start}
@media(max-width:900px){.stage{grid-template-columns:1fr}}
.plate-card{position:relative;padding:14px;border-radius:18px;border:1px solid var(--hair);background:radial-gradient(circle at 50% 46%,#fbfdfb 0%,#eef2ec 62%,#e2e8e0 100%)}
.plate-cap{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:2px 6px 10px;flex-wrap:wrap}
.breadcrumb{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);letter-spacing:.3px;display:flex;flex-wrap:wrap;align-items:center;gap:2px}
.breadcrumb .seg{cursor:pointer;padding:1px 4px;border-radius:5px;transition:.12s;unicode-bidi:plaintext}
.breadcrumb .seg:hover{background:var(--green-tint);color:var(--green-2)}
.breadcrumb .seg.here{color:var(--ink);font-weight:600;cursor:default}
.breadcrumb .seg.here:hover{background:none}
.breadcrumb .sep{color:var(--green-line)}
.metrics{display:flex;gap:6px;margin-inline-start:auto}
.metric{border:1px solid var(--hair);background:var(--panel);border-radius:999px;padding:4px 12px;font-size:11px;cursor:pointer;color:var(--muted);font-family:'Space Grotesk',sans-serif;letter-spacing:.3px;transition:.15s;white-space:nowrap}
.metric .ar{font-family:'Tajawal',sans-serif}
.metric.on{background:var(--green);color:#fff;border-color:var(--green)}
.dishwrap{position:relative}
#plate{width:100%;display:grid;place-items:center;min-height:640px}
#plate svg{max-width:100%;height:auto}
.nucleus{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none;z-index:3}
.nucleus .card{text-align:center;max-width:180px}
.nucleus .val{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:25px;letter-spacing:-1px;color:var(--green-2);line-height:1}
.nucleus .lab{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-top:3px}
.cbar-wrap{margin-top:6px}
.cbar{display:flex;align-items:center;gap:10px;margin:8px 8px 2px}
.cbar .lab{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);min-width:96px}
.cbar .grad{flex:1;height:10px;border-radius:6px;border:1px solid var(--hair)}
.cbar-ticks-row{display:flex;align-items:flex-start;gap:10px}
.cbar-ticks-row .spacer{min-width:96px;flex:0 0 96px}
.ticks{display:flex;justify-content:space-between;font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:var(--muted);flex:1 1 auto;margin-top:3px}
.slip{background:var(--panel);border:1px solid var(--hair);border-radius:14px;overflow:hidden;position:sticky;top:16px}
.slip .head{padding:14px 16px 12px;border-bottom:1px dashed var(--hair);background:linear-gradient(180deg,var(--green-tint),var(--panel))}
.slip .eyebrow{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--green)}
.slip .eyebrow .ar{font-family:'Tajawal',sans-serif;letter-spacing:0;color:var(--muted)}
.slip .title{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:17px;margin:4px 0 0;line-height:1.2;unicode-bidi:plaintext}
.slip .body{padding:14px 16px 16px}
.big{display:flex;align-items:baseline;gap:8px;margin-bottom:12px}
.big .n{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:32px;letter-spacing:-1px}
.big .u{color:var(--muted);font-size:12px}
.readout{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.cell{border:1px solid var(--hair);border-radius:9px;padding:8px 10px;background:#fdfefd}
.cell .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted)}
.cell .k .ar{font-family:'Tajawal',sans-serif;text-transform:none}
.cell .v{font-family:'IBM Plex Mono',monospace;font-size:18px;margin-top:2px}
.cell.ok .v{color:var(--green-2)} .cell.hot .v{color:var(--c4)} .cell.unknown .v{color:#64748b}
.orgs{margin:2px 0 12px}
.orgs .lab{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:6px}
.orgs .lab .ar{font-family:'Tajawal',sans-serif;text-transform:none}
.org{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:13px;unicode-bidi:plaintext}
.org .bar{height:7px;border-radius:4px;background:var(--c4);opacity:.85;flex:0 0 auto}
.org .cnt{font-family:'IBM Plex Mono',monospace;color:var(--muted);margin-inline-start:auto;font-size:11px}
.spark{margin-top:6px}
.spark .lab{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:4px}
.spark .lab .ar{font-family:'Tajawal',sans-serif;text-transform:none}
footer{margin-top:24px;display:flex;gap:16px;align-items:center;color:var(--muted);font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.4px;flex-wrap:wrap;border-top:1px solid var(--hair);padding-top:14px}
footer a{color:var(--peri-2)}
.footer-note .ar{font-family:'Tajawal',sans-serif;direction:rtl}
.sunburst-tooltip{font-family:'IBM Plex Sans Arabic',sans-serif!important;font-size:12px!important;background:rgba(27,35,32,.92)!important;border-radius:8px!important;padding:7px 10px!important;max-width:260px!important}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head>
<body><div class="wrap">
<header class="mast">
  <div class="emblem" style="background-image:url('__LOGO__')"></div>
  <div class="tblock">
    <span class="ar">أمانة منطقة الرياض · مختبر الأحياء الدقيقة</span>
    <span class="en">Culture Plate II — Microbiology</span>
  </div>
  <span class="tag"><span class="pkg">rendered with <b>sunburst-chart</b> · D3</span><br>RIYADH MUNICIPALITY · R&amp;D</span>
</header>

<div class="lede">Every sample, plated and cultured — <b>__TOTAL__</b> readings, a D3 rendering of the culture plate that <span class="r">spoiled</span> outward through year, sector, category, organism.</div>
<div class="sub">A second design on the D3 <b>sunburst-chart</b> package (vasturiano), now at full parity with the Plotly view. Click a wedge to zoom; centre or breadcrumb to climb out; hover for the reading. <span class="ar">تصميم بديل بمكتبة D3 — انقر للتكبير.</span></div>
<div class="statline">
  <span class="st">Samples <b>__TOTAL__</b> · عينة</span>
  <span class="st hot">Non-compliant <b>__STAT_NC_PCT__</b> of known validity · غير مطابق</span>
  <span class="st">Unknown validity <b>__STAT_UNK__</b> · صلاحية غير معروفة</span>
  <span class="st">Top NC category <b>__STAT_TOPCAT__</b> (__STAT_TOPCAT_N__)</span>
  <span class="st ar">أرقام إجمالية من البيانات المنظفة ٢٠٢٤–٢٠٢٥</span>
</div>

<div class="rings">
  <span class="rl"><span class="num" style="background:var(--green-2)">1</span>Year <span class="ar">السنة</span></span><span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--green)">2</span>Sector <span class="ar">القطاع</span></span><span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--peri-2)">3</span>Category <span class="ar">الفئة</span></span><span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--gold)">4</span>Organism <span class="ar">الكائن</span></span>
</div>

<div class="stage">
  <div class="plate-card">
    <div class="plate-cap">
      <span class="breadcrumb" id="crumb"></span>
      <span class="metrics">
        <span class="metric on" data-m="nc">contamination <span class="ar">التلوث</span></span>
        <span class="metric" data-m="path">pathogen <span class="ar">ممرض</span></span>
        <span class="metric" data-m="vol">volume <span class="ar">الحجم</span></span>
      </span>
    </div>
    <div class="dishwrap">
      <div id="plate"></div>
      <div class="nucleus"><div class="card"><div class="val" id="c_val">—</div><div class="lab" id="c_lab">all · contaminated</div></div></div>
    </div>
    <div class="cbar-wrap">
      <div class="cbar"><span class="lab" id="cbar_lab">% contaminated</span><span class="grad" id="cbar_grad"></span></div>
      <div class="cbar-ticks-row"><span class="spacer"></span><span class="ticks" id="cbar_ticks"></span></div>
    </div>
  </div>
  <aside class="slip">
    <div class="head">
      <div class="eyebrow">Specimen reading <span class="ar">· قراءة العينة</span></div>
      <div class="title" id="s_title">All samples</div>
    </div>
    <div class="body">
      <div class="big"><span class="n" id="s_n">—</span><span class="u">samples cultured <span class="ar">عينة</span></span></div>
      <div class="readout">
        <div class="cell ok"><div class="k">Compliant <span class="ar">مطابق</span></div><div class="v" id="s_ok">—</div></div>
        <div class="cell hot"><div class="k">Non-compliant <span class="ar">غير مطابق</span></div><div class="v" id="s_nc">—</div></div>
        <div class="cell unknown"><div class="k">Unknown validity <span class="ar">صلاحية غير معروفة</span></div><div class="v" id="s_unk">—</div></div>
        <div class="cell"><div class="k">% contaminated <span class="ar">نسبة التلوث</span></div><div class="v" id="s_rate">—</div></div>
        <div class="cell"><div class="k">% pathogen <span class="ar">نسبة الممرض</span></div><div class="v" id="s_prate">—</div></div>
      </div>
      <div class="orgs"><div class="lab">Top organisms <span class="ar">أبرز الكائنات</span> · most-severe</div><div id="s_orgs"></div></div>
      <div class="spark"><div class="lab">Monthly volume <span class="ar">الحجم الشهري</span> · 2024–2025</div><div id="s_spark"></div></div>
    </div>
  </aside>
</div>

<footer>
  <span>angle = sample volume · colour = selected metric</span>
  <span class="footer-note"><span class="ar">أمانة منطقة الرياض</span> · updated __STAMP__</span>
</footer>
</div>
<script>
const DATA=__DATA__, MONTHS=__MONTHS__, VOLMAX=__VOLMAX__;
const fmt=n=>Number(n).toLocaleString();
let metric='nc', focus=null;
const CULT=[[0,[14,165,233]],[0.25,[99,102,241]],[0.5,[168,85,247]],[0.75,[236,72,153]],[1,[225,29,72]]];
const VOL=[[0,[236,238,246]],[0.5,[127,151,196]],[1,[0,96,64]]];
function interp(stops,t){t=Math.max(0,Math.min(1,t));
  for(let i=0;i<stops.length-1;i++){const [t0,c0]=stops[i],[t1,c1]=stops[i+1];
    if(t<=t1){const f=t1==t0?0:(t-t0)/(t1-t0);
      return `rgb(${Math.round(c0[0]+(c1[0]-c0[0])*f)},${Math.round(c0[1]+(c1[1]-c0[1])*f)},${Math.round(c0[2]+(c1[2]-c0[2])*f)})`;}}
  return 'rgb(225,29,72)';}
function mconf(){
  if(metric==='path') return {cmax:30,lab:'% pathogen',grad:'linear-gradient(90deg,#0ea5e9,#6366f1,#a855f7,#ec4899,#e11d48)',ticks:['0','','15','','30%']};
  if(metric==='vol')  return {cmax:VOLMAX,lab:'samples (volume)',grad:'linear-gradient(90deg,#eceef6,#7f97c4,#006040)',ticks:['0','','','',(VOLMAX>=1000?(VOLMAX/1000).toFixed(1)+'k':''+VOLMAX)]};
  return {cmax:60,lab:'% contaminated',grad:'linear-gradient(90deg,#0ea5e9,#6366f1,#a855f7,#ec4899,#e11d48)',ticks:['0','','30','','60%']};
}
function nodeColor(o){o=o.data||o;const n=o.n||1,nu=o.nu||0,known=Math.max(n-nu,1),c=mconf();
  if(metric==='vol') return interp(VOL,(o.n||0)/c.cmax);
  const rate=metric==='path'?100*(o.np||0)/known:100*(o.nc||0)/known;
  return interp(CULT,rate/c.cmax);}
function drawCbar(){const c=mconf();
  document.getElementById('cbar_grad').style.background=c.grad;
  document.getElementById('cbar_lab').textContent=c.lab;
  document.getElementById('cbar_ticks').innerHTML=c.ticks.map(t=>`<span>${t}</span>`).join('');}
function sparkline(vals){const w=300,h=38,max=Math.max(1,...vals),n=vals.length;
  const pts=vals.map((v,i)=>[6+i*(w-12)/(n-1),h-4-(h-8)*v/max]);
  const d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
  return `<svg width="100%" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="display:block">
    <path d="${d} L ${(w-6).toFixed(1)} ${h-4} L 6 ${h-4} Z" fill="rgba(0,96,64,.12)"/>
    <path d="${d}" fill="none" stroke="#006040" stroke-width="1.6"/></svg>`;}
function showStats(d){d=d||DATA;
  document.getElementById('s_title').textContent=d.name;
  const n=d.n,nc=d.nc,nu=d.nu||0,ok=n-nc-nu,known=Math.max(n-nu,1);
  document.getElementById('s_n').textContent=fmt(n);
  document.getElementById('s_ok').textContent=fmt(ok);
  document.getElementById('s_nc').textContent=fmt(nc);
  document.getElementById('s_unk').textContent=fmt(nu);
  document.getElementById('s_rate').textContent=(known?100*nc/known:0).toFixed(1)+'%';
  document.getElementById('s_prate').textContent=(known?100*d.np/known:0).toFixed(1)+'%';
  const top=d.top||[],maxc=Math.max(1,...top.map(t=>t[1]));
  document.getElementById('s_orgs').innerHTML= top.length
    ? top.map(([o,c])=>`<div class="org"><span class="bar" style="width:${8+70*c/maxc}px"></span>
        <span>${o}</span><span class="cnt">${fmt(c)}</span></div>`).join('')
    : '<div class="org" style="color:var(--muted)">no contamination in this culture</div>';
  document.getElementById('s_spark').innerHTML=sparkline(d.spark||MONTHS.map(()=>0));}
function nucleus(o){o=o||DATA;const n=o.n||1,nu=o.nu||0,known=Math.max(n-nu,1);let v,l;
  if(metric==='vol'){v=fmt(n);l='samples';}
  else if(metric==='path'){v=(100*(o.np||0)/known).toFixed(1)+'%';l='pathogen';}
  else {v=(100*(o.nc||0)/known).toFixed(1)+'%';l='contaminated';}
  document.getElementById('c_val').textContent=v;
  document.getElementById('c_lab').textContent=(o.id==='ALL'?'all · ':'')+l;}
function crumb(node){const chain=node.ancestors().reverse();
  window.__chain=chain;const el=document.getElementById('crumb');el.innerHTML='';
  chain.forEach((a,i)=>{if(i)el.insertAdjacentHTML('beforeend','<span class="sep">›</span>');
    const s=document.createElement('span');s.className='seg'+(i===chain.length-1?' here':'');
    s.textContent=a.data.name.replace(/^[✓⃠]\s*/,'');s.dataset.i=i;el.appendChild(s);});}
function writeHash(id){history.replaceState(null,'',id==='ALL'?location.pathname+location.search:'#f='+encodeURIComponent(id));}
function focusTo(node){focus=node;chart.focusOnNode(node);
  showStats(node.data);nucleus(node.data);crumb(node);writeHash(node.data.id);}

const el=document.getElementById('plate');
const side=Math.min(880, Math.max(560, el.clientWidth||760));
const chart=new Sunburst(el)
  .data(DATA).width(side).height(side)
  .label('name').size('value').color(nodeColor)
  .radiusScaleExponent(1).minSliceAngle(0.4).transitionDuration(750)
  .tooltipTitle(d=>(d.data||d).name)
  .tooltipContent(d=>{d=d.data||d;const n=d.n||1;
    return `${fmt(d.n)} samples &middot; ${(100*(d.nc||0)/n).toFixed(1)}% contaminated`;})
  .onHover(node=>showStats(node?node.data:(focus?focus.data:DATA)))
  .onClick(node=>{if(!node){if(focus&&focus.parent)focusTo(focus.parent);return;}
    focusTo(node===focus&&node.parent?node.parent:node);});

drawCbar(); showStats(DATA); nucleus(DATA);
document.querySelectorAll('.metric').forEach(m=>m.addEventListener('click',()=>{
  document.querySelectorAll('.metric').forEach(x=>x.classList.remove('on'));
  m.classList.add('on');metric=m.dataset.m;
  chart.color(nodeColor);drawCbar();
  nucleus(focus?focus.data:DATA);
  if(focus&&focus.data.id!=='ALL')chart.focusOnNode(focus);}));
document.getElementById('crumb').addEventListener('click',e=>{
  const seg=e.target.closest('.seg');if(seg&&window.__chain)focusTo(window.__chain[+seg.dataset.i]);});
// initial focus + deep-link restore once paths exist
setTimeout(()=>{const p=el.querySelector('path');if(!p)return;
  const root=p.__data__.ancestors().pop();
  const m=/(?:^|[#&])f=([^&]+)/.exec(location.hash);const id=m?decodeURIComponent(m[1]):'ALL';
  const all=[...el.querySelectorAll('path')].map(x=>x.__data__);
  const target=id!=='ALL'?all.find(d=>d.data.id===id):root;
  focusTo(target||root);}, 500);
</script>
</body></html>"""


if __name__ == "__main__":
    build()
