# 2024 GSO panel scope — systematic gaps for sign-off (MR item B3)
**نطاق فحوص GSO — الفجوات المنهجية للاعتماد**

Prepared 2026-08-10. These are the **10 tests** that GSO 1016 lists as required for a
product, but which the lab **(near-)never runs** for it (missing on ≥90% of that
product's 2024 samples). They drive most of the "incomplete panel" flag.

**For each, one decision:**
- **`optional`** → the test is genuinely out of scope for this product. I set
  `optional: true` on it in `schemas/gso_1016_reference.yaml`, and it stops counting
  as a gap.
- **`required`** → it's a real practice gap; the lab should be running it. It stays in
  the panel and remains flagged (a finding to raise with the lab).

**Impact if you mark all 10 `optional`:** incomplete panels drop **4,126 → 3,071**
(1,055 samples clear). The remaining **3,071 are *sporadic*** — tests the lab normally
runs but missed on individual samples (that list is the real "chase the lab" set,
available on request).

| # | code | product | GSO test the lab skips | ran / total | % missing | my note (lab decides) | your call |
|---|---|---|---|---|---:|---|---|
| 1 | I-9 | Cakes & bakery (RTE) | Listeria (الليستيريا) | 3 / 506 | 99% | low-aw baked goods are low Listeria risk; schema note already says "* Optional" |  |
| 2 | C-9 | Frozen cooked poultry | E. coli O157 (ايشيريشيا كولاي O157) | 3 / 428 | 99% | relevant to poultry — scope call |  |
| 3 | C-9 | Frozen cooked poultry | B. cereus (باصلص سيرز) | 4 / 428 | 99% | relevant to poultry — scope call |  |
| 4 | C-9 | Frozen cooked poultry | C. perfringens (كلوستريديوم بيرفرنجنز) | 10 / 428 | 98% | relevant to poultry — scope call |  |
| 5 | L-9 | Arabic sweets | Listeria (الليستيريا) | 0 / 368 | 100% | sugary sweets = low Listeria risk → likely optional |  |
| 6 | P-2 | Sandwiches (no salad) | Total plate count (العد الكلي للبكتيريا) | 7 / 157 | 96% | ⚠️ TPC is a basic hygiene test — skipping it looks like a **real gap** |  |
| 7 | G-2 | Tomato products (ketchup…) | Salmonella (السالمونيلا) | 4 / 94 | 96% | acidic/processed → likely optional |  |
| 8 | A-16 | Ice cream / edible ices | Yeasts & moulds (الخمائر والاعفان) | 0 / 78 | 100% | frozen product → likely optional |  |
| 9 | L-8 | Honey | Sulphite-reducing anaerobes | 0 / 69 | 100% | honey/botulism is a genuine concern — scope call |  |
| 10 | D-1 | Raw fish & products | Aeromonas | 3 / 51 | 94% | Aeromonas is relevant to raw fish — scope call |  |

*Write `optional` or `required` in the last column (or `?` to leave for the lab).*

## How I apply it (on your sign-off)
1. Set `optional: true` on each confirmed test in `schemas/gso_1016_reference.yaml`.
2. One-line fix in `enrich_gso.py` so the required panel excludes optional tests
   (currently it counts them), then re-run `enrich_gso.py` + rebuild the dashboard.
3. The GSO-audit card's "incomplete panel" + systematic-gap numbers update accordingly.

Related: `microbiology/VALIDATION_2026-08-10.md` §5 (B3) · full per-product breakdown
in this session's analysis.
