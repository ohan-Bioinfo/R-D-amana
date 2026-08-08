# Microbiology Changelog

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
