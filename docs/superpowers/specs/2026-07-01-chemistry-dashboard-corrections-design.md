# Chemistry Dashboard Corrections — Design

**Date:** 2026-07-01
**Scope:** Chemistry only (`chemistry/` pipeline + `chemistry/reports/chemistry_dashboard.html`).
**Source of comments:** Muhannad's review notes ("تعليقات كيمستري مهند"), 2024 + 2025.

## 1. Goal

Correct the chemistry dashboard and its underlying data on the points Muhannad
raised. The comments fall into three workstreams: **(A) sample-category / data
correctness**, **(B) missing water failed-test details**, and **(C) dashboard UI
fixes**. Work proceeds in phases with a **review gate** after an audit step, so
no rows are silently reclassified before Muhannad approves the rules.

## 2. Root-cause findings (verified against the data)

### 2.1 The category system is broken and inconsistent
- **2024 has NO `sample_category` at all** — every 2024 row is null. The dashboard
  *guesses* the category from keywords in the sample name and defaults unmatched
  rows to **"Miscellaneous Foods."** This is why water 2024 shows "miscellaneous
  food" and aflatoxin 2024 shows meat/beverage/vegetable types.
- **2025 canonicalization was applied inconsistently** —
  `clean/scripts/apply_category_canonical.py` added `sample_category_canonical`
  to `food_chemistry` and `water_analysis` 2025 but **skipped `aflatoxins`**, so
  aflatoxin 2025 still carries raw, messy labels.
- **Raw 2025 labels contain data-entry errors** — e.g. water 2025 has 1 row
  labeled "Meat and Poultry", food_chemistry 2025 has 1 row labeled "Tap water"
  (the water sample Muhannad flagged), plus trailing-quote junk
  (`الحبوب والبقوليات"`) and English+Arabic duplicate variants.

**Conclusion:** the fix is one consistent category pass across **all sections and
both years**, with **per-section validation**, not per-item patches.

### 2.2 Water failed-test details are never surfaced
- Water has **no inline limit columns** (limits live in the GSO 1016 reference),
  so the limit-comparison logic derives nothing → `failed_tests_derived` is
  **empty for all water rows** → the dashboard shows "no test details."
- **Water 2025:** the failing tests already exist in the captured `invalid_test`
  column (58 rows populated, e.g. `"TDS, nitrate, Chloride"`). They are simply
  not wired into the displayed failed-tests. → **wiring fix.**
- **Water 2024:** `invalid_test` is empty (0 rows). The failures exist only as
  the **red-marked cells** in the source xlsx. → **red-cell extraction fix.**

## 3. Architecture decision

**Option A — Fix in the cleaner (chosen).** `sample_category_canonical` becomes a
first-class output column produced for **every section and both years** by a
single rules + validation module. Result: the parquet files, the Excel (xlsx)
mirrors, and the dashboard all show correct categories from one source of truth.
Rejected: Option B (separate post-script — stays a forgettable extra step) and
Option C (dashboard-only — leaves the exported data wrong).

## 4. Comment → fix mapping

| ID | Comment (Muhannad) | Fix | Phase |
|----|--------------------|-----|-------|
| D1 | Aflatoxin shows meat/beverage/water/veg types | Per-section valid-category validation; suspect rows flagged in audit | 0 → 1 |
| D2 | Water section shows "miscellaneous food" (~12) | Force water-section rows to a water category; flag exceptions | 0 → 1 |
| D3 | Food chemistry shows a water sample | Flag in audit; reclassify or relocate per Muhannad's decision | 0 → 1 |
| D4 | Merge all filter-water variants (عجانة etc.) | Canonical merge → **"مياه فلتر"** | 0 → 1 |
| D5 | Group all "شطة …" variants | Canonical merge → **"شطة"** | 0 → 1 |
| M1 | Water "no test details" (real failures are red in sheets) | 2025: wire `invalid_test`; 2024: red-cell extraction | 0 → 1 |
| U2 | Dashboard title | Set title → **"مختبرات أمانة الرياض"** | 2 |
| U3 | Remove small-font info under the top bar | Remove the muted subtitle/subheader block(s) | 2 |
| U4 | Top 10 violating facilities + samples | Change relevant top-N lists to **10** | 2 |
| U5 | Test filter doesn't change with year/section | Repopulate test-filter options from the currently filtered rows | 2 |
| U6 | Filters don't reflect real numbers | Fix KPI recomputation so every card reacts to active filters | 2 |
| U1 | "السنة اللي فوق ينشال 12,614" | **Deferred** — pin against the live dashboard with Muhannad | later |

## 5. Phase 0 — Audit report (no data changes)

Deliverable: a review workbook (`chemistry/reports/category_audit_2026-07-01.xlsx`
+ a short `.md` summary) that lets Muhannad approve the rules before any change:

1. **Category distribution** per section × year (raw label → proposed canonical, with counts).
2. **Suspect rows** — rows whose proposed canonical is **invalid for the section**
   (D1 aflatoxin non-aflatoxin types; D2 water non-water; D3 food-chem water),
   listed with sample_id, sample_name, raw label, proposed canonical, reason.
3. **Merge preview** — every distinct filter-water variant (D4) and every "شطة …"
   variant (D5) that would collapse, with counts, so Muhannad sees exactly what merges.
4. **Water M1 preview** — 2024 invalid water samples with the failed tests the
   red-cell extraction recovers (extraction built in preview mode here), plus the
   2025 rows whose `invalid_test` will be surfaced.
5. **Proposed per-section valid-category allow-list** — the taxonomy Phase 1 will
   enforce, derived from the observed data, for Muhannad to confirm/edit.

**Review gate:** Muhannad approves/edits the allow-list, the merges, and the
suspect-row dispositions (reclassify vs relocate vs leave) before Phase 1 runs.

## 6. Phase 1 — Data fixes (after approval)

1. **New module `chemistry/scripts/categories.py`** containing:
   - `NAME_RULES` — sample-name keyword → canonical category (extended from the
     keyword table currently embedded in `build_dashboard.py`).
   - `SECTION_VALID_CATEGORIES` — the approved per-section allow-list.
   - Explicit merges: filter-water variants → "مياه فلتر"; `شطة*` → "شطة".
   - `canonical_category(section, raw_label, sample_name)` → canonical value.
   - `validate(section, canonical)` → ok / suspect flag.
2. **Integrate into `clean_chemistry.py`** so every section/year parquet gains a
   populated `sample_category_canonical` column (raw `sample_category` preserved
   for rollback). Applies uniformly — closes the aflatoxins-2025 gap and the
   2024 null-category gap.
3. **Water failed-tests:**
   - 2025: map `invalid_test` → `failed_tests_derived` when the limit-derived set is empty.
   - 2024: extend the water reader to capture red-font/red-fill cells from the
     source xlsx and derive the failed parameter names.
4. **Regenerate** `chemistry/cleaned/*.parquet`, copy into `clean/chemistry/`,
   and re-run the xlsx export so Excel mirrors match.
5. **Point `build_dashboard.py` at `sample_category_canonical`** for all sections
   (remove/retire the inline keyword guesser now centralized in `categories.py`).

## 7. Phase 2 — Dashboard fixes

Edits to `chemistry/scripts/build_dashboard.py`, then regenerate
`chemistry/reports/chemistry_dashboard.html`:

- **U2** — Arabic title → "مختبرات أمانة الرياض".
- **U3** — remove the small-font subtitle/info block(s) under the masthead
  (exact element(s) confirmed against the live page).
- **U4** — set the top violating-**facilities** and top-**samples** lists to 10.
- **U5** — rebuild the test-filter options from the currently-filtered rows so the
  list reflects the active year/section instead of a static full list.
- **U6** — ensure all KPI cards recompute from the active filtered set (root-cause
  the specific cards that read a pre-filtered/global total).

## 8. Out of scope / deferred
- **U1** (the "12,614 / year above" element) — revisit against the live dashboard.
- Microbiology and the joint dashboard — untouched (chemistry-only engagement).
- No change to the include-hidden-rows and Aflatoxin-Total-only verdict decisions.

## 9. Verification
- Phase 1: row-count parity per section before/after (canonical adds a column,
  drops no rows unless Muhannad approves discards); spot-check the specific rows
  Muhannad flagged (water→water, food-chem water sample, aflatoxin types).
- Water: confirm previously-empty `failed_tests_derived` is populated for invalid
  water rows (2025 from column, 2024 from red cells); counts match the audit preview.
- Phase 2: open the regenerated HTML, exercise year/section filters, confirm KPIs,
  test-filter options, Top-10 lists, title, and removed subtitle all behave.

## 10. Regeneration commands
```bash
PY=microbiology/.venv/bin/python   # or food_analysis/Iter-2/.venv/bin/python
$PY chemistry/scripts/clean_chemistry.py --section all
cp chemistry/cleaned/*.parquet clean/chemistry/
$PY clean/scripts/export_to_xlsx.py
$PY chemistry/scripts/build_dashboard.py
```
