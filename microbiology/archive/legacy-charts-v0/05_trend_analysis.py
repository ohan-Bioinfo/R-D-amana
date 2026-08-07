# -*- coding: utf-8 -*-
"""
=============================================================
 تحليل اتجاه التلوث - Contamination Trend Analysis
=============================================================
 1. خط اتجاه شهري - Monthly Trend Line
 2. مقارنة ربع سنوية - Quarterly Comparison
 3. اتجاه لكل بلدية - Trend per Municipality
 4. اتجاه لأنواع الميكروبات - Trend per Microbe Type
=============================================================
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import re
import os
import sys
import warnings
warnings.filterwarnings('ignore')

# استيراد قائمة العينات المستثناة والدوال المشتركة
from excluded_samples import filter_excluded_rows

# محاولة تحميل مكتبات العربية
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC = True
except ImportError:
    try:
        os.system('pip3 install arabic-reshaper python-bidi -q')
        import arabic_reshaper
        from bidi.algorithm import get_display
        HAS_ARABIC = True
    except:
        HAS_ARABIC = False

# ============================================================
# إعداد الخط العربي
# ============================================================
from matplotlib.font_manager import FontProperties

arabic_font_path = None
font_search_paths = [
    '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
    '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/Library/Fonts/Arial Unicode.ttf',
    '/System/Library/Fonts/Geeza Pro.ttc',
    '/System/Library/Fonts/Supplemental/GeezaPro.ttc',
    'C:\\Windows\\Fonts\\arial.ttf',
    'C:\\Windows\\Fonts\\tahoma.ttf',
]

for fp in font_search_paths:
    if os.path.exists(fp):
        arabic_font_path = fp
        break

if arabic_font_path is None:
    try:
        os.makedirs(os.path.expanduser('~/.fonts'), exist_ok=True)
        font_url = "https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf"
        font_dest = os.path.expanduser('~/.fonts/NotoSansArabic.ttf')
        if not os.path.exists(font_dest):
            import urllib.request
            urllib.request.urlretrieve(font_url, font_dest)
        if os.path.exists(font_dest):
            arabic_font_path = font_dest
    except:
        pass

def get_font(size=12, bold=False):
    if arabic_font_path:
        return FontProperties(fname=arabic_font_path, size=size, weight='bold' if bold else 'normal')
    return FontProperties(size=size, weight='bold' if bold else 'normal')

def ar(text):
    if not HAS_ARABIC:
        return str(text)
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except:
        return str(text)


# ============================================================
# الاختبارات المستثناة
# ============================================================
EXCLUDED_TESTS = ['العد الكلي للبكتيريا', 'الخمائر والاعفان', 'خمائر', 'اعفان']



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

# درجات خطورة الميكروبات
MICROBE_SEVERITY = {
    'السالمونيلا': 10, 'سالمونيلا': 10, 'Salmonella': 10,
    'ايشيريشيا كولاي': 9, 'الايشيريشيا كولاي': 9, 'E.coli': 9, 'E. coli': 9,
    'ليستيريا': 9, 'الليستيريا': 9, 'Listeria': 9,
    'المكورات العنقودية': 8, 'ستافيلوكوكس': 8, 'Staphylococcus': 8,
    'كلوستريديوم': 8, 'Clostridium': 8,
    'باسيلس سيريس': 7, 'Bacillus cereus': 7,
    'كوليفورم': 5, 'الكوليفورم': 5, 'Coliform': 5,
    'انتيروباكتيريسي': 5, 'انتيروبكتريسي': 5, 'Enterobacteriaceae': 5,
}


# ============================================================
# دوال التنظيف
# ============================================================

def unify_sample_names(df):
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
    df = df.copy()
    df['اسم_البلدية'] = df['اسم_البلدية'].astype(str).str.strip()
    df = df[~df['اسم_البلدية'].isin(EXCLUDED_MUNICIPALITIES)]
    df = df[df['اسم_البلدية'].str.len() > 1]
    return df


# ============================================================
# قراءة البيانات
# ============================================================

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
    
    # الربع السنوي
    df['الربع'] = df['الشهر'].apply(lambda m: f'Q{((int(m)-1)//3)+1}' if pd.notna(m) else 'غير محدد')
    
    # استثناء العينات الخاصة والعينات المحددة (لحوم نيئة/أعضاء/دجاج ني/كباب)
    df = filter_excluded_rows(df)
    
    df['الاختبار_غير_المطابق'] = df['الاختبار_غير_المطابق'].fillna('لا يوجد').astype(str).str.strip()
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


# ============================================================
# استخراج الميكروبات من عمود الاختبارات
# ============================================================

def extract_microbes(test_text):
    """استخراج قائمة الميكروبات من نص الاختبار"""
    if pd.isna(test_text) or str(test_text).strip() in ['لا يوجد', 'nan', '']:
        return []
    tests = [t.strip() for t in str(test_text).split('|')]
    return [t for t in tests if t and t != 'لا يوجد']


# ============================================================
# 1. خط اتجاه شهري - Monthly Trend Line
# ============================================================

def monthly_trend(df, output_dir):
    """تحليل اتجاه التلوث الشهري مع خط اتجاه"""
    print("\n" + "="*70)
    print("  1. اتجاه التلوث الشهري")
    print("="*70)
    
    df_dated = df[df['الشهر'].notna()].copy()
    
    monthly = df_dated.groupby('الشهر').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum')
    ).reset_index()
    
    monthly['نسبة_عدم_المطابقة%'] = (monthly['عينات_غير_مطابقة'] / monthly['إجمالي_العينات'] * 100).round(1)
    monthly = monthly.sort_values('الشهر')
    
    month_names = {1:'يناير', 2:'فبراير', 3:'مارس', 4:'أبريل', 5:'مايو', 6:'يونيو',
                   7:'يوليو', 8:'أغسطس', 9:'سبتمبر', 10:'أكتوبر', 11:'نوفمبر', 12:'ديسمبر'}
    monthly['اسم_الشهر'] = monthly['الشهر'].map(month_names)
    
    # حساب خط الاتجاه (Linear Regression)
    x = monthly['الشهر'].values
    y = monthly['نسبة_عدم_المطابقة%'].values
    if len(x) >= 2:
        coeffs = np.polyfit(x, y, 1)
        trend_line = np.polyval(coeffs, x)
        slope = coeffs[0]
        if slope > 0.5:
            trend_direction = 'تصاعدي (التلوث يزداد)'
            trend_color = 'red'
        elif slope < -0.5:
            trend_direction = 'تنازلي (التلوث يتحسن)'
            trend_color = 'green'
        else:
            trend_direction = 'مستقر'
            trend_color = 'orange'
    else:
        trend_line = y
        slope = 0
        trend_direction = 'بيانات غير كافية'
        trend_color = 'gray'
    
    monthly['خط_الاتجاه'] = trend_line.round(1)
    monthly['اتجاه_التلوث'] = trend_direction
    
    print(f"\n  اتجاه التلوث العام: {trend_direction}")
    print(f"  معامل الميل: {slope:.2f}% لكل شهر")
    print(f"\n{'الشهر':<12} {'إجمالي':<10} {'غير مطابقة':<14} {'النسبة%':<10} {'الاتجاه':<10}")
    print("-" * 60)
    for _, row in monthly.iterrows():
        print(f"  {row['اسم_الشهر']:<10} {int(row['إجمالي_العينات']):<10} "
              f"{int(row['عينات_غير_مطابقة']):<14} {row['نسبة_عدم_المطابقة%']:<10} {row['خط_الاتجاه']:<10}")
    
    # رسم بياني
    try:
        fig, ax1 = plt.subplots(figsize=(14, 7))
        
        months_ar = [ar(month_names.get(m, str(m))) for m in monthly['الشهر']]
        x_pos = range(len(monthly))
        
        # أعمدة العينات
        bars_total = ax1.bar([p - 0.2 for p in x_pos], monthly['إجمالي_العينات'], 
                             width=0.4, color='#3498db', alpha=0.7, label=ar('إجمالي العينات'))
        bars_invalid = ax1.bar([p + 0.2 for p in x_pos], monthly['عينات_غير_مطابقة'], 
                               width=0.4, color='#e74c3c', alpha=0.7, label=ar('غير مطابقة'))
        
        ax1.set_xlabel(ar('الشهر'), fontproperties=get_font(12))
        ax1.set_ylabel(ar('عدد العينات'), fontproperties=get_font(12))
        ax1.set_xticks(list(x_pos))
        ax1.set_xticklabels(months_ar, fontproperties=get_font(9))
        
        # خط النسبة والاتجاه
        ax2 = ax1.twinx()
        ax2.plot(list(x_pos), monthly['نسبة_عدم_المطابقة%'], 'ko-', linewidth=2, 
                 markersize=8, label=ar('نسبة عدم المطابقة%'))
        ax2.plot(list(x_pos), monthly['خط_الاتجاه'], '--', color=trend_color, 
                 linewidth=2.5, label=ar(f'خط الاتجاه ({trend_direction})'))
        ax2.set_ylabel(ar('نسبة عدم المطابقة %'), fontproperties=get_font(12))
        
        # إضافة النسب فوق النقاط
        for i, (xp, yp) in enumerate(zip(x_pos, monthly['نسبة_عدم_المطابقة%'])):
            ax2.annotate(f'{yp:.1f}%', (xp, yp), textcoords="offset points", 
                        xytext=(0, 12), ha='center', fontsize=9, fontweight='bold')
        
        ax1.set_title(ar('اتجاه التلوث الشهري - Monthly Contamination Trend'), 
                      fontproperties=get_font(16, bold=True), pad=20)
        
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', 
                   prop=get_font(10))
        
        plt.tight_layout()
        chart_path = os.path.join(output_dir, 'trend_01_monthly.png')
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"\n  ✓ تم حفظ الرسم: {chart_path}")
    except Exception as e:
        print(f"\n  ✗ خطأ في الرسم: {e}")
    
    return monthly


# ============================================================
# 2. مقارنة ربع سنوية - Quarterly Comparison
# ============================================================

def quarterly_comparison(df, output_dir):
    """مقارنة ربع سنوية لنسب التلوث"""
    print("\n" + "="*70)
    print("  2. المقارنة الربع سنوية")
    print("="*70)
    
    df_dated = df[df['الربع'] != 'غير محدد'].copy()
    
    quarterly = df_dated.groupby('الربع').agg(
        إجمالي_العينات=('رمز_العينة', 'count'),
        عينات_غير_مطابقة=('غير_مطابقة', 'sum'),
        عدد_المنشآت=('اسم_المنشأة', 'nunique'),
        عدد_البلديات=('اسم_البلدية', 'nunique'),
    ).reset_index()
    
    quarterly['نسبة_عدم_المطابقة%'] = (quarterly['عينات_غير_مطابقة'] / quarterly['إجمالي_العينات'] * 100).round(1)
    quarterly = quarterly.sort_values('الربع')
    
    # أسماء الأرباع
    quarter_names = {'Q1': 'الربع الأول (يناير-مارس)', 'Q2': 'الربع الثاني (أبريل-يونيو)',
                     'Q3': 'الربع الثالث (يوليو-سبتمبر)', 'Q4': 'الربع الرابع (أكتوبر-ديسمبر)'}
    quarterly['اسم_الربع'] = quarterly['الربع'].map(quarter_names)
    
    # تحديد أعلى وأدنى ربع
    max_q = quarterly.loc[quarterly['نسبة_عدم_المطابقة%'].idxmax()]
    min_q = quarterly.loc[quarterly['نسبة_عدم_المطابقة%'].idxmin()]
    
    print(f"\n  أعلى ربع تلوثاً: {max_q['اسم_الربع']} ({max_q['نسبة_عدم_المطابقة%']}%)")
    print(f"  أدنى ربع تلوثاً: {min_q['اسم_الربع']} ({min_q['نسبة_عدم_المطابقة%']}%)")
    
    print(f"\n{'الربع':<35} {'إجمالي':<10} {'غير مطابقة':<14} {'النسبة%':<10} {'المنشآت':<10}")
    print("-" * 85)
    for _, row in quarterly.iterrows():
        print(f"  {row['اسم_الربع']:<33} {int(row['إجمالي_العينات']):<10} "
              f"{int(row['عينات_غير_مطابقة']):<14} {row['نسبة_عدم_المطابقة%']:<10} {int(row['عدد_المنشآت']):<10}")
    
    # تحليل الميكروبات لكل ربع
    quarterly_microbes = []
    for q in quarterly['الربع']:
        q_data = df_dated[df_dated['الربع'] == q]
        q_invalid = q_data[q_data['غير_مطابقة'] == 1]
        all_microbes = []
        for tests in q_invalid['الاختبار_غير_المطابق']:
            all_microbes.extend(extract_microbes(tests))
        if all_microbes:
            from collections import Counter
            top_microbes = Counter(all_microbes).most_common(3)
            microbe_text = ' | '.join([f"{m} ({c})" for m, c in top_microbes])
        else:
            microbe_text = 'لا يوجد'
        quarterly_microbes.append(microbe_text)
    quarterly['أبرز_الميكروبات'] = quarterly_microbes
    
    # رسم بياني
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
        
        quarters_ar = [ar(q) for q in quarterly['الربع']]
        colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']
        
        # رسم الأعمدة
        bars = ax1.bar(quarters_ar, quarterly['نسبة_عدم_المطابقة%'], color=colors[:len(quarterly)], 
                       edgecolor='white', linewidth=2)
        for bar, val in zip(bars, quarterly['نسبة_عدم_المطابقة%']):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    f'{val:.1f}%', ha='center', fontsize=12, fontweight='bold')
        
        ax1.set_title(ar('نسبة عدم المطابقة حسب الربع'), fontproperties=get_font(14, bold=True))
        ax1.set_ylabel(ar('النسبة %'), fontproperties=get_font(12))
        ax1.set_xticklabels(quarters_ar, fontproperties=get_font(11))
        
        # رسم دائري
        ax2.pie(quarterly['عينات_غير_مطابقة'], labels=quarters_ar, autopct='%1.1f%%',
                colors=colors[:len(quarterly)], startangle=90, textprops={'fontproperties': get_font(11)})
        ax2.set_title(ar('توزيع العينات غير المطابقة على الأرباع'), fontproperties=get_font(14, bold=True))
        
        plt.tight_layout()
        chart_path = os.path.join(output_dir, 'trend_02_quarterly.png')
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"\n  ✓ تم حفظ الرسم: {chart_path}")
    except Exception as e:
        print(f"\n  ✗ خطأ في الرسم: {e}")
    
    return quarterly


# ============================================================
# 3. اتجاه لكل بلدية - Trend per Municipality
# ============================================================

def municipality_trend(df, output_dir):
    """تحليل اتجاه التلوث لكل بلدية عبر الأشهر"""
    print("\n" + "="*70)
    print("  3. اتجاه التلوث حسب البلدية")
    print("="*70)
    
    df_dated = df[df['الشهر'].notna()].copy()
    
    # البلديات الرئيسية (أكثر من 30 عينة)
    mun_counts = df_dated.groupby('اسم_البلدية')['رمز_العينة'].count()
    major_muns = mun_counts[mun_counts >= 30].index.tolist()
    
    if not major_muns:
        major_muns = mun_counts.nlargest(5).index.tolist()
    
    print(f"\n  البلديات المحللة ({len(major_muns)} بلدية بأكثر من 30 عينة):")
    
    all_mun_trends = []
    mun_monthly_data = {}
    
    for mun in major_muns:
        mun_data = df_dated[df_dated['اسم_البلدية'] == mun]
        
        monthly = mun_data.groupby('الشهر').agg(
            إجمالي=('رمز_العينة', 'count'),
            غير_مطابقة=('غير_مطابقة', 'sum')
        ).reset_index()
        monthly['نسبة%'] = (monthly['غير_مطابقة'] / monthly['إجمالي'] * 100).round(1)
        monthly = monthly.sort_values('الشهر')
        
        mun_monthly_data[mun] = monthly
        
        # حساب الاتجاه
        if len(monthly) >= 3:
            x = monthly['الشهر'].values
            y = monthly['نسبة%'].values
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            if slope > 0.5:
                trend = 'تصاعدي ↑'
            elif slope < -0.5:
                trend = 'تنازلي ↓'
            else:
                trend = 'مستقر ↔'
        else:
            slope = 0
            trend = 'بيانات قليلة'
        
        total_samples = len(mun_data)
        total_invalid = mun_data['غير_مطابقة'].sum()
        overall_rate = round(total_invalid / total_samples * 100, 1) if total_samples > 0 else 0
        
        all_mun_trends.append({
            'اسم_البلدية': mun,
            'إجمالي_العينات': total_samples,
            'عينات_غير_مطابقة': total_invalid,
            'نسبة_عدم_المطابقة%': overall_rate,
            'معامل_الميل': round(slope, 2),
            'الاتجاه': trend,
            'أشهر_البيانات': len(monthly),
        })
        
        print(f"  {mun:<25} إجمالي: {total_samples:<6} نسبة: {overall_rate}%  الاتجاه: {trend} (ميل: {slope:.2f})")
    
    mun_trend_df = pd.DataFrame(all_mun_trends)
    
    # رسم بياني - اتجاه أهم البلديات
    try:
        fig, ax = plt.subplots(figsize=(16, 8))
        
        month_names = {1:'يناير', 2:'فبراير', 3:'مارس', 4:'أبريل', 5:'مايو', 6:'يونيو',
                       7:'يوليو', 8:'أغسطس', 9:'سبتمبر', 10:'أكتوبر', 11:'نوفمبر', 12:'ديسمبر'}
        
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']
        markers = ['o', 's', '^', 'D', 'v', 'p', 'h', '*']
        
        top_muns = mun_trend_df.nlargest(min(8, len(mun_trend_df)), 'إجمالي_العينات')['اسم_البلدية'].tolist()
        
        for i, mun in enumerate(top_muns):
            monthly = mun_monthly_data[mun]
            ax.plot(monthly['الشهر'], monthly['نسبة%'], 
                   color=colors[i % len(colors)], marker=markers[i % len(markers)],
                   linewidth=2, markersize=8, label=ar(mun))
        
        ax.set_xlabel(ar('الشهر'), fontproperties=get_font(12))
        ax.set_ylabel(ar('نسبة عدم المطابقة %'), fontproperties=get_font(12))
        ax.set_title(ar('اتجاه التلوث الشهري حسب البلدية'), fontproperties=get_font(16, bold=True), pad=20)
        
        months_ar = [ar(month_names.get(m, str(m))) for m in range(1, 13)]
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(months_ar, fontproperties=get_font(9))
        
        ax.legend(loc='upper left', prop=get_font(10), ncol=2)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_path = os.path.join(output_dir, 'trend_03_municipality.png')
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"\n  ✓ تم حفظ الرسم: {chart_path}")
    except Exception as e:
        print(f"\n  ✗ خطأ في الرسم: {e}")
    
    return mun_trend_df


# ============================================================
# 4. اتجاه أنواع الميكروبات - Trend per Microbe Type
# ============================================================

def microbe_trend(df, output_dir):
    """تحليل اتجاه ظهور كل نوع ميكروب عبر الأشهر"""
    print("\n" + "="*70)
    print("  4. اتجاه ظهور الميكروبات")
    print("="*70)
    
    df_dated = df[(df['الشهر'].notna()) & (df['غير_مطابقة'] == 1)].copy()
    
    # استخراج كل الميكروبات مع الشهر
    microbe_records = []
    for _, row in df_dated.iterrows():
        microbes = extract_microbes(row['الاختبار_غير_المطابق'])
        for microbe in microbes:
            microbe_records.append({
                'الشهر': int(row['الشهر']),
                'الميكروب': microbe.strip(),
                'البلدية': row['اسم_البلدية'],
                'المنشأة': row['اسم_المنشأة'],
            })
    
    if not microbe_records:
        print("  لا توجد بيانات كافية")
        return pd.DataFrame()
    
    microbe_df = pd.DataFrame(microbe_records)
    
    # أكثر الميكروبات ظهوراً
    microbe_counts = microbe_df['الميكروب'].value_counts()
    top_microbes = microbe_counts.head(10)
    
    print(f"\n  أكثر الميكروبات ظهوراً:")
    print(f"\n{'#':<4} {'الميكروب':<30} {'عدد الظهور':<14} {'النسبة%':<10}")
    print("-" * 60)
    total_appearances = microbe_counts.sum()
    for i, (microbe, count) in enumerate(top_microbes.items(), 1):
        pct = round(count / total_appearances * 100, 1)
        print(f"  {i:<3} {microbe:<28} {count:<14} {pct}%")
    
    # اتجاه شهري لأهم الميكروبات
    month_names = {1:'يناير', 2:'فبراير', 3:'مارس', 4:'أبريل', 5:'مايو', 6:'يونيو',
                   7:'يوليو', 8:'أغسطس', 9:'سبتمبر', 10:'أكتوبر', 11:'نوفمبر', 12:'ديسمبر'}
    
    top_microbe_names = top_microbes.head(6).index.tolist()
    
    microbe_monthly_data = {}
    all_microbe_trends = []
    
    for microbe in top_microbe_names:
        m_data = microbe_df[microbe_df['الميكروب'] == microbe]
        monthly = m_data.groupby('الشهر').size().reset_index(name='عدد_الظهور')
        monthly = monthly.sort_values('الشهر')
        
        microbe_monthly_data[microbe] = monthly
        
        # حساب الاتجاه
        if len(monthly) >= 3:
            x = monthly['الشهر'].values
            y = monthly['عدد_الظهور'].values
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            if slope > 0.3:
                trend = 'تصاعدي ↑'
            elif slope < -0.3:
                trend = 'تنازلي ↓'
            else:
                trend = 'مستقر ↔'
        else:
            slope = 0
            trend = 'بيانات قليلة'
        
        # خطورة الميكروب
        severity = 0
        for key, val in MICROBE_SEVERITY.items():
            if key in microbe or microbe in key:
                severity = val
                break
        
        all_microbe_trends.append({
            'الميكروب': microbe,
            'إجمالي_الظهور': len(m_data),
            'عدد_المنشآت': m_data['المنشأة'].nunique(),
            'عدد_البلديات': m_data['البلدية'].nunique(),
            'درجة_الخطورة': severity,
            'معامل_الميل': round(slope, 2),
            'الاتجاه': trend,
            'أشهر_الظهور': len(monthly),
        })
    
    microbe_trend_df = pd.DataFrame(all_microbe_trends)
    
    # رسم بياني - اتجاه أهم الميكروبات
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 14))
        
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
        markers = ['o', 's', '^', 'D', 'v', 'p']
        
        # الرسم العلوي: خطوط الاتجاه
        for i, microbe in enumerate(top_microbe_names):
            monthly = microbe_monthly_data[microbe]
            ax1.plot(monthly['الشهر'], monthly['عدد_الظهور'],
                    color=colors[i % len(colors)], marker=markers[i % len(markers)],
                    linewidth=2, markersize=8, label=ar(microbe))
        
        ax1.set_xlabel(ar('الشهر'), fontproperties=get_font(12))
        ax1.set_ylabel(ar('عدد مرات الظهور'), fontproperties=get_font(12))
        ax1.set_title(ar('اتجاه ظهور الميكروبات عبر الأشهر'), fontproperties=get_font(16, bold=True), pad=20)
        months_ar = [ar(month_names.get(m, str(m))) for m in range(1, 13)]
        ax1.set_xticks(range(1, 13))
        ax1.set_xticklabels(months_ar, fontproperties=get_font(9))
        ax1.legend(loc='upper left', prop=get_font(10), ncol=2)
        ax1.grid(True, alpha=0.3)
        
        # الرسم السفلي: أعمدة مقارنة
        microbes_ar = [ar(m) for m in top_microbes.head(10).index]
        counts = top_microbes.head(10).values
        bar_colors = []
        for m in top_microbes.head(10).index:
            sev = 0
            for key, val in MICROBE_SEVERITY.items():
                if key in m or m in key:
                    sev = val
                    break
            if sev >= 9:
                bar_colors.append('#e74c3c')
            elif sev >= 7:
                bar_colors.append('#f39c12')
            elif sev >= 5:
                bar_colors.append('#f1c40f')
            else:
                bar_colors.append('#3498db')
        
        bars = ax2.barh(range(len(microbes_ar)), counts, color=bar_colors, edgecolor='white')
        ax2.set_yticks(range(len(microbes_ar)))
        ax2.set_yticklabels(microbes_ar, fontproperties=get_font(10))
        ax2.set_xlabel(ar('عدد مرات الظهور'), fontproperties=get_font(12))
        ax2.set_title(ar('أكثر الميكروبات ظهوراً (ملون حسب الخطورة)'), fontproperties=get_font(14, bold=True))
        ax2.invert_yaxis()
        
        for bar, val in zip(bars, counts):
            ax2.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    str(val), va='center', fontsize=11, fontweight='bold')
        
        # مفتاح الألوان
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#e74c3c', label=ar('خطورة عالية جداً (9-10)')),
            Patch(facecolor='#f39c12', label=ar('خطورة عالية (7-8)')),
            Patch(facecolor='#f1c40f', label=ar('خطورة متوسطة (5-6)')),
            Patch(facecolor='#3498db', label=ar('خطورة منخفضة')),
        ]
        ax2.legend(handles=legend_elements, loc='lower right', prop=get_font(9))
        
        plt.tight_layout()
        chart_path = os.path.join(output_dir, 'trend_04_microbes.png')
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"\n  ✓ تم حفظ الرسم: {chart_path}")
    except Exception as e:
        print(f"\n  ✗ خطأ في الرسم: {e}")
    
    return microbe_trend_df


# ============================================================
# التنفيذ الرئيسي
# ============================================================

if __name__ == '__main__':
    print("="*60)
    print("  تحليل اتجاه التلوث - Contamination Trend Analysis")
    print("="*60)
    
    # تحميل البيانات
    try:
        df = load_data('Data 2025.xlsx')
        print(f"  تم تحميل {len(df):,} صف")
    except FileNotFoundError:
        print("  ✗ خطأ: ملف 'Data 2025.xlsx' غير موجود!")
        sys.exit(1)
    
    # تطبيق الاستثناءات
    df = apply_exclusion_filter(df)
    df = filter_invalid_municipalities(df)
    
    # إنشاء مجلد الرسوم
    output_dir = 'charts'
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. اتجاه شهري
    monthly_data = monthly_trend(df, output_dir)
    
    # 2. مقارنة ربع سنوية
    quarterly_data = quarterly_comparison(df, output_dir)
    
    # 3. اتجاه البلديات
    mun_trend_data = municipality_trend(df, output_dir)
    
    # 4. اتجاه الميكروبات
    microbe_trend_data = microbe_trend(df, output_dir)
    
    # حفظ في ملف إكسل
    output_file = 'تحليل_اتجاه_التلوث.xlsx'
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # الاتجاه الشهري
        month_cols = ['الشهر', 'اسم_الشهر', 'إجمالي_العينات', 'عينات_غير_مطابقة', 
                      'نسبة_عدم_المطابقة%', 'خط_الاتجاه', 'اتجاه_التلوث']
        monthly_data[month_cols].to_excel(writer, sheet_name='الاتجاه_الشهري', index=False)
        
        # المقارنة الربع سنوية
        q_cols = ['الربع', 'اسم_الربع', 'إجمالي_العينات', 'عينات_غير_مطابقة',
                  'نسبة_عدم_المطابقة%', 'عدد_المنشآت', 'عدد_البلديات', 'أبرز_الميكروبات']
        quarterly_data[q_cols].to_excel(writer, sheet_name='المقارنة_الربعية', index=False)
        
        # اتجاه البلديات
        if len(mun_trend_data) > 0:
            mun_trend_data.to_excel(writer, sheet_name='اتجاه_البلديات', index=False)
        
        # اتجاه الميكروبات
        if len(microbe_trend_data) > 0:
            microbe_trend_data.to_excel(writer, sheet_name='اتجاه_الميكروبات', index=False)
        
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
    print(f"  تم حفظ النتائج في: {output_file}")
    print(f"  الشيتات:")
    print(f"    1. الاتجاه_الشهري - خط اتجاه التلوث شهرياً")
    print(f"    2. المقارنة_الربعية - مقارنة Q1 vs Q2 vs Q3 vs Q4")
    print(f"    3. اتجاه_البلديات - هل كل بلدية تتحسن أو تسوء")
    print(f"    4. اتجاه_الميكروبات - هل ميكروب معين يزداد")
    print(f"\n  الرسوم البيانية في مجلد: {output_dir}/")
    print(f"    - trend_01_monthly.png")
    print(f"    - trend_02_quarterly.png")
    print(f"    - trend_03_municipality.png")
    print(f"    - trend_04_microbes.png")
    print(f"{'='*60}")
