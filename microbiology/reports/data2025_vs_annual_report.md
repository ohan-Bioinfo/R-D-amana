# Comparison: cleaned/data2025.parquet vs Annual Report 2025

Comparing only the **MICRO** stream from the report (CHEM is outside our data scope).

Report file: `2025-original/Annual Report 2025.xlsx`
Our parquet: `cleaned/data2025.parquet` (11,563 rows)

## Totals

| Metric | Annual Report (MICRO) | Our parquet | Δ |
|---|---:|---:|---:|
| Total samples | 11,404 | 11,563 | +159 (+1.4%) |
| Compliant samples | 8,345 | 8,524 | +179 |
| Compliance rate | 73.18% | 73.72% | +0.54 pp |

## Monthly

| Month | Report total | Our total | Δ | Report compliance | Our compliance | Δ pp |
|---|---:|---:|---:|---:|---:|---:|
| Jan | 859 | 944 | +85 | 70.20% | 70.02% | -0.18 |
| Feb | 782 | 967 | +185 | 72.38% | 70.73% | -1.65 |
| Mar | 761 | 913 | +152 | 81.21% | 79.52% | -1.69 |
| Apr | 1380 | 1454 | +74 | 69.49% | 69.53% | +0.04 |
| May | 1269 | 974 | -295 | 71.39% | 68.58% | -2.81 |
| June | 704 | 971 | +267 | 73.58% | 74.36% | +0.78 |
| July | 1130 | 827 | -303 | 72.12% | 75.45% | +3.33 |
| Aug | 1107 | 668 | -439 | 71.54% | 71.26% | -0.28 |
| Sep | 806 | 647 | -159 | 74.57% | 75.89% | +1.32 |
| Oct | 803 | 908 | +105 | 71.73% | 78.52% | +6.79 |
| Nov | 935 | 1181 | +246 | 75.72% | 73.92% | -1.80 |
| Dec | 868 | 1109 | +241 | 78.69% | 78.90% | +0.21 |

## Per-test invalid counts

| Test (Arabic) | Report total | Report invalid | Our invalid | Δ invalid |
|---|---:|---:|---:|---:|
| العد الكلي للبكتيريا | 6645 | 1514 | 1491 | -23 |
| استافيلوكوكس اورياس | 7250 | 862 | 765 | -97 |
| الخمائر والاعفان | 4561 | 736 | 650 | -86 |
| انتيروباكتريسي | 3784 | 556 | 380 | -176 |
| ايشيريشيا كولاي | 7342 | 264 | 195 | -69 |
| السالمونيلا | 8305 | 140 | 122 | -18 |
| كوليفورم | 778 | 86 | 83 | -3 |
| باسيلس سيريس | 1340 | 33 | 29 | -4 |
| سيدوموناس | 332 | 20 | 15 | -5 |

## Likely reasons for the differences

1. **Date basis**: report's monthly column is likely **lab-receive date or report-issue date**; our `sampling_date` is when the sample was collected. This shifts samples between adjacent months (Feb +185, May −295, July −303, Aug −439, etc.) while keeping the year-total close (+1.4%).
2. **Test-count granularity**: our row count is per sample; the report's per-test totals (e.g. APC = 6,645) suggests it counts test runs, including replicates, confirmatory tests, and some samples re-tested. Our `invalid_tests` lists count failures once per sample.
3. **Deduplication**: we dropped 7 true-duplicate sample IDs and suffixed 11 ID collisions. The report likely retained those rows.
4. **Source-data inconsistencies**: 9 rows had `is_valid` ↔ `invalid_tests` conflicts. We use the composite `is_failure`; the report uses whichever validity column its export chose.

## What's NOT in our parquet

- **CHEM stream**: the report's chemistry sub-stream covers 7,287 samples (pesticides, aflatoxins, moisture, ash, pH, sensory, water analysis). Our raw input doesn't include these — we'd need a separate input file to ingest them.
- **Sector-level municipality grouping**: the report aggregates by 5 cardinal sectors (الأوسط/الشمال/الغرب/الشرق/الجنوب + الخاصة) totaling 17,648. Our data is at neighborhood granularity. Mapping neighborhood → sector would require a domain-supplied lookup table.
- **Pesticide details**: banned/restricted/above-MRL counts, contaminated crops, top pesticides — all in the report, none in our parquet.
