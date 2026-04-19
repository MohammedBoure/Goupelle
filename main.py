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
        # إذا كان البرنامج يعمل كملف تنفيذي مجمع
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # إذا كان البرنامج يعمل كسكريبت بايثون عادي
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 1. تعيين أيقونة البرنامج (شريط العنوان وشريط المهام)
    logo_path = get_resource_path(os.path.join("ui", "logo.png"))
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
    else:
        logging.warning(f"Logo not found at: {logo_path}")
    
    # 2. تطبيق ستايل الواجهة
    app.setStyleSheet("""
        QDialog { background-color: #f4f7fa; }
        QLabel { color: #2c3e50; font-family: "Segoe UI"; font-size: 14px; }
        QGroupBox { font-weight: bold; border: 1px solid #cfd8dc; border-radius: 6px; margin-top: 15px; padding-top: 15px; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; color: #d4af37; }
        QComboBox, QDoubleSpinBox { padding: 5px; border: 1px solid #cfd8dc; border-radius: 4px; background: white; min-height: 25px; font-size: 14px;}
        QPushButton:hover { background-color: #f5f5f5; }
    """)

    # 3. إظهار الواجهة الرئيسية للطباعة
    dialog = MainPrintDialog()
    dialog.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()