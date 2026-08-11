# Microbiology Statistics, GSO Mapping Challenges, & Numerical Ledger

This report provides a comprehensive review of the challenges encountered across the microbiology data pipeline. It summarizes the obstacles regarding statistical representation, GSO categorization, methods, data cleaning, standard operating stages, and provides an exhaustive numerical ledger of the audit results.

## 1. Stages of the Microbiology Data Pipeline
The microbiology pipeline transforms unstructured, ambiguous lab data into statistically valid insights. It consists of the following key stages:
1. **Extraction & Basic Cleaning (`clean_2024.py`, `clean_2025.py`):** Ingestion of raw Excel files across different months. This stage resolves immediate data-entry bugs (e.g., sample ID collisions) and maps raw headers into standard data structures.
2. **Normalization:** Cleaning spelling variants for tests, organisms, and facilities (e.g., standardizing different Arabic spellings for 'Subway' or 'Listeria').
3. **Enrichment & GSO Mapping (`enrich_gso.py`):** The engine assigning strict regulatory standard codes (GSO 1016) based on source codes, learned mappings, and complex naming rules.
4. **Validation & Auditing:** Comparing actual lab test verdicts against required GSO limits, identifying whether the panel was complete, and assessing test severities (Pathogen vs. Indicator).
5. **Dashboarding & Visualization:** Generating interactive Plotly/D3 html dashboards, network graphs, treemaps, and streamgraphs to summarize compliance rates.

## 2. GSO Classification & Categorization Challenges

Mapping a free-text "Sample Name" to a strict regulatory GSO code involves significant linguistic and domain-specific challenges:

### A. Precedence Rules & Contextual Ambiguity
- **Sauce vs. Main Dish:** Distinguishing between items where the sauce is the main ingredient (`صوص برجر`) vs items where the sauce is a condiment to the main dish (`برجر لحم بصوص`). The rule engine requires whole-token scanning and precedence structures (e.g. Sauce-head precedence) to avoid assigning cooked foods into sauce categories.
- **Whole-Token vs. Substring Conflicts:** Arabic substring matching is highly prone to false positives. For example, the string `رز` (Rice) would falsely match inside words like `كرز` (Cherry) or `سنيكرز` (Snickers), wrongly assigning these items to the Rice standard. Strict whole-token bounds are used.

### B. Distinguishing Swabs from True Food Samples
- Environmental hygiene swabs (e.g., `مسحة طاولة`) are frequently entered into the same columns as food samples, occasionally carrying placeholder GSO codes. A dedicated layer is required to identify the word `مسحة` and isolate these samples into a `swab` bucket, preventing them from skewing food compliance statistics.
- **Wash-water swabs** (e.g. `غسيل رز`) needed specific rules to be pushed back into valid `water` buckets rather than generalized swab buckets.

### C. Placeholder Codes and 2025 Extrapolation
- **Code "H":** Lab technicians occasionally used placeholder letters like 'H', which had to be mapped retrospectively by examining the product names (e.g., 'Cheddar' to A-13).
- **2025 Name Extrapolation:** 2025 source data lacked explicit GSO code columns entirely. The pipeline relies on a machine-learning-style "Tier 1" exact match against 2024 names to backfill the codes, achieving an initial ~37% mapping. A strict equality pass is required to prevent false friends (e.g., `جبنة بيتزا` vs `لبنه بيتزا`).

## 3. Data Quality & Statistical Challenges

Data cleaning uncovered profound structural edge cases that directly impact how compliance statistics are computed and aggregated:

### A. Lab Validity Conflicts
- **Valid with Failures:** Rows explicitly marked by the lab as "Valid / Pass" despite listing explicit failed pathogen tests in the adjacent column.
- **Invalid with No Failures:** Rows marked "Invalid / Fail" but containing no failed tests.
*Resolution:* The script standardizes these by prioritizing the objective test list (`n_failed_tests > 0`) over the subjective validity column.

### B. Denominator Honesty & Statistical Noise
When aggregating compliance across facilities or food categories, statistical noise can heavily skew rates. 
- *Challenge:* A restaurant with 1 failed test out of 1 sample would show a 100% failure rate, overshadowing a factory with 40 failures out of 100 samples.
- *Resolution:* The pipeline enforces a statistical threshold (e.g., minimum 20 samples) before calculating percentages in dashboard aggregations to preserve 'denominator honesty'.

### C. Date Parsing Anomalies
Raw lab sheets contained severe date typographical errors, sometimes recording dates as 2026, 2027, or 2028 instead of 2025. The ingestion layer utilizes coercive date logic to collapse anomalous future dates back to their correct 2025 timestamps.

### D. Test-Name Alias Normalization
Laboratories often spell identical microbiology tests in a dozen different ways. 
- Example: `لستيريا`, `L.monocytogenes`, `الليستيريا` all map to the same pathogen.
- Example: `CAMPYLOPACTER` vs `كامبيلوباكتر`. 
Statistics would become fragmented if these aliases were not canonicalized.

### E. Right-to-Left (RTL) Numeric Flipping (`>10` Convention)
A major statistical challenge involved handling non-numeric comparison prefixes. Roughly 14,000 results in 2024 carried a `>10` prefix. Initially appearing as a failure (greater than limit), it was determined to be an RTL data-entry flip for `<10` (Below reporting limit). Failing to catch this convention would have incorrectly flagged thousands of satisfactory samples as failures.

### F. Measuring Panel Completeness (Systematic vs. Sporadic Gaps)
When determining if a sample was comprehensively tested, it was discovered that test gaps are not homogeneous. The pipeline splits missing required tests into:
- **Systematic Gaps:** Tests the lab skipped for ≥90% of samples in that GSO category (a systemic operational gap, e.g., missing Listeria in Cakes).
- **Sporadic Gaps:** Tests skipped randomly (e.g., missing one E.coli check out of thousands).
These definitions enable accurate gap analysis in the statistical dashboards. 

### G. Severity Tiers and Pathogen Reclassification
Severity is dynamically computed based on the failed test profile:
- `Multi-pathogen`: ≥2 pathogen failures.
- `Pathogen`: Exactly 1 pathogen failure.
- `Indicator Only`: ≥1 failure, but purely hygiene indicators (e.g., Coliforms).
- *Note:* Certain tests require domain review for proper tiering. For example, *Pseudomonas* was manually elevated to a Pathogen tier specifically due to its implications in drinking water. 

---

## 4. Comprehensive Numerical Ledger

The following section presents the exhaustive breakdown of all statistical counts, discrepancies, and rule overrides extracted during the pipeline audit.

### 4.1 Master Dataset Counts
| Metric | Count |
| :--- | :--- |
| **Total Processed Samples (Both Years)** | **20,881** |
| Total 2024 Samples | 9,317 |
| Total 2025 Samples | 11,564 |
| Total 2024 Long Format Rows (Pre-Pivot) | 36,461 |

### 4.2 Official vs. Pipeline Discrepancies
| Metric | Count |
| :--- | :--- |
| 2025 Official Annual Report Total | 11,404 |
| **2025 Pipeline Total** | **11,564** |
| Discrepancy (Unexplained extra samples) | +160 |
| Identified `Sector` (قطاع) samples | 505 |
| Identified `Private` (خاص) samples | 67 |
| Sample ID Collisions Rescued (Suffixed -a/-b) | 22 |
*(Note: A conclusive exclusion rule matching the exactly 160 missing samples remains an open question for the laboratory.)*

### 4.3 Compliance & Severities
| Metric | Count |
| :--- | :--- |
| **Overall Non-Compliance Rate (Known Validity)** | **28.14%** |
| 2024 Valid (Passed) Samples | 6,420 |
| 2024 Invalid (Failed) Samples | 2,814 |
| Unknown Validity Samples (Missing pass/fail) | 83 |
| Top Contaminated Category (Sauces/Spices G-2/G-3) | 1,173 |

### 4.4 GSO Mapping Rules & Reclassifications (Applied to Both Years)
These are the exact number of samples that were algorithmically re-routed to fix lab categorization errors:
| Rule / Action | Count Affected |
| :--- | :--- |
| Cooked/Grilled/Fried dishes forced to **Ready-to-Eat (P)** | 2,239 |
| Sauces (صوص) forced to **Sauces (G-2 / G-3)** | 2,909 |
| Wash-water (غسيل) forced to **Unbottled Water (N-3)** | 225 |
| 'Group A' strict strict-equality exact name matches | 111 |
| Swabs safely preserved from being misclassified as food | 133 |
| Placeholder 'H' code manually mapped | 36 |

### 4.5 GSO 1016 Coverage & Sample Types
| Metric | Count |
| :--- | :--- |
| 2024 Samples with Native GSO Codes | 7,919 |
| 2025 Samples Programmatically Mapped | 6,152 |
| **2025 Samples pending manual review (Group B)** | **3,751** |
| 2024 True Environmental Swabs (No GSO) | 1,398 |
| 2025 True Environmental Swabs (No GSO) | 1,674 |
| 2025 `Other` Bucket (Reduced from 23) | 0 |
| 2025 Missing English Categories (Reduced from 383) | 129 |

### 4.6 GSO 1016 Limit Audits & Disagreements (2024 Only)
*Test-level data limits are currently only available for 2024.*
| Metric | Count |
| :--- | :--- |
| **Full Panel Complete** (All required tests run) | **3,756** |
| **Incomplete Panels** (Missing required tests) | **4,090** |
| ↳ *Systematic Gaps* (Lab consistently skips test >90%) | 1,756 |
| ↳ *Sporadic Gaps* (Lab randomly missed test) | 2,334 |
| **Total Lab vs. GSO Verdict Disagreements** | **54** |
| ↳ *Lab says Pass, but should have Failed* | 48 (rows) |
| ↳ *Lab says Fail, but should have Passed* | 14 (rows) |

### 4.7 Data Quality Flags & Fixes
| Metric | Count |
| :--- | :--- |
| `>10` RTL logic flips fixed (Falsely appeared as failure) | 14,120 rows |
| ISO Method Swabs (Outside GSO 1016 Scope) | 1,328 |
| Subway (`صب واي`) spelling variants merged | 68 |
| *C. botulinum* (`بوتيلونيوم`) spelling typos fixed | 22 |
| 2025 Valid/Invalid subjective logic conflicts fixed | 9 |
