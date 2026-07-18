# Micro Dashboard Interactivity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add click-to-cross-filter, shareable URL-hash views + bookmarks, and a one-command data refresh to the self-contained microbiology dashboard — no server, no framework.

**Architecture:** Features 1–3 are vanilla-JS additions to the inline `<script>` authored inside `TEMPLATE` in `microbiology/scripts/build_dashboard_combined.py`; they reuse the existing `state` object, `applyFilters()`, `buildChips()`, and `reactChart()`. Feature 4 is a new shell script that runs the existing pipeline end-to-end.

**Tech Stack:** Python 3.12 (dashboard generator), vanilla JS + vendored Plotly (inline), bash.

## Global Constraints

- Micro-only commits: `git diff --cached --name-only | grep -c chemistry` must be `0` before every commit.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- After every dashboard rebuild, extract the largest `<script>` and run `node --check` — must pass.
- The emitted HTML stays fully self-contained — no new external network requests.
- Build command: `microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py` (run from `microbiology/`).
- Reuse existing patterns: `state[stateKey]` Sets, `applyFilters()` as the single re-render entry point, `buildChips()` chip model (chips carry `dataset.value`, active shown via `.active` class), and the `node.removeAllListeners('plotly_click')` + `node.on('plotly_click', …)` pattern already used by the tests drill-down.

### Reference: the JS extract + check snippet (used in every task's verify step)

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology
.venv/bin/python - <<'PY'
import re
html=open("reports/microbiology_dashboard.html",encoding="utf-8").read()
big=max(re.findall(r"<script>(.*?)</script>", html, re.S),key=len)
open("/tmp/dash.js","w").write(big)
PY
node --check /tmp/dash.js && echo "JS OK"
```

---

### Task 1: Cross-filtering (click a chart → toggle the matching filter)

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — add `crossFilter()` helper near `buildChips()` (~line 1144); attach `plotly_click` handlers inside `renderGsoCategory`, `_renderVolumeVsRate` (sector), `renderTopMicrobes`, `renderSeverityMonth`, `renderMap`; add a hint line to the filter bar HTML.

**Interfaces:**
- Produces: `crossFilter(parentId, stateKey, value)` — toggles `value` in `state[stateKey]` (a Set), syncs the matching chip's `.active` class inside `#parentId`, then calls `applyFilters()`. Used by Task 3 bookmarks indirectly (same state Sets).

- [ ] **Step 1: Add the `crossFilter` helper**

Insert immediately after the `buildChips` function (after its closing `}` at ~line 1144):

```javascript
// Cross-filter: a chart click toggles the SAME state Set the manual chips use,
// then re-syncs that dimension's chip so the UI matches, then re-renders.
function crossFilter(parentId, stateKey, value) {
  if (value == null || value === '') return;
  const set = state[stateKey];
  const v = (stateKey === 'years') ? parseInt(value, 10) : value;
  if (set.has(v)) set.delete(v); else set.add(v);
  const parent = document.getElementById(parentId);
  if (parent) parent.querySelectorAll('.chip').forEach(el => {
    const cv = (stateKey === 'years') ? parseInt(el.dataset.value, 10) : el.dataset.value;
    if (cv === v) el.classList.toggle('active', set.has(v));
  });
  applyFilters();
}
```

- [ ] **Step 2: Wire `renderGsoCategory` (horizontal bar → `pt.y` = category)**

At the end of `renderGsoCategory`, after its `reactChart('chart_gso_cat', …)` call, add:

```javascript
  const _gcNode = document.getElementById('chart_gso_cat');
  _gcNode.removeAllListeners && _gcNode.removeAllListeners('plotly_click');
  _gcNode.on('plotly_click', e => crossFilter('f_gso_category', 'gso_category', e.points[0].y));
```

- [ ] **Step 3: Wire the sector chart (in `_renderVolumeVsRate`, vertical bar → `pt.x`)**

`_renderVolumeVsRate` is shared; only the sector instance uses `labelKey === 'sector'`. After its `reactChart(domId, …)` call add:

```javascript
  if (labelKey === 'sector') {
    const _svNode = document.getElementById(domId);
    _svNode.removeAllListeners && _svNode.removeAllListeners('plotly_click');
    _svNode.on('plotly_click', e => crossFilter('f_sector', 'sector', e.points[0].x));
  }
```

- [ ] **Step 4: Wire `renderTopMicrobes` (horizontal bar → `pt.y` = organism)**

After its `reactChart('top-microbes', …)` call add:

```javascript
  const _tmNode = document.getElementById('top-microbes');
  _tmNode.removeAllListeners && _tmNode.removeAllListeners('plotly_click');
  _tmNode.on('plotly_click', e => crossFilter('f_microbe', 'microbe', e.points[0].y));
```

- [ ] **Step 5: Wire `renderSeverityMonth` (grouped bars, trace `name` = tier → `pt.data.name`)**

After its `reactChart('chart_severity_month', …)` call add:

```javascript
  const _smNode = document.getElementById('chart_severity_month');
  _smNode.removeAllListeners && _smNode.removeAllListeners('plotly_click');
  _smNode.on('plotly_click', e => crossFilter('f_severity', 'severity', e.points[0].data.name));
```

- [ ] **Step 6: Wire `renderMap` (scattermapbox, trace `name` = sector → `pt.data.name`)**

After its `reactChart('chart_map', …)` call add:

```javascript
  const _mpNode = document.getElementById('chart_map');
  _mpNode.removeAllListeners && _mpNode.removeAllListeners('plotly_click');
  _mpNode.on('plotly_click', e => { const s = e.points[0].data && e.points[0].data.name;
    if (s) crossFilter('f_sector', 'sector', s); });
```

- [ ] **Step 7: Add the "click charts to filter" hint**

In the year-bar HTML (`<div class="year-bar" id="year_bar">`, ~line 887), add before the reset button:

```html
  <span class="filter-pill" style="background:var(--sand-100)">💡 click any chart to filter</span>
```

- [ ] **Step 8: Rebuild + `node --check` + verify handlers present**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
```
Then run the JS extract+check snippet (Global Constraints). Expected: `JS OK`.
```bash
grep -c "crossFilter(" reports/microbiology_dashboard.html   # expect >= 6 (1 def + 5 handlers)
```

- [ ] **Step 9: Commit**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: click-to-cross-filter on GSO/sector/microbe/severity/map charts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: URL-hash view persistence

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — add `serializeState()`, `deserializeState(hash)`, `syncAllChips()` near `crossFilter` (~line 1160); call `serializeState()` at the end of `applyFilters()`; call `deserializeState(location.hash)` before the initial `applyFilters()` at the bottom of the script.

**Interfaces:**
- Consumes: `state`, `FACETS.years/sectors/severity/gso_categories/date_min/date_max`, `COMPLIANCE_OPTIONS`, `PATHOGEN_SET`, `INDICATOR_SET`, `INDICATOR_TOKEN` (all already defined).
- Produces: `serializeState() → string` (hash body, no leading `#`); `deserializeState(hash)` (mutates `state`, calls `syncAllChips()`); `syncAllChips()` (sets chip `.active` + date inputs + boolean toggles from `state`). Task 3 reuses `syncAllChips()`.

- [ ] **Step 1: Add `serializeState`**

Insert after `crossFilter`:

```javascript
// Encode the non-default parts of `state` into a compact URL-hash body.
function serializeState() {
  const p = [];
  const setParam = (k, s) => { if (s && s.size) p.push(k + '=' + Array.from(s).map(encodeURIComponent).join(',')); };
  setParam('y', state.years); setParam('comp', state.compliance); setParam('sec', state.sector);
  setParam('sev', state.severity); setParam('gso', state.gso_category); setParam('mic', state.microbe);
  if (state.pathogen_only) p.push('path=1');
  if (state.repeat_only) p.push('rep=1');
  if (state.exclude_raw_meat) p.push('xmeat=1');
  if (state.date_from && state.date_from !== FACETS.date_min) p.push('df=' + encodeURIComponent(state.date_from));
  if (state.date_to && state.date_to !== FACETS.date_max) p.push('dt=' + encodeURIComponent(state.date_to));
  return p.join('&');
}
```

- [ ] **Step 2: Add `syncAllChips`**

Note: confirm the pathogen-only and repeat-only toggle element ids by reading their `addEventListener` handlers (search `state.pathogen_only =` and `state.repeat_only =`); substitute the real ids for `PATH_TOGGLE_ID`/`REPEAT_TOGGLE_ID` below.

```javascript
// Push `state` INTO the DOM controls (inverse of the click handlers). Used after
// deserializeState and after a bookmark sets state programmatically.
function syncAllChips() {
  const map = { f_year:'years', f_compliance:'compliance', f_sector:'sector',
                f_severity:'severity', f_gso_category:'gso_category', f_microbe:'microbe' };
  Object.entries(map).forEach(([pid, key]) => {
    const parent = document.getElementById(pid); if (!parent) return;
    parent.querySelectorAll('.chip').forEach(el => {
      const v = (key === 'years') ? parseInt(el.dataset.value, 10) : el.dataset.value;
      el.classList.toggle('active', state[key].has(v));
    });
  });
  document.getElementById('f_date_from').value = state.date_from;
  document.getElementById('f_date_to').value = state.date_to;
  const pt = document.getElementById('PATH_TOGGLE_ID'); if (pt) pt.classList.toggle('active', state.pathogen_only);
  const rp = document.getElementById('REPEAT_TOGGLE_ID'); if (rp) rp.classList.toggle('active', state.repeat_only);
}
```

- [ ] **Step 3: Add `deserializeState`**

```javascript
// Restore `state` from a URL-hash body. Unknown tokens are ignored (never throw).
function deserializeState(hash) {
  if (!hash || hash === '#') return;
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const load = (key, sk, valid, cast) => {
    const raw = params.get(key); if (!raw) return;
    raw.split(',').forEach(v0 => { const v = decodeURIComponent(v0);
      if (valid && !valid.has(cast ? cast(v) : v)) return;
      state[sk].add(cast ? cast(v) : v); });
  };
  load('y', 'years', new Set((FACETS.years || []).map(Number)), v => parseInt(v, 10));
  load('comp', 'compliance', new Set(COMPLIANCE_OPTIONS));
  load('sec', 'sector', new Set(FACETS.sectors || []));
  load('sev', 'severity', new Set(FACETS.severity || []));
  load('gso', 'gso_category', new Set(FACETS.gso_categories || []));
  const mic = params.get('mic');
  if (mic) mic.split(',').forEach(v0 => { const v = decodeURIComponent(v0);
    if (v === INDICATOR_TOKEN || PATHOGEN_SET.has(v) || INDICATOR_SET.has(v)) state.microbe.add(v); });
  if (params.get('path') === '1') state.pathogen_only = true;
  if (params.get('rep') === '1') state.repeat_only = true;
  if (params.get('xmeat') === '1') state.exclude_raw_meat = true;
  const df = params.get('df'); if (df) state.date_from = decodeURIComponent(df);
  const dt = params.get('dt'); if (dt) state.date_to = decodeURIComponent(dt);
  syncAllChips();
}
```

- [ ] **Step 4: Write the hash at the end of `applyFilters()`**

Find the end of `applyFilters()` (the line `renderAll(rowsFiltered);`) and add immediately after it:

```javascript
  const _hash = serializeState();
  history.replaceState(null, '', _hash ? '#' + _hash : location.pathname + location.search);
```

- [ ] **Step 5: Restore on load**

Find the final bare `applyFilters();` call at the bottom of the script and change it to:

```javascript
deserializeState(location.hash);
applyFilters();
```

- [ ] **Step 6: Rebuild + `node --check` + verify round-trip**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
```
Run the JS extract+check snippet → expect `JS OK`. Then check presence:
```bash
grep -c "serializeState\|deserializeState\|syncAllChips" reports/microbiology_dashboard.html  # expect >= 6
grep -c "PATH_TOGGLE_ID\|REPEAT_TOGGLE_ID" reports/microbiology_dashboard.html                # expect 0 (placeholders replaced)
```

- [ ] **Step 7: Commit**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: URL-hash view persistence (state <-> location.hash)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Bookmarks bar + copy-link

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — add a bookmarks bar `<div>` under the year-bar HTML; add `applyBookmark(name)` + `copyViewLink()` JS near `deserializeState`; wire the buttons. Confirm the non-compliant `compliance` chip token by reading `COMPLIANCE_OPTIONS`.

**Interfaces:**
- Consumes: `state`, `syncAllChips()`, `applyFilters()`, the Reset logic (clears all Sets/bools).

- [ ] **Step 1: Add the bookmarks bar HTML**

Directly after the closing `</div>` of the year-bar (~line 894), insert:

```html
<div class="year-bar" id="bookmark_bar" style="gap:8px">
  <span class="year-bar-label">Views</span>
  <button class="btn" data-bm="path2025">2025 · pathogens only</button>
  <button class="btn" data-bm="central">Central sector</button>
  <button class="btn" data-bm="noncomp">Non-compliant only</button>
  <button class="btn" data-bm="rte">Ready-to-Eat foods</button>
  <button class="btn" id="btn_copy_link" style="margin-left:auto">🔗 Copy view link</button>
</div>
```

- [ ] **Step 2: Add `applyBookmark`**

Confirm the non-compliant token: `grep -n "COMPLIANCE_OPTIONS" scripts/build_dashboard_combined.py` and read its values; substitute the real non-compliant string for `NONCOMPLIANT_TOKEN` below.

```javascript
// One-click preset views. Each clears state, sets its combo, syncs UI, re-renders.
function applyBookmark(name) {
  state.years.clear(); state.compliance.clear(); state.sector.clear();
  state.severity.clear(); state.gso_category.clear(); state.microbe.clear();
  state.pathogen_only = false; state.repeat_only = false;
  state.date_from = FACETS.date_min; state.date_to = FACETS.date_max;
  if (name === 'path2025') { state.years.add(2025); state.pathogen_only = true; }
  else if (name === 'central') { state.sector.add('Central'); }
  else if (name === 'noncomp') { state.compliance.add('NONCOMPLIANT_TOKEN'); }
  else if (name === 'rte') { state.gso_category.add('Ready to Eat Foods'); }
  syncAllChips();
  applyFilters();
}
```

- [ ] **Step 3: Add `copyViewLink`**

```javascript
function copyViewLink() {
  const url = location.href;
  const done = () => { const b = document.getElementById('btn_copy_link');
    const t = b.textContent; b.textContent = 'copied ✓'; setTimeout(() => b.textContent = t, 1500); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(done).catch(() => window.prompt('Copy this view link:', url));
  } else {
    const i = document.createElement('input'); i.value = url; document.body.appendChild(i);
    i.select(); try { document.execCommand('copy'); done(); } catch (_) { window.prompt('Copy this view link:', url); }
    document.body.removeChild(i);
  }
}
```

- [ ] **Step 4: Wire the buttons**

Add near the other DOM wiring (after `buildChips(...)` calls, ~line 1160):

```javascript
document.querySelectorAll('#bookmark_bar [data-bm]').forEach(b =>
  b.addEventListener('click', () => applyBookmark(b.dataset.bm)));
document.getElementById('btn_copy_link').addEventListener('click', copyViewLink);
```

- [ ] **Step 5: Rebuild + `node --check` + verify**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -1
```
Run JS extract+check → `JS OK`. Then:
```bash
grep -c "applyBookmark\|copyViewLink\|bookmark_bar" reports/microbiology_dashboard.html  # expect >= 4
grep -c "NONCOMPLIANT_TOKEN" reports/microbiology_dashboard.html                          # expect 0
```

- [ ] **Step 6: Commit**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: bookmarks bar (4 presets) + copy-view-link

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Frictionless refresh script + README

**Files:**
- Create: `microbiology/scripts/refresh.sh`
- Create: `microbiology/scripts/README_refresh.md`

- [ ] **Step 1: Confirm `clean_2025.py` invocation**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology
grep -n "argparse\|add_argument\|--year" scripts/clean_2025.py | head
```
If it takes no `--year`, call it bare (as written below); if it requires `--year 2025`, append that flag in Step 2.

- [ ] **Step 2: Write `refresh.sh`**

```bash
#!/usr/bin/env bash
# One-command full refresh: re-clean both years, re-enrich, rebuild the dashboard.
# The self-contained HTML lands at reports/microbiology_dashboard.html.
set -euo pipefail
cd "$(dirname "$0")/.."          # -> microbiology/
PY=.venv/bin/python
echo "▶ 1/5 clean 2024";    "$PY" scripts/clean_2024.py --year 2024
echo "▶ 2/5 enrich 2024";   "$PY" scripts/enrich_2024.py --year 2024
echo "▶ 3/5 clean 2025";    "$PY" scripts/clean_2025.py
echo "▶ 4/5 enrich GSO";    "$PY" scripts/enrich_gso.py
echo "▶ 5/5 build";         "$PY" scripts/build_dashboard_combined.py
echo "✔ dashboard refreshed → reports/microbiology_dashboard.html"
```

- [ ] **Step 3: Make it executable and run it**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology
chmod +x scripts/refresh.sh
./scripts/refresh.sh 2>&1 | tail -6
```
Expected final lines include `✔ dashboard refreshed` and the build line reporting `2024=9316 2025=11564`.

- [ ] **Step 4: Write `README_refresh.md`**

```markdown
# Refreshing the microbiology dashboard

One command rebuilds everything from the raw files:

    ./scripts/refresh.sh

It re-cleans 2024 + 2025, re-enriches (GSO join), and regenerates the
self-contained dashboard at `reports/microbiology_dashboard.html`. Share that
one file — it needs no server and opens in any browser.

## Scheduled auto-refresh (optional)

There is no live server; "fresh" means re-running the build. To refresh daily at
06:00, add a cron entry (`crontab -e`):

    0 6 * * * cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology && ./scripts/refresh.sh >> /tmp/micro_refresh.log 2>&1
```

- [ ] **Step 5: Commit**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad
git add microbiology/scripts/refresh.sh microbiology/scripts/README_refresh.md \
        microbiology/cleaned/*.parquet microbiology/reports/microbiology_dashboard.html
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Add one-command dashboard refresh (refresh.sh) + README

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Cross-filtering (4 dims + map) → Task 1 ✓
- URL-hash sync + restore → Task 2 ✓
- Copy view link → Task 3 ✓
- Bookmarks (4 presets) → Task 3 ✓
- Frictionless refresh + README/cron → Task 4 ✓
- Out-of-scope items (framework, backend, export, chains/subtypes cross-filter) → correctly absent ✓

**Placeholder note:** `PATH_TOGGLE_ID`, `REPEAT_TOGGLE_ID`, `NONCOMPLIANT_TOKEN` are intentional lookups with an explicit "confirm by reading X" instruction and a grep gate that fails if left unreplaced — not silent placeholders.

**Type consistency:** `crossFilter(parentId, stateKey, value)`, `serializeState()→string`, `deserializeState(hash)`, `syncAllChips()`, `applyBookmark(name)`, `copyViewLink()` are referenced consistently across tasks; all reuse the existing `state` Sets and `applyFilters()`.
