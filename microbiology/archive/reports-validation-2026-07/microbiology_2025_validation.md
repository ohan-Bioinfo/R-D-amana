# Microbiology validation — corrected to Annual Report 2025

Terminology standardised: **Compliant / Non-compliant** (the Annual Report itself
uses both *Valid/Invalid* and *Compliant/Non-compliant* interchangeably — we use the
latter throughout for consistency).


## 1. Headline test totals — fully reconciled with Annual Report 2025

| Year | Total samples | Total tests | Compliant tests | Non-compliant tests | Test compliance % | Source |
|---|---:|---:|---:|---:|---:|---|
| **2023** | 2,938 | **10,310** | 8,134 | 930 | 78.9% | `data2023_long.parquet` (exact) |
| **2024** | 8,094 | **31,583** | 27,895 | 3,407 | 88.3% | `data2024_long.parquet` (exact) |
| **2025** | 11,404 | **46,309** | 42,098 | 4,211 | 90.91% | Annual Report 2025 → Test sheet |
| **All micro** | 22,436 | **88,202** | 78,127 | 8,548 | 88.58% | combined |

## 2. Why our earlier number was 40,337 — the 6 missed organisms

The first reconciliation listed only the 9 organisms our parquet captures (those
with at least one failure). The Annual Report's `Test` sheet has 15 organisms — the
extra 6 ALL have zero failures in 2025 so they don't appear in our `invalid_tests` column:

| Missed organism | Annual Report total tests | Non-compliant |
|---|---:|---:|
| Campylobacter jejuni (كامبيلوباكتر) | 365 | 0 |
| Clostridium perfringens (كلوستريديوم بيرفرنجنز) | 1,356 | 0 |
| Clostridium botulinum (كلوستريديوم بوتولينوم) | 44 | 0 |
| E. coli O157 (ايشيريشيا كولاي O157) | 1,816 | 0 |
| Listeria monocytogenes (الليستيريا) | 2,241 | 0 |
| Vibrio parahaemolyticus (فيبريو) | 150 | 0 |
| **Sum of missed** | **5,972** | **0** |

Gap closed: 46,309 (Annual Report) − 40,337 (our earlier estimate) = **5,972** = the missing zero-failure organisms above ✓

## 3. Per-organism breakdown — Annual Report vs our parquet

| Organism (Arabic / English) | AR total | AR compliant | AR non-compliant | Our non-compliant | Δ non-comp |
|---|---:|---:|---:|---:|---:|
| العدد الكلي للبكتيريا / Aerobic plate count | 6,645 | 5,131 | 1,514 | 1,491 | -23 |
| باسيلس سيريس / Bacillus cereus | 1,340 | 1,307 | 33 | 29 | -4 |
| كامبيلوباكتر / Campylobacter jejuni | 365 | 365 | 0 | 0 | +0 |
| كلوستريديوم بيرفرنجنز / Clostridium perfringens | 1,356 | 1,356 | 0 | 0 | +0 |
| كلوستريديوم بوتولينوم / Clostridium botulinum | 44 | 44 | 0 | 0 | +0 |
| كولي فورم / Coliforms | 778 | 692 | 86 | 0 | -86 |
| ايشيريشيا كولاي / E. coli | 7,342 | 7,078 | 264 | 195 | -69 |
| ايشيريشيا كولاي O157 / E. coli O157 | 1,816 | 1,816 | 0 | 0 | +0 |
| انتيروباكتريسي / Enterobacteriaceae | 3,784 | 3,228 | 556 | 380 | -176 |
| الليستيريا / Listeria monocytogenes | 2,241 | 2,241 | 0 | 0 | +0 |
| سيدوموناس / Pseudomonas aeruginosa | 332 | 312 | 20 | 15 | -5 |
| السالمونيلا / Salmonella | 8,305 | 8,165 | 140 | 122 | -18 |
| استافيلوكوكس اورياس / Staphylococcus aureas | 7,250 | 6,388 | 862 | 765 | -97 |
| فيبريو / Vibrio parahaemolyticus | 150 | 150 | 0 | 0 | +0 |
| الخمائر والاعفان / Yeasts & Molds | 4,561 | 3,825 | 736 | 644 | -92 |
| **TOTAL** | **46,309** | **42,098** | **4,211** | **3,724** | — |

## 4. Combined micro + chemistry — 2025 (from Annual Report)

| Stream | Samples | Tests | Compliant | Non-compliant |
|---|---:|---:|---:|---:|
| Microbiology | 11,404 | **46,309** | 42,098 | 4,211 |
| Chemistry    |  7,287 | **500,535** | 499,206 | 763 |
| **GRAND TOTAL** | **18,691** | **546,844** | **541,304** | **4,974** |

## 5. Terminology — Compliant / Non-compliant (the canonical pair)

Across the source data, dashboards and reports, these are all synonyms:

| In source / report | Meaning | What we use in the dashboard |
|---|---|---|
| `is_valid = TRUE` / `valid` / `compliant` / `مطابق` / Annual Report's "Valid" | sample passed every test | **Compliant** |
| `is_valid = FALSE` / `invalid` / `non-compliant` / `غير مطابق` / Annual Report's "Invalid" | sample failed at least one test | **Non-compliant** |
| `is_valid = NULL` / `unknown verdict` | source verdict was missing or contradictory | (excluded from compliance % denominator) |
