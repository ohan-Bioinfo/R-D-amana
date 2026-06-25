#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
 تقرير تقييم المخاطر الاحترافي للفحص الرقابي
 Professional Risk Assessment Report
=============================================================
 يُنتج تقرير HTML احترافي يشمل:
 - ملخص تنفيذي
 - تصنيف المخاطر للمنشآت
 - تحليل الميكروبات وخطورتها
 - التحليل الموسمي والجغرافي
 - التوصيات والإجراءات التصحيحية
=============================================================
 ملاحظة: يتم استثناء الاختبارات غير المرضية وإعادة حساب المطابقة
=============================================================
"""

import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# استيراد قائمة العينات المستثناة والدوال المشتركة
from excluded_samples import filter_excluded_rows


# ============================================================
# الاختبارات المستثناة من التحليل
# ============================================================
EXCLUDED_TESTS = ['العد الكلي للبكتيريا', 'الخمائر والاعفان', 'خمائر', 'اعفان']




# ============================================================
# 1. قراءة البيانات
# ============================================================

# قاموس توحيد أسماء العينات المتشابهة
SAMPLE_NAME_MAPPING = {
    'سلطة مشوي': 'سلطة مشاوي',
    'سلطه مشوي': 'سلطة مشاوي',
    'سلطه مشاوي': 'سلطة مشاوي',
    'سلطة مشويات': 'سلطة مشاوي',
    'سلطة خضراء': 'سلطة خضار',
    'سلطه خضراء': 'سلطة خضار',
    'سلطه خضار': 'سلطة خضار',
}

BASE_INGREDIENTS = [
    'بقدونس', 'خس', 'طماطم', 'خيار', 'جرجير', 'نعناع', 'كزبرة', 'كزبره',
    'شبت', 'فلفل', 'بصل', 'ثوم', 'زنجبيل', 'ليمون', 'برتقال', 'تفاح',
    'موز', 'عنب', 'فراولة', 'فراوله', 'بطيخ', 'شمام', 'مانجو', 'أناناس',
    'باذنجان', 'كوسا', 'جزر', 'بطاطس', 'بامية', 'باميه', 'ملفوف',
    'كرفس', 'سبانخ', 'روكا', 'فجل',
]

DESCRIPTIVE_WORDS = [
    'قطع', 'شرائح', 'مقطع', 'مفروم', 'مبشور', 'مهروس',
    'طازج', 'طازجة', 'طازه', 'مجفف', 'مجمد', 'معلب',
    'كامل', 'كاملة', 'كامله', 'صغير', 'كبير',
    'أخضر', 'أحمر', 'أصفر', 'أبيض',
    'مع', 'بدون', 'من',
]

EXCLUDED_MUNICIPALITIES = ['-', '—', '–', '', 'nan', 'None', 'غير محدد']


def unify_sample_names(df):
    """توحيد أسماء العينات المتشابهة"""
    import re
    df = df.copy()
    df['اسم_العينة'] = df['اسم_العينة'].astype(str).str.strip()
    df['اسم_العينة'] = df['اسم_العينة'].replace(SAMPLE_NAME_MAPPING)
    def normalize_taa(text):
        if pd.isna(text): return text
        text = re.sub(r'([\u0621-\u064A])ه(?=\s|$)', r'\1ة', str(text))
        return text.strip()
    df['اسم_العينة'] = df['اسم_العينة'].apply(normalize_taa)
    def normalize_ingredient(name):
        if pd.isna(name): return name
        name = str(name).strip()
        words = name.split()
        if len(words) <= 1: return name
        found_ingredient = None
        other_words = []
        for word in words:
            is_ingredient = False
            for ingredient in BASE_INGREDIENTS:
                if word == ingredient or word.startswith(ingredient) or ingredient.startswith(word):
                    found_ingredient = ingredient
                    is_ingredient = True
                    break
            if not is_ingredient:
                other_words.append(word)
        if found_ingredient:
            all_descriptive = all(
                any(w == dw or w.startswith(dw) for dw in DESCRIPTIVE_WORDS)
                for w in other_words
            ) if other_words else False
            if all_descriptive:
                return found_ingredient
        return name
    df['اسم_العينة'] = df['اسم_العينة'].apply(normalize_ingredient)
    return df


def filter_invalid_municipalities(df):
    """حذف الصفوف التي اسم البلدية فيها غير صالح"""
    df = df.copy()
    df['اسم_البلدية'] = df['اسم_البلدية'].astype(str).str.strip()
    df = df[~df['اسم_البلدية'].isin(EXCLUDED_MUNICIPALITIES)]
    df = df[df['اسم_البلدية'].str.len() > 1]
    return df


def load_data(file_path='Data 2025.xlsx'):
    """قراءة البيانات"""
    df = pd.read_excel(file_path, sheet_name=0, usecols=range(8), header=None, skiprows=1)
    df = df.dropna(how='all').reset_index(drop=True)
    df.columns = [
        'تاريخ_سحب_العينة', 'فئة_العينة', 'اسم_العينة', 'رمز_العينة',
        'اسم_المنشأة', 'اسم_البلدية', 'مطابقة', 'الاختبار_غير_المطابق'
    ]
    df['تاريخ_سحب_العينة'] = pd.to_datetime(df['تاريخ_سحب_العينة'], dayfirst=True, errors='coerce')
    # فلتر: الاحتفاظ فقط بتواريخ سنة 2025
    before_filter = len(df)
    df = df[df['تاريخ_سحب_العينة'].dt.year == 2025]
    after_filter = len(df)
    if before_filter != after_filter:
        print(f'تم استبعاد {before_filter - after_filter} صف بتواريخ خارج 2025')
    df['السنة'] = df['تاريخ_سحب_العينة'].dt.year
    df['الشهر'] = df['تاريخ_سحب_العينة'].dt.month
    
    month_names_ar = {
        1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
        5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }
    df['اسم_الشهر'] = df['الشهر'].map(month_names_ar)
    
    def get_season(m):
        if pd.isna(m): return 'غير محدد'
        m = int(m)
        if m in [12, 1, 2]: return 'شتاء'
        elif m in [3, 4, 5]: return 'ربيع'
        elif m in [6, 7, 8]: return 'صيف'
        elif m in [9, 10, 11]: return 'خريف'
        return 'غير محدد'
    
    df['الموسم'] = df['الشهر'].apply(get_season)
    
    # استثناء العينات الخاصة والعينات المحددة (لحوم نيئة/أعضاء/دجاج ني/كباب)
    df = filter_excluded_rows(df)
    
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].fillna('لا يوجد').astype(str).str.strip()
    
    # توحيد أسماء العينات المتشابهة
    df = unify_sample_names(df)
    
    return df


def apply_exclusion_filter(df):
    """
    استثناء الاختبارات غير المرضية وإعادة حساب حالة المطابقة
    """
    df = df.copy()
    
    def filter_tests(test_text):
        if pd.isna(test_text) or str(test_text).strip() in ['لا يوجد', 'nan', '']:
            return 'لا يوجد'
        tests = [t.strip() for t in str(test_text).split('|')]
        filtered = [t for t in tests if t and t != 'لا يوجد' and t not in EXCLUDED_TESTS]
        if filtered:
            return ' | '.join(filtered)
        else:
            return 'لا يوجد'
    
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].apply(filter_tests)
    
    # إعادة حساب حالة المطابقة
    df['غير_مطابقة_أصلي'] = df['مطابقة'].astype(str).str.contains(
        'غير|invalid|Invalid|INVALID', case=False, na=False
    ).astype(int)
    
    df['غير_مطابقة'] = ((df['غير_مطابقة_أصلي'] == 1) & 
                         (df['الاختبار_غير_المطابق'] != 'لا يوجد')).astype(int)
    
    original_invalid = df['غير_مطابقة_أصلي'].sum()
    new_invalid = df['غير_مطابقة'].sum()
    print(f"  تطبيق الاستثناء: غير مطابقة {original_invalid:,} → {new_invalid:,} (تحولت {original_invalid - new_invalid:,} إلى مطابقة)")
    
    return df


def extract_individual_tests(df):
    """استخراج الاختبارات الفردية (المرضية فقط)"""
    all_tests = []
    for idx, row in df.iterrows():
        test_text = str(row['الاختبار_غير_المطابق'])
        if test_text == 'لا يوجد' or test_text == 'nan':
            continue
        tests = [t.strip() for t in test_text.split('|')]
        for test in tests:
            if test and test != 'لا يوجد' and test not in EXCLUDED_TESTS:
                all_tests.append({
                    'الاختبار': test,
                    'اسم_المنشأة': row['اسم_المنشأة'],
                    'اسم_العينة': row['اسم_العينة'],
                    'اسم_البلدية': row['اسم_البلدية'],
                    'الموسم': row['الموسم'],
                    'فئة_العينة': row['فئة_العينة']
                })
    return pd.DataFrame(all_tests)


# ============================================================
# 2. قاموس خطورة الميكروبات (المرضية فقط)
# ============================================================

MICROBE_RISK_DB = {
    'استافيلوكوكس اورياس': {
        'المستوى': 'عالي',
        'الدرجة': 8,
        'الوصف': 'بكتيريا مسببة للتسمم الغذائي عبر إفراز السموم المعوية',
        'المخاطر_الصحية': 'تسمم غذائي حاد (غثيان، قيء، إسهال) خلال 1-6 ساعات من التناول',
        'الإجراء': 'فحص صحة العاملين، تعزيز النظافة الشخصية، مراقبة درجات الحرارة'
    },
    'ايشيريشيا كولاي': {
        'المستوى': 'عالي',
        'الدرجة': 8,
        'الوصف': 'مؤشر على التلوث البرازي، بعض السلالات شديدة الخطورة (O157:H7)',
        'المخاطر_الصحية': 'إسهال دموي، متلازمة انحلال الدم اليوريمي (HUS)، فشل كلوي',
        'الإجراء': 'فحص مصادر المياه، تعزيز غسل اليدين، فصل اللحوم النيئة'
    },
    'السالمونيلا': {
        'المستوى': 'حرج',
        'الدرجة': 10,
        'الوصف': 'من أخطر مسببات الأمراض المنقولة بالغذاء عالمياً',
        'المخاطر_الصحية': 'حمى التيفوئيد، تسمم غذائي شديد، قد تكون مميتة لكبار السن والأطفال',
        'الإجراء': 'إغلاق فوري للمنشأة، تحقيق وبائي، فحص جميع العاملين والمواد الخام'
    },
    'انتيروباكتريسي': {
        'المستوى': 'متوسط',
        'الدرجة': 6,
        'الوصف': 'عائلة بكتيرية تشمل عدة أنواع مسببة للأمراض',
        'المخاطر_الصحية': 'التهابات معوية، عدوى المسالك البولية، قد تسبب تسمم دموي',
        'الإجراء': 'مراجعة إجراءات الطهي والتبريد، فحص المواد الخام'
    },
    'كوليفورم': {
        'المستوى': 'متوسط',
        'الدرجة': 5,
        'الوصف': 'مجموعة بكتيرية مؤشرة على التلوث البيئي أو البرازي',
        'المخاطر_الصحية': 'التهابات معوية، مؤشر على وجود مسببات أمراض أخرى',
        'الإجراء': 'فحص مصادر المياه، تعزيز إجراءات التعقيم'
    },
    'باسيلس سيريس': {
        'المستوى': 'عالي',
        'الدرجة': 7,
        'الوصف': 'بكتيريا مكونة للأبواغ تسبب نوعين من التسمم الغذائي',
        'المخاطر_الصحية': 'تسمم غذائي (نوع القيء خلال 1-5 ساعات، نوع الإسهال خلال 8-16 ساعة)',
        'الإجراء': 'عدم ترك الأرز والنشويات في درجة حرارة الغرفة، تبريد سريع'
    },
    'سيدوموناس': {
        'المستوى': 'عالي',
        'الدرجة': 7,
        'الوصف': 'بكتيريا انتهازية مقاومة للمضادات الحيوية',
        'المخاطر_الصحية': 'عدوى خطيرة لذوي المناعة الضعيفة، التهابات جلدية وتنفسية',
        'الإجراء': 'فحص جودة المياه، تعقيم الأسطح والمعدات'
    }
}


# ============================================================
# 3. حساب تقييم المخاطر للمنشآت
# ============================================================

def calculate_facility_risk(df):
    """حساب درجة المخاطر لكل منشأة (بكتيريا مرضية فقط)"""
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    facility_stats = df.groupby('اسم_المنشأة').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum'),
        البلدية=('اسم_البلدية', 'first')
    ).reset_index()
    
    facility_stats['نسبة_عدم_المطابقة'] = (
        facility_stats['عينات_غير_مطابقة'] / facility_stats['إجمالي_العينات'] * 100
    ).round(1)
    
    # حساب درجة خطورة الميكروبات لكل منشأة
    risk_scores = {}
    microbe_details = {}
    
    if len(tests_df) > 0:
        for facility in facility_stats['اسم_المنشأة']:
            fac_tests = tests_df[tests_df['اسم_المنشأة'] == facility]
            if len(fac_tests) == 0:
                risk_scores[facility] = 0
                microbe_details[facility] = []
                continue
            
            microbes = fac_tests['الاختبار'].value_counts()
            total_risk = 0
            details = []
            for microbe, count in microbes.items():
                risk_info = MICROBE_RISK_DB.get(microbe, {'الدرجة': 3, 'المستوى': 'غير محدد'})
                microbe_risk = risk_info['الدرجة'] * count
                total_risk += microbe_risk
                details.append({
                    'الميكروب': microbe,
                    'العدد': count,
                    'درجة_الخطورة': risk_info['الدرجة'],
                    'المستوى': risk_info['المستوى']
                })
            
            risk_scores[facility] = total_risk
            microbe_details[facility] = details
    
    facility_stats['درجة_خطورة_الميكروبات'] = facility_stats['اسم_المنشأة'].map(risk_scores).fillna(0)
    
    # حساب تنوع الميكروبات
    if len(tests_df) > 0:
        diversity_df = tests_df.groupby('اسم_المنشأة')['الاختبار'].nunique().reset_index()
        diversity_df.columns = ['اسم_المنشأة', 'تنوع_الميكروبات']
        facility_stats = facility_stats.merge(diversity_df, on='اسم_المنشأة', how='left')
    facility_stats['تنوع_الميكروبات'] = facility_stats.get('تنوع_الميكروبات', pd.Series(dtype=float)).fillna(0).astype(int)
    
    # حساب متوسط الشدة المرجح
    severity_avg = {}
    if len(tests_df) > 0:
        for facility in facility_stats['اسم_المنشأة']:
            fac_tests = tests_df[tests_df['اسم_المنشأة'] == facility]
            if len(fac_tests) == 0:
                severity_avg[facility] = 0
                continue
            total_s, total_c = 0, 0
            for microbe, count in fac_tests['الاختبار'].value_counts().items():
                total_s += MICROBE_RISK_DB.get(microbe, {}).get('الدرجة', 3) * count
                total_c += count
            severity_avg[facility] = total_s / total_c if total_c > 0 else 0
    facility_stats['متوسط_الشدة'] = facility_stats['اسم_المنشأة'].map(severity_avg).fillna(0)
    
    # حساب الدرجة المركبة (المعادلة المدمجة)
    max_pct = facility_stats['نسبة_عدم_المطابقة'].max() or 1
    max_severity = facility_stats['متوسط_الشدة'].max() or 1
    max_diversity = facility_stats['تنوع_الميكروبات'].max() or 1
    max_log_total = np.log1p(facility_stats['إجمالي_العينات'].max()) or 1
    
    facility_stats['درجة_المخاطر_الكلية'] = (
        (facility_stats['نسبة_عدم_المطابقة'] / max_pct * 35) +
        (facility_stats['متوسط_الشدة'] / max_severity * 30) +
        (facility_stats['تنوع_الميكروبات'] / max_diversity * 20) +
        (np.log1p(facility_stats['إجمالي_العينات']) / max_log_total * 15)
    ).round(1)
    
    # معامل تعديل للمنشآت بأقل من 3 عينات
    facility_stats['درجة_المخاطر_الكلية'] = (facility_stats['درجة_المخاطر_الكلية'] * facility_stats['إجمالي_العينات'].apply(
        lambda x: 0.5 if x == 1 else (0.75 if x == 2 else 1.0)
    )).round(1)
    
    # تصنيف المخاطر
    def classify_risk(score):
        if score >= 70: return 'حرجة'
        elif score >= 50: return 'عالية'
        elif score >= 30: return 'متوسطة'
        elif score > 0: return 'منخفضة'
        return 'آمنة'
    
    facility_stats['تصنيف_المخاطر'] = facility_stats['درجة_المخاطر_الكلية'].apply(classify_risk)
    
    # إضافة عمود أسماء الميكروبات المكتشفة لكل منشأة
    def get_microbe_names(facility_name):
        details = microbe_details.get(facility_name, [])
        if not details:
            return '-'
        # عرض اسم الميكروب مع عدد المرات
        parts = []
        for d in sorted(details, key=lambda x: x['العدد'], reverse=True):
            if d['العدد'] > 1:
                parts.append(f"{d['الميكروب']} ({d['العدد']})")
            else:
                parts.append(d['الميكروب'])
        return '، '.join(parts)
    
    facility_stats['الميكروبات_المكتشفة'] = facility_stats['اسم_المنشأة'].apply(get_microbe_names)
    
    return facility_stats.sort_values('درجة_المخاطر_الكلية', ascending=False), microbe_details


# ============================================================
# 4. توليد تقرير HTML احترافي
# ============================================================

def generate_html_report(df, output_file='تقرير_تقييم_المخاطر.html'):
    """توليد تقرير HTML احترافي شامل"""
    
    total = len(df)
    invalid_count = df['غير_مطابقة'].sum()
    valid_count = total - invalid_count
    invalid_pct = (invalid_count / total * 100)
    
    # حسابات
    facility_risk, microbe_details = calculate_facility_risk(df)
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    # إحصائيات الميكروبات
    if len(tests_df) > 0:
        microbe_counts = tests_df['الاختبار'].value_counts()
    else:
        microbe_counts = pd.Series(dtype=int)
    
    # إحصائيات موسمية
    season_stats = df.groupby('الموسم').agg(
        إجمالي=('رمز_العينة', 'count'),
        غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    season_stats['نسبة'] = (season_stats['غير_مطابقة'] / season_stats['إجمالي'] * 100).round(1)
    
    # إحصائيات العينات (المنتجات) مع المعادلة المدمجة
    sample_stats = df.groupby('اسم_العينة').agg(
        إجمالي=('رمز_العينة', 'count'),
        غير_مطابقة=('غير_مطابقة', 'sum'),
        عدد_المنشآت=('اسم_المنشأة', 'nunique')
    ).reset_index()
    sample_stats['نسبة'] = (sample_stats['غير_مطابقة'] / sample_stats['إجمالي'] * 100).round(1)
    
    # حساب عدد المنشآت الملوثة لكل منتج
    if len(tests_df) > 0:
        fac_per_sample = tests_df.groupby('اسم_العينة')['اسم_المنشأة'].nunique().reset_index()
        fac_per_sample.columns = ['اسم_العينة', 'منشآت_ملوثة']
        sample_stats = sample_stats.merge(fac_per_sample, on='اسم_العينة', how='left')
    sample_stats['منشآت_ملوثة'] = sample_stats.get('منشآت_ملوثة', pd.Series(dtype=float)).fillna(0).astype(int)
    
    # حساب تنوع الميكروبات لكل منتج
    if len(tests_df) > 0:
        sample_diversity = tests_df.groupby('اسم_العينة')['الاختبار'].nunique().reset_index()
        sample_diversity.columns = ['اسم_العينة', 'تنوع']
        sample_stats = sample_stats.merge(sample_diversity, on='اسم_العينة', how='left')
    sample_stats['تنوع'] = sample_stats.get('تنوع', pd.Series(dtype=float)).fillna(0).astype(int)
    
    # حساب متوسط شدة الميكروبات لكل منتج
    sample_severity = {}
    if len(tests_df) > 0:
        for sname in sample_stats['اسم_العينة']:
            s_tests = tests_df[tests_df['اسم_العينة'] == sname]
            if len(s_tests) == 0:
                sample_severity[sname] = 0
                continue
            total_s, total_c = 0, 0
            for microbe, count in s_tests['الاختبار'].value_counts().items():
                total_s += MICROBE_RISK_DB.get(microbe, {}).get('الدرجة', 3) * count
                total_c += count
            sample_severity[sname] = total_s / total_c if total_c > 0 else 0
    sample_stats['شدة'] = sample_stats['اسم_العينة'].map(sample_severity).fillna(0)
    
    # تطبيق المعادلة المدمجة على العينات
    s_max_pct = sample_stats['نسبة'].max() or 1
    s_max_sev = sample_stats['شدة'].max() or 1
    s_max_div = sample_stats['تنوع'].max() or 1
    s_max_log = np.log1p(sample_stats['إجمالي'].max()) or 1
    
    sample_stats['درجة_التلوث'] = (
        (sample_stats['نسبة'] / s_max_pct * 35) +
        (sample_stats['شدة'] / s_max_sev * 30) +
        (sample_stats['تنوع'] / s_max_div * 20) +
        (np.log1p(sample_stats['إجمالي']) / s_max_log * 15)
    ).round(1)
    
    # معامل تعديل للعينات بأقل من 3 فحوصات
    sample_stats['درجة_التلوث'] = (sample_stats['درجة_التلوث'] * sample_stats['إجمالي'].apply(
        lambda x: 0.5 if x == 1 else (0.75 if x == 2 else 1.0)
    )).round(1)
    
    # إحصائيات البلديات
    mun_stats = df.groupby('اسم_البلدية').agg(
        إجمالي=('رمز_العينة', 'count'),
        غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    mun_stats['نسبة'] = (mun_stats['غير_مطابقة'] / mun_stats['إجمالي'] * 100).round(1)
    
    # أكثر موسم تلوثاً
    worst_season = season_stats.loc[season_stats['نسبة'].idxmax()] if len(season_stats) > 0 else None
    
    # تصنيف المنشآت
    critical_count = len(facility_risk[facility_risk['تصنيف_المخاطر'] == 'حرجة'])
    high_count = len(facility_risk[facility_risk['تصنيف_المخاطر'] == 'عالية'])
    medium_count = len(facility_risk[facility_risk['تصنيف_المخاطر'] == 'متوسطة'])
    low_count = len(facility_risk[facility_risk['تصنيف_المخاطر'] == 'منخفضة'])
    safe_count = len(facility_risk[facility_risk['تصنيف_المخاطر'] == 'آمنة'])
    
    # بناء HTML
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تقرير تقييم المخاطر - الفحص الرقابي على المنشآت الغذائية</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@300;400;500;600;700;800&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Noto Sans Arabic', 'Segoe UI', Tahoma, sans-serif;
            background: #f0f2f5;
            color: #2c3e50;
            line-height: 1.8;
            direction: rtl;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        /* Header */
        .report-header {{
            background: linear-gradient(135deg, #1a5276 0%, #2c3e50 50%, #1a5276 100%);
            color: white;
            padding: 40px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        
        .report-header h1 {{
            font-size: 2.2em;
            margin-bottom: 10px;
            font-weight: 800;
        }}
        
        .report-header .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
            margin-bottom: 15px;
        }}
        
        .report-header .date {{
            font-size: 0.95em;
            opacity: 0.8;
            border-top: 1px solid rgba(255,255,255,0.3);
            padding-top: 15px;
            margin-top: 15px;
        }}
        
        .report-header .note {{
            font-size: 0.85em;
            opacity: 0.7;
            margin-top: 10px;
            font-style: italic;
        }}
        
        /* Summary Cards */
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }}
        
        .card:hover {{
            transform: translateY(-3px);
        }}
        
        .card .number {{
            font-size: 2.5em;
            font-weight: 800;
            margin-bottom: 5px;
        }}
        
        .card .label {{
            font-size: 0.95em;
            color: #7f8c8d;
            font-weight: 500;
        }}
        
        .card.danger .number {{ color: #e74c3c; }}
        .card.success .number {{ color: #27ae60; }}
        .card.warning .number {{ color: #f39c12; }}
        .card.info .number {{ color: #3498db; }}
        
        /* Sections */
        .section {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        
        .section h2 {{
            font-size: 1.5em;
            color: #1a5276;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #3498db;
            font-weight: 700;
        }}
        
        .section h3 {{
            font-size: 1.2em;
            color: #2c3e50;
            margin: 20px 0 10px;
            font-weight: 600;
        }}
        
        .section p {{
            margin-bottom: 12px;
            text-align: justify;
        }}
        
        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 0.9em;
        }}
        
        th {{
            background: #1a5276;
            color: white;
            padding: 12px 15px;
            text-align: right;
            font-weight: 600;
        }}
        
        td {{
            padding: 10px 15px;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        
        tr:hover {{
            background: #eaf2f8;
        }}
        
        /* Risk Badges */
        .risk-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            color: white;
        }}
        
        .risk-critical {{ background: #c0392b; }}
        .risk-high {{ background: #e74c3c; }}
        .risk-medium {{ background: #f39c12; }}
        .risk-low {{ background: #27ae60; }}
        .risk-safe {{ background: #95a5a6; }}
        
        /* Risk Distribution */
        .risk-distribution {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        
        .risk-box {{
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            color: white;
            font-weight: 600;
        }}
        
        .risk-box .count {{
            font-size: 2.5em;
            font-weight: 800;
        }}
        
        .risk-box.critical {{ background: linear-gradient(135deg, #c0392b, #e74c3c); }}
        .risk-box.high {{ background: linear-gradient(135deg, #d35400, #e67e22); }}
        .risk-box.medium {{ background: linear-gradient(135deg, #f39c12, #f1c40f); color: #2c3e50; }}
        .risk-box.low {{ background: linear-gradient(135deg, #27ae60, #2ecc71); }}
        .risk-box.safe {{ background: linear-gradient(135deg, #7f8c8d, #95a5a6); }}
        
        /* Microbe Cards */
        .microbe-card {{
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            border-right: 5px solid;
        }}
        
        .microbe-card.critical {{ border-right-color: #c0392b; }}
        .microbe-card.high {{ border-right-color: #e74c3c; }}
        .microbe-card.medium {{ border-right-color: #f39c12; }}
        .microbe-card.low {{ border-right-color: #27ae60; }}
        
        .microbe-card h4 {{
            font-size: 1.1em;
            margin-bottom: 8px;
            color: #2c3e50;
        }}
        
        .microbe-card .detail {{
            font-size: 0.9em;
            color: #555;
            margin: 5px 0;
        }}
        
        /* Recommendations */
        .recommendation {{
            background: #eaf2f8;
            border-radius: 8px;
            padding: 15px 20px;
            margin: 10px 0;
            border-right: 4px solid #3498db;
        }}
        
        .recommendation.urgent {{
            background: #fdedec;
            border-right-color: #e74c3c;
        }}
        
        .recommendation.important {{
            background: #fef9e7;
            border-right-color: #f39c12;
        }}
        
        /* Footer */
        .report-footer {{
            text-align: center;
            padding: 20px;
            color: #7f8c8d;
            font-size: 0.85em;
            margin-top: 30px;
        }}
        
        /* Print */
        @media print {{
            body {{ background: white; }}
            .container {{ max-width: 100%; }}
            .section {{ box-shadow: none; border: 1px solid #ddd; }}
            .card {{ box-shadow: none; border: 1px solid #ddd; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        
        <!-- Header -->
        <div class="report-header">
            <h1>تقرير تقييم المخاطر</h1>
            <div class="subtitle">الفحص الرقابي على المنشآت الغذائية - البكتيريا المرضية</div>
            <div class="date">
                الفترة: {df['تاريخ_سحب_العينة'].min().strftime('%Y-%m-%d') if df['تاريخ_سحب_العينة'].notna().any() else 'غير محدد'}
                إلى {df['تاريخ_سحب_العينة'].max().strftime('%Y-%m-%d') if df['تاريخ_سحب_العينة'].notna().any() else 'غير محدد'}
                &nbsp;|&nbsp; تاريخ إعداد التقرير: {datetime.now().strftime('%Y-%m-%d')}
            </div>
            <div class="note">
                * تم استثناء اختبارات: العد الكلي للبكتيريا، الخمائر والاعفان، خمائر، اعفان - التحليل يشمل البكتيريا المرضية فقط
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary-cards">
            <div class="card info">
                <div class="number">{total:,}</div>
                <div class="label">إجمالي العينات</div>
            </div>
            <div class="card success">
                <div class="number">{valid_count:,}</div>
                <div class="label">عينات مطابقة</div>
            </div>
            <div class="card danger">
                <div class="number">{invalid_count:,}</div>
                <div class="label">عينات غير مطابقة (بكتيريا مرضية)</div>
            </div>
            <div class="card warning">
                <div class="number">{invalid_pct:.1f}%</div>
                <div class="label">نسبة عدم المطابقة</div>
            </div>
            <div class="card info">
                <div class="number">{df['اسم_المنشأة'].nunique():,}</div>
                <div class="label">منشأة مفحوصة</div>
            </div>
        </div>
        
        <!-- الملخص التنفيذي -->
        <div class="section">
            <h2>الملخص التنفيذي</h2>
            <p>
                يقدم هذا التقرير تقييماً شاملاً للمخاطر بناءً على نتائج الفحص الرقابي لعدد 
                <strong>{total:,}</strong> عينة غذائية تم سحبها من 
                <strong>{df['اسم_المنشأة'].nunique():,}</strong> منشأة غذائية موزعة على 
                <strong>{df['اسم_البلدية'].nunique()}</strong> بلدية.
                يركز هذا التقرير على <strong>البكتيريا المرضية فقط</strong> مع استثناء اختبارات العد الكلي للبكتيريا والخمائر والاعفان.
            </p>
            <p>
                أظهرت النتائج أن <strong>{invalid_pct:.1f}%</strong> من العينات كانت غير مطابقة بسبب بكتيريا مرضية، 
                حيث تم رصد <strong>{invalid_count:,}</strong> عينة غير مطابقة. 
                تم تحديد <strong>{len(microbe_counts)}</strong> نوعاً من البكتيريا المرضية، 
                أبرزها <strong>{microbe_counts.index[0] if len(microbe_counts) > 0 else 'غير محدد'}</strong> 
                بعدد <strong>{microbe_counts.values[0] if len(microbe_counts) > 0 else 0}</strong> حالة.
            </p>
            <p>
                من حيث التصنيف الموسمي، كان فصل 
                <strong>{worst_season['الموسم'] if worst_season is not None else 'غير محدد'}</strong> 
                هو الأكثر تلوثاً بنسبة عدم مطابقة بلغت 
                <strong>{worst_season['نسبة'] if worst_season is not None else 0}%</strong>.
            </p>
        </div>
        
        <!-- توزيع تصنيف المخاطر -->
        <div class="section">
            <h2>توزيع تصنيف المخاطر للمنشآت</h2>
            <p>تم تصنيف المنشآت بناءً على المعادلة المدمجة: نسبة عدم المطابقة (35%) + شدة الميكروبات المرجحة (30%) + تنوع الميكروبات (20%) + log(إجمالي العينات) (15%)، مع معامل تعديل للمنشآت بأقل من 3 عينات.</p>
            
            <div class="risk-distribution">
                <div class="risk-box critical">
                    <div class="count">{critical_count}</div>
                    <div>حرجة</div>
                </div>
                <div class="risk-box high">
                    <div class="count">{high_count}</div>
                    <div>عالية</div>
                </div>
                <div class="risk-box medium">
                    <div class="count">{medium_count}</div>
                    <div>متوسطة</div>
                </div>
                <div class="risk-box low">
                    <div class="count">{low_count}</div>
                    <div>منخفضة</div>
                </div>
                <div class="risk-box safe">
                    <div class="count">{safe_count}</div>
                    <div>آمنة</div>
                </div>
            </div>
        </div>
        
        <!-- أكثر المنشآت خطورة -->
        <div class="section">
            <h2>أكثر المنشآت خطورة (Top 20) - بكتيريا مرضية</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>اسم المنشأة</th>
                        <th>البلدية</th>
                        <th>إجمالي العينات</th>
                        <th>غير مطابقة</th>
                        <th>النسبة%</th>
                        <th>الميكروبات المكتشفة</th>
                        <th>درجة المخاطر</th>
                        <th>التصنيف</th>
                    </tr>
                </thead>
                <tbody>"""
    
    for i, (_, row) in enumerate(facility_risk.head(20).iterrows(), 1):
        risk_class = {
            'حرجة': 'critical', 'عالية': 'high',
            'متوسطة': 'medium', 'منخفضة': 'low', 'آمنة': 'safe'
        }.get(row['تصنيف_المخاطر'], 'safe')
        
        html += f"""
                    <tr>
                        <td>{i}</td>
                        <td>{row['اسم_المنشأة']}</td>
                        <td>{row['البلدية']}</td>
                        <td>{int(row['إجمالي_العينات'])}</td>
                        <td>{int(row['عينات_غير_مطابقة'])}</td>
                        <td>{row['نسبة_عدم_المطابقة']}%</td>
                        <td style="font-size:0.85em;">{row['الميكروبات_المكتشفة']}</td>
                        <td>{row['درجة_المخاطر_الكلية']}</td>
                        <td><span class="risk-badge risk-{risk_class}">{row['تصنيف_المخاطر']}</span></td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <!-- تحليل الميكروبات -->
        <div class="section">
            <h2>تحليل البكتيريا المرضية المكتشفة وخطورتها</h2>
            <p>فيما يلي تحليل تفصيلي لكل نوع من البكتيريا المرضية المكتشفة مع تقييم مستوى الخطورة والمخاطر الصحية والإجراءات التصحيحية المطلوبة.</p>"""
    
    for microbe, count in microbe_counts.items():
        info = MICROBE_RISK_DB.get(microbe, {
            'المستوى': 'غير محدد', 'الدرجة': 3,
            'الوصف': 'ميكروب غير مصنف',
            'المخاطر_الصحية': 'يتطلب تقييم إضافي',
            'الإجراء': 'مراجعة متخصصة'
        })
        risk_class = {
            'حرج': 'critical', 'عالي': 'high',
            'متوسط': 'medium', 'منخفض': 'low'
        }.get(info['المستوى'], 'medium')
        
        html += f"""
            <div class="microbe-card {risk_class}">
                <h4>{microbe} <span class="risk-badge risk-{risk_class}">{info['المستوى']}</span> — عدد الحالات: {count}</h4>
                <div class="detail"><strong>الوصف:</strong> {info['الوصف']}</div>
                <div class="detail"><strong>المخاطر الصحية:</strong> {info['المخاطر_الصحية']}</div>
                <div class="detail"><strong>الإجراء التصحيحي:</strong> {info['الإجراء']}</div>
            </div>"""
    
    html += """
        </div>
        
        <!-- أكثر العينات تلوثاً -->
        <div class="section">
            <h2>أكثر العينات (المنتجات) تلوثاً بالبكتيريا المرضية</h2>
            <p style="font-size:0.9em; color:#666; margin-bottom:10px;">الترتيب بالمعادلة المدمجة: نسبة 35% + شدة 30% + تنوع 20% + log(إجمالي) 15% | معامل تعديل: ×0.5 لعينة واحدة، ×0.75 لعينتين</p>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>اسم العينة</th>
                        <th>إجمالي العينات</th>
                        <th>غير مطابقة</th>
                        <th>نسبة%</th>
                        <th>منشآت ملوثة</th>
                        <th>درجة التلوث</th>
                    </tr>
                </thead>
                <tbody>"""
    
    top_samples = sample_stats.sort_values('درجة_التلوث', ascending=False).head(20)
    for i, (_, row) in enumerate(top_samples.iterrows(), 1):
        html += f"""
                    <tr>
                        <td>{i}</td>
                        <td>{row['اسم_العينة']}</td>
                        <td>{int(row['إجمالي'])}</td>
                        <td>{int(row['غير_مطابقة'])}</td>
                        <td>{row['نسبة']}%</td>
                        <td>{int(row['منشآت_ملوثة'])}</td>
                        <td>{row['درجة_التلوث']}</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <!-- التحليل الموسمي -->
        <div class="section">
            <h2>التحليل الموسمي</h2>
            <table>
                <thead>
                    <tr>
                        <th>الموسم</th>
                        <th>إجمالي العينات</th>
                        <th>غير مطابقة</th>
                        <th>نسبة عدم المطابقة%</th>
                    </tr>
                </thead>
                <tbody>"""
    
    for _, row in season_stats.iterrows():
        highlight = ' style="background:#fdedec; font-weight:bold;"' if worst_season is not None and row['الموسم'] == worst_season['الموسم'] else ''
        html += f"""
                    <tr{highlight}>
                        <td>{row['الموسم']}</td>
                        <td>{int(row['إجمالي'])}</td>
                        <td>{int(row['غير_مطابقة'])}</td>
                        <td>{row['نسبة']}%</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <!-- تحليل البلديات -->
        <div class="section">
            <h2>تحليل البلديات</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>البلدية</th>
                        <th>إجمالي العينات</th>
                        <th>غير مطابقة</th>
                        <th>نسبة عدم المطابقة%</th>
                    </tr>
                </thead>
                <tbody>"""
    
    top_mun = mun_stats.sort_values('نسبة', ascending=False).head(15)
    for i, (_, row) in enumerate(top_mun.iterrows(), 1):
        html += f"""
                    <tr>
                        <td>{i}</td>
                        <td>{row['اسم_البلدية']}</td>
                        <td>{int(row['إجمالي'])}</td>
                        <td>{int(row['غير_مطابقة'])}</td>
                        <td>{row['نسبة']}%</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <!-- التوصيات -->
        <div class="section">
            <h2>التوصيات والإجراءات التصحيحية</h2>
            
            <h3>إجراءات عاجلة (فورية)</h3>
            <div class="recommendation urgent">
                <strong>1. المنشآت ذات التصنيف الحرج:</strong>
                يجب اتخاذ إجراءات فورية تشمل: إيقاف النشاط مؤقتاً، إجراء تحقيق وبائي شامل، 
                فحص جميع العاملين صحياً، وإعادة الفحص خلال 48 ساعة.
            </div>
            <div class="recommendation urgent">
                <strong>2. حالات السالمونيلا:</strong>
                أي منشأة تم رصد السالمونيلا فيها يجب إغلاقها فوراً وإبلاغ الجهات الصحية المختصة 
                وتتبع المنتجات المشتبه بها.
            </div>
            
            <h3>إجراءات مهمة (خلال أسبوع)</h3>
            <div class="recommendation important">
                <strong>3. المنشآت ذات التصنيف العالي:</strong>
                تكثيف الزيارات الرقابية، إلزام المنشآت بخطة تصحيحية موثقة، 
                وإعادة الفحص خلال أسبوعين.
            </div>
            <div class="recommendation important">
                <strong>4. العينات الأكثر تلوثاً:</strong>
                التركيز على مراقبة المنتجات الأكثر تلوثاً وتعزيز الرقابة على سلسلة التوريد الخاصة بها.
            </div>
            
            <h3>إجراءات وقائية (مستمرة)</h3>
            <div class="recommendation">
                <strong>5. التدريب والتوعية:</strong>
                تنفيذ برامج تدريبية للعاملين في المنشآت الغذائية حول ممارسات النظافة الجيدة (GHP) 
                وممارسات التصنيع الجيدة (GMP).
            </div>
            <div class="recommendation">
                <strong>6. المراقبة الموسمية:</strong>"""
    
    if worst_season is not None:
        html += f"""
                تكثيف الرقابة خلال فصل <strong>{worst_season['الموسم']}</strong> الذي سجل أعلى نسبة تلوث ({worst_season['نسبة']}%)، 
                مع التركيز على مراقبة سلسلة التبريد ودرجات الحرارة."""
    
    html += """
            </div>
            <div class="recommendation">
                <strong>7. نظام الإنذار المبكر:</strong>
                تطوير نظام رقمي للإنذار المبكر يربط بين نتائج الفحوصات ويحدد المنشآت عالية الخطورة تلقائياً.
            </div>
            <div class="recommendation">
                <strong>8. تعزيز المختبرات:</strong>
                زيادة القدرة الاستيعابية للمختبرات وتوسيع نطاق الفحوصات لتشمل الملوثات الكيميائية والفيزيائية.
            </div>
        </div>
        
        <!-- Footer -->
        <div class="report-footer">
            <p>تم إعداد هذا التقرير آلياً بواسطة نظام تحليل بيانات سلامة الغذاء</p>
            <p>جميع البيانات والتحليلات مبنية على نتائج الفحوصات المخبرية الرسمية</p>
            <p>* التحليل يشمل البكتيريا المرضية فقط (مستثنى: العد الكلي للبكتيريا، الخمائر والاعفان)</p>
        </div>
        
    </div>
</body>
</html>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"تم إنشاء التقرير: {output_file}")
    return output_file


# ============================================================
# التنفيذ الرئيسي
# ============================================================

if __name__ == '__main__':
    print("="*60)
    print("  إنشاء تقرير تقييم المخاطر (بكتيريا مرضية فقط)")
    print("="*60)
    
    df = load_data('Data 2025.xlsx')
    
    # تطبيق استثناء الاختبارات غير المرضية وإعادة حساب المطابقة
    df = apply_exclusion_filter(df)
    
    # استثناء البلديات غير الصالحة (مثل "-")
    df = filter_invalid_municipalities(df)
    
    # إنشاء التقرير
    report_file = generate_html_report(df, 'تقرير_تقييم_المخاطر.html')
    
    # حفظ بيانات تقييم المخاطر في إكسل
    facility_risk, _ = calculate_facility_risk(df)
    facility_risk.to_excel('تقييم_مخاطر_المنشآت.xlsx', index=False, engine='openpyxl')
    print("تم حفظ بيانات تقييم المخاطر في: تقييم_مخاطر_المنشآت.xlsx")
    
    print(f"\n{'='*60}")
    print("  تم إنشاء التقرير بنجاح!")
    print(f"{'='*60}")
