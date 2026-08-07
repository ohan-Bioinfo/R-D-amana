# -*- coding: utf-8 -*-
"""
=============================================================
 تقارير إضافية - ملف إكسل منفصل
 Extra Reports - Separate Excel File
=============================================================
 شيت 1: البلديات وعدد المنشآت المغطاة في كل بلدية
 شيت 2: أنواع العينات التي ظهرت فيها سالمونيلا وعدد المرات
=============================================================
"""

import pandas as pd
import numpy as np
import re
import warnings
warnings.filterwarnings('ignore')

# استيراد قائمة العينات المستثناة والدوال المشتركة
from excluded_samples import filter_excluded_rows


# ============================================================
# الاختبارات المستثناة
# ============================================================
EXCLUDED_TESTS = ['العد الكلي للبكتيريا', 'الخمائر والاعفان', 'خمائر', 'اعفان']




# ============================================================
# توحيد أسماء العينات
# ============================================================
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


# ============================================================
# دوال التنظيف
# ============================================================

def unify_sample_names(df):
    """توحيد أسماء العينات المتشابهة"""
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


# ============================================================
# قراءة البيانات
# ============================================================

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
    # استثناء العينات الخاصة والعينات المحددة (لحوم نيئة/أعضاء/دجاج ني/كباب)
    df = filter_excluded_rows(df)
    
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].fillna('لا يوجد').astype(str).str.strip()
    
    # توحيد أسماء العينات
    df = unify_sample_names(df)
    
    return df


def apply_exclusion_filter(df):
    """استثناء الاختبارات غير المرضية وإعادة حساب المطابقة"""
    df = df.copy()
    
    def filter_tests(test_text):
        if pd.isna(test_text) or str(test_text).strip() in ['لا يوجد', 'nan', '']:
            return 'لا يوجد'
        tests = [t.strip() for t in str(test_text).split('|')]
        filtered = [t for t in tests if t and t != 'لا يوجد' and t not in EXCLUDED_TESTS]
        return ' | '.join(filtered) if filtered else 'لا يوجد'
    
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].apply(filter_tests)
    
    df['غير_مطابقة_أصلي'] = df['مطابقة'].astype(str).str.contains(
        'غير|invalid|Invalid|INVALID', case=False, na=False
    ).astype(int)
    
    df['غير_مطابقة'] = ((df['غير_مطابقة_أصلي'] == 1) & 
                         (df['الاختبار_غير_المطابق'] != 'لا يوجد')).astype(int)
    
    original_invalid = df['غير_مطابقة_أصلي'].sum()
    new_invalid = df['غير_مطابقة'].sum()
    print(f"  تطبيق الاستثناء: غير مطابقة {original_invalid:,} → {new_invalid:,} (تحولت {original_invalid - new_invalid:,} إلى مطابقة)")
    
    return df


# ============================================================
# شيت 1: البلديات وعدد المنشآت المغطاة
# ============================================================

def municipalities_facilities_report(df):
    """
    إنشاء تقرير البلديات وعدد المنشآت المغطاة في كل بلدية
    """
    print("\n" + "="*70)
    print("  البلديات وعدد المنشآت المغطاة")
    print("="*70)
    
    mun_stats = df.groupby('اسم_البلدية').agg(
        عدد_المنشآت=('اسم_المنشأة', 'nunique'),
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    
    mun_stats['نسبة_عدم_المطابقة%'] = (
        mun_stats['عينات_غير_مطابقة'] / mun_stats['إجمالي_العينات'] * 100
    ).round(1)
    
    # متوسط عدد العينات لكل منشأة
    mun_stats['متوسط_العينات_لكل_منشأة'] = (
        mun_stats['إجمالي_العينات'] / mun_stats['عدد_المنشآت']
    ).round(1)
    
    # ترتيب حسب عدد المنشآت تنازلياً
    mun_stats = mun_stats.sort_values('عدد_المنشآت', ascending=False)
    
    # طباعة النتائج
    print(f"\n{'#':<4} {'البلدية':<25} {'عدد المنشآت':<14} {'إجمالي العينات':<16} {'غير مطابقة':<14} {'النسبة%':<8}")
    print("-" * 90)
    for i, (_, row) in enumerate(mun_stats.iterrows(), 1):
        name = str(row['اسم_البلدية'])[:23]
        print(f"{i:<4} {name:<25} {int(row['عدد_المنشآت']):<14} {int(row['إجمالي_العينات']):<16} "
              f"{int(row['عينات_غير_مطابقة']):<14} {row['نسبة_عدم_المطابقة%']:<8}")
    
    # إجمالي
    print("-" * 90)
    print(f"{'':>4} {'الإجمالي':<25} {int(mun_stats['عدد_المنشآت'].sum()):<14} "
          f"{int(mun_stats['إجمالي_العينات'].sum()):<16} {int(mun_stats['عينات_غير_مطابقة'].sum()):<14}")
    
    return mun_stats


# ============================================================
# شيت 2: العينات التي ظهرت فيها سالمونيلا
# ============================================================

def salmonella_samples_report(df):
    """
    إنشاء تقرير أنواع العينات التي ظهرت فيها سالمونيلا وعدد المرات
    """
    print("\n" + "="*70)
    print("  أنواع العينات التي ظهرت فيها سالمونيلا")
    print("="*70)
    
    # البحث عن السالمونيلا في عمود الاختبارات غير المطابقة
    # تشمل: السالمونيلا، سالمونيلا، Salmonella بجميع أشكالها
    salmonella_keywords = ['سالمونيلا', 'السالمونيلا', 'salmonella', 'Salmonella']
    
    def has_salmonella(test_text):
        if pd.isna(test_text) or str(test_text).strip() in ['لا يوجد', 'nan', '']:
            return False
        text = str(test_text).lower()
        for keyword in salmonella_keywords:
            if keyword.lower() in text:
                return True
        return False
    
    # تصفية العينات التي تحتوي على سالمونيلا
    df_salmonella = df[df['الاختبار_غير_المطابق'].apply(has_salmonella)].copy()
    
    if len(df_salmonella) == 0:
        print("\n  لم يتم العثور على أي عينات تحتوي على سالمونيلا")
        return pd.DataFrame()
    
    print(f"\n  إجمالي العينات التي ظهرت فيها سالمونيلا: {len(df_salmonella)}")
    
    # تجميع حسب نوع العينة
    salmonella_by_sample = df_salmonella.groupby('اسم_العينة').agg(
        عدد_مرات_الظهور=('رمز_العينة', 'count'),
        عدد_المنشآت=('اسم_المنشأة', 'nunique'),
        عدد_البلديات=('اسم_البلدية', 'nunique'),
    ).reset_index()
    
    # إضافة أسماء المنشآت التي ظهرت فيها
    facility_names = df_salmonella.groupby('اسم_العينة')['اسم_المنشأة'].apply(
        lambda x: ' | '.join(x.unique()[:5])  # أول 5 منشآت كحد أقصى
    ).reset_index()
    facility_names.columns = ['اسم_العينة', 'المنشآت_المتأثرة']
    
    salmonella_by_sample = salmonella_by_sample.merge(facility_names, on='اسم_العينة', how='left')
    
    # إضافة أسماء البلديات
    mun_names = df_salmonella.groupby('اسم_العينة')['اسم_البلدية'].apply(
        lambda x: ' | '.join(x.unique())
    ).reset_index()
    mun_names.columns = ['اسم_العينة', 'البلديات']
    
    salmonella_by_sample = salmonella_by_sample.merge(mun_names, on='اسم_العينة', how='left')
    
    # ترتيب حسب عدد مرات الظهور تنازلياً
    salmonella_by_sample = salmonella_by_sample.sort_values('عدد_مرات_الظهور', ascending=False)
    
    # حساب النسبة من إجمالي ظهور السالمونيلا
    total_salmonella = salmonella_by_sample['عدد_مرات_الظهور'].sum()
    salmonella_by_sample['النسبة_من_الإجمالي%'] = (
        salmonella_by_sample['عدد_مرات_الظهور'] / total_salmonella * 100
    ).round(1)
    
    # طباعة النتائج
    print(f"\n{'#':<4} {'نوع العينة':<30} {'عدد المرات':<12} {'النسبة%':<8} {'المنشآت':<10} {'البلديات':<10}")
    print("-" * 85)
    for i, (_, row) in enumerate(salmonella_by_sample.iterrows(), 1):
        name = str(row['اسم_العينة'])[:28]
        print(f"{i:<4} {name:<30} {int(row['عدد_مرات_الظهور']):<12} {row['النسبة_من_الإجمالي%']:<8} "
              f"{int(row['عدد_المنشآت']):<10} {int(row['عدد_البلديات']):<10}")
    
    print(f"\n  الإجمالي: {total_salmonella} ظهور للسالمونيلا في {len(salmonella_by_sample)} نوع عينة")
    
    # ترتيب الأعمدة للإكسل
    salmonella_by_sample = salmonella_by_sample[[
        'اسم_العينة', 'عدد_مرات_الظهور', 'النسبة_من_الإجمالي%',
        'عدد_المنشآت', 'عدد_البلديات', 'المنشآت_المتأثرة', 'البلديات'
    ]]
    
    return salmonella_by_sample


# ============================================================
# التنفيذ الرئيسي
# ============================================================

if __name__ == '__main__':
    print("="*60)
    print("  إنشاء التقارير الإضافية")
    print("="*60)
    
    # تحميل البيانات
    df = load_data('Data 2025.xlsx')
    
    # تطبيق استثناء الاختبارات غير المرضية
    df = apply_exclusion_filter(df)
    
    # استثناء البلديات غير الصالحة
    df = filter_invalid_municipalities(df)
    
    # شيت 1: البلديات وعدد المنشآت
    mun_facilities = municipalities_facilities_report(df)
    
    # شيت 2: السالمونيلا حسب نوع العينة
    salmonella_report = salmonella_samples_report(df)
    
    # حفظ في ملف إكسل
    output_file = 'تقارير_إضافية.xlsx'
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # شيت البلديات
        mun_cols = ['اسم_البلدية', 'عدد_المنشآت', 'إجمالي_العينات', 
                    'عينات_غير_مطابقة', 'نسبة_عدم_المطابقة%', 'متوسط_العينات_لكل_منشأة']
        mun_facilities[mun_cols].to_excel(
            writer, sheet_name='البلديات_والمنشآت', index=False)
        
        # شيت السالمونيلا
        if len(salmonella_report) > 0:
            salmonella_report.to_excel(
                writer, sheet_name='عينات_السالمونيلا', index=False)
        
        # تنسيق عرض الأعمدة
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_length = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                ws.column_dimensions[col_letter].width = min(max_length + 4, 50)
    
    print(f"\n{'='*60}")
    print(f"  تم حفظ التقارير الإضافية في: {output_file}")
    print(f"  الشيتات:")
    print(f"    1. البلديات_والمنشآت - عدد المنشآت المغطاة في كل بلدية")
    print(f"    2. عينات_السالمونيلا - أنواع العينات التي ظهرت فيها سالمونيلا")
    print(f"{'='*60}")
