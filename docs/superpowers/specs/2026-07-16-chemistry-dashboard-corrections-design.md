# Chemistry dashboard corrections — design (2026-07-16)

Corrective pass over the chemistry dashboard driven by Muhannad's review of the
2026-07-09 build. Fifteen points, grouped below by mechanism. Scope is strictly
`chemistry/` (+ its `clean/chemistry/` mirror).

## Guiding principle — one source of truth for name-grouping

Today there are **two divergent name-grouping systems**:

- `categories.name_group()` (Python) writes a `sample_name_group` column into
  every parquet.
- `build_dashboard.py` **ignores that column** and re-groups names in JS via
  `canonName` / `SAMPLE_NAME_FAMILY`, used only by the top-subtypes chart.

The JS copy is what actually drives the chart, and its greedy fruit regex is the
root cause of the frutella bug (#11). The fix collapses these into one path:
`name_group()` becomes the comprehensive, **category-aware** grouper; the
dashboard reads `sample_name_group` from the payload; the JS grouper is deleted.

## Decisions locked with Muhannad (2026-07-16)

- **Others (أخرى):** drop the rows entirely from the pipeline output.
- **Top-non-compliant-test labels:** all **English**.
- **Name merges (#3/#6/#7):** author category-scoped, token-order-insensitive
  rules directly (heuristic); Muhannad spot-checks the rebuilt dashboard.
- **كشنة:** spices & sauces (`C_SPICE`), moved out of Ready-to-Eat.

---

## A. Classification & name-merging — `scripts/categories.py`

### A1. `name_group()` becomes category-aware

New signature: `name_group(sample_name, category, sample_id=None)`. The cleaner
already calls it per row (clean_chemistry.py:407) where category and sample_id
are in scope, so pass them through.

Rules, applied in order:

1. **Fruit families** (ليمون / برتقال / يوسفي / فراولة / تفاح / عنب / بصل /
   طماطم / خس / فلفل …) apply **only** when `category` is fruit&veg
   (`C_FRVEG`). This stops «حليب جمل فراولة» (camel-milk strawberry, a dairy
   product) from collapsing into subtype «فراولة». — **fixes #11.**
2. **Meats** (`C_MEAT`, #3): build a token-order-insensitive key — normalise,
   split to tokens, drop noise tokens (بلدي, «عينة خاصة», standalone digits),
   sort the remainder, rejoin. «لحم عجل كتف بلدي» and any reordering map to one
   group.
3. **Fish** (`C_FISH`, #7): same family/keyword collapse for the common fish
   sub-variants.
4. **Filter water** (#4): any name containing فلتر → «مياه فلتر» (all subtype
   suffixes such as عجانة merge).
5. **Nameless water** (#1/#2): when `sample_name` is empty and the `sample_id`
   prefix is `ubot` → display name «مياه الحنفية»; prefix `bot` → «مياه معبأة».
   The canonical **category is unchanged** (still potable — the 2-class water
   rule stands); this only supplies a display/group name so the sample stops
   being dropped from subtype charts.
6. **Generic normalisation** (#6, all categories): strip trailing sample
   numbers, «عينة خاصة», and collapse whitespace before returning, so
   near-duplicate names fold together.

Return the group label, or fall back to the cleaned original name.

### A2. كشنة → spices (#14)

Move the كشنة entry in `NAME_OVERRIDE` from `C_RTE` to `C_SPICE`.

### A3. Drop «أخرى» / Others (#13)

After classification, the **cleaner drops** rows whose canonical category is
`C_OTHER` («أخرى»). Log the dropped count per section. Non-destructive to source
— parquets always rebuild from `raw/`, so re-including them later is a one-line
revert. Downstream totals (KPIs, YoY, GSO chart) shrink accordingly, which is
the intended effect.

---

## B. "Top non-compliant tests" label fixes — `scripts/build_dashboard.py`

All labels rendered in **English**.

### B1. Split space-joined water failures (#12)

Water `failed_tests_derived` / `invalid_test` store multiple failed analytes as
one space-joined string, e.g. `'TDS T.Hardness Chloride Nitrate Sulphate
Sodium'`. In `renderFail()` (and the drilldown that mirrors it), tokenise water
rows into individual analytes so each is counted on its own — chloride alone,
nitrite alone, etc. Non-water sections keep the existing `|`-split.

### B2. Canonicalise + merge labels (#5/#8)

Extend `FAIL_LABEL_MAP` (keys lowercased):

- `arsenic`, `total arsenic`, `الزرنيخ الكلي` → **Arsenic** (#8).
- Water analytes → canonical English: `sulphate` → **Sulphate**,
  `chloride` → **Chloride**, `nitrate` / `nitrate(no3)` / `النترات` → **Nitrate**,
  `nitrite` → **Nitrite**, `floride` / `fluorid` → **Fluoride**,
  `tds` / `total dissolved salt tds` → **TDS**, `t.hardness` / `total hardness`
  → **Total hardness**, `sodium`, `ph`, `turbidity`.

### B3. Strip leaked subtype tokens

Add «مياه فلتر» and «فلتر» to `PLACEHOLDER_TOKENS` so subtype names that leaked
into the failed-test field stop being counted as tests.

---

## C. Dashboard behaviour

### C1. YoY respects filters (#9)

`renderYoY()` currently reads `sec.rows` (year-only), bypassing compliance /
sector / GSO / search. Re-drive both branches (all-sections table and
per-section card) off `filteredRows()` grouped by year, so the card reflects the
active filter set.

### C2. Unspecified failed test (#10)

عصير برتقال (and any row) that is `is_valid=0` with **no** derivable failing
test currently contributes nothing to the fail chart, so the user can't see why
it failed. Two-part fix:

1. Investigate the raw food-chemistry cell — if a test is derivable from a
   value-vs-limit comparison the cleaner missed, capture it in
   `failed_tests_derived`.
2. Otherwise render an explicit **"Unspecified"** label in `renderFail()` so the
   invalid sample is visible and flagged for lab follow-up rather than silently
   dropped.

### C3. Payload wiring

Add `sample_name_group` to the payload column list in `build_payload()`; point
the top-subtypes chart at it; delete `canonName` and `SAMPLE_NAME_FAMILY`.

---

## D. Deferred

- **Jam (المربى, #15):** blocked on Amjad's spreadsheet. Revisit when it lands.

---

## Rebuild sequence

```
chemistry/scripts/clean_chemistry.py --section all
cp chemistry/cleaned/*.parquet clean/chemistry/     # byte-identical mirror
chemistry/scripts/build_dashboard.py
```

## Verification

- **#11:** no fruit-family label (فراولة, برتقال…) appears under a dairy GSO row
  in top-subtypes.
- **#12:** non-potable water fail chart shows individual analytes, not
  space-joined strings.
- **#8:** one "Arsenic" bar, not Arsenic + Total arsenic + الزرنيخ الكلي.
- **#9:** applying a sector/compliance filter changes the YoY numbers.
- **#13:** no «أخرى» / Others bucket anywhere; totals drop by the logged count.
- **#14:** كشنة samples classify as spices.
- **#1/#2:** nameless ubot/bot rows appear with «مياه الحنفية» / «مياه معبأة».
- Spot-check: meats/fish/filter-water near-duplicate names collapse in
  top-subtypes and the category table.
