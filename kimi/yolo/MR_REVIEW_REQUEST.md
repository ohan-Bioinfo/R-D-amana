# MR Review — everything needed to make the microbiology data 100% complete
# مراجعة السيد مهند — كل ما نحتاجه لإكمال بيانات الأحياء الدقيقة 100%

Prepared 2026-08-08 · Kimi Code · repo `R-D-amana`, branch `main`.
All numbers below are verified against the cleaned parquets (20,881 samples:
2024 = 9,317 · 2025 = 11,564). Technical trail: `microbiology/CHANGELOG.md`.

**How to use this report:** answer each numbered item (one line is enough —
e.g. "yes", "optional", the correct rule). Nothing here requires MR to edit
files; every answer is applied by us and the dashboards regenerate.

---

## A. Where we stand (already fixed — no action needed) / ما تم إنجازه

| Area | Status |
|---|---|
| Sample totals & validity (20,881 · 83 unknown · 28.1% NC) | ✅ verified, all 3 dashboards agree |
| All-swab classification (equipment/surface samples) | ✅ fixed |
| Category buckets (okra, molokhia, shira, waffle… → GSO categories) | ✅ fixed |
| Test-name spelling aliases (Listeria, yeasts, Campylobacter, B. cereus, Aeromonas, Pseudomonas, C. botulinum, Fecal Coliforms) | ✅ applied — 1,010 false panel flags cleared, `test_value_unrecognised` = 0 |
| ISO-placeholder swabs (1,328) | ✅ reclassified informational (correctly outside GSO 1016) |
| 'H'-code samples (36) | ✅ **confirmed by MR 2026-08-09**: ignore `H`, categorize by product name — cheddar → A-13 (25), ketchup → G-2 (2), sauces → G-3 (9) |
| 2025 GSO codes by name — Tier 1 | ✅ live: 4,263 / 11,564 (36.9%) |
| `>10` result convention | ✅ **answered by MR 2026-08-09**: it means `<10` (below limit = pass) — applied; disagreements final at 54, ambiguous retired |

---

## B. What we need from MR / المطلوب من السيد مهند

### ~~B1. Result convention: what does `>10` mean?~~ ✅ ANSWERED 2026-08-09
**MR's answer:** `>10` is written wrong in the source — it actually means
**less than 10** (`أقل من 10`), so the sample is compliant and the test
passes. **Applied:** prefixed results are treated as below-limit pass in the
cross-check; disagreements finalised at **54 samples**, the "ambiguous"
category is retired. Nothing further needed.

### ~~B2. Confirm the internal code "H"~~ ✅ ANSWERED 2026-08-09
**MR's answer:** ignore the `H` code and categorize the samples by product
name. That is exactly the mapping already applied: cheddar جبنة شيدر →
**A-13** (25) · ketchup صوص كاتشب → **G-2** (2) · other sauces مايونيز/رانش →
**G-3** (9), flagged `gso_code_h_mapped_by_name`. Nothing further needed.

### B3. GSO panel scope — is the rarely-run test in scope? ⏱ 15 minutes
GSO 1016 requires these tests, but the lab rarely/never runs them. For each
row answer **"in scope"** (real lab gap — keep flagging) or **"optional"**
(we mark it `optional: true` in the reference and the flag clears):

| GSO code | Product | Test | Lab coverage |
|---|---|---|---|
| G-3 | Mayonnaise/sauces | C. perfringens | 271 / 1,185 |
| J-1 | Precut fruit & veg | E. coli O157 | 326 / 1,074 |
| J-1 | Precut fruit & veg | Listeria | 637 / 1,074 |
| I-9 | Cakes & bakery (RTE) | Listeria | 0 / 503 |
| C-9 | Frozen cooked poultry | O157, B. cereus, C. perfringens, Campylobacter | ~0–71 / 425 |
| L-9 | Arabic sweets | Listeria (0/368) · E. coli O157 (110/368) | partial |
| A-13 | Hard/semi-hard cheese | Listeria | 514 / 716 |
| A-3 | Yoghurt/laban | Salmonella | 71 / 248 |
| P-2 | Sandwiches (no salad) | Total plate count | 0 / 150 |
| G-2 | Tomato products | Salmonella | 1 / 89 |
| A-16 | Ice cream | Yeasts & moulds | 0 / 78 |
| L-8 | Honey | Sulphite-reducing anaerobes · C. botulinum | 0 / 69 |
| D-1 | Raw fish | Aeromonas | 3 / 51 |
| E-1 | Fresh eggs | Campylobacter | 0 / 40 |

**Impact:** decides the final meaning of "Incomplete GSO panel —
currently 4,126 samples (52.4% of 7,882 coded; 1,756 systematic / 2,334 sporadic)".

### B4. The 2025 Annual Report rule (+160) ⏱ 5 minutes
Cleaned 2025 data = **11,564 samples**; Annual Report = **11,404**.
Ruled out already: private samples, sector-tagged rows, ID collisions,
date-range, simple duplicates.
**Answer needed:** the exact inclusion/exclusion rule behind 11,404
(e.g. re-tests excluded? a specific subset? a different file cut?).

### B5. 2024 official totals ⏱ 5 minutes
**Answer needed:** official 2024 totals (samples / compliant / non-compliant),
or confirmation that none exist (then we drop the conflicting footnote).

### B6. 2025 test-level export 📁 the big one
The 2025 file stores one row per *sample* (verdict + failed tests only), so
**which tests were run is unknown** → 2025 panel completeness and GSO-limit
cross-checks are impossible from this file. The Annual Report is built from
test-level counts, so this data exists in the LIMS.
**Needed:** one row per test — sample ID · test name · result/raw value ·
limit · per-test verdict.
**Impact:** 2025 gets full parity with 2024 (panel completeness, limits,
disagreements) — ~11.5k samples join the GSO audit properly.

### B7. Tier 2 name review — 45 sample names ⏱ 10 minutes
Remaining 2025 food names with no confident code. Proposals prepared in
`kimi/yolo/2025_gso_code_name_review.md` (e.g. حمص/متبل/بابا غنوج → P-6/4
dips · مخلل → J-7 · صوصات → G-3 · نكهات → O-?).
**Answer needed:** mark each row ✔ / ✏️ corrected code / ✘ leave uncoded.
**Impact:** 2025 code coverage rises from 36.9% toward ~49%.

---

## C. Definition of 100% — checklist / تعريف الاكتمال

| # | Milestone | Blocked by |
|---|---|---|
| 1 | Lab-vs-GSO disagreements final (no ambiguous) | ✅ done 2026-08-09 (54 final) |
| 2 | All source codes mapped & confirmed | ✅ done 2026-08-09 (H → name mapping confirmed) |
| 3 | "Incomplete panel" = real gaps only | B3 |
| 4 | 2025 dashboard matches Annual Report exactly | B4 |
| 5 | 2024 verified against official numbers (or footnote removed) | B5 |
| 6 | 2025 panel completeness + limit checks live | B6 |
| 7 | 2025 GSO code coverage maximised | B7 |
| 8 | Chemistry lab audit (next phase — not part of microbiology 100%) | scheduling |

**After MR's answers:** apply → re-run pipeline
(`clean_2024.py` → `enrich_gso.py` → `build_dashboard_combined.py` →
sunbursts → landing) → verify numbers → update CHANGELOG & this report →
push with "kimi push".

---

*Related docs: `kimi/yolo/muhannad_open_questions.md` (detailed context),
`kimi/yolo/2025_gso_code_name_review.md` (B7 mark-up table),
`kimi/yolo/HANDOFF_2026-08-08.md` (technical handoff).*
