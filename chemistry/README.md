# Riyadh Chemistry Lab — v2 Pipeline (2024 + 2025)

Fresh start (2026-06-04) on the chemistry pipeline using the lab's "updated"
xlsx files. The previous pipeline was discarded per user request; v2 covers
**2024 + 2025** across 7 analytical sections, with **Honey** as a 2025-only
new section.

## Status

- **16,069 rows total** across 7 sections × 2 years = 12 parquets
  (Honey + Hormones are 2025-only)
- 99–100% sample_id coverage
- **Row-for-row verified** against raw xlsx
- Dashboard: `reports/chemistry_dashboard.html` (3.7 MB, with year filter)

### Per-section row counts

| Section | 2024 | 2025 | T/F/Unknown (2024) | T/F/Unknown (2025) |
|---|---:|---:|---|---|
| aflatoxins | 1,122 | 1,157 | 891 / 12 / 219 | 1,151 / 6 / 0 |
| food_chemistry | 2,815 | 4,230 | 2,651 / 137 / 27 | 3,881 / 19 / 330 |
| heavy_metals | 220 | 924 | 207 / 9 / 4 | 768 / 148 / 8 |
| honey **(new)** | — | 46 | — | 31 / 15 / 0 |
| hormones_antibiotics | — | 9 | — | 9 / 0 / 0 |
| pesticides | 1,957 | 2,748 | 1,788 / 163 / 6 | 2,285 / 462 / 1 |
| water_analysis | 249 | 592 | 203 / 46 / 0 | 491 / 101 / 0 |
| **Total** | **6,363** | **9,706** | | **grand total 16,069** |

### Year-over-year invalid-rate delta (concerning trends ⚠️)

| Section | 2024 fail % | 2025 fail % | Δ |
|---|---:|---:|---:|
| aflatoxins | 1.1% | 0.5% | −0.6 pp ✓ |
| food_chemistry | 4.9% | 0.4% | −4.4 pp ✓ |
| heavy_metals | 4.1% | **16.0%** | **+11.9 pp** ⚠️ |
| pesticides | 8.3% | **16.8%** | **+8.5 pp** ⚠️ |
| water_analysis | 18.5% | 17.1% | −1.4 pp |

Heavy metals and pesticides failure rates roughly doubled year-over-year —
worth confirming with the lab whether this reflects (a) methodology / limit
changes, (b) better detection, or (c) real contamination spike.

## Layout

```
chemistry/
├── raw/                  7 xlsx source files (6 from 'updated chemistry data' + water from prior set)
├── schemas/              chem_<section>.yaml × 7
├── scripts/
│   ├── _common.py        shared utilities (text normalisation, sample-ID, sheet iteration)
│   ├── clean_chemistry.py  generic schema-driven cleaner
│   └── build_dashboard.py
├── cleaned/              chem_<section>_2025.parquet × 7
└── reports/
    ├── chem_<section>_2025.md  per-section audit summary
    └── chemistry_dashboard.html
```

## Pipeline

```bash
# Clean every section
.venv/bin/python scripts/clean_chemistry.py --section all

# Clean one section (debugging)
.venv/bin/python scripts/clean_chemistry.py --section heavy_metals

# Rebuild dashboard
.venv/bin/python scripts/build_dashboard.py
```

The venv is shared with the microbiology workstream at `food_analysis/Iter-2/.venv/`.

## Duplicates and header-leak guards

The cleaner enforces two row-level dedup rules to handle known source-xlsx
artifacts:

**Header-leak guard** — the lab occasionally pasted the header row into the
data range. Rows where `sample_id` literally contains `"Sample ID"` or
`"رمز العينة"` are dropped (10 such rows in water_analysis 2025 June-25).

**Intra-sheet deduplication** — drops repeated rows within the same sheet.
Dedup key:
- pesticides (long-format): `(sheet, sample_id, pesticide_name, concentration_ppm)`
- all other sections: `(sheet, sample_id)`

This caught **261 duplicate rows** across the source xlsx, most concentrated
in water_analysis 2025 June-25 (the lab copy-pasted the same 43 samples up
to 10 times each in the source). Other small dedups in food_chemistry 2024
(15 rows), food_chemistry 2025 (7), heavy_metals_2025 (3), and trace amounts
in aflatoxins/pesticides.

After dedup: total cleaned rows went from 16,069 → **15,807** (−262 rows, −1.6%).
Verification: `df.duplicated(subset=key_cols)` returns 0 for every section.

## Hidden rows and Excel autofilters

**The cleaner intentionally ignores Excel's autofilter and `row.hidden` flags.**
Many of the lab's xlsx files have autofilters applied (63 sheets observed) and
some rows marked `hidden=True` (670 across all files, e.g. 249 in pesticide
Oct-2025, ~100 in water 2024 sheets, 40 in heavy_metals 2024 Sept). These are
real sample rows the lab entered then visually filtered for review — they were
never deleted or rejected. We treat the xlsx as a data source, not a UI snapshot,
so all rows are read regardless of their `hidden` state. If the lab ever wants
to flag a row as truly excluded, they should move it to an "invalid samples"
sheet or delete the row entirely.

## Conventions

- **Sample IDs** are normalised to lowercase, e.g. `Mango-0004-R01` → `mango-0004-r01`. 4-segment IDs (e.g. `OaU-ap-0145-R01`) are also handled.
- **N.D / Not Detected** — in a *result* column → `value=0.0, is_nd=True`. In a *limit* column → `limit=None` (semantically "no limit set"; never compared as 0).
- **Validity vocabulary** — `مطابقة` / `غير مطابقة` / `Valid/Invalid` / `Matched/not matched` / `Compliant/Non-compliant` (case-insensitive). Tested FALSE-first since FALSE strings contain TRUE substrings (e.g. `غير مطابق` contains `مطابق`).
- **Sheet filtering** — global rules: any sheet starting with `final` is skipped; any sheet whose detected year ≠ the file's year is skipped; non-monthly sheets are skipped except where `single_sheet: true` (Honey).
- **Bilingual headers** — `English\nArabic` shape. The cleaner matches alias against `header_en()` first, then full bilingual normalised string (needed for the 4 food-chem sensory columns sharing the English half `اختبار حسي`).
- **Pesticides long-format** — sample metadata appears only on the first row of each sample-block; cleaner forward-fills sample_id, sample_name, validity, etc. onto continuation rows.
- **Row-drop** — strict: any row with no `sample_id` AND no `sample_name` is dropped (catches lab placeholder rows with default 0.0 cells, e.g. water-analysis June with 700+ orphan rows).
- **Min-direction tests** — schema can set `direction: min` on a test where the limit is a minimum threshold (honey purity requires Glucose+Fructose ≥ 60%). Cleaner flips the comparison.
- **Auto pass-through** — any schema-declared column not in `tests:` and not a base metadata field is emitted as a normalised-text column. Lets future schema additions flow to parquet without code changes.

## Honey direction-of-failure logic

| Test | Direction | Why |
|---|---|---|
| Glucose + Fructose | **min** | Real honey must contain ≥ 60% reducing sugars. Lower = adulteration. |
| Sucrose | max | Added sugar / adulteration indicator. |
| HMF | max | Heat/age damage indicator. |
| Moisture | max | High moisture indicates fermentation risk. |
| Acidity | max | High acidity suggests improper storage. |
| Concentration | max | (TBC with lab — currently treated as max.) |
| Sensory | string | Qualitative pass/fail text. |

## Row-for-row verification

`scripts/verify_v2.py` (regenerable from the inline script used in the audit
pass) compares each parquet's validity counts to a manual recount of verdict
cells in the raw xlsx. Result: 5/7 exact, 2 expected ⚠️:

- **pesticides**: parquet has +205 True / +197 False vs raw — forward-fill
  restored verdicts for continuation rows where raw cells are blank.
- **water_analysis**: ±16 from recount row-gate (cleaner uses sample_id_norm,
  recount uses sample_name as the gate).

Both deltas are documented expected behaviour, not cleaner bugs.

## Known quirks documented in source

- Pesticides 2025 file has stray Jan/Feb/Mar **2026** tabs (lab started next
  period). The year-purity rule drops them; ~554 rows excluded.
- Heavy metals Dec-2025 sheet has only 4 rows (effectively empty).
- Honey is a single non-monthly sheet ("Honey Section") with 46 samples.
- Food chemistry has duplicate `"Invalid test"` header (with a literal leading
  double-quote) in some sheets — ignored, the clean `Invalid test` column is
  captured.
- Hormones/antibiotics "LIMT" header (lab typo for "LIMIT") is matched as-is.
- Heavy metals 2025 panel does **not** include Ca/K/Mg/Na (lab removed those
  from 2025 onward).

## Notable 2025 findings

- **Heavy metals — Lead**: 98 samples (10.6%) exceed lead limit. Top offenders
  are fish and olive oil samples.
- **Heavy metals — Arsenic**: 21 exceedances; **Cadmium**: 10.
- **Honey — Adulteration**: 3 samples below the 60% Glucose+Fructose minimum
  (likely fake honey or heavy water dilution). 4 above the HMF maximum
  (over-heated or aged).
- **Food chemistry — pH**: hot sauce (`hs-*` prefix) routinely fails pH
  acidity limits (process-control issue).
- **Aflatoxins — Total + B1**: 6 samples (0.5%) fail; consistent with B1 being
  the dominant aflatoxin in spices/nuts.

## When new data arrives

- **Replace files in `raw/`** with the same filename, run `clean_chemistry.py --section all`. The cleaner re-reads, verifies, and rewrites all parquets.
- **Add a new year** (e.g. 2026): add `2026: "<filename>.xlsx"` to each schema's `applies_to:` block, place the xlsx in `raw/`, run the cleaner. Year-purity filter routes each sheet to the right output parquet automatically.
- **Add a new section**: write a `chem_<section>.yaml` schema, add the section name to the `--section` choices in `clean_chemistry.py`, and add it to `SECTIONS` in `build_dashboard.py`.
