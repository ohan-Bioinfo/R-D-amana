# Chemistry Dashboard — Standardize to Micro Tabbed Touch-First Design — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the microbiology dashboard's 5-tab, touch-first design onto the chemistry dashboard: zoom/pinch/touch on every chart, lab-record-divider tabs, click-to-drill, active-tab-in-hash, and a sortable GSO tab.

**Architecture:** All changes are in the inline HTML/CSS/JS `TEMPLATE` of `chemistry/scripts/build_dashboard.py`; the dashboard is regenerated from it. Masthead + Section bar + filter chips + KPI strips stay pinned; the existing `.grid` of cards is wrapped in five `<section class="tabpanel">` blocks with a tab `<nav>`; charts are created once (via the existing `renderAll`→`Plotly.newPlot`) and `Plotly.Plots.resize()`d when their tab is shown.

**Tech Stack:** Python 3.12 generator (runs on `../microbiology/.venv/bin/python`), vanilla JS + vendored Plotly (inline), CSS. Verification is build + `node --check` on the emitted app `<script>` + headless-chrome screenshots (no pytest — generated HTML artifact).

**Design spec:** `docs/superpowers/specs/2026-08-11-chem-dashboard-standardize-design.md`

## Global Constraints

- Chemistry only. Build/verify from `chemistry/` with `PY=../microbiology/.venv/bin/python`.
- Build command: `$PY scripts/build_dashboard.py` — must print `15876 rows across 8 sections`. If the row total changes, STOP.
- After every rebuild, extract the largest `<script>` and run `node --check`:
  ```bash
  ../microbiology/.venv/bin/python - <<'PY'
  import re; html=open("reports/chemistry_dashboard.html",encoding="utf-8").read()
  open("/tmp/chem.js","w").write(max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len))
  PY
  node --check /tmp/chem.js && echo "CHEM JS OK"
  ```
- Screenshot a tab:
  ```bash
  google-chrome-stable --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --window-size=1360,2600 --virtual-time-budget=9000 \
    --screenshot=/tmp/shot.png "file://$PWD/reports/chemistry_dashboard.html#<hash>"
  ```
- Preserve: all filters (Section/year/compliance/sector/GSO chips), search, Reset, the YoY table, drilldown, reconciled totals, self-contained offline HTML, Riyadh masthead.
- Data facts (verified): NC per row = `COLS.is_valid === 0` (1=compliant, 0=non-compliant, null=without-spec); sector = `COLS.municipality`; category = `COLS.gso_category`; year = `COLS.year`. Filter state: `activeSectors` (Set of municipality names), `activeGso` (Set of category names), `currentSection`, `currentYear`; chip clicks mutate these and call `renderAll()`.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Verify 0 microbiology files staged before each commit (`git diff --cached --name-only | grep -c microbiology` must be 0).

---

### Task 1: Shared zoom / touch config on every chart

**Files:** Modify `chemistry/scripts/build_dashboard.py` — add a `PLOTLY_CONFIG` const in the app `<script>` (near the top of the IIFE, before the render functions) and replace every inline `Plotly.newPlot` config with it.

**Interfaces:** Produces a module-scope `PLOTLY_CONFIG` used by all `newPlot` calls.

- [ ] **Step 1: Add the config const.** In the app `<script>`, near the top of the main IIFE (e.g. just after `const COLS = {};` at ~line 696, or wherever module consts live), add:
```javascript
const PLOTLY_CONFIG = { responsive: true, scrollZoom: true, displayModeBar: 'hover',
  displaylogo: false, doubleClick: 'reset',
  modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'toggleSpikelines'] };
```

- [ ] **Step 2: Replace all inline configs.** There are 6 `Plotly.newPlot(...)` call sites whose 4th argument is `{responsive:true, displayModeBar:false}` (2 spaced, 4 compact variants — chart-monthly, chart-validity, chart-fail, chart-gso, chart-map, and one more). Replace each 4th-argument config object with `PLOTLY_CONFIG`. Find them:
```bash
grep -nE "Plotly\.newPlot" scripts/build_dashboard.py
```
For each, change the trailing `, {responsive:true, displayModeBar:false})` (or the spaced variant) to `, PLOTLY_CONFIG)`. Do NOT change the map's `layout` — only the config (4th) argument. If any `newPlot` intentionally needs the modebar hidden, leave a note; otherwise all use `PLOTLY_CONFIG`.

- [ ] **Step 3: Rebuild + verify.**
```bash
cd /home/lab/storage/Data-Analysis-Muhannad/chemistry
../microbiology/.venv/bin/python scripts/build_dashboard.py 2>&1 | tail -1   # expect 15876 rows across 8 sections
grep -c "scrollZoom: true" reports/chemistry_dashboard.html    # >= 1
grep -c "displayModeBar:false\|displayModeBar: false" reports/chemistry_dashboard.html   # expect 0 (all replaced)
```
Run the node --check snippet (expect `CHEM JS OK`). Screenshot the default view — charts still render.

- [ ] **Step 4: Commit** (chemistry files only):
```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add chemistry/scripts/build_dashboard.py chemistry/reports/chemistry_dashboard.html
[ "$(git diff --cached --name-only | grep -c microbiology)" = 0 ] && \
git commit -m "Chem dashboard: shared zoom/pinch/touch Plotly config on all charts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Tab shell — nav, panel grouping, switch + resize-on-show, divider CSS

**Files:** Modify `chemistry/scripts/build_dashboard.py` — insert tab `<nav>` before `<div class="grid">` (~line 669); relocate `card-yoy` (currently a standalone card at ~line 664, above the grid, `display:none`) into the Sections & tests panel; wrap the grid cards into five `<section class="tabpanel">`; add tab CSS near `:root` (~line 368); add `showTab` + resize + nav-click JS; call `showTab(initial)` after the load-time `renderAll()`.

**Interfaces:** Produces `showTab(name)` (sets `.active` nav button, unhides matching `<section data-tab>`, `Plotly.Plots.resize()`s every `.js-plotly-plot` in it) and `window.__activeTab`. Consumed by Task 3.

- [ ] **Step 1: Add tab CSS** near the `:root{}` block (chemistry already defines `--green-700`, `--gold-700`, `--sand-*`, `--ink-*`):
```css
.tabnav { display:flex; gap:2px; align-items:flex-end; margin:14px 0 0;
  border-bottom:2px solid var(--gold-700); flex-wrap:wrap; }
.tabnav button { appearance:none; border:1px solid var(--sand-200); border-bottom:none;
  background:var(--sand-100); color:var(--ink-500); font:600 12.5px/1 system-ui,sans-serif;
  letter-spacing:.3px; padding:10px 16px 9px; border-radius:9px 9px 0 0; cursor:pointer;
  display:flex; align-items:center; gap:7px; transition:.15s; margin-bottom:-2px; }
.tabnav button .ar { font-family:'Tajawal',sans-serif; font-weight:500; font-size:11px; color:var(--ink-500); }
.tabnav button:hover { background:var(--sand-50); color:var(--ink-900); }
.tabnav button.active { background:var(--bg-2); color:var(--green-700); border-color:var(--gold-700);
  border-bottom:2px solid var(--bg-2); }
.tabnav button.active::before { content:"۞"; color:var(--gold-700); font-size:13px; }
.tabpanel[hidden] { display:none; }
.tabpanel { animation:tabfade .2s ease both; }
@keyframes tabfade { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
@media (prefers-reduced-motion:reduce){ .tabpanel{animation:none} }
```
(If `--bg-2` is not defined, use `#fffdf8` — it appears in the chemistry `:root`.)

- [ ] **Step 2: Insert the tab nav + open the first panel.** Immediately before `<div class="grid">` (~line 669) insert:
```html
<nav class="tabnav" id="tabnav">
  <button data-tab="overview" class="active">📊 Overview <span class="ar">نظرة عامة</span></button>
  <button data-tab="location">📍 Location <span class="ar">المواقع</span></button>
  <button data-tab="products">🧪 Products <span class="ar">المنتجات</span></button>
  <button data-tab="sections">⚗️ Sections &amp; tests <span class="ar">الأقسام</span></button>
  <button data-tab="gso">📋 GSO &amp; Quality <span class="ar">الجودة</span></button>
</nav>
<div class="grid">
<section class="tabpanel" data-tab="overview">
```

- [ ] **Step 3: Group the cards into panels.** Move the existing card blocks verbatim so each lands in the right `<section>`; insert `</section><section class="tabpanel" data-tab="…" hidden>` between groups. Also MOVE the `card-yoy` block (currently above the grid at ~line 664) into the `sections` panel. Keep `card-yoy`'s existing `display:none`/show logic untouched (it toggles visibility based on year). Target grouping (by chart/table id):

| tab | cards |
|---|---|
| `overview` | `chart-map` card · `chart-monthly` card · `chart-validity` card |
| `location` | `chart-municipalities` card · `tbl-facilities` card |
| `products` | `chart-gso` card · `chart-top-subtypes` card · `tbl-categories` card |
| `sections` | `chart-fail` card · `card-yoy` (moved here) |
| `gso` | (Task 5 adds the sortable GSO table card here) · any data-quality/notes card |

Every `data-tab` section opened and closed exactly once; only `overview` lacks `hidden`. Verify the `<div class="grid">` still closes after the last section (`</section></div>`). If a card doesn't obviously belong (e.g. a notes/footer card), put it in `gso`.

- [ ] **Step 4: Add the switch JS.** Just above `function renderAll()` (~line 1767) add:
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

- [ ] **Step 5: Resize the active tab after the initial paint.** Find the load-time `renderAll();` call (~line 1858). Immediately AFTER it, add `showTab(window.__activeTab || 'overview');` so the visible panel's charts get sized once created. (Task 3 will set `window.__activeTab` from the hash before this runs.)

- [ ] **Step 6: Rebuild, node --check, screenshot all 5 tabs.**
```bash
cd /home/lab/storage/Data-Analysis-Muhannad/chemistry
../microbiology/.venv/bin/python scripts/build_dashboard.py 2>&1 | tail -1   # 15876
grep -c 'class="tabpanel"' reports/chemistry_dashboard.html   # exactly 5
grep -c 'data-tab=' reports/chemistry_dashboard.html          # 10 (5 nav + 5 sections)
```
node --check (expect `CHEM JS OK`). Screenshot the default and each of `#tab=location`, `#tab=products`, `#tab=sections`, `#tab=gso` (tall window, e.g. 1360x2600). Every panel renders its charts with NO empty Plotly boxes (empty box → resize-on-show not firing; recheck Steps 4–5). Section bar + chips + KPIs pinned above the tabs.

- [ ] **Step 7: Commit** (chemistry files only, same guard + message pattern):
```
Chem dashboard: 5-tab shell (lab-record dividers) + resize-on-show
```

---

### Task 3: Active tab in a minimal `#tab=` hash

**Files:** Modify `chemistry/scripts/build_dashboard.py` — write the tab to `location.hash` on click; read it on load.

**Interfaces:** Consumes `showTab`/`window.__activeTab` (Task 2). Chemistry has no other hash state, so this is a standalone tab-only hash.

- [ ] **Step 1: Write the hash on tab click.** Extend the `#tabnav` click listener (Task 2 Step 4) so that after `showTab(b.dataset.tab)` it records the tab:
```javascript
document.getElementById('tabnav').addEventListener('click', e => {
  const b = e.target.closest('button[data-tab]');
  if (b) {
    showTab(b.dataset.tab);
    history.replaceState(null, '', b.dataset.tab === 'overview'
      ? location.pathname + location.search
      : '#tab=' + b.dataset.tab);
  }
});
```

- [ ] **Step 2: Read the hash on load.** BEFORE the load-time `showTab(...)` call added in Task 2 Step 5, parse the hash and seed `window.__activeTab`:
```javascript
const _m = (location.hash || '').match(/tab=([a-z]+)/);
if (_m && document.querySelector('.tabpanel[data-tab="' + _m[1] + '"]')) window.__activeTab = _m[1];
```
So the existing `showTab(window.__activeTab || 'overview');` opens the deep-linked tab.

- [ ] **Step 3: Rebuild + verify.** Build (15876), node --check (`CHEM JS OK`). Screenshot with `#tab=products` — the Products tab must be the visible one. Load with no hash → Overview.

- [ ] **Step 4: Commit** — `Chem dashboard: persist active tab in URL hash (tab=)`

---

### Task 4: Click-to-drill on sector + GSO charts

**Files:** Modify `chemistry/scripts/build_dashboard.py` — add `plotly_click` handlers in `renderMunicipalities` (~line 1609) and `renderGsoCat` (~line 1328).

**Interfaces:** Consumes `activeSectors` / `activeGso` Sets and `renderAll()` (existing).

- [ ] **Step 1: Wire the sector chart.** In `renderMunicipalities`, after its `Plotly.newPlot('chart-municipalities', …)` call, add:
```javascript
const _muN = document.getElementById('chart-municipalities');
_muN.removeAllListeners && _muN.removeAllListeners('plotly_click');
_muN.on('plotly_click', e => {
  const s = e.points[0].x;            // sector name = municipality value
  if (activeSectors.has(s)) activeSectors.delete(s); else activeSectors.add(s);
  renderAll();
});
```
(Verify the x-axis category equals the `municipality` value, i.e. one of Central/East/North/South/West/None — it does, per `renderSectorChips`.)

- [ ] **Step 2: Wire the GSO-category chart.** In `renderGsoCat`, after its `Plotly.newPlot('chart-gso', …)` call, add:
```javascript
const _gcN = document.getElementById('chart-gso');
_gcN.removeAllListeners && _gcN.removeAllListeners('plotly_click');
_gcN.on('plotly_click', e => {
  const g = e.points[0].x;            // GSO category name
  if (!g) return;
  if (activeGso.has(g)) activeGso.delete(g); else activeGso.add(g);
  renderAll();
});
```
Confirm the `chart-gso` x-axis values are the full `gso_category` names that populate `activeGso` (per `renderGsoChips`). If the x uses a wrapped/abbreviated label, map it back to the full category (like micro's heatmap did); if you cannot confirm a clean mapping, wire only the sector chart and report the GSO chart as deferred (do NOT filter by a truncated label).

- [ ] **Step 3: Rebuild + verify.** Build (15876), node --check. `grep -c "on('plotly_click'" reports/chemistry_dashboard.html` — expect 2 more than before (report before/after). Screenshot `#tab=location` (sector chart) and `#tab=products` (GSO chart) — both render.

- [ ] **Step 4: Commit** — `Chem dashboard: click-to-drill on sector + GSO-category charts`

---

### Task 5: Sortable GSO-info table (GSO & Quality tab)

**Files:** Modify `chemistry/scripts/build_dashboard.py` — add a `<div id="gso_info_table">` card in the `gso` panel; add `renderGsoInfoTable()` + `sortGsoInfoTable()`; call from `renderAll`.

**Interfaces:** Consumes the filtered rows `renderAll` iterates, `COLS.gso_category`, `COLS.is_valid`.

- [ ] **Step 1: Add the card** in the `gso` tabpanel (Task 2):
```html
  <div class="card full">
    <h2>GSO 1016 categories — sortable table</h2>
    <div class="muted" style="font-size:11px">Click a column header to sort. Represents the numbers; makes no scope judgment.</div>
    <div id="gso_info_table" style="overflow-x:auto"></div>
  </div>
```

- [ ] **Step 2: Add the render + sort JS.** Add near the other render functions. NC = `is_valid === 0`; NC% is over *evaluated* samples (`is_valid !== null`) to match how chemistry reports compliance. First confirm the exact rows variable `renderAll` uses for its charts (the filtered set) and pass the SAME set in:
```javascript
function renderGsoInfoTable(rows) {
  const agg = {};  // category -> {n, nc, evald}
  rows.forEach(r => {
    const cat = r[COLS.gso_category] || '—';
    const a = agg[cat] || (agg[cat] = { n: 0, nc: 0, evald: 0 });
    a.n++;
    const v = r[COLS.is_valid];
    if (v === 0) { a.nc++; a.evald++; } else if (v === 1) { a.evald++; }
  });
  const data = Object.entries(agg).map(([cat, a]) =>
    ({ cat, n: a.n, nc: a.nc, rate: a.evald ? 100 * a.nc / a.evald : 0 }))
    .sort((x, y) => y.n - x.n);
  const cols = [['cat','Category'],['n','Samples'],['nc','Non-compliant'],['rate','NC %']];
  const th = cols.map(([k, l]) => `<th data-k="${k}" style="cursor:pointer">${l} <span class="sort-ar"></span></th>`).join('');
  const body = data.map(d =>
    `<tr><td>${d.cat}</td><td>${d.n.toLocaleString()}</td>` +
    `<td>${d.nc.toLocaleString()}</td><td>${d.rate.toFixed(1)}%</td></tr>`).join('');
  const el = document.getElementById('gso_info_table');
  if (!el) return;
  el.innerHTML = `<table class="gso-table"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>`;
  el.__data = data; el.__dir = {};
  el.querySelectorAll('th').forEach(h => h.addEventListener('click', () => sortGsoInfoTable(h.dataset.k)));
}
function sortGsoInfoTable(k) {
  const el = document.getElementById('gso_info_table');
  const dir = el.__dir[k] = -(el.__dir[k] || 1);
  const num = k !== 'cat';
  const sorted = [...el.__data].sort((a, b) => num ? dir * (a[k] - b[k]) : dir * String(a[k]).localeCompare(String(b[k])));
  el.__data = sorted;
  el.querySelector('tbody').innerHTML = sorted.map(d =>
    `<tr><td>${d.cat}</td><td>${d.n.toLocaleString()}</td>` +
    `<td>${d.nc.toLocaleString()}</td><td>${d.rate.toFixed(1)}%</td></tr>`).join('');
  el.querySelectorAll('th').forEach(h => h.querySelector('.sort-ar').textContent =
    h.dataset.k === k ? (dir < 0 ? '▾' : '▴') : '');
}
```
Add CSS near the tab CSS:
```css
.gso-table { width:100%; border-collapse:collapse; font-size:12.5px; }
.gso-table th, .gso-table td { text-align:left; padding:7px 12px; border-bottom:1px solid var(--sand-200); }
.gso-table th { position:sticky; top:0; background:var(--sand-100); font:600 11px system-ui,sans-serif;
  text-transform:uppercase; letter-spacing:.5px; color:var(--ink-500); }
.gso-table td:nth-child(n+2) { font-variant-numeric:tabular-nums; }
```

- [ ] **Step 3: Call it from `renderAll`.** Add `renderGsoInfoTable(<same filtered rows the other charts use>);` alongside the other render calls in `renderAll` (~line 1767). Identify the correct rows variable first (the one passed to `renderGsoCat`/`renderMunicipalities`).

- [ ] **Step 4: Rebuild + verify.** Build (15876), node --check. `grep -c "gso-table" reports/chemistry_dashboard.html` >= 1. Screenshot `#tab=gso` — the table renders WITH DATA: real category names, non-zero Non-compliant, non-zero NC %. Report the top row's values (if NC shows all zeros, the `is_valid===0` logic or the rows variable is wrong — recheck).

- [ ] **Step 5: Commit** — `Chem dashboard: sortable GSO 1016 categories table (GSO tab)`

---

### Task 6: Finalize — CHANGELOG, full verification, push

**Files:** Modify `chemistry/CHANGELOG.md`.

- [ ] **Step 1: Full reconciliation + all-tabs sweep.**
```bash
cd /home/lab/storage/Data-Analysis-Muhannad/chemistry
../microbiology/.venv/bin/python scripts/build_dashboard.py 2>&1 | tail -1   # 15876 rows across 8 sections
```
node --check (`CHEM JS OK`). Screenshot each tab hash (`#tab=overview/location/products/sections/gso`) — every panel renders, no empty Plotly boxes, Section bar + chips + KPIs pinned above all tabs.

- [ ] **Step 2: CHANGELOG entry.** Prepend `## 2026-08-11 — Dashboard standardized to the tabbed touch-first design` summarizing: 5 tabs (lab-record dividers, matching micro), zoom/pinch/touch on all charts, click-to-drill (sector + GSO), sortable GSO table, tab persisted in `#tab=`; totals unchanged (15,876 rows / 1,133,621 tests); node --check clean.

- [ ] **Step 3: Commit + push.**
```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add chemistry/CHANGELOG.md chemistry/reports/chemistry_dashboard.html
[ "$(git diff --cached --name-only | grep -c microbiology)" = 0 ] && \
git commit -m "Chem dashboard standardize: changelog + final rebuild

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## Self-Review

**Spec coverage:**
- 5-tab layout + pinned controls → Task 2 ✓
- Zoom/touch on all charts → Task 1 ✓
- Click-to-drill (sector + GSO) → Task 4 ✓
- Active tab in hash → Task 3 ✓
- Sortable GSO table → Task 5 ✓
- Lab-record-divider signature + shared identity → Task 2 (CSS reuses chemistry's existing green/gold/sand tokens) ✓
- Preserve filters/YoY/drilldown/totals/offline → Global Constraints + verify steps ✓

**Placeholder scan:** config, tab nav/CSS/switch, hash, drill snippets, and sortable table carry literal code. The card→tab regrouping (Task 2 Step 3) is a precise id→tab mapping with verbatim-move + insertion markers (reproducing ~10 card blocks literally is error-prone; the mapping table is the spec). Tasks 4/5 carry grep/confirm gates for the x-axis-label mapping and the `renderAll` rows variable, with explicit "wire only what's confirmed, don't invent/guess" fallbacks. No TBD/TODO.

**Type consistency:** `showTab(name)`/`window.__activeTab` consistent across Tasks 2–3; `activeSectors`/`activeGso`/`renderAll` used per the existing chemistry model in Task 4; `renderGsoInfoTable(rows)`/`sortGsoInfoTable(k)` consistent in Task 5; `PLOTLY_CONFIG` defined in Task 1 and used by Task 4's new charts implicitly (they reuse existing `newPlot` calls already converted).

**Note on verification:** generated HTML dashboard — test cycle is build + `node --check` + headless screenshot + row reconciliation (15,876), not pytest. Interactive behaviours (tab click, drill, sort, pinch-zoom) asserted via handler-presence greps + screenshots.
