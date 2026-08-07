# Dashboard parity audit (chemistry × microbiology)

**Date**: 2026-06-18 · **Spec**: `docs/superpowers/specs/2026-06-18-dashboard-parity-design.md`

## 1. Chemistry — new SCOPE filters

| Filter | Status | Distinct values | Notes |
|---|---|---|---|
| Compliance chip | ✓ | 2 (Compliant / Non-compliant) | Two-state, both selected = no filter |
| Sector chip | ✓ | 4 (East / North / West / South) | Existing `sector` column |
| GSO 1016 chip | ✓ | 13 | New bridge from `sample_category_canonical` |
| Search box | already existed | — | sample_id / name / facility / failed tests / pesticide |

## 2. Chemistry — new charts

| Card | Status |
|---|---|
| GSO category bar (stacked-by-year + non-comp % line) | ✓ |
| Top 10 most-contaminated subtypes (sample_name, ≥20) | ✓ |
| Riyadh map placeholder (4 sector pins) | ✓ |

## 3. GSO bridge coverage

| GSO category | Sample count |
|---|---:|
| Miscellaneous Foods | 5,277 |
| Fruit and Vegetables | 2,377 |
| Cereals; Legumes and their Products | 2,304 |
| Tomato Concentrates, Sauces, Vinegar, Spices and Herbs | 1,150 |
| Ready to Eat Foods | 523 |
| Meat, Poultry and its Products | 434 |
| Drinking Water | 333 |
| Fish and Shellfish their Products | 107 |
| Animal Feed | 49 |
| Dairy Products | 27 |
| Beverages | 26 |
| Chocolate, Sweets and their Ingredients | 5 |
| Fats and Oils | 2 |
| **TOTAL** | **12,614** |

**Miscellaneous Foods bucket**: 5,277 samples — these are categories like "محار" (oysters), "بيض" (eggs without phrase suffix), or values too rare to map. Add more Arabic→English entries to `CHEM_TO_GSO` if a section grows.

## 4. Microbiology — existing filters confirmed unchanged

Year · Date range · Compliance · Sector · Municipality · GSO category · Severity · Microbe chips · Pathogen-only · Repeat-offender · Exclude raw meat — all verified in the prior filter-linkage audit.

Items pending for full parity (not in this delivery — large scope):

- Micro: search box, Test panel chip (Pathogen panel / Indicator panel), Compliance donut, Year-over-year card, Sample-category table

Adding these would replicate ~300 lines of JS into the micro file. Recommend a follow-up turn with these as the scope.

