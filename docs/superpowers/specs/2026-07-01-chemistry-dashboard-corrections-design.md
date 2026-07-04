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

## 9a. Phase 0 outcome + approved decisions (2026-07-01)

Audit shipped: `chemistry/scripts/audit_categories.py` →
`chemistry/reports/category_audit_2026-07-01.{xlsx,md}`. Findings: 107 genuine
cross-section mislabels (93 = coffee-in-aflatoxin), 18 review, ~2,500 UNCLASSIFIED
2024 rows (name-guess gap, not mislabels). Merges preview clean; water M1 recovers
54/64 (2025 column) + 41/46 (2024 red cells).

**Muhannad's approved rules for Phase 1:**
1. **Coffee (قهوة) → الحبوب والبقوليات** (valid for aflatoxin) — resolves the 93.
2. **Remaining mislabels → section-aware best-judgment:** water names → water,
   chicken-spice (`بهارات دجاج`) → spices, wheat (`ضرماء` false match) → cereal;
   flag only the truly ambiguous (honey-in-aflatoxin, fresh vs dried fruit).
3. **Both name merges confirmed** exactly as previewed: filter-water (461 rows) →
   «مياه فلتر», شطة (132 rows) → «شطة».
4. **2024 unclassified → section-aware best-effort** name rules; leftovers stay
   "miscellaneous".

## 9b. Phase 1 outcome (2026-07-01)

Shipped: `chemistry/scripts/categories.py` (canonical rules) + integration into
`clean_chemistry.py` (adds `sample_category_canonical`, `category_flag`,
`sample_name_group`; water M1 recovery). Regenerated all 12 chemistry parquets
+ synced to `clean/chemistry/` + xlsx. Row parity held (heavy_metals 2025 went
917→924 because the committed parquet was stale vs the committed script, not from
this change — verified by re-running the HEAD script).

Results: coffee 181 rows → grains/legumes (0 real beverages left); **suspect flags
down 107→12** (honey/hibiscus-in-aflatoxin, the real water-in-foodchem sample, 2
pesticide name quirks — all genuinely-ambiguous, left for review); review 18
(aflatoxin fruit/veg); 1 reclassified (meat→water, D2); merges applied exactly as
previewed (مياه فلتر 461, شطة 132); water failed-tests recovered 41/46 (2024 red
cells) + 54/64 (2025 `invalid_test`).

**Deprecation:** `clean/scripts/apply_category_canonical.py` is now SUPERSEDED —
the cleaner produces `sample_category_canonical` natively for all sections/years.
Do NOT re-run it; it would overwrite with the old 2025-only inconsistent logic.

The dashboard reads `chemistry/cleaned/` directly and already prefers
`sample_category_canonical`, so Phase 2 picks up these fixes automatically.

## 9c. Phase 1b — taxonomy refinements + sectors (2026-07-01)

After reviewing the classification workbook (`chemistry/reports/
classification_review_2026-07-01.{xlsx,md}`), Muhannad ruled:
1. **Aflatoxin valid = grains/legumes, spices, sweets only** (removed RTE, meat,
   beverage). The 184 "RTE" nut rows (لوز/فستق/كاجو) reclassified to grains/legumes.
2. **فلفل → spices (البهارات والصوصات), ALL of them** — overrides any fruit/veg or
   cereal label. 1,616 rows now spices. Also a «فلفل» name-group consolidates the
   74 pepper-name variants in the subtypes chart (this was the wrong top-10 count).
3. **Nuts fold into grains/legumes** per GSO 1016 (no separate nuts category).
4. **Sectors enriched + normalized:** new `chemistry/scripts/sectors.py` maps
   municipality → 5-sector amanah taxonomy (from the microbio schema), with
   normalization (البلدية//typos/الشفاء→الشفا). Added `sector` + `sector_flag`
   columns. Coverage: 12,332 rows mapped; 3,265 `no_municipality` (2024 source has
   no municipality); 168 `private`; **21 `unmapped` (sample names leaked into the
   municipality column — true junk)**. The dashboard's existing sector display now
   has data to show.

Aflatoxin suspect flags now 22 (13 RTE-not-nuts, 7 honey, 1 meat, 1 beverage).

## 9d. Phase 1c — retire Ready-to-Eat, honey→sweets (2026-07-01)

Muhannad ruled (after reviewing RTE_contents): **RTE category → 0** everywhere,
**nuts stay in grains/legumes** (kept the GSO ruling), **honey → sweets/chocolate**,
other RTE items **reclassify by name**. Implemented in `categories.py`: removed the
"ready to eat" keyword and C_RTE from all section valid-sets (so RTE rows fall to
name-based classification), routed عسل/دبس → sweets, added name rules for ex-RTE
items (خبز/توست/طحين/سميد→grains, بصل مجفف/حبة البركة→spices, بصل/فجل/فطر→veg,
رقائق→sweets). Result: **RTE=0**, honey section 25→sweets, nuts consistently
grains (لوز 492 / فستق 367 / كاجو 263), suspect flags 22→5.

**Still pending (Phase 2, dashboard):** (a) rename all "failed"/"failure" →
"non-compliant" in the UI; (b) the duplicate category labels
(`Cereals; Legumes...` / `الحبوب والبقوليات"` / `Cereal and Legume products`) are
already ONE canonical value in the data — they collapse once the dashboard is
rebuilt against `sample_category_canonical`.

## 9e. Phase 3 — validated re-classification + dashboard reactivity (2026-07-04)

Muhannad validated the Phase 1/2 output in
`chemistry/reports/category_location_validation_2026-07-01-Corrected.xlsx`
(sheet 8 «التصنيف الصحيح» — 3,093 row edits — plus a sample_id-prefix decode tab)
and issued a series of rulings that **revise several 2026-07-01 decisions**.

**Classification engine (`categories.py`) — now layered; precedence top→down:**
1. **Per-sample_id corrections** — `chemistry/scripts/category_corrections.csv`
   (2,401 rows lifted verbatim from the «التصنيف الصحيح» column). Authoritative;
   loaded at import, applied first. **This CSV is now a pipeline INPUT** — the
   cleaner depends on it; regenerate categories after editing it.
2. **Name overrides** (win over prefix) — حبة البركة/الحبة السوداء→spices,
   كشنة→ready-to-eat, زيت زيتون→fats. Bread items skip, so «خبز بالحبة السوداء»
   stays a cereal.
3. **sample_id PREFIX → product** (`PREFIX_TO_CANONICAL`) — the lab encodes the
   product in the id prefix (al=almond, uu-pe=pepper, zab=raisin, ses=sesame,
   milk=dairy, raw=meat, bot/ubot=water …); overrides mislabeled raw categories.
4. Water sub-classifier → 5. name keywords → 6. raw keyword → 7. default («أخرى»,
   except the pesticide section which defaults to fruit & veg).

**Taxonomy rulings (these REVERSE the 2026-07-01 taxonomy):**
- Nuts (لوز/فستق/كاجو/بندق/جوز/ترمس/مكسرات) → **sweets** (were grains/legumes).
- فلفل, بصل مجفف, زبيب, سلطة, رقائق/شيبس, خوخ → **fruit & veg** (فلفل was a spice).
- سمسم → **Miscellaneous**; مربى → jelly/jam; حليب/لبن/جبن → dairy; هريس/جريش → cereals.
- **Miscellaneous = sesame ONLY**; every other unclassified row → new **«أخرى» (Others)**.
- **Water = two classes**: potable «مياه صالحة للشرب» (tap + filter + bottled
  merged) and non-potable «مياه غير صالحة للشرب» (حوض/راكد/متحرك). `ubot`
  (un-bottled) never maps to bottled.
- **Pesticide section** (fresh-produce panel): ALL spices **and** cereals/legumes
  → fruit & veg; the single beverage sample is dropped. Olive oil (زيت زيتون) →
  fats (fixed a bug where «تون»/tuna is a substring of «زيتون»/olive).
- Per-section valid-category **gating retired** — `category_flag` is now only
  `None` or `defaulted`; classification comes purely from the product.

**Data drops:** food_chemistry 2024 sheet-months 2024-01/02/04 (sparse — 23 rows).
Total chemistry **15,786 → 15,762**.

**Dashboard (`build_dashboard.py`) — Phase 2 + reactivity:**
- Title «مختبرات أمانة الرياض»; top-10 violating facilities; "failed" → "non-compliant".
- **KPIs react to the section tab** — sample cards recompute from `filteredRows()`;
  the compliant/non-compliant **test** split is precomputed per `(section, year)`.
- **"None" location bucket** for rows with no amanah sector (no-municipality /
  private / unmapped = 3,433); sector chips show per-scope counts; "Sectors
  covered" excludes None.
- **Riyadh map is data-driven** — one marker per sector, size = sample volume,
  colour = % non-compliance, count on the label. Sector chips/chart/map all use
  the English sector names (`_sector_en`).
- Aflatoxin section blurb removed; GSO chips reactive; build stamp shows date + time.

**Current taxonomy (audited 2026-07-04, 15,762 rows):**

| Canonical | GSO 1016 | Rows |
|---|---|---|
| الفواكه والخضار | Fruit and Vegetables | 7,248 |
| الحبوب والبقوليات | Cereals; Legumes | 3,300 |
| الحلويات والشوكولاتة | Chocolate, Sweets | 1,557 |
| البهارات والصوصات | Spices / Sauces | 1,527 |
| مياه صالحة للشرب | Drinking Water | 1,050 |
| اللحوم والدواجن | Meat, Poultry | 427 |
| أغذية متنوعة (sesame only) | Miscellaneous | 273 |
| الأسماك والمأكولات البحرية | Fish | 167 |
| الحليب ومنتجات الألبان | Dairy | 57 |
| الأعلاف | Animal Feed | 55 |
| المشروبات | Beverages | 40 |
| مياه غير صالحة للشرب | Non-potable Water | 23 |
| المربى والجلي | Jelly, Jam | 16 |
| أخرى | Others | 15 |
| الدهون والزيوت | Fats and Oils | 4 |
| الأطعمة الجاهزة للأكل | Ready to Eat | 3 |

Sectors: Central 4,504 · West 3,153 · North 1,833 · East 1,817 · South 1,022 · **None 3,433**.

## 10. Regeneration commands
```bash
PY=microbiology/.venv/bin/python
$PY chemistry/scripts/clean_chemistry.py --section all
cp chemistry/cleaned/*.parquet clean/chemistry/
$PY clean/scripts/export_to_xlsx.py
$PY chemistry/scripts/build_dashboard.py
```
