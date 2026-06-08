import sqlite3

import database


def insert_record(
    db_path,
    print_time,
    metal_type,
    purity,
    weight,
    equivalent_weight,
    printer_name="Test Printer",
):
    with sqlite3.connect(db_path) as conn:
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


def table_columns(db_path):
    with sqlite3.connect(db_path) as conn:
        return [row[1] for row in conn.execute("PRAGMA table_info(printed_labels)")]


def table_rows(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT * FROM printed_labels ORDER BY id").fetchall()


def test_init_db_creates_printed_labels_table(monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path))

    database.init_db()

    assert db_path.exists()
    assert table_columns(db_path) == [
        "id",
        "print_time",
        "metal_type",
        "actual_purity",
        "actual_weight",
        "equivalent_weight",
        "printer_name",
    ]


def test_save_print_record_returns_id_and_persists_values(monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path))
    database.init_db()

    record_id = database.save_print_record("Or", 750.0, 4.25, 4.37, "Printer A")

    rows = table_rows(db_path)
    assert record_id == 1
    assert len(rows) == 1
    assert rows[0][0] == 1
    assert rows[0][1]
    assert rows[0][2:] == ("Or", 750.0, 4.25, 4.37, "Printer A")


def test_get_record_by_id_returns_exact_record(monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path))
    database.init_db()
    first_id = insert_record(db_path, "2026-06-08 10:00:00", "Or", 750.0, 4.25, 4.37)
    second_id = insert_record(db_path, "2026-06-08 11:00:00", "Argent", 925.0, 10.0, 10.0)

    record = database.get_record_by_id(second_id)

    assert first_id == 1
    assert record == (
        2,
        "2026-06-08 11:00:00",
        "Argent",
        925.0,
        10.0,
        10.0,
        "Test Printer",
    )


def test_get_record_by_id_returns_none_for_missing_record(monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path))
    database.init_db()

    assert database.get_record_by_id(404) is None


def test_get_records_by_date_range_filters_and_orders_desc(monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path))
    database.init_db()
    insert_record(db_path, "2026-06-01 09:00:00", "Or", 730.0, 2.0, 2.0)
    insert_record(db_path, "2026-06-08 10:00:00", "Or", 750.0, 4.25, 4.37)
    insert_record(db_path, "2026-06-08 12:00:00", "Argent", 925.0, 8.0, 8.0)
    insert_record(db_path, "2026-07-01 09:00:00", "Argent", 999.9, 3.0, 3.0)

    records = database.get_records_by_date_range(
        "2026-06-08 00:00:00",
        "2026-06-08 23:59:59",
    )

    assert [record[1] for record in records] == [
        "2026-06-08 12:00:00",
        "2026-06-08 10:00:00",
    ]
    assert [record[2] for record in records] == ["Argent", "Or"]


def test_get_records_by_date_range_returns_empty_for_empty_table(monkeypatch, tmp_path):
    db_path = tmp_path / "print_history.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path))
    database.init_db()

    assert database.get_records_by_date_range(
        "2026-06-08 00:00:00",
        "2026-06-08 23:59:59",
    ) == []


def test_get_last_month_records_delegates_to_date_range(monkeypatch):
    calls = []

    def fake_get_records_by_date_range(start_date, end_date):
        calls.append((start_date, end_date))
        return ["records"]

    monkeypatch.setattr(database, "get_records_by_date_range", fake_get_records_by_date_range)

    assert database.get_last_month_records() == ["records"]
    assert len(calls) == 1
    assert calls[0][0].endswith("00:00:00")
    assert calls[0][1].endswith("23:59:59")
