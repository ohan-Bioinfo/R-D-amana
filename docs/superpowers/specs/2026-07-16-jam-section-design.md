# Jam section — design (2026-07-16)

Ingest the lab's jam (مربى) dataset — currently unread — as a new `jam`
analytical section, so ~83 jam samples appear in the dashboard under the GSO
"Jelly, Jam and Marmalade" category. Point #15 from the 2026-07-16 review;
Amjad supplied the sheet.

## Where the data actually lives

The jam data is **already in the raw tree**, in a sheet the cleaner skips:
`raw/2024/Food chemistry section.xlsx`, sheet **`"Jams "`** (trailing space),
83 data rows, dated 2024. The cleaner ignores it because it is a non-monthly
sheet and the `food_chemistry` schema only reads monthly sheets. (The same file
also holds an unread `"Honey section"` sheet — 2024 honey with limits+verdicts —
**out of scope** here, noted for a later task.)

## Data shape (from the raw sheet)

Header row 2 (row 1 is a `"Jam samples "` title). Columns:

- Metadata: Receiving Date, Sample name (all `مربى …`), Sample ID (`1-2189-R01`…),
  Facility Name, Municipality name.
- Sugar panel (no limit columns): Fructose %, Glucose %, (Glucose + Fructose) %,
  Sucrose, Maltose, Carbohydrate QC %, HMF %, Concentration, Moisture, pH,
  Acidity.
- Sensory: القوام (texture), اللون (colour).
- Verdict: `Matched/not matched` — **blank for 82 of 83 rows**; one row is
  `غير مطابقة`.
- Testing Notes.

**Consequence:** there are no limit thresholds for any test and essentially no
lab verdicts, so jam compliance cannot be derived. Jam is **display-only**:
values are shown; validity is *unknown* for all but the single `غير مطابقة`
sample (which is marked non-compliant with no per-test reason → renders as
"Unspecified" via the existing renderFail fallback).

## Decisions (locked with Muhannad 2026-07-16)

- **New `jam` section** (not folded into food_chemistry).
- **Jam only** this task; 2024 honey deferred.
- Category → `المربى والجلي` → GSO **"Jelly, Jam and Marmalade"**.

## Design

### 1. Sheet targeting — `only_sheets` whitelist (`scripts/_common.py`)

`"Jams "` is one sheet inside a 15-sheet file, so `single_sheet: true` alone
would wrongly read every sheet. Add an optional **`only_sheets`** list to the
schema, honoured in `iter_data_sheets`: when present, read only sheets whose
normalised name (strip + lowercase) matches a whitelist token (exact or
startswith). This is a small, general addition (also useful for the future
2024-honey task). When absent, behaviour is unchanged.

### 2. Jam schema (`schemas/chem_jam.yaml`)

Modelled on `chem_honey.yaml` but limit-less:

```yaml
section: jam
applies_to:
  2024: "Food chemistry section.xlsx"
single_sheet: true
only_sheets: ["Jams"]        # matches the "Jams " sheet
header_row_max: 4
columns:
  sampling_date:    ["Receiving Date"]   # only date present → drives monthly chart
  sample_name:      ["Sample name", "Sample Name"]
  sample_id:        ["Sample ID"]
  facility_name:    ["Facility Name"]
  municipality:     ["Municipality name"]
  validity_raw:     ["Matched/not matched", "Matched/ not matched"]
  fructose:              ["Fructose %"]
  glucose:               ["Glucose %"]
  glucose_plus_fructose: ["(Glucose + Fructose) %"]
  sucrose:               ["Sucrose"]
  maltose:               ["Maltose"]
  carb_qc:               ["Carbohydrate QC %"]
  hmf:                   ["HMF %"]
  concentration:         ["Concentration"]
  moisture:              ["Moisture"]
  ph:                    ["pH"]
  acidity:               ["Acidity"]
  texture:               ["القوام"]
  colour:                ["اللون"]
  testing_notes:         ["Testing Notes"]
tests:
  - { name: "Fructose",            result: fructose,              limit: null, unit: "%" }
  - { name: "Glucose",             result: glucose,               limit: null, unit: "%" }
  - { name: "Glucose + Fructose",  result: glucose_plus_fructose, limit: null, unit: "%" }
  - { name: "Sucrose",             result: sucrose,               limit: null, unit: "%" }
  - { name: "Maltose",             result: maltose,               limit: null, unit: "%" }
  - { name: "HMF",                 result: hmf,                   limit: null, unit: "%" }
  - { name: "Concentration",       result: concentration,         limit: null, unit: "%" }
  - { name: "Moisture",            result: moisture,              limit: null, unit: "%" }
  - { name: "pH",                  result: ph,                    limit: null }
  - { name: "Acidity",             result: acidity,               limit: null, unit: "%" }
  - { name: "Texture",             result: texture,               kind: string }
  - { name: "Colour",              result: colour,                kind: string }
```

All numeric tests have `limit: null` → the cleaner emits the value with no
pass/fail. Validity comes solely from `validity_raw`.

### 3. Cleaner wiring (`scripts/clean_chemistry.py`)

Add `"jam"` to the `--section` choices and to the `all` iteration list. No other
logic changes — the generic schema-driven path handles a limit-less section.

### 4. Classification (`scripts/categories.py`)

Sample names are `مربى …`, which the existing `مربى → C_JAM` keyword classifies
to `المربى والجلي`. But 2 rows are typo'd `مربو …` whose fruit-flavour keywords
(توت/مشمش) would misroute them to fruit/veg before any section default fires.
Since the `"Jams "` sheet is entirely jam, `classify()` **force-classifies the
`jam` section** to `C_JAM` via a `section == "jam"` short-circuit at the top —
so all 83 rows land in Jelly/Jam regardless of name.

### 5. Dashboard (`scripts/build_dashboard.py`)

Add to `SECTIONS`:
`("jam", "Jam & jelly", "Sugar profile (Fructose/Glucose/Sucrose), HMF, moisture, pH — display-only, no GSO limits")`.
Jam then gets its own tab and flows into All-sections, the GSO category chart
(under "Jelly, Jam and Marmalade"), sector breakdown, subtypes, and the
drilldown. Its validity is mostly *unknown*, which the existing unknown-handling
already renders. No dashboard logic changes beyond the SECTIONS entry.

## Out of scope
- 2024 honey ("Honey section" sheet) — deferred.
- Deriving jam compliance / GSO jam limits — none available.

## Verification
- Cleaner emits `cleaned/chem_jam_2024.parquet` with **83 rows**, all
  `sample_category_canonical == المربى والجلي`, sugar-panel values populated,
  `is_valid` = False for 1 row (`غير مطابقة`) and null for the rest.
- `only_sheets` reads exactly the `"Jams "` sheet (not the 14 other sheets), and
  the `food_chemistry` section's output is unchanged (regression check on its
  row count).
- Dashboard rebuilds with a **Jam & jelly** tab; jam volume appears under GSO
  "Jelly, Jam and Marmalade"; existing sections unchanged.
- Mirror `clean/chemistry/chem_jam_2024.parquet` byte-identical.

## Rebuild
```
scripts/clean_chemistry.py --section all
cp cleaned/*.parquet ../clean/chemistry/
scripts/build_dashboard.py
```
