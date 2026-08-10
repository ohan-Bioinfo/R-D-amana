# Microbiology — Validation & Open Issues (for Muhannad)
**التحقق والمسائل المفتوحة — للمراجعة**

Prepared 2026-08-10. This is your **input file** — fill in the "your answer / your code"
fields, tick the checkboxes, and hand it back; I'll apply your decisions.
Full technical record of what changed is in `microbiology/CHANGELOG.md`
(2026-08-09 (4) + 2026-08-10 entries) and the design spec/plan under
`docs/superpowers/specs|plans/2026-08-09-micro-gso-rule-reclassification*`.

---

## 0. What we just did (record)

A deterministic **name-keyword GSO rule layer** was added to `enrich_gso.py`, applied
to **both years**, and reviewed end-to-end (5 tasks, each independently reviewed;
final whole-branch review caught + fixed 4 keyword bugs). Net result:

| Change | Rows | Effect |
|---|---:|---|
| Cooked/grilled/fried/boiled/smoked/stuffed → **Ready-to-Eat (P)** | 2,239 | blanket (overrides C-9/D-5/J-8/E-1 and 2024 native codes) |
| صوص/صلصة → **Sauces (G-2 tomato / G-3)** | 2,909 | sauce-head wins; dish-with-sauce stays P |
| **Group A** strict normalized-equality (2025) | +111 | false-friend-safe (cheese≠labneh never assigned) |
| **Group C** wash-water → **N-3**; food-named swabs re-typed | 225 | genuine `مسحة` swabs preserved |
| Guards | — | swab samples never reclassified; `محمص`≠`حمص`, `كرز`≠`رز` fixed |

- **2025 GSO coverage: 36.9% → 53.1%.** 2024: 85.4%. Row total unchanged at **20,881**.
- All committed + pushed to `main` (HEAD `c5cdf9d`); dashboards + both sunbursts rebuilt.

---

## 1. VALIDATE the reclassification ✅ (5 min)

Eyeball a sample of what the rules produced. Tick OK or note corrections.

**Cooked → Ready-to-Eat (P):**
| Code | count | examples |
|---|---:|---|
| P-4 (RTE meals) | 991 | بيض مسلوق · شاورما دجاج · بطاطس مقلي · كبة دجاج · باذنجان مطبوخ |
| P-5 (rice) | 161 | رز ابيض مسلوق · رز برياني دجاج · رز مقلي مع دجاج |
| P-6/4 (dips/mezze/stuffed) | 878 | حمص · متبل · ورق عنب · ملفوف محشي · بابا غنوج |
| P-6/2 (samosa/soup/mashed/tart) | 94 | سمبوسة دجاج · تارت فواكة · بطاطس مهروسة |
| P-6/1 (falafel) | 76 | فلافل · فلافل محشي |
| P-2 (sandwich no salad) | 26 | ساندوتش دجاج · ساندوتش سمك |
| P-3 (coleslaw) | 13 | سلطة كولسلو · كولسلو |

**صوص → Sauces:** G-3 (2,686): صوص كراميل · صوص سيزر · صوص هني ماسترد · صوص بستو | G-2 (223): كاتشب · صوص كاتشب

- [ ] Reclassification looks correct as-is.
- [ ] Corrections (list name → the code it should be): _______________________________

**Known edge cases — your ruling:**
| item | now | question | your call |
|---|---|---|---|
| `مرق حمص` (hummus broth/soup) | P-6/4 | soup → P-6/2, or keep dip P-6/4? |  |
| `كبة نية` (raw kibbeh) | P-4 | raw → keep P (RTE), or C-4 (raw minced)? |  |
| `رز محمص` in chocolate (toasted rice) | P-5 | it's a chocolate (L-1), not rice — reclassify? |  |

---

## 2. VALIDATE the 2024 native-code override ⚠️ (important, 10 min)

The "both years" decision means the rules **overrode the lab's own 2024 GSO codes on
2,069 rows** (e.g. a chicken the lab coded C-9 is now P-4). This is intentional per
your ruling, but it shifts 2024 category counts and panel-completeness, and may affect
any reconciliation against 2024 official numbers.

- [ ] Keep 2024 override (full consistency) — confirmed.
- [ ] Actually, apply rules to **2025 only**; leave 2024 native codes intact. (I'll switch it.)
- [ ] Show me the 2,069 affected 2024 rows before I decide.

---

## 3. Group B — code the ambiguous food names 📝 (your input drives coverage)

`kimi/yolo/2025_gso_groupB_disambiguation.md` (regenerated 2026-08-10, **swab names now
excluded**) lists the top 150 real food/drink names still uncoded — **3,751 rows total**.
Fill the `your code` column. Examples of the kind of ambiguity: `بيتزا` (I-9 bakery vs
P-4 RTE meal), `مربى فراولة` (K-1 jam vs G-3), sweets (I-9 vs L-9).

- [ ] I'll mark up the Group B doc and return it.
- [ ] Auto-assign the obvious ones yourself and only ask me about the genuinely unclear.

---

## 4. Group C residuals (2 min)

- **21 / 190 wash-water rows** use spelling variants the keyword list misses, so they
  aren't `N-3` (they keep a reasonable prior class). Fix them?
  - [ ] Yes, add the variants → N-3.  - [ ] Leave as-is.
- **`sample_type = "food"`** (coarse) was set on 5 reclassified food-named swab rows.
  - [ ] Fine.  - [ ] Derive the proper bucket (produce/dairy/…) instead.

---

## 5. Open lab / MR questions (carried forward — still blocking full parity)

These predate this session (`kimi/yolo/MR_REVIEW_REQUEST.md`, `muhannad_open_questions.md`)
and still need answers for further enhancement:

| # | Item | Why it matters | Your answer |
|---|---|---|---|
| B3 | **GSO panel scope** — which rarely-run tests are *optional* per code (14 listed: G-3 C.perfringens, J-1 E.coli O157/Listeria, I-9 Listeria, C-9 multiple, L-8 honey…) | decides how much "incomplete panel" (4,126) is a real gap vs out-of-scope |  |
| B4 | **2025 Annual Report count rule** (11,404 vs our 11,564, +160) | make the 2025 dashboard match the official report |  |
| B5 | **2024 official totals** (samples / compliant / non-compliant), or "none exist" | reconcile 2024 or drop the pending footnote |  |
| B6 | **2025 test-level export** (one row per test: sample·test·result·limit·verdict) | the ONLY route to 2025 panel completeness + limit checks (currently 2024-only) |  |
| B7 | **Tier 2 name review** (`kimi/yolo/2025_gso_code_name_review.md`) | overlaps Group B (§3) — do both together |  |

---

## 6. All issues for enhancement (prioritized backlog)

| P | Issue | Detail | Fix path |
|---|---|---|---|
| High | 2025 test-level data missing | panel-completeness + limit checks are 2024-only | needs **B6** export from LIMS |
| High | Group B backlog | 3,751 non-swab 2025 rows still uncoded (long tail beyond top-150) | your picks (§3) + Tier-1c heuristics |
| Med | 2024 override reconciliation | 2,069 native codes changed — may clash with official 2024 numbers | resolve with **B2/B5** answer (§2) |
| Med | Wash-water keyword completeness | 21 spelling variants miss N-3 | expand `_WASHWATER_KW` (§4) |
| Med | `incomplete panel` interpretation | 4,126 flagged; systematic vs sporadic split exists but scope unconfirmed | **B3** |
| Low | `sample_type "food"` coarse | 5 rows; dashboard falls back to "other" | derive real bucket (§4) |
| Low | Group B doc had swab pollution | fixed 2026-08-10 (swabs excluded) | done |
| Low | Uncoded 2025 swabs (1,674 rows) | correctly outside GSO 1016 — not a bug | none (documented) |

---

### How to return this
Edit this file (tick boxes / fill "your answer" cells) and/or mark up
`kimi/yolo/2025_gso_groupB_disambiguation.md`, then tell me "validation done" —
I'll apply everything and re-run the pipeline + dashboards.
