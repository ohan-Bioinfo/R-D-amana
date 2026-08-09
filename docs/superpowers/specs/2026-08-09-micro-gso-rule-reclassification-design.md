# Microbiology GSO sample-labeling: rule-based reclassification — Design

**Date:** 2026-08-09
**Status:** Approved for spec review (Muhannad)
**Scope:** microbiology only (both years, 2024 + 2025)

## Goal

Improve GSO 1016 sample labeling for the microbiology data by adding a
deterministic, keyword-driven **rule layer** that assigns/overrides each sample's
`gso_code` from its name, plus a false-friend-safe spelling-variant pass and
rulings for the remaining ambiguous/contradictory rows. The result: higher and
more correct 2025 code coverage, and a consistent cooked-food / sauce taxonomy
across both years.

## Background / current state

- 2024 has **native** lab `gso_code`s (~7,985 coded of 9,317 rows).
- 2025 has **no** source code; `enrich_gso.py::assign_2025_codes_by_name()`
  currently name-matches to 2024 (Tier 1: 4,263 / 11,564 = 36.9% coded).
- A fuzzy-match audit (`kimi/yolo/2025_gso_tier1b_spelling_variants.md`) sorted
  the uncoded 2025 rows into **Group A** (single-code spelling variants, safe),
  **Group B** (multi-code, ambiguous), **Group C** (9 swab-vs-food contradictions).
- GSO taxonomy reference: `microbiology/schemas/gso_1016_reference.yaml` (mirror in
  `kimi/yolo/gso_1016_code_reference.md`). Key categories used here: **P — Ready to
  Eat Foods** (P-1..P-6/4), **G — Tomato/Sauces/Spices** (G-2 tomato, G-3 sauces).

## Decisions (from Muhannad, 2026-08-09)

1. **Cooked/grilled/fried/boiled/smoked/charcoal + stuffed → Ready-to-Eat (P)**,
   **blanket** — overrides the standard's own cooked codes (C-9 cooked poultry,
   D-5 smoked/cooked fish, J-8 fried potato, D-8 cooked shellfish, E-1 cooked egg)
   **and** 2024 native codes.
2. **Anything with صوص / صلصة → Sauces (G)** — G-2 for tomato-based, G-3 otherwise.
3. **Applies to BOTH years** (full-consistency; overrides 2024 native codes).
4. **Group A** applied with a normalized-equality false-friend guard.
5. **Group B** resolved by the rules where possible; residue → review doc for sign-off.
6. **Group C** food-named rows → food code; wash-water → N-3.

Confirmed defaults (Muhannad approved the design that carried these):
- Sandwiches → **P-2**, but **P-1** when the name contains salad (سلطة / خس).
- Stuffed محشي (e.g. ملفوف محشي) → **P-6/4** (grouped with ورق عنب mezze).
- Group B residue → **review doc**, not auto-applied.

## Impact (measured on current parquets)

- Names containing a cooking keyword: 497 (2024) + 480 (2025); of these **941**
  are currently non-P and would move to P.
- Names containing صوص/صلصة: 1,048 (2024) + 1,848 (2025) ≈ **2,896** → G.
- ~3,800 rows re-coded across both years. Row totals unchanged (20,881).

## Architecture

A single new function in `microbiology/scripts/enrich_gso.py`,
`apply_gso_name_rules(df, *, year)`, called from the wide-enrichment path **after**
codes are resolved (2024 native / 2025 name-assigned) and **before** category /
`sample_type` derivation, so category, `category_en`, `sample_type`, panel keys,
and the dashboard all follow the overridden code automatically.

Order of operations per wide row:
```
existing gso_code  →  apply_gso_name_rules()  →  (maybe overridden gso_code)
                   →  derive category/category_en/sample_type from final code
```
The 2024 **long** parquet gets the same override on its `gso_code` (keyed by
`sample_id`) so panel-completeness and lab-vs-GSO checks stay consistent with the
wide codes.

### Rule precedence (per row, first match wins)

1. **Cooked / prepared → P** (see keyword table). Cooking-method match takes
   precedence over the sauce rule, so a cooked dish that merely mentions صوص
   (e.g. `بطاطس مقلي بصوص`) stays P, not G.
2. **Sauce → G** (صوص/صلصة).
3. **No rule matches** → keep the existing code (native 2024 / name-assigned 2025).

A new wide column `gso_code_rule_applied` records which rule fired
(`cooked_to_P`, `sauce_to_G`, or empty), for auditability and dashboard filtering.

### Rule 1 — Cooked / prepared → P

**Triggers (any present in the normalized name):**
- Cooking methods (Muhannad-directed): `مقلي` · `مطبوخ` · `مشوي` · `مسلوق` ·
  `مدخن` · `شوي`/`شواية`/`شواء` · `على الفحم` · `محشي`/`محاشي` (+ ة/ه, feminine
  variants handled by normalization).
- Prepared-food nouns that are inherently RTE (proposed extension, resolves
  Group A/B; flag for review): dips & mezze (`حمص`, `متبل`, `بابا غنوج`,
  `ورق عنب`), `فلافل`/`بهاجي`, `سمبوسة`, `كولسلو`, `سبرنغ رول`, sandwiches
  (`ساندويتش`/`ساندوتش`), `شاورما`, `كباب`/`كبة`.

**Sub-code resolution (checked in this order; first hit wins):**
| # | detect | → |
|---|---|---|
| 1 | coleslaw (`كولسلو`) | P-3 |
| 2 | falafel/bhaji (`فلافل`, `بهاجي`) | P-6/1 |
| 3 | samosa/soup/mashed/dessert-tart (`سمبوسة`, `شوربة`, `بطاطس مهروسة`, `تارت`, `فلان`, `كريم كراميل`, `فطيرة حلوة`) | P-6/2 |
| 4 | spring roll / trifle (`سبرنغ رول`, `ترايفل`) | P-6/3 |
| 5 | dips·mezze·stuffed (`حمص`, `متبل`, `بابا غنوج`, `ورق عنب`, `محشي`) | P-6/4 |
| 6 | sandwich/wrap (`ساندويتش`, `ساندوتش`, `رول`) — **P-1** if salad (`سلطة`/`خس`) else | P-2 |
| 7 | rice (`رز`, `أرز`) | P-5 |
| 8 | everything else cooked | **P-4** |

Stuffed (row 5) is checked before rice (row 7) so `ملفوف محشي بالرز` → P-6/4.

### Rule 2 — Sauce → G

- tomato-sauce indicators (`كاتشب`, `صلصة طماطم`, `صلصة بيتزا`) → **G-2**
- else name contains `صوص` or `صلصة` → **G-3**

### Rule 3 — Group A: false-friend-safe spelling-variant assignment

For 2025 rows still uncoded after Rules 1–2, match against the 2024 name→code
table using a **normalized-equality** guard (replaces the manual 8-exclusion list):

`normalize(name)` = lowercase → strip Arabic diacritics/tatweel → `ة→ه`, `ى/ي→ي`
(unify), `أ/إ/آ→ا`, drop leading `ال`, remove spaces and punctuation
(`-`, `.`, `/`, `()[]`, etc.).

Accept the code **only if** `normalize(2025_name) == normalize(2024_name)` **and**
the matched 2024 name carries exactly one code. This rejects the cheese/labneh
(`جبنة`≠`لبنه`), `لحم`/`حمص`, `سلمون`/`ليمون`, `بسبوسة`/`سمبوسة` classes and every
other content-word mismatch automatically. Assigned rows keep the existing flag
`gso_code_assigned_by_name`.

### Rule 4 — Group B: ambiguous multi-code names

Rules 1–2 already resolve the bulk (all صوص → G-3; all cooked/dip → P). For the
genuine residue (e.g. `مربى فراولة` K-1 vs G-3, `بيتزا` I-9 vs P, sweets I-9 vs
L-9), produce `kimi/yolo/2025_gso_groupB_disambiguation.md` with one **proposed**
code per name + row count for Muhannad's one-pass sign-off. **Not auto-applied.**

### Rule 5 — Group C: swab-vs-food (9 rows)

- Food/drink-named rows (`تشيز كيك`→I-9, `سلطة خضراء`→J-1, `رمان حب`→J-1,
  `مشروب كركدية`→O-4, `مشكل مخلل حار`→J-7): reclassify `sample_type` off `swab`
  and let the food code stand (Rules 1–3 / name-match assign it).
- Wash-water rows (`مياه حنفية لغسيل …`, `مياه غسيل ادوات`): set code **N-3**
  ("water for human consumption / unbottled — مياه غسيل" per the GSO example);
  keep them out of the swab bucket. The two `ملحمة سماء القاهرة` / fish-wash cases
  are environmental and consistent with N-3.

## Downstream effects (expected, not bugs)

- Category distribution shifts toward **P (Ready to Eat)** and **G (Sauces)**;
  fewer C/D/J/A rows (esp. 2024, where ~466 cooked rows leave C/D/J and ~1,048
  صوص rows consolidate to G).
- **Panel-completeness** recomputes against the new codes' required-test panels
  (P and G panels differ from C-9/D-5/…). The GSO-audit card numbers will change.
- **Lab-vs-GSO limit** checks re-key to the new codes.
- 2025 coded coverage rises well past 41.6% (cooked + صوص alone add ~1,500 2025
  rows before Group A).

## Testing / verification

1. Row totals unchanged: 20,881 (2024 = 9,317; 2025 = 11,564).
2. Print a **before/after `gso_code` distribution delta** and the count per
   `gso_code_rule_applied` value; assert cooked→P and sauce→G counts match the
   measured ~941 and ~2,896 (±normalization drift).
3. Manual spot-check of **20 reclassified names** per year (mix of cooked, صوص,
   Group A, Group C) — recorded in the clean report.
4. Group A guard: assert **zero** of the 8 known false friends (and the
   cheese/labneh class) get assigned.
5. `node --check` on the extracted dashboard + both sunburst app scripts.
6. Regenerate and report the new 2025 coverage %.

## Deliverables / files touched

- `microbiology/scripts/enrich_gso.py` — `apply_gso_name_rules()`, normalized-equality
  Group A guard, Group C handling, `gso_code_rule_applied` column, 2024 long-parquet override.
- `microbiology/cleaned/data2024.parquet`, `data2024_long.parquet`, `data2025.parquet` — regenerated.
- `microbiology/scripts/build_dashboard_combined.py` — surface `gso_code_rule_applied`
  in the GSO-audit card / explainer (rule-reclassified counts).
- `microbiology/reports/microbiology_dashboard.html`, `microbiology_sunburst.html`,
  `microbiology_sunburst2.html` — rebuilt.
- `kimi/yolo/2025_gso_groupB_disambiguation.md` — new review doc (Group B).
- `microbiology/CHANGELOG.md` — new entry.

## Regeneration order
```bash
cd microbiology
.venv/bin/python scripts/clean_2024.py --year 2024
.venv/bin/python scripts/clean_2025.py "2025-original/Data 2025.xlsx" cleaned/data2025.parquet reports/data2025_diff.md
.venv/bin/python scripts/enrich_gso.py
.venv/bin/python scripts/build_dashboard_combined.py
.venv/bin/python scripts/build_micro_sunburst.py
.venv/bin/python scripts/build_micro_sunburst2.py
```

## Out of scope
- Chemistry (paused / under audit).
- Group B auto-application (needs sign-off first).
- 2025 test-level panel completeness (blocked on lab export — MR item B6).
- GSO panel-scope `optional:true` rulings (MR item B3).
- Official-report reconciliation (MR items B4/B5).
