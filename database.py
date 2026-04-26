# database.py
import sqlite3
import logging
from datetime import datetime, timedelta
import os

DB_FILE = "print_history.db"

def init_db():
    """تهيئة قاعدة البيانات بإنشاء الجداول اللازمة إذا لم تكن موجودة."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS printed_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    print_time TEXT,
                    metal_type TEXT,
                    actual_purity REAL,
                    actual_weight REAL,
                    equivalent_weight REAL,
                    printer_name TEXT
                )
            ''')
            conn.commit()
    except Exception as e:
        logging.error(f"خطأ في تهيئة قاعدة البيانات: {e}")

def save_print_record(metal_type, purity, weight, equiv_weight, printer_name):
    """تخزين تفاصيل الملصق في قاعدة البيانات وإرجاع الـ ID الجديد."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO printed_labels 
                (print_time, metal_type, actual_purity, actual_weight, equivalent_weight, printer_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (current_time, metal_type, purity, weight, equiv_weight, printer_name))
            conn.commit()
            return cursor.lastrowid  # <--- إضافة هذا السطر لإرجاع رقم الطلب الجديد
    except Exception as e:
        logging.error(f"خطأ في تخزين السجل: {e}")
        return None

# ==========================================
# دوال استرجاع البيانات (لواجهة السجلات)
# ==========================================

def get_last_month_records():
    """جلب سجلات آخر 30 يوماً كإعداد افتراضي للواجهة."""
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
    end_date = datetime.now().strftime("%Y-%m-%d 23:59:59")
    return get_records_by_date_range(start_date, end_date)

def get_records_by_date_range(start_date, end_date):
    """
    جلب السجلات بناءً على نطاق زمني محدد.
    صيغة التواريخ المتوقعة: YYYY-MM-DD HH:MM:SS
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM printed_labels 
                WHERE print_time >= ? AND print_time <= ?
                ORDER BY print_time DESC
            ''', (start_date, end_date))
            return cursor.fetchall()
    except Exception as e:
        logging.error(f"خطأ في جلب السجلات بالنطاق الزمني: {e}")
        return []

def get_record_by_id(record_id):
    """البحث المباشر عن طلب محدد برقم الـ ID لعرض تفاصيله."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM printed_labels WHERE id = ?', (record_id,))
            return cursor.fetchone()
    except Exception as e:
        logging.error(f"خطأ في البحث عن السجل: {e}")
        return None