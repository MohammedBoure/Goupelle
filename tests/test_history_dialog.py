import sqlite3

from PySide6.QtCore import QDate

import ui.history_dialog as history_dialog_module
from ui.history_dialog import HistoryDialog


def create_history_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE printed_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                print_time TEXT,
                metal_type TEXT,
                actual_purity REAL,
                actual_weight REAL,
                equivalent_weight REAL,
                printer_name TEXT
            )
            """
        )
        conn.commit()


def insert_record(
    path,
    print_time,
    metal_type,
    purity,
    weight,
    equivalent_weight,
    printer_name="Test Printer",
):
    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO printed_labels
            (print_time, metal_type, actual_purity, actual_weight, equivalent_weight, printer_name)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (print_time, metal_type, purity, weight, equivalent_weight, printer_name),
        )
        conn.commit()
        return cursor.lastrowid


def open_history_dialog(qapp, monkeypatch, db_path):
    monkeypatch.setattr(history_dialog_module, "DB_FILE", str(db_path))
    dialog = HistoryDialog()
    dialog.date_from.setDate(QDate(2026, 1, 1))
    dialog.date_to.setDate(QDate(2026, 12, 31))
    dialog.load_data()
    return dialog


def table_row_texts(dialog, row):
    return [dialog.table.item(row, col).text() for col in range(dialog.table.columnCount())]


def test_history_table_displays_saved_records(qapp, monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    create_history_db(db_path)
    insert_record(db_path, "2026-06-08 10:00:00", "Or", 750.0, 4.25, 4.37, "Printer A")
    insert_record(db_path, "2026-06-08 11:00:00", "Argent", 925.0, 10.0, 10.0, "Printer B")

    dialog = open_history_dialog(qapp, monkeypatch, db_path)

    try:
        assert dialog.table.rowCount() == 2
        assert table_row_texts(dialog, 0) == [
            "2",
            "2026-06-08 11:00:00",
            "Argent",
            "925",
            "10 g",
        ]
        assert table_row_texts(dialog, 1) == [
            "1",
            "2026-06-08 10:00:00",
            "Or",
            "750",
            "4.25 g",
        ]
    finally:
        dialog.close()


def test_history_table_uses_expected_columns(qapp, monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    create_history_db(db_path)

    dialog = open_history_dialog(qapp, monkeypatch, db_path)

    try:
        headers = [
            dialog.table.horizontalHeaderItem(index).text()
            for index in range(dialog.table.columnCount())
        ]
        assert headers == ["ID", "التاريخ والوقت", "المعدن", "العيار", "الوزن الفعلي"]
    finally:
        dialog.close()


def test_history_details_show_selected_saved_record(qapp, monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    create_history_db(db_path)
    insert_record(db_path, "2026-06-08 10:00:00", "Or", 750.0, 4.25, 4.37, "Printer A")

    dialog = open_history_dialog(qapp, monkeypatch, db_path)

    try:
        dialog.table.setCurrentCell(0, 0)
        dialog.table.selectRow(0)
        dialog.table.item(0, 0).setSelected(True)
        dialog.show_details()

        assert dialog.lbl_det_id.text() == "1"
        assert dialog.lbl_det_date.text() == "2026-06-08 10:00:00"
        assert dialog.lbl_det_metal.text() == "Or"
        assert dialog.lbl_det_purity.text() == "750"
        assert dialog.lbl_det_weight.text() == "4.25 g"
        assert dialog.lbl_det_equiv.text() == "4.37 g"
        assert dialog.lbl_det_printer.text() == "Printer A"
    finally:
        dialog.close()


def test_history_empty_database_does_not_crash(qapp, monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    create_history_db(db_path)

    dialog = open_history_dialog(qapp, monkeypatch, db_path)

    try:
        assert dialog.table.rowCount() == 0
        assert dialog.lbl_page_info.text() == "صفحة 1 من 1 (إجمالي: 0)"
        assert dialog.lbl_det_id.text() == "-"
        assert dialog.lbl_det_equiv.text() == "-"
    finally:
        dialog.close()


def test_history_table_updates_after_new_record_is_added(qapp, monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    create_history_db(db_path)
    insert_record(db_path, "2026-06-08 10:00:00", "Or", 750.0, 4.25, 4.37)

    dialog = open_history_dialog(qapp, monkeypatch, db_path)

    try:
        assert dialog.table.rowCount() == 1

        insert_record(db_path, "2026-06-08 12:00:00", "Argent", 925.0, 8.0, 8.0)
        dialog.load_data()

        assert dialog.table.rowCount() == 2
        assert table_row_texts(dialog, 0) == [
            "2",
            "2026-06-08 12:00:00",
            "Argent",
            "925",
            "8 g",
        ]
    finally:
        dialog.close()
