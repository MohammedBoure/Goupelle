import json
from pathlib import Path

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QGroupBox

from main import apply_white_theme
from ui.settings_dialog import SettingsDialog


CONVERSION_KEYS = [
    "conv_gold_730",
    "conv_gold_750",
    "conv_silver_925",
    "conv_silver_9999",
]
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def save_and_read(dialog, config_path):
    dialog.save_config()
    return json.loads(config_path.read_text(encoding="utf-8"))


def test_application_applies_white_fusion_theme(qapp):
    apply_white_theme(qapp)
    palette = qapp.palette()

    assert qapp.style().objectName().lower() == "fusion"
    assert palette.color(QPalette.Window).name() == "#ffffff"
    assert palette.color(QPalette.Base).name() == "#ffffff"
    assert palette.color(QPalette.Button).name() == "#ffffff"


def test_main_stylesheet_keeps_core_widgets_white():
    stylesheet = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")

    assert "QDialog, QWidget" in stylesheet
    assert "background-color: #ffffff" in stylesheet
    assert "QLineEdit" in stylesheet
    assert "background-color: #ffffff" in stylesheet


def test_settings_dialog_does_not_show_reference_purity_section(qapp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    dialog = SettingsDialog()
    dialog.preview_timer.stop()

    try:
        group_titles = [box.title() for box in dialog.findChildren(QGroupBox)]
        assert all("العيار المرجعي للتحويل" not in title for title in group_titles)
        assert not hasattr(dialog, "sp_ref_gold")
        assert not hasattr(dialog, "sp_ref_silver")
    finally:
        dialog.close()


def test_settings_dialog_allows_enabling_gold_and_silver_conversion_label_options(
    qapp,
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "label_config.json"
    dialog = SettingsDialog()
    dialog.preview_timer.stop()

    try:
        for key in CONVERSION_KEYS:
            getattr(dialog, f"chk_{key}").setChecked(True)

        saved = save_and_read(dialog, config_path)

        assert saved["elements"]["conv_gold_730"]["show"] is True
        assert saved["elements"]["conv_gold_750"]["show"] is True
        assert saved["elements"]["conv_silver_925"]["show"] is True
        assert saved["elements"]["conv_silver_9999"]["show"] is True
    finally:
        dialog.close()


def test_settings_save_does_not_require_reference_purity_widgets(qapp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "label_config.json"
    dialog = SettingsDialog()
    dialog.preview_timer.stop()

    try:
        assert not hasattr(dialog, "sp_ref_gold")
        assert not hasattr(dialog, "sp_ref_silver")

        saved = save_and_read(dialog, config_path)

        assert saved["ref_gold"] == 730.0
        assert saved["ref_silver"] == 925.0
    finally:
        dialog.close()
