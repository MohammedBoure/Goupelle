import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def no_message_boxes(monkeypatch):
    def _noop(*args, **kwargs):
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "information", _noop)
    monkeypatch.setattr(QMessageBox, "warning", _noop)
    monkeypatch.setattr(QMessageBox, "critical", _noop)
