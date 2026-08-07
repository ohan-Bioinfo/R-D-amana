#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
excluded_samples.py
نظام الاستبعاد العميق على مستوى المنشأة (Facility-Level Deep Exclusion)
يستبعد المنشأة بالكامل إذا سُحب منها عينة لحم أو أعضاء داخلية واحدة على الأقل

آخر تحديث: 2026-03-08
"""

import re

# ============================================================
# أنماط الكلمات المفتاحية المستثناة (Regex Patterns)
# ============================================================

# نمط العينات الخاصة
PRIVATE_SAMPLE_PATTERN = r'(?i)private\s*sample|عين[ةه]\s*خاص[ةه]'

# نمط الأعضاء الداخلية
ORGANS_PATTERN = r'كبد[ةه]|كل[يى][ةه]|كلو[ةه]|كلاوي|قلب|كرش|مصارين|فوارغ|طحال|مخ|لسان'

# نمط اللحوم الحمراء النيئة فقط (عجل، غنم، حاشي، إلخ)
# ملاحظة: الدجاج بجميع أنواعه (نيء أو مطبوخ) لا يُحذف ولا يُحذف بسببه أي منشأة
RAW_MEAT_PATTERN = r'لحم|كباب|حاشي|عجل|غنم|نعيمي|سواكني|بربري|تيس|خروف|خاروف|بتلو|بقر|هندي|باكستاني|كشميري|انقوس|فخذ|كتف|رقب[ةه]|جنب|ضهر|ظهر|ريش|اوصال|شيش|كفت[ةه]|برجر|سجق|مفروم'

# نمط المنشآت المستثناة بالاسم
EXCLUDED_FACILITIES_PATTERN = r'الهلال.*لحوم.*طازج[ةه]'

ALL_EXCLUSION_PATTERNS = [
    PRIVATE_SAMPLE_PATTERN,
    ORGANS_PATTERN,
    RAW_MEAT_PATTERN,
    EXCLUDED_FACILITIES_PATTERN
]

# الأسماء المحتملة لعمود اسم العينة
SAMPLE_COL_NAMES = ['اسم_العينة', 'Sample Name', 'sample_name', 'اسم العينة', 'عينة', 'sample']
# الأسماء المحتملة لعمود اسم المنشأة
FACILITY_COL_NAMES = ['اسم_المنشأة', 'Facility Name', 'facility_name', 'اسم المنشأة', 'منشأة', 'facility']

def find_col(df, candidates):
    """البحث عن اسم العمود من قائمة الأسماء المحتملة"""
    for name in candidates:
        if name in df.columns:
            return name
    # إذا لم يوجد، ابحث بشكل جزئي
    for col in df.columns:
        col_lower = str(col).lower()
        for name in candidates:
            if name.lower() in col_lower or col_lower in name.lower():
                return col
    return None

def should_exclude_value(val):
    """التحقق هل القيمة تحتوي على كلمات مستثناة"""
    if not val or str(val).strip() in ['nan', '', 'None']:
        return False
    val_str = str(val)
    for pattern in ALL_EXCLUSION_PATTERNS:
        if re.search(pattern, val_str, re.IGNORECASE):
            return True
    return False

def filter_excluded_rows(df):
    """
    تطبيق الاستبعاد العميق على مستوى المنشأة:
    1. تحديد المنشآت التي سُحب منها عينة مستثناة (لحوم/أعضاء/إلخ)
    2. حذف هذه المنشآت بالكامل (بكل عيناتها الأخرى)
    """
    if df is None or len(df) == 0:
        return df

    before_total = len(df)

    # البحث عن أعمدة اسم العينة واسم المنشأة
    sample_col = find_col(df, SAMPLE_COL_NAMES)
    facility_col = find_col(df, FACILITY_COL_NAMES)

    print(f"\n[نظام الاستبعاد] أعمدة البيانات: {list(df.columns)}")
    print(f"[نظام الاستبعاد] عمود اسم العينة: '{sample_col}' | عمود اسم المنشأة: '{facility_col}'")

    if facility_col is None or sample_col is None:
        print("[تحذير] لم يتم العثور على أعمدة اسم العينة أو اسم المنشأة - لن يتم تطبيق الاستبعاد")
        return df

    # الخطوة 1: تحديد المنشآت المستثناة
    # أ. منشآت مستثناة بالاسم (مثل الهلال)
    mask_facility_name = df[facility_col].apply(should_exclude_value)
    # ب. منشآت سُحب منها عينات مستثناة (لحوم/أعضاء)
    mask_sample_name = df[sample_col].apply(should_exclude_value)

    # قائمة المنشآت السوداء
    blacklisted = set(df[mask_facility_name | mask_sample_name][facility_col].dropna().unique())

    print(f"[نظام الاستبعاد] عدد المنشآت المستثناة: {len(blacklisted)}")
    if blacklisted:
        examples = list(blacklisted)[:5]
        print(f"[نظام الاستبعاد] أمثلة: {', '.join(str(x) for x in examples)}")

    # الخطوة 2: حذف جميع سجلات هذه المنشآت
    df_filtered = df[~df[facility_col].isin(blacklisted)].copy()

    after_total = len(df_filtered)
    removed_count = before_total - after_total

    print(f"[نظام الاستبعاد] تم حذف {removed_count} صف | المتبقي: {after_total} من أصل {before_total}")

    return df_filtered
