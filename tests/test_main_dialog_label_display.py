import json
from types import SimpleNamespace

import pytest

import ui.main_dialog as main_dialog_module
from ui.main_dialog import MainPrintDialog


def write_config(path, elements=None):
    path.write_text(
        json.dumps(
            {
                "printer_name": "Test Printer",
                "label_width_mm": 40,
                "label_height_mm": 20,
                "gap_mm": 2,
                "offset_x_mm": 0,
                "offset_y_mm": 0,
                "orientation": "Horizontal",
                "elements": elements or {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@pytest.fixture
def main_dialog(qapp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_dialog_module, "init_db", lambda: None)
    dialog = MainPrintDialog()
    yield dialog, tmp_path / "label_config.json"
    dialog.close()


@pytest.fixture
def fake_printing(monkeypatch):
    saved_records = []

    def fake_save_print_record(**kwargs):
        saved_records.append(kwargs)
        return 1005

    fake_win32print = SimpleNamespace(
        OpenPrinter=lambda printer_name: object(),
        StartDocPrinter=lambda *args, **kwargs: None,
        StartPagePrinter=lambda *args, **kwargs: None,
        WritePrinter=lambda *args, **kwargs: None,
        EndPagePrinter=lambda *args, **kwargs: None,
        EndDocPrinter=lambda *args, **kwargs: None,
        ClosePrinter=lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(main_dialog_module, "save_print_record", fake_save_print_record)
    monkeypatch.setattr(main_dialog_module, "win32print", fake_win32print, raising=False)
    return saved_records


def capture_drawn_texts(dialog, monkeypatch):
    drawn_texts = []

    def fake_draw(img, text, x, y, font, angle):
        drawn_texts.append(text)

    monkeypatch.setattr(dialog, "_draw_rotated_text", fake_draw)
    return drawn_texts


def visible_extra_refs(dialog):
    return {
        ref
        for ref, label in dialog.extra_conversion_labels.items()
        if not label.isHidden()
    }


def print_label_and_capture(dialog, monkeypatch, weight, gold="", silver=""):
    drawn_texts = capture_drawn_texts(dialog, monkeypatch)
    dialog.weight_input.setText(weight)
    dialog.gold_input.setText(gold)
    dialog.silver_input.setText(silver)
    dialog.print_label()
    return drawn_texts


def test_live_gold_displays_only_730_and_750(main_dialog):
    dialog, _ = main_dialog

    dialog.weight_input.setText("4.25")
    dialog.gold_input.setText("750")

    assert dialog.lbl_live_title.text() == "730:"
    assert dialog.lbl_live_equiv.text() == "4.37 g"
    assert visible_extra_refs(dialog) == {"750"}
    assert dialog.extra_conversion_labels["750"].text() == "4.25 g"


def test_live_silver_displays_only_925_and_9999(main_dialog):
    dialog, _ = main_dialog

    dialog.weight_input.setText("10")
    dialog.silver_input.setText("925")

    assert dialog.lbl_live_title.text() == "925:"
    assert dialog.lbl_live_equiv.text() == "10.00 g"
    assert visible_extra_refs(dialog) == {"999.9"}
    assert dialog.extra_conversion_labels["999.9"].text() == "9.25 g"


def test_label_gold_draws_only_gold_conversion_elements(main_dialog, fake_printing, monkeypatch):
    dialog, config_path = main_dialog
    write_config(
        config_path,
        {
            "conv_gold_730": {"show": True, "text": "G730:", "x": 1, "y": 1, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_gold_750": {"show": True, "text": "G750:", "x": 1, "y": 2, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_silver_925": {"show": True, "text": "S925:", "x": 1, "y": 3, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_silver_9999": {"show": True, "text": "S999:", "x": 1, "y": 4, "size": 12, "font": "arial.ttf", "angle": 0},
        },
    )

    drawn_texts = print_label_and_capture(dialog, monkeypatch, "4.25", gold="750")

    assert "G730: 4.37 g" in drawn_texts
    assert "G750: 4.25 g" in drawn_texts
    assert all(not text.startswith("S925:") for text in drawn_texts)
    assert all(not text.startswith("S999:") for text in drawn_texts)
    assert fake_printing[0]["equiv_weight"] == pytest.approx(4.25 * 750 / 730)


def test_label_silver_draws_only_silver_conversion_elements(main_dialog, fake_printing, monkeypatch):
    dialog, config_path = main_dialog
    write_config(
        config_path,
        {
            "conv_gold_730": {"show": True, "text": "G730:", "x": 1, "y": 1, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_gold_750": {"show": True, "text": "G750:", "x": 1, "y": 2, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_silver_925": {"show": True, "text": "S925:", "x": 1, "y": 3, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_silver_9999": {"show": True, "text": "S999:", "x": 1, "y": 4, "size": 12, "font": "arial.ttf", "angle": 0},
        },
    )

    drawn_texts = print_label_and_capture(dialog, monkeypatch, "10", silver="925")

    assert "S925: 10.00 g" in drawn_texts
    assert "S999: 9.25 g" in drawn_texts
    assert all(not text.startswith("G730:") for text in drawn_texts)
    assert all(not text.startswith("G750:") for text in drawn_texts)
    assert fake_printing[0]["equiv_weight"] == pytest.approx(10 * 925 / 925)


def test_disabled_label_element_is_not_drawn(main_dialog, fake_printing, monkeypatch):
    dialog, config_path = main_dialog
    write_config(
        config_path,
        {
            "weight": {"show": False, "text": "Weight:", "x": 1, "y": 1, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_gold_730": {"show": True, "text": "G730:", "x": 1, "y": 2, "size": 12, "font": "arial.ttf", "angle": 0},
        },
    )

    drawn_texts = print_label_and_capture(dialog, monkeypatch, "4.25", gold="750")

    assert all(not text.startswith("Weight:") for text in drawn_texts)
    assert "G730: 4.37 g" in drawn_texts


def test_custom_label_prefixes_are_drawn_before_values(main_dialog, fake_printing, monkeypatch):
    dialog, config_path = main_dialog
    write_config(
        config_path,
        {
            "metal": {"show": True, "text": "Metal is", "x": 1, "y": 1, "size": 12, "font": "arial.ttf", "angle": 0},
            "purity": {"show": True, "text": "Titre =", "x": 1, "y": 2, "size": 12, "font": "arial.ttf", "angle": 0},
            "weight": {"show": True, "text": "Poids =", "x": 1, "y": 3, "size": 12, "font": "arial.ttf", "angle": 0},
            "conv_gold_750": {"show": True, "text": "Or 750 =", "x": 1, "y": 5, "size": 12, "font": "arial.ttf", "angle": 0},
        },
    )

    drawn_texts = print_label_and_capture(dialog, monkeypatch, "4.25", gold="750")

    assert "Metal is Or" in drawn_texts
    assert "Titre = 750 mg/g" in drawn_texts
    assert "Poids = 4.25 g" in drawn_texts
    assert "Or 750 = 4.25 g" in drawn_texts
