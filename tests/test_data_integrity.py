import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ui.main_dialog as main_dialog_module
from ui.main_dialog import MainPrintDialog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_DATA_FILES = [
    PROJECT_ROOT / "label_config.json",
    PROJECT_ROOT / "print_history.db",
]


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
def real_data_file_stats():
    return {
        path: path.stat().st_mtime_ns
        for path in REAL_DATA_FILES
        if path.exists()
    }


@pytest.fixture
def isolated_main_dialog(qapp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_dialog_module, "init_db", lambda: None)
    dialog = MainPrintDialog()
    config_path = tmp_path / "label_config.json"
    write_config(config_path)
    yield dialog, config_path
    dialog.close()


@pytest.fixture
def fake_persistence_and_printing(monkeypatch):
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


def mute_label_drawing(dialog, monkeypatch):
    monkeypatch.setattr(dialog, "_draw_rotated_text", lambda *args, **kwargs: None)


def attempt_print(dialog, monkeypatch, weight="", gold="", silver=""):
    mute_label_drawing(dialog, monkeypatch)
    dialog.weight_input.setText(weight)
    dialog.gold_input.setText(gold)
    dialog.silver_input.setText(silver)
    dialog.print_label()


def assert_real_data_files_unchanged(stats_before):
    for path, old_mtime in stats_before.items():
        assert path.exists()
        assert path.stat().st_mtime_ns == old_mtime


def test_weight_accepts_comma_and_dot_decimals(
    isolated_main_dialog,
    fake_persistence_and_printing,
    monkeypatch,
):
    dialog, _ = isolated_main_dialog

    attempt_print(dialog, monkeypatch, weight="3,5", gold="750")
    attempt_print(dialog, monkeypatch, weight="3.5", gold="750")

    assert [record["weight"] for record in fake_persistence_and_printing] == [3.5, 3.5]
    assert fake_persistence_and_printing[0]["equiv_weight"] == pytest.approx(3.5 * 750 / 730)
    assert fake_persistence_and_printing[1]["equiv_weight"] == pytest.approx(3.5 * 750 / 730)


def test_silver_9999_purity_is_calculated_and_saved_correctly(
    isolated_main_dialog,
    fake_persistence_and_printing,
    monkeypatch,
):
    dialog, _ = isolated_main_dialog

    dialog.weight_input.setText("10")
    dialog.silver_input.setText("999.9")

    assert dialog.lbl_live_title.text() == "925:"
    assert dialog.lbl_live_equiv.text() == "10.81 g"
    assert dialog.extra_conversion_labels["999.9"].text() == "10.00 g"

    attempt_print(dialog, monkeypatch, weight="10", silver="999.9")

    saved = fake_persistence_and_printing[0]
    assert saved["metal_type"] == "Argent"
    assert saved["purity"] == pytest.approx(999.9)
    assert saved["weight"] == pytest.approx(10.0)
    assert saved["equiv_weight"] == pytest.approx(10 * 999.9 / 925)


@pytest.mark.parametrize(
    ("weight", "gold", "silver"),
    [
        ("", "750", ""),
        ("0", "750", ""),
        ("3.5", "", ""),
    ],
)
def test_empty_or_missing_values_do_not_save_invalid_records(
    isolated_main_dialog,
    fake_persistence_and_printing,
    monkeypatch,
    weight,
    gold,
    silver,
):
    dialog, _ = isolated_main_dialog

    attempt_print(dialog, monkeypatch, weight=weight, gold=gold, silver=silver)

    assert fake_persistence_and_printing == []


def test_gold_input_ignores_silver_purity_for_saved_record(
    isolated_main_dialog,
    fake_persistence_and_printing,
    monkeypatch,
):
    dialog, _ = isolated_main_dialog

    attempt_print(dialog, monkeypatch, weight="4", gold="750", silver="925")

    saved = fake_persistence_and_printing[0]
    assert saved["metal_type"] == "Or"
    assert saved["purity"] == pytest.approx(750.0)
    assert saved["equiv_weight"] == pytest.approx(4 * 750 / 730)


def test_silver_input_uses_silver_purity_for_saved_record(
    isolated_main_dialog,
    fake_persistence_and_printing,
    monkeypatch,
):
    dialog, _ = isolated_main_dialog

    attempt_print(dialog, monkeypatch, weight="4", silver="925")

    saved = fake_persistence_and_printing[0]
    assert saved["metal_type"] == "Argent"
    assert saved["purity"] == pytest.approx(925.0)
    assert saved["equiv_weight"] == pytest.approx(4 * 925 / 925)


def test_integrity_tests_do_not_modify_real_data_files(
    isolated_main_dialog,
    fake_persistence_and_printing,
    monkeypatch,
    real_data_file_stats,
):
    dialog, config_path = isolated_main_dialog

    attempt_print(dialog, monkeypatch, weight="3,5", gold="750")

    assert config_path.exists()
    assert fake_persistence_and_printing
    assert_real_data_files_unchanged(real_data_file_stats)
