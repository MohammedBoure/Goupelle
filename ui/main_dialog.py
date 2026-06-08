import os
import io
import json
import logging
import re
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                               QLabel, QLineEdit, QPushButton, 
                               QGroupBox, QGridLayout, QMessageBox, QFrame)
from PySide6.QtGui import QDoubleValidator, QPixmap
from PySide6.QtCore import Qt, QFile, QTextStream
from .settings_dialog import SettingsDialog
from database import init_db, save_print_record
import sys

LIVE_EXTRA_CONVERSION_REFS = {
    "Or": (("750", 750.0),),
    "Argent": (("999.9", 999.9),),
}

LABEL_CONVERSION_ELEMENTS = {
    "conv_gold_730": {"metal": "Or", "ref": 730.0, "label": "730"},
    "conv_gold_750": {"metal": "Or", "ref": 750.0, "label": "750"},
    "conv_silver_925": {"metal": "Argent", "ref": 925.0, "label": "925"},
    "conv_silver_9999": {"metal": "Argent", "ref": 999.9, "label": "999.9"},
}

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
        self.setFixedSize(500, 660) 
        self.config_file = "label_config.json"
        
        init_db()
        self.init_ui()
        # self.load_professional_style()  <--- قم بتعطيل هذا السطر
        self.update_live_equiv()
        self.weight_input.setFocus()

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
        
        header_layout = QHBoxLayout()
        title_label = QLabel("Goupelle")
        title_label.setObjectName("header_title")
        
        self.btn_history = QPushButton("🗂️")
        self.btn_history.setObjectName("btn_history")
        self.btn_history.setFixedSize(40, 40)
        self.btn_history.setCursor(Qt.PointingHandCursor)
        self.btn_history.clicked.connect(self.open_history)
        
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_history)
        header_layout.addWidget(self.btn_settings)
        main_layout.addLayout(header_layout)
        
        group_box = QGroupBox()
        grid = QGridLayout(group_box)
        grid.setContentsMargins(20, 30, 20, 20) 
        grid.setVerticalSpacing(15) 
        grid.setHorizontalSpacing(15)
        
        validator = QDoubleValidator(0.00, 9999.99, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)

        # 1. الوزن
        grid.addWidget(QLabel("الوزن (غ):"), 0, 0)
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("0.00")
        self.weight_input.setValidator(validator)
        self.weight_input.setAlignment(Qt.AlignCenter)
        self.weight_input.textChanged.connect(self.update_live_equiv) # ربط التغيير بالحساب الحي
        grid.addWidget(self.weight_input, 0, 1)

        # 2. الذهب
        grid.addWidget(QLabel("عيار الذهب:"), 1, 0)
        self.gold_input = QLineEdit()
        self.gold_input.setPlaceholderText("مثال: 750")
        self.gold_input.setValidator(validator)
        self.gold_input.setAlignment(Qt.AlignCenter)
        self.gold_input.textChanged.connect(self.update_live_equiv) # ربط التغيير بالحساب الحي
        grid.addWidget(self.gold_input, 1, 1)

        # 3. الفضة
        grid.addWidget(QLabel("عيار الفضة:"), 2, 0)
        self.silver_input = QLineEdit()
        self.silver_input.setPlaceholderText("مثال: 925")
        self.silver_input.setValidator(validator)
        self.silver_input.setAlignment(Qt.AlignCenter)
        self.silver_input.textChanged.connect(self.update_live_equiv) # ربط التغيير بالحساب الحي
        grid.addWidget(self.silver_input, 2, 1)
        
        # خط فاصل
        hline = QFrame()
        hline.setFrameShape(QFrame.HLine)
        hline.setStyleSheet("color: #ecf0f1; margin-top: 5px; margin-bottom: 5px;")
        grid.addWidget(hline, 3, 0, 1, 2)

        # 4. العرض الحي للوزن المحول
        self.lbl_live_title = QLabel("الوزن المحول (Eq):")
        self.lbl_live_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        grid.addWidget(self.lbl_live_title, 4, 0)
        
        self.lbl_live_equiv = QLabel("0.00 g")
        self.lbl_live_equiv.setAlignment(Qt.AlignCenter)
        self.lbl_live_equiv.setStyleSheet("""
            background-color: #f0fdf4; 
            color: #166534; 
            min-height: 40px;
            font-size: 20px; 
            font-weight: 900; 
            border-radius: 12px; 
            border: 2px dashed #bbf7d0;
        """)
        grid.addWidget(self.lbl_live_equiv, 4, 1)

        self.extra_conversion_titles = {}
        self.extra_conversion_labels = {}
        all_extra_refs = []
        for refs in LIVE_EXTRA_CONVERSION_REFS.values():
            for ref_label, ref_value in refs:
                if ref_label not in self.extra_conversion_labels:
                    all_extra_refs.append((ref_label, ref_value))

        for row_offset, (ref_label, _) in enumerate(all_extra_refs, start=5):
            title = QLabel(f"{ref_label}:")
            title.setStyleSheet("font-weight: bold; color: #2c3e50;")
            grid.addWidget(title, row_offset, 0)

            value_label = QLabel("0.00 g")
            value_label.setAlignment(Qt.AlignCenter)
            value_label.setStyleSheet("""
                background-color: #fff7ed;
                color: #9a3412;
                min-height: 34px;
                font-size: 18px;
                font-weight: 800;
                border-radius: 10px;
                border: 2px dashed #fed7aa;
            """)
            grid.addWidget(value_label, row_offset, 1)
            self.extra_conversion_titles[ref_label] = title
            self.extra_conversion_labels[ref_label] = value_label

        main_layout.addWidget(group_box)
        
        self.btn_print = QPushButton("🖨️ طباعة ملصق (Enter)")
        self.btn_print.setObjectName("btn_print")
        self.btn_print.setCursor(Qt.PointingHandCursor)
        self.btn_print.clicked.connect(self.print_label)
        main_layout.addWidget(self.btn_print)

        footer_info = QLabel("النظام مهيأ للعمل مع الطابعات الحرارية TSPL")
        footer_info.setAlignment(Qt.AlignCenter)
        footer_info.setStyleSheet("color: #95a5a6; font-size: 11px;")
        main_layout.addWidget(footer_info)

    def update_live_equiv(self):
        """تحديث الوزن المحول مع عرض العيار المرجعي المستخدم في الحساب"""
        weight_val = self.weight_input.text().replace(',', '.')
        gold_val = self.gold_input.text().replace(',', '.')
        silver_val = self.silver_input.text().replace(',', '.')
        
        cfg = self.load_config()
        
        try:
            actual_weight = float(weight_val) if weight_val else 0.0
            # قراءة العيارات المرجعية من ملف الإعدادات المعرف من قبلك
            ref_gold = float(cfg.get("ref_gold", 730.0))
            ref_silver = float(cfg.get("ref_silver", 925.0))
            
            equiv_val = 0.0
            current_ref = 0.0
            actual_purity = 0.0
            
            if gold_val:
                metal_type = "Or"
                actual_purity = float(gold_val)
                if ref_gold > 0:
                    equiv_val = (actual_weight * actual_purity) / ref_gold
                    current_ref = ref_gold
            elif silver_val:
                metal_type = "Argent"
                actual_purity = float(silver_val)
                if ref_silver > 0:
                    equiv_val = (actual_weight * actual_purity) / ref_silver
                    current_ref = ref_silver
            else:
                metal_type = None
            
            # إذا كان هناك حساب، اعرض العيار المرجعي بجانب النتيجة
            if current_ref > 0:
                self.lbl_live_title.setText(f"{current_ref:g}:")
                self.lbl_live_equiv.setText(f"{equiv_val:.2f} g")
            else:
                self.lbl_live_title.setText("الوزن المحول (Eq):")
                self.lbl_live_equiv.setText("0.00 g")
            self.update_extra_conversions(actual_weight, actual_purity, metal_type)
                
        except ValueError:
            self.lbl_live_title.setText("الوزن المحول (Eq):")
            self.lbl_live_equiv.setText("0.00 g")
            self.update_extra_conversions(0.0, 0.0, None)

    def update_extra_conversions(self, actual_weight, actual_purity, metal_type):
        visible_refs = LIVE_EXTRA_CONVERSION_REFS.get(metal_type, ())
        visible_labels = {ref_label for ref_label, _ in visible_refs}
        for ref_label, title_label in self.extra_conversion_titles.items():
            is_visible = ref_label in visible_labels
            title_label.setVisible(is_visible)
            self.extra_conversion_labels[ref_label].setVisible(is_visible)

        for ref_label, ref_value in visible_refs:
            result = 0.0
            if actual_weight > 0 and actual_purity > 0 and ref_value > 0:
                result = (actual_weight * actual_purity) / ref_value
            self.extra_conversion_labels[ref_label].setText(f"{result:.2f} g")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focused = self.focusWidget()
            if focused == self.weight_input: self.gold_input.setFocus()
            elif focused == self.gold_input:
                if self.gold_input.text().strip():
                    self.silver_input.clear(); self.print_label()
                else: self.silver_input.setFocus()
            elif focused == self.silver_input:
                if self.silver_input.text().strip(): self.gold_input.clear()
                self.print_label()
        else: super().keyPressEvent(event)

    def load_config(self):
        default_config = {
            "printer_name": "", "label_width_mm": 40, "label_height_mm": 20, 
            "gap_mm": 2.0, "offset_x_mm": 0.0, "offset_y_mm": 0.0, "orientation": "Horizontal",
            "ref_gold": 730.0, "ref_silver": 925.0,  
            "logo": {"show": False, "path": "", "x": 0, "y": 0, "angle": 0},
            "elements": {
                "id": {"show": False, "text": "ID:", "x": 2, "y": 2, "size": 10, "font": "arial.ttf", "angle": 0},
                "store": {"show": True, "text": "مجوهرات الذهب", "x": 15, "y": 2, "size": 14, "font": "arial.ttf", "angle": 0},
                "metal": {"show": True, "text": "المعدن:", "x": 5, "y": 8, "size": 12, "font": "arial.ttf", "angle": 0},
                "purity": {"show": True, "text": "العيار:", "x": 20, "y": 8, "size": 12, "font": "arial.ttf", "angle": 0},
                "extra": {"show": True, "text": "mg/g"},
                "weight": {"show": True, "text": "الوزن:", "x": 5, "y": 14, "size": 12, "font": "arial.ttf", "angle": 0},
                "date": {"show": False, "text": "التاريخ:", "x": 5, "y": 18, "size": 10, "font": "arial.ttf", "angle": 0},
                "conv_gold_730": {"show": False, "text": "730:", "x": 20, "y": 14, "size": 12, "font": "arial.ttf", "angle": 0},
                "conv_gold_750": {"show": False, "text": "750:", "x": 20, "y": 17, "size": 12, "font": "arial.ttf", "angle": 0},
                "conv_silver_925": {"show": False, "text": "925:", "x": 20, "y": 14, "size": 12, "font": "arial.ttf", "angle": 0},
                "conv_silver_9999": {"show": False, "text": "999.9:", "x": 20, "y": 17, "size": 12, "font": "arial.ttf", "angle": 0},
            }
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k == "elements" and isinstance(v, dict):
                            for ek, ev in v.items():
                                if ek in default_config["elements"]: default_config["elements"][ek].update(ev)
                        elif k in ["logo"] and isinstance(v, dict): default_config[k].update(v)
                        else: default_config[k] = v
            except Exception as e: logging.error(f"Config error: {e}")
        return default_config

    def _draw_rotated_text(self, img, text, x, y, font, angle):
        if not text: return
        try:
            if re.search(r'[\u0600-\u06FF]', text):
                reshaped_text = arabic_reshaper.reshape(text); text = get_display(reshaped_text)
        except Exception: pass
        safe_width = int(font.size * len(text) * 1.5 + 50); safe_height = int(font.size * 3 + 50)
        txt_img = Image.new('RGBA', (safe_width, safe_height), (255, 255, 255, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((10, 10), text, font=font, fill=(0, 0, 0, 255))
        bbox = txt_img.getbbox()
        if not bbox: return
        txt_img = txt_img.crop(bbox)
        if angle != 0: txt_img = txt_img.rotate(angle, expand=True)
        img.paste(txt_img, (x, y), txt_img)

    def print_label(self):
        gold_val = self.gold_input.text().replace(',', '.')
        silver_val = self.silver_input.text().replace(',', '.')
        weight_val = self.weight_input.text().replace(',', '.')
        
        if not weight_val or float(weight_val or 0) <= 0: self.weight_input.setFocus(); return
        if not gold_val and not silver_val: self.gold_input.setFocus(); return

        metal_type = "Or" if gold_val else "Argent"
        purity = gold_val if gold_val else silver_val
        cfg = self.load_config()
        printer_name = cfg.get("printer_name", "")
        if not printer_name: QMessageBox.warning(self, "تنبيه", "يجب اختيار طابعة من الإعدادات أولاً."); self.open_settings(); return

        try:
            try:
                actual_weight = float(weight_val)
                actual_purity = float(purity)
                ref_gold = float(cfg.get("ref_gold", 730.0))
                ref_silver = float(cfg.get("ref_silver", 925.0))
                equiv_val = 0.0
                if gold_val and ref_gold > 0: equiv_val = (actual_weight * actual_purity) / ref_gold
                elif silver_val and ref_silver > 0: equiv_val = (actual_weight * actual_purity) / ref_silver
            except ValueError:
                actual_weight = 0.0; actual_purity = 0.0; equiv_val = 0.0

            # 1. حفظ البيانات في قاعدة البيانات والحصول على الـ ID الجديد
            new_record_id = save_print_record(
                metal_type=metal_type, purity=actual_purity, weight=actual_weight, 
                equiv_weight=equiv_val, printer_name=printer_name
            )
            if not new_record_id: new_record_id = "Error"

            # 2. إعدادات الرسم
            DPI_MULT = 8 
            w_mm = cfg.get("label_width_mm", 40); h_mm = cfg.get("label_height_mm", 20)
            gap_mm = cfg.get("gap_mm", 2.0)
            global_off_x = int(cfg.get("offset_x_mm", 0.0) * DPI_MULT); global_off_y = int(cfg.get("offset_y_mm", 0.0) * DPI_MULT)
            w_px = int(w_mm * DPI_MULT); h_px = int(h_mm * DPI_MULT)
            img = Image.new('RGBA', (w_px, h_px), (255, 255, 255, 255))

            def get_font(font_name, size):
                try: return ImageFont.truetype(font_name, size)
                except: return ImageFont.load_default()

            lg = cfg.get("logo", {})
            if lg.get("show") and os.path.exists(lg.get("path", "")):
                try:
                    logo = Image.open(lg["path"]).convert("RGBA")
                    scale = cfg.get("logo_settings", {}).get('scale', 100) / 100.0
                    new_w, new_h = int(logo.width * scale), int(logo.height * scale)
                    if new_w > 0 and new_h > 0:
                        logo = logo.resize((new_w, new_h))
                        thresh = cfg.get("logo_settings", {}).get('threshold', 128)
                        logo_l = logo.convert("L").point(lambda p: 0 if p < thresh else 255, '1')
                        final_logo = Image.new("RGBA", logo.size)
                        final_logo.paste((0,0,0,255), mask=ImageOps.invert(logo_l.convert("L")))
                        angle = lg.get("angle", 0)
                        if angle != 0: final_logo = final_logo.rotate(angle, expand=True)
                        lx = int(lg.get("x", 0) * DPI_MULT) + global_off_x
                        ly = int(lg.get("y", 0) * DPI_MULT) + global_off_y
                        img.paste(final_logo, (lx, ly), final_logo)
                except Exception as e: logging.error(f"Error drawing logo: {e}")

            els = cfg.get("elements", {})
            
            # دمج الـ ID مع البادئة الخاصة به
            if "id" in els:
                prefix = els["id"].get("text", "")
                els["id"]["text"] = f"{prefix} {new_record_id}".strip()

            if "metal" in els:
                prefix = els["metal"].get("text", "")
                els["metal"]["text"] = f"{prefix} {metal_type}".strip()
                
            if "weight" in els:
                prefix = els["weight"].get("text", "")
                els["weight"]["text"] = f"{prefix} {weight_val} g".strip()
                
            if "purity" in els:
                prefix = els["purity"].get("text", "")
                p_text = f"{prefix} {purity}".strip()
                if els.get("extra", {}).get("show", False):
                    extra_txt = els["extra"].get("text", "").strip()
                    if extra_txt: p_text += f" {extra_txt}"
                els["purity"]["text"] = p_text

            for key, conversion in LABEL_CONVERSION_ELEMENTS.items():
                el = els.get(key)
                if not el:
                    continue
                if conversion["metal"] != metal_type:
                    el["show"] = False
                    continue
                ref_value = conversion.get("ref")
                if ref_value is None:
                    ref_value = float(cfg.get(conversion["ref_key"], conversion["default_ref"]))
                converted_value = 0.0
                if ref_value > 0:
                    converted_value = (actual_weight * actual_purity) / ref_value
                prefix = el.get("text", conversion["label"] + ":")
                el["text"] = f"{prefix} {converted_value:.2f} g".strip()
                
            if "date" in els:
                prefix = els["date"].get("text", "")
                els["date"]["text"] = f"{prefix} {datetime.now().strftime('%d/%m/%Y %H:%M')}".strip()

            elements_keys = ["id", "store", "metal", "purity", "weight", "date", *LABEL_CONVERSION_ELEMENTS.keys()]
            for key in elements_keys:
                el = els.get(key, {})
                if el.get("show"): 
                    font = get_font(el.get("font", "arial.ttf"), el.get("size", 12))
                    x = int(el.get("x", 0) * DPI_MULT) + global_off_x
                    y = int(el.get("y", 0) * DPI_MULT) + global_off_y
                    self._draw_rotated_text(img, el.get("text", ""), x, y, font, el.get("angle", 0))

            if cfg.get("orientation") == "Vertical": img = img.rotate(90, expand=True, fillcolor=(255, 255, 255, 255))
            final_img = img.convert("L").point(lambda x: 0 if x < 128 else 255, '1')

            w_mm_str = f"{w_mm:g}"; h_mm_str = f"{h_mm:g}"; gap_mm_str = f"{gap_mm:g}"
            w_bytes = (final_img.width + 7) // 8  
            
            cmds = [
                f"SIZE {w_mm_str} mm, {h_mm_str} mm", f"GAP {gap_mm_str} mm, 0 mm",
                "DIRECTION 1", "CLS", "SET PEEL OFF", "SET TEAR ON", f"BITMAP 0,0,{w_bytes},{final_img.height},0,"
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
            QMessageBox.critical(self, "خطأ طباعة", f"حدث خطأ أثناء الاتصال بالطابعة أو قاعدة البيانات:\n{str(e)}")
            return

        self.gold_input.clear(); self.silver_input.clear(); self.weight_input.clear(); self.weight_input.setFocus()
        self.update_live_equiv() # تصفير العداد بعد الطباعة

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec(): 
            self.load_professional_style()
            self.update_live_equiv() # تحديث القيمة الحية إذا تغير العيار المرجعي

    def open_history(self):
        try:
            from .history_dialog import HistoryDialog
            dialog = HistoryDialog(self)
            dialog.exec()
        except ImportError: QMessageBox.information(self, "تنبيه", "ملف history_dialog.py غير موجود.")
