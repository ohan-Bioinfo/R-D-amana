# Microbiology data-quality audit report

**Date:** 2026-08-08  
**Scope:** 2024 + 2025 microbiology cleaned data and dashboard  
**Total samples:** 20,881 (2024 = 9,317; 2025 = 11,564)

---

## 1. What was fixed

### 1.1 2025 sample-type buckets
The dashboard/parquet `sample_type` bucket list in `microbiology/schemas/lab_data_2025_v1.yaml` was missing keywords that exist in the data. After adding them, the `other` bucket dropped from **23 rows to 0 rows**.

| Bucket | Keywords added (selection) |
|---|---|
| `produce` | okra / بامية, ملوخية, berries, avocado / افوكادو, celery, peaches, grapes / عنب, guava / جوافة, radish / فجل, tabbouleh / تبولة, pine / الصنوبر, mango / مانجا |
| `dairy` | dairy, halloumi / حلومي, cheddar / شيدر, ايسكريم |
| `prepared_meal` | محاشي, kofta / كفتة, kibbeh / كبة, ايدام, مصقع, مشكل, barbecue / باربكيو |
| `sauce_condiment` | shira / شيرة, تتبيلة, بابا غنوج |
| `sweets_bakery` | تراميسو / tiramisu, كريم كراميل / كاراميل, waffle / وافل, بيتي فور, chips, شبس, فشار, popcorn, مهلبية / mahalibah, حلا |
| `cereals` | شابورة / شابورا |
| `cooked_meat_poultry` | turkey / ديك رومي |
| `fats_oils` | oil, frying oil, زيت قلي, fat, دهن, سمن, margarine, etc. (bare `زيت` deliberately excluded to keep olives in `produce`) |

*Implementation notes:*
- An early `sweets_bakery` catch was inserted before `produce` so `popcorn`/`فشار`/`chips` are not captured by `produce`'s broad `corn` keyword.
- `classify_sample_type()` now falls back to `sample_name` when the category fields are missing, so rows like `سلطة بيقوقالو` and `شرائح طماطم` are still bucketed.
- A manual override forces `ملحمة سماء القاهرة` → `swab` because those rows are environmental swabs collected from the shop.

The same keyword set was mirrored in `microbiology/scripts/enrich_gso.py::SAMPLE_TYPE_KEYWORDS` so 2024 GSO-derived categories classify consistently.

### 1.2 2024 placeholder GSO codes
`microbiology/scripts/enrich_gso.py` builds a `sample_name → canonical gso_code` lookup from valid 2024 rows and applies it to rows whose raw `gso_code` is present but un-normalisable (placeholders such as `H`, `1`, `31`, `124`).

- **73 food-product rows recovered** and reclassified out of `swab`.
- **64 rows remain as swabs** — most are environmental/hygiene samples (`مسحة …`) and legitimately have no GSO code.

Resulting 2024 category split:

| Category source | Count |
|---|---|
| Mapped from GSO code | 7,919 |
| Classified as swabs | 1,398 |
| Unknown validity | 83 |
| **Total** | **9,317** |

### 1.3 2024 sample_id now uses m_s_no
`microbiology/scripts/clean_2024.py` no longer uses `gso_code` as the sample identifier. The wide parquet now uses:

- Primary ID: `{source_file}_{m_s_no}`
- Fallback to `gso_code` when `m_s_no` is missing.
- Fallback to `{source_file}_row{row_excel}` when both are missing.

This makes 2024 IDs consistent with the 2025 style and fixes cross-year repeat-offender / chain logic. One previously-deduplicated distinct physical sample is now retained, so 2024 grew from **9,316 → 9,317 rows**.

### 1.4 2025 validity conflicts — Option A
There are 9 rows in 2025 where `is_valid` and `invalid_tests` disagree. Per the agreed Option A, the objective test-result list is trusted. `microbiology/scripts/clean_2025.py` now defines:

```python
is_failure = (n_failed_tests > 0)
```

The 9 rows are still flagged in `data_quality_flags` (`validity_says_valid_but_has_failures` / `validity_says_invalid_but_no_failures`) for audit traceability.

### 1.5 2024 unknown-validity rows
83 rows in 2024 have `is_valid = NA`/`is_failure = NA`. They are no longer silently treated as compliant:

- `microbiology/scripts/build_dashboard_combined.py` now encodes `failure = null` for these rows.
- A new **Unknown** option was added to the dashboard Compliance chip filter.
- The compliance-rate KPI excludes unknown-validity rows from the denominator and shows their count in the footnote.

### 1.6 GSO 1016 audit exposed in dashboard
A new dashboard card shows:

- 2024 samples with a GSO code.
- Count / percentage with the full required GSO panel run.
- Count / percentage with incomplete panels.
- Lab-vs-GSO agreement and disagreement counts.

### 1.7 2024 official numbers footnote
Hardcoded 2024 official counts in `scripts/build_dashboard_combined.py` were replaced with `null`. The footnote now says **"2024 official numbers pending reconciliation"** instead of showing a percentage that conflicts with the cleaned data.

### 1.8 Facility-chain spelling normalisation
`scripts/clean_2025.py` now applies substring replacements to facility names before splitting chain/branch. This merges spelling variants that were fragmenting chain-level aggregations.

- Example: `صب وأي` → `صب واي` (Subway).
- Result: **68 rows** now roll up under a single `صب واي` chain (previously split between two spellings).

### 1.9 English labels for Arabic-only categories
Many 2025 `category_canonical` values are Arabic-only and had no English label, leaving **383 rows** with `category_en = NA`.

`scripts/clean_2025.py` now uses a `CATEGORY_EN_FALLBACK` lookup for common Arabic-only categories (e.g. `الخضار المشوية و المطبوخة` → `cooked and grilled vegetables`, `طحينة` → `tahini`, `الزيت القلي` → `used frying oil`, swab labels, fish types, desserts, etc.).

- Result: `category_en` missing dropped from **383 → 129 rows**.
- The remaining 129 are mostly unique/free-text sample names (e.g. `Soup (all kinds) Samosa, Mashed potato, Desserts.`, `Pasteurized fruit juice and drink`) that do not map to a recurring Arabic category.

### 1.10 Data-quality summary in dashboard
`scripts/build_dashboard_combined.py` now exposes a **Data-quality summary** KPI card (`#data_quality_summary`) showing counts of key quality flags:

- Sample-ID collisions.
- Validity conflicts.
- Date-parsed-from-text.
- Category merges.
- Municipality placeholders.

### 1.11 Sample-type distribution chart
A new grouped bar chart (`#chart_sample_type`, `renderSampleTypeDistribution`) shows the 2024 vs 2025 `sample_type` breakdown side-by-side, making bucket shifts visible.

### 1.12 Dashboard filter / chart / labelling audit
A focused pass was run to verify every filter control is wired and every chart label is readable.

| Issue found | Fix |
|---|---|
| **Reset button deactivated the wrong toggles.** `btn_reset` was clearing the `.active` class from *all* `.toggle` elements, including the map metric (`% non-compliance` / `% pathogen` / `Total samples`) and map tile (`Light` / `Streets` / `Dark`) view controls, without resetting their underlying state variables. | Reset now calls `syncAllChips()` and only touches the filter chips and the three filter toggles (`Pathogen only`, `Repeat offender`, `Exclude meat & poultry`). |
| **Severity filter chips showed raw codes** (`indicator_only`, `pathogen`, `multi_pathogen`). | Added `SEVERITY_LABEL` map and a `labelMap` option to `buildChips()`; chips now display "Indicator only", "Pathogen", "Multi-pathogen". |
| **Severity chart axes/legends showed raw codes** in `renderSeverityMonth`, `renderYoY`, and `renderHeatmap`. | Charts now use `SEVERITY_LABEL` for display labels; `crossFilter()` resolves a clicked label back to the raw state value via `LABEL_TO_RAW`. |
| **Sample-type distribution chart showed raw codes** (`produce`, `dairy`, etc.) on the x-axis. | Added `SAMPLE_TYPE_LABEL` map and sorted types by total count; x-axis now shows readable labels ("Fruit & Vegetables", "Dairy", etc.). |
| **Data-quality summary under-counted `Unknown validity` and `Missing facility name`.** They were only counted for rows that also had `dq_flags`. | Moved both counts outside the flag-only loop; facility card is restricted to 2025 because 2024 source lacks facility data. |

### 1.13 Verified dashboard wiring
- All declared filter containers (`f_year`, `f_compliance`, `f_severity`, `f_sector`, `f_gso_category`, `f_microbe`, date range, quick toggles) are built and have event listeners.
- All chart containers (`chart_*`) have matching render functions and are called from `renderAll()`.
- `node --check` on the extracted dashboard JavaScript passes with no syntax errors.

### 1.14 Sunburst dashboards rebuilt with correct non-compliance denominator
Both `microbiology_sunburst.html` and `microbiology_sunburst2.html` were rebuilt from the latest cleaned parquet files.

| Fix | Detail |
|---|---|
| Unknown-validity rows treated consistently | 83 rows in 2024 with `is_failure = NaN/None` previously fell into the "✓ Compliant" leaf, lowering the true non-compliance rate. They now get their own **"Unknown validity"** leaf. |
| Non-compliance % now matches the main dashboard | Denominator for `% contaminated` and `% pathogen` is `n - unknown` (known-validity rows only). |
| New readout card | Each sunburst slip now shows **Compliant / Non-compliant / Unknown validity / % contaminated / % pathogen**. |
| Rebuilt counts | Total = **20,881**; unknown = **83**; overall NC = **28.1%** (known-validity only), matching the Plotly dashboard. |

### 1.15 Cross-dashboard consistency check
| Dashboard | Total | Unknown validity | NC rate (known-only) |
|---|---|---|---|
| Plotly (`microbiology_dashboard.html`) | 20,881 | 83 | 28.14% |
| Sunburst 1 (`microbiology_sunburst.html`) | 20,881 | 83 | 28.1% |
| Sunburst 2 (`microbiology_sunburst2.html`) | 20,881 | 83 | 28.1% |

---

## 2. Remaining gaps / items for decision

### 2.1 2025 Annual Report headline mismatch
The cleaned 2025 file contains **11,564 samples**; the Annual Report states **11,404** (difference = **+160**). Investigation found:

- Private samples (`خاص`): 67.
- Sector-tagged samples (`قطاع`): 505.
- ID-collision disambiguation adds 22 rows (11 pairs with `-a`/`-b` suffixes).
- Date range is fully within 2025.
- No single exclusion rule among the obvious candidates reproduces 11,404.

**Next step:** confirm with Muhannad/the lab what rule the Annual Report uses (e.g. re-test handling, private/sector inclusion).

### 2.2 2024 official numbers
Once the Annual Report inclusion rule is confirmed, update `OFFICIAL_COMPLIANCE[2024]` in `scripts/build_dashboard_combined.py`.

### 2.3 Chemistry dashboard
The chemistry files have not yet been audited. Re-use the same explore → report → fix → regenerate pattern.

---

## 3. Files changed

- `microbiology/schemas/lab_data_2025_v1.yaml`
- `microbiology/scripts/clean_2025.py`
- `microbiology/scripts/clean_2024.py`
- `microbiology/scripts/enrich_gso.py`
- `microbiology/scripts/build_dashboard_combined.py`
- `microbiology/scripts/build_micro_sunburst.py`
- `microbiology/scripts/build_micro_sunburst2.py`
- `microbiology/cleaned/data2024.parquet`
- `microbiology/cleaned/data2024_long.parquet`
- `microbiology/cleaned/data2025.parquet`
- `microbiology/reports/data2024_clean_report.md`
- `microbiology/reports/microbiology_dashboard.html`
- `microbiology/reports/microbiology_sunburst.html`
- `microbiology/reports/microbiology_sunburst2.html`
- `microbiology/reports/data2025_diff.md`
- `microbiology/reports/data2025_review.md`
- `kimi/yolo/microbiology_audit_report.md`
- `kimi/yolo/microbiology_remaining_gaps_and_suggestions.md`
- `microbiology/CHANGELOG.md`

---

## 4. How to regenerate

```bash
cd microbiology
.venv/bin/python scripts/clean_2024.py --year 2024
.venv/bin/python scripts/clean_2025.py "2025-original/Data 2025.xlsx" cleaned/data2025.parquet reports/data2025_diff.md
.venv/bin/python scripts/enrich_gso.py
.venv/bin/python scripts/build_dashboard_combined.py
```

---

## 5. Quick verification

```python
import pandas as pd
df24 = pd.read_parquet('microbiology/cleaned/data2024.parquet')
df25 = pd.read_parquet('microbiology/cleaned/data2025.parquet')

assert len(df24) == 9317
assert len(df25) == 11564
assert df25['sample_type'].value_counts().get('other', 0) == 0
assert df25['category_en'].isna().sum() == 129
assert df25[df25['facility_chain'] == 'صب واي'].shape[0] == 68
assert df24['gso_code_canonical'].notna().sum() == 7919
assert df24['is_valid'].isna().sum() == 83
assert df24['sample_id'].isna().sum() == 0
```

*Report generated by Kimi Code — changes are logged in `microbiology/CHANGELOG.md`.*
