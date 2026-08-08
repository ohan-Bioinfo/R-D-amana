# Microbiology Changelog

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
