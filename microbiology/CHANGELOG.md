# Microbiology Changelog

## 2026-08-11 — Core dashboard: tabbed, touch-first redesign

Restructured `microbiology_dashboard.html` (via `scripts/build_dashboard_combined.py`)
from one long scroll of ~13 panels into a **5-tab, touch-first instrument**. Totals
unchanged: **20,881 rows** (2024=9,317 · 2025=11,564); emitted JS passes `node --check`;
still self-contained offline HTML with the Riyadh masthead.

- **Zoom / pinch / touch on every chart.** Shared `PLOTLY_CONFIG` now enables
  `scrollZoom`, `displayModeBar:'hover'`, `doubleClick:'reset'` (lasso/select/autoscale
  removed); `reactChart` defaults to it. The map keeps its own explicit config.
- **5-tab shell with "lab-record divider" tabs** (📊 Overview · 📍 Location · 🍱 Products ·
  🦠 Organisms & tests · 📋 GSO & Quality). Masthead + filter bar + KPI strip + Views/bookmarks
  stay pinned above all tabs. Charts render once and `Plotly.Plots.resize()` on tab-show
  (Plotly can't lay out in a hidden container). Interior Where/When/Who dividers retired.
- **Active tab persisted in the URL hash** (`tab=`); old links without it open Overview.
- **Extended click-to-drill:** the severity × GSO-category heatmap is now tappable
  (cell → filters that GSO category, mapping the shortened axis label back to the full
  name). Sample-type and chains charts were left non-interactive — no matching filter
  dimension exists (adding those filters is separate feature work).
- **Sortable GSO 1016 categories table** in the GSO & Quality tab: Category · Code ·
  Samples · Non-compliant · NC %, header-click sort (numeric-aware). Represents the
  numbers; makes no scope judgment.
- **Merged the two failed-tests bars into one chart** with a Pathogens/Indicators toggle
  (per-year stacking preserved; drilldown preserved). Added a 3-stop data-palette token
  set (`--data-compliant/indicator/pathogen/neutral`) and retinted the non-compliance
  rate line to `#c0392b` for a consistent NC signal.

Spec: `docs/superpowers/specs/2026-08-10-micro-dashboard-tabbed-redesign-design.md`.
Plan: `docs/superpowers/plans/2026-08-10-micro-dashboard-tabbed-redesign.md`.

## 2026-08-10 — Standalone Interactive Microbiology Deliverables (Interactive 3 to 7)

Created 5 dedicated interactive HTML reports in `microbiology/reports/` and linked them on the main landing page (`index.html`) under the Microbiology card list:

- 🔀 **Interactive 3 · Sankey Flow Explorer** (`build_micro_sankey.py` → `microbiology_sankey.html`): Multi-stage flow tracking sample failures (`Location/Sector → Food Category → Organism → Severity Outcome`).
- 🟦 **Interactive 4 · Treemap & Hierarchy Explorer** (`build_micro_treemap.py` → `microbiology_treemap.html`): Hierarchical treemap (`Sector → Category → Subtype → Organism`) with volume and non-compliance metric toggles.
- 🔥 **Interactive 5 · Sector Location × Pathogen Matrix Heatmap** (`build_micro_heatmap_matrix.py` → `microbiology_heatmap_matrix.html`): Contamination intensity matrix mapping 5 Riyadh Sectors against top pathogens.
- 🕸️ **Interactive 6 · Product Category ↔ Microbe Network Graph** (`build_micro_network.py` → `microbiology_network.html`): Bipartite relationship graph connecting Food Categories (green nodes) with Microbes (red nodes).
- 📈 **Interactive 7 · Organism Prevalence Streamgraph** (`build_micro_streamgraph.py` → `microbiology_streamgraph.html`): Smooth stacked area streamgraph depicting monthly pathogen relative prevalence over 2024–2025.

**Wiring & Integrity:**
- Kept the main decision dashboard (`microbiology_dashboard.html`) clean and focused on its core Riyadh map, filters, and KPIs.
- Updated `build_landing.py` to display cards for Interactive 3 through 7.
- Updated `microbiology/scripts/refresh.sh` to build all interactive deliverables in sequence.

## 2026-08-10 — Name rules made 2025-ONLY (restores the 2024 panel audit)

Muhannad flagged (from the dashboard GSO-audit card) that the "both years"
override had broken 2024 panel completeness: **systematic gaps collapsed
1,756 → 13**, sporadic inflated, lab-vs-GSO disagreements 62 → 109. Cause: the
2024 panel/limit audit judges each sample against the tests required for the
code the lab **actually tested it under** (its native code); overriding e.g. a
C-9 chicken to P-4 compared it against the wrong panel, and P became a
heterogeneous bucket so no ≥90% systematic gap survived.

**Fix (decision: rules 2025-only):**
- `enrich_gso.py` — `apply_gso_name_rules` and `reclassify_group_c` now run only
  when `label == "2025"`; the `enrich_long` (2024) override was removed. 2024
  keeps its native lab codes end-to-end.
- Dashboard explainer + the "re-coded by name rule" card now say **2025 only ·
  2024 keeps its native lab codes**.

**Verified:** 2024 `gso_code_rule_applied` non-null = **0**; panel_complete
restored to **3,756 / 4,126**, lab-vs-GSO disagreements to **54**. 2025 rules
intact (cooked_to_P 1,235, sauce_to_G 1,844; 2025 coverage 53.1%). Row total
20,881; dashboard + both sunbursts rebuilt, `node --check` clean.

## 2026-08-10 — Validation file for Muhannad + Group B doc cleanup

- Added `microbiology/VALIDATION_2026-08-10.md` — a consolidated input file for
  Muhannad: records the GSO rule-layer changes, asks him to validate the
  reclassification + the 2,069 2024 native-code overrides, and lists every open
  issue/decision (Group B/C, edge cases, MR items B3–B7, enhancement backlog)
  with fill-in fields.
- Regenerated `kimi/yolo/2025_gso_groupB_disambiguation.md` to **exclude
  environmental swab names** (363 `مسحة …` names, 1,674 rows, were polluting the
  top of the list). Now shows the top 150 real food/drink names of the 3,751
  non-swab uncoded 2025 rows for code sign-off. No parquet/data change.

## 2026-08-10 — Final-review precision fixes: sauce-head precedence, رز whole-token, N-3 tag clear

Three findings from the whole-branch final review, all in `enrich_gso.py`:

- **Sauce-head precedence (Important, 66 rows)**: names whose first
  normalised token is صوص/صلصة (e.g. `صوص برجر`, `صوص مشوي`, `صوص تارتار`,
  `صوص حمص`, `صوص رز`) were being caught by `classify_prepared_to_P` (cooked
  rule ran first) instead of `classify_sauce_to_G`, even though the head noun
  of the name is the sauce itself. `apply_gso_name_rules` now checks the
  first token first: if it is صوص/صلصة, the sauce rule wins outright; only
  when the name's head noun is something else (e.g. `بطاطس مقلي بصوص`) does
  cooked-before-sauce precedence still apply. Real dishes named after a
  prepared-food noun (`برجر لحم`) are unaffected — `برجر`/`برغر` remain in
  `_PREP_MAIN`.
- **رز substring over-match (Important, 36 rows)**: `رز`/`ارز` were matching
  as substrings inside كرز (cherry), churros, snickers, tenders, etc.,
  wrongly assigning P-5 (rice). Changed to the same whole-token guard already
  used for حمص: `"رز" in n.split() or "ارز" in n.split()`.
- **Stale cooked_to_P tag on N-3 wash-water rows (Minor, 17 rows)**:
  `reclassify_group_c` rewrites رز-wash-water rows' `gso_code_canonical` to
  N-3 but was leaving `gso_code_rule_applied="cooked_to_P"` behind (the
  wash-water sample name often contains "رز" style tokens that had tripped
  the rule upstream). The wash-water branch now also clears the rule tag to
  `None` on the rows it touches; the food-named-swab branch (which only
  changes `sample_type`) is untouched.

Regression tests added to `scripts/test_gso_rules.py`: sauce-head vs.
dish-with-sauce vs. real-burger precedence; كرز/سنيكرز no longer classify as
rice; `رز برياني` still resolves to P-5.

Re-ran `enrich_gso.py` (row total unchanged: 20,881) and rebuilt all three
dashboards (each confirms 20,881 rows). Tag tallies shifted as expected:
`cooked_to_P` 2,340 → 2,239, `sauce_to_G` 2,856 → 2,909. Verified: no
sauce-head name remains tagged `cooked_to_P`; `classify_prepared_to_P`
returns `None` for pure كرز/سنيكرز names; zero rows have
`gso_code_rule_applied=="cooked_to_P"` and `gso_code_canonical=="N-3"`
simultaneously.

## 2026-08-09 (4) — GSO name-rule reclassification layer (cooked→P, صوص→G) + Group A/C + dashboard surfacing

### Problem
GSO 1016 coding relied on source codes (2024) and sample-name matching against
2024-learned names (2025). Two large, unambiguous name patterns were still
falling through uncoded or landing on the wrong category regardless of source
code: cooked/prepared dishes (سلطة مطبوخة, حمص, متبل, بطاطس مقلي, دجاج شواية,
etc.) that belong under Ready-to-Eat/Prepared Foods (P), and sauce items
(صوص كاتشب, صوص ثوم, صوص مايونيز, etc.) that belong under Sauces/Condiments
(G). Spelling/spacing variants of already-coded 2025 names were also missed
by the looser Tier-1 name normaliser, and wash-water swabs and food-named
swabs were sitting in the wrong `sample_type` bucket.

### Changes (Tasks 1–5, this branch)
- **Rule 1 — cooked → P**: added `classify_prepared_to_P` keyword classifier
  (Task 1) and wired it into both years' wide (and 2024 long) parquets via
  `apply_gso_name_rules` (Task 2). Matches whole-token "حمص" (hummus) rather
  than substring, so "محمص" (toasted) is not falsely caught (fixed in the
  swab-guard commit).
- **Rule 2 — صوص → G**: added `classify_sauce_to_G` (Task 1), same wiring
  (Task 2). Precedence: cooked-before-sauce when a name could match both.
- **Swab guard**: `apply_gso_name_rules` now skips environmental swab names
  (مسحه token) so swabs are never reclassified to a food code — previously
  133 rows (2024=25, 2025=108) would have been wrongly food-coded.
- **Group A (2025 strict-equality tier)**: added `_norm_name_strict` +
  Tier-1b strict-equality pass in `assign_2025_codes_by_name` (Task 3) —
  exact-match-only (no fuzzy matching) so false friends (e.g. جبنة بيتزا vs
  لبنه بيتزا, لحم سبايسي vs حمص سبايسي) cannot collide. +111 rows coded for
  2025 (36.9% → 37.8% of 11,564).
- **Group B (review doc, not auto-applied)**: generated
  `kimi/yolo/2025_gso_groupB_disambiguation.md` — top 120 still-uncoded 2025
  sample names (by row count) for manual code assignment; 3,163 distinct
  uncoded names / 5,412 uncoded rows remain in 2025 after rules + Group A.
- **Group C**: added `reclassify_group_c(df)` (Task 4) — wash-water swabs
  (غسيل + exact keyword phrases) reclassified to `N-3` / `sample_type=water`
  (225 rows: 2025=169, 2024=56); food-named rows previously stuck at
  `sample_type=swab` (e.g. تشيز كيك توت, سلطة خضراء, رمان حب) now carry their
  correct food typing. Genuine environmental swabs (مسحة طاولة تحضير شاورما,
  etc.) remain uncoded/`swab` — untouched.
- **New column** `gso_code_rule_applied` (values `cooked_to_P` / `sauce_to_G`
  / null) added to both years' parquets (Task 2), recording which rows had
  their GSO code set/overridden by the name-rule layer.
- **Dashboard**: added `gso_code_rule_applied` to `build_dashboard_combined.py`'s
  `DATA_COLS` payload (with a fill-missing guard on `combined` for older
  parquets), a new GSO-audit card `↳ re-coded by name rule (cooked→P /
  صوص→G)` showing the combined-years count, and an explainer sentence
  describing the rule layer.

### Counts (both years combined, post-rules)
- `gso_code_rule_applied == cooked_to_P`: **2,340** rows (2024=1,051 · 2025=1,289)
- `gso_code_rule_applied == sauce_to_G`: **2,856** rows (2024=1,047 · 2025=1,809),
  of which G-3=2,633 / G-2=223
- 2024 coded: 7,955 / 9,317 (85.4%)
- 2025 coded: 6,152 / 11,564 (53.2%)
- Row totals unchanged throughout: 2024=9,317, 2025=11,564, **total=20,881**

### Files touched
- `microbiology/scripts/enrich_gso.py` (Tasks 1–4: classifiers, rule wiring,
  Group A strict tier, Group C reclassification)
- `microbiology/scripts/test_gso_rules.py` (Tasks 1, 3: unit + false-friend tests)
- `microbiology/cleaned/data2024.parquet`, `data2025.parquet` (regenerated,
  Tasks 2–4)
- `microbiology/scripts/build_dashboard_combined.py` (this entry: payload
  column + guard + GSO-audit card)
- `microbiology/reports/microbiology_dashboard.html`,
  `microbiology_sunburst.html`, `microbiology_sunburst2.html` (rebuilt)
- `kimi/yolo/2025_gso_groupB_disambiguation.md` (new — Group B review doc)

### How to regenerate
```bash
python3 microbiology/scripts/enrich_gso.py
python3 microbiology/scripts/build_dashboard_combined.py
python3 microbiology/scripts/build_micro_sunburst.py
python3 microbiology/scripts/build_micro_sunburst2.py
```

### Verify
- `node --check` passes on the largest `<script>` in all three rebuilt
  HTML files.
- Dashboard prints `20881 rows` (2024=9317, 2025=11564).
- Spot-check: cooked items (`حمص`, `متبل`, `بطاطس مقلي`, `دجاج شواية`, …) all
  carry category "Ready to Eat Foods" (P); صوص items (`صوص كاتشب`, `صوص ثوم`,
  `صوص مايونيز`, …) all carry category "Tomato Concentrates, Sauces, Vinegar,
  Spices and Herbs" (G-2/G-3).

### Push note
- Committed and pushed to `origin/main` with message `Dashboard: surface GSO
  rule reclassification; Group B review doc; rebuild`.

## 2026-08-08 — added build timestamp (date + time) to dashboards and landing page

### Changes
- `microbiology/scripts/build_dashboard_combined.py`: changed the masthead "Last build" stamp from date-only to `dd Mmm YYYY · HH:MM`.
- `microbiology/scripts/build_micro_sunburst.py` and `build_micro_sunburst2.py`:
  - Imported `datetime`.
  - Added an `updated __STAMP__` line to the footer.
  - Stamp format: `dd Mmm YYYY · HH:MM`.
- `build_landing.py`: updated the footer `build __STAMP__` to include time as well.
- Rebuilt all three microbiology dashboards and `index.html`.

### Files touched
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/scripts/build_micro_sunburst.py`
- `microbiology/scripts/build_micro_sunburst2.py`
- `build_landing.py`
- `microbiology/reports/microbiology_dashboard.html`
- `microbiology/reports/microbiology_sunburst.html`
- `microbiology/reports/microbiology_sunburst2.html`
- `index.html`

### How to regenerate
```bash
python3 microbiology/scripts/build_dashboard_combined.py
python3 microbiology/scripts/build_micro_sunburst.py
python3 microbiology/scripts/build_micro_sunburst2.py
python3 build_landing.py
```

### Push note
- Committed and pushed to `origin/main` with message `Add build date+time stamp to dashboards and landing page (kimi push)`.

## 2026-08-08 — landing page: chemistry under construction, microbiology count corrected

### Problems addressed
- The root `index.html` landing page linked to chemistry dashboards/sunbursts that have not yet been audited/rebuilt, so users could open stale or inconsistent reports.
- The microbiology sample count on the landing page still showed **20,880** instead of the current **20,881**.

### Changes
- Updated `build_landing.py`:
  - Replaced the three chemistry `<a class="entry">` links with `<div class="entry disabled">` elements.
  - Added `under construction · قيد الإنشاء` labels and 🚧 arrows.
  - Added `.entry.disabled` CSS (reduced opacity, `not-allowed` cursor, no pointer events) and an "Audit in progress" badge above the chemistry entries.
  - Updated the microbiology sample count from **20,880 → 20,881**.
- Rebuilt `index.html` from the template.

### Files touched
- `build_landing.py`
- `index.html`

### How to regenerate
```bash
python3 build_landing.py
```

### Push note
- Committed and pushed to `origin/main` with message `Landing page: chemistry under construction, micro count corrected (kimi push)`.

## 2026-08-08 — sunburst dashboards rebuilt with correct non-compliance denominator

### Problems addressed
- Both sunburst dashboards (`microbiology_sunburst.html` and `microbiology_sunburst2.html`) were treating 2024 rows with unknown validity (`is_failure = NaN/None`) as "✓ Compliant", which understated the true non-compliance rate and made it inconsistent with the main Plotly dashboard.
- The sunburst non-compliance percentage was computed as `nc / total_samples` instead of `nc / known_validity_samples`.

### Changes
- Updated `scripts/build_micro_sunburst.py` and `scripts/build_micro_sunburst2.py`:
  - Detect rows where `is_failure` is null/NaN and assign them a new leaf label **"Unknown validity"**.
  - Track `nu` (unknown-validity count) per node.
  - Use `n - nu` as the denominator for `% contaminated` and `% pathogen` calculations so the rate matches the main dashboard.
- Updated the sunburst HTML/JS templates:
  - Added an **Unknown validity** readout cell in the specimen slip.
  - Added `.cell.unknown` CSS styling.
  - Updated centre nucleus readout, colour scale, and hover percentages to use the known-validity denominator.

### Results
- All three microbiology dashboards now agree:
  - Total samples: **20,881**
  - Unknown validity: **83**
  - Overall non-compliance rate (known-validity only): **28.1%**
- `node --check` passes on the extracted app JavaScript for all three dashboards.

### Files touched
- `microbiology/scripts/build_micro_sunburst.py`
- `microbiology/scripts/build_micro_sunburst2.py`
- `microbiology/reports/microbiology_sunburst.html`
- `microbiology/reports/microbiology_sunburst2.html`
- `microbiology/reports/microbiology_dashboard.html` (rebuilt for consistency)
- `kimi/yolo/microbiology_audit_report.md`
- `kimi/yolo/microbiology_remaining_gaps_and_suggestions.md`

### How to regenerate
```bash
cd microbiology
.venv/bin/python scripts/build_dashboard_combined.py
.venv/bin/python scripts/build_micro_sunburst.py
.venv/bin/python scripts/build_micro_sunburst2.py
```

### Push note
- Committed and pushed to `origin/main` with message `Microbiology sunburst dashboards rebuilt with correct NC denominator (kimi push)`.

### Next steps (not in this change)
- Confirm with Muhannad the exact rule behind the Annual Report 2025 sample count (11,404 vs 11,564).
- Once 2024 official numbers are reconciled, re-populate `OFFICIAL_COMPLIANCE[2024]`.
- Move to chemistry audit.

## 2026-08-08 — dashboard filter/chart/label audit and fixes

### Problems addressed
- **Reset button** cleared the active state of every `.toggle` element, including the map metric (`% non-compliance` / `% pathogen` / `Total samples`) and map tile (`Light` / `Streets` / `Dark`) view controls, without resetting their underlying JavaScript variables, leaving the UI out of sync.
- **Severity filter chips** and severity chart labels displayed raw codes (`indicator_only`, `pathogen`, `multi_pathogen`).
- **Sample-type distribution chart** x-axis displayed raw codes (`produce`, `dairy`, etc.).
- **Data-quality summary** only counted "Unknown validity" and "Missing facility name" for rows that also had `data_quality_flags`, under-reporting both.

### Changes
- Refactored `btn_reset` click handler in `scripts/build_dashboard_combined.py`:
  - Removed the broad `document.querySelectorAll('.toggle').forEach(...)` clear.
  - Now calls `syncAllChips()` so only the actual filter chips and filter toggles are reset; map view toggles keep their state and active appearance.
- Added `SEVERITY_LABEL` and `SAMPLE_TYPE_LABEL` lookup maps near the top of the dashboard JS.
- Added `LABEL_TO_RAW` reverse lookup so chart clicks on human-readable labels resolve back to the raw state values used by filter chips.
- Extended `buildChips()` with an optional `labelMap` argument; severity chips now show "Indicator only", "Pathogen", "Multi-pathogen" while still storing raw values in `dataset.value`.
- Updated `renderSeverityMonth`, `renderYoY`, and `renderHeatmap` to use readable severity labels on axes/legends/hover.
- Updated `renderSampleTypeDistribution` to show readable sample-type labels and sort types by total count descending.
- Updated `renderDataQualitySummary`:
  - Counts `Unknown validity` across the whole view.
  - Counts `Missing facility name` only for 2025 rows (2024 source has no facility field).
  - Adds an "Other top flags" card showing the top 3 remaining flags in the current view.

### Results
- Dashboard JavaScript passes `node --check` with no syntax errors.
- All filter containers (`f_year`, `f_compliance`, `f_severity`, `f_sector`, `f_gso_category`, `f_microbe`, date inputs, quick toggles) remain wired to `applyFilters()`.
- All chart containers have matching render functions called from `renderAll()`.
- Dashboard total remains **20,881** (2024 = 9,317; 2025 = 11,564).

### Files touched
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/reports/microbiology_dashboard.html`
- `kimi/yolo/microbiology_audit_report.md`
- `kimi/yolo/microbiology_remaining_gaps_and_suggestions.md`

### How to regenerate
```bash
cd microbiology
.venv/bin/python scripts/build_dashboard_combined.py
```

### Push note
- Committed and pushed to `origin/main` with message `Microbiology dashboard filter/chart/label audit (kimi push)`.

### Next steps (not in this change)
- Confirm with Muhannad the exact rule behind the Annual Report 2025 sample count (11,404 vs 11,564).
- Once 2024 official numbers are reconciled, re-populate `OFFICIAL_COMPLIANCE[2024]`.
- Move to chemistry audit.

## 2026-08-08 — facility normalisation, English category fallbacks, data-quality dashboard cards

### Problems addressed
- Facility-chain spelling variants (`صب وأي` vs `صب واي`) were splitting the same chain into separate rows in repeat-offender and chain-ranking aggregations.
- 383 rows in 2025 had `category_en = NA` because their `category_canonical` was Arabic-only.
- Data-quality flags (sample-id collisions, validity conflicts, date parsing, category merges) were only visible in script logs and parquet columns, not surfaced in the dashboard.
- The 2024 vs 2025 sample-type split was not shown in a single chart.

### Changes
- Added `FACILITY_SUBSTRING_REPLACEMENTS` to `scripts/clean_2025.py`:
  - `("صب وأي", "صب واي")` merges the two Subway spelling variants before chain/branch splitting.
- Added `CATEGORY_EN_FALLBACK` mapping in `scripts/clean_2025.py` for Arabic-only categories:
  - Covers cooked/grilled vegetables, tahini, breads, rice dishes, fish types, sauces, salads, desserts, swab labels, etc.
- Extended `DATA_COLS` in `scripts/build_dashboard_combined.py` to include `sample_type` and `dq_flags` in the per-row dashboard payload.
- Added a **Data-quality summary** KPI card to the dashboard (`#data_quality_summary`, `renderDataQualitySummary`).
- Added a **Sample-type distribution** grouped bar chart (`#chart_sample_type`, `renderSampleTypeDistribution`).

### Results
- 2025 `facility_chain == 'صب واي'` now rolls up **68 rows** under one spelling.
- 2025 `category_en` missing dropped from **383 → 129 rows**; the remainder are mostly unique/free-text sample descriptions.
- Dashboard total remains **20,881** (2024 = 9,317; 2025 = 11,564).
- Dashboard now exposes quality-flag counts and year-over-year sample-type distribution.

### Files touched
- `microbiology/scripts/clean_2025.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/cleaned/data2025.parquet`
- `microbiology/cleaned/data2024.parquet`
- `microbiology/cleaned/data2024_long.parquet`
- `microbiology/reports/microbiology_dashboard.html`
- `microbiology/reports/data2025_diff.md`
- `microbiology/reports/data2025_review.md`
- `kimi/yolo/microbiology_audit_report.md`
- `kimi/yolo/microbiology_remaining_gaps_and_suggestions.md`

### How to regenerate
```bash
cd microbiology
.venv/bin/python scripts/clean_2025.py "2025-original/Data 2025.xlsx" cleaned/data2025.parquet reports/data2025_diff.md
.venv/bin/python scripts/enrich_gso.py
.venv/bin/python scripts/build_dashboard_combined.py
```

### Push note
- Committed and pushed to `origin/main` with message `Microbiology re-audit enhancements (kimi push)`.

### Next steps (not in this change)
- Confirm with Muhannad the exact rule behind the Annual Report 2025 sample count (11,404 vs 11,564).
- Once 2024 official numbers are reconciled, re-populate `OFFICIAL_COMPLIANCE[2024]`.
- Move to chemistry audit.

## 2026-08-08 — 2024 category & swab classification fix

### Problem
- `cleaned/data2024.parquet` had `category_canonical = NA` for all 9,316 rows.
- 1,332 of those rows had no `gso_code` and therefore appeared as "Unspecified" in dashboard category filters/charts.
- Investigation showed the no-code rows are environmental/hygiene swabs (`مسحة ...`), not food products, so they legitimately lack a GSO 1016 product code.

### Change
- Modified `scripts/enrich_gso.py` to populate `category_canonical`, `category_en`, and `sample_type` for the 2024 wide parquet:
  - Rows with a valid, mappable `gso_code` are assigned a category derived from `gso_category_name_en` using a new `GSO_CATEGORY_TO_DISPLAY` mapping (Arabic labels aligned with 2025 categories).
  - Rows with no `gso_code`, or a code that cannot be normalised/mapped, are classified as:
    - `category_canonical = "(Swabs) المسحات"`
    - `category_en = "Swabs"`
    - `sample_type = "swab"`
- Added `classify_sample_type_from_en()` helper in `scripts/enrich_gso.py` to assign `sample_type` consistently with the bucket keywords in `schemas/lab_data_2025_v1.yaml`.

### Result
- 2024 rows now have categories:
  - 7,845 rows mapped from GSO code
  - 1,471 rows classified as swabs
- Dashboard category filters and charts now work for 2024 data instead of showing everything as "Unspecified."
- Total dashboard count unchanged at 20,880 (2024 = 9,316; 2025 = 11,564).

### Files touched
- `microbiology/scripts/enrich_gso.py` — added category mapping + swab fallback
- `microbiology/cleaned/data2024.parquet` — regenerated
- `microbiology/reports/microbiology_dashboard.html` — rebuilt

### How to regenerate
```bash
cd microbiology
.venv/bin/python scripts/enrich_gso.py
.venv/bin/python scripts/build_dashboard_combined.py
```

## 2026-08-08 — sample_type buckets, 2024 GSO placeholders, validity conflicts, unknown-validity handling

### Problems addressed
- 2025 sample-type buckets were missing keywords found in the cleaned data; `other` held 23 rows including okra, berries, avocado, kofta, halloumi, shira, popcorn, etc.
- 2024 had 137 rows with placeholder/raw GSO codes (`H`, `1`, `31`, `124`, etc.) that could not be normalised, so they were falling back to `swab` even though 73 of them are food products.
- 2025 had 9 rows where `is_valid` disagreed with `invalid_tests`; the dashboard needed a single decision-maker.
- 2024 had 83 rows with unparseable/unknown validity; they were being silently counted as compliant.

### Changes
- Expanded `sample_type_buckets` in `schemas/lab_data_2025_v1.yaml`:
  - `produce`: okra/بامية, ملوخية, berries, avocado/افوكادو, celery, peaches, grapes/عنب, guava/جوافة, radish/فجل, tabbouleh/تبولة, pine/الصنوبر, mango/مانجا.
  - `dairy`: dairy, halloumi/حلومي, cheddar/شيدر, ايسكريم.
  - `prepared_meal`: محاشي, kofta/كفتة, kibbeh/كبة, ايدام, مصقع, مشكل, barbecue/باربكيو.
  - `sauce_condiment`: shira/شيرة, تتبيلة, بابا غنوج.
  - `sweets_bakery`: تراميسو, tiramisu, كريم كراميل/كاراميل, waffle/وافل, بيتي فور, chips, شبس, فشار, popcorn, مهلبية/mahalibah, حلا.
  - `cereals`: شابورة/شابورا.
  - Added an early `sweets_bakery` catch before `produce` so popcorn/chips are not grabbed by the broad `corn` keyword.
  - `cooked_meat_poultry`: turkey/ديك رومي.
- Mirrored the new keywords in `enrich_gso.py::SAMPLE_TYPE_KEYWORDS` so 2024 GSO-derived categories classify consistently.
- Added placeholder-GSO recovery in `enrich_gso.py`:
  - Builds a `sample_name → canonical gso_code` lookup from valid 2024 rows.
  - Applies it to rows whose raw `gso_code` is present but un-normalisable.
  - 73 food-product rows recovered; 64 remain as swabs (mostly `مسحة …` environmental samples).
- Changed 2025 `is_failure` logic in `scripts/clean_2025.py` to Option A: trust the objective test-result list (`n_failed_tests > 0`) rather than the OR of `is_valid` and failed tests. The 9 conflicting rows are still flagged in `data_quality_flags`.
- Transparent handling of 2024 unknown-validity rows in `scripts/build_dashboard_combined.py`:
  - `failure` column now encodes `null` for rows where `is_failure` is unknown.
  - Added `Unknown` to the Compliance chip filter.
  - Compliance-rate KPI now excludes unknown-validity rows from the denominator and shows their count in the footnote.

### Results
- 2025 `other` bucket reduced from 23 rows to 4 rows (`الزيت القلي`, `ملحمة سماء القاهرة`).
- 2024 categories:
  - 7,920 rows mapped from GSO code (was 7,845).
  - 1,398 rows classified as swabs (was 1,471).
  - 83 rows with unknown validity are now explicitly flagged/filterable instead of being treated as compliant.
- Dashboard total unchanged at 20,880 (2024 = 9,316; 2025 = 11,564).
- 2025 failure count now driven by detected failed tests (3,038 failing samples).

### Files touched
- `microbiology/schemas/lab_data_2025_v1.yaml`
- `microbiology/scripts/clean_2025.py`
- `microbiology/scripts/enrich_gso.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/cleaned/data2024.parquet`
- `microbiology/cleaned/data2025.parquet`
- `microbiology/reports/microbiology_dashboard.html`
- `microbiology/reports/data2025_diff.md`
- `microbiology/reports/data2025_review.md`

### How to regenerate
```bash
cd microbiology
.venv/bin/python scripts/clean_2025.py "2025-original/Data 2025.xlsx" cleaned/data2025.parquet reports/data2025_diff.md
.venv/bin/python scripts/enrich_gso.py
.venv/bin/python scripts/build_dashboard_combined.py
```

## 2026-08-08 — fats_oils bucket, 2024 sample_id, official footnote, GSO audit card

### Problems addressed
- `الزيت القلي` had no appropriate `sample_type` bucket.
- `ملحمة سماء القاهرة` rows are environmental swabs collected from the shop, but were landing in `other`.
- 2024 `sample_id` was derived from `gso_code` (a product standard), not from the lab's sample identifier.
- Hardcoded 2024 official numbers in the dashboard conflicted with the cleaned data.
- 2025 Annual Report total (11,404) differed from the cleaned data (11,564) and needed investigation.
- GSO panel completeness and lab-vs-GSO disagreements were only visible in script logs, not in the dashboard.

### Changes
- Added `fats_oils` sample-type bucket in `schemas/lab_data_2025_v1.yaml` and `enrich_gso.py`:
  - Keywords: `oil`, `frying oil`, `زيت قلي`, `الزيت القلي`, `shortening`, `fat`, `دهن`, `سمن`, `margarine`, etc.
  - Bare `زيت` intentionally omitted to avoid misclassifying `زيتون` (olives).
- Added a manual override in `scripts/clean_2025.py` forcing `ملحمة سماء القاهرة` → `swab`.
- Added sample-name fallback in `scripts/clean_2025.py::classify_sample_type()` so rows with a missing category but a recognisable sample name (e.g. `سلطة بيقوقالو`, `شرائح طماطم`) still get bucketed.
- Switched 2024 `sample_id` to use `m_s_no` scoped by `source_file` in `scripts/clean_2024.py`:
  - Primary ID: `{source_file}_{m_s_no}`.
  - Fallback to `gso_code` when `m_s_no` is missing.
  - Fallback to `{source_file}_row{row_excel}` when both are missing.
- Replaced hardcoded 2024 official compliance numbers with `null` in `scripts/build_dashboard_combined.py`:
  - Footnote now shows "2024 official numbers pending reconciliation" instead of a conflicting percentage.
- Investigated 2025 Annual Report mismatch:
  - Private samples (`خاص`): 67.
  - Sector-tagged samples (`قطاع`): 505.
  - ID-collision disambiguation adds 22 rows (11 pairs).
  - Date range is fully within 2025.
  - No clear single exclusion rule reproduces 11,404; likely the report uses a different inclusion/exclusion rule (e.g. re-test handling) that Muhannad needs to confirm.
- Added a GSO 1016 audit card to the dashboard (`scripts/build_dashboard_combined.py`):
  - 2024 samples with GSO code, full panel count, incomplete panel count.
  - Lab-vs-GSO agreement/disagreement counts.

### Results
- 2025 `other` bucket reduced from 4 rows to **0 rows**.
- 2025 `fats_oils` bucket: 1 row (`الزيت القلي`).
- 2024 dashboard rows: **9,317** (was 9,316). The +1 row is a previously deduplicated distinct physical sample that now has its own `m_s_no`-based ID.
- Dashboard total: **20,881** (2024 = 9,317; 2025 = 11,564).
- 2024 GSO-mapped rows: 7,919.

### Files touched
- `microbiology/schemas/lab_data_2025_v1.yaml`
- `microbiology/scripts/clean_2025.py`
- `microbiology/scripts/clean_2024.py`
- `microbiology/scripts/enrich_gso.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/cleaned/data2024.parquet`
- `microbiology/cleaned/data2024_long.parquet`
- `microbiology/cleaned/data2025.parquet`
- `microbiology/reports/data2024_clean_report.md`
- `microbiology/reports/microbiology_dashboard.html`
- `microbiology/reports/data2025_diff.md`
- `microbiology/reports/data2025_review.md`

### How to regenerate
```bash
cd microbiology
.venv/bin/python scripts/clean_2024.py --year 2024
.venv/bin/python scripts/clean_2025.py "2025-original/Data 2025.xlsx" cleaned/data2025.parquet reports/data2025_diff.md
.venv/bin/python scripts/enrich_gso.py
.venv/bin/python scripts/build_dashboard_combined.py
```

### Push note
- Committed and pushed to `origin/main` with message `Microbiology data-quality fixes (kimi push)`.

### Next steps (not in this change)
- Confirm with Muhannad the exact rule behind the Annual Report 2025 sample count (11,404 vs 11,564).
- Once 2024 official numbers are reconciled, re-populate `OFFICIAL_COMPLIANCE[2024]`.
- Move to chemistry audit.

---

## 2026-08-08 — Microbiology sunburst interactives: readability, size, info

### What changed
- `microbiology/scripts/build_micro_sunburst.py` (Plotly) and
  `microbiology/scripts/build_micro_sunburst2.py` (D3 `sunburst-chart`):
  - Plate enlarged: Plotly dish `max-width` 760px → 920px; D3 SVG side cap
    720px → 880px and `#plate` min-height 560px → 640px.
  - Centre nucleus readout enlarged (val 23→27px Plotly / 21→25px D3,
    label 10→11px / 9→10px).
  - Specimen slip column widened 344px → 380px; slip typography bumped
    (title 16→17px, big count 30→32px, readout keys 10→10.5px,
    readout values 17→18px, organism rows 12.5→13px).
  - Plotly sunburst wedge labels 14px → 15px.
  - New **quick-stats strip** under the sub-heading on both pages, computed
    from the cleaned data at build time: total samples (20,881),
    non-compliant rate of known validity (28.1%), unknown-validity count (83),
    and top NC GSO category (Tomato Concentrates, Sauces, Vinegar, Spices and
    Herbs — 1,173).

### Verification
- Both builds print `root n=20881`, `unknown=83`, `NC=28.1% (known-validity
  only)` — unchanged and consistent with the main dashboard.
- No template placeholders left in the generated HTML.
- Extracted app JS passes `node --check` for both pages.

### Files touched
- `microbiology/scripts/build_micro_sunburst.py`
- `microbiology/scripts/build_micro_sunburst2.py`
- `microbiology/reports/microbiology_sunburst.html` (regenerated)
- `microbiology/reports/microbiology_sunburst2.html` (regenerated)

### How to regenerate
```bash
python3 microbiology/scripts/build_micro_sunburst.py
python3 microbiology/scripts/build_micro_sunburst2.py
```

---

## 2026-08-08 (2) — GSO panel-completeness: spelling aliases + systematic/sporadic split

### Background
The dashboard's "Incomplete GSO panel" card read 5,100 (65.0% of coded 2024
samples). Breakdown showed much of it was false: the GSO reference and the lab
sheets spell the same test differently, so a test that *was* run counted as
missing. User reviewed the full breakdown and approved three actions.

### What changed
1. **Test-name aliases** (`microbiology/scripts/enrich_gso.py`,
   `TEST_ALIAS_TO_CANONICAL`) — 7 additions, all user-approved:
   - `لستيريا` → `الليستيريا` (Listeria)
   - `L.monocytogenes` → `الليستيريا`
   - `خمائر` → `الخمائر والاعفان` (lab runs the combined yeasts & molds test)
   - `CAMPYLOPACTER` → `كامبيلوباكتر` (Campylobacter)
   - `باسلس سيرس` → `باصلص سيرز` (Bacillus cereus)
   - `Aeromonas spp` → `Aeromonas`
   - `P.aeruginosa` → `سيدومومناس` (bottled water: user confirmed the lab's
     Pseudomonas-genus test is the P. aeruginosa test)
2. **Systematic/sporadic split** (`microbiology/scripts/build_dashboard_combined.py`):
   new payload column `panel_gap_kind` (index 25). A missing test is
   *systematic* when the lab skips it for ≥90% of samples under the same GSO
   code (standing practice gap), else the sample's gap is *sporadic*. The
   "GSO 1016 audit" card now shows both counts under the incomplete total,
   with an updated explainer line.

### Results (2024, after re-running `enrich_gso.py`)
- Incomplete panels: **5,100 → 4,090** (−1,010 false flags cleared).
- Full panel run: 3,756 of 7,846 coded samples (47.9%, was 35.0%).
- Split: **1,756 systematic** (22.4% of coded) vs **2,334 sporadic** (29.7%).
- Biggest remaining systematic gaps: Listeria in cakes/bakery (I-9, 503) and
  Arabic sweets (L-9, 368); E. coli O157 + B. cereus + C. perfringens +
  Campylobacter in frozen poultry (C-9, 425); Listeria in cheese (A-13, 202).
- Dashboard totals unchanged: 20,881 rows (2024 = 9,317; 2025 = 11,564).

### Files touched
- `microbiology/scripts/enrich_gso.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/cleaned/data2024.parquet` (audit columns re-propagated)
- `microbiology/cleaned/data2024_long.parquet`
- `microbiology/cleaned/data2025.parquet` (stub columns re-written)
- `microbiology/reports/microbiology_dashboard.html` (regenerated)

### How to regenerate
```bash
python3 microbiology/scripts/enrich_gso.py
python3 microbiology/scripts/build_dashboard_combined.py
```

### Verification
- `enrich_gso.py` prints panel completeness 3,766/9,328 long-sample groups
  (wide merge: 4,090 incomplete of 7,846 coded).
- Dashboard app JS passes `node --check`; split counts reproduced
  independently from the wide parquet (systematic 1,756 + sporadic 2,334 = 4,090).

### Open decisions for Muhannad / the lab (not in this change)
- G-3 mayonnaise/sauces: C. perfringens run for only 271/1,185 samples
  (77% — classified sporadic, borderline systematic). Lab scope?
- J-1 precut produce: E. coli O157 run for 326/1,074, Listeria 637/1,074.
- P-2 sandwiches: total plate count never run (150).
- L-8 honey: sulphite-reducing anaerobes / C. botulinum never run.
- Whether any of these should be marked `optional: true` in
  `schemas/gso_1016_reference.yaml` (needs lab sign-off).

---

## 2026-08-08 (3) — Data-quality flags: ISO reclassify, H-code mapping, >10 ambiguity, spelling fixes

### Background
The dashboard's data-quality summary surfaced
`result_numeric_comparison_prefix:>` (6,599 samples),
`limit_numeric_comparison_prefix:<` (1,347) and
`gso_code_was_iso_placeholder` (1,327) as top flags. Investigation showed most
were not data errors. Four user-approved actions:

### What changed
1. **ISO placeholder reclassified** (`clean_2024.py`): all 1,328 "ISO"-coded
   samples are environmental swabs/equipment surfaces, tested under ISO
   methods — correctly outside GSO 1016 scope. Flag renamed from
   `gso_code_was_iso_placeholder` to informational `iso_method_outside_gso1016`.
2. **'H'-code mapping** (`clean_2024.py`): 'H' is not a GSO 1016 letter; the
   lab used it internally. Mapped by product name: cheddar (جبنة شيدر) →
   **A-13** (25 samples), ketchup (صوص كاتشب) → **G-2** (2), other sauces
   (صوص مايونيز/رانش…) → **G-3** (9). Traceable via new flag
   `gso_code_h_mapped_by_name`. These 36 samples now join the GSO audit.
3. **'>10' ambiguity handling** (`enrich_gso.py`): 14,120 result rows carry a
   `>10`/`<10` comparison prefix and 99.4% are lab-valid — the convention is
   unconfirmed (possible RTL flip of `<10`). Disagreements that hinge on a
   prefixed result are now recorded as `ambiguous_prefixed_result` instead of
   true disagreements. New wide column `gso_lab_vs_gso_ambiguous`; dashboard
   GSO-audit card shows "↳ ambiguous (>10 convention)" separately.
4. **Test-name spelling fixes** (`schemas/lab_data_2024_v2.yaml`):
   `كلوستريديوم بوتيلونيوم` → `كلوستريديوم بوتولينوم` (C. botulinum typo,
   22 rows); `Fecal Coliforms` → `Faecal Coliforms` (1 row; added to
   canonical list). `test_value_unrecognised` is now **0**.

### Results (2024, after full re-clean + re-enrich)
- Row counts reproduced exactly: long 36,461; wide 9,317; dashboard 20,881.
- Lab-vs-GSO: **80 disagreements → 51 true + 29 ambiguous** (row level:
  89 → 59 true + 30 ambiguous).
- GSO-coded samples: 7,846 → **7,882** (+36 H-mapped); incomplete panels
  4,090 → 4,126 (the 36 new coded samples mostly run incomplete panels).
- `gso_code_pattern_violation`: 119 → 83 long rows (H rows resolved).

### Files touched
- `microbiology/scripts/clean_2024.py`
- `microbiology/scripts/enrich_gso.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/schemas/lab_data_2024_v2.yaml`
- `microbiology/cleaned/data2024.parquet`, `data2024_long.parquet`, `data2025.parquet`
- `microbiology/reports/microbiology_dashboard.html`, `data2024_clean_report.md`

### How to regenerate
```bash
python3 microbiology/scripts/clean_2024.py --year 2024
python3 microbiology/scripts/enrich_gso.py
python3 microbiology/scripts/build_dashboard_combined.py
```

### Verification
- Row counts unchanged; `node --check` passes on dashboard app JS.
- All audit numbers independently recomputed from the wide parquet.

### Open question for the lab
- What does a `>10` result mean in the 2024 sheets (literal "above 10", or an
  RTL-flipped `<10` "below 10 = satisfactory")? The 29 ambiguous samples
  resolve to agree/disagree once confirmed.

---

## 2026-08-08 (4) — Landing-page chemistry cross + sunburst rebuild + handoff note

### What changed
- `build_landing.py`: chemistry plate ring is now greyed out
  (`grayscale(.75) opacity(.5)`) with a large **✕ cross** replacing the
  ornament, and the hover spin disabled. The three chemistry entries remain
  fully deactivated (no `href`, `pointer-events:none`) with
  "under construction · قيد الإنشاء" labels.
- Both microbiology sunbursts rebuilt on the refreshed parquets (post
  H-mapping / aliases / re-clean): totals re-verified — root n=20,881,
  unknown=83, NC=28.1% (known-validity only); app JS passes `node --check`.
- New consolidated handoff note: `kimi/yolo/HANDOFF_2026-08-08.md` (what
  changed, verified numbers, regeneration order, open items for Muhannad).

### Files touched
- `build_landing.py`, `index.html`
- `microbiology/reports/microbiology_sunburst.html` (regenerated)
- `microbiology/reports/microbiology_sunburst2.html` (regenerated)
- `kimi/yolo/HANDOFF_2026-08-08.md` (new)

---

## 2026-08-08 (5) — 2025 GSO code assignment by sample name (Tier 1 live)

### Background
The GSO audit card was 2024-only because the 2025 source carries no GSO code
column. User approved a two-tier name-based assignment plus a lab request for
2025 test-level data (the only route to true 2025 panel completeness — the
source records verdicts, not the tests run).

### What changed
1. **`enrich_gso.py` — `assign_2025_codes_by_name()`**: writes a `gso_code`
   column into the 2025 wide parquet before `enrich_wide`.
   - *Tier 1 (live)*: unambiguous normalised name→code pairs learned from the
     2024 long parquet (digits stripped, ة/ه and أ/إ/آ unified both sides).
   - *Tier 2*: `NAME_TO_CODE_2025` curated-override dict — empty pending
     review sign-off (`kimi/yolo/2025_gso_code_name_review.md`).
   - Assigned rows flagged `gso_code_assigned_by_name`; idempotent (recomputed
     each run).
   - `enrich_wide(..., derive_categories=False)` for 2025: uncoded 2025 rows
     keep their cleaner categories instead of being mislabeled swabs.
2. **Dashboard GSO-audit card**: new "2025 samples with GSO code" card
   (name-assigned) + explainer rewritten to state that panel metrics stay
   2024-only until the lab provides test-level data.
3. **`kimi/yolo/muhannad_open_questions.md`**: new item 3.3 requesting the
   2025 test-level export (sample ID · test · result · limit · verdict).

### Results (verified)
- 2025 coded: **4,263 / 11,564 (36.9%)** — all flagged `gso_code_assigned_by_name`.
- 2025 cleaner categories intact (no swab mislabeling).
- 2024 metrics unchanged: coded 7,950; incomplete panel 4,126; disagree 51;
  ambiguous 29. Dashboard 20,881 rows; app JS passes `node --check`.

### Files touched
- `microbiology/scripts/enrich_gso.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/cleaned/data2025.parquet`
- `microbiology/reports/microbiology_dashboard.html` (regenerated)
- `kimi/yolo/2025_gso_code_name_review.md` (new — awaiting user mark-up)
- `kimi/yolo/muhannad_open_questions.md` (item 3.3 added)

### Next step
User marks up the Tier 2 review doc → fill `NAME_TO_CODE_2025` → re-run
`enrich_gso.py` + dashboard → 2025 coverage rises toward ~49%.

---

## 2026-08-09 — `>10` convention confirmed by MR: below-limit = pass

### What changed
MR confirmed the 2024 sheets' `>10` results are a data-entry flip of
`أقل من 10` — they mean **below the reporting limit**, i.e. satisfactory /
pass. `enrich_gso.py` now evaluates any comparison-prefixed result
(`>10` / `<10` / `≥` / `≤`) as **0 (non-detect)** in the
validity-vs-GSO-limit cross-check. The `ambiguous_prefixed_result` category
introduced 2026-08-08 is retired: the `gso_lab_vs_gso_ambiguous` column and
its dashboard card are removed, and the explainer text now states the
confirmed convention.

### Results (verified against parquets)
- Row level: 30 ambiguous → **27 agree + 3 lab_says_fail_should_pass**.
  Decisions now: agree 18,194 · lab_says_pass_should_fail 48 ·
  lab_says_fail_should_pass 14 (was 89 disagreement/ambiguous → 62 true).
- Sample level: lab-vs-GSO disagreements **51 true + 29 ambiguous → 54 final**.
- Everything else unchanged: 20,881 rows (9,317 / 11,564); panel incomplete
  4,126; 2025 name-assigned codes 4,263; app JS passes `node --check`.

### Files touched
- `microbiology/scripts/enrich_gso.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/cleaned/data2024.parquet`, `data2024_long.parquet`, `data2025.parquet`
- `microbiology/reports/microbiology_dashboard.html` (regenerated)

### Closes
- MR review item **B1** (`kimi/yolo/MR_REVIEW_REQUEST.md`) — answered and applied.

---

## 2026-08-09 (2) — MR confirms 'H'-code handling: ignore H, categorize by name

MR answered review item **B2**: ignore the `H` code and categorize those 36
samples by product name. This matches the mapping already applied in
`clean_2024.py` (cheddar → A-13 ×25, ketchup → G-2 ×2, other sauces → G-3 ×9,
flag `gso_code_h_mapped_by_name`), so no code or data change was required —
the item is closed in `kimi/yolo/MR_REVIEW_REQUEST.md` and
`muhannad_open_questions.md`. Milestones 1–2 of the 100% checklist are done;
remaining MR items: B3 (panel scope), B4 (2025 report rule), B5 (2024
official totals), B6 (2025 test-level export), B7 (Tier 2 name mark-up).

---

## 2026-08-09 (3) — Sunburst rebuild (stale after >10 fix) + Tier-1b spelling-variant audit

### Sunbursts
`microbiology_sunburst.html` / `microbiology_sunburst2.html` were still built from
the pre-`>10`-fix parquets (2026-08-08 23:04 vs parquets 2026-08-09 18:02).
Rebuilt both; verified: root n=20,881 · unknown-validity 83 · overall NC=28.1%
(known-validity only) · 454 nodes.

### Audit sweep (no data changes)
Fresh gap sweep of the cleaned parquets. Clean: no duplicate sample_ids, no
facility-name collisions, no 2025 `other` bucket. Findings written to
`kimi/yolo/2025_gso_tier1b_spelling_variants.md` for user decision:
- **Group A:** 346 uncoded 2025 names (547 rows) are spelling variants of
  singly-coded names → proposed Tier-1b auto-assign (would lift 2025 coded
  coverage from 36.9% to ~41.6%). ~8 false-friend matches flagged for exclusion.
- **Group B:** 88 names (864 rows) map to names carrying multiple 2024 codes —
  needs disambiguation (overlaps MR item B7).
- **Group C:** 9 rows (7 in 2025 + 2 in 2024) typed `swab` with food/drink
  names and GSO codes — swab-vs-food contradiction awaiting user ruling.
- **Minor:** 2024 `other` bucket = 183 rows (jams 120, halawa/tahini misc 53,
  infant 10); optional re-bucketing proposed, not applied.

### Files touched
- `microbiology/reports/microbiology_sunburst.html`, `microbiology_sunburst2.html` (regenerated)
- `kimi/yolo/2025_gso_tier1b_spelling_variants.md` (new report)

---

## 2026-08-11 — Dashboard audit after tabbed redesign: GSO-tab accuracy fixes

Audited `microbiology_dashboard.html` after the Claude tabbed redesign +
GSO rule reclassification (commits through 9188995). JS valid, markup
balanced, filters/tabs/hash-sync/drill-downs all sound; payload matches the
parquets (20,881 = 9,317 + 11,564; unknown validity 83; NC 28.1%;
2025 coded now 6,139 = 53.1% after the rule layer; rule tests green).
Three accuracy bugs found and fixed in `build_dashboard_combined.py`:

1. **Systematic/sporadic panel-gap split was broken** (regression). The
   ≥90% skip-rate denominators counted 2025 rule-coded rows, which have no
   test records — flipping nearly all systematic gaps to sporadic
   (14 / 4,112 shown). Restricted the computation to 2024 rows →
   **systematic 1,758 · sporadic 2,368** (of 4,126 incomplete panels).
2. **"Lab vs GSO agrees" counted uncoded samples.** The audit set was all
   9,317 2024 rows; uncoded rows default to agree. Now restricted to coded
   rows → **agree 7,896 · disagree 54** of 7,950 audited.
3. **"2024 samples with GSO code" card showed 7,882** (panel-evaluated rows)
   instead of the true coded count. Now shows **7,950** with a sub-note:
   "panel evaluated for 7,882 · no test records for 68".

Not a bug (verified consistent): dashboard KPIs and both sunbursts all use
`is_failure` (NC 5,852), which counts the 8 flagged
`validity_says_valid_but_has_failures` 2025 rows as non-compliant;
`is_valid` (5,845) is the source-verdict column. Both round to NC 28.1%.

### Files touched
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/reports/microbiology_dashboard.html` (regenerated, JS `node --check` OK)

---

## 2026-08-11 (2) — Dashboard polish: GSO table Codes column + panel-card wording

Two small accuracy enhancements to the GSO tab (user direction: dashboard only):

1. **GSO categories table "Code" column was misleading** — it showed the
   first row's code for each category, but a GSO category spans many codes.
   The column now shows the **distinct-code count** per category (e.g.
   "18 codes"), '—' when uncoded, and sorts numerically.
2. **Panel-card sub-labels said "% of coded"** but the denominator is the
   panel-*evaluated* subset (7,882 of 7,950 coded; 68 coded samples have no
   test records). Subs now read "% of evaluated" to match the number shown.

Dashboard rebuilt: 20,881 rows (9,317 + 11,564), JS `node --check` OK.

### Files touched
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/reports/microbiology_dashboard.html` (regenerated)
