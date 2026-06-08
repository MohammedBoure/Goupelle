import json

import pytest

from ui.settings_dialog import LABEL_CONVERSION_ELEMENTS, SettingsDialog


STANDARD_ELEMENT_KEYS = [
    "id",
    "store",
    "metal",
    "purity",
    "weight",
    "date",
]

CONVERSION_ELEMENT_KEYS = [
    "conv_gold_730",
    "conv_gold_750",
    "conv_silver_925",
    "conv_silver_9999",
]


@pytest.fixture
def settings_dialog(qapp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    dialog = SettingsDialog()
    dialog.preview_timer.stop()
    yield dialog, tmp_path / "label_config.json"
    dialog.close()


def save_and_load(dialog, config_path):
    dialog.save_config()
    assert config_path.exists()
    return json.loads(config_path.read_text(encoding="utf-8"))


def set_angle_combo(combo, degrees):
    index_by_degrees = {0: 0, 90: 1, 180: 2, 270: 3}
    combo.setCurrentIndex(index_by_degrees[degrees])


def test_loads_default_settings_when_config_is_missing(settings_dialog):
    dialog, config_path = settings_dialog

    assert not config_path.exists()
    assert dialog.config["printer_name"] == ""
    assert dialog.config["label_width_mm"] == 40
    assert dialog.config["label_height_mm"] == 20
    assert dialog.config["gap_mm"] == 2.0
    assert dialog.config["offset_x_mm"] == 0.0
    assert dialog.config["offset_y_mm"] == 0.0
    assert dialog.config["orientation"] == "Horizontal"

    for key in STANDARD_ELEMENT_KEYS + CONVERSION_ELEMENT_KEYS:
        assert key in dialog.config["elements"]

    assert set(LABEL_CONVERSION_ELEMENTS) == set(CONVERSION_ELEMENT_KEYS)


def test_save_config_writes_label_geometry_dpi_margins_and_logo(settings_dialog, tmp_path):
    dialog, config_path = settings_dialog

    dialog.sp_w.setValue(42.0)
    dialog.sp_h.setValue(21.0)
    image = dialog.get_pil_image()
    assert image.size == (336, 168)

    dialog.cmb_printer.addItem("Test Printer")
    dialog.cmb_printer.setCurrentText("Test Printer")
    dialog.sp_gap.setValue(3.5)
    dialog.sp_offset_x.setValue(1.25)
    dialog.sp_offset_y.setValue(-2.5)
    dialog.cmb_orient.setCurrentText("Vertical")

    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(b"not a real image, only a saved path")
    dialog.chk_logo.setChecked(True)
    dialog.lbl_logo_path.setText(str(logo_path))
    dialog.sp_logo_x.setValue(4.5)
    dialog.sp_logo_y.setValue(6.75)
    set_angle_combo(dialog.cmb_logo_angle, 90)
    dialog.logo_settings = {"scale": 125, "threshold": 180}

    saved = save_and_load(dialog, config_path)

    assert saved["printer_name"] == "Test Printer"
    assert saved["label_width_mm"] == 42.0
    assert saved["label_height_mm"] == 21.0
    assert saved["gap_mm"] == 3.5
    assert saved["offset_x_mm"] == 1.25
    assert saved["offset_y_mm"] == -2.5
    assert saved["orientation"] == "Vertical"
    assert saved["logo"] == {
        "show": True,
        "path": str(logo_path),
        "x": 4.5,
        "y": 6.75,
        "angle": 90,
    }
    assert saved["logo_settings"] == {"scale": 125, "threshold": 180}


def test_save_config_writes_standard_label_element_properties(settings_dialog):
    dialog, config_path = settings_dialog

    for index, key in enumerate(STANDARD_ELEMENT_KEYS):
        getattr(dialog, f"chk_{key}").setChecked(index % 2 == 0)
        getattr(dialog, f"inp_{key}").setText(f"{key} prefix")
        getattr(dialog, f"sp_{key}_x").setValue(index + 1.5)
        getattr(dialog, f"sp_{key}_y").setValue(index + 2.5)
        getattr(dialog, f"sp_{key}_sz").setValue(10 + index)
        getattr(dialog, f"cmb_{key}_f").setCurrentText("tahoma.ttf")
        set_angle_combo(getattr(dialog, f"cmb_{key}_a"), 180)

    saved = save_and_load(dialog, config_path)

    for index, key in enumerate(STANDARD_ELEMENT_KEYS):
        element = saved["elements"][key]
        assert element["show"] is (index % 2 == 0)
        assert element["text"] == f"{key} prefix"
        assert element["x"] == index + 1.5
        assert element["y"] == index + 2.5
        assert element["size"] == 10 + index
        assert element["font"] == "tahoma.ttf"
        assert element["angle"] == 180


def test_save_config_writes_conversion_element_options(settings_dialog):
    dialog, config_path = settings_dialog

    for index, key in enumerate(CONVERSION_ELEMENT_KEYS):
        getattr(dialog, f"chk_{key}").setChecked(True)
        getattr(dialog, f"inp_{key}").setText(f"{LABEL_CONVERSION_ELEMENTS[key]['label']} =")
        getattr(dialog, f"sp_{key}_x").setValue(20 + index)
        getattr(dialog, f"sp_{key}_y").setValue(10 + index)
        getattr(dialog, f"sp_{key}_sz").setValue(14 + index)
        getattr(dialog, f"cmb_{key}_f").setCurrentText("calibri.ttf")
        set_angle_combo(getattr(dialog, f"cmb_{key}_a"), 270)

    saved = save_and_load(dialog, config_path)

    for index, key in enumerate(CONVERSION_ELEMENT_KEYS):
        element = saved["elements"][key]
        assert element["show"] is True
        assert element["text"] == f"{LABEL_CONVERSION_ELEMENTS[key]['label']} ="
        assert element["x"] == 20 + index
        assert element["y"] == 10 + index
        assert element["size"] == 14 + index
        assert element["font"] == "calibri.ttf"
        assert element["angle"] == 270


def test_preview_draws_all_enabled_conversion_elements(settings_dialog, monkeypatch):
    dialog, _ = settings_dialog
    drawn_texts = []

    for key in CONVERSION_ELEMENT_KEYS:
        getattr(dialog, f"chk_{key}").setChecked(True)

    monkeypatch.setattr(
        dialog,
        "_draw_rotated_text",
        lambda img, text, x, y, font, angle: drawn_texts.append(text),
    )

    dialog.get_pil_image()

    assert "730: 4.37 g" in drawn_texts
    assert "750: 4.25 g" in drawn_texts
    assert "925: 3.45 g" in drawn_texts
    assert "999.9: 3.19 g" in drawn_texts


def test_equivalent_weight_setting_is_removed(settings_dialog):
    dialog, config_path = settings_dialog

    assert "equiv_weight" not in dialog.config["elements"]
    assert not hasattr(dialog, "chk_equiv_weight")
    assert not hasattr(dialog, "chk_equiv_gold")
    assert not hasattr(dialog, "chk_equiv_silver")

    saved = save_and_load(dialog, config_path)

    assert "equiv_weight" not in saved["elements"]


def test_reference_purity_fields_are_not_required_for_save(settings_dialog):
    dialog, config_path = settings_dialog

    assert not hasattr(dialog, "sp_ref_gold")
    assert not hasattr(dialog, "sp_ref_silver")

    saved = save_and_load(dialog, config_path)

    assert saved["ref_gold"] == 730.0
    assert saved["ref_silver"] == 925.0
