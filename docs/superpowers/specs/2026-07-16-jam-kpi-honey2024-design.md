# Jam KPI "not evaluated" + 2024 honey — design (2026-07-16)

Two independent follow-ups after the jam section merged:
1. Jam has no validity, so its tests must not be counted as *compliant* in the
   test-count KPI — instead show a **"Not evaluated"** bucket (jam stays in the
   total volume, just out of the compliant/non-compliant split).
2. Ingest the unread **2024 honey** data (the `"Honey section"` sheet in the
   2024 food-chem file) into the existing honey section, enabling honey
   year-over-year.

## Part A — "Not evaluated" bucket in the test-count KPI

### Problem
`_compute_test_counts` (`build_dashboard.py`) splits each section's test cells
into `compliant = n − nc` and `non_compliant = nc`, where `nc =
sum(n_failed_tests_derived)`. A limit-less section (jam) has `nc = 0` for every
row, so **all** its test cells fall into *compliant* — misrepresenting
no-validity data as passing.

### Signal
Use an **explicit `DISPLAY_ONLY_SECTIONS = {"jam"}`** set. (A tempting
"no `*_limit_value` columns" heuristic is WRONG — aflatoxins, pesticides, and
water_analysis also have zero `*_limit_value` columns yet derive real compliance
from `is_valid`; detecting by columns would zero out their compliant counts. Jam
is distinguished by having no validity data at all, `is_valid` null for 82/83
rows. An explicit set is unambiguous and safe.) Add sections to the set if
future display-only panels appear.

### Change — Python (`_compute_test_counts`)
Add a third split component `not_evaluated` everywhere the split is built
(`split_by_year`, `split_by_section_year`, and the grand `compliance_split`):

- For a **display-only** section (`section in DISPLAY_ONLY_SECTIONS`, i.e. jam):
  `not_evaluated = n`, `compliant = 0`, `non_compliant = 0`. Its `n` still
  contributes to `by_year`/`by_section_year` totals (volume unchanged).
- For a **normal** section: `not_evaluated = 0`, `compliant = n − nc`,
  `non_compliant = nc` (unchanged).

Each split dict becomes `{"compliant", "non_compliant", "not_evaluated"}`. The
invariant `compliant + non_compliant + not_evaluated == total` holds per
section/year and in aggregate.

### Change — JS (`testCountsScope` + test-banner render)
- `testCountsScope()` (build_dashboard.py:766-784): track `not_evaluated`
  alongside `compliant`/`non_compliant`; `addSplit` adds `s.not_evaluated || 0`;
  return it in the object.
- Test-banner render (build_dashboard.py:918-930): add a 4th item **"Not
  evaluated"** showing `neTests` and its percentage of total. Percentages of
  compliant/non-compliant are already `x/totalTests`, so with the new bucket the
  three now sum to 100%. Style the new item neutrally (`var(--warn)` or
  `var(--ink-500)`, matching the sample-level "Without specifications" item).

### Behaviour
- **Jam tab:** total tests = jam volume; Compliant = 0, Non-compliant = 0, Not
  evaluated = 100%.
- **All sections:** jam's cells appear only under "Not evaluated"; compliant /
  non-compliant reflect the limit-bearing sections exactly as before.
- No change to the sample-level banner or any other chart.

## Part B — 2024 honey

### Change — `schemas/chem_honey.yaml`
- `applies_to`: add `2024: "Food chemistry section.xlsx"` (keep `2025`).
- Add `only_sheets: ["Honey"]`. This whitelist (from the earlier `only_sheets`
  feature) matches the 2025 file's sole sheet `"Honey Section"` (startswith
  "honey") **and** the 2024 file's `"Honey section"` — and nothing else in
  either file (no monthly/Jams sheet contains "honey"). `single_sheet: true`
  stays.

That is the only change needed — the generic cleaner handles the rest. The 2024
`"Honey section"` carries the same panel **with** limit columns (Sucrose limit%,
HMF limit%, Concentration/Moisture limits, حدود الحموضه) and a `Matched/not
matched` verdict, so 2024 honey derives real compliance exactly like 2025.

### Watch items (verified in the plan, not assumed)
- The 2024 `"Honey section"` header has a **duplicated** `(Glucose + Fructose) %`
  column (value + a second one that is the limit). Confirm the schema aliases
  (`(Glucose + Fructose) %` and `(Glucose + Fructose) % limit`) map cleanly and
  the sheet parses without column collision; if the second column's header is a
  bare duplicate rather than `"… limit"`, note it (the limit may land null — the
  Glucose+Fructose min-verdict would then not fire for 2024, which is acceptable
  and to be reported, not silently masked).
- Honey-2025 output must be **unchanged** (same sheet read; `only_sheets` must
  not alter it) — regression check on its row count and validity counts.
- food_chemistry output unchanged (its schema has no `only_sheets`; it already
  skips the non-monthly `"Honey section"`).

## Out of scope
- 2024 jam already shipped; not touched here.
- No new jam limits (jam stays display-only — that is the whole point of Part A).

## Verification
- **Part A:** rebuild dashboard; `test_counts.compliance_split` has a
  `not_evaluated` equal to the jam test-cell count; jam section's split is
  `{compliant:0, non_compliant:0, not_evaluated:N}`; `compliant + non_compliant
  + not_evaluated == grand`; the built HTML's test-banner code contains a "Not
  evaluated" item.
- **Part B:** `cleaned/chem_honey_2024.parquet` created (~48 rows) with
  `*_limit_value` columns and a real is_valid True/False split; honey-2025 row
  count unchanged; the Honey YoY card now has two years.
- Existing suites (`test_categories.py`, `verify_data.py`, `verify_dashboard.py`,
  `verify_jam.py`) still pass; mirror byte-identical.

## Rebuild
```
scripts/clean_chemistry.py --section all
cp cleaned/*.parquet ../clean/chemistry/
scripts/build_dashboard.py
```
