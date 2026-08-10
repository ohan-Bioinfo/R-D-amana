# Microbiology Dashboard Tabbed Touch-First Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `microbiology_dashboard.html` into a 5-tab, touch-first instrument — every chart zoom/pinch/pan + click-to-drill, panels grouped into tabs, redundant charts consolidated, and a sortable GSO-info tab.

**Architecture:** All changes are in the inline HTML/CSS/JS `TEMPLATE` of `microbiology/scripts/build_dashboard_combined.py`; the dashboard is regenerated from it. The masthead, filter bar, and KPI strip stay pinned; the existing `.grid` of `.card` panels is wrapped in five `<section class="tabpanel">` blocks with a tab `<nav>`; charts are created once and `Plotly.Plots.resize()`d when their tab is shown.

**Tech Stack:** Python 3.12 generator, vanilla JS + vendored Plotly (inline), CSS. Verification is build + `node --check` on the emitted app `<script>` + headless-chrome screenshots (no pytest — this is a generated HTML artifact).

**Design spec:** `docs/superpowers/specs/2026-08-10-micro-dashboard-tabbed-redesign-design.md`

## Global Constraints

- Microbiology only. Build/verify from `microbiology/` with `PY=.venv/bin/python`.
- Build command: `.venv/bin/python scripts/build_dashboard_combined.py` — must print `20881 rows, 2024=9317 2025=11564`. If the row total changes, STOP.
- After every rebuild, extract the largest `<script>` and run `node --check` — must pass.
  ```bash
  .venv/bin/python - <<'PY'
  import re; html=open("reports/microbiology_dashboard.html",encoding="utf-8").read()
  open("/tmp/dash.js","w").write(max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len))
  PY
  node --check /tmp/dash.js && echo "DASH JS OK"
  ```
- Screenshot a tab (verification):
  ```bash
  google-chrome-stable --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --window-size=1360,1000 --virtual-time-budget=8000 \
    --screenshot=/tmp/shot.png "file://$PWD/reports/microbiology_dashboard.html#<hash>"
  ```
- Preserve: all filters, Views/bookmarks, URL-hash filter state, reconciled totals, self-contained offline HTML, Riyadh masthead.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Verify 0 chemistry files staged before each commit.

---

### Task 1: Enable zoom / pinch / touch on every chart

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — `PLOTLY_CONFIG` (line ~1164) and `reactChart` (line ~1661).

**Interfaces:**
- Produces: a shared `PLOTLY_CONFIG` with zoom/touch enabled, applied by `reactChart` whenever a caller passes no explicit config.

- [ ] **Step 1: Update `PLOTLY_CONFIG`**

Replace line 1164:
```javascript
const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };
```
with:
```javascript
const PLOTLY_CONFIG = { responsive: true, scrollZoom: true, displayModeBar: 'hover',
  displaylogo: false, doubleClick: 'reset',
  modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'toggleSpikelines'] };
```

- [ ] **Step 2: Make `reactChart` default to `PLOTLY_CONFIG`**

In `reactChart`, change the final call:
```javascript
  Plotly.react(id, traces, layout, config);
```
to:
```javascript
  Plotly.react(id, traces, layout, config || PLOTLY_CONFIG);
```

- [ ] **Step 3: Rebuild + verify config present + node --check**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
grep -c "scrollZoom: true" reports/microbiology_dashboard.html   # expect >= 1
```
Then run the Global-Constraints node --check snippet. Expected `DASH JS OK` and row line `20881`.

- [ ] **Step 4: Screenshot a chart to confirm modebar-on-hover renders**

Run the screenshot snippet with empty hash; open `/tmp/shot.png` — charts render, no errors. (Modebar shows on hover; not visible in a static shot, but the chart must not be broken.)

- [ ] **Step 5: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: enable zoom/pinch/touch on all charts (shared Plotly config)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Tab shell — nav, panel grouping, switch + resize-on-show, divider styling

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — insert tab `<nav>` before `<div class="grid">` (line ~1010); wrap the existing `.card`/`.group-head` blocks into five `<section class="tabpanel">`; add tab CSS in the `<style>` block (near `:root`, ~line 652); add tab-switch + resize JS near `renderAll` (~line 3019).

**Interfaces:**
- Produces: `showTab(name)` JS — sets `.active` on the nav button and unhides the matching `<section class="tabpanel" data-tab="name">`, hides the others, and calls `Plotly.Plots.resize()` on every `.js-plotly-plot` inside the shown panel. Global `window.__activeTab` holds the current tab name. Consumed by Task 3 (hash).

- [ ] **Step 1: Add tab CSS**

In the `<style>` block, after the `:root{…}` rule (~line 668), add:
```css
/* ── lab-record divider tabs ─────────────────────────────── */
.tabnav { display:flex; gap:2px; align-items:flex-end; margin:14px 0 0;
  border-bottom:2px solid var(--gold-700); flex-wrap:wrap; position:sticky; top:0; z-index:20;
  background:var(--bg); padding-top:6px; }
.tabnav button { appearance:none; border:1px solid var(--line); border-bottom:none;
  background:var(--bg-3); color:var(--muted); font:600 12.5px/1 'Space Grotesk',system-ui,sans-serif;
  letter-spacing:.3px; padding:10px 16px 9px; border-radius:9px 9px 0 0; cursor:pointer;
  display:flex; align-items:center; gap:7px; transition:.15s; margin-bottom:-2px; }
.tabnav button .ar { font-family:'Tajawal',sans-serif; font-weight:500; font-size:11px; color:var(--muted); }
.tabnav button:hover { background:var(--bg-2); color:var(--fg); }
.tabnav button.active { background:var(--bg-2); color:var(--green-700); border-color:var(--gold-700);
  border-bottom:2px solid var(--bg-2); }
.tabnav button.active::before { content:"۞"; color:var(--gold-700); font-size:13px; }
.tabpanel[hidden] { display:none; }
.tabpanel { animation:tabfade .2s ease both; }
@keyframes tabfade { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
@media (prefers-reduced-motion:reduce){ .tabpanel{animation:none} }
```

- [ ] **Step 2: Insert the tab nav + open the first panel**

Immediately before `<div class="grid">` (line 1010) insert:
```html
<nav class="tabnav" id="tabnav">
  <button data-tab="overview" class="active">📊 Overview <span class="ar">نظرة عامة</span></button>
  <button data-tab="location">📍 Location <span class="ar">المواقع</span></button>
  <button data-tab="products">🍱 Products <span class="ar">المنتجات</span></button>
  <button data-tab="organisms">🦠 Organisms &amp; tests <span class="ar">الكائنات</span></button>
  <button data-tab="gso">📋 GSO &amp; Quality <span class="ar">الجودة</span></button>
</nav>
<div class="grid">
<section class="tabpanel" data-tab="overview">
```

- [ ] **Step 3: Wrap each card group into its tab panel**

The current `.grid` holds these cards in order (by chart id / content). **Move the existing card blocks verbatim** so each ends up inside the right `<section>`; insert `</section><section class="tabpanel" data-tab="…" hidden>` between groups. Target grouping:

| tab | cards to place (by chart id / content) |
|---|---|
| `overview` | `chart_map` card · `chart_trend` card · "Top 10 failed tests (microbes)" card |
| `location` | `chart_sector` card · `chart_heatmap` card · repeat-offenders (`repeat_table`) card |
| `products` | `chart_gso_cat` card · `chart_sample_type` card · "Top 10 most-contaminated subtypes" card · `chart_chains` card |
| `organisms` | "Non-compliant tests · pathogens vs indicators" card (`chart_tests_pathogen`/`chart_tests_indicator`) · `chart_severity_month` card |
| `gso` | "GSO 1016 audit" group-head + card · "Data-quality summary" card · official-test-table card · `chart_yoy` card · `chart_dow` card |

Drop the now-redundant interior `.group-head` dividers ("Where/When/Who") — the tabs replace them. After the last card (repeat_table area / end of grid), the structure closes with `</section></div>` (close the final panel, then the grid). Verify every `data-tab` section is opened and closed exactly once and only the first lacks `hidden`.

- [ ] **Step 4: Add the tab-switch + resize JS**

Just above `function renderAll(rows) {` (line ~3019) add:
```javascript
function showTab(name) {
  window.__activeTab = name;
  document.querySelectorAll('#tabnav button').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tabpanel').forEach(p => {
    const on = p.dataset.tab === name;
    p.hidden = !on;
    if (on) p.querySelectorAll('.js-plotly-plot').forEach(g => { try { Plotly.Plots.resize(g); } catch (e) {} });
  });
}
document.getElementById('tabnav').addEventListener('click', e => {
  const b = e.target.closest('button[data-tab]'); if (b) showTab(b.dataset.tab);
});
```

- [ ] **Step 5: Rebuild, node --check, screenshot all 5 tabs**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1   # expect 20881
```
Run the node --check snippet (expect `DASH JS OK`). Then screenshot the default (Overview) and — since tabs switch via JS click — verify no empty Plotly boxes by opening the file in headless chrome and screenshotting; the Overview charts (map/trend/microbes) must render. Manually confirm (or via a small JS-injection screenshot) that clicking a tab shows its panel with sized charts. If a switched-to chart is blank, the resize-on-show (Step 4) is the fix — recheck it fires.

- [ ] **Step 6: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: 5-tab shell (lab-record dividers) + resize-on-show

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Active tab in the URL hash

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — `serializeState` (line ~1263) and `deserializeState` (line ~1324).

**Interfaces:**
- Consumes: `window.__activeTab` (Task 2), `showTab` (Task 2).
- Produces: hash carries `tab=<name>`; on load the saved tab opens (default `overview`).

- [ ] **Step 1: Write the tab into the hash**

In `serializeState`, immediately before `return p.join('&');` add:
```javascript
  if (window.__activeTab && window.__activeTab !== 'overview') p.push('tab=' + window.__activeTab);
```

- [ ] **Step 2: Restore the tab on load**

In `deserializeState(hash)`, after the `URLSearchParams` is parsed and before the final chip sync/return, add (use the same `params` object the function already builds):
```javascript
  const _tab = params.get('tab');
  if (_tab && document.querySelector('.tabpanel[data-tab="' + _tab + '"]')) showTab(_tab);
```
(If `deserializeState` runs before the DOM/tabs exist, place this call at the very end of the function; `showTab` is defined globally by Task 2.)

- [ ] **Step 3: Rebuild + verify deep-link opens the tab**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
```
node --check (expect OK). Screenshot with `#tab=products` in the hash; the Products tab must be the visible one.

- [ ] **Step 4: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: persist active tab in URL hash (tab=)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Universal click-to-drill

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — add `plotly_click` → `crossFilter` handlers to the charts that lack them, following the existing pattern (e.g. lines 2062, 2331, 2701, 2772).

**Interfaces:**
- Consumes: `crossFilter(parentId, stateKey, value)` (line ~1248), the existing `f_sector`/`f_gso_category`/`f_microbe`/`f_severity` chip containers.

- [ ] **Step 1: Wire the missing charts**

For each chart below, after its `reactChart(<id>, …)` call in its render function, add a handler that mirrors the established pattern (`node.removeAllListeners && node.removeAllListeners('plotly_click'); node.on('plotly_click', e => crossFilter(<chip>, <stateKey>, <value>))`):

```javascript
// Sample-type distribution (grouped bar, x = sample_type)  — in renderSampleTypeDistribution
const _stN = document.getElementById('chart_sample_type');
_stN.removeAllListeners && _stN.removeAllListeners('plotly_click');
_stN.on('plotly_click', e => crossFilter('f_sample_type', 'sample_type', e.points[0].x));
```
```javascript
// Top facilities/chains (horizontal bar, y = facility)  — in renderChains
const _chN = document.getElementById('chart_chains');
_chN.removeAllListeners && _chN.removeAllListeners('plotly_click');
_chN.on('plotly_click', e => crossFilter('f_facility', 'facility', e.points[0].y));
```
```javascript
// Heatmap (severity × category): tap a cell → filter its GSO category  — in renderHeatmap
const _hmN = document.getElementById('chart_heatmap');
_hmN.removeAllListeners && _hmN.removeAllListeners('plotly_click');
_hmN.on('plotly_click', e => crossFilter('f_gso_category', 'gso_category', e.points[0].x));
```

Note: only wire a chart to a `stateKey`/chip that already exists. If `sample_type` or `facility` has **no** filter chip/state, SKIP that chart's handler and record it in the report as "no matching filter dimension — left non-interactive" rather than inventing a filter. Confirm which chip ids exist first:
```bash
grep -nE "id=\"f_(sample_type|facility|sector|gso_category|microbe|severity)\"" scripts/build_dashboard_combined.py
```

- [ ] **Step 2: Rebuild + verify handlers present + node --check**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
grep -c "on('plotly_click'" reports/microbiology_dashboard.html   # expect > previous count
```
node --check → OK. Screenshot Products/Location tabs render.

- [ ] **Step 3: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: extend click-to-drill to sample-type/chains/heatmap charts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Sortable GSO-info table (in the GSO & Quality tab)

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — add a `<div id="gso_info_table"></div>` card in the `gso` tab panel; add `renderGsoInfoTable()` + a `sortTable` helper; call it from `renderAll`.

**Interfaces:**
- Consumes: the per-row payload (has `gso_category`/`gso_code_canonical`, compliance) already used elsewhere; the `COLS` index map.
- Produces: `renderGsoInfoTable()` — builds a sortable HTML table from the current filtered rows.

- [ ] **Step 1: Add the card container**

Inside the `gso` tabpanel (Task 2), after the GSO-audit card, add:
```html
  <div class="card full">
    <h2>GSO 1016 categories — sortable table</h2>
    <div class="card-sub">Click a column header to sort. Represents the numbers; makes no scope judgment.</div>
    <div id="gso_info_table" style="overflow-x:auto"></div>
  </div>
```

- [ ] **Step 2: Add the render + sort JS**

Near the other render functions, add:
```javascript
function renderGsoInfoTable(rows) {
  const agg = {};  // category -> {code, n, nc}
  rows.forEach(r => {
    const cat = r[COLS.gso_category] || '—';
    const a = agg[cat] || (agg[cat] = { code: r[COLS.gso_code_canonical] || '', n: 0, nc: 0 });
    a.n++; if (r[COLS.failure] === true) a.nc++;
  });
  const data = Object.entries(agg).map(([cat, a]) =>
    ({ cat, code: a.code, n: a.n, nc: a.nc, rate: a.n ? 100 * a.nc / a.n : 0 }))
    .sort((x, y) => y.n - x.n);
  const cols = [['cat','Category'],['code','Code'],['n','Samples'],['nc','Non-compliant'],['rate','NC %']];
  const th = cols.map(([k, l]) => `<th data-k="${k}" style="cursor:pointer">${l} <span class="sort-ar"></span></th>`).join('');
  const body = data.map(d =>
    `<tr><td>${d.cat}</td><td>${d.code}</td><td>${d.n.toLocaleString()}</td>` +
    `<td>${d.nc.toLocaleString()}</td><td>${d.rate.toFixed(1)}%</td></tr>`).join('');
  const el = document.getElementById('gso_info_table');
  el.innerHTML = `<table class="gso-table"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>`;
  el.__data = data; el.__cols = cols; el.__dir = {};
  el.querySelectorAll('th').forEach(h => h.addEventListener('click', () => sortGsoTable(h.dataset.k)));
}
function sortGsoTable(k) {
  const el = document.getElementById('gso_info_table');
  const dir = el.__dir[k] = -(el.__dir[k] || 1);
  const num = k !== 'cat' && k !== 'code';
  const sorted = [...el.__data].sort((a, b) => num ? dir * (a[k] - b[k]) : dir * String(a[k]).localeCompare(String(b[k])));
  el.__data = sorted;
  const body = sorted.map(d =>
    `<tr><td>${d.cat}</td><td>${d.code}</td><td>${d.n.toLocaleString()}</td>` +
    `<td>${d.nc.toLocaleString()}</td><td>${d.rate.toFixed(1)}%</td></tr>`).join('');
  el.querySelector('tbody').innerHTML = body;
  el.querySelectorAll('th').forEach(h => h.querySelector('.sort-ar').textContent =
    h.dataset.k === k ? (dir < 0 ? '▾' : '▴') : '');
}
```
Add matching CSS near the tab CSS:
```css
.gso-table { width:100%; border-collapse:collapse; font-size:12.5px; }
.gso-table th, .gso-table td { text-align:left; padding:7px 12px; border-bottom:1px solid var(--line); }
.gso-table th { position:sticky; top:0; background:var(--bg-3); font:600 11px 'Space Grotesk',sans-serif;
  text-transform:uppercase; letter-spacing:.5px; color:var(--muted); }
.gso-table td:nth-child(n+3) { font-family:'IBM Plex Mono',monospace; }
```

- [ ] **Step 3: Call it from `renderAll`**

Confirm the `COLS` keys exist first: `grep -nE "gso_category|gso_code_canonical|failure" scripts/build_dashboard_combined.py | grep COLS` (or read the `COLS` definition). Then in `renderAll(rows)`, add `renderGsoInfoTable(rows);` alongside the other render calls. If the exact `COLS` key names differ (e.g. no `gso_code_canonical` in the payload), use the ones that exist and note it.

- [ ] **Step 4: Rebuild + verify + node --check**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
grep -c "gso-table" reports/microbiology_dashboard.html   # expect >= 1
```
node --check → OK. Screenshot `#tab=gso` — the sortable table renders with rows.

- [ ] **Step 5: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: sortable GSO 1016 categories table (GSO tab)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Chart consolidation + one data palette (polish)

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — merge the two failed-tests charts into one with a pathogen/indicator toggle; retint chart traces to the 3-stop data palette.

**Interfaces:**
- Consumes: `renderTests` (the pathogen/indicator renderers), the `:root` palette vars.

- [ ] **Step 1: Add data-palette tokens**

In `:root` (after line 667) add:
```css
  --data-compliant:#2f9e6b; --data-indicator:#e0a53a; --data-pathogen:#c0392b; --data-neutral:#64748b;
```

- [ ] **Step 2: Merge the two failed-tests bars into one toggle chart**

Replace the two side-by-side chart divs (`chart_tests_pathogen` + `chart_tests_indicator`, ~lines 1046-1053) with a single container + a segmented toggle:
```html
    <div class="seg-toggle" id="tests_toggle">
      <button data-t="pathogen" class="active">Pathogens</button>
      <button data-t="indicator">Indicators</button>
    </div>
    <div id="chart_tests" class="chart" style="min-height:420px"></div>
```
In `renderTests`, render into `chart_tests` based on the active toggle (default pathogen); wire the toggle buttons to re-render. Colour pathogen bars `--data-pathogen`, indicator bars `--data-indicator`. Add `.seg-toggle` CSS (reuse `.toggle`/chip styling already in the file). Keep the existing click-to-drill (`crossFilter('f_microbe', …)`) on the merged chart.

- [ ] **Step 3: Retint the main breakdown charts**

In `_renderVolumeVsRate` and the sector/category renderers, set the non-compliance line/marker colour to `--data-pathogen` equivalent `#c0392b` (already orange `#ea580c` — change to `#c0392b`), and keep year bars on the existing year colours. Do not restyle every chart exhaustively — just make the NC signal consistently red across breakdowns.

- [ ] **Step 4: Rebuild + verify + node --check + screenshots**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
```
node --check → OK. Screenshot `#tab=organisms` — the merged tests chart renders; toggling is JS (confirm both buttons present via `grep -c "tests_toggle"`).

- [ ] **Step 5: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: merge failed-tests into one toggle chart + consistent NC palette

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Finalize — CHANGELOG, full verification, push

**Files:**
- Modify: `microbiology/CHANGELOG.md`.

- [ ] **Step 1: Full reconciliation + all-tabs screenshot sweep**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1   # 20881 · 2024=9317 2025=11564
```
Run node --check (OK). Screenshot each tab hash (`#tab=overview`, `location`, `products`, `organisms`, `gso`) — every panel renders, no empty Plotly boxes, filter bar + KPIs pinned above all tabs.

- [ ] **Step 2: CHANGELOG entry**

Prepend a `## 2026-08-10 — Dashboard tabbed touch-first redesign` entry summarising: 5 tabs (lab-record dividers), zoom/pinch/touch on all charts, universal click-to-drill, merged failed-tests toggle, sortable GSO table, tab persisted in URL hash; totals unchanged (20,881); node --check clean.

- [ ] **Step 3: Commit + push**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/CHANGELOG.md microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard tabbed redesign: changelog + final rebuild

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## Self-Review

**Spec coverage:**
- 5-tab layout + pinned controls → Task 2 ✓
- Zoom/touch/pan on all charts → Task 1 ✓
- Universal click-to-drill → Task 4 (+ existing) ✓
- Active tab in URL hash → Task 3 ✓
- Fewer/cleaner charts (merge tests, palette) → Task 6 ✓
- Sortable GSO table → Task 5 ✓
- Lab-record-divider signature + identity → Task 2 (CSS) ✓
- Preserve filters/bookmarks/totals/offline → Global Constraints + verify steps ✓

**Placeholder scan:** discrete pieces (config, tab nav/CSS, switch JS, hash, sortable table) carry literal code; the structural regrouping (Task 2 Step 3) is a precise card→tab mapping by chart-id with verbatim-move instructions (reproducing all ~13 card blocks literally is impractical and error-prone — the mapping table + insertion markers are the exact spec). Task 4/5 include grep gates to confirm chip/`COLS` names before wiring, with an explicit "skip + report, don't invent" rule. No TBD/TODO.

**Type consistency:** `showTab(name)` / `window.__activeTab` used consistently across Tasks 2–3. `crossFilter(parentId, stateKey, value)` used per the existing signature in Task 4. `renderGsoInfoTable(rows)` + `sortGsoTable(k)` consistent in Task 5. `PLOTLY_CONFIG` defined in Task 1, defaulted by `reactChart`.

**Note on verification:** this is a generated HTML dashboard — the test cycle is build + `node --check` + headless screenshot + row reconciliation, not pytest. Interactive behaviours (tab click, chart click-drill, table sort, pinch-zoom) are asserted via presence-of-handler greps + screenshots; a reviewer opening the file confirms the live interactions.
