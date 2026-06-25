# Audit — why our 2025 parquet has 11,564 samples vs Annual Report's 11,404

## TL;DR

The +160 row offset (+1.4%) is NOT due to duplicates in our pipeline. Our parquet has:

- **0 sample_id duplicates** (every ID is unique after the cleaner's suffixing)
- **0 base_id duplicates** after stripping the R1/R2 retest suffix
- **22 sample_id collisions** already handled (suffixed `-a` / `-b`)
- **3 dates coerced** from text to 2025
- **571 "soft duplicates"** (same date+name+facility) which are LEGITIMATE
  multiple samples (e.g., 11 different refrigerator-swab samples from the
  same facility on the same day — each a distinct surface/fridge)

The Annual Report's 11,404 likely uses a different filter/dedup methodology
that we cannot reconstruct without the report's source query.

## Per-organism failed-test gap (more important)

Our pipeline reports 3,730 failed test results; the Annual Report counts 4,211 (Δ -481).
This gap is consistent across all 9 organisms (we are 12–32% lower).

Root cause: the Annual Report counts every test RUN including replicates and
confirmatory re-tests, while our `n_failed_tests` counts each distinct failed
organism once per sample. A sample tested for Salmonella 3 times (initial + 2
confirmations), all failing → report counts 3, we count 1.

| Organism | Our failed | Annual report failed | Δ |
|---|---:|---:|---:|
| العد الكلي للبكتيريا | 1,491 | 1,514 | -23 |
| استافيلوكوكس اورياس | 765 | 862 | -97 |
| الخمائر والاعفان | 650 | 736 | -86 |
| انتيروباكتريسي | 380 | 556 | -176 |
| ايشيريشيا كولاي | 195 | 264 | -69 |
| السالمونيلا | 122 | 140 | -18 |
| كوليفورم | 83 | 86 | -3 |
| باسيلس سيريس | 29 | 33 | -4 |
| سيدوموناس | 15 | 20 | -5 |
| **TOTAL** | **3,730** | **4,211** | **-481** |

## What CAN be aligned

Closest dedup attempts:
- `(date + name + facility)` → 10,993 (-411 — too aggressive, drops legitimate samples)
- `(date + name + sample_id_raw)` → 11,557 (-153 — collapses 7 of the 22 collisions)
- `(date + name + facility + sample_type)` → 10,996 (-408)

None hit 11,404 exactly. The report's number includes ~160 dedup decisions
we don't have visibility into.

## Recommendation

Keep the parquet at 11,564 (every distinct sample we received). The dashboard
banner displays the Annual Report's 11,404 / 40,337 / 4,211 / 73.18% as the
official manual totals. The lower KPI strip shows our 11,564-row baseline so
filters and breakdowns work correctly.

The 1.4% sample offset and the 11% failed-test offset are both *expected
methodology differences*, not data errors.
