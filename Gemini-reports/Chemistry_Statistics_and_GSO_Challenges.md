# Chemistry Statistics, GSO Mapping Challenges, & Numerical Ledger

This report reviews the challenges encountered across the **chemistry** data
pipeline — the sibling of the microbiology review. It covers the pipeline stages,
GSO 1016 categorization, the five-way validity model unique to analytical
chemistry, data-cleaning edge cases, and an exhaustive numerical ledger. All
counts are drawn from the current 14 parquets and the dashboard payload
(2026-08-11) and are row-for-row verified against the raw xlsx.

## 1. Stages of the Chemistry Data Pipeline

The pipeline transforms eight streams of raw analytical lab data into one
deterministic dataset. The whole build regenerates byte-identical in ~30 seconds
and runs on the microbiology virtual-env (no chemistry-local venv).

1. **Ingestion (`raw/{2024,2025}/*.xlsx`):** Section-driven read of monthly (or
   single-sheet) workbooks. Sheets named `final*`, `invalid samples`, `study`,
   `edited`, or year-impure tabs are skipped; a sheet needs ≥2 rows and ≥3
   columns.
2. **Cleaning & header mapping (`clean_chemistry.py`):** Bilingual header alias
   matching, paired result/limit/QC columns, `parse_date()` anomaly coercion,
   `normalise_sample_id()` (`Mango-0004-R01` → `mango-0004-r01`).
3. **Validity judgment (`map_validity()`, `derive_test_result()`):** Map the
   lab's verdict, or derive one from exceeded-limit counts and verdict text, then
   classify into `validity_status`.
4. **Categorization & GSO mapping (`categories.py`, `sectors.py`):** A 7-tier
   category resolver, and a 26-sub-municipality → 5-sector amanah map.
5. **Deliverables (`build_dashboard.py`, `build_chem_sunburst.py`):** A
   self-contained 5-tab dashboard and a zoomable assay-plate sunburst, plus
   per-section `.md` audit summaries.

## 2. GSO Classification & Categorization Challenges

Mapping a free-text Arabic sample name to a strict GSO 1016 category — across
eight chemically distinct sections — carries different traps from the
microbiology sauce/swab problem.

### A. Multilingual & Misspelled Raw Categories
The lab enters `sample_category` in Arabic with drifting spelling: `لوز` vs
`اللوز` (almond), `فستق` vs `فسطق` (pistachio), and misspelled ID prefixes
(`uu-pe`, `oau-da`). `categories.classify()` resolves this with a **7-tier
chain**: per-sample corrections → product-name overrides → sample-ID prefix
decode → water sub-detection → 130+ name keywords → raw-category keywords →
section default.

### B. Ambiguous Prefixes & Hand-Audited Corrections
A prefix like `pe` could mean peanut (`فول سوداني`) or pepper (`فلفل`) — so
ambiguous prefixes are deliberately omitted from the decode table and left to the
keyword tier. Where rules cannot be trusted, Muhannad's sheet-8 audit column
(`التصنيف الصحيح`) feeds `category_corrections.csv` (~2,400 rows), which **wins
over every rule**.

### C. Mid-Pipeline Reclassifications (2026-07)
Nine product groups were re-homed after review: **nuts** (`لوز/فستق/كاجو`)
moved from cereals → sweets/chocolate; **pepper** and **dried onion** moved from
spices → fruit & vegetables; **raisins, salad, chips** → fruit & veg; **sesame**
isolated to "miscellaneous foods" while tahini stays a spice; and a new
**non-potable water** class was created for `حوض/راكد/متحرك` samples.

### D. Section-Specific Short-Circuits
- **Jam:** entirely jam/jelly, so fruit-flavour keywords (`توت/مشمش`) must not
  misroute it — the classifier forces the jam section to `المربى والجلي` before
  any keyword runs.
- **Water:** every potable variant (`مياه/مياة/موية`) folds to one class; only
  `حوض/راكد/متحرك` stays non-potable.
- **Sectors:** private samples (`عينة خاصة`, `private`) are flagged and their
  municipality cleared; spelling aliases (`الشفاء`→`الشفا`, `لعليا`→`العليا`) are
  normalised before the 5-sector map.

## 3. Data Quality & Statistical Challenges

### A. The Five Validity States
Unlike a binary pass/fail, a chemistry result is only judgeable when a regulatory
*limit* exists for it, so samples land in one of five `validity_status` states:

| Status | Meaning | Count |
|---|---|---:|
| valid | `is_valid == True` (lab-entered or derived) | 14,677 |
| invalid | `is_valid == False` — a test exceeded its limit | 1,101 |
| no_limit | Result present but no regulatory limit | 92 |
| rejected | Lab marked `مرفوض` / unfit for analysis | 4 |
| unknown | `is_valid is None`, no actionable signal | 2 |

### B. "No Limit" Semantics & Non-Detects
In a **result** column, `N.D` parses to `(0.0, is_nd=True)` — not detected. In a
**limit** column, `N.D` parses to `None` — the limit is *unset*, never 0.0 (which
would falsely flag every trace as an exceedance). **Jam 2024** is the extreme
case: 82 of 83 rows carry analytes with no regulatory limit, so only one row is
judgeable.

### C. Pesticides Long-Format Explosion
Pesticides arrive one row **per detected analyte**; sample metadata appears only
on the first row and is forward-filled onto continuation rows. The dashboard
therefore counts **15,876 rows** while the sunburst collapses pesticides to
**15,297 unique samples** — a +579-row difference. Confusing the two denominators
is the easiest way to misstate the non-compliance rate.

### D. Comparison Prefixes
Results like `>10`, `<5`, `≤0.01`, `≥100` are stripped before numeric parse
(`parse_nd_to_float()`); the prefix is discarded, not stored.

### E. Date Anomalies (Year-Purity Guard)
Stray 2026 tabs appear inside some 2025 workbooks. `parse_date()` tries multiple
formats; if the sampling-date year exceeds the file year, the row is dropped with
a `date_after_file_year` flag.

### F. Header Leaks & Duplicate Handling
Pasted header rows (containing `Sample ID` / `رمز العينة`) are discarded.
Intra-sheet duplicates are removed with section-specific keys — pesticides on
`(sheet, sample_id, pesticide_name, conc)`, others on `(sheet, sample_id)`.

### G. FALSE-Token-First Validity Mapping
`map_validity()` tests FALSE tokens **before** TRUE, because `غير مطابق`
(non-compliant) contains `مطابق` (compliant) as a substring. It also recognises
typos (`مطايق`, `invaild`) and non-verdict markers (`مرفوض` → rejected).

### H. Year-over-Year Failure Spikes ⚠️
Two sections roughly doubled their invalid rate in 2025: heavy_metals
**4.1% → 16.1% (+12.0 pp)** and pesticides **8.3% → 16.9% (+8.5 pp)**. This may
reflect (a) methodology/limit changes, (b) better detection, or (c) a real
contamination spike — confirm with the lab before reading it as a trend.

## 4. Comprehensive Numerical Ledger

### 4.1 Master Dataset Counts

| Metric | Count |
|---|---:|
| Total cleaned samples | 15,876 |
| 2024 samples | 6,441 |
| 2025 samples | 9,435 |
| Unique samples (pesticides collapsed) | 15,297 |
| Parquet files (8 × 2 − 2) | 14 |
| Category corrections (hand-audited) | ~2,400 |

### 4.2 Per-Section Sample Counts

| Section | Total | Years |
|---|---:|---|
| food_chemistry | 7,000 | 2024 + 2025 |
| pesticides | 4,701 | 2024 + 2025 |
| aflatoxins | 2,269 | 2024 + 2025 |
| heavy_metals | 1,138 | 2024 + 2025 |
| water_analysis | 606 | 2024 + 2025 |
| jam | 83 | 2024 only |
| honey | 70 | 2024 + 2025 |
| hormones_antibiotics | 9 | 2025 only |
| **Total** | **15,876** | — |

### 4.3 Sample Validity Distribution

| Metric | Count |
|---|---:|
| Valid | 14,677 |
| Invalid | 1,101 |
| No limit | 92 |
| Rejected | 4 |
| Unknown | 2 |
| **Overall NC rate (evaluated)** | **6.98%** |

### 4.4 Test-Level Ledger

| Metric | Count |
|---|---:|
| Distinct test results | 1,133,621 |
| — 2024 | 634,978 |
| — 2025 | 498,643 |
| Compliant tests | 1,131,632 |
| Non-compliant tests | 1,243 |
| Not evaluated (no limit) | 746 |

### 4.5 GSO 1016 Coverage (15 categories)

| GSO Category | Samples |
|---|---:|
| Fruit and Vegetables | 7,257 |
| Cereals; Legumes and their Products | 3,293 |
| Chocolate, Sweets and their Ingredients | 1,601 |
| Tomato Concentrates, Sauces, Vinegar, Spices & Herbs | 1,529 |
| Drinking Water | 1,051 |
| Meat, Poultry and its Products | 427 |
| Miscellaneous Foods | 273 |
| Fish and Shellfish and their Products | 167 |
| Jelly, Jam and Marmalade | 99 |
| Dairy Products | 57 |
| Animal Feed | 53 |
| Beverages | 40 |
| Non-potable Water | 23 |
| Fats and Oils | 4 |
| Ready to Eat Foods | 2 |

### 4.6 Data-Quality Guards

| Guard | What it catches |
|---|---|
| Year-purity guard | Stray 2026 tabs inside 2025 workbooks |
| Header-leak drop | Pasted header rows (`Sample ID` / `رمز العينة`) |
| Intra-sheet dedup | Repeated samples within a sheet |
| FALSE-token-first validity | `غير مطابق` not misread as `مطابق` |
| Water red-cell recovery (2024) | Failed tests read from red cell fills |
