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


def build():
    fonts = FONTS.read_text(encoding="utf-8") if FONTS.exists() else ""
    logo = ("data:image/jpeg;base64," +
            base64.b64encode(LOGO.read_bytes()).decode("ascii")) if LOGO.exists() else ""
    html = (TEMPLATE
            .replace("__FONTS__", f"<style>{fonts}</style>")
            .replace("__LOGO__", logo)
            .replace("__STAMP__", datetime.now().strftime("%d %b %Y")))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB; logo={'yes' if logo else 'MISSING'})")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>R&amp;D · أمانة منطقة الرياض — Food-Safety Lab Analytics</title>
__FONTS__
<style>
:root{
  --green:#006040; --green-2:#004d33; --green-3:#1f9d63;
  --peri:#5f70a2; --peri-2:#8e9fc7;
  --gold:#b08a2e; --field:#e7e8e0; --panel:#fbfcfa; --panel-2:#f4f6f1;
  --ink:#1b2320; --muted:#6a736d; --hair:#d5dbd2;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--field);color:var(--ink);
  font-family:'IBM Plex Sans Arabic','Space Grotesk',system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
body{min-height:100vh;display:flex;flex-direction:column;
  background-image:
    radial-gradient(130% 90% at 50% -20%, #eef1ea 0%, var(--field) 60%),
    radial-gradient(60% 50% at 100% 0%, rgba(95,112,162,.06), transparent 60%);}
.wrap{width:100%;max-width:1080px;margin:0 auto;padding:0 28px 40px;flex:1}
a{color:inherit;text-decoration:none}

/* ── hero ─────────────────────────────────────────────── */
header.hero{padding:44px 4px 26px;position:relative}
.brandline{display:flex;align-items:center;gap:16px}
.emblem{width:60px;height:60px;border-radius:50%;flex:0 0 auto;
  background:#fff center/90% no-repeat;
  box-shadow:0 3px 12px -4px rgba(0,60,40,.45),inset 0 0 0 1px #bcd3c7}
.brandline .ar{font-family:'Tajawal',sans-serif;font-weight:700;font-size:16px;
  color:var(--green);direction:rtl;line-height:1.3}
.brandline .ar small{display:block;font-weight:500;color:var(--muted);font-size:12.5px}
.wordmark{margin:22px 0 0;display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap}
.wordmark h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:76px;
  letter-spacing:-2px;margin:0;line-height:.9;
  background:linear-gradient(180deg,var(--ink),#2f3a34);-webkit-background-clip:text;
  background-clip:text}
.wordmark .amp{color:var(--gold)}
.wordmark .sub{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:12.5px;
  letter-spacing:3px;text-transform:uppercase;color:var(--muted);padding-bottom:9px}
.rule{height:2px;width:130px;margin:20px 0 0;
  background:linear-gradient(90deg,var(--green),var(--gold) 60%,transparent)}
.lede{font-family:'Space Grotesk',sans-serif;font-size:19px;font-weight:500;line-height:1.4;
  max-width:56ch;margin:18px 2px 0;letter-spacing:-.2px}
.lede b{color:var(--green)}
.lede .ar{font-family:'Tajawal',sans-serif;direction:rtl;color:var(--muted);
  font-size:15px;display:block;margin-top:4px}

/* ── the two labs ─────────────────────────────────────── */
.labs{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:34px}
@media(max-width:760px){.labs{grid-template-columns:1fr}
  .wordmark h1{font-size:58px}}

.lab{position:relative;background:var(--panel);border:1px solid var(--hair);
  border-radius:20px;padding:26px 26px 20px;overflow:hidden;
  transition:transform .25s cubic-bezier(.2,.7,.2,1),box-shadow .25s,border-color .25s;
  will-change:transform}
.lab::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;
  background:linear-gradient(90deg,var(--accent),transparent 70%)}
.lab:hover{transform:translateY(-4px);box-shadow:0 24px 50px -30px rgba(0,50,34,.5);
  border-color:var(--accent-line)}
.lab.micro{--accent:var(--green);--accent2:var(--green-3);--accent-line:#bcd3c7;
  --tint:rgba(0,96,64,.07)}
.lab.chem{--accent:var(--peri);--accent2:var(--peri-2);--accent-line:#c3c9e0;
  --tint:rgba(95,112,162,.08)}

.lab-top{display:flex;align-items:center;gap:18px}
/* the plate ring — a preview of that lab's sunburst */
.ring{width:96px;height:96px;border-radius:50%;flex:0 0 auto;position:relative;
  -webkit-mask:radial-gradient(circle,transparent 30px,#000 31px);
          mask:radial-gradient(circle,transparent 30px,#000 31px)}
.ring.micro{background:conic-gradient(from -90deg,
  #1f9d63,#5aa84f,#8fb24a,#e0a53a,#e07b2f,#c0392b,#1f9d63)}
.ring.chem{background:conic-gradient(from -90deg,
  #eceef6,#8e9fc7,#5f70a2,#7f97c4,#1f9d63,#8e9fc7,#eceef6)}
.plate{width:96px;height:96px;flex:0 0 auto;position:relative;display:grid;place-items:center}
.plate .hole{position:absolute;font-family:'IBM Plex Mono',monospace;font-size:11px;
  color:var(--muted);letter-spacing:.5px}
.plate .glyph{position:absolute;color:var(--gold);font-size:15px;opacity:.9}
.lab:hover .ring{animation:spin 9s linear infinite}

.names .kicker{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;
  text-transform:uppercase;color:var(--accent);font-weight:600}
.names h2{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:23px;
  margin:3px 0 1px;letter-spacing:-.4px}
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
.entry .ico{width:34px;height:34px;border-radius:9px;flex:0 0 auto;display:grid;place-items:center;
  background:var(--panel-2);border:1px solid var(--hair);color:var(--accent)}
.entry .txt{flex:1;min-width:0}
.entry .lb{display:block;font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:14.5px}
.entry .sub{display:block;margin-top:2px;font-size:11.5px;color:var(--muted);
  font-family:'IBM Plex Mono',monospace;letter-spacing:.2px}
.entry .arrow{color:var(--accent);font-size:16px;transition:transform .18s;opacity:.55}
.entry:hover .arrow{transform:translateX(4px);opacity:1}

footer{border-top:1px solid var(--hair)}
.foot-in{max-width:1080px;margin:0 auto;padding:16px 28px;display:flex;gap:16px;
  align-items:center;flex-wrap:wrap;color:var(--muted);
  font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.4px}
.foot-in .ar{font-family:'Tajawal',sans-serif;direction:rtl}
.foot-in .sp{margin-inline-start:auto}
.foot-in .signout{color:var(--green);transition:color .15s}
.foot-in .signout:hover,.foot-in .signout:focus-visible{color:var(--green-2);outline:none;text-decoration:underline}

/* motion */
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.hero,.labs>.lab{animation:rise .6s cubic-bezier(.2,.7,.2,1) both}
.labs>.lab:nth-child(1){animation-delay:.10s}
.labs>.lab:nth-child(2){animation-delay:.20s}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="brandline">
      <div class="emblem" style="background-image:url('__LOGO__')"></div>
      <div class="ar">أمانة منطقة الرياض<small>البحث والتطوير · مختبرات سلامة الغذاء</small></div>
    </div>
    <div class="wordmark">
      <h1>R<span class="amp">&amp;</span>D</h1>
      <span class="sub">Research &amp; Development — Food-Safety Lab Analytics</span>
    </div>
    <div class="rule"></div>
    <p class="lede">Two laboratories, one 2024–2025 record. Open each lab as a
      <b>decision dashboard</b> or an <b>interactive plate</b>.
      <span class="ar">مختبران، سجلّ واحد ٢٠٢٤–٢٠٢٥ — لوحة قرار أو عرض تفاعلي.</span>
    </p>
  </header>

  <main class="labs">
    <!-- Microbiology -->
    <section class="lab micro">
      <div class="lab-top">
        <div class="plate">
          <div class="ring micro"></div>
          <span class="glyph">۞</span>
        </div>
        <div class="names">
          <div class="kicker">Laboratory</div>
          <h2>Microbiology</h2>
          <div class="ar">الأحياء الدقيقة</div>
        </div>
      </div>
      <div class="stat"><span class="n">20,880</span><span class="u">samples · 5 sectors · 2024–2025</span></div>
      <div class="desc">Pathogen &amp; indicator screening across Riyadh's sectors — compliance, severity, and the organism behind each failure.</div>
      <div class="entries">
        <a class="entry" href="microbiology/reports/microbiology_dashboard.html">
          <span class="ico">▦</span>
          <span class="txt"><span class="lb">Dashboard</span><span class="sub">filters · Riyadh map · KPIs</span></span>
          <span class="arrow">→</span>
        </a>
        <a class="entry" href="microbiology/reports/microbiology_sunburst.html">
          <span class="ico">◎</span>
          <span class="txt"><span class="lb">Interactive</span><span class="sub">zoomable culture plate</span></span>
          <span class="arrow">→</span>
        </a>
      </div>
    </section>

    <!-- Chemistry -->
    <section class="lab chem">
      <div class="lab-top">
        <div class="plate">
          <div class="ring chem"></div>
          <span class="glyph">۞</span>
        </div>
        <div class="names">
          <div class="kicker">Laboratory</div>
          <h2>Chemistry</h2>
          <div class="ar">الكيمياء</div>
        </div>
      </div>
      <div class="stat"><span class="n">15,876</span><span class="u">records · 8 sections · 2024–2025</span></div>
      <div class="desc">Heavy metals, pesticides, aflatoxins, water &amp; more — limit exceedances and the analyte that failed each assay.</div>
      <div class="entries">
        <a class="entry" href="chemistry/reports/chemistry_dashboard.html">
          <span class="ico">▦</span>
          <span class="txt"><span class="lb">Dashboard</span><span class="sub">filters · Riyadh map · KPIs</span></span>
          <span class="arrow">→</span>
        </a>
        <a class="entry" href="chemistry/reports/chemistry_sunburst.html">
          <span class="ico">◎</span>
          <span class="txt"><span class="lb">Interactive</span><span class="sub">zoomable assay plate</span></span>
          <span class="arrow">→</span>
        </a>
      </div>
    </section>
  </main>
</div>

<footer>
  <div class="foot-in">
    <span class="ar">أمانة منطقة الرياض · البحث والتطوير</span>
    <span>self-contained · opens in any browser</span>
    <a class="sp signout" href="/logout">Sign out →</a>
    <span>build __STAMP__</span>
  </div>
</footer>
</body></html>"""


if __name__ == "__main__":
    build()
