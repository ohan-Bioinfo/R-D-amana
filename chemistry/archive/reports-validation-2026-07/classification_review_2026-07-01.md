# Chemistry classification review — 2026-07-01

Workbook `classification_review_2026-07-01.xlsx` (7 sheets) for your review/guidance.

## GSO 1016 categories (official 15)

- Animal Feed
- Beverages
- Cereals; Legumes and their Products
- Chocolate, Sweets and their Ingredients
- Dairy Products
- Drinking Water
- Egg and Egg Products
- Fats and Oils
- Fish and Shellfish their Products
- Fruit and Vegetables
- Infants, Children and Certain Categories of Dietetic Foods
- Jelly, Jam and Marmalade
- Meat, Poultry and its Products
- Miscellaneous Foods
- Ready to Eat Foods
- Tomato Concentrates, Sauces, Vinegar, Spices and Herbs

## Per-section valid categories — PROPOSED change (aflatoxin)

- **aflatoxins now:** البهارات والصوصات، الحبوب والبقوليات، الحلويات والشوكولاتة
- **aflatoxins PROPOSED:** البهارات والصوصات، الحبوب والبقوليات، الحلويات والشوكولاتة  (review: الفواكه والخضار)
  - Removes RTE / meat / beverage. The 197 'RTE' aflatoxin rows are actually NUTS (لوز/فستق/كاجو) → reclassify to الحبوب والبقوليات by name.

## Name-groups

- Applied: فلتر → «مياه فلتر» ، شط[ةه] → «شطة»
- **PROPOSED:** فلفل → «فلفل» (74 variants / 463 rows fragment the aflatoxin top-10)

## Municipality → sector coverage (chemistry)

- 55 distinct municipality values → mapped after normalization; **15 true-junk values (21 rows)** remain (sample names leaked into the municipality column); 3 private-sample values (168 rows) have no sector.
- Sector column NOW added to the chemistry parquets. Rows with no municipality at all (mostly 2024) get flag `no_municipality` and no sector.

### True-junk municipality values (sample names in wrong column)

  - 460718156294.0  (3 rows)
  - هيل امريكي رقم ٣  (2 rows)
  - بهارات مشكل  (2 rows)
  - كمون سوري  (2 rows)
  - فلفل اسود  (2 rows)
  - حلاوة طحينة - سائل  (1 rows)
  - شطة شامية حارة  (1 rows)
  - قهوة تركي غامق  (1 rows)
  - قهوة هرري وسط  (1 rows)
  - فستق سادة  (1 rows)
  - لوز امريكي ني  (1 rows)
  - زبيب طبخ ذهبي  (1 rows)
  - زبيب اسود افغاني  (1 rows)
  - سمسم ني  (1 rows)
  - سلطة حمراء حارة  (1 rows)