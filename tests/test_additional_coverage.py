import json
import runpy
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QEvent
from PySide6.QtGui import QImage, QKeyEvent, QPalette
from PySide6.QtWidgets import QFileDialog

import database
import main as app_main
import ui.main_dialog as main_dialog_module
import ui.settings_dialog as settings_dialog_module
from ui.main_dialog import MainPrintDialog
from ui.settings_dialog import LogoSettingsDialog, SettingsDialog


class ExitCalled(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class FakeApplication:
    instances = []

    def __init__(self, argv):
        self.argv = argv
        self.style = None
        self.palette = None
        self.stylesheet = ""
        self.window_icon = None
        FakeApplication.instances.append(self)

    def setStyle(self, style):
        self.style = style

    def setPalette(self, palette):
        self.palette = palette

    def setStyleSheet(self, stylesheet):
        self.stylesheet = stylesheet

    def setWindowIcon(self, icon):
        self.window_icon = icon

    def exec(self):
        return 7


class FakeDialog:
    shown = False

    def __init__(self):
        FakeDialog.shown = False

    def show(self):
        FakeDialog.shown = True


def create_png(path, color=(255, 255, 255, 255)):
    Image.new("RGBA", (4, 4), color).save(path)
    return path


@pytest.fixture
def settings_dialog(qapp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    dialog = SettingsDialog()
    dialog.preview_timer.stop()
    yield dialog, tmp_path
    dialog.close()


@pytest.fixture
def main_dialog(qapp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_dialog_module, "init_db", lambda: None)
    dialog = MainPrintDialog()
    yield dialog, tmp_path
    dialog.close()


def write_main_config(path, **overrides):
    config = {
        "printer_name": "Fake Printer",
        "label_width_mm": 40,
        "label_height_mm": 20,
        "gap_mm": 2,
        "offset_x_mm": 0,
        "offset_y_mm": 0,
        "orientation": "Horizontal",
        "elements": {},
    }
    config.update(overrides)
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")


def fake_win32print(writes=None, open_error=None):
    if writes is None:
        writes = []

    def open_printer(printer_name):
        if open_error:
            raise open_error
        return object()

    return SimpleNamespace(
        OpenPrinter=open_printer,
        StartDocPrinter=lambda *args, **kwargs: None,
        StartPagePrinter=lambda *args, **kwargs: None,
        WritePrinter=lambda printer, data: writes.append(data),
        EndPagePrinter=lambda *args, **kwargs: None,
        EndDocPrinter=lambda *args, **kwargs: None,
        ClosePrinter=lambda *args, **kwargs: None,
    )


def exec_module_with_blocked_imports(monkeypatch, module_name, path, blocked_names):
    import builtins
    import importlib.util

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if any(name == blocked or name.startswith(f"{blocked}.") for blocked in blocked_names):
            raise ImportError(f"blocked {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_resource_path_uses_source_directory(monkeypatch):
    monkeypatch.setattr(app_main.sys, "frozen", False, raising=False)

    path = app_main.get_resource_path("ui/logo.png")

    assert path.endswith("ui/logo.png")


def test_get_resource_path_uses_frozen_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(app_main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_main.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert app_main.os.path.normpath(app_main.get_resource_path("ui/logo.png")) == str(tmp_path / "ui/logo.png")


def test_main_initializes_white_theme_and_shows_dialog(monkeypatch):
    FakeApplication.instances.clear()
    monkeypatch.setattr(app_main, "QApplication", FakeApplication)
    monkeypatch.setattr(app_main, "MainPrintDialog", FakeDialog)
    monkeypatch.setattr(app_main.os.path, "exists", lambda path: False)
    monkeypatch.setattr(app_main.sys, "exit", lambda code: (_ for _ in ()).throw(ExitCalled(code)))

    with pytest.raises(ExitCalled) as exc:
        app_main.main()

    fake_app = FakeApplication.instances[0]
    assert exc.value.code == 7
    assert fake_app.style == "Fusion"
    assert fake_app.palette.color(QPalette.Window).name() == "#ffffff"
    assert "QDialog, QWidget" in fake_app.stylesheet
    assert "background-color: #ffffff" in fake_app.stylesheet
    assert FakeDialog.shown is True


def test_main_sets_window_icon_when_logo_exists(monkeypatch):
    FakeApplication.instances.clear()
    monkeypatch.setattr(app_main, "QApplication", FakeApplication)
    monkeypatch.setattr(app_main, "QIcon", lambda path: ("icon", path))
    monkeypatch.setattr(app_main, "MainPrintDialog", FakeDialog)
    monkeypatch.setattr(app_main.os.path, "exists", lambda path: True)
    monkeypatch.setattr(app_main.sys, "exit", lambda code: (_ for _ in ()).throw(ExitCalled(code)))

    with pytest.raises(ExitCalled):
        app_main.main()

    assert FakeApplication.instances[0].window_icon is not None


def test_main_script_entrypoint_calls_main(monkeypatch):
    FakeApplication.instances.clear()
    monkeypatch.setattr("PySide6.QtWidgets.QApplication", FakeApplication)
    monkeypatch.setattr("PySide6.QtGui.QIcon", lambda path: ("icon", path))
    monkeypatch.setitem(app_main.sys.modules, "ui.main_dialog", SimpleNamespace(MainPrintDialog=FakeDialog))
    monkeypatch.setattr(app_main.os.path, "exists", lambda path: False)
    monkeypatch.setattr(app_main.sys, "exit", lambda code: (_ for _ in ()).throw(ExitCalled(code)))

    with pytest.raises(ExitCalled) as exc:
        runpy.run_path(app_main.__file__, run_name="__main__")

    assert exc.value.code == 7
    assert FakeDialog.shown is True


def test_ui_modules_log_missing_optional_printing_imports(monkeypatch, caplog):
    exec_module_with_blocked_imports(
        monkeypatch,
        "ui.main_dialog_missing_print_libs",
        main_dialog_module.__file__,
        {"PIL"},
    )
    exec_module_with_blocked_imports(
        monkeypatch,
        "ui.settings_dialog_missing_print_libs",
        settings_dialog_module.__file__,
        {"PIL"},
    )

    assert "Missing printing libraries" in caplog.text


def test_ui_modules_log_missing_arabic_imports(monkeypatch, caplog):
    exec_module_with_blocked_imports(
        monkeypatch,
        "ui.main_dialog_missing_arabic_libs",
        main_dialog_module.__file__,
        {"arabic_reshaper"},
    )
    exec_module_with_blocked_imports(
        monkeypatch,
        "ui.settings_dialog_missing_arabic_libs",
        settings_dialog_module.__file__,
        {"arabic_reshaper"},
    )

    assert "Arabic reshaping libraries missing" in caplog.text


def test_database_functions_return_safe_values_on_connection_errors(monkeypatch):
    def raise_sqlite_error(*args, **kwargs):
        raise sqlite_error

    sqlite_error = RuntimeError("sqlite unavailable")
    monkeypatch.setattr(database.sqlite3, "connect", raise_sqlite_error)

    database.init_db()
    assert database.save_print_record("Or", 750, 4.25, 4.37, "Printer") is None
    assert database.get_records_by_date_range("2026-01-01", "2026-12-31") == []
    assert database.get_record_by_id(1) is None


def test_logo_settings_dialog_filters_image_and_returns_settings(qapp, tmp_path):
    logo_path = create_png(tmp_path / "logo.png", (0, 0, 0, 255))
    dialog = LogoSettingsDialog(str(logo_path), {"scale": 50, "threshold": 100})

    try:
        assert dialog.preview_label.pixmap() is not None
        dialog.sld_scale.setValue(75)
        dialog.sld_threshold.setValue(200)

        assert dialog.get_final_settings() == {"scale": 75, "threshold": 200}
    finally:
        dialog.close()


def test_settings_load_config_merges_saved_nested_values(qapp, monkeypatch, tmp_path):
    config_path = tmp_path / "label_config.json"
    config_path.write_text(
        json.dumps(
            {
                "printer_name": "Saved Printer",
                "logo": {"show": True, "path": "saved-logo.png", "x": 3},
                "logo_settings": {"scale": 33, "threshold": 222},
                "elements": {
                    "store": {"text": "Saved Store", "show": False},
                    "conv_gold_730": {"show": True, "text": "730 saved:"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    dialog = SettingsDialog()
    dialog.preview_timer.stop()

    try:
        assert dialog.config["printer_name"] == "Saved Printer"
        assert dialog.config["logo"]["show"] is True
        assert dialog.config["logo"]["path"] == "saved-logo.png"
        assert dialog.config["logo"]["x"] == 3
        assert dialog.logo_settings == {"scale": 33, "threshold": 222}
        assert dialog.config["elements"]["store"]["text"] == "Saved Store"
        assert dialog.config["elements"]["store"]["show"] is False
        assert dialog.config["elements"]["conv_gold_730"]["show"] is True
    finally:
        dialog.close()


def test_settings_load_config_handles_invalid_json(qapp, monkeypatch, tmp_path):
    (tmp_path / "label_config.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    dialog = SettingsDialog()
    dialog.preview_timer.stop()

    try:
        assert dialog.config["label_width_mm"] == 40
        assert dialog.config["elements"]["weight"]["show"] is True
    finally:
        dialog.close()


def test_settings_logo_actions_and_logo_dialog(settings_dialog, monkeypatch):
    dialog, tmp_path = settings_dialog
    logo_path = create_png(tmp_path / "logo.png")

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(logo_path), ""))
    dialog.browse_logo()
    assert dialog.lbl_logo_path.text() == str(logo_path)
    assert dialog.chk_logo.isChecked()

    class AcceptedLogoDialog:
        def __init__(self, path, settings, parent=None):
            self.path = path
            self.settings = settings

        def exec(self):
            return True

        def get_final_settings(self):
            return {"scale": 44, "threshold": 155}

    monkeypatch.setattr(settings_dialog_module, "LogoSettingsDialog", AcceptedLogoDialog)
    dialog.open_logo_dialog()
    assert dialog.logo_settings == {"scale": 44, "threshold": 155}

    dialog.clear_logo()
    assert not dialog.chk_logo.isChecked()


def test_settings_open_logo_dialog_warns_for_missing_logo(settings_dialog):
    dialog, _ = settings_dialog
    dialog.lbl_logo_path.setText("missing-logo.png")

    dialog.open_logo_dialog()

    assert dialog.logo_settings == {"scale": 100, "threshold": 128}


def test_settings_zoom_and_generate_preview(settings_dialog):
    dialog, _ = settings_dialog

    dialog.generate_preview()
    assert dialog.lbl_preview.pixmap() is not None

    original_zoom = dialog.zoom_factor
    dialog.zoom_in()
    assert dialog.zoom_factor == original_zoom + 0.5

    dialog.zoom_out()
    assert dialog.zoom_factor == original_zoom

    dialog.zoom_reset()
    assert dialog.zoom_factor == 2.0


def test_settings_get_pil_image_draws_logo_and_vertical_orientation(settings_dialog, tmp_path):
    dialog, _ = settings_dialog
    logo_path = create_png(tmp_path / "logo.png", (0, 0, 0, 255))
    dialog.chk_logo.setChecked(True)
    dialog.lbl_logo_path.setText(str(logo_path))
    dialog.logo_settings = {"scale": 100, "threshold": 128}
    dialog.cmb_logo_angle.setCurrentIndex(1)
    dialog.cmb_orient.setCurrentText("Vertical")

    image = dialog.get_pil_image()

    assert image is not None
    assert image.size == (160, 320)


def test_settings_draw_rotated_text_handles_empty_and_reshaper_errors(settings_dialog, monkeypatch):
    dialog, _ = settings_dialog
    image = settings_dialog_module.Image.new("RGBA", (120, 60), (255, 255, 255, 255))
    font = settings_dialog_module.ImageFont.load_default()

    dialog._draw_rotated_text(image, "", 0, 0, font, 0)
    monkeypatch.setattr(
        settings_dialog_module.arabic_reshaper,
        "reshape",
        lambda text: (_ for _ in ()).throw(RuntimeError("reshape failed")),
    )
    dialog._draw_rotated_text(image, "text", 5, 5, font, 0)

    assert image.getbbox() is not None


def test_settings_get_pil_image_handles_zero_size(settings_dialog):
    dialog, _ = settings_dialog
    dialog.sp_w.value = lambda: 0

    assert dialog.get_pil_image() is None


def test_settings_get_pil_image_handles_logo_errors_and_preview_filters(settings_dialog, monkeypatch, tmp_path):
    dialog, _ = settings_dialog
    logo_path = create_png(tmp_path / "broken-logo.png", (0, 0, 0, 255))
    drawn_texts = []

    dialog.chk_logo.setChecked(True)
    dialog.lbl_logo_path.setText(str(logo_path))
    dialog.chk_equiv_weight.setChecked(True)
    dialog.chk_equiv_gold.setChecked(False)
    dialog.chk_conv_silver_925.setChecked(True)
    monkeypatch.setattr(settings_dialog_module.Image, "open", lambda path: (_ for _ in ()).throw(RuntimeError("logo failed")))
    monkeypatch.setattr(
        dialog,
        "_draw_rotated_text",
        lambda img, text, *args: drawn_texts.append(text),
    )

    image = dialog.get_pil_image()

    assert image is not None
    assert not any("4.37 g" in text for text in drawn_texts)
    assert not any("3.45 g" in text for text in drawn_texts)


def test_settings_get_pil_image_uses_default_font_when_font_file_missing(settings_dialog, monkeypatch):
    dialog, _ = settings_dialog
    dialog.chk_store.setChecked(True)
    dialog.cmb_store_f.addItem("definitely-missing-font.ttf")
    dialog.cmb_store_f.setCurrentText("definitely-missing-font.ttf")

    assert dialog.get_pil_image() is not None


def test_settings_save_config_reports_write_errors(settings_dialog, monkeypatch, tmp_path):
    dialog, _ = settings_dialog
    errors = []
    dialog.config_file = str(tmp_path)
    monkeypatch.setattr(settings_dialog_module.QMessageBox, "critical", lambda *args: errors.append(args))

    dialog.save_config()

    assert errors


def test_settings_print_test_warns_without_printer(settings_dialog):
    dialog, _ = settings_dialog

    dialog.print_test()

    assert dialog.cmb_printer.currentText() == ""


def test_settings_print_test_sends_tspl_to_fake_printer(settings_dialog, monkeypatch):
    dialog, _ = settings_dialog
    writes = []
    dialog.cmb_printer.addItem("Fake Printer")
    dialog.cmb_printer.setCurrentText("Fake Printer")

    fake_win32print = SimpleNamespace(
        OpenPrinter=lambda printer_name: object(),
        StartDocPrinter=lambda *args, **kwargs: None,
        StartPagePrinter=lambda *args, **kwargs: None,
        WritePrinter=lambda printer, data: writes.append(data),
        EndPagePrinter=lambda *args, **kwargs: None,
        EndDocPrinter=lambda *args, **kwargs: None,
        ClosePrinter=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(settings_dialog_module, "win32print", fake_win32print, raising=False)

    dialog.print_test()

    assert writes
    assert writes[0].startswith(b"SIZE")
    assert writes[0].endswith(b"\r\nPRINT 1\r\n")


def test_settings_print_test_handles_printer_error(settings_dialog, monkeypatch):
    dialog, _ = settings_dialog
    dialog.cmb_printer.addItem("Fake Printer")
    dialog.cmb_printer.setCurrentText("Fake Printer")
    monkeypatch.setattr(
        settings_dialog_module,
        "win32print",
        SimpleNamespace(OpenPrinter=lambda printer_name: (_ for _ in ()).throw(RuntimeError("printer error"))),
        raising=False,
    )

    dialog.print_test()


def test_main_dialog_loads_professional_style(main_dialog):
    dialog, _ = main_dialog

    dialog.load_professional_style()

    assert dialog.styleSheet()


def test_main_dialog_key_press_navigation_and_print_calls(main_dialog, monkeypatch):
    dialog, _ = main_dialog
    print_calls = []
    focus_calls = []
    monkeypatch.setattr(dialog, "print_label", lambda: print_calls.append("printed"))
    monkeypatch.setattr(dialog.gold_input, "setFocus", lambda: focus_calls.append("gold"))
    monkeypatch.setattr(dialog.silver_input, "setFocus", lambda: focus_calls.append("silver"))

    enter_event = SimpleNamespace(key=lambda: main_dialog_module.Qt.Key_Return)

    monkeypatch.setattr(dialog, "focusWidget", lambda: dialog.weight_input)
    dialog.keyPressEvent(enter_event)
    assert focus_calls == ["gold"]

    dialog.gold_input.setText("750")
    monkeypatch.setattr(dialog, "focusWidget", lambda: dialog.gold_input)
    dialog.keyPressEvent(enter_event)
    assert print_calls == ["printed"]
    assert dialog.silver_input.text() == ""

    dialog.gold_input.clear()
    dialog.keyPressEvent(enter_event)
    assert focus_calls[-1] == "silver"

    dialog.silver_input.setText("925")
    monkeypatch.setattr(dialog, "focusWidget", lambda: dialog.silver_input)
    dialog.keyPressEvent(enter_event)
    assert print_calls == ["printed", "printed"]
    assert dialog.gold_input.text() == ""

    escape_event = QKeyEvent(QEvent.KeyPress, main_dialog_module.Qt.Key_Escape, main_dialog_module.Qt.NoModifier)
    dialog.keyPressEvent(escape_event)


def test_main_dialog_draw_rotated_text_handles_empty_arabic_and_angle(main_dialog):
    dialog, _ = main_dialog
    image = main_dialog_module.Image.new("RGBA", (160, 80), (255, 255, 255, 255))
    font = main_dialog_module.ImageFont.load_default()

    dialog._draw_rotated_text(image, "", 0, 0, font, 0)
    dialog._draw_rotated_text(image, "ذهب", 5, 5, font, 90)

    assert image.getbbox() is not None


def test_main_dialog_draw_rotated_text_ignores_reshaper_errors(main_dialog, monkeypatch):
    dialog, _ = main_dialog
    image = main_dialog_module.Image.new("RGBA", (160, 80), (255, 255, 255, 255))
    font = main_dialog_module.ImageFont.load_default()
    monkeypatch.setattr(
        main_dialog_module.arabic_reshaper,
        "reshape",
        lambda text: (_ for _ in ()).throw(RuntimeError("reshape failed")),
    )

    dialog._draw_rotated_text(image, "\u0630\u0647\u0628", 5, 5, font, 0)

    assert image.getbbox() is not None


def test_main_dialog_load_config_handles_invalid_json(main_dialog, tmp_path):
    dialog, _ = main_dialog
    (tmp_path / "label_config.json").write_text("{bad json", encoding="utf-8")

    config = dialog.load_config()

    assert config["label_width_mm"] == 40


def test_main_dialog_print_label_draws_logo_rotates_label_and_clears_inputs(
    main_dialog,
    monkeypatch,
):
    dialog, tmp_path = main_dialog
    logo_path = create_png(tmp_path / "logo.png", (0, 0, 0, 255))
    config_path = tmp_path / "label_config.json"
    write_main_config(
        config_path,
        orientation="Vertical",
        logo={"show": True, "path": str(logo_path), "x": 0, "y": 0, "angle": 90},
        logo_settings={"scale": 100, "threshold": 128},
        elements={
            "id": {"show": True, "text": "ID:", "x": 1, "y": 1, "size": 12, "font": "arial.ttf", "angle": 0},
            "date": {"show": True, "text": "Date:", "x": 1, "y": 4, "size": 12, "font": "arial.ttf", "angle": 0},
        },
    )
    drawn_texts = []
    writes = []
    monkeypatch.setattr(dialog, "_draw_rotated_text", lambda img, text, *args: drawn_texts.append(text))
    monkeypatch.setattr(main_dialog_module, "save_print_record", lambda **kwargs: None)
    monkeypatch.setattr(main_dialog_module, "win32print", fake_win32print(writes), raising=False)

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("750")
    dialog.print_label()

    assert "ID: Error" in drawn_texts
    assert any(text.startswith("Date:") for text in drawn_texts)
    assert writes and writes[0].startswith(b"SIZE 40 mm, 20 mm")
    assert dialog.weight_input.text() == ""
    assert dialog.gold_input.text() == ""
    assert dialog.silver_input.text() == ""


def test_main_dialog_print_label_handles_invalid_numeric_purity(main_dialog, monkeypatch):
    dialog, tmp_path = main_dialog
    config_path = tmp_path / "label_config.json"
    write_main_config(
        config_path,
        elements={
            "equiv_weight": {"show": True, "text": "Eq:", "x": 1, "y": 1, "size": 12, "font": "arial.ttf", "angle": 0},
        },
    )
    saved_records = []
    drawn_texts = []
    monkeypatch.setattr(main_dialog_module, "save_print_record", lambda **kwargs: saved_records.append(kwargs) or 22)
    monkeypatch.setattr(main_dialog_module, "win32print", fake_win32print(), raising=False)
    monkeypatch.setattr(dialog, "_draw_rotated_text", lambda img, text, *args: drawn_texts.append(text))

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("abc")
    dialog.print_label()

    assert saved_records[0]["purity"] == 0.0
    assert saved_records[0]["equiv_weight"] == 0.0
    assert "Eq: 0.00 g" in drawn_texts


def test_main_dialog_print_label_uses_default_font_for_missing_font(main_dialog, monkeypatch, tmp_path):
    dialog, tmp_path = main_dialog
    write_main_config(
        tmp_path / "label_config.json",
        elements={
            "store": {
                "show": True,
                "text": "Store",
                "x": 1,
                "y": 1,
                "size": 12,
                "font": "definitely-missing-font.ttf",
                "angle": 0,
            },
        },
    )
    monkeypatch.setattr(main_dialog_module, "save_print_record", lambda **kwargs: 11)
    monkeypatch.setattr(main_dialog_module, "win32print", fake_win32print(), raising=False)

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("750")
    dialog.print_label()

    assert dialog.weight_input.text() == ""


def test_main_dialog_print_label_handles_logo_open_errors(main_dialog, monkeypatch, tmp_path):
    dialog, tmp_path = main_dialog
    logo_path = create_png(tmp_path / "broken-logo.png", (0, 0, 0, 255))
    write_main_config(
        tmp_path / "label_config.json",
        logo={"show": True, "path": str(logo_path), "x": 0, "y": 0, "angle": 0},
        elements={},
    )
    monkeypatch.setattr(main_dialog_module.Image, "open", lambda path: (_ for _ in ()).throw(RuntimeError("logo failed")))
    monkeypatch.setattr(main_dialog_module, "save_print_record", lambda **kwargs: 12)
    monkeypatch.setattr(main_dialog_module, "win32print", fake_win32print(), raising=False)

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("750")
    dialog.print_label()

    assert dialog.weight_input.text() == ""


def test_main_dialog_print_label_hides_gold_equiv_and_skips_missing_conversion(
    main_dialog,
    monkeypatch,
    tmp_path,
):
    dialog, tmp_path = main_dialog
    drawn_texts = []
    write_main_config(
        tmp_path / "label_config.json",
        elements={
            "equiv_weight": {
                "show": True,
                "text": "Eq:",
                "x": 1,
                "y": 1,
                "size": 12,
                "font": "arial.ttf",
                "angle": 0,
                "show_for_gold": False,
            },
            "conv_gold_730": {
                "show": True,
                "text": "730:",
                "x": 1,
                "y": 4,
                "size": 12,
                "font": "arial.ttf",
                "angle": 0,
            },
        },
    )
    monkeypatch.setattr(dialog, "_draw_rotated_text", lambda img, text, *args: drawn_texts.append(text))
    monkeypatch.setitem(
        main_dialog_module.LABEL_CONVERSION_ELEMENTS,
        "conv_missing",
        {"metal": "Or", "ref": 760.0, "label": "Missing"},
    )
    monkeypatch.setattr(main_dialog_module, "save_print_record", lambda **kwargs: 13)
    monkeypatch.setattr(main_dialog_module, "win32print", fake_win32print(), raising=False)

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("750")
    dialog.print_label()

    assert not any(text.startswith("Eq:") for text in drawn_texts)
    assert any(text.startswith("730:") for text in drawn_texts)


def test_main_dialog_print_label_uses_conversion_ref_fallback(main_dialog, monkeypatch, tmp_path):
    dialog, tmp_path = main_dialog
    drawn_texts = []
    write_main_config(
        tmp_path / "label_config.json",
        fallback_ref=800,
        elements={
            "conv_gold_730": {
                "show": True,
                "text": "Fallback:",
                "x": 1,
                "y": 1,
                "size": 12,
                "font": "arial.ttf",
                "angle": 0,
            },
        },
    )
    monkeypatch.setitem(
        main_dialog_module.LABEL_CONVERSION_ELEMENTS,
        "conv_gold_730",
        {"metal": "Or", "ref": None, "ref_key": "fallback_ref", "default_ref": 730.0, "label": "Fallback"},
    )
    monkeypatch.setattr(dialog, "_draw_rotated_text", lambda img, text, *args: drawn_texts.append(text))
    monkeypatch.setattr(main_dialog_module, "save_print_record", lambda **kwargs: 14)
    monkeypatch.setattr(main_dialog_module, "win32print", fake_win32print(), raising=False)

    dialog.weight_input.setText("8")
    dialog.gold_input.setText("750")
    dialog.print_label()

    assert "Fallback: 7.50 g" in drawn_texts


def test_main_dialog_print_label_warns_when_printer_missing(main_dialog, monkeypatch):
    dialog, tmp_path = main_dialog
    (tmp_path / "label_config.json").write_text(
        json.dumps({"printer_name": "", "elements": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    opened_settings = []
    monkeypatch.setattr(dialog, "open_settings", lambda: opened_settings.append("opened"))

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("750")
    dialog.print_label()

    assert opened_settings == ["opened"]


def test_main_dialog_print_label_handles_printer_error(main_dialog, monkeypatch):
    dialog, tmp_path = main_dialog
    write_main_config(tmp_path / "label_config.json")
    monkeypatch.setattr(main_dialog_module, "save_print_record", lambda **kwargs: 5)
    monkeypatch.setattr(
        main_dialog_module,
        "win32print",
        fake_win32print(open_error=RuntimeError("printer unavailable")),
        raising=False,
    )

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("750")
    dialog.print_label()

    assert dialog.weight_input.text() == "4.25"


def test_main_dialog_open_settings_refreshes_when_accepted(main_dialog, monkeypatch):
    dialog, _ = main_dialog
    calls = []

    class AcceptedSettingsDialog:
        def __init__(self, parent=None):
            self.parent = parent

        def exec(self):
            return True

    monkeypatch.setattr(main_dialog_module, "SettingsDialog", AcceptedSettingsDialog)
    monkeypatch.setattr(dialog, "load_professional_style", lambda: calls.append("style"))
    monkeypatch.setattr(dialog, "update_live_equiv", lambda: calls.append("live"))

    dialog.open_settings()

    assert calls == ["style", "live"]


def test_main_dialog_open_history_executes_dialog(main_dialog, monkeypatch):
    dialog, _ = main_dialog
    calls = []

    class FakeHistoryDialog:
        def __init__(self, parent=None):
            self.parent = parent

        def exec(self):
            calls.append("history")

    import ui.history_dialog as history_dialog_module

    monkeypatch.setattr(history_dialog_module, "HistoryDialog", FakeHistoryDialog)

    dialog.open_history()

    assert calls == ["history"]


def test_main_dialog_open_history_warns_when_dialog_import_fails(main_dialog, monkeypatch):
    import builtins

    dialog, _ = main_dialog
    infos = []
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "history_dialog" and level == 1:
            raise ImportError("missing history dialog")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(main_dialog_module.QMessageBox, "information", lambda *args: infos.append(args))

    dialog.open_history()

    assert infos
