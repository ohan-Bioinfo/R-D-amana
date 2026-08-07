#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
 كود التحليل الإحصائي للفحص الرقابي على المنشآت الغذائية
 Food Safety Inspection Statistical Analysis
=============================================================
 الملف: Data 2025.xlsx
 الأعمدة (A-H):
   A: Sampling Date / تاريخ سحب العينة
   B: Sample Category / فئة العينة
   C: Sample Name / اسم العينة (موحد)
   D: Sample ID / رمز العينة
   E: Facility Name / اسم المنشأة
   F: Municipality name / اسم البلدية
   G: Valid/Invalid / مطابقة/غير مطابقة
   H: Invalid test / الاختبار الغير مطابق (موحد)
=============================================================
 ملاحظة: يتم استثناء الاختبارات التالية من جميع التحليلات:
   - العد الكلي للبكتيريا
   - الخمائر والاعفان
   - خمائر
   - اعفان
 ويتم إعادة حساب حالة المطابقة بعد الاستثناء
=============================================================
 منهجية تقييم المخاطر (معادلة مدمجة مبنية على إطار WHO/Codex):
   Final Risk = (نسبة عدم المطابقة × 0.35) + (شدة الميكروبات × 0.30)
              + (تنوع الميكروبات × 0.20) + (log(إجمالي العينات) × 0.15)
   
   مع معامل تعديل: ×0.5 لعينة واحدة، ×0.75 لعينتين
=============================================================
"""

import pandas as pd
import numpy as np
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

# استيراد قائمة العينات المستثناة والدوال المشتركة
from excluded_samples import filter_excluded_rows


# ============================================================
# الاختبارات المستثناة من التحليل
# ============================================================
EXCLUDED_TESTS = ['العد الكلي للبكتيريا', 'الخمائر والاعفان', 'خمائر', 'اعفان']



# ============================================================
# قاموس خطورة الميكروبات المرضية (مقياس 1-10)
# مبني على تصنيف WHO/FDA لخطورة مسببات الأمراض المنقولة بالغذاء
# ============================================================
MICROBE_RISK_DB = {
    'السالمونيلا': 10,        # حرج - حمى التيفوئيد، قد تكون مميتة
    'استافيلوكوكس اورياس': 8, # عالي - تسمم غذائي حاد
    'ايشيريشيا كولاي': 8,     # عالي - إسهال دموي، فشل كلوي
    'باسيلس سيريس': 7,        # عالي - تسمم غذائي
    'سيدوموناس': 7,           # عالي - عدوى انتهازية خطيرة
    'انتيروباكتريسي': 6,      # متوسط - التهابات معوية
    'كوليفورم': 5,             # متوسط - مؤشر تلوث
}


# ============================================================
# 1. قراءة البيانات وتجهيزها
# ============================================================

def load_data(file_path='Data 2025.xlsx'):
    """قراءة الملف وتسمية الأعمدة"""
    df = pd.read_excel(file_path, sheet_name=0, usecols=range(8), header=None, skiprows=1)
    
    # حذف الصفوف الفارغة بالكامل
    df = df.dropna(how='all').reset_index(drop=True)
    
    # تسمية الأعمدة بأسماء عربية واضحة
    df.columns = [
        'تاريخ_سحب_العينة',
        'فئة_العينة',
        'اسم_العينة',
        'رمز_العينة',
        'اسم_المنشأة',
        'اسم_البلدية',
        'مطابقة',
        'الاختبار_غير_المطابق'
    ]
    
    # تحويل التاريخ
    df['تاريخ_سحب_العينة'] = pd.to_datetime(df['تاريخ_سحب_العينة'], dayfirst=True, errors='coerce')
    # فلتر: الاحتفاظ فقط بتواريخ سنة 2025
    before_filter = len(df)
    df = df[df['تاريخ_سحب_العينة'].dt.year == 2025]
    after_filter = len(df)
    if before_filter != after_filter:
        print(f'تم استبعاد {before_filter - after_filter} صف بتواريخ خارج 2025')
    
    # إضافة أعمدة مساعدة
    df['السنة'] = df['تاريخ_سحب_العينة'].dt.year
    df['الشهر'] = df['تاريخ_سحب_العينة'].dt.month
    df['اسم_الشهر'] = df['تاريخ_سحب_العينة'].dt.month_name()
    
    # تحديد الموسم
    df['الموسم'] = df['الشهر'].apply(get_season)
    
    # استثناء العينات الخاصة والعينات المحددة (لحوم نيئة/أعضاء/دجاج ني/كباب)
    df = filter_excluded_rows(df)
    
    # تنظيف عمود الاختبار
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].fillna('لا يوجد')
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].astype(str).str.strip()
    
    # توحيد أسماء العينات المتشابهة
    df = unify_sample_names(df)
    
    print(f"تم تحميل {len(df):,} صف بنجاح")
    print(f"الفترة: من {df['تاريخ_سحب_العينة'].min()} إلى {df['تاريخ_سحب_العينة'].max()}")
    
    return df


# ============================================================
# توحيد أسماء العينات المتشابهة
# ============================================================

# قاموس يدوي لتوحيد الأسماء المركبة الخاصة
SAMPLE_NAME_MAPPING = {
    'سلطة مشوي': 'سلطة مشاوي',
    'سلطه مشوي': 'سلطة مشاوي',
    'سلطه مشاوي': 'سلطة مشاوي',
    'سلطة مشويات': 'سلطة مشاوي',
    'سلطة خضراء': 'سلطة خضار',
    'سلطه خضراء': 'سلطة خضار',
    'سلطه خضار': 'سلطة خضار',
}

# قائمة المكونات الأساسية التي يجب توحيدها
# إذا كان اسم العينة يحتوي على أحد هذه المكونات مع كلمات وصفية (قطع، شرائح، طازج...) يتم توحيده للاسم الأساسي
BASE_INGREDIENTS = [
    'بقدونس', 'خس', 'طماطم', 'خيار', 'جرجير', 'نعناع', 'كزبرة', 'كزبره',
    'شبت', 'فلفل', 'بصل', 'ثوم', 'زنجبيل', 'ليمون', 'برتقال', 'تفاح',
    'موز', 'عنب', 'فراولة', 'فراوله', 'بطيخ', 'شمام', 'مانجو', 'أناناس',
    'باذنجان', 'كوسا', 'جزر', 'بطاطس', 'بامية', 'باميه', 'ملفوف',
    'كرفس', 'سبانخ', 'روكا', 'فجل',
]

# كلمات وصفية تُحذف عند التوحيد (تصف طريقة التقطيع/التحضير)
DESCRIPTIVE_WORDS = [
    'قطع', 'شرائح', 'مقطع', 'مفروم', 'مبشور', 'مهروس',
    'طازج', 'طازجة', 'طازه', 'مجفف', 'مجمد', 'معلب',
    'كامل', 'كاملة', 'كامله', 'صغير', 'كبير',
    'أخضر', 'أحمر', 'أصفر', 'أبيض',
    'مع', 'بدون', 'من',
]

# قائمة البلديات المستثناة (قيم غير صالحة)
EXCLUDED_MUNICIPALITIES = ['-', '—', '–', '', 'nan', 'None', 'غير محدد']


def unify_sample_names(df):
    """
    توحيد أسماء العينات المتشابهة بكتابات مختلفة.
    
    المنطق:
    1. تطبيق القاموس اليدوي (سلطة مشوي → سلطة مشاوي)
    2. توحيد التاء المربوطة/الهاء
    3. توحيد المكونات الأساسية: "قطع بقدونس" و "بقدونس قطع" و "بقدونس" → "بقدونس"
    """
    import re
    df = df.copy()
    original_unique = df['اسم_العينة'].nunique()
    
    # الخطوة 1: تنظيف أساسي
    df['اسم_العينة'] = df['اسم_العينة'].astype(str).str.strip()
    
    # الخطوة 2: تطبيق القاموس اليدوي
    df['اسم_العينة'] = df['اسم_العينة'].replace(SAMPLE_NAME_MAPPING)
    
    # الخطوة 3: توحيد التاء المربوطة/الهاء
    def normalize_taa(text):
        if pd.isna(text):
            return text
        text = re.sub(r'([\u0621-\u064A])ه(?=\s|$)', r'\1ة', str(text))
        return text.strip()
    
    df['اسم_العينة'] = df['اسم_العينة'].apply(normalize_taa)
    
    # الخطوة 4: توحيد المكونات الأساسية
    # "قطع بقدونس" و "بقدونس قطع" و "بقدونس مع ملفوف" → "بقدونس"
    def normalize_ingredient(name):
        if pd.isna(name):
            return name
        name = str(name).strip()
        # البحث عن المكون الأساسي في اسم العينة
        name_lower = name
        words = name_lower.split()
        
        # إذا كان الاسم كلمة واحدة فقط، لا تغيير
        if len(words) <= 1:
            return name
        
        # البحث عن مكون أساسي في الكلمات
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
        
        # إذا وجدنا مكون أساسي والكلمات الأخرى كلها وصفية
        if found_ingredient:
            all_descriptive = all(
                any(w == dw or w.startswith(dw) for dw in DESCRIPTIVE_WORDS)
                for w in other_words
            ) if other_words else False
            
            if all_descriptive:
                return found_ingredient
        
        return name
    
    df['اسم_العينة'] = df['اسم_العينة'].apply(normalize_ingredient)
    
    new_unique = df['اسم_العينة'].nunique()
    if original_unique != new_unique:
        print(f"  توحيد الأسماء: {original_unique} → {new_unique} نوع عينة (تم دمج {original_unique - new_unique} اسم مكرر)")
    
    return df


def filter_invalid_municipalities(df):
    """
    حذف الصفوف التي اسم البلدية فيها غير صالح (مثل: - أو فارغ)
    """
    original_count = len(df)
    df = df.copy()
    df['اسم_البلدية'] = df['اسم_البلدية'].astype(str).str.strip()
    df = df[~df['اسم_البلدية'].isin(EXCLUDED_MUNICIPALITIES)]
    df = df[df['اسم_البلدية'].str.len() > 1]  # حذف أي قيمة بحرف واحد
    removed = original_count - len(df)
    if removed > 0:
        print(f"  استثناء بلديات غير صالحة: تم حذف {removed} صف باسم بلدية غير صالح")
    return df


def get_season(month):
    """تحديد الموسم بناءً على الشهر"""
    if pd.isna(month):
        return 'غير محدد'
    month = int(month)
    if month in [12, 1, 2]:
        return 'شتاء'
    elif month in [3, 4, 5]:
        return 'ربيع'
    elif month in [6, 7, 8]:
        return 'صيف'
    elif month in [9, 10, 11]:
        return 'خريف'
    return 'غير محدد'


# ============================================================
# 2. تطبيق الاستثناء وإعادة حساب المطابقة
# ============================================================

def apply_exclusion_filter(df):
    """
    استثناء الاختبارات غير المرضية (العد الكلي، الخمائر، الاعفان)
    وإعادة حساب حالة المطابقة لكل عينة.
    """
    df = df.copy()
    
    def filter_tests(test_text):
        """إزالة الاختبارات المستثناة من نص الاختبار"""
        if pd.isna(test_text) or str(test_text).strip() in ['لا يوجد', 'nan', '']:
            return 'لا يوجد'
        
        tests = [t.strip() for t in str(test_text).split('|')]
        filtered = [t for t in tests if t and t != 'لا يوجد' and t not in EXCLUDED_TESTS]
        
        if filtered:
            return ' | '.join(filtered)
        else:
            return 'لا يوجد'
    
    # تطبيق الفلتر على عمود الاختبار
    df['الاختبار_غير_المطابق_أصلي'] = df['الاختبار_غير_المطابق']
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].apply(filter_tests)
    
    # إعادة حساب حالة المطابقة
    df['غير_مطابقة_أصلي'] = df['مطابقة'].astype(str).str.contains(
        'غير|invalid|Invalid|INVALID', case=False, na=False
    ).astype(int)
    
    # إعادة الحساب: غير مطابقة فقط إذا يوجد اختبار مرضي
    df['غير_مطابقة'] = ((df['غير_مطابقة_أصلي'] == 1) & 
                         (df['الاختبار_غير_المطابق'] != 'لا يوجد')).astype(int)
    
    # إحصائيات الاستثناء
    original_invalid = df['غير_مطابقة_أصلي'].sum()
    new_invalid = df['غير_مطابقة'].sum()
    changed = original_invalid - new_invalid
    
    print(f"\n{'='*60}")
    print(f"  تطبيق استثناء الاختبارات غير المرضية")
    print(f"{'='*60}")
    print(f"  الاختبارات المستثناة: {', '.join(EXCLUDED_TESTS)}")
    print(f"  عينات غير مطابقة (قبل الاستثناء): {original_invalid:,}")
    print(f"  عينات غير مطابقة (بعد الاستثناء): {new_invalid:,}")
    print(f"  عينات تحولت إلى مطابقة: {changed:,}")
    print(f"  نسبة عدم المطابقة الأصلية: {original_invalid/len(df)*100:.1f}%")
    print(f"  نسبة عدم المطابقة الجديدة: {new_invalid/len(df)*100:.1f}%")
    print(f"{'='*60}\n")
    
    return df


# ============================================================
# 3. استخراج الاختبارات الفردية من الخلايا المتعددة
# ============================================================

def extract_individual_tests(df):
    """
    استخراج الاختبارات الفردية من عمود الاختبار الموحد
    حيث قد تحتوي الخلية على عدة اختبارات مفصولة بـ |
    """
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
                    'تاريخ_سحب_العينة': row['تاريخ_سحب_العينة'],
                    'فئة_العينة': row['فئة_العينة']
                })
    
    return pd.DataFrame(all_tests)


# ============================================================
# 4. أكثر المنشآت تلوثاً (معادلة WHO المحسنة)
# ============================================================

def top_contaminated_facilities(df, top_n=20):
    """
    تحليل أكثر المنشآت تلوثاً بمعادلة مبنية على إطار WHO/Codex:
    
    درجة المخاطر = نسبة عدم المطابقة (35%) + شدة الميكروبات (30%)
                  + تنوع الميكروبات (20%) + log(إجمالي العينات) (15%)
    
    مع معامل تعديل للمنشآت بأقل من 3 عينات (لتجنب تضخم النسب)
    """
    print("\n" + "="*70)
    print("  أكثر المنشآت تلوثاً - معادلة WHO المحسنة (بكتيريا مرضية فقط)")
    print("="*70)
    print("  المعادلة: نسبة 35% + شدة الميكروبات 30% + تنوع 20% + log(إجمالي العينات) 15%")
    print("="*70)
    
    # إحصائيات لكل منشأة
    facility_stats = df.groupby('اسم_المنشأة').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum'),
        البلدية=('اسم_البلدية', 'first')
    ).reset_index()
    
    facility_stats['نسبة_عدم_المطابقة'] = (
        facility_stats['عينات_غير_مطابقة'] / facility_stats['إجمالي_العينات'] * 100
    ).round(1)
    
    # استخراج الاختبارات المرضية
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    # حساب تنوع الميكروبات لكل منشأة
    if len(tests_df) > 0:
        microbe_diversity = tests_df.groupby('اسم_المنشأة')['الاختبار'].nunique().reset_index()
        microbe_diversity.columns = ['اسم_المنشأة', 'تنوع_الميكروبات']
        facility_stats = facility_stats.merge(microbe_diversity, on='اسم_المنشأة', how='left')
    
    facility_stats['تنوع_الميكروبات'] = facility_stats.get('تنوع_الميكروبات', pd.Series(dtype=float)).fillna(0).astype(int)
    
    # حساب متوسط شدة الميكروبات لكل منشأة (المعيار الأهم)
    severity_scores = {}
    if len(tests_df) > 0:
        for facility in facility_stats['اسم_المنشأة']:
            fac_tests = tests_df[tests_df['اسم_المنشأة'] == facility]
            if len(fac_tests) == 0:
                severity_scores[facility] = 0
                continue
            # حساب متوسط الشدة المرجح بعدد المرات
            total_severity = 0
            total_count = 0
            microbes = fac_tests['الاختبار'].value_counts()
            for microbe, count in microbes.items():
                severity = MICROBE_RISK_DB.get(microbe, 3)  # افتراضي 3 لغير المعروف
                total_severity += severity * count
                total_count += count
            severity_scores[facility] = total_severity / total_count if total_count > 0 else 0
    
    facility_stats['متوسط_شدة_الميكروبات'] = facility_stats['اسم_المنشأة'].map(severity_scores).fillna(0)
    
    # ====== حساب الدرجة المركبة (المعادلة المدمجة) ======
    max_pct = facility_stats['نسبة_عدم_المطابقة'].max() or 1
    max_severity = facility_stats['متوسط_شدة_الميكروبات'].max() or 1
    max_diversity = facility_stats['تنوع_الميكروبات'].max() or 1
    max_log_total = np.log1p(facility_stats['إجمالي_العينات'].max()) or 1
    
    facility_stats['درجة_الخطورة'] = (
        (facility_stats['نسبة_عدم_المطابقة'] / max_pct * 35) +                        # نسبة 35%
        (facility_stats['متوسط_شدة_الميكروبات'] / max_severity * 30) +                 # شدة 30%
        (facility_stats['تنوع_الميكروبات'] / max_diversity * 20) +                      # تنوع 20%
        (np.log1p(facility_stats['إجمالي_العينات']) / max_log_total * 15)               # log(إجمالي) 15%
    ).round(1)
    
    # معامل تعديل للمنشآت بأقل من 3 عينات (لتجنب تضخم النسب)
    # منشأة بعينة واحدة 100% ليست بالضرورة أخطر من منشأة بـ 50 عينة و30%
    facility_stats['معامل_الثقة'] = facility_stats['إجمالي_العينات'].apply(
        lambda x: 0.5 if x == 1 else (0.75 if x == 2 else 1.0)
    )
    facility_stats['درجة_الخطورة'] = (facility_stats['درجة_الخطورة'] * facility_stats['معامل_الثقة']).round(1)
    
    # تصنيف مستوى الخطورة
    facility_stats['مستوى_الخطر'] = facility_stats['درجة_الخطورة'].apply(
        lambda x: 'حرجة' if x >= 70 else ('عالية' if x >= 50 else ('متوسطة' if x >= 30 else 'منخفضة'))
    )
    
    # ترتيب حسب درجة الخطورة
    top_facilities = facility_stats.sort_values('درجة_الخطورة', ascending=False).head(top_n)
    
    print(f"\n{'#':<4} {'اسم المنشأة':<35} {'البلدية':<15} {'إجمالي':<7} {'غ.مطابقة':<9} {'النسبة%':<8} {'تنوع':<5} {'الشدة':<7} {'الدرجة':<8} {'المستوى':<8}")
    print("-" * 120)
    for i, (_, row) in enumerate(top_facilities.iterrows(), 1):
        name = str(row['اسم_المنشأة'])[:33]
        municipality = str(row['البلدية'])[:13]
        print(f"{i:<4} {name:<35} {municipality:<15} {int(row['إجمالي_العينات']):<7} "
              f"{int(row['عينات_غير_مطابقة']):<9} {row['نسبة_عدم_المطابقة']:<8} "
              f"{int(row['تنوع_الميكروبات']):<5} {row['متوسط_شدة_الميكروبات']:.1f}{'':>3} "
              f"{row['درجة_الخطورة']:<8} {row['مستوى_الخطر']:<8}")
    
    return facility_stats.sort_values('درجة_الخطورة', ascending=False)


# ============================================================
# 5. أكثر العينات (المنتجات) تلوثاً - بالنسبة وخطورة الميكروبات
# ============================================================

def top_contaminated_samples(df, top_n=20):
    """
    تحليل أكثر أنواع العينات (المنتجات) تلوثاً
    الترتيب بناءً على المعادلة المدمجة:
    - نسبة عدم المطابقة: 35%
    - شدة الميكروبات المرجحة: 30%
    - تنوع الميكروبات: 20%
    - log(إجمالي العينات): 15%
    
    مع معامل تعديل للعينات بأقل من 3 فحوصات
    """
    print("\n" + "="*70)
    print("  أكثر العينات (المنتجات) تلوثاً - بالنسبة وخطورة الميكروبات")
    print("="*70)
    print("  المعادلة: نسبة 35% + شدة الميكروبات 30% + تنوع 20% + log(إجمالي العينات) 15%")
    print("="*70)
    
    # إحصائيات لكل نوع عينة
    sample_stats = df.groupby('اسم_العينة').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    
    sample_stats['نسبة_عدم_المطابقة'] = (
        sample_stats['عينات_غير_مطابقة'] / sample_stats['إجمالي_العينات'] * 100
    ).round(1)
    
    # استخراج الاختبارات المرضية
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    # حساب تنوع الميكروبات لكل عينة
    if len(tests_df) > 0:
        sample_diversity = tests_df.groupby('اسم_العينة')['الاختبار'].nunique().reset_index()
        sample_diversity.columns = ['اسم_العينة', 'تنوع_الميكروبات']
        sample_stats = sample_stats.merge(sample_diversity, on='اسم_العينة', how='left')
    
    sample_stats['تنوع_الميكروبات'] = sample_stats.get('تنوع_الميكروبات', pd.Series(dtype=float)).fillna(0).astype(int)
    
    # حساب متوسط شدة الميكروبات لكل عينة
    severity_scores = {}
    if len(tests_df) > 0:
        for sample_name in sample_stats['اسم_العينة']:
            samp_tests = tests_df[tests_df['اسم_العينة'] == sample_name]
            if len(samp_tests) == 0:
                severity_scores[sample_name] = 0
                continue
            total_severity = 0
            total_count = 0
            microbes = samp_tests['الاختبار'].value_counts()
            for microbe, count in microbes.items():
                severity = MICROBE_RISK_DB.get(microbe, 3)
                total_severity += severity * count
                total_count += count
            severity_scores[sample_name] = total_severity / total_count if total_count > 0 else 0
    
    sample_stats['متوسط_شدة_الميكروبات'] = sample_stats['اسم_العينة'].map(severity_scores).fillna(0)
    
    # ====== حساب درجة التلوث المركبة (المعادلة المدمجة) ======
    max_pct = sample_stats['نسبة_عدم_المطابقة'].max() or 1
    max_severity = sample_stats['متوسط_شدة_الميكروبات'].max() or 1
    max_diversity = sample_stats['تنوع_الميكروبات'].max() or 1
    max_log_total = np.log1p(sample_stats['إجمالي_العينات'].max()) or 1
    
    sample_stats['درجة_التلوث'] = (
        (sample_stats['نسبة_عدم_المطابقة'] / max_pct * 35) +                        # نسبة 35%
        (sample_stats['متوسط_شدة_الميكروبات'] / max_severity * 30) +                 # شدة 30%
        (sample_stats['تنوع_الميكروبات'] / max_diversity * 20) +                      # تنوع 20%
        (np.log1p(sample_stats['إجمالي_العينات']) / max_log_total * 15)               # log(إجمالي) 15%
    ).round(1)
    
    # معامل تعديل للعينات بأقل من 3 فحوصات
    sample_stats['معامل_الثقة'] = sample_stats['إجمالي_العينات'].apply(
        lambda x: 0.5 if x == 1 else (0.75 if x == 2 else 1.0)
    )
    sample_stats['درجة_التلوث'] = (sample_stats['درجة_التلوث'] * sample_stats['معامل_الثقة']).round(1)
    
    # ترتيب حسب درجة التلوث
    top_samples = sample_stats.sort_values('درجة_التلوث', ascending=False).head(top_n)
    
    print(f"\n{'#':<4} {'اسم العينة':<35} {'إجمالي':<8} {'غ.مطابقة':<9} {'النسبة%':<8} {'تنوع':<5} {'الشدة':<7} {'الدرجة':<8}")
    print("-" * 100)
    for i, (_, row) in enumerate(top_samples.iterrows(), 1):
        name = str(row['اسم_العينة'])[:33]
        print(f"{i:<4} {name:<35} {int(row['إجمالي_العينات']):<8} "
              f"{int(row['عينات_غير_مطابقة']):<9} {row['نسبة_عدم_المطابقة']:<8} "
              f"{int(row['تنوع_الميكروبات']):<5} {row['متوسط_شدة_الميكروبات']:.1f}{'':>3} "
              f"{row['درجة_التلوث']:<8}")
    
    return sample_stats


# ============================================================
# 6. أكثر الاختبارات غير مطابقة
# ============================================================

def top_failed_tests(df, top_n=15):
    """تحليل أكثر الاختبارات (الميكروبات المرضية) غير مطابقة"""
    print("\n" + "="*70)
    print("  أكثر الاختبارات (الميكروبات المرضية) غير مطابقة")
    print("="*70)
    
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    if len(tests_df) == 0:
        print("لا توجد اختبارات غير مطابقة")
        return pd.DataFrame()
    
    test_counts = tests_df['الاختبار'].value_counts().reset_index()
    test_counts.columns = ['الاختبار', 'عدد_المرات']
    test_counts['النسبة%'] = (test_counts['عدد_المرات'] / test_counts['عدد_المرات'].sum() * 100).round(1)
    
    # إضافة درجة الخطورة
    test_counts['درجة_الخطورة'] = test_counts['الاختبار'].map(MICROBE_RISK_DB).fillna(3)
    
    print(f"\n{'#':<4} {'الاختبار/الميكروب':<35} {'عدد المرات':<12} {'النسبة%':<8} {'الخطورة':<8}")
    print("-" * 75)
    for i, (_, row) in enumerate(test_counts.head(top_n).iterrows(), 1):
        print(f"{i:<4} {row['الاختبار']:<35} {int(row['عدد_المرات']):<12} {row['النسبة%']:<8} {int(row['درجة_الخطورة']):<8}")
    
    # تحليل: أي عينات ترتبط بكل ميكروب
    print(f"\n--- أكثر العينات تأثراً بكل ميكروب ---")
    for test in test_counts.head(5)['الاختبار']:
        test_samples = tests_df[tests_df['الاختبار'] == test]['اسم_العينة'].value_counts().head(5)
        print(f"\n  {test}:")
        for sample, count in test_samples.items():
            print(f"    - {sample}: {count} مرة")
    
    return test_counts


# ============================================================
# 7. أكثر المواسم تلوثاً
# ============================================================

def seasonal_analysis(df):
    """تحليل موسمي للتلوث (بكتيريا مرضية فقط)"""
    print("\n" + "="*70)
    print("  التحليل الموسمي للتلوث - بكتيريا مرضية فقط")
    print("="*70)
    
    season_order = ['شتاء', 'ربيع', 'صيف', 'خريف']
    
    season_stats = df.groupby('الموسم').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    
    season_stats['نسبة_عدم_المطابقة'] = (
        season_stats['عينات_غير_مطابقة'] / season_stats['إجمالي_العينات'] * 100
    ).round(1)
    
    # ترتيب حسب المواسم
    season_stats['ترتيب'] = season_stats['الموسم'].map(
        {s: i for i, s in enumerate(season_order)}
    )
    season_stats = season_stats.sort_values('ترتيب').drop('ترتيب', axis=1)
    
    print(f"\n{'الموسم':<12} {'إجمالي العينات':<16} {'غير مطابقة':<14} {'نسبة عدم المطابقة%':<20}")
    print("-" * 65)
    for _, row in season_stats.iterrows():
        print(f"{row['الموسم']:<12} {int(row['إجمالي_العينات']):<16} "
              f"{int(row['عينات_غير_مطابقة']):<14} {row['نسبة_عدم_المطابقة']:<20}")
    
    # أكثر موسم تلوثاً
    worst_season = season_stats.loc[season_stats['نسبة_عدم_المطابقة'].idxmax()]
    print(f"\n>>> أكثر المواسم تلوثاً: {worst_season['الموسم']} "
          f"بنسبة {worst_season['نسبة_عدم_المطابقة']}%")
    
    # تحليل شهري
    print(f"\n--- التحليل الشهري ---")
    month_names_ar = {
        1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
        5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }
    
    monthly_stats = df.groupby('الشهر').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    
    monthly_stats['نسبة_عدم_المطابقة'] = (
        monthly_stats['عينات_غير_مطابقة'] / monthly_stats['إجمالي_العينات'] * 100
    ).round(1)
    monthly_stats['اسم_الشهر'] = monthly_stats['الشهر'].map(month_names_ar)
    
    print(f"\n{'الشهر':<12} {'إجمالي':<10} {'غير مطابقة':<14} {'النسبة%':<8}")
    print("-" * 50)
    for _, row in monthly_stats.sort_values('الشهر').iterrows():
        print(f"{row['اسم_الشهر']:<12} {int(row['إجمالي_العينات']):<10} "
              f"{int(row['عينات_غير_مطابقة']):<14} {row['نسبة_عدم_المطابقة']:<8}")
    
    return season_stats, monthly_stats


# ============================================================
# 8. تحليل البلديات
# ============================================================

def municipality_analysis(df, top_n=15):
    """تحليل التلوث حسب البلديات (بكتيريا مرضية فقط) - بالمعادلة المدمجة"""
    print("\n" + "="*70)
    print("  تحليل التلوث حسب البلديات - بكتيريا مرضية فقط")
    print("="*70)
    
    mun_stats = df.groupby('اسم_البلدية').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    
    mun_stats['نسبة_عدم_المطابقة'] = (
        mun_stats['عينات_غير_مطابقة'] / mun_stats['إجمالي_العينات'] * 100
    ).round(1)
    
    # حساب تنوع الميكروبات لكل بلدية
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    if len(tests_df) > 0:
        mun_diversity = tests_df.groupby('اسم_البلدية')['الاختبار'].nunique().reset_index()
        mun_diversity.columns = ['اسم_البلدية', 'تنوع_الميكروبات']
        mun_stats = mun_stats.merge(mun_diversity, on='اسم_البلدية', how='left')
    mun_stats['تنوع_الميكروبات'] = mun_stats.get('تنوع_الميكروبات', pd.Series(dtype=float)).fillna(0).astype(int)
    
    # حساب متوسط شدة الميكروبات لكل بلدية
    mun_severity = {}
    if len(tests_df) > 0:
        for mun in mun_stats['اسم_البلدية']:
            m_tests = tests_df[tests_df['اسم_البلدية'] == mun]
            if len(m_tests) == 0:
                mun_severity[mun] = 0
                continue
            total_s, total_c = 0, 0
            for microbe, count in m_tests['الاختبار'].value_counts().items():
                total_s += MICROBE_RISK_DB.get(microbe, 3) * count
                total_c += count
            mun_severity[mun] = total_s / total_c if total_c > 0 else 0
    mun_stats['متوسط_الشدة'] = mun_stats['اسم_البلدية'].map(mun_severity).fillna(0)
    
    # المعادلة المدمجة للبلديات
    m_max_pct = mun_stats['نسبة_عدم_المطابقة'].max() or 1
    m_max_sev = mun_stats['متوسط_الشدة'].max() or 1
    m_max_div = mun_stats['تنوع_الميكروبات'].max() or 1
    m_max_log = np.log1p(mun_stats['إجمالي_العينات'].max()) or 1
    
    mun_stats['درجة_الخطورة'] = (
        (mun_stats['نسبة_عدم_المطابقة'] / m_max_pct * 35) +
        (mun_stats['متوسط_الشدة'] / m_max_sev * 30) +
        (mun_stats['تنوع_الميكروبات'] / m_max_div * 20) +
        (np.log1p(mun_stats['إجمالي_العينات']) / m_max_log * 15)
    ).round(1)
    
    # معامل تعديل للبلديات بأقل من 3 عينات
    mun_stats['درجة_الخطورة'] = (mun_stats['درجة_الخطورة'] * mun_stats['إجمالي_العينات'].apply(
        lambda x: 0.5 if x == 1 else (0.75 if x == 2 else 1.0)
    )).round(1)
    
    # ترتيب حسب درجة الخطورة
    top_mun = mun_stats.sort_values('درجة_الخطورة', ascending=False).head(top_n)
    
    print(f"\n{'#':<4} {'البلدية':<25} {'إجمالي':<10} {'غير مطابقة':<14} {'النسبة%':<8} {'الدرجة':<8}")
    print("-" * 80)
    for i, (_, row) in enumerate(top_mun.iterrows(), 1):
        name = str(row['اسم_البلدية'])[:23]
        print(f"{i:<4} {name:<25} {int(row['إجمالي_العينات']):<10} "
              f"{int(row['عينات_غير_مطابقة']):<14} {row['نسبة_عدم_المطابقة']:<8} {row['درجة_الخطورة']:<8}")
    
    return mun_stats


# ============================================================
# 9. ملخص عام
# ============================================================

def general_summary(df):
    """ملخص إحصائي عام (بعد استثناء الاختبارات غير المرضية)"""
    print("\n" + "="*70)
    print("  الملخص الإحصائي العام (بكتيريا مرضية فقط)")
    print("="*70)
    
    total = len(df)
    invalid = df['غير_مطابقة'].sum()
    valid = total - invalid
    
    print(f"\n  إجمالي العينات المفحوصة: {total:,}")
    print(f"  العينات المطابقة: {valid:,} ({valid/total*100:.1f}%)")
    print(f"  العينات غير المطابقة (بكتيريا مرضية): {invalid:,} ({invalid/total*100:.1f}%)")
    print(f"  عدد المنشآت المفحوصة: {df['اسم_المنشأة'].nunique():,}")
    print(f"  عدد البلديات: {df['اسم_البلدية'].nunique():,}")
    print(f"  عدد أنواع العينات: {df['اسم_العينة'].nunique():,}")
    print(f"  عدد فئات العينات: {df['فئة_العينة'].nunique():,}")
    
    if df['تاريخ_سحب_العينة'].notna().any():
        print(f"  الفترة الزمنية: {df['تاريخ_سحب_العينة'].min().strftime('%Y-%m-%d')} "
              f"إلى {df['تاريخ_سحب_العينة'].max().strftime('%Y-%m-%d')}")
    
    # فئات العينات
    print(f"\n--- توزيع فئات العينات ---")
    cat_stats = df.groupby('فئة_العينة').agg(
        إجمالي=('رمز_العينة', 'count'),
        غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    cat_stats['النسبة%'] = (cat_stats['غير_مطابقة'] / cat_stats['إجمالي'] * 100).round(1)
    
    for _, row in cat_stats.sort_values('غير_مطابقة', ascending=False).iterrows():
        print(f"  {row['فئة_العينة']}: {int(row['إجمالي'])} عينة، "
              f"{int(row['غير_مطابقة'])} غير مطابقة ({row['النسبة%']}%)")
    
    return {
        'total': total,
        'invalid': int(invalid),
        'valid': int(valid),
        'facilities': df['اسم_المنشأة'].nunique(),
        'municipalities': df['اسم_البلدية'].nunique(),
        'sample_types': df['اسم_العينة'].nunique()
    }


# ============================================================
# التنفيذ الرئيسي
# ============================================================

if __name__ == '__main__':
    # تحميل البيانات
    df = load_data('Data 2025.xlsx')
    
    # تطبيق استثناء الاختبارات غير المرضية وإعادة حساب المطابقة
    df = apply_exclusion_filter(df)
    
    # استثناء البلديات غير الصالحة (مثل "-")
    df = filter_invalid_municipalities(df)
    
    # الملخص العام
    summary = general_summary(df)
    
    # أكثر المنشآت تلوثاً
    facility_stats = top_contaminated_facilities(df)
    
    # أكثر العينات تلوثاً
    sample_stats = top_contaminated_samples(df)
    
    # أكثر الاختبارات غير مطابقة
    test_stats = top_failed_tests(df)
    
    # التحليل الموسمي
    season_stats, monthly_stats = seasonal_analysis(df)
    
    # تحليل البلديات
    mun_stats = municipality_analysis(df)
    
    # حفظ النتائج في ملف إكسل
    output_file = 'نتائج_التحليل_الإحصائي.xlsx'
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # المنشآت - مرتبة بدرجة الخطورة
        fac_cols = ['اسم_المنشأة', 'البلدية', 'إجمالي_العينات', 'عينات_غير_مطابقة', 
                    'نسبة_عدم_المطابقة', 'تنوع_الميكروبات', 'متوسط_شدة_الميكروبات',
                    'درجة_الخطورة', 'مستوى_الخطر']
        facility_stats.head(50)[fac_cols].to_excel(
            writer, sheet_name='المنشآت_الأكثر_تلوثاً', index=False)
        
        # العينات - مرتبة بدرجة التلوث
        samp_cols = ['اسم_العينة', 'إجمالي_العينات', 'عينات_غير_مطابقة',
                     'نسبة_عدم_المطابقة', 'تنوع_الميكروبات', 'متوسط_شدة_الميكروبات',
                     'درجة_التلوث']
        sample_stats.sort_values('درجة_التلوث', ascending=False).head(50)[samp_cols].to_excel(
            writer, sheet_name='العينات_الأكثر_تلوثاً', index=False)
        
        test_stats.to_excel(writer, sheet_name='الاختبارات_غير_المطابقة', index=False)
        season_stats.to_excel(writer, sheet_name='التحليل_الموسمي', index=False)
        monthly_stats.to_excel(writer, sheet_name='التحليل_الشهري', index=False)
        mun_cols = ['اسم_البلدية', 'إجمالي_العينات', 'عينات_غير_مطابقة',
                    'نسبة_عدم_المطابقة', 'تنوع_الميكروبات', 'متوسط_الشدة', 'درجة_الخطورة']
        mun_stats.sort_values('درجة_الخطورة', ascending=False)[mun_cols].to_excel(
            writer, sheet_name='تحليل_البلديات', index=False)
    
    print(f"\n\nتم حفظ جميع النتائج في: {output_file}")
    print(f"\n{'='*70}")
    print("  منهجية التقييم:")
    print("  المعادلة المدمجة: نسبة 35% + شدة الميكروبات 30% + تنوع 20% + log(إجمالي) 15%")
    print("  * معامل تعديل 0.5 للمنشآت/العينات بعينة واحدة، 0.75 لعينتين")
    print(f"{'='*70}")
