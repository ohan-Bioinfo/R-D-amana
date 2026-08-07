#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
 كود الرسوم البيانية للفحص الرقابي على المنشآت الغذائية
 Food Safety Inspection Charts & Visualizations
=============================================================
 يدعم اللغة العربية بالكامل في جميع الرسوم
=============================================================
 ملاحظة: يتم استثناء الاختبارات غير المرضية وإعادة حساب المطابقة
 الترتيب بناءً على معادلة WHO المحسنة (النسبة + شدة الميكروبات)
=============================================================
"""

import pandas as pd
import numpy as np
import os
import sys
import subprocess

# استيراد قائمة العينات المستثناة والدوال المشتركة
from excluded_samples import filter_excluded_rows

# ============================================================
# 0. تثبيت المكتبات المطلوبة تلقائياً
# ============================================================

def install_packages():
    """تثبيت المكتبات المطلوبة إذا لم تكن موجودة"""
    required = {
        'arabic_reshaper': 'arabic-reshaper',
        'bidi': 'python-bidi',
        'matplotlib': 'matplotlib',
        'seaborn': 'seaborn',
        'openpyxl': 'openpyxl'
    }
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            print(f"  جاري تثبيت {package}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', package, '-q'],
                          capture_output=True)

install_packages()

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle

# تطبيق الستايل بأمان
try:
    mplstyle.use('seaborn-v0_8-whitegrid')
except:
    try:
        mplstyle.use('seaborn-whitegrid')
    except:
        pass

import matplotlib.font_manager as fm
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')


# ============================================================
# 1. إعداد الخط العربي
# ============================================================

arabic_font_path = None
arabic_font_prop = None

def setup_font():
    """البحث عن خط عربي مناسب وإعداده"""
    global arabic_font_path, arabic_font_prop
    
    search_names = ['NotoSansArabic', 'NotoNaskhArabic', 'NotoKufiArabic',
                    'Arial', 'Tahoma', 'Segoe UI', 'DejaVu Sans',
                    'Amiri', 'Scheherazade', 'Lateef', 'Harmattan']
    
    for font_path in fm.findSystemFonts():
        for name in search_names[:3]:
            if name in font_path and 'Regular' in font_path and 'Condensed' not in font_path:
                arabic_font_path = font_path
                break
        if arabic_font_path:
            break
    
    if arabic_font_path is None:
        for font_path in fm.findSystemFonts():
            for name in search_names[:3]:
                if name in font_path and 'Condensed' not in font_path:
                    arabic_font_path = font_path
                    break
            if arabic_font_path:
                break
    
    if arabic_font_path is None:
        try:
            font_url = "https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf"
            font_dir = os.path.expanduser("~/.fonts")
            os.makedirs(font_dir, exist_ok=True)
            font_file = os.path.join(font_dir, "NotoSansArabic.ttf")
            if not os.path.exists(font_file):
                subprocess.run(['wget', '-q', '-O', font_file, font_url], capture_output=True, timeout=30)
            if os.path.exists(font_file) and os.path.getsize(font_file) > 1000:
                arabic_font_path = font_file
                fm.fontManager.addfont(font_file)
        except:
            pass
    
    if arabic_font_path:
        try:
            arabic_font_prop = fm.FontProperties(fname=arabic_font_path)
            font_name = arabic_font_prop.get_name()
            plt.rcParams['font.family'] = font_name
            print(f"  تم تحميل الخط العربي: {font_name}")
        except:
            arabic_font_prop = None
            print("  تحذير: فشل تحميل الخط العربي، سيتم استخدام الخط الافتراضي")
    else:
        print("  تحذير: لم يتم العثور على خط عربي، سيتم استخدام الخط الافتراضي")

setup_font()

plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.dpi'] = 150
plt.rcParams['savefig.bbox'] = 'tight'
plt.rcParams['figure.figsize'] = (14, 8)


# ============================================================
# 2. دوال دعم العربية
# ============================================================

HAS_ARABIC_SUPPORT = False

def setup_arabic():
    global HAS_ARABIC_SUPPORT
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        HAS_ARABIC_SUPPORT = True
        print("  تم تفعيل دعم العربية (arabic_reshaper + python-bidi)")
        return True
    except ImportError:
        HAS_ARABIC_SUPPORT = False
        print("  تحذير: مكتبات العربية غير متوفرة، النصوص قد تظهر بشكل معكوس")
        return False


def get_display_text(text):
    text = str(text)
    if not HAS_ARABIC_SUPPORT:
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text


def get_font_prop():
    return arabic_font_prop


# ============================================================
# 3. الاختبارات المستثناة وقاموس الخطورة
# ============================================================
EXCLUDED_TESTS = ['العد الكلي للبكتيريا', 'الخمائر والاعفان', 'خمائر', 'اعفان']



MICROBE_RISK_DB = {
    'السالمونيلا': 10,
    'استافيلوكوكس اورياس': 8,
    'ايشيريشيا كولاي': 8,
    'باسيلس سيريس': 7,
    'سيدوموناس': 7,
    'انتيروباكتريسي': 6,
    'كوليفورم': 5,
}


# ============================================================
# 4. دوال البيانات
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


def extract_individual_tests(df):
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


def calc_facility_risk_score(df):
    """حساب درجة خطورة المنشآت بمعادلة WHO المحسنة"""
    fac_stats = df.groupby('اسم_المنشأة').agg(
        غير_مطابقة=('غير_مطابقة', 'sum'),
        إجمالي=('رمز_العينة', 'count'),
        البلدية=('اسم_البلدية', 'first')
    ).reset_index()
    fac_stats['نسبة'] = (fac_stats['غير_مطابقة'] / fac_stats['إجمالي'] * 100).round(1)
    
    # تنوع وشدة الميكروبات
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    if len(tests_df) > 0:
        diversity = tests_df.groupby('اسم_المنشأة')['الاختبار'].nunique().reset_index()
        diversity.columns = ['اسم_المنشأة', 'تنوع']
        fac_stats = fac_stats.merge(diversity, on='اسم_المنشأة', how='left')
    fac_stats['تنوع'] = fac_stats.get('تنوع', pd.Series(dtype=float)).fillna(0).astype(int)
    
    # شدة الميكروبات
    severity_scores = {}
    if len(tests_df) > 0:
        for facility in fac_stats['اسم_المنشأة']:
            fac_tests = tests_df[tests_df['اسم_المنشأة'] == facility]
            if len(fac_tests) == 0:
                severity_scores[facility] = 0
                continue
            total_s, total_c = 0, 0
            for microbe, count in fac_tests['الاختبار'].value_counts().items():
                total_s += MICROBE_RISK_DB.get(microbe, 3) * count
                total_c += count
            severity_scores[facility] = total_s / total_c if total_c > 0 else 0
    fac_stats['شدة'] = fac_stats['اسم_المنشأة'].map(severity_scores).fillna(0)
    
    # الدرجة المركبة
    max_s = fac_stats['شدة'].max() or 1
    max_p = fac_stats['نسبة'].max() or 1
    max_d = fac_stats['تنوع'].max() or 1
    max_v = fac_stats['غير_مطابقة'].max() or 1
    
    max_log_total = np.log1p(fac_stats['إجمالي'].max()) or 1
    
    fac_stats['درجة'] = (
        (fac_stats['نسبة'] / max_p * 35) +
        (fac_stats['شدة'] / max_s * 30) +
        (fac_stats['تنوع'] / max_d * 20) +
        (np.log1p(fac_stats['إجمالي']) / max_log_total * 15)
    ).round(1)
    
    # معامل تعديل
    fac_stats['درجة'] = (fac_stats['درجة'] * fac_stats['إجمالي'].apply(
        lambda x: 0.5 if x == 1 else (0.75 if x == 2 else 1.0)
    )).round(1)
    
    return fac_stats.sort_values('درجة', ascending=False)


def calc_sample_risk_score(df):
    """حساب درجة تلوث العينات بمعادلة مبنية على النسبة والشدة"""
    sample_stats = df.groupby('اسم_العينة').agg(
        غير_مطابقة=('غير_مطابقة', 'sum'),
        إجمالي=('رمز_العينة', 'count')
    ).reset_index()
    sample_stats['نسبة'] = (sample_stats['غير_مطابقة'] / sample_stats['إجمالي'] * 100).round(1)
    
    invalid_df = df[df['غير_مطابقة'] == 1]
    tests_df = extract_individual_tests(invalid_df)
    
    if len(tests_df) > 0:
        diversity = tests_df.groupby('اسم_العينة')['الاختبار'].nunique().reset_index()
        diversity.columns = ['اسم_العينة', 'تنوع']
        sample_stats = sample_stats.merge(diversity, on='اسم_العينة', how='left')
    sample_stats['تنوع'] = sample_stats.get('تنوع', pd.Series(dtype=float)).fillna(0).astype(int)
    
    severity_scores = {}
    if len(tests_df) > 0:
        for sample_name in sample_stats['اسم_العينة']:
            samp_tests = tests_df[tests_df['اسم_العينة'] == sample_name]
            if len(samp_tests) == 0:
                severity_scores[sample_name] = 0
                continue
            total_s, total_c = 0, 0
            for microbe, count in samp_tests['الاختبار'].value_counts().items():
                total_s += MICROBE_RISK_DB.get(microbe, 3) * count
                total_c += count
            severity_scores[sample_name] = total_s / total_c if total_c > 0 else 0
    sample_stats['شدة'] = sample_stats['اسم_العينة'].map(severity_scores).fillna(0)
    
    max_p = sample_stats['نسبة'].max() or 1
    max_s = sample_stats['شدة'].max() or 1
    max_d = sample_stats['تنوع'].max() or 1
    max_log_total = np.log1p(sample_stats['إجمالي'].max()) or 1
    
    sample_stats['درجة'] = (
        (sample_stats['نسبة'] / max_p * 35) +
        (sample_stats['شدة'] / max_s * 30) +
        (sample_stats['تنوع'] / max_d * 20) +
        (np.log1p(sample_stats['إجمالي']) / max_log_total * 15)
    ).round(1)
    
    sample_stats['درجة'] = (sample_stats['درجة'] * sample_stats['إجمالي'].apply(
        lambda x: 0.5 if x == 1 else (0.75 if x == 2 else 1.0)
    )).round(1)
    
    return sample_stats.sort_values('درجة', ascending=False)


# ============================================================
# 5. الرسوم البيانية
# ============================================================

def chart_01_overview_pie(df, output_dir='charts'):
    """رسم 1: نسبة المطابقة وعدم المطابقة (دائري)"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        valid = len(df[df['غير_مطابقة'] == 0])
        invalid = len(df[df['غير_مطابقة'] == 1])
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        labels = [get_display_text('مطابقة'), get_display_text('غير مطابقة')]
        sizes = [valid, invalid]
        colors = ['#2ecc71', '#e74c3c']
        explode = (0, 0.05)
        
        fp = get_font_prop()
        text_props = {'fontsize': 16}
        if fp:
            text_props['fontproperties'] = fp
        
        wedges, texts, autotexts = ax.pie(
            sizes, explode=explode, labels=labels, colors=colors,
            autopct='%1.1f%%', shadow=True, startangle=90,
            textprops=text_props
        )
        
        for autotext in autotexts:
            autotext.set_fontsize(14)
            autotext.set_fontweight('bold')
        
        title = get_display_text(f'نسبة المطابقة وعدم المطابقة (بكتيريا مرضية) - إجمالي {len(df):,} عينة')
        title_kwargs = {'fontsize': 18, 'fontweight': 'bold', 'pad': 20}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax.set_title(title, **title_kwargs)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '01_نسبة_المطابقة.png'))
        plt.close()
        print("  ✓ تم إنشاء: 01_نسبة_المطابقة.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 01: {e}")
        plt.close('all')


def chart_02_top_facilities(df, output_dir='charts', top_n=15):
    """رسم 2: أكثر المنشآت تلوثاً - مرتبة بدرجة الخطورة (نسبة + شدة)"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        fac_stats = calc_facility_risk_score(df)
        # فقط المنشآت التي لديها عينات غير مطابقة
        fac_stats = fac_stats[fac_stats['غير_مطابقة'] > 0]
        top = fac_stats.head(top_n).iloc[::-1]  # عكس للرسم الأفقي
        
        if len(top) == 0:
            print("  ⚠ لا توجد منشآت غير مطابقة لرسمها")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
        fp = get_font_prop()
        
        # الرسم الأول: نسبة عدم المطابقة
        y_labels = [get_display_text(str(n)[:30]) for n in top['اسم_المنشأة']]
        colors_pct = ['#c0392b' if p >= 50 else '#e67e22' if p >= 25 else '#f1c40f' for p in top['نسبة']]
        bars1 = ax1.barh(range(len(top)), top['نسبة'].values, color=colors_pct, alpha=0.85, height=0.7)
        
        ax1.set_yticks(range(len(top)))
        tick_kwargs = {'fontsize': 10}
        if fp:
            tick_kwargs['fontproperties'] = fp
        ax1.set_yticklabels(y_labels, **tick_kwargs)
        
        for bar, inv, total in zip(bars1, top['غير_مطابقة'].values, top['إجمالي'].values):
            width = bar.get_width()
            ax1.text(width + 0.5, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f}% ({int(inv)}/{int(total)})', va='center', fontsize=9, fontweight='bold')
        
        title1 = get_display_text(f'أكثر {top_n} منشأة تلوثاً - نسبة عدم المطابقة %')
        title_kwargs = {'fontsize': 13, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax1.set_title(title1, **title_kwargs)
        
        xlabel1 = get_display_text('نسبة عدم المطابقة %')
        xlabel_kwargs = {'fontsize': 12}
        if fp:
            xlabel_kwargs['fontproperties'] = fp
        ax1.set_xlabel(xlabel1, **xlabel_kwargs)
        
        # الرسم الثاني: درجة الخطورة المركبة
        colors_risk = ['#c0392b' if d >= 70 else '#e67e22' if d >= 50 else '#f39c12' if d >= 30 else '#27ae60' for d in top['درجة']]
        bars2 = ax2.barh(range(len(top)), top['درجة'].values, color=colors_risk, alpha=0.85, height=0.7)
        
        ax2.set_yticks(range(len(top)))
        ax2.set_yticklabels(y_labels, **tick_kwargs)
        
        for bar in bars2:
            width = bar.get_width()
            ax2.text(width + 0.3, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f}', va='center', fontsize=9, fontweight='bold')
        
        title2 = get_display_text('درجة الخطورة المركبة (نسبة 35% + شدة 30% + تنوع 20% + log(إجمالي) 15%)')
        title_kwargs2 = {'fontsize': 11, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs2['fontproperties'] = fp
        ax2.set_title(title2, **title_kwargs2)
        
        xlabel2 = get_display_text('درجة الخطورة')
        ax2.set_xlabel(xlabel2, **xlabel_kwargs)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '02_المنشآت_الأكثر_تلوثاً.png'))
        plt.close()
        print("  ✓ تم إنشاء: 02_المنشآت_الأكثر_تلوثاً.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 02: {e}")
        plt.close('all')


def chart_03_top_samples(df, output_dir='charts', top_n=15):
    """رسم 3: أكثر العينات تلوثاً - مرتبة بالنسبة ودرجة التلوث"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        sample_stats = calc_sample_risk_score(df)
        sample_stats = sample_stats[sample_stats['غير_مطابقة'] > 0]
        top = sample_stats.head(top_n).iloc[::-1]
        
        if len(top) == 0:
            print("  ⚠ لا توجد عينات غير مطابقة لرسمها")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
        fp = get_font_prop()
        
        # الرسم الأول: نسبة عدم المطابقة
        y_labels = [get_display_text(str(n)[:30]) for n in top['اسم_العينة']]
        colors_pct = ['#c0392b' if p >= 50 else '#e67e22' if p >= 25 else '#f1c40f' for p in top['نسبة']]
        bars1 = ax1.barh(range(len(top)), top['نسبة'].values, color=colors_pct, alpha=0.85, height=0.7)
        
        ax1.set_yticks(range(len(top)))
        tick_kwargs = {'fontsize': 10}
        if fp:
            tick_kwargs['fontproperties'] = fp
        ax1.set_yticklabels(y_labels, **tick_kwargs)
        
        for bar, inv, total in zip(bars1, top['غير_مطابقة'].values, top['إجمالي'].values):
            width = bar.get_width()
            ax1.text(width + 0.5, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f}% ({int(inv)}/{int(total)})', va='center', fontsize=9, fontweight='bold')
        
        title1 = get_display_text(f'أكثر {top_n} عينة تلوثاً - نسبة عدم المطابقة %')
        title_kwargs = {'fontsize': 13, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax1.set_title(title1, **title_kwargs)
        
        xlabel1 = get_display_text('نسبة عدم المطابقة %')
        xlabel_kwargs = {'fontsize': 12}
        if fp:
            xlabel_kwargs['fontproperties'] = fp
        ax1.set_xlabel(xlabel1, **xlabel_kwargs)
        
        # الرسم الثاني: درجة التلوث المركبة
        colors_risk = ['#c0392b' if d >= 70 else '#e67e22' if d >= 50 else '#f39c12' if d >= 30 else '#27ae60' for d in top['درجة']]
        bars2 = ax2.barh(range(len(top)), top['درجة'].values, color=colors_risk, alpha=0.85, height=0.7)
        
        ax2.set_yticks(range(len(top)))
        ax2.set_yticklabels(y_labels, **tick_kwargs)
        
        for bar in bars2:
            width = bar.get_width()
            ax2.text(width + 0.3, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f}', va='center', fontsize=9, fontweight='bold')
        
        title2 = get_display_text('درجة التلوث المركبة (نسبة 35% + شدة 30% + تنوع 20% + log(إجمالي) 15%)')
        title_kwargs2 = {'fontsize': 11, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs2['fontproperties'] = fp
        ax2.set_title(title2, **title_kwargs2)
        
        xlabel2 = get_display_text('درجة التلوث')
        ax2.set_xlabel(xlabel2, **xlabel_kwargs)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '03_العينات_الأكثر_تلوثاً.png'))
        plt.close()
        print("  ✓ تم إنشاء: 03_العينات_الأكثر_تلوثاً.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 03: {e}")
        plt.close('all')


def chart_04_top_tests(df, output_dir='charts'):
    """رسم 4: أكثر الاختبارات (الميكروبات المرضية) غير مطابقة"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        invalid_df = df[df['غير_مطابقة'] == 1]
        tests_df = extract_individual_tests(invalid_df)
        
        if len(tests_df) == 0:
            print("  ⚠ لا توجد بيانات للاختبارات المرضية")
            return
        
        test_counts = tests_df['الاختبار'].value_counts()
        fp = get_font_prop()
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 9))
        
        labels = [get_display_text(str(n)) for n in test_counts.index]
        colors = sns.color_palette('Reds_r', len(test_counts))
        bars = ax1.barh(range(len(test_counts)), test_counts.values, color=colors, alpha=0.85, height=0.7)
        
        ax1.set_yticks(range(len(test_counts)))
        tick_kwargs = {'fontsize': 12}
        if fp:
            tick_kwargs['fontproperties'] = fp
        ax1.set_yticklabels(labels, **tick_kwargs)
        
        for bar in bars:
            width = bar.get_width()
            ax1.text(width + 5, bar.get_y() + bar.get_height()/2,
                    f'{int(width)}', va='center', fontsize=11, fontweight='bold')
        
        title1 = get_display_text('البكتيريا المرضية غير المطابقة')
        title_kwargs = {'fontsize': 14, 'fontweight': 'bold'}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax1.set_title(title1, **title_kwargs)
        
        pie_labels = [get_display_text(str(n)) for n in test_counts.index]
        text_props = {'fontsize': 10}
        if fp:
            text_props['fontproperties'] = fp
        
        wedges, texts, autotexts = ax2.pie(
            test_counts.values, labels=pie_labels,
            autopct='%1.1f%%', startangle=90,
            textprops=text_props
        )
        
        title2 = get_display_text('توزيع نسب البكتيريا المرضية')
        title_kwargs2 = {'fontsize': 14, 'fontweight': 'bold'}
        if fp:
            title_kwargs2['fontproperties'] = fp
        ax2.set_title(title2, **title_kwargs2)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '04_الاختبارات_غير_المطابقة.png'))
        plt.close()
        print("  ✓ تم إنشاء: 04_الاختبارات_غير_المطابقة.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 04: {e}")
        plt.close('all')


def chart_05_seasonal(df, output_dir='charts'):
    """رسم 5: التحليل الموسمي"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        fp = get_font_prop()
        
        season_order = ['شتاء', 'ربيع', 'صيف', 'خريف']
        season_stats = df.groupby('الموسم').agg(
            إجمالي=('رمز_العينة', 'count'),
            غير_مطابقة=('غير_مطابقة', 'sum')
        ).reset_index()
        season_stats['نسبة'] = (season_stats['غير_مطابقة'] / season_stats['إجمالي'] * 100).round(1)
        season_stats['ترتيب'] = season_stats['الموسم'].map({s: i for i, s in enumerate(season_order)})
        season_stats = season_stats.sort_values('ترتيب')
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
        
        x = np.arange(len(season_stats))
        width = 0.35
        
        season_labels = [get_display_text(s) for s in season_stats['الموسم']]
        season_colors = {'شتاء': '#3498db', 'ربيع': '#2ecc71', 'صيف': '#e74c3c', 'خريف': '#f39c12'}
        
        bars1 = ax1.bar(x - width/2, season_stats['إجمالي'], width,
                        label=get_display_text('إجمالي العينات'), color='#3498db', alpha=0.7)
        bars2 = ax1.bar(x + width/2, season_stats['غير_مطابقة'], width,
                        label=get_display_text('غير مطابقة'), color='#e74c3c', alpha=0.7)
        
        ax1.set_xticks(x)
        tick_kwargs = {'fontsize': 14}
        if fp:
            tick_kwargs['fontproperties'] = fp
        ax1.set_xticklabels(season_labels, **tick_kwargs)
        
        for bar in bars1:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10,
                    f'{int(bar.get_height())}', ha='center', fontsize=10, fontweight='bold')
        for bar in bars2:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10,
                    f'{int(bar.get_height())}', ha='center', fontsize=10, fontweight='bold')
        
        title1 = get_display_text('عدد العينات حسب الموسم (بكتيريا مرضية)')
        title_kwargs = {'fontsize': 14, 'fontweight': 'bold'}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax1.set_title(title1, **title_kwargs)
        
        legend_kwargs = {'fontsize': 12}
        if fp:
            legend_kwargs['prop'] = fp
        ax1.legend(**legend_kwargs)
        
        bar_colors = [season_colors.get(s, '#95a5a6') for s in season_stats['الموسم']]
        bars3 = ax2.bar(x, season_stats['نسبة'], color=bar_colors, alpha=0.85, width=0.6)
        
        ax2.set_xticks(x)
        ax2.set_xticklabels(season_labels, **tick_kwargs)
        
        for bar, pct in zip(bars3, season_stats['نسبة']):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    f'{pct}%', ha='center', fontsize=13, fontweight='bold')
        
        title2 = get_display_text('نسبة عدم المطابقة حسب الموسم (%)')
        title_kwargs2 = {'fontsize': 14, 'fontweight': 'bold'}
        if fp:
            title_kwargs2['fontproperties'] = fp
        ax2.set_title(title2, **title_kwargs2)
        
        ylabel = get_display_text('النسبة %')
        ylabel_kwargs = {'fontsize': 12}
        if fp:
            ylabel_kwargs['fontproperties'] = fp
        ax2.set_ylabel(ylabel, **ylabel_kwargs)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '05_التحليل_الموسمي.png'))
        plt.close()
        print("  ✓ تم إنشاء: 05_التحليل_الموسمي.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 05: {e}")
        plt.close('all')


def chart_06_monthly_trend(df, output_dir='charts'):
    """رسم 6: الاتجاه الشهري"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        fp = get_font_prop()
        
        month_names_ar = {
            1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
            5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
            9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
        }
        
        monthly = df.groupby('الشهر').agg(
            إجمالي=('رمز_العينة', 'count'),
            غير_مطابقة=('غير_مطابقة', 'sum')
        ).reset_index()
        monthly['نسبة'] = (monthly['غير_مطابقة'] / monthly['إجمالي'] * 100).round(1)
        monthly = monthly.sort_values('الشهر')
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        x = monthly['الشهر'].values
        month_labels = [get_display_text(month_names_ar.get(m, str(m))) for m in x]
        
        line = ax.plot(x, monthly['نسبة'], 'o-', color='#e74c3c', linewidth=2.5,
                       markersize=10, markerfacecolor='white', markeredgewidth=2.5,
                       label=get_display_text('نسبة عدم المطابقة %'))
        
        ax.fill_between(x, monthly['نسبة'], alpha=0.15, color='#e74c3c')
        
        for xi, yi in zip(x, monthly['نسبة']):
            ax.annotate(f'{yi}%', (xi, yi), textcoords="offset points",
                       xytext=(0, 15), ha='center', fontsize=11, fontweight='bold', color='#c0392b')
        
        ax.set_xticks(x)
        tick_kwargs = {'fontsize': 11, 'rotation': 45}
        if fp:
            tick_kwargs['fontproperties'] = fp
        ax.set_xticklabels(month_labels, **tick_kwargs)
        
        title = get_display_text('الاتجاه الشهري لنسبة عدم المطابقة - بكتيريا مرضية (%)')
        title_kwargs = {'fontsize': 16, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax.set_title(title, **title_kwargs)
        
        ylabel = get_display_text('نسبة عدم المطابقة %')
        ylabel_kwargs = {'fontsize': 13}
        if fp:
            ylabel_kwargs['fontproperties'] = fp
        ax.set_ylabel(ylabel, **ylabel_kwargs)
        
        legend_kwargs = {'fontsize': 12}
        if fp:
            legend_kwargs['prop'] = fp
        ax.legend(**legend_kwargs)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '06_الاتجاه_الشهري.png'))
        plt.close()
        print("  ✓ تم إنشاء: 06_الاتجاه_الشهري.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 06: {e}")
        plt.close('all')


def chart_07_municipalities(df, output_dir='charts', top_n=15):
    """رسم 7: تحليل البلديات - مرتبة بنسبة عدم المطابقة"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        fp = get_font_prop()
        
        mun_stats = df.groupby('اسم_البلدية').agg(
            غير_مطابقة=('غير_مطابقة', 'sum'),
            إجمالي=('رمز_العينة', 'count')
        ).reset_index()
        mun_stats['نسبة'] = (mun_stats['غير_مطابقة'] / mun_stats['إجمالي'] * 100).round(1)
        # ترتيب بالنسبة بدلاً من العدد
        top = mun_stats[mun_stats['غير_مطابقة'] > 0].sort_values('نسبة', ascending=True).tail(top_n)
        
        if len(top) == 0:
            print("  ⚠ لا توجد بلديات غير مطابقة لرسمها")
            return
        
        fig, ax = plt.subplots(figsize=(14, 9))
        
        y_labels = [get_display_text(str(n)[:25]) for n in top['اسم_البلدية']]
        colors = ['#c0392b' if p >= 20 else '#e67e22' if p >= 10 else '#f1c40f' for p in top['نسبة']]
        bars = ax.barh(range(len(top)), top['نسبة'].values, color=colors, alpha=0.85, height=0.7)
        
        ax.set_yticks(range(len(top)))
        tick_kwargs = {'fontsize': 12}
        if fp:
            tick_kwargs['fontproperties'] = fp
        ax.set_yticklabels(y_labels, **tick_kwargs)
        
        for bar, inv, total in zip(bars, top['غير_مطابقة'].values, top['إجمالي'].values):
            width = bar.get_width()
            ax.text(width + 0.3, bar.get_y() + bar.get_height()/2,
                    f'{width:.1f}% ({int(inv)}/{int(total)})', va='center', fontsize=10, fontweight='bold')
        
        title = get_display_text(f'أكثر {top_n} بلدية من حيث نسبة عدم المطابقة (بكتيريا مرضية)')
        title_kwargs = {'fontsize': 16, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax.set_title(title, **title_kwargs)
        
        xlabel = get_display_text('نسبة عدم المطابقة %')
        xlabel_kwargs = {'fontsize': 13}
        if fp:
            xlabel_kwargs['fontproperties'] = fp
        ax.set_xlabel(xlabel, **xlabel_kwargs)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '07_تحليل_البلديات.png'))
        plt.close()
        print("  ✓ تم إنشاء: 07_تحليل_البلديات.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 07: {e}")
        plt.close('all')


def chart_08_category_analysis(df, output_dir='charts'):
    """رسم 8: تحليل فئات العينات"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        fp = get_font_prop()
        
        cat_stats = df.groupby('فئة_العينة').agg(
            إجمالي=('رمز_العينة', 'count'),
            غير_مطابقة=('غير_مطابقة', 'sum')
        ).reset_index()
        cat_stats['نسبة'] = (cat_stats['غير_مطابقة'] / cat_stats['إجمالي'] * 100).round(1)
        cat_stats = cat_stats.sort_values('نسبة', ascending=True)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
        
        y_labels = [get_display_text(str(n)[:25]) for n in cat_stats['فئة_العينة']]
        colors = sns.color_palette('Set2', len(cat_stats))
        
        tick_kwargs = {'fontsize': 12}
        if fp:
            tick_kwargs['fontproperties'] = fp
        
        bars = ax1.barh(range(len(cat_stats)), cat_stats['غير_مطابقة'].values, color=colors, alpha=0.85)
        ax1.set_yticks(range(len(cat_stats)))
        ax1.set_yticklabels(y_labels, **tick_kwargs)
        
        for bar in bars:
            width = bar.get_width()
            ax1.text(width + 1, bar.get_y() + bar.get_height()/2,
                    f'{int(width)}', va='center', fontsize=11, fontweight='bold')
        
        title1 = get_display_text('عدد العينات غير المطابقة حسب الفئة (بكتيريا مرضية)')
        title_kwargs = {'fontsize': 14, 'fontweight': 'bold'}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax1.set_title(title1, **title_kwargs)
        
        bars2 = ax2.barh(range(len(cat_stats)), cat_stats['نسبة'].values, color=colors, alpha=0.85)
        ax2.set_yticks(range(len(cat_stats)))
        ax2.set_yticklabels(y_labels, **tick_kwargs)
        
        for bar, pct in zip(bars2, cat_stats['نسبة']):
            width = bar.get_width()
            ax2.text(width + 0.3, bar.get_y() + bar.get_height()/2,
                    f'{pct}%', va='center', fontsize=11, fontweight='bold')
        
        title2 = get_display_text('نسبة عدم المطابقة حسب الفئة (%)')
        title_kwargs2 = {'fontsize': 14, 'fontweight': 'bold'}
        if fp:
            title_kwargs2['fontproperties'] = fp
        ax2.set_title(title2, **title_kwargs2)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '08_تحليل_الفئات.png'))
        plt.close()
        print("  ✓ تم إنشاء: 08_تحليل_الفئات.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 08: {e}")
        plt.close('all')


def chart_09_heatmap_microbe_sample(df, output_dir='charts'):
    """رسم 9: خريطة حرارية - الميكروبات × العينات"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        fp = get_font_prop()
        
        invalid_df = df[df['غير_مطابقة'] == 1]
        tests_df = extract_individual_tests(invalid_df)
        
        if len(tests_df) == 0:
            print("  ⚠ لا توجد بيانات للخريطة الحرارية")
            return
        
        top_samples = tests_df['اسم_العينة'].value_counts().head(12).index
        filtered = tests_df[tests_df['اسم_العينة'].isin(top_samples)]
        pivot = filtered.groupby(['اسم_العينة', 'الاختبار']).size().unstack(fill_value=0)
        
        fig, ax = plt.subplots(figsize=(16, 10))
        
        x_labels = [get_display_text(str(c)[:20]) for c in pivot.columns]
        y_labels = [get_display_text(str(r)[:25]) for r in pivot.index]
        
        sns.heatmap(pivot.values, annot=True, fmt='d', cmap='YlOrRd',
                    xticklabels=x_labels, yticklabels=y_labels,
                    ax=ax, linewidths=0.5, cbar_kws={'label': get_display_text('عدد المرات')})
        
        tick_kwargs = {'fontsize': 11}
        if fp:
            tick_kwargs['fontproperties'] = fp
        
        ax.set_xticklabels(x_labels, rotation=45, ha='right', **tick_kwargs)
        ax.set_yticklabels(y_labels, **tick_kwargs)
        
        title = get_display_text('خريطة حرارية: البكتيريا المرضية × أكثر العينات تلوثاً')
        title_kwargs = {'fontsize': 16, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax.set_title(title, **title_kwargs)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '09_خريطة_حرارية.png'))
        plt.close()
        print("  ✓ تم إنشاء: 09_خريطة_حرارية.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 09: {e}")
        plt.close('all')


def chart_10_risk_matrix(df, output_dir='charts'):
    """رسم 10: مصفوفة المخاطر للمنشآت"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        fp = get_font_prop()
        
        fac_stats = calc_facility_risk_score(df)
        fac_with_issues = fac_stats[fac_stats['غير_مطابقة'] > 0]
        
        if len(fac_with_issues) == 0:
            print("  ⚠ لا توجد منشآت بمشاكل لرسم مصفوفة المخاطر")
            return
        
        fig, ax = plt.subplots(figsize=(14, 10))
        
        scatter = ax.scatter(
            fac_with_issues['إجمالي'],
            fac_with_issues['نسبة'],
            s=fac_with_issues['درجة'] * 3,
            c=fac_with_issues['نسبة'],
            cmap='RdYlGn_r',
            alpha=0.6,
            edgecolors='black',
            linewidth=0.5
        )
        
        ax.axhline(y=50, color='red', linestyle='--', alpha=0.5, linewidth=1)
        ax.axhline(y=25, color='orange', linestyle='--', alpha=0.5, linewidth=1)
        
        text_kwargs = {'fontsize': 12, 'alpha': 0.7}
        if fp:
            text_kwargs['fontproperties'] = fp
        
        ax.text(ax.get_xlim()[1] * 0.7, 55, get_display_text('منطقة خطورة عالية'),
                color='red', **text_kwargs)
        ax.text(ax.get_xlim()[1] * 0.7, 30, get_display_text('منطقة خطورة متوسطة'),
                color='orange', **text_kwargs)
        
        plt.colorbar(scatter, ax=ax, label=get_display_text('نسبة عدم المطابقة %'))
        
        title = get_display_text('مصفوفة المخاطر: المنشآت (بكتيريا مرضية فقط)')
        title_kwargs = {'fontsize': 14, 'fontweight': 'bold', 'pad': 15}
        if fp:
            title_kwargs['fontproperties'] = fp
        ax.set_title(title, **title_kwargs)
        
        label_kwargs = {'fontsize': 13}
        if fp:
            label_kwargs['fontproperties'] = fp
        
        xlabel = get_display_text('إجمالي العينات المفحوصة')
        ylabel = get_display_text('نسبة عدم المطابقة %')
        ax.set_xlabel(xlabel, **label_kwargs)
        ax.set_ylabel(ylabel, **label_kwargs)
        
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, '10_مصفوفة_المخاطر.png'))
        plt.close()
        print("  ✓ تم إنشاء: 10_مصفوفة_المخاطر.png")
    except Exception as e:
        print(f"  ✗ خطأ في رسم 10: {e}")
        plt.close('all')


# ============================================================
# التنفيذ الرئيسي
# ============================================================

if __name__ == '__main__':
    print("="*60)
    print("  إنشاء الرسوم البيانية (بكتيريا مرضية فقط)")
    print("  المعادلة المدمجة: نسبة 35% + شدة 30% + تنوع 20% + log(إجمالي) 15%")
    print("="*60)
    
    setup_arabic()
    
    try:
        df = load_data('Data 2025.xlsx')
        print(f"  تم تحميل {len(df):,} صف")
    except FileNotFoundError:
        print("  ✗ خطأ: ملف 'Data 2025.xlsx' غير موجود!")
        print("    تأكد من وجود الملف في نفس المجلد")
        sys.exit(1)
    except Exception as e:
        print(f"  ✗ خطأ في تحميل البيانات: {e}")
        sys.exit(1)
    
    df = apply_exclusion_filter(df)
    
    # استثناء البلديات غير الصالحة (مثل "-")
    df = filter_invalid_municipalities(df)
    
    output_dir = 'charts'
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n  جاري إنشاء الرسوم البيانية في مجلد: {output_dir}/\n")
    
    charts = [
        ("01 - نسبة المطابقة", chart_01_overview_pie),
        ("02 - المنشآت الأكثر تلوثاً", chart_02_top_facilities),
        ("03 - العينات الأكثر تلوثاً", chart_03_top_samples),
        ("04 - الاختبارات غير المطابقة", chart_04_top_tests),
        ("05 - التحليل الموسمي", chart_05_seasonal),
        ("06 - الاتجاه الشهري", chart_06_monthly_trend),
        ("07 - تحليل البلديات", chart_07_municipalities),
        ("08 - تحليل الفئات", chart_08_category_analysis),
        ("09 - خريطة حرارية", chart_09_heatmap_microbe_sample),
        ("10 - مصفوفة المخاطر", chart_10_risk_matrix),
    ]
    
    success_count = 0
    fail_count = 0
    
    for name, func in charts:
        try:
            func(df, output_dir)
            success_count += 1
        except Exception as e:
            print(f"  ✗ فشل {name}: {e}")
            fail_count += 1
    
    print(f"\n{'='*60}")
    print(f"  النتيجة: {success_count} رسم ناجح، {fail_count} فشل")
    
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if f.endswith('.png')]
        if files:
            print(f"  الملفات المنتجة ({len(files)}):")
            for f in sorted(files):
                size = os.path.getsize(os.path.join(output_dir, f))
                print(f"    - {f} ({size:,} bytes)")
        else:
            print("  ⚠ لم يتم إنتاج أي ملفات!")
    
    print(f"{'='*60}")
