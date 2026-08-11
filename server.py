"""R&D hub server — serves the landing page + both labs' deliverables behind a
simple branded sign-in. Standard library only (no dependencies), so it runs
anywhere, including Railway with `web: python server.py`.

Credentials default to demo / demo; override on Railway with the AUTH_USER and
AUTH_PASS environment variables. The server binds the PORT env var (Railway sets
it) or 8000 locally. Only the landing page and the four deliverable HTMLs are
served; every other path 404s even once signed in.
"""
from __future__ import annotations
import base64
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
USER = os.environ.get("AUTH_USER", "demo")
PASS = os.environ.get("AUTH_PASS", "demo")
COOKIE = "rnd_auth"
TOKEN = "ok"  # demo gate — the credential (demo/demo) is the only secret

ALLOW_PREFIX = ("microbiology/reports/", "chemistry/reports/",
                "Gemini-reports/",
                "microbiology/index.html", "chemistry/index.html")
# Deliverable HTML (dashboards, sunbursts, reports) has no built-in nav — the
# server injects a floating Hub/Sign-out control so viewers are never stranded.
# The lab hub + lab index pages have their own nav, so they are excluded.
DELIVERABLE_PREFIX = ("microbiology/reports/", "chemistry/reports/", "Gemini-reports/")
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css",
        ".js": "application/javascript", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml",
        ".json": "application/json", ".ico": "image/x-icon"}

# Self-contained floating nav injected before </body> on deliverable pages.
# Absolute links (/ and /logout) resolve from any folder depth when served.
NAV_HTML = """
<style>
#rnd-nav{position:fixed;top:10px;right:10px;z-index:2147483647;display:flex;gap:6px;
  font-family:'Space Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif}
#rnd-nav a{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:999px;
  font-size:12.5px;font-weight:600;letter-spacing:.2px;text-decoration:none;color:#fff;
  background:rgba(0,77,51,.92);border:1px solid rgba(255,255,255,.24);
  box-shadow:0 4px 14px -4px rgba(0,50,34,.55);-webkit-backdrop-filter:blur(4px);
  backdrop-filter:blur(4px);opacity:.85;transition:background .15s,opacity .15s,transform .12s}
#rnd-nav a:hover,#rnd-nav a:focus-visible{opacity:1;transform:translateY(-1px);outline:none}
#rnd-nav a:focus-visible{box-shadow:0 0 0 3px rgba(255,255,255,.6)}
#rnd-nav a.hub:hover,#rnd-nav a.hub:focus-visible{background:#004d33}
#rnd-nav a.out{background:rgba(122,38,22,.92)}
#rnd-nav a.out:hover,#rnd-nav a.out:focus-visible{background:#7a2616}
@media print{#rnd-nav{display:none}}
@media(max-width:520px){#rnd-nav{top:8px;right:8px}#rnd-nav a{padding:6px 10px;font-size:11.5px}}
@media(prefers-reduced-motion:reduce){#rnd-nav a{transition:none}}
</style>
<nav id="rnd-nav" aria-label="R&amp;D navigation">
  <a class="hub" href="/" title="Back to the R&amp;D hub">⌂ Hub</a>
  <a class="out" href="/logout" title="Sign out">Sign out</a>
</nav>
"""
NAV_BYTES = NAV_HTML.encode("utf-8")


def _inject_nav(data: bytes) -> bytes:
    """Splice the floating nav in before the last </body> (bytes-level, no full decode)."""
    i = data.rfind(b"</body>")
    return data + NAV_BYTES if i == -1 else data[:i] + NAV_BYTES + data[i:]


def _b64(rel: str) -> str:
    f = ROOT / rel
    return base64.b64encode(f.read_bytes()).decode() if f.exists() else ""


_ff = ROOT / "microbiology" / "vendor" / "fonts_inline.css"
FONTS = "<style>%s</style>" % _ff.read_text(encoding="utf-8") if _ff.exists() else ""
LOGO = "data:image/jpeg;base64," + _b64("microbiology/assets/riyadh_emblem.jpg")


def login_page(error: str = "") -> str:
    err = f'<div class="err">{error}</div>' if error else ""
    return (LOGIN_HTML.replace("__FONTS__", FONTS)
                      .replace("__LOGO__", LOGO)
                      .replace("__ERROR__", err))


class Handler(BaseHTTPRequestHandler):
    server_version = "RnDHub/1.0"

    def _authed(self) -> bool:
        return f"{COOKIE}={TOKEN}" in (self.headers.get("Cookie") or "")

    def _send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            return self._send(200, login_page())
        if path == "/logout":
            return self._send(302, b"", headers={
                "Location": "/login",
                "Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0"})
        if path in ("/healthz", "/health"):
            return self._send(200, b"ok", "text/plain")
        if not self._authed():
            return self._send(302, b"", headers={"Location": "/login"})

        rel = "index.html" if path == "/" else urllib.parse.unquote(path.lstrip("/"))
        if rel != "index.html" and not rel.startswith(ALLOW_PREFIX):
            return self._send(404, b"Not found", "text/plain")
        target = (ROOT / rel).resolve()
        if ROOT not in target.parents or not target.is_file():
            return self._send(404, b"Not found", "text/plain")
        ctype = MIME.get(target.suffix.lower(), "application/octet-stream")
        data = target.read_bytes()
        if ctype.startswith("text/html") and rel.startswith(DELIVERABLE_PREFIX):
            data = _inject_nav(data)
        return self._send(200, data, ctype)

    do_HEAD = do_GET

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))
            if form.get("u", [""])[0] == USER and form.get("p", [""])[0] == PASS:
                return self._send(302, b"", headers={
                    "Location": "/",
                    "Set-Cookie": f"{COOKIE}={TOKEN}; Path=/; HttpOnly; SameSite=Lax"})
            return self._send(401, login_page("Wrong username or password."))
        return self._send(404, b"Not found", "text/plain")

    def log_message(self, *args):
        pass  # quiet


LOGIN_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in · R&amp;D — أمانة منطقة الرياض</title>
__FONTS__
<style>
:root{--green:#006040;--green-2:#004d33;--gold:#b08a2e;--field:#e7e8e0;
  --panel:#fbfcfa;--ink:#1b2320;--muted:#6a736d;--hair:#d5dbd2;--peri:#5f70a2}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{min-height:100vh;display:grid;place-items:center;background:var(--field);
  color:var(--ink);font-family:'IBM Plex Sans Arabic','Space Grotesk',system-ui,sans-serif;
  background-image:radial-gradient(120% 80% at 50% -10%,#eef1ea,var(--field) 60%),
    radial-gradient(50% 50% at 100% 100%,rgba(95,112,162,.07),transparent 60%);
  -webkit-font-smoothing:antialiased;padding:24px}
.card{width:100%;max-width:388px;background:var(--panel);border:1px solid var(--hair);
  border-radius:20px;padding:30px 30px 26px;position:relative;overflow:hidden;
  box-shadow:0 30px 60px -40px rgba(0,50,34,.5)}
.card::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;
  background:linear-gradient(90deg,var(--green),var(--gold) 70%,transparent)}
.top{display:flex;align-items:center;gap:14px;margin-bottom:22px}
.emblem{width:52px;height:52px;border-radius:50%;flex:0 0 auto;background:#fff center/90% no-repeat;
  box-shadow:0 3px 10px -4px rgba(0,60,40,.45),inset 0 0 0 1px #bcd3c7}
.top .ar{font-family:'Tajawal',sans-serif;font-weight:700;font-size:14px;color:var(--green);
  direction:rtl;line-height:1.3}
.top .ar small{display:block;font-weight:500;color:var(--muted);font-size:11px}
h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:30px;letter-spacing:-1px;
  margin:0 0 2px}h1 .amp{color:var(--gold)}
.sub{color:var(--muted);font-size:12.5px;margin:0 0 20px}
label{display:block;font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:1.5px;
  text-transform:uppercase;color:var(--muted);margin:0 0 6px}
input{width:100%;padding:11px 13px;border:1px solid var(--hair);border-radius:11px;
  background:#fff;font-size:14px;font-family:inherit;color:var(--ink);margin-bottom:14px;
  transition:border-color .15s,box-shadow .15s}
input:focus{outline:none;border-color:var(--green);box-shadow:0 0 0 3px rgba(0,96,64,.12)}
button{width:100%;padding:12px;border:0;border-radius:11px;background:var(--green);color:#fff;
  font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:14px;letter-spacing:.3px;
  cursor:pointer;transition:background .15s,transform .1s}
button:hover{background:var(--green-2)}button:active{transform:translateY(1px)}
.hint{margin-top:16px;padding:9px 12px;border:1px dashed var(--hair);border-radius:10px;
  font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);text-align:center}
.hint b{color:var(--ink)}
.err{background:#fdeceb;border:1px solid #e7b9b4;color:#a5352b;font-size:12.5px;
  border-radius:10px;padding:9px 12px;margin-bottom:14px}
</style></head>
<body>
<form class="card" method="post" action="/login">
  <div class="top">
    <div class="emblem" style="background-image:url('__LOGO__')"></div>
    <div class="ar">أمانة منطقة الرياض<small>البحث والتطوير · سلامة الغذاء</small></div>
  </div>
  <h1>R<span class="amp">&amp;</span>D</h1>
  <div class="sub">Sign in to open the food-safety lab analytics.</div>
  __ERROR__
  <label for="u">Username</label>
  <input id="u" name="u" autocomplete="username" autofocus required>
  <label for="p">Password</label>
  <input id="p" name="p" type="password" autocomplete="current-password" required>
  <button type="submit">Sign in</button>
  <div class="hint">Demo access — username <b>demo</b> · password <b>demo</b></div>
</form>
</body></html>"""


def main():
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"R&D hub serving on 0.0.0.0:{port}  (sign-in: {USER} / ****)")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
