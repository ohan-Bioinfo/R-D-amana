# Review report: Data 2025.xlsx

This report surfaces edge cases the cleaner flagged but did NOT auto-fix.
Resolve each section by editing the source xlsx or extending the YAML schema.

## Summary

| issue | count | resolution path |
|---|---:|---|
| Source-data conflict: marked VALID but has failed tests | 8 | validity_says_valid_but_has_failures |
| Source-data conflict: marked INVALID but no failed tests listed | 1 | validity_says_invalid_but_no_failures |
| Categories not yet covered by sample_type_buckets (sample_type='other') | 62 | sample_type_unbucketed |
| Failed tests not classified as pathogen or indicator | 0 | test_unclassified |
| Municipality values that didn't match any split rule | 0 | municipality_unrecognised |
| Failed tests not in the canonical test-name list | 0 | invalid_test_unmapped |
| Sample IDs reused for different physical samples (suffixed -a/-b/...) | 22 | sample_id_collision |

**Total review items:** 93

## Source-data conflict: marked VALID but has failed tests

_Count: 8_  ·  _Flag: `validity_says_valid_but_has_failures`_

**How to resolve:** Open the source xlsx at the row, decide which field is correct (validity column or invalid-tests column), and patch the source. The cleaner won't auto-pick a winner.

| row_excel | sample_id | sampling_date | facility_chain | category_canonical | is_valid | n_failed_tests | invalid_tests |
|---:|---|---|---|---|---|---:|---|
| 58 | sau-1038-r01 | 2025-01-05 | فلافل ذوق | صوص (sauce) | True | 1 | الخمائر والاعفان |
| 2949 | sau-1366-r01 | 2025-04-13 | استليتا | (Sausage) نقانق | True | 1 | العد الكلي للبكتيريا |
| 4269 | sw-3033-r01 | 2025-11-05 | ازيان هاوز | (Swabs) المسحات | True | 1 | العد الكلي للبكتيريا |
| 5356 | ubot-0992-r01 | 2025-06-17 | معرض الوطنيه | المياه الغير معبأة (Unbottled water) | True | 2 | كوليفورم, سيدوموناس |
| 7286 | 1-3347-R01 | 2025-09-08 | مشاغيث | ( Luqaimat) لقيمات | True | 1 | كوليفورم |
| 8716 | sal-1635-r01 | 2025-09-20 | شركه مطاعم ركن هاشم | السلطة(Salad) | True | 1 | استافيلوكوكس اورياس |
| 9209 | ubot-1107-r01 | 2025-10-12 | اسواق التين المركزية | المياه الغير معبأة (Unbottled water) | True | 2 | كوليفورم, سيدوموناس |
| 10412 | ca-0078-r01 | 2025-11-22 | مصدر الكافيين | الكعك ومنتجات المخابز الجاهزة للاكل بدون تسخين (Ca | True | 1 | باسيلس سيريس |

## Source-data conflict: marked INVALID but no failed tests listed

_Count: 1_  ·  _Flag: `validity_says_invalid_but_no_failures`_

**How to resolve:** Same as above — manual reconciliation against the source xlsx.

| row_excel | sample_id | sampling_date | facility_chain | category_canonical | is_valid | n_failed_tests | invalid_tests |
|---:|---|---|---|---|---|---:|---|
| 1808 | OU-pa-0212-R01 | 2025-03-03 | بيت الحمص (شركة الراجحي الغذائية) | البقدونس (parsley) | False | 0 |  |

## Categories not yet covered by sample_type_buckets (sample_type='other')

_Count: 62_  ·  _Flag: `sample_type_unbucketed`_

**How to resolve:** Add the category's distinguishing keyword(s) to the right bucket in `schemas/lab_data_2025_v1.yaml` → `sample_type_buckets`. Re-run the cleaner.

| value | count |
|---|---:|
| 'البامية (okra)' | 3 |
| 'المحاشي (almahashi)' | 3 |
| 'الملوخية (Jute mallow)' | 2 |
| '(Shira) شيرة' | 2 |
| 'الالبان (Dairy)' | 2 |
| 'التوت (berries)' | 2 |
| 'افوكادو(avocado)' | 2 |
| 'ايدام مصقع' | 1 |
| 'ايدام مشكل فرن' | 1 |
| 'تراميسو' | 1 |
| 'تشيز ايسكريم' | 1 |
| 'حلا لايك' | 1 |
| 'كريم كراميل' | 1 |
| '(Waffle) وافل' | 1 |
| 'الزيت القلي' | 1 |
| 'ربيان' | 1 |
| '(Kofta) كفتة' | 1 |
| '(Halloumi) حلومي' | 1 |
| 'الصنوبر (Pine)' | 1 |
| 'كبة جاج' | 1 |
| 'تبولة' | 1 |
| 'حلا مانجا' | 1 |
| 'حلا فراولة' | 1 |
| 'حلا ام علي' | 1 |
| 'بابا غنوج' | 1 |
| 'مصقع' | 1 |
| 'مشكل فرن' | 1 |
| 'بيتي فور' | 1 |
| 'العنب (Grapes)' | 1 |
| 'شابورا بر شرايح' | 1 |
| '(chips) شبس' | 1 |
| 'الجوافة (Guava)' | 1 |
| 'فجل مبشور' | 1 |
| 'قطع مانجا' | 1 |
| 'افوكادو' | 1 |
| 'زهرة مقلية' | 1 |
| '(turkey) ديك رومي' | 1 |
| 'الكرفس (Celery)' | 1 |
| 'ملحمة سماء القاهرة' | 1 |
| 'فشار مالح' | 1 |
| 'فشار كراميل' | 1 |
| 'فشار سبايسي' | 1 |
| 'فشار مالح مكس ناتشوز' | 1 |
| 'شيدر تشيز وايت' | 1 |
| 'شيدر تشيز يلو' | 1 |
| 'باربكيو' | 1 |
| 'الخوخ (Peaches)' | 1 |
| '(Seasoning) تتبيلة' | 1 |
| '(shrimp) روبيان' | 1 |
| 'القمح (wheat)' | 1 |

_…+1 more distinct values_

## Sample IDs reused for different physical samples (suffixed -a/-b/...)

_Count: 22_  ·  _Flag: `sample_id_collision`_

**How to resolve:** These are kept with disambiguating suffixes. If an ID was reused at the lab, no fix needed — the suffix handles it. If a true bug, fix at source.

| row_excel | sample_id | sampling_date | facility_chain | category_canonical | is_valid | n_failed_tests | invalid_tests |
|---:|---|---|---|---|---|---:|---|
| 562 | so-0004-r01-a | 2025-01-20 | مطعم دار مبارك | Soup (all kinds) Samosa, Mashed potato, Desserts. | False | 1 | العد الكلي للبكتيريا |
| 8952 | so-0004-r01-b | 2025-10-04 | شركة النحلات الثلاثة الفندقية مساهمة مقف | (Soft Cheese) جبن طري / جبن سائل | True | 0 |  |
| 826 | so-0005-r01-a | 2025-02-01 | مطعم فيجن البخاري | Soup (all kinds) Samosa, Mashed potato, Desserts. | False | 1 | العد الكلي للبكتيريا |
| 8966 | so-0005-r01-b | 2025-10-04 | شركة النحلات الثلاثة الفندقية مساهمة مقف | (Soft Cheese) جبن طري / جبن سائل | False | 1 | استافيلوكوكس اورياس |
| 2167 | so-0007-r01-a | 2025-03-15 | شركة مطاعم الناضج | Soup (all kinds) Samosa, Mashed potato, Desserts. | True | 0 |  |
| 10231 | so-0007-r01-b | 2025-11-16 | فندق هوليدي ان | (Soft Cheese) جبن طري / جبن سائل | True | 0 |  |
| 10470 | he-0010-r01-a | 2025-11-23 | افاقيKAFFIX | (Swabs) المسحات | True | 0 |  |
| 10615 | he-0010-r01-b | 2025-11-23 | افاقيKAFFIX | الأعشاب المجففة (Dried herbs ) | True | 0 |  |
| 10781 | cho-0111-r01-a | 2025-12-01 | مقهى فليم | الشوكولاته (Chocolate) | True | 0 |  |
| 10829 | cho-0111-r01-b | 2025-12-01 | مقهى فليم | الشوكولاته (Chocolate) | True | 0 |  |
| 10782 | ca-0137-r01-a | 2025-12-01 | مقهى فليم | الحلويات العربية (Arabic sweets) | True | 0 |  |
| 10830 | ca-0137-r01-b | 2025-12-01 | مقهى فليم | الكعك ومنتجات المخابز الجاهزة للاكل بدون تسخين (Ca | True | 0 |  |
| 10783 | sa-0961-r01-a | 2025-12-01 | مقهى فليم | اطعمة جاهزة للأكل Ready to eat meals | False | 1 | استافيلوكوكس اورياس |
| 10831 | sa-0961-r01-b | 2025-12-01 | مقهى فليم | اطعمة جاهزة للأكل Ready to eat meals | True | 0 |  |
| 10785 | sa-0963-r01-a | 2025-12-01 | مقهى فليم | اطعمة جاهزة للأكل Ready to eat meals | False | 1 | العد الكلي للبكتيريا |
| 10833 | sa-0963-r01-b | 2025-12-01 | مقهى فليم | اطعمة جاهزة للأكل Ready to eat meals | True | 0 |  |
| 10788 | ca-0140-r01-a | 2025-12-01 | مقهى فليم | الكعك ومنتجات المخابز الجاهزة للاكل بدون تسخين (Ca | False | 1 | العد الكلي للبكتيريا |
| 10836 | ca-0140-r01-b | 2025-12-01 | مقهى فليم | الكعك ومنتجات المخابز الجاهزة للاكل بدون تسخين (Ca | True | 0 |  |
| 10790 | coff-1072-r01-a | 2025-12-01 | مقهى فليم | القهوة ومشتقاتها (Coffee and derivatives) | False | 1 | الخمائر والاعفان |
| 10838 | coff-1072-r01-b | 2025-12-01 | مقهى فليم | القهوة ومشتقاتها (Coffee and derivatives) | True | 0 |  |
| 10791 | milk-0059-r01-a | 2025-12-01 | مقهى فليم | الحليب (Milk) | False | 2 | العد الكلي للبكتيريا, انتيروباكتريسي |
| 10839 | milk-0059-r01-b | 2025-12-01 | مقهى فليم | الحليب (Milk) | True | 0 |  |
