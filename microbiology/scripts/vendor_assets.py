"""One-time (reproducible) vendoring of the demo assets so the standalone demos
work fully OFFLINE — no CDN. Downloads plotly.min.js and builds a self-contained
@font-face stylesheet with every woff2 embedded as a base64 data: URI.

Run once (needs network):
  microbiology/.venv/bin/python microbiology/scripts/vendor_assets.py
Writes: microbiology/vendor/plotly-2.35.2.min.js
        microbiology/vendor/fonts_inline.css
"""
from __future__ import annotations
import base64
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
PLOTLY_URL = "https://cdn.plot.ly/plotly-2.35.2.min.js"
# Union of every family/weight used across the three demos.
FONTS_URL = ("https://fonts.googleapis.com/css2?"
             "family=Space+Grotesk:wght@400;500;700"
             "&family=IBM+Plex+Mono:wght@400;500;600"
             "&family=IBM+Plex+Sans+Arabic:wght@300;400;500;600"
             "&family=Tajawal:wght@400;500;700"
             "&family=Fraunces:opsz,wght@9..144,500;9..144,600"
             "&display=swap")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


def fetch(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    return data if binary else data.decode("utf-8")


def build():
    VENDOR.mkdir(exist_ok=True)

    print("↓ plotly …")
    (VENDOR / "plotly-2.35.2.min.js").write_bytes(fetch(PLOTLY_URL, binary=True))

    print("↓ fonts css …")
    css = fetch(FONTS_URL)
    urls = re.findall(r"url\((https://[^)]+\.woff2)\)", css)
    print(f"  embedding {len(urls)} woff2 files")
    cache: dict[str, str] = {}
    for u in dict.fromkeys(urls):
        b = fetch(u, binary=True)
        cache[u] = "data:font/woff2;base64," + base64.b64encode(b).decode("ascii")
    css_inline = re.sub(r"url\((https://[^)]+\.woff2)\)",
                        lambda m: f"url({cache[m.group(1)]})", css)
    (VENDOR / "fonts_inline.css").write_text(css_inline, encoding="utf-8")

    pj = (VENDOR / "plotly-2.35.2.min.js").stat().st_size
    fc = (VENDOR / "fonts_inline.css").stat().st_size
    print(f"wrote {VENDOR}/plotly-2.35.2.min.js ({pj//1024} KB)")
    print(f"wrote {VENDOR}/fonts_inline.css ({fc//1024} KB, {len(cache)} fonts)")


if __name__ == "__main__":
    build()
