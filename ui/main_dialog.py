import os
import io
import json
import logging
import re
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                               QLabel, QLineEdit, QPushButton, 
                               QGroupBox, QGridLayout, QMessageBox)
from PySide6.QtGui import QDoubleValidator,QPixmap
from PySide6.QtCore import Qt, QFile, QTextStream
from .settings_dialog import SettingsDialog
import sys
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    import win32print
except ImportError as e:
    logging.error(f"Missing printing libraries: {e}")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    logging.warning("Arabic reshaping libraries missing. Please run: pip install arabic-reshaper python-bidi")

class MainPrintDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("نظام طباعة ملصقات المجوهرات")
        
        self.setFixedSize(500, 520) 
        self.config_file = "label_config.json"
        
        self.init_ui()
        self.load_professional_style()
        self.gold_input.setFocus()

    def load_professional_style(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        style_path = os.path.join(current_dir, "styles.qss")
        if os.path.exists(style_path):
            file = QFile(style_path)
            if file.open(QFile.ReadOnly | QFile.Text):
                stream = QTextStream(file)
                self.setStyleSheet(stream.readAll())
                file.close()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # --- الهيدر ---
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Goupelle")
        title_label.setObjectName("header_title")
        
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_settings)
        main_layout.addLayout(header_layout)
        
        # --- منطقة الإدخال ---
        group_box = QGroupBox("الوزن و العيار")
        grid = QGridLayout(group_box)
        
        grid.setContentsMargins(20, 35, 20, 20) 
        grid.setVerticalSpacing(20) 
        grid.setHorizontalSpacing(15)
        
        validator = QDoubleValidator(0.00, 9999.99, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)

        # الذهب
        grid.addWidget(QLabel("عيار الذهب:"), 0, 0)
        self.gold_input = QLineEdit()
        self.gold_input.setPlaceholderText("مثال: 18")
        self.gold_input.setValidator(validator)
        self.gold_input.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.gold_input, 0, 1)

        # الفضة
        grid.addWidget(QLabel("عيار الفضة:"), 1, 0)
        self.silver_input = QLineEdit()
        self.silver_input.setPlaceholderText("مثال: 925")
        self.silver_input.setValidator(validator)
        self.silver_input.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.silver_input, 1, 1)

        # الوزن
        grid.addWidget(QLabel("الوزن (غ):"), 2, 0)
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("0.00")
        self.weight_input.setValidator(validator)
        self.weight_input.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.weight_input, 2, 1)

        main_layout.addWidget(group_box)
        
        # --- زر الطباعة ---
        self.btn_print = QPushButton("🖨️ طباعة ملصق (Enter)")
        self.btn_print.setObjectName("btn_print")
        self.btn_print.setCursor(Qt.PointingHandCursor)
        self.btn_print.clicked.connect(self.print_label)
        main_layout.addWidget(self.btn_print)

        # تذييل
        footer_info = QLabel("النظام مهيأ للعمل مع الطابعات الحرارية TSPL")
        footer_info.setAlignment(Qt.AlignCenter)
        footer_info.setStyleSheet("color: #95a5a6; font-size: 11px;")
        main_layout.addWidget(footer_info)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focused = self.focusWidget()
            if focused == self.gold_input:
                if self.gold_input.text().strip():
                    self.silver_input.clear()
                    self.weight_input.setFocus()
                else:
                    self.silver_input.setFocus()
            elif focused == self.silver_input:
                if self.silver_input.text().strip():
                    self.gold_input.clear()
                self.weight_input.setFocus()
            elif focused == self.weight_input:
                self.print_label()
        else:
            super().keyPressEvent(event)

    def load_config(self):
        default_config = {
            "printer_name": "", 
            "label_width_mm": 40, "label_height_mm": 20, 
            "gap_mm": 2.0, "offset_x_mm": 0.0, "offset_y_mm": 0.0,
            "orientation": "Horizontal",
            "logo": {"show": False, "path": "", "x": 0, "y": 0, "angle": 0},
            "elements": {
                "store": {"show": True, "text": "مجوهرات الذهب", "x": 15, "y": 2, "size": 14, "font": "arial.ttf", "angle": 0},
                "metal": {"show": True, "text": "Or", "x": 5, "y": 8, "size": 12, "font": "arial.ttf", "angle": 0},
                "purity": {"show": True, "text": "Titre: 18", "x": 20, "y": 8, "size": 12, "font": "arial.ttf", "angle": 0},
                "extra": {"show": True, "text": "mg/g"},
                "weight": {"show": True, "text": "Poids: 4.25 g", "x": 5, "y": 14, "size": 12, "font": "arial.ttf", "angle": 0},
                "date": {"show": False, "text": "", "x": 5, "y": 18, "size": 10, "font": "arial.ttf", "angle": 0}
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k == "elements" and isinstance(v, dict):
                            for ek, ev in v.items():
                                if ek in default_config["elements"]:
                                    default_config["elements"][ek].update(ev)
                        elif k in ["logo"] and isinstance(v, dict):
                            default_config[k].update(v)
                        else:
                            default_config[k] = v
            except Exception as e:
                logging.error(f"Config error: {e}")
        return default_config

    def _draw_rotated_text(self, img, text, x, y, font, angle):
        if not text: return
        try:
            # 🟢 الحماية من قلب الأرقام والوقت: 
            # يتم تطبيق مكتبة إعادة التشكيل (bidi) فقط إذا كان النص يحتوي على أحرف عربية
            if re.search(r'[\u0600-\u06FF]', text):
                reshaped_text = arabic_reshaper.reshape(text)
                text = get_display(reshaped_text)
        except Exception:
            pass
        
        safe_width = int(font.size * len(text) * 1.5 + 50)
        safe_height = int(font.size * 3 + 50)
        
        txt_img = Image.new('RGBA', (safe_width, safe_height), (255, 255, 255, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((10, 10), text, font=font, fill=(0, 0, 0, 255))
        
        bbox = txt_img.getbbox()
        if not bbox: return
        txt_img = txt_img.crop(bbox)
        
        if angle != 0:
            txt_img = txt_img.rotate(angle, expand=True)
            
        img.paste(txt_img, (x, y), txt_img)

    def print_label(self):
        gold_val = self.gold_input.text().replace(',', '.')
        silver_val = self.silver_input.text().replace(',', '.')
        weight_val = self.weight_input.text().replace(',', '.')
        
        if not weight_val or float(weight_val or 0) <= 0:
            self.weight_input.setFocus()
            return
            
        if not gold_val and not silver_val:
            self.gold_input.setFocus()
            return

        metal_type = "Or" if gold_val else "Argent"
        purity = gold_val if gold_val else silver_val
        
        cfg = self.load_config()
        printer_name = cfg.get("printer_name", "")
        
        if not printer_name:
            QMessageBox.warning(self, "تنبيه", "يجب اختيار طابعة من الإعدادات أولاً.")
            self.open_settings()
            return

        try:
            DPI_MULT = 8 
            w_mm = cfg.get("label_width_mm", 40)
            h_mm = cfg.get("label_height_mm", 20)
            gap_mm = cfg.get("gap_mm", 2.0)
            global_off_x = int(cfg.get("offset_x_mm", 0.0) * DPI_MULT)
            global_off_y = int(cfg.get("offset_y_mm", 0.0) * DPI_MULT)
            
            w_px = int(w_mm * DPI_MULT)
            h_px = int(h_mm * DPI_MULT)
            
            img = Image.new('RGBA', (w_px, h_px), (255, 255, 255, 255))

            def get_font(font_name, size):
                try: return ImageFont.truetype(font_name, size)
                except: return ImageFont.load_default()

            lg = cfg.get("logo", {})
            if lg.get("show") and os.path.exists(lg.get("path", "")):
                try:
                    logo = Image.open(lg["path"]).convert("RGBA")
                    l_sett = cfg.get("logo_settings", {})
                    scale = l_sett.get('scale', 100) / 100.0
                    new_w, new_h = int(logo.width * scale), int(logo.height * scale)
                    if new_w > 0 and new_h > 0:
                        logo = logo.resize((new_w, new_h))
                        thresh = l_sett.get('threshold', 128)
                        logo_l = logo.convert("L").point(lambda p: 0 if p < thresh else 255, '1')
                        final_logo = Image.new("RGBA", logo.size)
                        final_logo.paste((0,0,0,255), mask=ImageOps.invert(logo_l.convert("L")))
                        
                        angle = lg.get("angle", 0)
                        if angle != 0:
                            final_logo = final_logo.rotate(angle, expand=True)
                            
                        lx = int(lg.get("x", 0) * DPI_MULT) + global_off_x
                        ly = int(lg.get("y", 0) * DPI_MULT) + global_off_y
                        img.paste(final_logo, (lx, ly), final_logo)
                except Exception as e:
                    logging.error(f"Error drawing logo: {e}")

            els = cfg.get("elements", {})
            
            if "metal" in els:
                els["metal"]["text"] = metal_type
                
            if "weight" in els:
                els["weight"]["text"] = f"Poids: {weight_val} g"
                
            if "purity" in els:
                p_text = f"Titre: {purity}"
                if els.get("extra", {}).get("show", False):
                    extra_txt = els["extra"].get("text", "").strip()
                    if extra_txt:
                        p_text += f" {extra_txt}"
                els["purity"]["text"] = p_text
                
            # 🟢 إجبار التاريخ والوقت ليكون اللحظة الحالية دائماً (تجاوز النص المحفوظ)
            if "date" in els:
                els["date"]["text"] = datetime.now().strftime("%d/%m/%Y %H:%M")

            elements_keys = ["store", "metal", "purity", "weight", "date"]
            for key in elements_keys:
                el = els.get(key, {})
                if el.get("show"):
                    font = get_font(el.get("font", "arial.ttf"), el.get("size", 12))
                    x = int(el.get("x", 0) * DPI_MULT) + global_off_x
                    y = int(el.get("y", 0) * DPI_MULT) + global_off_y
                    self._draw_rotated_text(img, el.get("text", ""), x, y, font, el.get("angle", 0))

            if cfg.get("orientation") == "Vertical":
                img = img.rotate(90, expand=True, fillcolor=(255, 255, 255, 255))

            final_img = img.convert("L").point(lambda x: 0 if x < 128 else 255, '1')

            w_mm_str = f"{w_mm:g}"
            h_mm_str = f"{h_mm:g}"
            gap_mm_str = f"{gap_mm:g}"
            w_bytes = (final_img.width + 7) // 8  
            
            cmds = [
                f"SIZE {w_mm_str} mm, {h_mm_str} mm",
                f"GAP {gap_mm_str} mm, 0 mm",
                "DIRECTION 1", "CLS",
                "SET PEEL OFF", "SET TEAR ON",
                f"BITMAP 0,0,{w_bytes},{final_img.height},0,"
            ]
            
            data = final_img.tobytes()
            tspl = "\r\n".join(cmds).encode("ascii") + data + b"\r\nPRINT 1\r\n"
            
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                win32print.StartDocPrinter(hprinter, 1, ("Label Print", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, tspl)
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
            
        except Exception as e:
            QMessageBox.critical(self, "خطأ طباعة", f"حدث خطأ أثناء الاتصال بالطابعة:\n{str(e)}")
            return

        self.gold_input.clear()
        self.silver_input.clear()
        self.weight_input.clear()
        self.gold_input.setFocus()

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.load_professional_style()