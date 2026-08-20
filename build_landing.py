"""Build the R&D landing page (index.html) — the hub linking both labs'
deliverables. Riyadh-emblem branded, bilingual, self-contained (emblem + fonts
inlined so it matches the dashboards/sunbursts exactly and opens offline).

Run:  microbiology/.venv/bin/python build_landing.py
Out:  index.html   (open in a browser; links are relative to the repo root)
"""
from __future__ import annotations
import base64
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "microbiology" / "vendor" / "fonts_inline.css"
LOGO = ROOT / "microbiology" / "assets" / "riyadh_emblem.jpg"
OUT = ROOT / "index.html"


def _inject(html: str, fonts: str, logo: str, vision: str) -> str:
    return (html
            .replace("__FONTS__", f"<style>{fonts}</style>")
            .replace("__LOGO__", logo)
            .replace("__VISION__", vision)
            .replace("__STAMP__", datetime.now().strftime("%d %b %Y · %H:%M")))


def build():
    fonts = FONTS.read_text(encoding="utf-8") if FONTS.exists() else ""
    logo = ("data:image/jpeg;base64," +
            base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""
            
    vision_file = ROOT / "vision2030.png"
    vision = ("data:image/png;base64," +
              base64.b64encode(vision_file.read_bytes()).decode("ascii")) if vision_file.exists() else ""

    rnd_file = ROOT / "rnd_header.jpg"
    rnd_img = ("data:image/jpeg;base64," +
               base64.b64encode(rnd_file.read_bytes()).decode("ascii")) if rnd_file.exists() else ""

    pipeline_img = ("data:image/jpeg;base64," +
                    base64.b64encode((ROOT / "genome/pipeline_3d.jpg").read_bytes()).decode("ascii")) if (ROOT / "genome/pipeline_3d.jpg").exists() else ""

    # 1) Root hub (index.html) — the two lab gateways.
    root_html = TEMPLATE.replace("__RND_HEADER_IMG__", rnd_img)
    OUT.write_text(_inject(root_html, fonts, logo, vision), encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB; logo={'yes' if logo else 'MISSING'})")

    # 2) One landing page per lab, sharing the hub's <head> (fonts + CSS).
    head = TEMPLATE.split("</head>", 1)[0] + "</head>"
    for lab in LABS:
        if lab["name"] == "Genome":
            body = GENOME_BODY.replace("__LOGO__", logo).replace("__PIPELINE_IMG__", pipeline_img)
            out = ROOT / lab["out"]
            out.parent.mkdir(exist_ok=True)
            out.write_text(_inject(head + body, fonts, logo, vision), encoding="utf-8")
            print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB)")
            continue
        viz = "\n".join(
            '        <a class="viz" href="{2}">\n'
            '          <span class="v-ico">{0}</span>\n'
            '          <div class="v-txt"><div class="v-lb">{1}</div>'
            '<div class="v-sub">{3}</div></div>\n'
            '        </a>'.format(*v) for v in lab["viz"])
        body = (LAB_BODY
                .replace("__ACCENT__", lab["accent"]).replace("__RING__", lab["ring"])
                .replace("__NAME__", lab["name"]).replace("__AR__", lab["ar"])
                .replace("__STAT_N__", lab["stat_n"]).replace("__STAT_U__", lab["stat_u"])
                .replace("__DESC__", lab["desc"]).replace("__DASH__", lab["dash"])
                .replace("__GSO__", lab["gso"]).replace("__REPORT__", lab["report"])
                .replace("__VIZN__", str(len(lab["viz"]))).replace("__VIZ__", viz))
        out = ROOT / lab["out"]
        out.parent.mkdir(exist_ok=True)
        out.write_text(_inject(head + body, fonts, logo, vision), encoding="utf-8")
        print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB)")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>R&amp;D · أمانة منطقة الرياض — مختبرات أمانة منطقة الرياض</title>
__FONTS__
<style>
:root{
  --green:#006040; --green-2:#004d33; --green-3:#1f9d63;
  --peri:#5f70a2; --peri-2:#8e9fc7;
  --gold:#c5a059; --gold-light:#e6d5a1;
  --field:#032018; --panel:rgba(8, 44, 33, 0.85); --panel-2:rgba(4, 26, 19, 0.9);
  --ink:#f0f7f4; --muted:#a0c2b2; --hair:rgba(197, 160, 89, 0.28);
  --accent:#c5a059; --accent-line:rgba(197, 160, 89, 0.4); --tint:rgba(197, 160, 89, 0.12);
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--field);color:var(--ink);
  font-family:'IBM Plex Sans Arabic','Space Grotesk',system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
body{min-height:100vh;display:flex;flex-direction:column;
  background-image:
    radial-gradient(140% 100% at 50% -20%, #094a37 0%, var(--field) 70%),
    radial-gradient(50% 50% at 100% 0%, rgba(197,160,89,.12), transparent 60%);}
.wrap{width:100%;max-width:1080px;margin:0 auto;padding:0 28px 40px;flex:1}
a{color:inherit;text-decoration:none}

/* ── hero ─────────────────────────────────────────────── */
header.hero{padding:44px 4px 26px;position:relative}
.brandline{display:flex;align-items:center;gap:16px}
.emblem{width:64px;height:64px;border-radius:50%;flex:0 0 auto;
  background:#fff center/92% no-repeat;
  box-shadow:0 0 20px rgba(197,160,89,0.35), 0 3px 12px -4px rgba(0,60,40,.6), inset 0 0 0 2px var(--gold)}
.brandline .ar{font-family:'Tajawal',sans-serif;font-weight:700;font-size:17px;
  color:var(--gold);direction:rtl;line-height:1.3}
.brandline .ar small{display:block;font-weight:500;color:var(--muted);font-size:13px}
.wordmark{margin:22px 0 0;display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap}
.wordmark h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:76px;
  letter-spacing:-2px;margin:0;line-height:.9;
  background:linear-gradient(180deg,#ffffff,#c5a059);-webkit-background-clip:text;
  background-clip:text;-webkit-text-fill-color:transparent}
.wordmark .amp{color:var(--gold)}
.wordmark .sub{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:12.5px;
  letter-spacing:3px;text-transform:uppercase;color:var(--muted);padding-bottom:9px}
.rule{height:2px;width:130px;margin:20px 0 0;
  background:linear-gradient(90deg,var(--gold),var(--green-3) 60%,transparent)}
.lede{font-family:'Space Grotesk',sans-serif;font-size:19px;font-weight:500;line-height:1.4;
  max-width:56ch;margin:18px 2px 0;letter-spacing:-.2px;color:var(--ink)}
.lede b{color:var(--gold)}
.lede .ar{font-family:'Tajawal',sans-serif;direction:rtl;color:var(--muted);
  font-size:15.5px;display:block;margin-top:6px}

    /* ── the two labs ─────────────────────────────────────── */
    .labs { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 22px; margin-top: 34px; }
    .hero { display: flex; align-items: center; justify-content: space-between; gap: 32px; flex-wrap: wrap; }
    .hero-content { flex: 1 1 400px; }
    .hero-image { flex: 1 1 400px; text-align: center; }
    .hero-image img { width: 100%; max-width: 500px; border-radius: 24px; box-shadow: 0 16px 50px -12px rgba(0,0,0,0.5); border:1px solid var(--hair); }
    @media(max-width:760px){.labs{grid-template-columns:1fr}
      .wordmark h1{font-size:58px}
      .hero { flex-direction: column; text-align: center; gap: 24px; }
      .brandline { justify-content: center; }
      .wordmark { justify-content: center; }
      .rule { margin: 20px auto 0; }
      .lede { margin: 18px auto 0; }
    }


.lab{position:relative;background:var(--panel);border:1px solid var(--hair);
  border-radius:20px;padding:26px 26px 20px;overflow:hidden;
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  transition:transform .25s cubic-bezier(.2,.7,.2,1),box-shadow .25s,border-color .25s;
  will-change:transform}
.lab::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;
  background:linear-gradient(90deg,var(--accent),transparent 70%)}
.lab:hover{transform:translateY(-4px);box-shadow:0 24px 50px -20px rgba(0,0,0,.7);
  border-color:var(--accent-line)}
.lab.micro{--accent:var(--gold);--accent2:var(--green-3);--accent-line:rgba(197,160,89,0.5);
  --tint:rgba(197,160,89,.12)}
.lab.chem{--accent:var(--peri-2);--accent2:var(--peri);--accent-line:rgba(142,159,199,0.5);
  --tint:rgba(95,112,162,.15)}
.lab.genome{--accent:var(--gold-light);--accent2:var(--gold);--accent-line:rgba(230,213,161,0.5);
  --tint:rgba(176,138,46,.15)}

.lab-top{display:flex;align-items:center;gap:18px}
.emblem-shield{width:76px;height:76px;border-radius:20px;flex:0 0 auto;position:relative;
  background:linear-gradient(135deg, rgba(0,96,64,0.4), rgba(197,160,89,0.25));
  border:1px solid var(--hair);display:grid;place-items:center;
  box-shadow:0 8px 24px -6px rgba(0,0,0,0.4);transition:transform .3s, box-shadow .3s}
.lab:hover .emblem-shield{transform:scale(1.05);box-shadow:0 12px 30px -4px rgba(197,160,89,0.3)}
.emblem-shield .emblem-img{width:46px;height:46px;border-radius:50%;background:#fff center/90% no-repeat;
  box-shadow:0 0 10px rgba(0,0,0,0.3);border:1px solid var(--gold)}
.emblem-shield .badge-ico{position:absolute;bottom:-4px;right:-4px;font-size:16px;background:var(--field);
  border:1px solid var(--hair);border-radius:50%;padding:2px 4px}

.names .kicker{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;
  text-transform:uppercase;color:var(--accent);font-weight:600}
.names h2{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:23px;
  margin:3px 0 1px;letter-spacing:-.4px;color:#fff}
.names .ar{font-family:'Tajawal',sans-serif;font-weight:700;font-size:15px;
  color:var(--muted);direction:rtl}

.stat{display:flex;align-items:baseline;gap:8px;margin:16px 2px 2px}
.stat .n{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:26px;
  letter-spacing:-1px;color:var(--accent)}
.stat .u{font-size:12px;color:var(--muted)}
.desc{color:var(--muted);font-size:13px;line-height:1.5;margin:6px 2px 0;min-height:38px}

.entries{margin-top:16px;border-top:1px dashed var(--hair);padding-top:6px}
.entry{display:flex;align-items:center;gap:12px;padding:12px 12px;border-radius:12px;
  transition:background .16s,padding .16s;cursor:pointer}
.entry:hover,.entry:focus-visible{background:var(--tint);outline:none;padding-inline-start:16px}
.entry:focus-visible{box-shadow:inset 0 0 0 2px var(--accent)}
.entry.disabled{opacity:.6;cursor:not-allowed;pointer-events:none}
.entry.disabled .arrow{opacity:.35}
.entry .ico{width:34px;height:34px;border-radius:9px;flex:0 0 auto;display:grid;place-items:center;
  background:var(--panel-2);border:1px solid var(--hair);color:var(--accent)}
.entry .txt{flex:1;min-width:0}
.entry .lb{display:block;font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:14.5px;color:#fff}
.entry .sub{display:block;margin-top:2px;font-size:11.5px;color:var(--muted);
  font-family:'IBM Plex Mono',monospace;letter-spacing:.2px}
.entry .arrow{color:var(--accent);font-size:16px;transition:transform .18s;opacity:.55}
.entry:hover .arrow{transform:translateX(4px);opacity:1}

footer{border-top:1px solid var(--hair);background:rgba(0,0,0,0.2)}
.foot-in{max-width:1080px;margin:0 auto;padding:16px 28px;display:flex;gap:16px;
  align-items:center;flex-wrap:wrap;color:var(--muted);
  font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.4px}
.foot-in .ar{font-family:'Tajawal',sans-serif;direction:rtl;color:var(--gold)}
.foot-in .sp{margin-inline-start:auto}
.foot-in .signout{color:var(--gold);transition:color .15s}
.foot-in .signout:hover,.foot-in .signout:focus-visible{color:#fff;outline:none;text-decoration:underline}

/* motion */
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.hero,.labs>.lab{animation:rise .6s cubic-bezier(.2,.7,.2,1) both}
.labs>.lab:nth-child(1){animation-delay:.10s}
.labs>.lab:nth-child(2){animation-delay:.20s}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}

/* ══ root card → gateway to the per-lab hub ══ */
.card-dests{display:flex;flex-wrap:wrap;gap:7px;margin-top:2px}
.dest{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);
  background:var(--panel-2);border:1px solid var(--hair);border-radius:999px;padding:5px 11px}
.enter{margin-top:16px;display:flex;align-items:center;gap:8px;
  font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:14px;color:var(--accent)}
.enter .arrow{transition:transform .18s}
.lab:hover .enter .arrow,.lab:focus-visible .enter .arrow{transform:translateX(5px)}
.lab:focus-visible{outline:none;box-shadow:0 0 0 3px var(--accent-line)}

/* ══ per-lab landing page ══ */
body.labpage{--accent:var(--gold);--accent2:var(--green-3);--accent-line:rgba(197,160,89,0.5);--tint:rgba(197,160,89,.12)}
body.labpage.chem{--accent:var(--peri-2);--accent2:var(--peri);--accent-line:rgba(142,159,199,0.5);--tint:rgba(95,112,162,.15)}
body.labpage.genome{--accent:var(--gold-light);--accent2:var(--gold);--accent-line:rgba(230,213,161,0.5);--tint:rgba(176,138,46,.15)}
.crumb{display:flex;align-items:center;gap:9px;margin:30px 2px 0;
  font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted)}
.crumb a{color:var(--accent);font-weight:600}
.crumb a:hover,.crumb a:focus-visible{text-decoration:underline;outline:none}
.crumb .sep{opacity:.5}
.lab-hero{display:flex;align-items:center;gap:22px;margin:20px 2px 0;flex-wrap:wrap}
.lab-hero .h-txt{min-width:220px}
.lab-hero .kicker{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;
  text-transform:uppercase;color:var(--accent);font-weight:600}
.lab-hero h1{font-family:'Space Grotesk',sans-serif;font-weight:700;
  font-size:clamp(30px,7vw,46px);letter-spacing:-1.5px;margin:3px 0 2px;line-height:.95;color:#fff}
.lab-hero .ar{font-family:'Tajawal',sans-serif;font-weight:700;font-size:16px;
  color:var(--muted);direction:rtl}
.lab-hero .h-stat{margin-left:auto;text-align:right}
.lab-hero .h-stat .n{font-family:'IBM Plex Mono',monospace;font-weight:500;
  font-size:clamp(24px,6vw,32px);letter-spacing:-1px;color:var(--accent);display:block}
.lab-hero .h-stat .u{font-size:12px;color:var(--muted)}
@media(max-width:620px){.lab-hero .h-stat{margin-left:0;text-align:left;width:100%}}
.lab-desc{color:var(--muted);font-size:14px;line-height:1.55;max-width:64ch;margin:16px 2px 0}
.portals{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:24px}
@media(max-width:820px){.portals{grid-template-columns:1fr 1fr}}
@media(max-width:520px){.portals{grid-template-columns:1fr}}
.portal{display:flex;flex-direction:column;gap:11px;padding:22px 22px 18px;border-radius:18px;
  background:var(--panel);border:1px solid var(--hair);position:relative;overflow:hidden;min-height:158px;
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  transition:transform .22s cubic-bezier(.2,.7,.2,1),box-shadow .22s,border-color .22s}
.portal::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;
  background:linear-gradient(90deg,var(--accent),transparent 70%)}
.portal:hover,.portal:focus-visible{transform:translateY(-4px);
  box-shadow:0 22px 46px -20px rgba(0,0,0,.7);border-color:var(--accent-line);outline:none}
.portal .p-ico{width:46px;height:46px;border-radius:12px;display:grid;place-items:center;font-size:22px;
  background:var(--panel-2);border:1px solid var(--hair);color:var(--accent)}
.portal .p-lb{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:19px;letter-spacing:-.3px;color:#fff}
.portal .p-sub{font-size:12.5px;color:var(--muted);line-height:1.45;flex:1}
.portal .p-go{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--accent);
  letter-spacing:.5px;display:flex;align-items:center;gap:6px}
.portal .p-go .arrow{transition:transform .18s}
.portal:hover .p-go .arrow,.portal:focus-visible .p-go .arrow{transform:translateX(4px)}
.section-head{display:flex;align-items:baseline;gap:12px;margin:36px 2px 0;flex-wrap:wrap}
.section-head h3{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:14px;
  letter-spacing:1px;text-transform:uppercase;color:var(--accent);margin:0}
.section-head .sh-sub{font-size:12px;color:var(--muted)}
.viz-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:14px}
.viz{display:flex;align-items:center;gap:12px;padding:13px 14px;border-radius:12px;
  background:var(--panel);border:1px solid var(--hair);backdrop-filter:blur(10px);
  transition:transform .16s,background .16s,border-color .16s}
.viz:hover,.viz:focus-visible{transform:translateY(-2px);border-color:var(--accent-line);
  background:var(--tint);outline:none}
.viz .v-ico{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;flex:0 0 auto;
  background:var(--panel-2);border:1px solid var(--hair);color:var(--accent)}
.viz .v-txt{min-width:0}
.viz .v-lb{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:13.5px;color:#fff}
.viz .v-sub{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-top:2px}
body.labpage .portal,body.labpage .viz{animation:rise .5s cubic-bezier(.2,.7,.2,1) both}
body.labpage .portals>.portal:nth-child(2){animation-delay:.06s}
body.labpage .portals>.portal:nth-child(3){animation-delay:.12s}
</style></head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="hero-content">
      <div class="brandline">
        <div class="emblem" style="background-image:url('__LOGO__')"></div>
        <div class="ar">أمانة منطقة الرياض<small>البحث والتطوير · مختبرات أمانة منطقة الرياض</small></div>
      </div>
      <div class="wordmark">
        <h1>R<span class="amp">&amp;</span>D</h1>
        <span class="sub">Research &amp; Development — Riyadh Municipality Labs</span>
      </div>
      <div class="rule"></div>
      <p class="lede">Analytics hub for Riyadh Municipality laboratories. Select a laboratory to explore its
        <b>dashboard</b>, <b>GSO guidelines</b>, <b>analytical reports</b>, and <b>interactive visualisations</b>.
        <span class="ar">المنصة التحليلية المتكاملة لمختبرات أمانة منطقة الرياض — استعرض اللوحات التفاعلية والتقارير.</span>
      </p>
    </div>
    <div class="hero-image">
      <img src="__RND_HEADER_IMG__" alt="Riyadh Municipality R&D Labs" />
    </div>
  </header>

  <main class="labs">
    <!-- Microbiology -->
    <a class="lab micro" href="microbiology/index.html">
      <div class="lab-top">
        <div class="emblem-shield micro">
          <div class="emblem-img" style="background-image:url('__LOGO__')"></div>
          <span class="badge-ico">🧫</span>
        </div>
        <div class="names">
          <div class="kicker">مختبرات أمانة منطقة الرياض</div>
          <h2>Microbiology</h2>
          <div class="ar">الأحياء الدقيقة</div>
        </div>
      </div>
      <div class="stat"><span class="n">20,881</span><span class="u">samples · 5 sectors · 2024–2025</span></div>
      <div class="desc">Pathogen &amp; indicator screening across Riyadh's sectors — compliance, severity, and the organism behind each failure.</div>
      <div class="entries">
        <div class="card-dests">
          <span class="dest">▦ Dashboard</span>
          <span class="dest">📋 GSO &amp; Quality</span>
          <span class="dest">📄 Report</span>
          <span class="dest">◎ 7 visualisations</span>
        </div>
        <div class="enter">Enter lab <span class="arrow">→</span></div>
      </div>
    </a>

    <!-- Chemistry -->
    <a class="lab chem" href="chemistry/index.html">
      <div class="lab-top">
        <div class="emblem-shield chem">
          <div class="emblem-img" style="background-image:url('__LOGO__')"></div>
          <span class="badge-ico">🧪</span>
        </div>
        <div class="names">
          <div class="kicker">مختبرات أمانة منطقة الرياض</div>
          <h2>Chemistry</h2>
          <div class="ar">الكيمياء</div>
        </div>
      </div>
      <div class="stat"><span class="n">15,876</span><span class="u">records · 8 sections · 2024–2025</span></div>
      <div class="desc">Heavy metals, pesticides, aflatoxins, water &amp; more — limit exceedances and the analyte that failed each assay.</div>
      <div class="entries">
        <div class="card-dests">
          <span class="dest">▦ Dashboard</span>
          <span class="dest">📋 GSO &amp; Quality</span>
          <span class="dest">📄 Report</span>
          <span class="dest">◎ 2 visualisations</span>
        </div>
        <div class="enter">Enter lab <span class="arrow">→</span></div>
      </div>
    </a>

    <!-- Genome -->
    <a class="lab genome" href="genome/index.html">
      <div class="lab-top">
        <div class="emblem-shield genome">
          <div class="emblem-img" style="background-image:url('__LOGO__')"></div>
          <span class="badge-ico">🧬</span>
        </div>
        <div class="names">
          <div class="kicker">مختبرات أمانة منطقة الرياض</div>
          <h2>Genome</h2>
          <div class="ar">الجينوم (Amplicon)</div>
        </div>
      </div>
      <div class="stat"><span class="n">Amplicon</span><span class="u">16S rRNA &amp; ITS Pipeline</span></div>
      <div class="desc">Amplicon-based sequencing pipeline (16S &amp; ITS profiling) for bacterial and fungal community analysis. (Metagenomics planned for future expansion).</div>
      <div class="entries">
        <div class="card-dests">
          <span class="dest">🧬 Amplicon Reads</span>
          <span class="dest">✂️ Primer Removal</span>
          <span class="dest">🧩 ASV Denoising</span>
          <span class="dest">🏷️ Taxonomy</span>
          <span class="dest">🔬 Metagenomics (Future)</span>
        </div>
        <div class="enter">Enter lab <span class="arrow">→</span></div>
      </div>
    </a>
  </main>

</div>

<footer>
  <div class="foot-in">
    <span class="ar">أمانة منطقة الرياض · البحث والتطوير</span>
    <span>self-contained · opens in any browser</span>
    <a class="sp signout" href="/logout">Sign out →</a>
    <img src="__VISION__" alt="Saudi Vision 2030" style="height:32px; object-fit:contain; opacity:0.85;" />
    <span>build __STAMP__</span>
  </div>
</footer>
</body></html>"""


LAB_BODY = r"""<body class="labpage__ACCENT__">
<div class="wrap">
  <header class="hero" style="padding-bottom:6px">
    <div class="brandline">
      <div class="emblem" style="background-image:url('__LOGO__')"></div>
      <div class="ar">أمانة منطقة الرياض<small>البحث والتطوير · مختبرات أمانة منطقة الرياض</small></div>
    </div>
  </header>

  <nav class="crumb"><a href="../index.html">← R&amp;D</a><span class="sep">/</span><span>__NAME__</span></nav>

  <section class="lab-hero">
    <div class="emblem-shield __RING__" style="width:84px; height:84px">
      <div class="emblem-img" style="width:52px; height:52px; background-image:url('__LOGO__')"></div>
      <span class="badge-ico" style="font-size:18px">۞</span>
    </div>
    <div class="h-txt">
      <div class="kicker">مختبرات أمانة منطقة الرياض</div>
      <h1>__NAME__</h1>
      <div class="ar">__AR__</div>
    </div>
    <div class="h-stat"><span class="n">__STAT_N__</span><span class="u">__STAT_U__</span></div>
  </section>
  <p class="lab-desc">__DESC__</p>

  <div class="portals">
    <a class="portal" href="__DASH__">
      <div class="p-ico">▦</div>
      <div class="p-lb">Dashboard</div>
      <div class="p-sub">Interactive decision board — year/section filters, Riyadh map, KPI strips, per-tab charts.</div>
      <div class="p-go">Open <span class="arrow">→</span></div>
    </a>
    <a class="portal" href="__GSO__">
      <div class="p-ico">📋</div>
      <div class="p-lb">GSO &amp; Quality</div>
      <div class="p-sub">GSO 1016 mapping guideline, sortable category table, and the data-quality audit.</div>
      <div class="p-go">Open <span class="arrow">→</span></div>
    </a>
    <a class="portal" href="__REPORT__">
      <div class="p-ico">📄</div>
      <div class="p-lb">Report</div>
      <div class="p-sub">Statistics, GSO challenges, numerical ledger, and the enhancement roadmap.</div>
      <div class="p-go">Open <span class="arrow">→</span></div>
    </a>
  </div>

  <div class="section-head">
    <h3>Visualisations</h3>
    <span class="sh-sub">__VIZN__ interactive views · zoomable · self-contained</span>
  </div>
  <div class="viz-grid">
__VIZ__
  </div>
</div>

<footer>
  <div class="foot-in">
    <span class="ar">أمانة منطقة الرياض · البحث والتطوير</span>
    <span>self-contained · opens in any browser</span>
    <a class="sp signout" href="../index.html">← Back to R&amp;D</a>
    <img src="__VISION__" alt="Saudi Vision 2030" style="height:32px; object-fit:contain; opacity:0.85;" />
    <span>build __STAMP__</span>
</footer>
</body></html>"""


GENOME_BODY = r"""<body class="labpage genome">
<style>
/* Modern Pipeline & Under Construction */
.pipeline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 16px 8px;
  overflow-x: auto;
  gap: 8px;
}
.pipe-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  position: relative;
  flex: 1;
  text-align: center;
  min-width: 100px;
}
.pipe-node .icon-wrap {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  background: linear-gradient(135deg, var(--panel), var(--panel-2));
  border: 1px solid var(--accent-line);
  display: grid;
  place-items: center;
  font-size: 28px;
  color: var(--accent);
  box-shadow: 0 12px 24px -8px rgba(176,138,46,0.3);
  position: relative;
  z-index: 2;
  transition: transform 0.2s, box-shadow 0.2s;
}
.pipe-node:hover .icon-wrap {
  transform: translateY(-4px) scale(1.05);
  box-shadow: 0 16px 32px -8px rgba(176,138,46,0.4);
  border-color: var(--accent);
}
.pipe-node .label {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 14.5px;
  color: var(--ink);
  letter-spacing: -0.2px;
}
.pipe-edge {
  flex: 0 0 auto;
  width: clamp(20px, 4vw, 50px);
  height: 3px;
  background: linear-gradient(90deg, var(--accent-line), var(--accent));
  border-radius: 2px;
  position: relative;
  opacity: 0.8;
  margin-top: -34px;
}
.pipe-edge::after {
  content: "";
  position: absolute;
  right: -2px;
  top: -3px;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  border-left: 6px solid var(--accent);
}

.portal.uc {
  position: relative;
  border-style: dashed;
}
.uc-badge {
  position: absolute;
  top: 14px;
  right: 14px;
  background: rgba(176,138,46,0.1);
  color: var(--accent);
  border: 1px solid rgba(176,138,46,0.25);
  padding: 4px 10px;
  border-radius: 999px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.uc-badge::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(176,138,46,0.6); }
  70% { box-shadow: 0 0 0 6px rgba(176,138,46,0); }
  100% { box-shadow: 0 0 0 0 rgba(176,138,46,0); }
}
.portal.uc .p-ico {
  background: transparent;
  border-color: transparent;
  font-size: 32px;
  margin-bottom: -4px;
}
</style>
<div class="wrap">
  <header class="hero" style="padding-bottom:6px">
    <div class="brandline">
      <div class="emblem" style="background-image:url('__LOGO__')"></div>
      <div class="ar">أمانة منطقة الرياض<small>البحث والتطوير · مختبرات سلامة الغذاء</small></div>
    </div>
  </header>
  <nav class="crumb"><a href="../index.html">← R&amp;D</a><span class="sep">/</span><span>Genome</span></nav>
  <section class="lab-hero">
    <div class="plate">
      <div class="ring genome"></div>
      <span class="glyph">۞</span>
    </div>
    <div class="h-txt">
      <div class="kicker">Laboratory · مختبر</div>
      <h1>Genome</h1>
      <div class="ar">الجينوم</div>
    </div>
    <div class="h-stat"><span class="n" style="font-size:24px">Building Pipeline</span></div>
  </section>
  <p class="lab-desc">Targeted metagenomics (amplicon) pipeline — 16S rRNA &amp; ITS marker-gene profiling of bacterial and fungal communities, from raw reads to diversity.</p>

  <div class="section-head">
    <h3>Pipeline Construction Flow</h3>
    <span class="sh-sub">Amplicon analysis stages · 16S / ITS</span>
  </div>
  
  <div class="viz-grid" style="margin-top:16px; margin-bottom:32px;">
      <div class="viz" style="grid-column: 1 / -1; display:flex; justify-content:center; align-items:center; padding: 24px; overflow: hidden; background: var(--panel); border-radius: 20px; box-shadow: 0 8px 30px -12px rgba(0,0,0,0.06); border-color: transparent;">
         <img src="__PIPELINE_IMG__" alt="Genome Pipeline 3D Graphic" style="width:100%; max-width:800px; height:auto; border-radius: 12px;" />
      </div>
  </div>

  <div class="portals" style="grid-template-columns:repeat(auto-fit, minmax(260px, 1fr))">
    <div class="portal uc">
      <div class="uc-badge">Building</div>
      <div class="p-ico">🧬</div>
      <div class="p-lb">Amplicon Reads</div>
      <div class="p-sub">Demultiplexed 16S rRNA &amp; ITS marker-gene reads; FASTQC quality assessment and per-run QC.</div>
    </div>
    <div class="portal uc">
      <div class="uc-badge">Building</div>
      <div class="p-ico">✂️</div>
      <div class="p-lb">Primer Removal &amp; QC</div>
      <div class="p-sub">Cutadapt primer/adapter trimming and DADA2 quality filtering, truncation, and error-rate learning.</div>
    </div>
    <div class="portal uc">
      <div class="uc-badge">Building</div>
      <div class="p-ico">🧮</div>
      <div class="p-lb">Denoising → ASVs</div>
      <div class="p-sub">DADA2 error-model denoising into exact amplicon sequence variants (ASVs), read merging, and chimera removal.</div>
    </div>
    <div class="portal uc">
      <div class="uc-badge">Building</div>
      <div class="p-ico">🏷️</div>
      <div class="p-lb">Taxonomic Classification</div>
      <div class="p-sub">ASV taxonomy against curated references — SILVA / GTDB for 16S bacteria, UNITE for ITS fungi.</div>
    </div>
    <div class="portal uc">
      <div class="uc-badge">Building</div>
      <div class="p-ico">📊</div>
      <div class="p-lb">Community &amp; Diversity</div>
      <div class="p-sub">Alpha/beta diversity, community composition, and differential-abundance analysis across samples.</div>
    </div>
  </div>
</div>
<footer>
  <div class="foot-in">
    <span class="ar">أمانة منطقة الرياض · البحث والتطوير</span>
    <span>self-contained · opens in any browser</span>
    <a class="sp signout" href="../index.html">← Back to R&amp;D</a>
    <img src="__VISION__" alt="Saudi Vision 2030" style="height:32px; object-fit:contain; opacity:0.85;" />
    <span>build __STAMP__</span>
  </div>
</footer>
</body></html>"""


LABS = [
    dict(
        out="genome/index.html", accent=" genome", ring="genome",
        name="Genome", ar="الجينوم",
        stat_n="", stat_u="", desc="", dash="", gso="", report="", viz=[]
    ),

    dict(
        out="microbiology/index.html", accent="", ring="micro",
        name="Microbiology", ar="الأحياء الدقيقة",
        stat_n="20,881", stat_u="samples · 5 sectors · 2024–2025",
        desc="Pathogen &amp; indicator screening across Riyadh's sectors — compliance, "
             "severity, and the organism behind each failure.",
        dash="reports/microbiology_dashboard.html",
        gso="reports/microbiology_dashboard.html#tab=gso&focus=1",
        report="reports/microbiology_comprehensive_report.html",
        viz=[
            ("◎", "Sunburst", "reports/microbiology_sunburst.html", "Plotly · zoomable culture plate"),
            ("◐", "Sunburst · D3", "reports/microbiology_sunburst2.html", "D3 · sunburst-chart"),
            ("🔀", "Sankey", "reports/microbiology_sankey.html", "sector → food → organism → severity"),
            ("🟦", "Treemap", "reports/microbiology_treemap.html", "hierarchy &amp; volume"),
            ("🔥", "Heatmap", "reports/microbiology_heatmap_matrix.html", "sector × pathogen matrix"),
            ("🕸️", "Network", "reports/microbiology_network.html", "food ↔ microbe graph"),
            ("📈", "Streamgraph", "reports/microbiology_streamgraph.html", "organism trends over time"),
        ],
    ),
    dict(
        out="chemistry/index.html", accent=" chem", ring="chem",
        name="Chemistry", ar="الكيمياء",
        stat_n="15,876", stat_u="records · 8 sections · 2024–2025",
        desc="Heavy metals, pesticides, aflatoxins, water &amp; more — limit exceedances "
             "and the analyte that failed each assay.",
        dash="reports/chemistry_dashboard.html",
        gso="reports/chemistry_dashboard.html#tab=gso&focus=1",
        report="reports/chemistry_comprehensive_report.html",
        viz=[
            ("◎", "Sunburst", "reports/chemistry_sunburst.html", "Plotly · zoomable assay plate"),
            ("◐", "Sunburst · D3", "reports/chemistry_sunburst2.html", "D3 · sunburst-chart"),
        ],
    ),
]


if __name__ == "__main__":
    build()
