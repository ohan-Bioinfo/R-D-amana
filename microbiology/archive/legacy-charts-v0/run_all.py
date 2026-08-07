#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
 سكربت التشغيل الشامل - Run All Scripts
=============================================================
 يقوم بتشغيل جميع سكربتات التحليل بالترتيب الصحيح:
   0. فحص تشخيصي للتواريخ
   1. التحليل الإحصائي
   2. الرسوم البيانية
   3. تقرير تقييم المخاطر
   4. التقارير الإضافية
   5. تحليل اتجاه التلوث
   6. عدد مرات السحب
=============================================================
 الاستخدام:
   python run_all.py
=============================================================
"""

import subprocess
import sys
import os
import time

# ============================================================
# الإعدادات
# ============================================================

# مسار مجلد العمل (نفس مجلد هذا الملف)
WORK_DIR = os.path.dirname(os.path.abspath(__file__))

# ملف البيانات
DATA_FILE = os.path.join(WORK_DIR, 'Data 2025.xlsx')

# قائمة السكربتات بالترتيب
SCRIPTS = [
    ('00_date_diagnostic.py', 'فحص تشخيصي للتواريخ'),
    ('01_statistics.py',      'التحليل الإحصائي الشامل'),
    ('02_charts.py',          'الرسوم البيانية'),
    ('03_risk_assessment.py', 'تقرير تقييم المخاطر'),
    ('04_extra_reports.py',   'التقارير الإضافية'),
    ('05_trend_analysis.py',  'تحليل اتجاه التلوث'),
    ('06_visit_counts.py',    'عدد مرات السحب'),
]


# ============================================================
# تثبيت المكتبات المطلوبة
# ============================================================

def install_requirements():
    """تثبيت جميع المكتبات المطلوبة"""
    print("\n" + "=" * 60)
    print("  تثبيت المكتبات المطلوبة")
    print("=" * 60)
    
    packages = [
        'pandas',
        'numpy',
        'matplotlib',
        'seaborn',
        'openpyxl',
        'arabic-reshaper',
        'python-bidi',
    ]
    
    for pkg in packages:
        try:
            # محاولة استيراد المكتبة
            module_name = pkg.replace('-', '_')
            if module_name == 'python_bidi':
                module_name = 'bidi'
            __import__(module_name)
            print(f"  ✓ {pkg} - موجود")
        except ImportError:
            print(f"  ⬇ تثبيت {pkg}...")
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                capture_output=True
            )
            print(f"  ✓ {pkg} - تم التثبيت")
    
    print()


# ============================================================
# تشغيل سكربت واحد
# ============================================================

def run_script(script_name, description):
    """تشغيل سكربت واحد وعرض النتيجة"""
    script_path = os.path.join(WORK_DIR, script_name)
    
    if not os.path.exists(script_path):
        print(f"  ❌ الملف غير موجود: {script_name}")
        return False
    
    print(f"\n{'=' * 60}")
    print(f"  ▶ تشغيل: {script_name}")
    print(f"    {description}")
    print(f"{'=' * 60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=WORK_DIR,
            capture_output=False,
            timeout=300  # 5 دقائق كحد أقصى
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n  ✓ اكتمل بنجاح ({elapsed:.1f} ثانية)")
            return True
        else:
            print(f"\n  ⚠ انتهى مع أخطاء (كود الخروج: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"\n  ❌ تجاوز الوقت المسموح (5 دقائق)")
        return False
    except Exception as e:
        print(f"\n  ❌ خطأ: {e}")
        return False


# ============================================================
# التنفيذ الرئيسي
# ============================================================

if __name__ == '__main__':
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + "  نظام تحليل بيانات الفحص الرقابي على المنشآت الغذائية  ".center(58) + "║")
    print("║" + "  Food Safety Inspection Analysis System  ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    
    # التحقق من وجود ملف البيانات
    if not os.path.exists(DATA_FILE):
        print(f"\n  ❌ خطأ: ملف البيانات غير موجود!")
        print(f"     المسار المتوقع: {DATA_FILE}")
        print(f"\n  الرجاء وضع ملف 'Data 2025.xlsx' في المجلد:")
        print(f"     {WORK_DIR}")
        sys.exit(1)
    
    print(f"\n  ✓ ملف البيانات موجود: Data 2025.xlsx")
    print(f"  📁 مجلد العمل: {WORK_DIR}")
    
    # تثبيت المكتبات
    install_requirements()
    
    # تشغيل جميع السكربتات
    results = {}
    total_start = time.time()
    
    for script_name, description in SCRIPTS:
        success = run_script(script_name, description)
        results[script_name] = success
    
    total_elapsed = time.time() - total_start
    
    # ============================================================
    # ملخص النتائج
    # ============================================================
    
    print("\n\n" + "╔" + "═" * 58 + "╗")
    print("║" + "  ملخص التشغيل  ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    
    success_count = sum(1 for v in results.values() if v)
    fail_count = sum(1 for v in results.values() if not v)
    
    for script_name, success in results.items():
        status = "✓ نجح" if success else "❌ فشل"
        print(f"  {status}  {script_name}")
    
    print(f"\n  الإجمالي: {success_count} نجح / {fail_count} فشل")
    print(f"  الوقت الكلي: {total_elapsed:.1f} ثانية")
    
    # عرض الملفات المُنتجة
    print(f"\n{'=' * 60}")
    print("  الملفات المُنتجة:")
    print("=" * 60)
    
    output_files = [
        ('نتائج_التحليل_الإحصائي.xlsx', 'التحليل الإحصائي الشامل (6 شيتات)'),
        ('charts/', 'مجلد الرسوم البيانية (10 رسوم)'),
        ('تقرير_تقييم_المخاطر.html', 'تقرير تقييم المخاطر التفاعلي'),
        ('تقييم_مخاطر_المنشآت.xlsx', 'بيانات تقييم المخاطر'),
        ('تقارير_إضافية.xlsx', 'البلديات + عينات السالمونيلا'),
        ('تحليل_الاتجاه.xlsx', 'بيانات اتجاه التلوث'),
        ('trend_charts/', 'مجلد رسوم الاتجاهات'),
        ('عدد_مرات_السحب.xlsx', 'عدد مرات سحب العينات (5 شيتات)'),
    ]
    
    for filename, description in output_files:
        filepath = os.path.join(WORK_DIR, filename)
        if os.path.exists(filepath):
            if os.path.isdir(filepath):
                file_count = len([f for f in os.listdir(filepath) if not f.startswith('.')])
                print(f"  ✓ {filename} ({file_count} ملف) - {description}")
            else:
                size_kb = os.path.getsize(filepath) / 1024
                print(f"  ✓ {filename} ({size_kb:.0f} KB) - {description}")
        else:
            print(f"  ○ {filename} - {description}")
    
    print(f"\n{'=' * 60}")
    
    if fail_count == 0:
        print("  ✓ تم الانتهاء بنجاح! جميع التحليلات جاهزة.")
    else:
        print(f"  ⚠ انتهى مع {fail_count} أخطاء. راجع الرسائل أعلاه.")
    
    print(f"{'=' * 60}\n")
