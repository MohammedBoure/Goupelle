# ui/settings_dialog.py
import os
import io
import json
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
    QComboBox, QPushButton, QLineEdit, QLabel, QCheckBox,
    QScrollArea, QSpinBox, QMessageBox, QSplitter, QWidget, QFileDialog, QSlider, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QFile, QTextStream, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtPrintSupport import QPrinterInfo

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

LABEL_CONVERSION_ELEMENTS = {
    "conv_gold_730": {"metal": "Or", "ref": 730.0, "label": "730"},
    "conv_gold_750": {"metal": "Or", "ref": 750.0, "label": "750"},
    "conv_silver_925": {"metal": "Argent", "ref": 925.0, "label": "925"},
    "conv_silver_9999": {"metal": "Argent", "ref": 999.9, "label": "999.9"},
}

class LogoSettingsDialog(QDialog):
    def __init__(self, image_path, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إعدادات الشعار المتقدمة")
        self.setMinimumSize(450, 550)
        self.original_image = QImage(image_path)
        self.settings = current_settings
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #ffffff; border: 2px dashed #bdc3c7; padding: 10px;")
        layout.addWidget(self.preview_label)

        layout.addWidget(QLabel("تغيير الحجم (Scale %) :"))
        self.sld_scale = QSlider(Qt.Horizontal)
        self.sld_scale.setRange(10, 300)
        self.sld_scale.setValue(self.settings.get('scale', 100))
        layout.addWidget(self.sld_scale)

        layout.addWidget(QLabel("عتبة الوضوح الأسود/الأبيض (Threshold) :"))
        self.sld_threshold = QSlider(Qt.Horizontal)
        self.sld_threshold.setRange(0, 255)
        self.sld_threshold.setValue(self.settings.get('threshold', 128))
        layout.addWidget(self.sld_threshold)

        self.sld_scale.valueChanged.connect(self.apply_filters)
        self.sld_threshold.valueChanged.connect(self.apply_filters)

        btns = QHBoxLayout()
        btn_ok = QPushButton("حفظ التعديلات")
        btn_ok.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)
        self.apply_filters()

    def apply_filters(self):
        scale = self.sld_scale.value() / 100.0
        new_w = int(self.original_image.width() * scale)
        if new_w <= 0: return
        img = self.original_image.scaledToWidth(new_w, Qt.SmoothTransformation)
        img = img.convertToFormat(QImage.Format_Grayscale8)
        thresh = self.sld_threshold.value()
        for y in range(img.height()):
            for x in range(img.width()):
                val = img.pixelColor(x, y).red()
                img.setPixelColor(x, y, QColor(0,0,0) if val <= thresh else QColor(255,255,255))
        self.preview_label.setPixmap(QPixmap.fromImage(img))

    def get_final_settings(self):
        return {'scale': self.sld_scale.value(), 'threshold': self.sld_threshold.value()}

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("الإعدادات الشاملة لقالب الملصق")
        self.setWindowState(Qt.WindowMaximized)
        self.setMinimumSize(1100, 750)
        self.config_file = "label_config.json"
        self.logo_settings = {'scale': 100, 'threshold': 128}
        self.zoom_factor = 2.0  
        self._preview_data = None 
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self.generate_preview)
        self.load_config()
        self.init_ui()
        self.trigger_preview()

    def load_config(self):
        self.config = {
            "printer_name": "", 
            "label_width_mm": 40, "label_height_mm": 20, 
            "gap_mm": 2.0, "offset_x_mm": 0.0, "offset_y_mm": 0.0,
            "orientation": "Horizontal",
            "ref_gold": 730.0,    
            "ref_silver": 925.0,  
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
                "conv_silver_9999": {"show": False, "text": "999.9:", "x": 20, "y": 17, "size": 12, "font": "arial.ttf", "angle": 0}
            }
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k == "elements" and isinstance(v, dict):
                            for ek, ev in v.items():
                                if ek in self.config["elements"]:
                                    self.config["elements"][ek].update(ev)
                        elif k in ["logo"] and isinstance(v, dict):
                            self.config[k].update(v)
                        else:
                            self.config[k] = v
                    self.logo_settings = self.config.get("logo_settings", self.logo_settings)
            except Exception as e:
                logging.error(f"Error loading config: {e}")

    def trigger_preview(self, *args): self.preview_timer.start()
    def zoom_in(self): self.zoom_factor += 0.5; self.generate_preview()
    def zoom_out(self): 
        if self.zoom_factor > 0.5: self.zoom_factor -= 0.5; self.generate_preview()
    def zoom_reset(self): self.zoom_factor = 2.0; self.generate_preview()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal) 
        main_layout.addWidget(self.splitter)

        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); form_layout = QVBoxLayout(content)

        grp_gen = QGroupBox("🖨️ 1. إعدادات الطباعة والورق")
        f_gen = QFormLayout(grp_gen)
        self.cmb_printer = QComboBox()
        self.cmb_printer.addItems([""] + [p.printerName() for p in QPrinterInfo.availablePrinters()])
        self.cmb_printer.setCurrentText(self.config["printer_name"])
        self.cmb_orient = QComboBox(); self.cmb_orient.addItems(["Horizontal", "Vertical"])
        self.cmb_orient.setCurrentText(self.config["orientation"]); self.cmb_orient.currentTextChanged.connect(self.trigger_preview)
        
        self.sp_w = QDoubleSpinBox(); self.sp_w.setRange(10, 200); self.sp_w.setValue(self.config["label_width_mm"])
        self.sp_h = QDoubleSpinBox(); self.sp_h.setRange(10, 200); self.sp_h.setValue(self.config["label_height_mm"])
        self.sp_w.valueChanged.connect(self.trigger_preview); self.sp_h.valueChanged.connect(self.trigger_preview)

        self.sp_gap = QDoubleSpinBox(); self.sp_gap.setRange(0, 50); self.sp_gap.setValue(self.config.get("gap_mm", 2.0))
        self.sp_offset_x = QDoubleSpinBox(); self.sp_offset_x.setRange(-50, 50); self.sp_offset_x.setValue(self.config.get("offset_x_mm", 0.0))
        self.sp_offset_y = QDoubleSpinBox(); self.sp_offset_y.setRange(-50, 50); self.sp_offset_y.setValue(self.config.get("offset_y_mm", 0.0))
        self.sp_offset_x.valueChanged.connect(self.trigger_preview); self.sp_offset_y.valueChanged.connect(self.trigger_preview)

        f_gen.addRow("الطابعة:", self.cmb_printer); f_gen.addRow("الاتجاه العام:", self.cmb_orient)
        f_gen.addRow("العرض (mm):", self.sp_w); f_gen.addRow("الارتفاع (mm):", self.sp_h)
        f_gen.addRow("الفاصل (Gap):", self.sp_gap); f_gen.addRow("إزاحة X:", self.sp_offset_x); f_gen.addRow("إزاحة Y:", self.sp_offset_y)
        form_layout.addWidget(grp_gen)

        grp_logo = QGroupBox("🖼️ 2. الشعار التجاري (Logo)")
        l_logo = QVBoxLayout(grp_logo)
        lg = self.config["logo"]
        self.chk_logo = QCheckBox("تفعيل الشعار"); self.chk_logo.setChecked(lg.get("show", False)); self.chk_logo.stateChanged.connect(self.trigger_preview)
        self.lbl_logo_path = QLabel(lg.get("path", "لا يوجد شعار")); self.lbl_logo_path.setStyleSheet("color: gray; font-size: 11px;")
        
        btn_h = QHBoxLayout()
        btn_br = QPushButton("📁 استعراض"); btn_br.clicked.connect(self.browse_logo)
        btn_set = QPushButton("⚙️ الألوان والحجم"); btn_set.clicked.connect(self.open_logo_dialog)
        btn_clr = QPushButton("🗑️ حذف"); btn_clr.clicked.connect(self.clear_logo)
        btn_h.addWidget(btn_br); btn_h.addWidget(btn_set); btn_h.addWidget(btn_clr)
        
        h_logo_pos = QHBoxLayout()
        self.sp_logo_x = QDoubleSpinBox(); self.sp_logo_x.setRange(-50, 300); self.sp_logo_x.setValue(lg.get("x", 0)); self.sp_logo_x.valueChanged.connect(self.trigger_preview)
        self.sp_logo_y = QDoubleSpinBox(); self.sp_logo_y.setRange(-50, 300); self.sp_logo_y.setValue(lg.get("y", 0)); self.sp_logo_y.valueChanged.connect(self.trigger_preview)
        self.cmb_logo_angle = QComboBox(); self.cmb_logo_angle.addItems(["0°", "90°", "180°", "270°"]); self.cmb_logo_angle.setCurrentText(f"{lg.get('angle', 0)}°")
        self.cmb_logo_angle.currentTextChanged.connect(self.trigger_preview)
        
        h_logo_pos.addWidget(QLabel("X:")); h_logo_pos.addWidget(self.sp_logo_x); h_logo_pos.addWidget(QLabel("Y:")); h_logo_pos.addWidget(self.sp_logo_y)
        h_logo_pos.addWidget(QLabel("زاوية:")); h_logo_pos.addWidget(self.cmb_logo_angle)
        
        l_logo.addWidget(self.chk_logo); l_logo.addWidget(self.lbl_logo_path); l_logo.addLayout(btn_h); l_logo.addLayout(h_logo_pos)
        form_layout.addWidget(grp_logo)

        grp_el = QGroupBox("📝 3. تخصيص النصوص والبوادئ")
        v_el = QVBoxLayout(grp_el)

        def create_element_row(key, label):
            el = self.config["elements"][key]
            row_main = QVBoxLayout()
            h_top = QHBoxLayout()
            chk = QCheckBox(label); chk.setChecked(el["show"]); chk.stateChanged.connect(self.trigger_preview)
            inp = QLineEdit(el.get("text", "")); inp.setPlaceholderText("البادئة هنا")
            inp.textChanged.connect(self.trigger_preview)
            h_top.addWidget(chk); h_top.addWidget(inp)
            
            h_bot = QHBoxLayout()
            sx = QDoubleSpinBox(); sx.setRange(-50, 300); sx.setValue(el["x"]); sx.valueChanged.connect(self.trigger_preview)
            sy = QDoubleSpinBox(); sy.setRange(-50, 300); sy.setValue(el["y"]); sy.valueChanged.connect(self.trigger_preview)
            sz = QSpinBox(); sz.setRange(6, 72); sz.setValue(el["size"]); sz.valueChanged.connect(self.trigger_preview)
            cmb_f = QComboBox(); cmb_f.addItems(["arial.ttf", "tahoma.ttf", "times.ttf", "cour.ttf", "calibri.ttf"]); cmb_f.setCurrentText(el.get("font", "arial.ttf")); cmb_f.currentTextChanged.connect(self.trigger_preview)
            cmb_a = QComboBox(); cmb_a.addItems(["0°", "90°", "180°", "270°"]); cmb_a.setCurrentText(f"{el.get('angle', 0)}°"); cmb_a.currentTextChanged.connect(self.trigger_preview)
            
            h_bot.addWidget(QLabel("X:")); h_bot.addWidget(sx); h_bot.addWidget(QLabel("Y:")); h_bot.addWidget(sy); h_bot.addWidget(QLabel("حجم:")); h_bot.addWidget(sz)
            h_bot.addWidget(cmb_f); h_bot.addWidget(cmb_a)
            
            row_main.addLayout(h_top); row_main.addLayout(h_bot)
            v_el.addLayout(row_main)
            
            setattr(self, f"chk_{key}", chk); setattr(self, f"inp_{key}", inp); setattr(self, f"sp_{key}_x", sx); setattr(self, f"sp_{key}_y", sy)
            setattr(self, f"sp_{key}_sz", sz); setattr(self, f"cmb_{key}_f", cmb_f); setattr(self, f"cmb_{key}_a", cmb_a)

        create_element_row("id", "رقم الطلب (ID):")
        create_element_row("store", "الترويسة:")
        create_element_row("metal", "المعدن:")
        create_element_row("purity", "العيار:")

        el_extra = self.config["elements"].get("extra", {"show": True, "text": "mg/g"})
        row_extra = QHBoxLayout()
        self.chk_extra = QCheckBox("➕ لاحقة العيار:"); self.chk_extra.setChecked(el_extra.get("show", True)); self.chk_extra.stateChanged.connect(self.trigger_preview)
        self.inp_extra = QLineEdit(el_extra.get("text", "mg/g")); self.inp_extra.textChanged.connect(self.trigger_preview)
        row_extra.addWidget(self.chk_extra); row_extra.addWidget(self.inp_extra)
        v_el.addLayout(row_extra)

        create_element_row("weight", "الوزن:")

        create_element_row("date", "التاريخ:")
        create_element_row("conv_gold_730", "Or 730:")
        create_element_row("conv_gold_750", "Or 750:")
        create_element_row("conv_silver_925", "Argent 925:")
        create_element_row("conv_silver_9999", "Argent 999.9:")

        form_layout.addWidget(grp_el)
        scroll.setWidget(content)
        left_layout.addWidget(scroll)

        h_btns = QHBoxLayout()
        btn_save = QPushButton("💾 حفظ الإعدادات"); btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 12px; font-weight: bold;"); btn_save.clicked.connect(self.save_config)
        btn_test = QPushButton("🖨️ طباعة اختبار"); btn_test.setStyleSheet("background-color: #e67e22; color: white; padding: 12px; font-weight: bold;"); btn_test.clicked.connect(self.print_test)
        h_btns.addWidget(btn_save); h_btns.addWidget(btn_test)
        left_layout.addLayout(h_btns)
        
        self.splitter.addWidget(left_panel)

        preview_panel = QWidget(); preview_layout = QVBoxLayout(preview_panel)
        h_header = QHBoxLayout()
        h_header.addWidget(QLabel("<b>👁️ المعاينة المباشرة </b>")); h_header.addStretch()
        btn_z_out = QPushButton("🔍 -"); btn_z_out.setFixedSize(40, 30); btn_z_out.clicked.connect(self.zoom_out)
        btn_z_res = QPushButton("1:1"); btn_z_res.setFixedSize(40, 30); btn_z_res.clicked.connect(self.zoom_reset)
        btn_z_in = QPushButton("🔍 +"); btn_z_in.setFixedSize(40, 30); btn_z_in.clicked.connect(self.zoom_in)
        h_header.addWidget(btn_z_out); h_header.addWidget(btn_z_res); h_header.addWidget(btn_z_in)
        preview_layout.addLayout(h_header)
        
        self.lbl_preview = QLabel(); self.lbl_preview.setAlignment(Qt.AlignCenter); self.lbl_preview.setStyleSheet("background: white; border: 2px solid #34495e; border-radius: 4px;")
        p_scroll = QScrollArea(); p_scroll.setAlignment(Qt.AlignCenter); p_scroll.setWidget(self.lbl_preview)
        preview_layout.addWidget(p_scroll)
        
        self.splitter.addWidget(preview_panel)
        self.splitter.setSizes([550, 550])

    def browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "اختر الشعار", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path: self.lbl_logo_path.setText(path); self.chk_logo.setChecked(True); self.trigger_preview()

    def clear_logo(self):
        self.lbl_logo_path.setText("لا يوجد شعار"); self.chk_logo.setChecked(False); self.trigger_preview()

    def open_logo_dialog(self):
        path = self.lbl_logo_path.text()
        if not os.path.exists(path): QMessageBox.warning(self, "تنبيه", "اختر صورة شعار صالحة أولاً."); return
        dlg = LogoSettingsDialog(path, self.logo_settings, self)
        if dlg.exec(): self.logo_settings = dlg.get_final_settings(); self.trigger_preview()

    def _draw_rotated_text(self, img, text, x, y, font, angle):
        if not text: return
        try: reshaped_text = arabic_reshaper.reshape(text); text = get_display(reshaped_text)
        except: pass
        safe_width = int(font.size * len(text) * 1.5 + 50); safe_height = int(font.size * 3 + 50)
        txt_img = Image.new('RGBA', (safe_width, safe_height), (255, 255, 255, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((10, 10), text, font=font, fill=(0, 0, 0, 255))
        bbox = txt_img.getbbox()
        if not bbox: return
        txt_img = txt_img.crop(bbox)
        if angle != 0: txt_img = txt_img.rotate(angle, expand=True)
        img.paste(txt_img, (x, y), txt_img)

    def get_pil_image(self):
        DPI_MULT = 8 
        w_px = int(self.sp_w.value() * DPI_MULT); h_px = int(self.sp_h.value() * DPI_MULT)
        if w_px <= 0 or h_px <= 0: return None
        global_off_x = int(self.sp_offset_x.value() * DPI_MULT); global_off_y = int(self.sp_offset_y.value() * DPI_MULT)
        img = Image.new('RGBA', (w_px, h_px), (255, 255, 255, 255))
        def get_font(font_name, size):
            try: return ImageFont.truetype(font_name, size)
            except: return ImageFont.load_default()

        if self.chk_logo.isChecked() and os.path.exists(self.lbl_logo_path.text()):
            try:
                logo = Image.open(self.lbl_logo_path.text()).convert("RGBA")
                scale = self.logo_settings.get('scale', 100) / 100.0
                new_w, new_h = int(logo.width * scale), int(logo.height * scale)
                if new_w > 0 and new_h > 0:
                    logo = logo.resize((new_w, new_h))
                    thresh = self.logo_settings.get('threshold', 128)
                    logo_l = logo.convert("L").point(lambda p: 0 if p < thresh else 255, '1')
                    final_logo = Image.new("RGBA", logo.size)
                    final_logo.paste((0,0,0,255), mask=ImageOps.invert(logo_l.convert("L")))
                    angle = int(self.cmb_logo_angle.currentText().replace("°", ""))
                    if angle != 0: final_logo = final_logo.rotate(angle, expand=True)
                    lx = int(self.sp_logo_x.value() * DPI_MULT) + global_off_x
                    ly = int(self.sp_logo_y.value() * DPI_MULT) + global_off_y
                    img.paste(final_logo, (lx, ly), final_logo)
            except Exception as e: logging.error(f"Logo err: {e}")

        elements_keys = ["id", "store", "metal", "purity", "weight", *LABEL_CONVERSION_ELEMENTS.keys(), "date"]
        test_values = {
            "id": "1005",
            "store": "",
            "metal": "Or",
            "purity": "750",
            "weight": "4.25 g",
            "conv_gold_730": "4.37 g",
            "conv_gold_750": "4.25 g",
            "conv_silver_925": "3.45 g",
            "conv_silver_9999": "3.19 g",
            "date": datetime.now().strftime("%d/%m/%Y")
        }

        for key in elements_keys:
            if getattr(self, f"chk_{key}").isChecked():
                prefix = getattr(self, f"inp_{key}").text()
                display_text = f"{prefix} {test_values[key]}" if key != "store" else prefix
                if key == "purity" and self.chk_extra.isChecked():
                    display_text += f" {self.inp_extra.text()}"
                
                font = get_font(getattr(self, f"cmb_{key}_f").currentText(), getattr(self, f"sp_{key}_sz").value())
                x = int(getattr(self, f"sp_{key}_x").value() * DPI_MULT) + global_off_x
                y = int(getattr(self, f"sp_{key}_y").value() * DPI_MULT) + global_off_y
                angle = int(getattr(self, f"cmb_{key}_a").currentText().replace("°", ""))
                self._draw_rotated_text(img, display_text, x, y, font, angle)

        if self.cmb_orient.currentText() == "Vertical": img = img.rotate(90, expand=True, fillcolor=(255, 255, 255, 255))
        return img.convert("L").point(lambda x: 0 if x < 128 else 255, '1')

    def generate_preview(self):
        img = self.get_pil_image()
        if not img: return
        img_rgba = img.convert("RGBA"); self._preview_data = img_rgba.tobytes("raw", "RGBA") 
        qim = QImage(self._preview_data, img.width, img.height, QImage.Format_RGBA8888)
        pix = QPixmap.fromImage(qim)
        p = QPainter(pix); p.setPen(QPen(Qt.red, 1, Qt.DashLine)); p.drawRect(0, 0, img.width - 1, img.height - 1); p.end()
        scaled_pix = pix.scaled(int(img.width * self.zoom_factor), int(img.height * self.zoom_factor), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_preview.setPixmap(scaled_pix); self.lbl_preview.setFixedSize(scaled_pix.size())

    def save_config(self):
        self.config.update({
            "printer_name": self.cmb_printer.currentText(),
            "label_width_mm": self.sp_w.value(), "label_height_mm": self.sp_h.value(),
            "gap_mm": self.sp_gap.value(), "offset_x_mm": self.sp_offset_x.value(),
            "offset_y_mm": self.sp_offset_y.value(), "orientation": self.cmb_orient.currentText(),
            "ref_gold": self.config.get("ref_gold", 730.0), "ref_silver": self.config.get("ref_silver", 925.0),
            "logo": {
                "show": self.chk_logo.isChecked(), "path": self.lbl_logo_path.text() if self.lbl_logo_path.text() != "لا يوجد شعار" else "",
                "x": self.sp_logo_x.value(), "y": self.sp_logo_y.value(), "angle": int(self.cmb_logo_angle.currentText().replace("°", ""))
            },
            "logo_settings": self.logo_settings
        })
        elements_keys = ["id", "store", "metal", "purity", "weight", *LABEL_CONVERSION_ELEMENTS.keys(), "date"]
        for key in elements_keys:
            self.config["elements"][key] = {
                "show": getattr(self, f"chk_{key}").isChecked(), "text": getattr(self, f"inp_{key}").text(),
                "x": getattr(self, f"sp_{key}_x").value(), "y": getattr(self, f"sp_{key}_y").value(),
                "size": getattr(self, f"sp_{key}_sz").value(), "font": getattr(self, f"cmb_{key}_f").currentText(),
                "angle": int(getattr(self, f"cmb_{key}_a").currentText().replace("°", ""))
            }
        self.config["elements"]["extra"] = {"show": self.chk_extra.isChecked(), "text": self.inp_extra.text()}

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f: json.dump(self.config, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "نجاح", "تم حفظ الإعدادات بنجاح!")
        except Exception as e: QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")

    def print_test(self):
        printer_name = self.cmb_printer.currentText()
        if not printer_name: QMessageBox.warning(self, "تنبيه", "اختر طابعة أولاً."); return
        img = self.get_pil_image()
        if not img: return
        w_bytes = (img.width + 7) // 8  
        tspl = f"SIZE {self.sp_w.value():g} mm, {self.sp_h.value():g} mm\r\nGAP {self.sp_gap.value():g} mm, 0 mm\r\nDIRECTION 1\r\nCLS\r\nBITMAP 0,0,{w_bytes},{img.height},0,".encode("ascii") + img.tobytes() + b"\r\nPRINT 1\r\n"
        try:
            hprinter = win32print.OpenPrinter(printer_name)
            win32print.StartDocPrinter(hprinter, 1, ("Test", None, "RAW")); win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, tspl); win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter); win32print.ClosePrinter(hprinter)
            QMessageBox.information(self, "نجاح", "تم إرسال الطباعة.")
        except Exception as e: QMessageBox.critical(self, "خطأ", str(e))
