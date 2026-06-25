#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_visit_counts.py
حساب عدد مرات سحب العينات من كل منشأة بناءً على التواريخ المختلفة
"""

import pandas as pd
import numpy as np
import os
import sys

# استيراد قائمة العينات المستثناة والدوال المشتركة
from excluded_samples import filter_excluded_rows

# ============================================================
# إعدادات الأعمدة
# ============================================================
DATE_COL_INDEX = 0       # عمود A - تاريخ سحب العينة
CATEGORY_COL_INDEX = 1   # عمود B - فئة العينة
SAMPLE_NAME_COL_INDEX = 2  # عمود C - اسم العينة
FACILITY_COL_INDEX = 4   # عمود E - اسم المنشأة
MUNICIPALITY_COL_INDEX = 5  # عمود F - اسم البلدية



# ============================================================
# تحميل البيانات
# ============================================================
def load_data():
    """تحميل البيانات من ملف الإكسل"""
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Data 2025.xlsx')
    if not os.path.exists(file_path):
        print(f"خطأ: الملف غير موجود: {file_path}")
        sys.exit(1)
    
    df = pd.read_excel(file_path, sheet_name=0)
    print(f"تم تحميل {len(df)} صف من البيانات")
    print(f"أسماء الأعمدة: {list(df.columns)}")
    
    # إعادة تسمية الأعمدة
    cols = df.columns.tolist()
    col_map = {}
    if len(cols) > DATE_COL_INDEX:
        col_map[cols[DATE_COL_INDEX]] = 'تاريخ_سحب_العينة'
    if len(cols) > CATEGORY_COL_INDEX:
        col_map[cols[CATEGORY_COL_INDEX]] = 'فئة_العينة'
    if len(cols) > SAMPLE_NAME_COL_INDEX:
        col_map[cols[SAMPLE_NAME_COL_INDEX]] = 'اسم_العينة'
    if len(cols) > FACILITY_COL_INDEX:
        col_map[cols[FACILITY_COL_INDEX]] = 'اسم_المنشأة'
    if len(cols) > MUNICIPALITY_COL_INDEX:
        col_map[cols[MUNICIPALITY_COL_INDEX]] = 'اسم_البلدية'
    
    df = df.rename(columns=col_map)
    
    # تحويل التاريخ
    df['تاريخ_سحب_العينة'] = pd.to_datetime(df['تاريخ_سحب_العينة'], dayfirst=True, errors='coerce')
    # فلتر: الاحتفاظ فقط بتواريخ سنة 2025
    before_filter = len(df)
    df = df[df['تاريخ_سحب_العينة'].dt.year == 2025]
    after_filter = len(df)
    if before_filter != after_filter:
        print(f'تم استبعاد {before_filter - after_filter} صف بتواريخ خارج 2025')
    
    # استثناء العينات الخاصة والعينات المحددة (لحوم نيئة/أعضاء/دجاج ني/كباب)
    df = filter_excluded_rows(df)
    
    # حذف الصفوف بدون تاريخ أو اسم منشأة
    df = df.dropna(subset=['تاريخ_سحب_العينة', 'اسم_المنشأة'])
    
    # تنظيف أسماء المنشآت
    df['اسم_المنشأة'] = df['اسم_المنشأة'].astype(str).str.strip()
    if 'اسم_البلدية' in df.columns:
        df['اسم_البلدية'] = df['اسم_البلدية'].astype(str).str.strip()
    
    # استخراج التاريخ فقط (بدون الوقت)
    df['تاريخ_السحب'] = df['تاريخ_سحب_العينة'].dt.date
    
    print(f"بعد التنظيف: {len(df)} صف")
    print(f"نطاق التواريخ: {df['تاريخ_سحب_العينة'].min().strftime('%Y-%m-%d')} إلى {df['تاريخ_سحب_العينة'].max().strftime('%Y-%m-%d')}")
    print(f"عدد المنشآت: {df['اسم_المنشأة'].nunique()}")
    
    return df

# ============================================================
# حساب عدد مرات السحب لكل منشأة
# ============================================================
def calculate_visit_counts(df):
    """حساب عدد الزيارات (تواريخ السحب المختلفة) لكل منشأة"""
    
    # --- شيت 1: ملخص المنشآت ---
    facility_stats = []
    
    for facility, group in df.groupby('اسم_المنشأة'):
        unique_dates = group['تاريخ_السحب'].nunique()
        total_samples = len(group)
        samples_per_visit = round(total_samples / unique_dates, 1) if unique_dates > 0 else 0
        
        # البلدية
        municipality = 'غير محدد'
        if 'اسم_البلدية' in group.columns:
            municipality = group['اسم_البلدية'].mode().iloc[0] if len(group['اسم_البلدية'].mode()) > 0 else 'غير محدد'
        
        # تواريخ الزيارات
        dates_list = sorted(group['تاريخ_السحب'].unique())
        dates_str = ' | '.join([d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in dates_list])
        
        # أول وآخر زيارة
        first_visit = min(dates_list)
        last_visit = max(dates_list)
        
        facility_stats.append({
            'اسم_المنشأة': facility,
            'البلدية': municipality,
            'عدد_مرات_السحب': unique_dates,
            'إجمالي_العينات': total_samples,
            'متوسط_العينات_لكل_زيارة': samples_per_visit,
            'أول_زيارة': first_visit,
            'آخر_زيارة': last_visit,
            'تواريخ_الزيارات': dates_str
        })
    
    df_facilities = pd.DataFrame(facility_stats)
    df_facilities = df_facilities.sort_values('عدد_مرات_السحب', ascending=False).reset_index(drop=True)
    df_facilities.index += 1
    df_facilities.index.name = '#'
    
    # --- شيت 2: ملخص حسب البلدية ---
    municipality_stats = []
    
    if 'اسم_البلدية' in df.columns:
        for mun, group in df.groupby('اسم_البلدية'):
            # استثناء البلديات غير الصالحة
            if pd.isna(mun) or str(mun).strip() in ['', '-', '—', 'nan']:
                continue
            if len(str(mun).strip()) <= 1:
                continue
            
            num_facilities = group['اسم_المنشأة'].nunique()
            total_samples = len(group)
            total_visits = group.groupby('اسم_المنشأة')['تاريخ_السحب'].nunique().sum()
            avg_visits_per_facility = round(total_visits / num_facilities, 1) if num_facilities > 0 else 0
            avg_samples_per_facility = round(total_samples / num_facilities, 1) if num_facilities > 0 else 0
            
            municipality_stats.append({
                'البلدية': mun,
                'عدد_المنشآت': num_facilities,
                'إجمالي_الزيارات': total_visits,
                'متوسط_الزيارات_لكل_منشأة': avg_visits_per_facility,
                'إجمالي_العينات': total_samples,
                'متوسط_العينات_لكل_منشأة': avg_samples_per_facility
            })
    
    df_municipalities = pd.DataFrame(municipality_stats)
    df_municipalities = df_municipalities.sort_values('عدد_المنشآت', ascending=False).reset_index(drop=True)
    df_municipalities.index += 1
    df_municipalities.index.name = '#'
    
    # --- شيت 3: تفصيل الزيارات ---
    visit_details = []
    
    for facility, group in df.groupby('اسم_المنشأة'):
        municipality = 'غير محدد'
        if 'اسم_البلدية' in group.columns:
            municipality = group['اسم_البلدية'].mode().iloc[0] if len(group['اسم_البلدية'].mode()) > 0 else 'غير محدد'
        
        for date, date_group in group.groupby('تاريخ_السحب'):
            visit_details.append({
                'اسم_المنشأة': facility,
                'البلدية': municipality,
                'تاريخ_السحب': date,
                'عدد_العينات': len(date_group),
                'أنواع_العينات': ' ، '.join(date_group['اسم_العينة'].unique().tolist()) if 'اسم_العينة' in date_group.columns else '-'
            })
    
    df_details = pd.DataFrame(visit_details)
    df_details = df_details.sort_values(['اسم_المنشأة', 'تاريخ_السحب']).reset_index(drop=True)
    df_details.index += 1
    df_details.index.name = '#'
    
    # --- شيت 4: المنشآت بزيارة واحدة فقط ---
    single_visit = df_facilities[df_facilities['عدد_مرات_السحب'] == 1].copy()
    
    # --- شيت 5: المنشآت الأكثر زيارة (3+ زيارات) ---
    frequent_visits = df_facilities[df_facilities['عدد_مرات_السحب'] >= 3].copy()
    
    return df_facilities, df_municipalities, df_details, single_visit, frequent_visits

# ============================================================
# حفظ النتائج
# ============================================================
def save_results(df_facilities, df_municipalities, df_details, single_visit, frequent_visits):
    """حفظ النتائج في ملف إكسل"""
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'عدد_مرات_السحب.xlsx')
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # شيت 1: ملخص المنشآت
        df_facilities.to_excel(writer, sheet_name='ملخص_المنشآت')
        
        # شيت 2: ملخص البلديات
        df_municipalities.to_excel(writer, sheet_name='ملخص_البلديات')
        
        # شيت 3: تفصيل الزيارات
        df_details.to_excel(writer, sheet_name='تفصيل_الزيارات')
        
        # شيت 4: منشآت بزيارة واحدة
        single_visit.to_excel(writer, sheet_name='زيارة_واحدة_فقط')
        
        # شيت 5: منشآت متكررة الزيارة
        frequent_visits.to_excel(writer, sheet_name='أكثر_من_3_زيارات')
        
        # تنسيق عرض الأعمدة
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_length = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[col_letter].width = adjusted_width
    
    print(f"\n✓ تم حفظ النتائج في: {output_path}")
    return output_path

# ============================================================
# طباعة الملخص
# ============================================================
def print_summary(df_facilities, df_municipalities):
    """طباعة ملخص النتائج"""
    
    print("\n" + "=" * 60)
    print("ملخص عدد مرات السحب من المنشآت")
    print("=" * 60)
    
    total_facilities = len(df_facilities)
    total_visits = df_facilities['عدد_مرات_السحب'].sum()
    avg_visits = df_facilities['عدد_مرات_السحب'].mean()
    max_visits = df_facilities['عدد_مرات_السحب'].max()
    single_visit_count = len(df_facilities[df_facilities['عدد_مرات_السحب'] == 1])
    multi_visit_count = len(df_facilities[df_facilities['عدد_مرات_السحب'] > 1])
    
    print(f"\nإجمالي المنشآت: {total_facilities}")
    print(f"إجمالي الزيارات: {total_visits}")
    print(f"متوسط الزيارات لكل منشأة: {avg_visits:.1f}")
    print(f"أعلى عدد زيارات لمنشأة واحدة: {max_visits}")
    print(f"منشآت بزيارة واحدة فقط: {single_visit_count} ({single_visit_count/total_facilities*100:.1f}%)")
    print(f"منشآت بأكثر من زيارة: {multi_visit_count} ({multi_visit_count/total_facilities*100:.1f}%)")
    
    print(f"\n--- أكثر 10 منشآت زيارة ---")
    top10 = df_facilities.head(10)
    for idx, row in top10.iterrows():
        print(f"  {idx}. {row['اسم_المنشأة']} - {row['عدد_مرات_السحب']} زيارة ({row['إجمالي_العينات']} عينة) - {row['البلدية']}")
    
    if len(df_municipalities) > 0:
        print(f"\n--- ملخص البلديات ---")
        for idx, row in df_municipalities.iterrows():
            print(f"  {idx}. {row['البلدية']}: {row['عدد_المنشآت']} منشأة، {row['إجمالي_الزيارات']} زيارة، متوسط {row['متوسط_الزيارات_لكل_منشأة']} زيارة/منشأة")

# ============================================================
# التنفيذ الرئيسي
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("حساب عدد مرات سحب العينات من كل منشأة")
    print("بناءً على التواريخ المختلفة للسحب")
    print("=" * 60)
    
    # تحميل البيانات
    df = load_data()
    
    # إعادة تسمية عمود اسم العينة إذا وجد
    cols = df.columns.tolist()
    if len(cols) > 2:
        # عمود C = اسم العينة
        original_col = cols[2] if cols[2] != 'اسم_العينة' else None
        if original_col and original_col in df.columns:
            df = df.rename(columns={original_col: 'اسم_العينة'})
    
    # حساب عدد مرات السحب
    df_facilities, df_municipalities, df_details, single_visit, frequent_visits = calculate_visit_counts(df)
    
    # طباعة الملخص
    print_summary(df_facilities, df_municipalities)
    
    # حفظ النتائج
    output_path = save_results(df_facilities, df_municipalities, df_details, single_visit, frequent_visits)
    
    print(f"\nالملف يحتوي على 5 شيتات:")
    print(f"  1. ملخص_المنشآت - جميع المنشآت مع عدد مرات السحب")
    print(f"  2. ملخص_البلديات - عدد المنشآت والزيارات لكل بلدية")
    print(f"  3. تفصيل_الزيارات - كل زيارة مع تاريخها وعدد العينات")
    print(f"  4. زيارة_واحدة_فقط - المنشآت التي زُيرت مرة واحدة")
    print(f"  5. أكثر_من_3_زيارات - المنشآت الأكثر زيارة")
    
    print("\n✓ تم الانتهاء بنجاح!")
