"""Official microbiology sunburst — a zoomable "Culture Plate" view, branded to
the Riyadh Municipality (أمانة منطقة الرياض) emblem & palette.

Rings (outward): Year -> Sector -> GSO Category -> Organism, where each category
splits into a '✓ Compliant' wedge plus one wedge per non-compliant sample's
MOST-SEVERE failed organism (pathogen beats indicator). Wedge angle = sample
count; colour = contamination / pathogen / volume (toggle). Click any wedge to
zoom (native smooth stretch); the breadcrumb, centre readout, and the specimen
"report slip" follow.

Riyadh emblem + green/periwinkle/white palette, Arabic-forward chrome, clickable
breadcrumb, volume colour metric, centre readout, ring legend, live colorbar,
and a shareable deep-link (current zoom written to the URL hash). Self-contained.

Run:  microbiology/.venv/bin/python microbiology/scripts/build_micro_sunburst.py
Out:  microbiology/reports/microbiology_sunburst.html
"""
from __future__ import annotations
import base64
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import pandas as pd

from build_classification_table import classify, _val
from build_dashboard_combined import (
    derive_sector_5, normalize_organism, load_test_classification,
)
from demo_assets import inline_offline

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "microbiology_sunburst.html"
LOGO = ROOT / "assets" / "riyadh_emblem.jpg"
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]


def build():
    tc = load_test_classification()
    pathogen_set = {normalize_organism(t) for t in tc["pathogen"]}

    # node accumulator: id -> {label, parent, depth, n, nc, nu, np, orgs, months}
    # nu = unknown validity (is_failure is null/NaN); excluded from NC% denominator
    # so the sunburst's contamination rate matches the main dashboard.
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
                leaf_label = severe
            elif is_unknown:
                severe = None
                leaf_label = "Unknown validity"
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
                if is_unknown:
                    nd["nu"] += 1
                if has_path:
                    nd["np"] += 1
                if month:
                    nd["months"][month] += 1

    # emit arrays sorted by depth so parents precede children
    ordered = sorted(nodes.items(), key=lambda kv: (kv[1]["depth"], kv[0]))
    ids, labels, parents, values, ns, ncs, nus, nps, depths, texts = [], [], [], [], [], [], [], [], [], []
    stats = {}
    for nid, nd in ordered:
        ids.append(nid); labels.append(nd["label"]); parents.append(nd["parent"])
        values.append(nd["n"]); ns.append(nd["n"]); ncs.append(nd["nc"])
        nus.append(nd["nu"]); nps.append(nd["np"]); depths.append(nd["depth"])
        # Blank the repetitive "✓ Compliant" and "Unknown validity" wedge labels —
        # colour already reads green/grey and hover still shows the full label.
        texts.append("" if nd["label"].startswith(("✓", "Unknown")) else nd["label"])
        top = [[o, c] for o, c in nd["orgs"].most_common(3)]
        spark = [nd["months"].get(m, 0) for m in MONTHS]
        stats[nid] = {"n": nd["n"], "nc": nd["nc"], "nu": nd["nu"], "np": nd["np"],
                      "top": top, "spark": spark, "d": nd["depth"]}

    # robust cap for the volume colour scale: 92nd percentile of node counts at
    # ring >= 2 (so category/organism wedges show a gradient, not all clipped by
    # the huge year/root totals).
    mids = sorted(nd["n"] for nd in nodes.values() if nd["depth"] >= 2)
    volmax = mids[int(0.92 * (len(mids) - 1))] if mids else 1

    NODES = {"ids": ids, "labels": labels, "parents": parents, "values": values,
             "n": ns, "nc": ncs, "nu": nus, "np": nps, "depth": depths, "text": texts}

    logo_uri = ("data:image/jpeg;base64," +
                base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""

    # headline numbers for the quick-stats strip: known-validity NC rate,
    # unknown-validity count, and the top non-compliant GSO category overall
    root_nd = nodes["ALL"]
    known_total = root_nd["n"] - root_nd["nu"]
    nc_pct = 100 * root_nd["nc"] / max(known_total, 1)
    cat_nc = Counter()
    for nd in nodes.values():
        if nd["depth"] == 3:
            cat_nc[nd["label"]] += nd["nc"]
    top_cat, top_cat_nc = cat_nc.most_common(1)[0] if cat_nc else ("—", 0)

    html = TEMPLATE
    html = html.replace("__NODES__", json.dumps(NODES, ensure_ascii=False))
    html = html.replace("__STATS__", json.dumps(stats, ensure_ascii=False))
    html = html.replace("__MONTHS__", json.dumps(MONTHS))
    html = html.replace("__VOLMAX__", str(int(volmax)))
    html = html.replace("__TOTAL__", f"{total:,}")
    html = html.replace("__STAT_NC_PCT__", f"{nc_pct:.1f}%")
    html = html.replace("__STAT_UNK__", f"{root_nd['nu']:,}")
    html = html.replace("__STAT_TOPCAT__", top_cat)
    html = html.replace("__STAT_TOPCAT_N__", f"{top_cat_nc:,}")
    html = html.replace("__LOGO__", logo_uri)
    html = html.replace("__STAMP__", datetime.now().strftime("%d %b %Y · %H:%M"))
    html = inline_offline(html)
    OUT.write_text(html, encoding="utf-8")
    root = nodes["ALL"]
    known = root['n'] - root['nu']
    print(f"wrote {OUT}")
    print(f"  root n={root['n']} (expect {total}); unknown={root['nu']}; nodes={len(nodes)}; "
          f"overall NC={100*root['nc']/known:.1f}% (known-validity only); volmax={int(volmax)}; "
          f"logo={'yes' if logo_uri else 'MISSING'}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>أمانة منطقة الرياض · Culture Plate — Microbiology Sunburst</title>
__FONTS__
__PLOTLY__
<style>
:root{
  /* Riyadh Municipality emblem palette */
  --green:#006040; --green-2:#004d33; --green-tint:#e4ede9; --green-line:#bcd3c7;
  --peri:#8e9fc7; --peri-2:#5f70a2; --peri-tint:#eceef6;
  --white:#f7f8f5; --field:#e7e8e0; --panel:#fbfcfa;
  --ink:#1b2320; --muted:#6a736d; --hair:#d5dbd2; --gold:#b08a2e;
  /* data (contamination) scale anchors */
  --c0:#1f9d63; --c1:#8fb24a; --c2:#e0a53a; --c3:#e07b2f; --c4:#c0392b;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--field);color:var(--ink);
  font-family:'IBM Plex Sans Arabic','Space Grotesk',system-ui,sans-serif;
  font-size:14px;-webkit-font-smoothing:antialiased}
body{min-height:100vh;
  background-image:radial-gradient(120% 80% at 50% -10%, #eef1ea 0%, var(--field) 58%);}
.wrap{max-width:1320px;margin:0 auto;padding:0 26px 48px}

/* ── masthead: real Riyadh emblem ─────────────────────────────── */
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

/* ── quick-stats strip ───────────────────────────────────────── */
.statline{display:flex;gap:8px 22px;flex-wrap:wrap;align-items:center;margin:10px 2px 4px;
  padding:9px 14px;background:var(--panel);border:1px solid var(--hair);border-radius:12px;
  font-size:12.5px;color:var(--muted)}
.statline .st b{color:var(--green-2);font-family:'IBM Plex Mono',monospace;font-weight:600}
.statline .st.hot b{color:var(--c4)}
.statline .st.ar{font-family:'Tajawal',sans-serif;direction:rtl;margin-inline-start:auto}

/* ── ring legend ─────────────────────────────────────────────── */
.rings{display:flex;gap:8px;flex-wrap:wrap;margin:12px 2px 16px;align-items:center}
.rings .rl{display:inline-flex;align-items:center;gap:7px;background:var(--panel);
  border:1px solid var(--hair);border-radius:999px;padding:4px 11px 4px 5px;font-size:11.5px}
.rings .num{width:18px;height:18px;border-radius:50%;display:grid;place-items:center;
  font-family:'IBM Plex Mono',monospace;font-size:10px;color:#fff;font-weight:600}
.rings .rl .ar{font-family:'Tajawal',sans-serif;color:var(--muted);direction:rtl;font-size:11px}
.rings .arrow{color:var(--green-line)}

/* ── stage: plate + slip ─────────────────────────────────────── */
.stage{display:grid;grid-template-columns:1fr 380px;gap:22px;align-items:start}
@media(max-width:900px){.stage{grid-template-columns:1fr}}

.plate-card{position:relative;padding:14px;border-radius:18px;
  border:1px solid var(--hair);
  background:radial-gradient(circle at 50% 46%, #fbfdfb 0%, #eef2ec 62%, #e2e8e0 100%);}
.dish{position:relative;aspect-ratio:1/1;max-width:920px;margin:0 auto;border-radius:999px;
  box-shadow:inset 0 0 0 1px var(--green-line), inset 0 0 44px rgba(0,72,48,.10),
             0 18px 40px -22px rgba(0,60,40,.42);
  background:
    repeating-radial-gradient(circle at 50% 50%, rgba(0,96,64,.045) 0 2px, transparent 2px 15px),
    radial-gradient(circle at 50% 42%, #fcfefc 0%, #edf3ee 72%);
  overflow:hidden}
#plate{width:100%;height:100%}
/* centre readout — the plate's nucleus */
.nucleus{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none;z-index:3}
.nucleus .card{text-align:center;transform:translateY(-1px);max-width:196px;padding:12px 16px;
  border-radius:999px;background:radial-gradient(closest-side,rgba(251,252,250,.92),rgba(251,252,250,.5) 62%,transparent)}
.nucleus .val{font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:27px;
  letter-spacing:-1px;color:var(--green-2);line-height:1;text-shadow:0 1px 3px rgba(255,255,255,.9)}
.nucleus .lab{font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);
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

/* colorbar */
.cbar{display:flex;align-items:center;gap:10px;margin:12px 6px 2px}
.cbar .grad{flex:1;height:10px;border-radius:6px;border:1px solid var(--hair)}
.cbar .lab{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);
  min-width:78px}
.cbar-wrap{margin-top:6px}
.cbar-ticks-row{display:flex;align-items:flex-start;gap:10px}
.cbar-ticks-row .spacer{min-width:78px;flex:0 0 78px}
.ticks{display:flex;justify-content:space-between;font-family:'IBM Plex Mono',monospace;
  font-size:9.5px;color:var(--muted);flex:1 1 auto;margin-top:3px}
.ticks span{white-space:nowrap}

/* specimen slip */
.slip{background:var(--panel);border:1px solid var(--hair);border-radius:14px;
  padding:0;overflow:hidden;position:sticky;top:16px}
.slip .head{padding:14px 16px 12px;border-bottom:1px dashed var(--hair);
  background:linear-gradient(180deg,var(--green-tint),var(--panel))}
.slip .eyebrow{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;
  text-transform:uppercase;color:var(--green)}
.slip .eyebrow .ar{font-family:'Tajawal',sans-serif;letter-spacing:0;color:var(--muted)}
.slip .title{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:17px;
  margin:4px 0 0;line-height:1.2;unicode-bidi:plaintext}
.slip .body{padding:14px 16px 16px}
.big{display:flex;align-items:baseline;gap:8px;margin-bottom:12px}
.big .n{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:32px;letter-spacing:-1px}
.big .u{color:var(--muted);font-size:12px}
.readout{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
.cell{border:1px solid var(--hair);border-radius:9px;padding:8px 10px;background:#fdfefd}
.cell .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted)}
.cell .k .ar{font-family:'Tajawal',sans-serif;text-transform:none;letter-spacing:0}
.cell .v{font-family:'IBM Plex Mono',monospace;font-size:18px;margin-top:2px}
.cell.ok .v{color:var(--green-2)}
.cell.hot .v{color:var(--c4)}
.cell.unknown .v{color:#64748b}
.orgs{margin:2px 0 12px}
.orgs .lab{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:6px}
.orgs .lab .ar{font-family:'Tajawal',sans-serif;text-transform:none}
.org{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:13px;unicode-bidi:plaintext}
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
    <span class="ar">أمانة منطقة الرياض · مختبر الأحياء الدقيقة</span>
    <span class="en">Culture Plate — Microbiology Sunburst</span>
  </div>
  <span class="tag">RIYADH MUNICIPALITY · R&amp;D<br><span class="ar2">زراعة العينات ٢٠٢٤–٢٠٢٥</span></span>
</header>

<div class="lede">Every sample, plated and cultured — <b>__TOTAL__</b> readings blooming from the lab's core outward through year, sector, food category, and the organism that <span class="r">spoiled</span> it.</div>
<div class="sub">Angle is how many samples. Colour is contamination — green reads clean, red reads spoiled. Click any colony to zoom; use the breadcrumb or the plate centre to climb back out. <span class="ar">الزاوية = عدد العينات · اللون = نسبة التلوث · انقر للتكبير.</span></div>
<div class="statline">
  <span class="st">Samples <b>__TOTAL__</b> · عينة</span>
  <span class="st hot">Non-compliant <b>__STAT_NC_PCT__</b> of known validity · غير مطابق</span>
  <span class="st">Unknown validity <b>__STAT_UNK__</b> · صلاحية غير معروفة</span>
  <span class="st">Top NC category <b>__STAT_TOPCAT__</b> (__STAT_TOPCAT_N__)</span>
  <span class="st ar">أرقام إجمالية من البيانات المنظفة ٢٠٢٤–٢٠٢٥</span>
</div>

<div class="rings" id="ring_legend">
  <span class="rl"><span class="num" style="background:var(--green-2)">1</span>Year <span class="ar">السنة</span></span>
  <span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--green)">2</span>Sector <span class="ar">القطاع</span></span>
  <span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--peri-2)">3</span>Category <span class="ar">الفئة</span></span>
  <span class="arrow">›</span>
  <span class="rl"><span class="num" style="background:var(--gold)">4</span>Organism <span class="ar">الكائن</span></span>
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
        <span class="metric on" data-m="nc">contamination <span class="ar">التلوث</span></span>
        <span class="metric" data-m="path">pathogen <span class="ar">ممرض</span></span>
        <span class="metric" data-m="vol">volume <span class="ar">الحجم</span></span>
      </span>
    </div>
    <div class="cbar-wrap">
      <div class="cbar">
        <span class="lab" id="cbar_lab">% contaminated</span>
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
  <span>angle = sample volume · الزاوية = الحجم</span>
  <span>click to zoom · center or breadcrumb to reset</span>
  <span class="footer-note"><span class="ar">أمانة منطقة الرياض</span> · updated __STAMP__</span>
</footer>
</div>
<script>
const NODES=__NODES__, STATS=__STATS__, MONTHS=__MONTHS__, VOLMAX=__VOLMAX__;
const CULTURE=[[0,'#1f9d63'],[0.35,'#8fb24a'],[0.6,'#e0a53a'],[0.8,'#e07b2f'],[1,'#c0392b']];
const VOLSCALE=[[0,'#eceef6'],[0.5,'#7f97c4'],[1,'#006040']];  // periwinkle → municipal green
const PARENT={}; NODES.ids.forEach((id,i)=>PARENT[id]=NODES.parents[i]);
let metric='nc', focus='ALL';

// metric config: scale, cap, colorbar label + gradient CSS + tick labels
function mconf(){
  if(metric==='path') return {scale:CULTURE,cmax:30,lab:'% pathogen',
    grad:'linear-gradient(90deg,#1f9d63,#8fb24a,#e0a53a,#e07b2f,#c0392b)',
    ticks:['0','','15','','30%']};
  if(metric==='vol') return {scale:VOLSCALE,cmax:VOLMAX,lab:'samples (volume)',
    grad:'linear-gradient(90deg,#eceef6,#7f97c4,#006040)',
    ticks:['0','','','', (VOLMAX>=1000?(VOLMAX/1000).toFixed(1)+'k':''+VOLMAX)]};
  return {scale:CULTURE,cmax:60,lab:'% contaminated',
    grad:'linear-gradient(90deg,#1f9d63,#8fb24a,#e0a53a,#e07b2f,#c0392b)',
    ticks:['0','','30','','60%']};
}
function colorVals(){
  return NODES.ids.map((id,i)=>{
    const n=NODES.n[i]||1;
    const known=n-(NODES.nu[i]||0);
    const denom=Math.max(known,1);
    if(metric==='vol')  return NODES.n[i]||0;
    if(metric==='path') return 100*(NODES.np[i]||0)/denom;
    return 100*(NODES.nc[i]||0)/denom;
  });
}
const layout={margin:{l:6,r:6,t:6,b:6},paper_bgcolor:'rgba(0,0,0,0)',
  font:{family:"'IBM Plex Sans Arabic','Space Grotesk',sans-serif",color:'#1b2320',size:11},
  sunburstcolorway:['#1f9d63'],extendsunburstcolorway:true};
const config={displayModeBar:false,responsive:true};

function draw(){
  const c=mconf(), vals=colorVals();
  const unit=(metric==='vol')?'':(metric==='path'?'% pathogen':'% contaminated');
  Plotly.react('plate',[{
    type:'sunburst',
    ids:NODES.ids,labels:NODES.labels,parents:NODES.parents,values:NODES.values,
    branchvalues:'total', level:focus,
    customdata:vals,
    marker:{colors:vals,colorscale:c.scale,cmin:0,cmax:c.cmax,
      line:{color:'#f2f6f0',width:1}},
    leaf:{opacity:0.96},
    // Readability: '✓ Compliant' wedges carry no text (blanked in NODES.text —
    // colour already reads clean), Plotly hides labels that don't fit the arc,
    // and 'auto' orientation keeps short names upright where they'll fit.
    text:NODES.text,
    texttemplate:'<b>%{text}</b>',
    textfont:{size:15,family:"'IBM Plex Sans Arabic','Space Grotesk',sans-serif"},
    insidetextorientation:'auto',
    hovertemplate:(metric==='vol')
      ? '<b>%{label}</b><br>%{value:,} samples<extra></extra>'
      : '<b>%{label}</b><br>%{value:,} samples<br>%{customdata:.1f}'+unit+'<extra></extra>',
    hoverlabel:{bgcolor:'#fbfcfa',bordercolor:'#bcd3c7',
      font:{family:"'IBM Plex Sans Arabic',sans-serif",color:'#1b2320'}},
  }],layout,config);
  const cg=document.getElementById('cbar_grad'); cg.style.background=c.grad;
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
  const n=s.n,nc=s.nc,nu=s.nu||0,ok=n-nc-nu;
  const known=Math.max(n-nu,1);
  document.getElementById('s_n').textContent=fmt(n);
  document.getElementById('s_ok').textContent=fmt(ok);
  document.getElementById('s_nc').textContent=fmt(nc);
  document.getElementById('s_unk').textContent=fmt(nu);
  document.getElementById('s_rate').textContent=(100*nc/known).toFixed(1)+'%';
  document.getElementById('s_prate').textContent=(100*s.np/known).toFixed(1)+'%';
  const maxc=Math.max(1,...s.top.map(t=>t[1]));
  document.getElementById('s_orgs').innerHTML= s.top.length
    ? s.top.map(([o,c])=>`<div class="org"><span class="bar" style="width:${8+70*c/maxc}px"></span>
        <span>${o}</span><span class="cnt">${fmt(c)}</span></div>`).join('')
    : '<div class="org" style="color:var(--muted)">no contamination in this culture · لا تلوث</div>';
  document.getElementById('s_spark').innerHTML=sparkline(s.spark);
  // centre nucleus readout — headline for the active metric
  let cv, cl;
  if(metric==='vol'){ cv=fmt(n); cl='samples'; }
  else if(metric==='path'){ cv=(100*s.np/known).toFixed(1)+'%'; cl='pathogen'; }
  else { cv=(100*nc/known).toFixed(1)+'%'; cl='contaminated'; }
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
    s.textContent=lab; s.dataset.id=pid;
    el.appendChild(s);
  });
}
function writeHash(id){
  const h=(id==='ALL')?location.pathname+location.search:'#f='+encodeURIComponent(id);
  history.replaceState(null,'',h);
}
// Sync the chrome (slip / breadcrumb / centre / hash) to a focus WITHOUT
// redrawing — used after Plotly's native click-zoom has already animated.
function sync(id){
  focus=(id&&STATS[id])?id:'ALL';
  showStats(focus); crumb(focus); writeHash(focus);
}
// Programmatic navigation (breadcrumb / deep-link): move Plotly's zoom too.
function navTo(id){
  focus=(id&&STATS[id])?id:'ALL';
  Plotly.restyle('plate',{level:focus});
  showStats(focus); crumb(focus); writeHash(focus);
}

// open at the deep-linked zoom (if any) so the first render is already there
(function(){
  const m=/(?:^|[#&])f=([^&]+)/.exec(location.hash);
  const id=m?decodeURIComponent(m[1]):'ALL';
  focus=STATS[id]?id:'ALL';
})();
draw();
sync(focus);
const gd=document.getElementById('plate');
// Let Plotly play its native smooth zoom (the "stretch"); we only follow along.
// Clicking the current centre climbs out one level, matching native behaviour.
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
