# Tier 2 review — 2025 GSO code assignment by sample name
**مراجعة المستوى الثاني — تعيين أكواد GSO لعينات 2025 حسب اسم العينة**

Prepared 2026-08-08. **Tier 1 (learned from 2024) is already live**: 4,263 /
11,564 2025 samples coded (36.9%). The names below are the top *remaining*
food samples with no confident match. **Please mark ✔ / ✏️ (correct code) /
✘ (leave uncoded) per row** — approved rows go into `NAME_TO_CODE_2025` in
`microbiology/scripts/enrich_gso.py` on the next enrich run.

Coverage: these 45 names ≈ **1,350 samples** (~12% of 2025). The remaining
~4,370 uncoded food samples are a long tail of rare names; swabs (1,671)
stay correctly uncoded.

## Dips & pickled (مقبلات ومخللات)

| Sample name | Count | Proposed code | Product | Confidence |
|---|---|---|---|---|
| حمص (hummus) | 121 | P-6/4 | Homous, Tzatziki, and other dips | ✔ if the dip |
| متبل (mutabbal) | 81 | P-6/4 | dips | ✔ |
| بابا غنوج | 49 | P-6/4 | dips | ✔ |
| حمص مقبلات | 8 | P-6/4 | dips | ✔ |
| سلطه زبادي (tzatziki) | 14 | P-6/4 | dips | ✔ |
| مخلل خيار (pickles) | 82 | J-7 | Pickled/fermented vegetables | ✔ |
| زيتون كالاماتا (olives) | 8 | J-7 | table olives | ✔ |
| سلطه مكدوس | 13 | J-7 | pickled eggplant | REVIEW |
| لبنه مكدوس | 11 | J-7 | makdous (dairy-pickle) | REVIEW |
| ورق عنب (vine leaves) | 66 | J-7 | brined leaves | REVIEW (or RTE meal) |

## Sauces (صوصات)

| Sample name | Count | Proposed code | Product | Confidence |
|---|---|---|---|---|
| صوص كراميل | 38 | G-3 | other sauces | ✔ |
| سلطه حاره / حمراء حاره (hot sauce) | 30+10 | G-3 | other sauces | ✔ |
| صوص بستاشو | 20 | G-3 | other sauces | ✔ |
| صوص لوتس / وايت شوكولاته / جبن | 9+9+9 | G-3 | other sauces | ✔ |
| صوص ثوم معلب | 8 | G-3 | other sauces | ✔ |

## Salads & fresh produce (سلطات وخضار طازجة)

| Sample name | Count | Proposed code | Product | Confidence |
|---|---|---|---|---|
| سلطه كولسلو | 11 | P-3 | Coleslaw (cabbage) | ✔ exact |
| ملفوف (cabbage) | 10 | J-1 | fresh vegetables | REVIEW |
| قطع برتقال (orange pieces) | 8 | J-1 | fresh fruits | ✔ |
| طماطم مجفف (dried tomato) | 10 | J-2 | dried vegetables | ✔ |
| برسيم (alfalfa) | 9 | J-1 | fresh greens | REVIEW |

## Meat & poultry — raw (لحوم نيئة)

| Sample name | Count | Proposed code | Product | Confidence |
|---|---|---|---|---|
| كباب دجاج ني / (ني) | 24+10 | C-2 | raw poultry | ✔ |
| قطع دجاج | 8 | C-2 | raw poultry | REVIEW (raw or cooked?) |
| كباب لحم ني / (ني) | 27+12 | C-1 | raw meat | REVIEW sub-code |
| لحم يد حاشي / بطن نعيمي بلدي | 9+9 | C-1 | raw meat | REVIEW sub-code |
| كباب لحم (no ني) | 8 | C-1 or C-5 | raw vs cooked | REVIEW |

## Sweets, desserts & flavours (حلويات ونكهات)

| Sample name | Count | Proposed code | Product | Confidence |
|---|---|---|---|---|
| كريم كراميل (flan) | 14 | P-6/2 | desserts (tarts, flans) | ✔ |
| مهلبيه (milk pudding) | 13 | P-6/2 | desserts | REVIEW |
| تشيز كيك فراوله | 8 | I-9 | cakes & bakery RTE | ✔ |
| ايس كريم فانيلا | 12 | A-16 | edible ices | ✔ |
| مربى فراوله (strawberry jam) | 10 | P-8 | jelly/jam | REVIEW |
| نكهه فراوله/باشن فروت/كراميل/ليمون/مانجا | 39+34+15+11+8 | O-? | beverage flavour concentrates | REVIEW — need O sub-code |

## Other

| Sample name | Count | Proposed code | Product | Confidence |
|---|---|---|---|---|
| رز ابيض (white rice) | 16 | P-5 | rice (RTE) | ✔ if cooked |
| بيتزا | 9 | P-4 | RTE meals (pasta/pizza) | ✔ |
| بطاطس مشوي (baked potato) | 8 | P-6/2 | potato dishes | REVIEW |
| كشنه | 8 | ? | unknown dish | REVIEW — what is it? |

---

**After your mark-up:** I fill `NAME_TO_CODE_2025`, re-run
`enrich_gso.py` + the dashboards, and update this doc with final coverage.
