# Change Notes — Chemistry & Microbiology (July 2026)

Audit + change log for both lab-data workstreams. Covers the corrective passes
run 2026‑07‑01 → 2026‑07‑09. Both are kept strictly scoped — chemistry commits
touch only `chemistry/` (+ its `clean/` mirror); microbiology commits touch only
`microbiology/`.

---

## Part A — Chemistry

**Goal:** audit the v1 chemistry pipeline and re-classify products onto the GSO
1016 taxonomy the user validated, then rebuild the dashboard.

### What we did (chronological)

**Phase 0 — read-only audit (2026‑07‑01)** · `7afa34c`, `fa93734`
- Audited category assignments + water failed-test handling. No data changes;
  recorded findings and the user's approved Phase 1 rules.

**Phase 1 / 1b / 1c (2026‑07‑01)** · `4720304`, `f7e5269`, `1f08d46`, `d597277`, `6af783f`
- Canonical category set + recovery of water failed-tests that were being dropped.
- Aflatoxin verdicting tightened (Total-only has the regulatory limit; B1/B2/G1/G2
  sum to Total).
- Early taxonomy moves: فلفل→spices, nuts→cereals (both later revised), sector
  enrichment, retire the "Ready-to-Eat" category, honey→sweets.
- Classification-review workbook produced for the user's taxonomy sign-off.

**Phase 2 / 3 — prefix-based reclassification (2026‑07‑04)** · `d2bef8f` → `dba16fa`
- **Classifier rewrite** (`chemistry/scripts/categories.py`): per-`sample_id`
  corrections → name-override → sample_id **prefix** decode → water subtype →
  name-keyword → raw → default. Driven by the user's validated
  `category_location_validation…-Corrected.xlsx` (sheet 8 corrections + prefix tab).
- **Taxonomy rulings applied:** nuts→sweets, فلفل→fruit/veg, olive oil (زيت زيتون)→
  Fats & Oils, pesticide-section spices **and** cereals/legumes→fruit & vegetables.
- **Miscellaneous reserved for sesame only**; new "Others" (أخرى) bucket for the
  genuinely-unclassified.
- **Water collapsed to 2 classes** (potable vs non-potable); `ubot` (unbottled)→tap.
- Dropped bad source rows (food_chem 2024 Jan/Feb/Apr; a stray pesticide beverage).
- **Dashboard Phase 2:** per-section reactive test KPIs, None-location bucket,
  data-driven Riyadh map (per-sector numbers), build stamp shows date + time.

**Finishing pass (2026‑07‑05 → 07‑09)** · `67d9272`, `88f2027`, `0ef2577`, `c0d7ae6`, `f99cc8a`
- `water_analysis` section defaults to potable (no more spurious "Others").
- **GSO bridge de-duplicated** to one canonical GSO per chemistry category (18 entries).
- **Municipality normalized** — private variants merged to «عينة خاصة», out-of-place
  junk cleared, unmapped→`no_municipality`.
- Classifier keyword gaps filled from the full sheet-8 review.
- Audit cleanup: dropped 6 null-id junk rows; audit recorded in design spec **§9f**.

### Key rulings (chemistry)
- **5-sector** taxonomy including **Central** (restored 2026‑06‑25 — do not drop).
- **Aflatoxin:** only *Aflatoxin Total* has a regulatory limit.
- Miscellaneous = sesame only; everything else classified or → Others.
- Water = 2 classes.

### Pipeline / how to regenerate
```
chemistry/scripts/clean_chemistry.py --section all
cp chemistry/cleaned/*.parquet clean/chemistry/       # byte-identical downstream mirror
chemistry/scripts/export_to_xlsx.py
chemistry/scripts/build_dashboard.py
```
- **Edit the source** in `chemistry/cleaned` — `clean/chemistry` is a generated
  copy; never hand-edit it.
- Pipeline inputs: `category_corrections.csv` (per-sample_id overrides).
- Design spec: `docs/superpowers/specs/2026-07-01-chemistry-dashboard-corrections-design.md`.

### Current state
- Dashboard: `chemistry/reports/chemistry_dashboard.html`.
- ⚠️ Uncommitted working artifacts present (regenerated): `chemistry_dashboard.html`,
  `category_audit_2026-07-01.{md,xlsx}`, a few `chem_*.md` section reports, and an
  untracked `chemistry_dashboard.zip`. These are regenerated outputs, left as-is.

---

## Part B — Microbiology

**Goal:** apply the user's validation tables + comments to the micro data and the
combined 2024/2025 dashboard, then audit the dashboard for bugs.

### What we did (chronological, all 2026‑07‑09)

**Discard 2023 + GSO corrections** · `d1c87f4`
- All 2023 data dropped from the workstream.
- **64 per-`sample_id` GSO-category targets** applied for 2025 via
  `microbiology/scripts/gso_category_corrections.csv` (highest-priority override).
- 2025 has no native GSO code, so GSO is derived: per-sample override → 2024 native
  → `SAMPLE_TYPE_TO_GSO` (bucket→GSO) → `classify_sample_name`. Result: 0 Miscellaneous
  in 2025.

**Dashboard bugs + core data fixes** · `f58fcf6`
- **Filter bug:** the *Most-contaminated subtypes* ranking was bound to the
  slice-independent scope set, so the Pathogen-only / microbe / severity slice never
  reached it. Made it slice-aware.
- **Subtype grouping:** «قطع بقدونس» (parsley pieces) now folds into «بقدونس».
- **Private samples** already unified to «عينة خاصة» (67) at the canonical field.
- **8 `sample_type` mis-buckets fixed** — all casefold-substring collisions or a
  missing bucket:

  | product | was | cause | now |
  |---|---|---|---|
  | watermelon البطيخ | water | `water` ⊂ `watermelon` | produce |
  | eggplant الباذنجان | dairy | `egg` ⊂ `eggplant` | produce |
  | strawberry الفراولة | raw_meat | `raw` ⊂ `st**raw**berries` | produce |
  | pickled veg مخلل الخضروات | dairy | bare `fermented` | produce |
  | molasses/debs المولاس | dairy | `لبن` ⊂ `البنية` | sauce_condiment |
  | donut دونات | produce | `nut` ⊂ `donut` | sweets_bakery |
  | falafel/bhaji فلافل | sweets | wrong keyword | prepared_meal |
  | fish/الأسماك | cooked_meat | no fish bucket | **new `fish` bucket** → Fish GSO |
  | eggs/البيض | dairy | no egg bucket | **new `egg` bucket** → Egg GSO |

- **5-sector migration:** micro moved from 4-sector to the chemistry-matching
  5-sector taxonomy; **Central restored** (الملز/المعذر/العليا/الشميسي/البطحاء,
  4,703 rows).

**4 taxonomy rulings** · `fd5383a` (user-confirmed)
- الخضار المشوية والمطبوخة grilled/cooked veg (129) → **Ready to Eat**
- المخلل Pickle (303) → **Fruit & Vegetables** (GSO J-7; matches 2024)
- السمبوسة Samosa (13) → **Ready to Eat**
- **New `cereals` bucket** → *Cereals; Legumes and their Products* (67: grains,
  bulgur, lentil, beans, freekeh, chickpea, jareesh, oats, lupin, wheat, malt).

**Dashboard audit — 4 bugs fixed** · `a2be606`
1. *Most-contaminated subtypes* collapsed to 100% for every row under any slice
   (numerator + denominator both from the sliced set; `MIN_SAMPLES=20` left 3 of 72
   subtypes). Fixed: denominator from scope, numerator from slice∩failure — pathogen-
   only now ranks 72 subtypes by real rate (سلطة مشاوي 81.8%, بقدونس 79.2%, تبولة 67.9%).
2. Map metric/tile toggles re-rendered from `__lastFiltered` (severity-events subset)
   instead of the `rowsScope` the map is drawn from. Added `window.__mapRows`.
3. Non-compliance rate line vanished from sector/municipality charts whenever a
   microbe chip was active (stale assumption; those charts are scope-fed). Guard removed.
4. Top-subtypes "click the chip to filter" was a dead affordance. Wired a delegated
   click → toggles the organism in the microbe filter + syncs the chip UI.

### 2025 GSO distribution (final)
Fruit&Veg 2512 · Sauces/Spices 2418 · Swabs 1680 · Sweets 1550 · Meat 890 · RTE 845 ·
Dairy 721 · Beverages 347 · Drinking Water 331 · **Fish 130** · **Cereals 67** ·
Animal Feed 40 · **Egg 32** · Fats 1 · **Miscellaneous 0**.

### Pipeline / how to regenerate
```
microbiology/.venv/bin/python scripts/clean_2025.py \
    2025-original/'Data 2025.xlsx' cleaned/data2025.parquet reports/data2025_diff.md
microbiology/.venv/bin/python scripts/build_dashboard_combined.py
```
- `sample_type` buckets are keyword-matched (casefold substring, first-hit-wins) in
  `microbiology/schemas/lab_data_2025_v1.yaml`. Edit buckets → **re-run `clean_2025.py`**.
- Sector logic (`derive_sector_5` / `SECTOR_5_OF_SUBMUNI`) + `SAMPLE_TYPE_TO_GSO`
  live in `build_dashboard_combined.py`.
- Per-sample GSO overrides: `scripts/gso_category_corrections.csv`.

### Current state
- Dashboard: `microbiology/reports/microbiology_dashboard.html` (19,658 rows; 2024=8,094, 2025=11,564).
- All micro work committed; working tree clean for `microbiology/`.

---

## Cross-cutting conventions
- **Scoped commits** — verify with `git diff --cached --name-only | grep chemistry`
  (or `microbiology`) before committing; never mix the two domains.
- **5-sector taxonomy (incl. Central)** is now shared by both labs.
- Shared `sample_id` join key between labs; don't break the ID format.
- Dashboard paths:
  - `chemistry/reports/chemistry_dashboard.html`
  - `microbiology/reports/microbiology_dashboard.html`
