"""Chemistry sunburst — ALTERNATE design ("Interactive 2"), rendered with the
D3-based `sunburst-chart` package (vasturiano) instead of Plotly, to view and
compare the two side by side.

Same data & hierarchy as the Plotly version (Year -> Section -> GSO Category ->
failing Analyte; pesticides collapsed to sample level; colour = % non-compliance).
Self-contained (library + fonts + emblem inlined).

Run:  microbiology/.venv/bin/python chemistry/scripts/build_chem_sunburst2.py
Out:  chemistry/reports/chemistry_sunburst2.html
Package: sunburst-chart (D3) — https://github.com/vasturiano/sunburst-chart
"""
from __future__ import annotations
import base64
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEANED = ROOT / "cleaned"
VENDOR = ROOT / "vendor"
OUT = ROOT / "reports" / "chemistry_sunburst2.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"
LIB = VENDOR / "sunburst-chart-1.21.4.min.js"
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]
CMAX = 25.0  # colour scale saturates at 25% non-compliance

SECTIONS = {
    "aflatoxins": "Aflatoxins", "food_chemistry": "Food Chemistry",
    "heavy_metals": "Heavy Metals", "honey": "Honey",
    "hormones_antibiotics": "Hormones & Antibiotics", "jam": "Jam",
    "pesticides": "Pesticides", "water_analysis": "Water",
}
_RULES = [
    (("lead", "رصاص"), "Lead · الرصاص"), (("arsenic", "زرنيخ"), "Arsenic · الزرنيخ"),
    (("cadmium", "كادميوم"), "Cadmium · الكادميوم"), (("mercury", "زئبق"), "Mercury · الزئبق"),
    (("hmf", "hydroxymethyl"), "HMF"), (("sulphate", "sulfate", "كبريتات"), "Sulphate"),
    (("nitrate", "نترات"), "Nitrate"), (("chloride", "كلوريد"), "Chloride"),
    (("hardness", "عسر"), "Hardness"), (("sodium", "صوديوم"), "Sodium"), (("tds",), "TDS"),
    (("aflatox", "b1", "b2", "g1", "g2", "سموم"), "Aflatoxin"), (("moisture", "رطوبة"), "Moisture"),
    (("acidity", "حموضة"), "Acidity"), (("sucrose", "سكروز"), "Sucrose"),
    (("glucose", "fructose"), "Glucose+Fructose"), (("sensory", "حسي"), "Sensory"), (("ph",), "pH"),
]
CULT = [(0.0, (31, 157, 99)), (0.35, (143, 178, 74)), (0.6, (224, 165, 58)),
        (0.8, (224, 123, 47)), (1.0, (192, 57, 43))]


def cult_hex(rate: float) -> str:
    t = max(0.0, min(1.0, rate / CMAX))
    for i in range(len(CULT) - 1):
        t0, c0 = CULT[i]
        t1, c1 = CULT[i + 1]
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return "#%02x%02x%02x" % (int(round(c0[0] + (c1[0]-c0[0])*f)),
                                      int(round(c0[1] + (c1[1]-c0[1])*f)),
                                      int(round(c0[2] + (c1[2]-c0[2])*f)))
    return "#c0392b"


def normalize_analyte(raw) -> str:
    if raw is None:
        return "Other"
    s = str(raw).strip()
    if s == "" or s.lower() in ("nan", "-", "none"):
        return "Other"
    low = s.lower()
    hits = []
    for tokens, label in _RULES:
        if any(t in low for t in tokens):
            hits.append(label)
    hits = list(dict.fromkeys(hits))
    if len(hits) >= 2:
        return "Multiple analytes"
    if len(hits) == 1:
        return hits[0]
    words = [w for w in low.replace(",", " ").split() if len(w) > 1]
    if len(words) >= 3:
        return "Multiple analytes"
    return s[:26]


def build():
    nodes: dict[str, dict] = {}

    def touch(nid, label, parent, depth):
        nd = nodes.get(nid)
        if nd is None:
            nd = nodes[nid] = {"label": label, "parent": parent, "depth": depth,
                               "n": 0, "nc": 0, "ne": 0, "orgs": Counter(), "months": Counter()}
        return nd

    def _cat(v):
        return str(v).strip() if v is not None and str(v).strip() and str(v) != "nan" else "Unspecified"

    def _month(r):
        mo = r.get("sheet_year_month")
        if not mo or str(mo) == "nan":
            sd = r.get("sampling_date")
            mo = pd.to_datetime(sd).strftime("%Y-%m") if sd is not None and not pd.isna(sd) else ""
        return str(mo)[:7]

    def add(year, section, cat, leaf, kind, month):
        path = [
            ("ALL", "All samples", "", 0),
            (f"Y·{year}", str(year), "ALL", 1),
            (f"Y·{year}|S·{section}", section, f"Y·{year}", 2),
            (f"Y·{year}|S·{section}|C·{cat}", cat, f"Y·{year}|S·{section}", 3),
            (f"Y·{year}|S·{section}|C·{cat}|L·{leaf}", leaf, f"Y·{year}|S·{section}|C·{cat}", 4),
        ]
        for nid, label, parent, depth in path:
            nd = touch(nid, label, parent, depth)
            nd["n"] += 1
            if kind == "fail":
                nd["nc"] += 1
                nd["orgs"][leaf] += 1
            elif kind == "ne":
                nd["ne"] += 1
            if month and month in MONTHS:
                nd["months"][month] += 1

    total = 0
    for f in sorted(CLEANED.glob("chem_*.parquet")):
        m = re.match(r"chem_(?P<sec>.+)_(?P<year>20\d\d)\.parquet$", f.name)
        if not m:
            continue
        sec_key, year = m.group("sec"), int(m.group("year"))
        section = SECTIONS.get(sec_key, sec_key.replace("_", " ").title())
        d = pd.read_parquet(f)
        if sec_key == "pesticides":
            for sid, g in d.groupby("sample_id", dropna=False):
                total += 1
                r0 = g.iloc[0].to_dict()
                cat = _cat(r0.get("sample_category_canonical"))
                month = _month(r0)
                exc = g[g["exceeds_limit"] == True] if "exceeds_limit" in g.columns else g.iloc[0:0]
                if len(exc):
                    names = [str(x) for x in exc["pesticide_name"].dropna().unique() if str(x).strip()]
                    leaf = names[0] if len(names) == 1 else ("Multiple pesticides" if names else "Pesticide (unspecified)")
                    add(year, section, cat, leaf, "fail", month)
                elif r0.get("is_valid") is False:
                    add(year, section, cat, "Pesticide (unspecified)", "fail", month)
                elif pd.isna(r0.get("is_valid")):
                    add(year, section, cat, "⃠ Not evaluated", "ne", month)
                else:
                    add(year, section, cat, "✓ Compliant", "ok", month)
            continue
        has_fd = "failed_tests_derived" in d.columns
        for r in d.to_dict("records"):
            total += 1
            cat = _cat(r.get("sample_category_canonical"))
            month = _month(r)
            iv = r.get("is_valid")
            if iv is False:
                src = r.get("failed_tests_derived") if has_fd else None
                if not src or str(src).strip() in ("", "nan", "None", "[]"):
                    src = r.get("invalid_test")
                add(year, section, cat, normalize_analyte(src), "fail", month)
            elif pd.isna(iv):
                add(year, section, cat, "⃠ Not evaluated", "ne", month)
            else:
                add(year, section, cat, "✓ Compliant", "ok", month)

    children = defaultdict(list)
    for nid, nd in nodes.items():
        if nid != "ALL":
            children[nd["parent"]].append(nid)
    for k in children:
        children[k].sort(key=lambda i: -nodes[i]["n"])

    def to_tree(nid):
        nd = nodes[nid]
        rate = 100 * nd["nc"] / nd["n"] if nd["n"] else 0
        node = {"name": nd["label"], "n": nd["n"], "nc": nd["nc"], "ne": nd["ne"],
                "rate": round(rate, 1), "color": cult_hex(rate),
                "top": [[o, c] for o, c in nd["orgs"].most_common(3)],
                "spark": [nd["months"].get(mm, 0) for mm in MONTHS]}
        kids = children.get(nid)
        if kids:
            node["children"] = [to_tree(k) for k in kids]
        else:
            node["value"] = nd["n"]
        return node

    tree = to_tree("ALL")

    lib = LIB.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
    fonts = (VENDOR / "fonts_inline.css").read_text(encoding="utf-8")
    logo = ("data:image/jpeg;base64," +
            base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""

    html = (TEMPLATE
            .replace("__DATA__", json.dumps(tree, ensure_ascii=False))
            .replace("__MONTHS__", json.dumps(MONTHS))
            .replace("__TOTAL__", f"{total:,}")
            .replace("__FONTS__", f"<style>{fonts}</style>")
            .replace("__LIB__", f"<script>{lib}</script>")
            .replace("__LOGO__", logo))
    OUT.write_text(html, encoding="utf-8")
    root = nodes["ALL"]
    print(f"wrote {OUT}")
    print(f"  root n={root['n']} (expect {total}); nodes={len(nodes)}; "
          f"NC={100*root['nc']/root['n']:.1f}%; lib={'yes' if lib else 'MISSING'}; "
          f"logo={'yes' if logo else 'MISSING'}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>أمانة منطقة الرياض · Assay Plate II — Chemistry (D3 sunburst-chart)</title>
__FONTS__
__LIB__
<style>
:root{
  --green:#006040; --green-2:#004d33; --green-tint:#e4ede9; --green-line:#bcd3c7;
  --peri:#8e9fc7; --peri-2:#5f70a2; --white:#f7f8f5; --field:#e7e8e0; --panel:#fbfcfa;
  --ink:#1b2320; --muted:#6a736d; --hair:#d5dbd2; --gold:#b08a2e; --c4:#c0392b;
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
.sub{color:var(--muted);font-size:12.5px;margin:0 2px 14px;max-width:64ch}
.sub .ar{font-family:'Tajawal',sans-serif;direction:rtl;unicode-bidi:isolate}
.stage{display:grid;grid-template-columns:1fr 344px;gap:22px;align-items:start}
@media(max-width:900px){.stage{grid-template-columns:1fr}}
.plate-card{position:relative;padding:14px;border-radius:18px;border:1px solid var(--hair);background:radial-gradient(circle at 50% 46%,#fbfdfb 0%,#eef2ec 62%,#e2e8e0 100%)}
#plate{width:100%;display:grid;place-items:center;min-height:560px}
#plate svg{max-width:100%;height:auto}
.hint{text-align:center;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);padding:6px 6px 2px}
.cbar{display:flex;align-items:center;gap:10px;margin:8px 8px 2px}
.cbar .lab{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);min-width:110px}
.cbar .grad{flex:1;height:10px;border-radius:6px;border:1px solid var(--hair);background:linear-gradient(90deg,#1f9d63,#8fb24a,#e0a53a,#e07b2f,#c0392b)}
.cbar .ends{font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:var(--muted)}
.slip{background:var(--panel);border:1px solid var(--hair);border-radius:14px;overflow:hidden;position:sticky;top:16px}
.slip .head{padding:14px 16px 12px;border-bottom:1px dashed var(--hair);background:linear-gradient(180deg,var(--green-tint),var(--panel))}
.slip .eyebrow{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--green)}
.slip .eyebrow .ar{font-family:'Tajawal',sans-serif;letter-spacing:0;color:var(--muted)}
.slip .title{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:16px;margin:4px 0 0;line-height:1.2;unicode-bidi:plaintext}
.slip .body{padding:14px 16px 16px}
.big{display:flex;align-items:baseline;gap:8px;margin-bottom:12px}
.big .n{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:30px;letter-spacing:-1px}
.big .u{color:var(--muted);font-size:12px}
.readout{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.cell{border:1px solid var(--hair);border-radius:9px;padding:8px 10px;background:#fdfefd}
.cell .k{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted)}
.cell .k .ar{font-family:'Tajawal',sans-serif;text-transform:none}
.cell .v{font-family:'IBM Plex Mono',monospace;font-size:17px;margin-top:2px}
.cell.ok .v{color:var(--green-2)} .cell.hot .v{color:var(--c4)}
.orgs{margin:2px 0 12px}
.orgs .lab{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:6px}
.orgs .lab .ar{font-family:'Tajawal',sans-serif;text-transform:none}
.org{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12.5px;unicode-bidi:plaintext}
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
    <span class="ar">أمانة منطقة الرياض · مختبر الكيمياء</span>
    <span class="en">Assay Plate II — Chemistry</span>
  </div>
  <span class="tag"><span class="pkg">rendered with <b>sunburst-chart</b> · D3</span><br>RIYADH MUNICIPALITY · R&amp;D</span>
</header>

<div class="lede">Every chemistry sample, assayed — <b>__TOTAL__</b> readings, an alternate rendering blooming outward through year, section, category, and the analyte that <span class="r">failed</span>.</div>
<div class="sub">A second design built on the D3 <b>sunburst-chart</b> package (vasturiano) to compare against the Plotly view. Click a wedge to zoom in; click the centre to climb back out; hover for the specimen reading. <span class="ar">تصميم بديل بمكتبة D3 — انقر للتكبير، والمركز للرجوع.</span></div>

<div class="stage">
  <div class="plate-card">
    <div id="plate"></div>
    <div class="hint">click a wedge to zoom · center to reset</div>
    <div class="cbar"><span class="lab">% non-compliant</span><span class="ends">0</span>
      <span class="grad"></span><span class="ends">25%</span></div>
  </div>
  <aside class="slip">
    <div class="head">
      <div class="eyebrow">Specimen reading <span class="ar">· قراءة العينة</span></div>
      <div class="title" id="s_title">All samples</div>
    </div>
    <div class="body">
      <div class="big"><span class="n" id="s_n">—</span><span class="u">samples assayed <span class="ar">عينة</span></span></div>
      <div class="readout">
        <div class="cell ok"><div class="k">Compliant <span class="ar">مطابق</span></div><div class="v" id="s_ok">—</div></div>
        <div class="cell hot"><div class="k">Non-compliant <span class="ar">غير مطابق</span></div><div class="v" id="s_nc">—</div></div>
        <div class="cell"><div class="k">% non-compliant <span class="ar">نسبة عدم المطابقة</span></div><div class="v" id="s_rate">—</div></div>
        <div class="cell"><div class="k">Not evaluated <span class="ar">لم تُقيّم</span></div><div class="v" id="s_ne">—</div></div>
      </div>
      <div class="orgs"><div class="lab">Top failing analytes <span class="ar">أبرز العناصر</span></div><div id="s_orgs"></div></div>
      <div class="spark"><div class="lab">Monthly volume <span class="ar">الحجم الشهري</span> · 2024–2025</div><div id="s_spark"></div></div>
    </div>
  </aside>
</div>

<footer>
  <span>angle = sample volume · colour = % non-compliance</span>
  <span class="footer-note"><span class="ar">أمانة منطقة الرياض</span> · package: <a href="https://github.com/vasturiano/sunburst-chart">sunburst-chart</a> (D3) · self-contained</span>
</footer>
</div>
<script>
const DATA=__DATA__, MONTHS=__MONTHS__;
const fmt=n=>Number(n).toLocaleString();
function sparkline(vals){
  const w=300,h=38,max=Math.max(1,...vals),n=vals.length;
  const pts=vals.map((v,i)=>[6+i*(w-12)/(n-1),h-4-(h-8)*v/max]);
  const d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
  return `<svg width="100%" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="display:block">
    <path d="${d} L ${(w-6).toFixed(1)} ${h-4} L 6 ${h-4} Z" fill="rgba(0,96,64,.12)"/>
    <path d="${d}" fill="none" stroke="#006040" stroke-width="1.6"/></svg>`;
}
function showStats(d){
  d=d||DATA;
  document.getElementById('s_title').textContent=d.name;
  const n=d.n,nc=d.nc,ne=d.ne||0,ok=n-nc-ne;
  document.getElementById('s_n').textContent=fmt(n);
  document.getElementById('s_ok').textContent=fmt(ok);
  document.getElementById('s_nc').textContent=fmt(nc);
  document.getElementById('s_rate').textContent=(n?100*nc/n:0).toFixed(1)+'%';
  document.getElementById('s_ne').textContent=fmt(ne);
  const top=d.top||[],maxc=Math.max(1,...top.map(t=>t[1]));
  document.getElementById('s_orgs').innerHTML= top.length
    ? top.map(([o,c])=>`<div class="org"><span class="bar" style="width:${8+70*c/maxc}px"></span>
        <span>${o}</span><span class="cnt">${fmt(c)}</span></div>`).join('')
    : '<div class="org" style="color:var(--muted)">no exceedance in this assay</div>';
  document.getElementById('s_spark').innerHTML=sparkline(d.spark||MONTHS.map(()=>0));
}
const el=document.getElementById('plate');
const side=Math.min(760, Math.max(520, el.clientWidth||720));
const chart=new Sunburst(el)
  .data(DATA).width(side).height(side)
  .label('name').size('value').color('color')
  .radiusScaleExponent(1).minSliceAngle(0.4).transitionDuration(750)
  .tooltipTitle((d)=>d.name)
  .tooltipContent((d)=>`${fmt(d.n)} samples &middot; ${(d.rate||0)}% non-compliant`)
  .onHover((node)=>showStats(node?node.data:DATA));
showStats(DATA);
</script>
</body></html>"""


if __name__ == "__main__":
    build()
