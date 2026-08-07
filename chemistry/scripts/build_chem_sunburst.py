"""Official chemistry sunburst — a zoomable "Assay Plate" view, branded to the
Riyadh Municipality (أمانة منطقة الرياض) emblem & palette.

Rings (outward): Year -> Analysis Section -> GSO Category -> failing Analyte,
where each category splits into a '✓ Compliant' wedge, a '⃠ Not evaluated' wedge
(validity unknown), plus one wedge per non-compliant sample's failing analyte
(normalised so lead/Lead/الرصاص collapse to one). Wedge angle = sample count;
colour = contamination (% non-compliant) or volume (toggle). Click any wedge to
zoom (native smooth stretch); breadcrumb, centre readout and the specimen slip
follow.

Self-contained (Plotly + fonts inlined from vendor/). Shareable deep-link (the
current zoom is written to the URL hash). Sibling to microbiology's sunburst.

Run:  microbiology/.venv/bin/python chemistry/scripts/build_chem_sunburst.py
Out:  chemistry/reports/chemistry_sunburst.html
"""
from __future__ import annotations
import base64
import json
import re
from collections import Counter
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEANED = ROOT / "cleaned"
VENDOR = ROOT / "vendor"
OUT = ROOT / "reports" / "chemistry_sunburst.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]

# canonical section (from parquet filename) -> English label shown on ring 2
SECTIONS = {
    "aflatoxins": "Aflatoxins",
    "food_chemistry": "Food Chemistry",
    "heavy_metals": "Heavy Metals",
    "honey": "Honey",
    "hormones_antibiotics": "Hormones & Antibiotics",
    "jam": "Jam",
    "pesticides": "Pesticides",
    "water_analysis": "Water",
}

# analyte normalisation: collapse bilingual / case / multi-test variants
_RULES = [
    (("lead", "رصاص"), "Lead · الرصاص"),
    (("arsenic", "زرنيخ"), "Arsenic · الزرنيخ"),
    (("cadmium", "كادميوم"), "Cadmium · الكادميوم"),
    (("mercury", "زئبق"), "Mercury · الزئبق"),
    (("hmf", "hydroxymethyl"), "HMF"),
    (("sulphate", "sulfate", "كبريتات"), "Sulphate"),
    (("nitrate", "نترات"), "Nitrate"),
    (("chloride", "كلوريد"), "Chloride"),
    (("hardness", "عسر"), "Hardness"),
    (("sodium", "صوديوم"), "Sodium"),
    (("tds",), "TDS"),
    (("aflatox", "b1", "b2", "g1", "g2", "سموم"), "Aflatoxin"),
    (("moisture", "رطوبة"), "Moisture"),
    (("acidity", "حموضة"), "Acidity"),
    (("sucrose", "سكروز"), "Sucrose"),
    (("glucose", "fructose"), "Glucose+Fructose"),
    (("sensory", "حسي"), "Sensory"),
    (("ph",), "pH"),
]


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
                               "n": 0, "nc": 0, "ne": 0,
                               "orgs": Counter(), "months": Counter()}
        return nd

    def _cat(v):
        return str(v).strip() if v is not None and str(v).strip() and str(v) != "nan" else "Unspecified فئة غير محددة"

    def _month(r):
        mo = r.get("sheet_year_month")
        if not mo or str(mo) == "nan":
            sd = r.get("sampling_date")
            mo = pd.to_datetime(sd).strftime("%Y-%m") if sd is not None and not pd.isna(sd) else ""
        return str(mo)[:7]

    def add(year, section, cat, leaf, kind, month):
        """kind: 'fail' (leaf=analyte) | 'ok' | 'ne'."""
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
        sec_key = m.group("sec")
        year = int(m.group("year"))
        section = SECTIONS.get(sec_key, sec_key.replace("_", " ").title())
        d = pd.read_parquet(f)

        if sec_key == "pesticides":
            # long-format: one row per (sample, pesticide). Collapse to sample level;
            # a sample fails if any pesticide exceeds its limit → that pesticide is the analyte.
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

        # wide sections: one row = one sample. Failing analyte from the derived field
        # (pH, Aflatoxin Total, Arsenic, …), falling back to the raw invalid_test.
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

    ordered = sorted(nodes.items(), key=lambda kv: (kv[1]["depth"], kv[0]))
    ids, labels, parents, values, ns, ncs, nes, depths, texts = [], [], [], [], [], [], [], [], []
    stats = {}
    for nid, nd in ordered:
        ids.append(nid); labels.append(nd["label"]); parents.append(nd["parent"])
        values.append(nd["n"]); ns.append(nd["n"]); ncs.append(nd["nc"])
        nes.append(nd["ne"]); depths.append(nd["depth"])
        texts.append("" if nd["label"].startswith(("✓", "⃠")) else nd["label"])
        top = [[o, c] for o, c in nd["orgs"].most_common(3)]
        spark = [nd["months"].get(mm, 0) for mm in MONTHS]
        stats[nid] = {"n": nd["n"], "nc": nd["nc"], "ne": nd["ne"],
                      "top": top, "spark": spark, "d": nd["depth"]}

    mids = sorted(nd["n"] for nd in nodes.values() if nd["depth"] >= 2)
    volmax = mids[int(0.92 * (len(mids) - 1))] if mids else 1

    NODES = {"ids": ids, "labels": labels, "parents": parents, "values": values,
             "n": ns, "nc": ncs, "ne": nes, "depth": depths, "text": texts}

    logo_uri = ("data:image/jpeg;base64," +
                base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""

    html = TEMPLATE
    html = html.replace("__NODES__", json.dumps(NODES, ensure_ascii=False))
    html = html.replace("__STATS__", json.dumps(stats, ensure_ascii=False))
    html = html.replace("__MONTHS__", json.dumps(MONTHS))
    html = html.replace("__VOLMAX__", str(int(volmax)))
    html = html.replace("__TOTAL__", f"{total:,}")
    html = html.replace("__LOGO__", logo_uri)
    html = inline_offline(html)
    OUT.write_text(html, encoding="utf-8")
    root = nodes["ALL"]
    print(f"wrote {OUT}")
    print(f"  root n={root['n']} (expect {total}); nodes={len(nodes)}; "
          f"overall NC={100*root['nc']/root['n']:.1f}%; volmax={int(volmax)}; "
          f"logo={'yes' if logo_uri else 'MISSING'}")


def inline_offline(html: str) -> str:
    js = (VENDOR / "plotly-2.35.2.min.js").read_text(encoding="utf-8").replace("</script>", "<\\/script>")
    css = (VENDOR / "fonts_inline.css").read_text(encoding="utf-8")
    return html.replace("__FONTS__", "<style>" + css + "</style>").replace("__PLOTLY__", "<script>" + js + "</script>")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>أمانة منطقة الرياض · Assay Plate — Chemistry Sunburst</title>
__FONTS__
__PLOTLY__
<style>
:root{
  --green:#006040; --green-2:#004d33; --green-tint:#e4ede9; --green-line:#bcd3c7;
  --peri:#8e9fc7; --peri-2:#5f70a2; --peri-tint:#eceef6;
  --white:#f7f8f5; --field:#e7e8e0; --panel:#fbfcfa;
  --ink:#1b2320; --muted:#6a736d; --hair:#d5dbd2; --gold:#b08a2e;
  --c0:#1f9d63; --c1:#8fb24a; --c2:#e0a53a; --c3:#e07b2f; --c4:#c0392b;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--field);color:var(--ink);
  font-family:'IBM Plex Sans Arabic','Space Grotesk',system-ui,sans-serif;
  font-size:14px;-webkit-font-smoothing:antialiased}
body{min-height:100vh;
  background-image:radial-gradient(120% 80% at 50% -10%, #eef1ea 0%, var(--field) 58%);}
.wrap{max-width:1320px;margin:0 auto;padding:0 26px 48px}
header.mast{display:flex;align-items:center;gap:18px;padding:20px 2px 16px;
  border-bottom:2px solid var(--green);position:relative}
header.mast::after{content:"";position:absolute;left:0;bottom:-2px;width:130px;height:2px;
  background:linear-gradient(90deg,var(--gold),transparent)}
.mast .emblem{width:66px;height:66px;border-radius:50%;flex:0 0 auto;
  background:#fff center/90% no-repeat;box-shadow:0 3px 10px -4px rgba(0,60,40,.4),
  inset 0 0 0 1px var(--green-line)}
.mast .tblock{display:flex;flex-direction:column;gap:2px;min-width:0}
.mast .ar{font-family:'Tajawal','IBM Plex Sans Arabic',sans-serif;font-weight:700;
  font-size:20px;color:var(--green);direction:rtl;line-height:1.15}
.mast .en{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:12px;
  letter-spacing:2.5px;text-transform:uppercase;color:var(--ink)}
.mast .tag{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--muted);
  letter-spacing:1px;margin-inline-start:auto;text-align:end;line-height:1.5}
.mast .tag .ar2{font-family:'Tajawal',sans-serif;direction:rtl}
.lede{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:500;
  line-height:1.35;max-width:62ch;margin:20px 2px 4px;letter-spacing:-.2px}
.lede b{color:var(--green);font-weight:700}
.lede .r{color:var(--c4)}
.sub{color:var(--muted);font-size:12.5px;margin:0 2px 6px;max-width:64ch}
.sub .ar{font-family:'Tajawal',sans-serif;direction:rtl;unicode-bidi:isolate}
.rings{display:flex;gap:8px;flex-wrap:wrap;margin:12px 2px 16px;align-items:center}
.rings .rl{display:inline-flex;align-items:center;gap:7px;background:var(--panel);
  border:1px solid var(--hair);border-radius:999px;padding:4px 11px 4px 5px;font-size:11.5px}
.rings .num{width:18px;height:18px;border-radius:50%;display:grid;place-items:center;
  font-family:'IBM Plex Mono',monospace;font-size:10px;color:#fff;font-weight:600}
.rings .rl .ar{font-family:'Tajawal',sans-serif;color:var(--muted);direction:rtl;font-size:11px}
.rings .arrow{color:var(--green-line)}
.stage{display:grid;grid-template-columns:1fr 344px;gap:22px;align-items:start}
@media(max-width:900px){.stage{grid-template-columns:1fr}}
.plate-card{position:relative;padding:14px;border-radius:18px;
  border:1px solid var(--hair);
  background:radial-gradient(circle at 50% 46%, #fbfdfb 0%, #eef2ec 62%, #e2e8e0 100%);}
.dish{position:relative;aspect-ratio:1/1;max-width:568px;margin:0 auto;border-radius:999px;
  box-shadow:inset 0 0 0 1px var(--green-line), inset 0 0 44px rgba(0,72,48,.10),
             0 18px 40px -22px rgba(0,60,40,.42);
  background:
    repeating-radial-gradient(circle at 50% 50%, rgba(0,96,64,.045) 0 2px, transparent 2px 15px),
    radial-gradient(circle at 50% 42%, #fcfefc 0%, #edf3ee 72%);
  overflow:hidden}
#plate{width:100%;height:100%}
.nucleus{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none;z-index:3}
.nucleus .card{text-align:center;transform:translateY(-1px);max-width:150px}
.nucleus .val{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:26px;
  letter-spacing:-1px;color:var(--green-2);line-height:1;text-shadow:0 1px 3px rgba(255,255,255,.9)}
.nucleus .lab{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);
  margin-top:3px;text-shadow:0 1px 2px rgba(255,255,255,.9)}
.plate-cap{display:flex;justify-content:space-between;align-items:center;gap:10px;
  padding:8px 6px 4px;flex-wrap:wrap}
.breadcrumb{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);
  letter-spacing:.3px;display:flex;flex-wrap:wrap;align-items:center;gap:2px}
.breadcrumb .seg{cursor:pointer;padding:1px 4px;border-radius:5px;transition:.12s;unicode-bidi:plaintext}
.breadcrumb .seg:hover{background:var(--green-tint);color:var(--green-2)}
.breadcrumb .seg.here{color:var(--ink);font-weight:600;cursor:default}
.breadcrumb .seg.here:hover{background:none}
.breadcrumb .sep{color:var(--green-line)}
.metrics{display:flex;gap:6px;margin-inline-start:auto}
.metric{border:1px solid var(--hair);background:var(--panel);border-radius:999px;
  padding:4px 12px;font-size:11px;cursor:pointer;color:var(--muted);
  font-family:'Space Grotesk',sans-serif;letter-spacing:.3px;transition:.15s;white-space:nowrap}
.metric .ar{font-family:'Tajawal',sans-serif}
.metric.on{background:var(--green);color:#fff;border-color:var(--green)}
.cbar-wrap{margin-top:6px}
.cbar{display:flex;align-items:center;gap:10px;margin:12px 6px 2px}
.cbar .grad{flex:1;height:10px;border-radius:6px;border:1px solid var(--hair)}
.cbar .lab{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);min-width:88px}
.cbar-ticks-row{display:flex;align-items:flex-start;gap:10px}
.cbar-ticks-row .spacer{min-width:88px;flex:0 0 88px}
.ticks{display:flex;justify-content:space-between;font-family:'IBM Plex Mono',monospace;
  font-size:9.5px;color:var(--muted);flex:1 1 auto;margin-top:3px}
.ticks span{white-space:nowrap}
.slip{background:var(--panel);border:1px solid var(--hair);border-radius:14px;
  padding:0;overflow:hidden;position:sticky;top:16px}
.slip .head{padding:14px 16px 12px;border-bottom:1px dashed var(--hair);
  background:linear-gradient(180deg,var(--green-tint),var(--panel))}
.slip .eyebrow{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;
  text-transform:uppercase;color:var(--green)}
.slip .eyebrow .ar{font-family:'Tajawal',sans-serif;letter-spacing:0;color:var(--muted)}
.slip .title{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:16px;
  margin:4px 0 0;line-height:1.2;unicode-bidi:plaintext}
.slip .body{padding:14px 16px 16px}
.big{display:flex;align-items:baseline;gap:8px;margin-bottom:12px}
.big .n{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:30px;letter-spacing:-1px}
.big .u{color:var(--muted);font-size:12px}
.readout{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.cell{border:1px solid var(--hair);border-radius:9px;padding:8px 10px;background:#fdfefd}
.cell .k{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted)}
.cell .k .ar{font-family:'Tajawal',sans-serif;text-transform:none;letter-spacing:0}
.cell .v{font-family:'IBM Plex Mono',monospace;font-size:17px;margin-top:2px}
.cell.ok .v{color:var(--green-2)}
.cell.hot .v{color:var(--c4)}
.orgs{margin:2px 0 12px}
.orgs .lab{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:6px}
.orgs .lab .ar{font-family:'Tajawal',sans-serif;text-transform:none}
.org{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12.5px;unicode-bidi:plaintext}
.org .bar{height:7px;border-radius:4px;background:var(--c4);opacity:.85;flex:0 0 auto}
.org .cnt{font-family:'IBM Plex Mono',monospace;color:var(--muted);margin-inline-start:auto;font-size:11px}
.spark{margin-top:6px}
.spark .lab{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:4px}
.spark .lab .ar{font-family:'Tajawal',sans-serif;text-transform:none}
footer{margin-top:24px;display:flex;gap:16px;align-items:center;color:var(--muted);
  font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.4px;flex-wrap:wrap;
  border-top:1px solid var(--hair);padding-top:14px}
.footer-note .ar{font-family:'Tajawal',sans-serif;direction:rtl}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head>
<body><div class="wrap">
<header class="mast">
  <div class="emblem" style="background-image:url('__LOGO__')"></div>
  <div class="tblock">
    <span class="ar">أمانة منطقة الرياض · مختبر الكيمياء</span>
    <span class="en">Assay Plate — Chemistry Sunburst</span>
  </div>
  <span class="tag">RIYADH MUNICIPALITY · R&amp;D<br><span class="ar2">التحاليل الكيميائية ٢٠٢٤–٢٠٢٥</span></span>
</header>

<div class="lede">Every chemistry sample, assayed — <b>__TOTAL__</b> readings blooming from the lab's core outward through year, analysis section, food category, and the analyte that <span class="r">failed</span>.</div>
<div class="sub">Angle is how many samples. Colour is contamination — green reads compliant, red reads a limit exceedance. Click any wedge to zoom; use the breadcrumb or the plate centre to climb back out. <span class="ar">الزاوية = عدد العينات · اللون = نسبة عدم المطابقة · انقر للتكبير.</span></div>

<div class="rings" id="ring_legend">
  <span class="rl"><span class="num" style="background:var(--green-2)">1</span>Year <span class="ar">السنة</span></span>
  <span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--green)">2</span>Section <span class="ar">القسم</span></span>
  <span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--peri-2)">3</span>Category <span class="ar">الفئة</span></span>
  <span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--gold)">4</span>Analyte <span class="ar">العنصر</span></span>
</div>

<div class="stage">
  <div class="plate-card">
    <div class="dish">
      <div id="plate"></div>
      <div class="nucleus"><div class="card">
        <div class="val" id="c_val">—</div><div class="lab" id="c_lab">all samples</div>
      </div></div>
    </div>
    <div class="plate-cap">
      <span class="breadcrumb" id="crumb"></span>
      <span class="metrics">
        <span class="metric on" data-m="nc">contamination <span class="ar">عدم المطابقة</span></span>
        <span class="metric" data-m="vol">volume <span class="ar">الحجم</span></span>
      </span>
    </div>
    <div class="cbar-wrap">
      <div class="cbar">
        <span class="lab" id="cbar_lab">% non-compliant</span>
        <span class="grad" id="cbar_grad"></span>
      </div>
      <div class="cbar-ticks-row"><span class="spacer"></span><span class="ticks" id="cbar_ticks"></span></div>
    </div>
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
  <span>angle = sample volume · الزاوية = الحجم</span>
  <span>click to zoom · center or breadcrumb to reset</span>
  <span class="footer-note"><span class="ar">أمانة منطقة الرياض</span> · official view · self-contained</span>
</footer>
</div>
<script>
const NODES=__NODES__, STATS=__STATS__, MONTHS=__MONTHS__, VOLMAX=__VOLMAX__;
const CULTURE=[[0,'#1f9d63'],[0.35,'#8fb24a'],[0.6,'#e0a53a'],[0.8,'#e07b2f'],[1,'#c0392b']];
const VOLSCALE=[[0,'#eceef6'],[0.5,'#7f97c4'],[1,'#006040']];
const PARENT={}; NODES.ids.forEach((id,i)=>PARENT[id]=NODES.parents[i]);
let metric='nc', focus='ALL';

function mconf(){
  if(metric==='vol') return {scale:VOLSCALE,cmax:VOLMAX,lab:'samples (volume)',
    grad:'linear-gradient(90deg,#eceef6,#7f97c4,#006040)',
    ticks:['0','','','', (VOLMAX>=1000?(VOLMAX/1000).toFixed(1)+'k':''+VOLMAX)]};
  return {scale:CULTURE,cmax:25,lab:'% non-compliant',
    grad:'linear-gradient(90deg,#1f9d63,#8fb24a,#e0a53a,#e07b2f,#c0392b)',
    ticks:['0','','12','','25%']};
}
function colorVals(){
  return NODES.ids.map((id,i)=>{
    const n=NODES.n[i]||1;
    if(metric==='vol')  return NODES.n[i]||0;
    return 100*(NODES.nc[i]||0)/n;
  });
}
const layout={margin:{l:6,r:6,t:6,b:6},paper_bgcolor:'rgba(0,0,0,0)',
  font:{family:"'IBM Plex Sans Arabic','Space Grotesk',sans-serif",color:'#1b2320',size:11},
  sunburstcolorway:['#1f9d63'],extendsunburstcolorway:true};
const config={displayModeBar:false,responsive:true};

function draw(){
  const c=mconf(), vals=colorVals();
  Plotly.react('plate',[{
    type:'sunburst',
    ids:NODES.ids,labels:NODES.labels,parents:NODES.parents,values:NODES.values,
    branchvalues:'total', level:focus,
    customdata:vals,
    marker:{colors:vals,colorscale:c.scale,cmin:0,cmax:c.cmax,line:{color:'#f2f6f0',width:1}},
    leaf:{opacity:0.96},
    text:NODES.text,
    texttemplate:'%{text}',
    textfont:{size:12.5,family:"'IBM Plex Sans Arabic','Space Grotesk',sans-serif"},
    insidetextorientation:'auto',
    hovertemplate:(metric==='vol')
      ? '<b>%{label}</b><br>%{value:,} samples<extra></extra>'
      : '<b>%{label}</b><br>%{value:,} samples<br>%{customdata:.1f}% non-compliant<extra></extra>',
    hoverlabel:{bgcolor:'#fbfcfa',bordercolor:'#bcd3c7',
      font:{family:"'IBM Plex Sans Arabic',sans-serif",color:'#1b2320'}},
  }],layout,config);
  document.getElementById('cbar_grad').style.background=c.grad;
  document.getElementById('cbar_lab').textContent=c.lab;
  document.getElementById('cbar_ticks').innerHTML=c.ticks.map(t=>`<span>${t}</span>`).join('');
}

const fmt=n=>n.toLocaleString();
function sparkline(vals){
  const w=300,h=38,max=Math.max(1,...vals),n=vals.length;
  const pts=vals.map((v,i)=>[6+i*(w-12)/(n-1),h-4-(h-8)*v/max]);
  const d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
  const area=d+` L ${(w-6).toFixed(1)} ${h-4} L 6 ${h-4} Z`;
  return `<svg width="100%" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="display:block">
    <path d="${area}" fill="rgba(0,96,64,.12)"/>
    <path d="${d}" fill="none" stroke="#006040" stroke-width="1.6"/></svg>`;
}
function labelFor(id){
  if(id==='ALL') return 'All samples';
  const seg=id.split('|').pop(); return seg.replace(/^[YSCL]·/,'');
}
function showStats(id){
  const s=STATS[id]||STATS['ALL'];
  document.getElementById('s_title').textContent=labelFor(id);
  const n=s.n,nc=s.nc,ne=s.ne||0,ok=n-nc-ne;
  document.getElementById('s_n').textContent=fmt(n);
  document.getElementById('s_ok').textContent=fmt(ok);
  document.getElementById('s_nc').textContent=fmt(nc);
  document.getElementById('s_rate').textContent=(100*nc/n).toFixed(1)+'%';
  document.getElementById('s_ne').textContent=fmt(ne);
  const maxc=Math.max(1,...s.top.map(t=>t[1]));
  document.getElementById('s_orgs').innerHTML= s.top.length
    ? s.top.map(([o,c])=>`<div class="org"><span class="bar" style="width:${8+70*c/maxc}px"></span>
        <span>${o}</span><span class="cnt">${fmt(c)}</span></div>`).join('')
    : '<div class="org" style="color:var(--muted)">no exceedance in this assay · لا تجاوز</div>';
  document.getElementById('s_spark').innerHTML=sparkline(s.spark);
  let cv, cl;
  if(metric==='vol'){ cv=fmt(n); cl='samples'; }
  else { cv=(100*nc/n).toFixed(1)+'%'; cl='non-compliant'; }
  document.getElementById('c_val').textContent=cv;
  document.getElementById('c_lab').textContent=(id==='ALL'?'all · ':'')+cl;
}
function crumb(id){
  const parts=[['ALL','All · الكل']];
  if(id!=='ALL'){ let acc=''; id.split('|').forEach(seg=>{
    acc=acc?acc+'|'+seg:seg; parts.push([acc, seg.replace(/^[YSCL]·/,'')]); }); }
  const el=document.getElementById('crumb'); el.innerHTML='';
  parts.forEach(([pid,lab],i)=>{
    if(i) el.insertAdjacentHTML('beforeend','<span class="sep">›</span>');
    const s=document.createElement('span');
    s.className='seg'+(i===parts.length-1?' here':'');
    s.textContent=lab; s.dataset.id=pid; el.appendChild(s);
  });
}
function writeHash(id){
  const h=(id==='ALL')?location.pathname+location.search:'#f='+encodeURIComponent(id);
  history.replaceState(null,'',h);
}
function sync(id){
  focus=(id&&STATS[id])?id:'ALL';
  showStats(focus); crumb(focus); writeHash(focus);
}
function navTo(id){
  focus=(id&&STATS[id])?id:'ALL';
  Plotly.restyle('plate',{level:focus});
  showStats(focus); crumb(focus); writeHash(focus);
}
(function(){
  const m=/(?:^|[#&])f=([^&]+)/.exec(location.hash);
  const id=m?decodeURIComponent(m[1]):'ALL';
  focus=STATS[id]?id:'ALL';
})();
draw();
sync(focus);
const gd=document.getElementById('plate');
gd.on('plotly_sunburstclick',ev=>{
  const clicked=(ev.points[0] && ev.points[0].id)||'ALL';
  sync(clicked===focus ? (PARENT[focus]||'ALL') : clicked);
});
document.getElementById('crumb').addEventListener('click',e=>{
  const seg=e.target.closest('.seg'); if(seg && seg.dataset.id) navTo(seg.dataset.id);
});
document.querySelectorAll('.metric').forEach(el=>el.addEventListener('click',()=>{
  document.querySelectorAll('.metric').forEach(x=>x.classList.remove('on'));
  el.classList.add('on'); metric=el.dataset.m; draw(); showStats(focus);
}));
</script>
</body></html>"""


if __name__ == "__main__":
    build()
