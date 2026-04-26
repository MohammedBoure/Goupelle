# main.py
import sys
import os
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_dialog import MainPrintDialog

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def get_resource_path(relative_path):
    """ إرجاع المسار الصحيح للملف سواء في بيئة التطوير أو بعد التجميع """
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 1. تعيين أيقونة البرنامج
    logo_path = get_resource_path(os.path.join("ui", "logo.png"))
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
    else:
        logging.warning(f"Logo not found at: {logo_path}")
    
    # 2. تطبيق ستايل الواجهة الاحترافي (Modern Theme)
    app.setStyleSheet("""
        /* إعدادات الخطوط والخلفية الأساسية */
        QWidget {
            font-family: "Segoe UI", "Tajawal", "Arial";
        }
        QDialog { 
            background-color: #f0f4f8; /* لون رمادي مزرق هادئ جداً مريح للعين */
        }
        
        /* عنوان البرنامج */
        QLabel#header_title { 
            color: #1e293b; 
            font-size: 28px; 
            font-weight: 900; 
            letter-spacing: 1px;
        }
        
        /* الأزرار العلوية (الإعدادات والسجل) */
        QPushButton#btn_settings, QPushButton#btn_history {
            background-color: #ffffff;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            color: #475569;
            font-size: 18px;
        }
        QPushButton#btn_settings:hover, QPushButton#btn_history:hover {
            background-color: #e0f2fe;
            border: 2px solid #38bdf8;
            color: #0284c7;
        }

        /* حاوية الوزن والعيار (البطاقة) */
        QGroupBox { 
            background-color: #ffffff;
            border: 1px solid #e2e8f0; 
            border-radius: 16px; 
            margin-top: 32px; /* مسافة لدفع الإطار أسفل العنوان */
        }
        QGroupBox::title { 
            subcontrol-origin: margin; 
            subcontrol-position: top center; 
            background-color: #3498db; 
            color: #ffffff; 
            padding: 8px 25px;
            border-radius: 14px;
            font-size: 15px;
            font-weight: bold;
        }

        /* حقول الإدخال */
        QLineEdit { 
            background-color: #f8fafc;
            border: 2px solid #e2e8f0; 
            border-radius: 10px; 
            min-height: 40px; /* الطول المناسب لجعل الحقل مريحاً للكتابة */
            padding-left: 10px;
            padding-right: 10px;
            font-size: 18px;
            font-weight: bold;
            color: #0f172a;
            selection-background-color: #3b82f6; /* لون التحديد عند تظليل النص */
        }
        QLineEdit:focus {
            background-color: #ffffff;
            border: 2px solid #3b82f6; /* إطار أزرق فاقع عند الكتابة */
        }
        QLineEdit::placeholder {
            color: #94a3b8;
        }

        /* النصوص (Labels) */
        QLabel { 
            font-size: 14px; 
            font-weight: bold; 
            color: #64748b; 
        }

        /* زر الطباعة العملاق */
        QPushButton#btn_print {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
            color: white;
            font-size: 18px;
            font-weight: bold;
            border: none;
            border-radius: 14px;
            min-height: 55px;
            margin-top: 10px;
        }
        QPushButton#btn_print:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #60a5fa, stop:1 #3b82f6);
        }
        QPushButton#btn_print:pressed {
            background-color: #1d4ed8;
        }
        
        /* القوائم المنسدلة والأرقام (لواجهة الإعدادات) */
        QComboBox, QDoubleSpinBox, QSpinBox { 
            padding: 6px; 
            border: 2px solid #e2e8f0; 
            border-radius: 8px; 
            background: #f8fafc; 
            min-height: 28px; 
            font-size: 14px;
            font-weight: bold;
        }
        QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
            border: 2px solid #3b82f6;
            background: #ffffff;
        }
    """)

    # 3. إظهار الواجهة الرئيسية للطباعة
    dialog = MainPrintDialog()
    dialog.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()