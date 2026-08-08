# Microbiology — remaining gaps and suggested fixes

**Date:** 2026-08-08  
**Status:** Microbiology data-quality gaps are now closed. Outstanding items: confirm the 2025 Annual Report inclusion rule, then move to chemistry.

---

## 1. Closed since the last report

| Gap | Fix |
|---|---|
| `الزيت القلي` unbucketed | Added `fats_oils` sample-type bucket. |
| `ملحمة سماء القاهرة` in `other` | Forced to `swab` (environmental swab from the shop). |
| 2024 `sample_id` derived from `gso_code` | Now uses `m_s_no` scoped by `source_file`. |
| Hardcoded 2024 official numbers | Set to `null`; footnote now says "pending reconciliation". |
| GSO panel completeness / disagreements hidden | New dashboard card shows panel completeness and lab-vs-GSO agreement/disagreement. |
| Facility-chain spelling variants fragmenting rankings | `clean_2025.py` applies `FACILITY_SUBSTRING_REPLACEMENTS` (e.g. `صب وأي` → `صب واي`). |
| Arabic-only categories missing English labels | `clean_2025.py` adds `CATEGORY_EN_FALLBACK`; missing `category_en` dropped from 383 → 129. |
| Data-quality flags only visible in logs | Dashboard now has a **Data-quality summary** KPI card. |
| Sample-type breakdown not shown by year | Dashboard now has a **Sample-type distribution** grouped bar chart. |
| Reset button broke map metric/tile toggles | Reset now only clears filter chips/toggles and calls `syncAllChips()`. |
| Severity and sample-type labels showed raw codes | Added `SEVERITY_LABEL` and `SAMPLE_TYPE_LABEL` maps for chips and chart axes. |
| Data-quality summary under-counted unknown validity / missing facility | Fixed scope; facility count restricted to 2025 (2024 source has no facility field). |
| Sunburst dashboards used stale / incorrect denominator | Rebuilt both sunbursts; 83 unknown-validity rows now have their own leaf; NC rate matches main dashboard at **28.1%**. |

---

## 2. Remaining gap: 2025 Annual Report mismatch (+160 samples)

### What we see
- Cleaned 2025 data: **11,564 samples**
- Annual Report 2025: **11,404 samples**
- Difference: **+160 samples (1.4%)**

### Investigation results

| Candidate explanation | Count | Does it explain 11,404? |
|---|---|---|
| Private samples (`municipality_type = خاص`) | 67 | No — excluding them gives 11,497. |
| Sector-tagged samples (`municipality_type = قطاع`) | 505 | No — excluding them gives 11,059. |
| ID-collision disambiguation (`-a`/`-b` suffixes) | 22 rows (11 pairs) | Partial — only 11 extra *IDs*, not 160. |
| Date range outside 2025 | 0 | No. |
| Duplicate `sample_name + facility + date` rows | 899 rows | Possible, but many are legitimate multi-batch samples with sequential IDs. |

### Conclusion
No obvious single exclusion rule reproduces the report's 11,404. The Annual Report likely applies a business rule we do not have (for example: exclude re-tests, exclude private samples **and** a specific subset of sector samples, or use a different source file cut).

### Suggested next step
Ask Muhannad/the lab for the exact inclusion rule behind the 11,404 figure, then implement it in `scripts/clean_2025.py` as an optional filter and document it in `schemas/lab_data_2025_v1.yaml`.

---

## 3. Next major phase: Chemistry audit

Apply the same workflow to the chemistry data:

1. Load cleaned chemistry parquet(s).
2. Check totals against any official report.
3. Check for missing/placeholder GSO codes, validity conflicts, unknown-validity rows, and category/sample-type buckets.
4. Report gaps, get your sign-off, fix, regenerate dashboard/report, log in `CHANGELOG.md`.

---

*For the full list of fixes already applied, see `microbiology_audit_report.md` and `microbiology/CHANGELOG.md`.*
