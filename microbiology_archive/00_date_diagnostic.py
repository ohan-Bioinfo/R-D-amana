#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
00_date_diagnostic.py
سكربت تشخيصي لفحص التواريخ في ملف البيانات والتأكد من صحتها
يجب تشغيله أولاً قبل باقي السكربتات للتحقق من سلامة البيانات

الاستخدام:
    python 00_date_diagnostic.py
"""

import pandas as pd
import numpy as np
import os
import sys

def diagnose_dates(file_path='Data 2025.xlsx'):
    """فحص شامل للتواريخ في ملف البيانات"""
    
    print("=" * 70)
    print("  فحص تشخيصي للتواريخ في ملف البيانات")
    print("=" * 70)
    
    if not os.path.exists(file_path):
        print(f"\n❌ خطأ: الملف غير موجود: {file_path}")
        sys.exit(1)
    
    # قراءة البيانات الخام
    df_raw = pd.read_excel(file_path, sheet_name=0, usecols=[0], header=None, skiprows=1)
    df_raw.columns = ['تاريخ_خام']
    df_raw = df_raw.dropna(how='all').reset_index(drop=True)
    
    total_rows = len(df_raw)
    print(f"\n  إجمالي الصفوف: {total_rows:,}")
    
    # عرض أمثلة من البيانات الخام
    print(f"\n  أول 10 قيم خام:")
    for i in range(min(10, total_rows)):
        print(f"    صف {i+1}: {df_raw.iloc[i, 0]} (نوع: {type(df_raw.iloc[i, 0]).__name__})")
    
    # تحويل التواريخ مع dayfirst=True
    df_raw['تاريخ_محول'] = pd.to_datetime(df_raw['تاريخ_خام'], dayfirst=True, errors='coerce')
    
    # فحص القيم الفارغة بعد التحويل
    null_dates = df_raw['تاريخ_محول'].isna().sum()
    print(f"\n  تواريخ فارغة بعد التحويل: {null_dates}")
    
    # فحص السنوات
    df_raw['السنة'] = df_raw['تاريخ_محول'].dt.year
    year_counts = df_raw['السنة'].value_counts().sort_index()
    
    print(f"\n  توزيع السنوات:")
    for year, count in year_counts.items():
        status = "✓" if year == 2025 else "❌ (خارج 2025!)"
        print(f"    {int(year)}: {count:,} صف {status}")
    
    # عرض الصفوف ذات السنوات الخاطئة
    wrong_years = df_raw[df_raw['السنة'] != 2025]
    if len(wrong_years) > 0:
        print(f"\n  ⚠️ تم العثور على {len(wrong_years)} صف بتواريخ خارج 2025:")
        print(f"  هذه الصفوف سيتم استبعادها تلقائياً بواسطة فلتر السنة في جميع السكربتات")
        print(f"\n  أمثلة على التواريخ الخاطئة (أول 20):")
        for i, (_, row) in enumerate(wrong_years.head(20).iterrows()):
            print(f"    صف {_+2}: خام={row['تاريخ_خام']} → محول={row['تاريخ_محول']} (سنة {int(row['السنة'])})")
    else:
        print(f"\n  ✓ جميع التواريخ ضمن سنة 2025")
    
    # فحص الأشهر (بعد فلتر 2025)
    df_2025 = df_raw[df_raw['السنة'] == 2025].copy()
    df_2025['الشهر'] = df_2025['تاريخ_محول'].dt.month
    month_counts = df_2025['الشهر'].value_counts().sort_index()
    
    month_names = {
        1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
        5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }
    
    print(f"\n  توزيع الأشهر (سنة 2025 فقط):")
    for month in range(1, 13):
        count = month_counts.get(month, 0)
        bar = '█' * (count // 20) if count > 0 else ''
        status = f"{count:>5,} صف {bar}" if count > 0 else "    لا توجد بيانات"
        print(f"    {month:>2}. {month_names[month]:<10}: {status}")
    
    # نطاق التواريخ
    if len(df_2025) > 0:
        min_date = df_2025['تاريخ_محول'].min()
        max_date = df_2025['تاريخ_محول'].max()
        print(f"\n  نطاق التواريخ (2025): {min_date.strftime('%Y-%m-%d')} إلى {max_date.strftime('%Y-%m-%d')}")
    
    # ملخص
    print(f"\n{'=' * 70}")
    print(f"  الملخص:")
    print(f"    إجمالي الصفوف: {total_rows:,}")
    print(f"    صفوف 2025: {len(df_2025):,}")
    print(f"    صفوف مستبعدة: {len(wrong_years):,}")
    print(f"    أشهر مغطاة: {len(month_counts)}/12")
    print(f"{'=' * 70}")
    
    return df_raw, df_2025


if __name__ == '__main__':
    diagnose_dates('Data 2025.xlsx')
