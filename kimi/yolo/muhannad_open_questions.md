# Open questions for Muhannad / the lab — Microbiology data
**أسئلة مفتوحة لم مهند / المختبر — بيانات الأحياء الدقيقة**

Prepared 2026-08-08 by Kimi Code after the data-quality audit.
Each item: what we need, why, and what changes in the dashboard once answered.
كل بند: ما المطلوب، ولماذا، وماذا يتغير في لوحة البيانات بعد الإجابة.

---

## 1. Lab recording conventions / اتفاقيات التسجيل في المختبر

### 1.1 ~~What does a `>10` result mean?~~ ✅ ANSWERED 2026-08-09
**MR's answer:** `>10` is written incorrectly in the source — it means
**less than 10** (`أقل من 10`), so the sample is compliant and the test
passes. **Applied:** prefixed results are treated as below-limit pass;
lab-vs-GSO disagreements final at 54 samples, ambiguous category retired.

### 1.2 ~~The internal code "H"~~ ✅ ANSWERED 2026-08-09
**MR's answer:** ignore the `H` code and categorize the samples by product
name — which is exactly the applied mapping: cheddar جبنة شيدر → **A-13**
(25) · ketchup صوص كاتشب → **G-2** (2) · other sauces → **G-3** (9),
flagged `gso_code_h_mapped_by_name`. Closed.

---

## 2. GSO panel scope — tests the standard requires but the lab rarely/never runs
## نطاق فحوص GSO — فحوص يطلبها المعيار ولا يجريها المختبر عادة

For each GSO code below: **does the lab actually run this test for this
product?** If a test is intentionally out of scope, we mark it
`optional: true` in `schemas/gso_1016_reference.yaml` and the "incomplete
panel" flag drops for those samples. If it should be run, these are real
practice gaps to fix in the lab, not in the data.

| GSO code | Product | Missing test | Coverage now |
|---|---|---|---|
| G-3 | Mayonnaise / sauces | C. perfringens (كلوستريديوم بيرفرنجنز) | 271 / 1,185 samples |
| J-1 | Precut fruits & vegetables | E. coli O157 | 326 / 1,074 |
| J-1 | Precut fruits & vegetables | Listeria (الليستيريا) | 637 / 1,074 |
| I-9 | Cakes & bakery (ready-to-eat) | Listeria | 0 / 503 |
| C-9 | Frozen cooked poultry | E. coli O157, B. cereus, C. perfringens, Campylobacter | ~0–71 / 425 |
| L-9 | Arabic sweets | Listeria (0 / 368), E. coli O157 (110 / 368) | partial |
| A-13 | Hard/semi-hard cheese | Listeria | 514 / 716 (+25 cheddar from "H") |
| A-3 | Yoghurt / laban (fermented milk) | Salmonella | 71 / 248 |
| P-2 | Sandwiches without salad | Total plate count (العد الكلي) | 0 / 150 |
| G-2 | Tomato products | Salmonella | 1 / 89 |
| A-16 | Ice cream / edible ices | Yeasts & moulds (الخمائر والاعفان) | 0 / 78 |
| L-8 | Honey | Sulphite-reducing anaerobes, C. botulinum | 0 / 69 |
| D-1 | Raw fish | Aeromonas | 3 / 51 |
| E-1 | Fresh whole eggs | Campylobacter | 0 / 40 |

**Current dashboard state:** 4,126 samples (52.4% of 7,882 coded) show
"incomplete GSO panel" — split into 1,756 *systematic* (lab skips the test
for ≥90% of samples under the code) and 2,334 *sporadic*. Your answers decide
how much of this is a data/scope artefact vs a real lab gap.

---

## 3. Official-report reconciliation / مطابقة التقرير السنوي الرسمي

### 3.1 2025 sample count rule
- Cleaned 2025 data: **11,564 samples**. Annual Report says **11,404**
  (+160 difference).
- Already ruled out: private samples, sector-tagged samples, ID-collision
  suffixes, out-of-range dates. 899 duplicate name+facility+date rows exist
  but most look like legitimate multi-batch samples.
- **What we need:** the exact inclusion/exclusion rule behind the 11,404
  figure (e.g. exclude re-tests? a specific sector subset? a different file
  cut?). We will implement it as an optional filter in `clean_2025.py`.

### 3.2 2024 official numbers
- We have no official 2024 totals to reconcile against (cleaned: **9,317
  samples**, 7,882 GSO-coded).
- **What we need:** the 2024 official totals (samples / compliant /
  non-compliant), or confirmation that none exist — then we either populate
  `OFFICIAL_COMPLIANCE[2024]` or remove the conflicting footnote.

### 3.3 2025 test-level data export — بيانات 2025 على مستوى الفحص
- **Context:** the 2025 source file records one row per *sample* with only the
  verdict and the failed test(s). Which tests were **run** is not in the file,
  so 2025 GSO panel completeness and GSO-limit cross-checks cannot be computed
  (they exist for 2024 only). The Annual Report is itself built from
  test-level counts, so this data exists in the LIMS.
- **What we need:** a 2025 test-level export — one row per test:
  sample ID (رمز العينة) · test name (الاختبار) · result/raw value ·
  limit (if available) · pass/fail per test.
- **Impact:** we build `data2025_long.parquet` and 2025 gets full parity with
  2024: panel completeness, per-test limits, and lab-vs-standard checks
  (~11.5k samples join the GSO audit instead of ~4.3k name-assigned codes).

---

## 4. Already confirmed by you (no action needed) / تم تأكيده سابقاً
- `سيدومومناس` (Pseudomonas genus) = the P. aeruginosa test for bottled water
  (N-1) — aliased; 202 samples' panels now complete.
- Spelling aliases for Listeria / yeasts / Campylobacter / B. cereus /
  Aeromonas — applied; 1,010 false "incomplete panel" flags cleared.

---

*Generated by Kimi Code · full technical detail in `microbiology/CHANGELOG.md`
(2026-08-08 entries) and `kimi/yolo/microbiology_audit_report.md`.*
