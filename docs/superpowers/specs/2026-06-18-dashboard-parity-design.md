# Cross-dashboard parity — design

**Date**: 2026-06-18
**Scope**: `chemistry/scripts/build_dashboard.py` + `food_analysis/Iter-2/scripts/build_dashboard_combined.py`.
**Goal**: bring the two lab dashboards into the same filter & chart vocabulary so they read as one institutional family.

## Parity matrix

| Filter | Chem today | Micro today | Action |
|---|---|---|---|
| Section / panel chip | ✓ | ✗ | **add to micro** (Pathogen panel / Indicator panel — synthetic chip derived from `failed_tests` classification) |
| Year chip | ✓ | ✓ | already parity |
| Search box | ✓ | ✗ | **add to micro** |
| Compliance chip (Compliant / Non-compliant) | ✗ | ✓ | **add to chemistry** |
| Sector chip (East / North / West / South) | ✗ | ✓ | **add to chemistry** |
| GSO 1016 category chip | ✗ | ✓ | **add to chemistry** — bridge `sample_category_canonical` → GSO category |
| Severity / Microbe / Pathogen-only / Repeat-offender | ✗ | ✓ | leave (no chem equivalent) |

| Chart | Chem today | Micro today | Action |
|---|---|---|---|
| Monthly compliance | ✓ | ✓ (severity-by-month) | parity |
| Validity / Compliance donut | ✓ | ✗ | **add to micro** |
| Sector breakdown bar (stacked-by-year) | ✓ | ✓ | parity |
| GSO category bar (volume + rate) | ✗ | ✓ | **add to chemistry** |
| Top failed tests | ✓ | ✓ | parity |
| Sample-category table | ✓ | ✗ | **add to micro** |
| Year-over-year card | ✓ | ✗ | **add to micro** |
| Top-10 most-contaminated subtypes | ✗ | ✓ | **add to chemistry** |
| Riyadh map | ✗ | ✓ | **add to chemistry** (placeholder — 4-sector outline, "awaiting coordinates") |
| Drilldown table | ✓ | ✓ | parity |
| Repeat-offender table | ✗ | ✓ | leave (chem has no chain data) |

## 3-tier row-set model — both dashboards

Same SCOPE / SLICE / Active split as the earlier filter-linkage fix. For chemistry, SLICE category is empty today; the hook stays for symmetry.

**Chemistry SCOPE**: section, year, search, compliance, sector, gso_category
**Chemistry SLICE**: (none today)

**Micro SCOPE**: year, date, sector, mun_type, municipality, gso_category, compliance, exclude_raw_meat, **search**, **test_panel**
**Micro SLICE**: severity, microbe, pathogen_only, repeat_only

## Chemistry → GSO bridge (new)

The chemistry parquet's `sample_category_canonical` field carries Arabic category names. Map them to GSO 1016 categories using the same lookup we built for microbio:

| chem `sample_category_canonical` (Arabic) | GSO 1016 category |
|---|---|
| الفواكه والخضار | Fruit and Vegetables |
| الحبوب والبقوليات | Cereals; Legumes and their Products |
| البهارات والصوصات | Tomato Concentrates, Sauces, Vinegar, Spices and Herbs |
| الأطعمة الجاهزه للاكل | Ready to Eat Foods |
| اللحوم والدواجن | Meat, Poultry and its Products |
| الحلويات والشوكولاتة | Chocolate, Sweets and their Ingredients |
| منتجات الألبان | Dairy Products |
| المشروبات | Beverages |
| الأسماك والمأكولات البحرية | Fish and Shellfish their Products |
| البيض ومنتجاته | Egg and Egg Products |
| الزيوت والدهون | Fats and Oils |
| المياه المعبأة / مياه الحنفية | Drinking Water |
| المربى والجلي | Jelly, Jam and Marmalade |
| أغذية أطفال | Infants, Children and Certain Categories of Dietetic Foods |
| غير ذلك | Miscellaneous Foods |

Fall-through: anything unmapped → "Miscellaneous Foods" (same rule as micro).

## Microbio → Test panel synthetic chip (new)

Two chip values:
- **Pathogen panel** — row matches if `failed_tests` contains any organism in the YAML pathogen list
- **Indicator panel** — row matches if `failed_tests` contains any organism in the YAML indicator list

OR semantics across selections. Empty selection = no constraint (current behaviour).

## Chemistry map placeholder

Plotly map of Riyadh centred on (24.7136, 46.6753), zoom 10, light tile. Plot 4 grey "awaiting data" pins at the 4-sector centroids we already use in micro (`SECTOR_CENTROIDS`). Card subtitle: *"Awaiting per-sample geographic coordinates. Sector centroids shown for orientation only."*

When the user later supplies coordinates, swap the 4 placeholder pins for real per-sample bubbles using the existing micro map renderer.

## Annual Report 2025 cross-checks (audit)

Both dashboards reconciled to AR — already verified in earlier audits:
- **Chemistry**: 7,287 samples / 500,535 tests / 763 non-comp tests
- **Microbiology**: 11,404 samples / 46,309 tests / 4,211 non-comp tests

New audit step: per-GSO-category sample counts for chemistry (so the new GSO chip's chip-count = filter result, no off-by-one bugs).

## Deliverables

1. **This spec** — `docs/superpowers/specs/2026-06-18-dashboard-parity-design.md`
2. **Combined audit MD** — `food_analysis/Iter-2/reports/dashboard_parity_audit.md` covering both dashboards: filter × chart matrix, per-GSO chip counts, slice-aware verification
3. **Both dashboards rebuilt + opened**

## Non-goals

- No changes to the cleaners or canonical mapping scripts
- No new typography or palette tweaks
- No map data ingestion (only the placeholder)
- Joint chem×micro dashboard not touched
