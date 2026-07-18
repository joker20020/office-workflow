"""Regression checks for locale-resilient PySide6 layouts."""

from PySide6.QtWidgets import QApplication, QLabel


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_clipped_label_exposes_its_full_text_in_a_tooltip():
    from src.ui.layout_utils import apply_elision_tooltip

    _application()
    label = QLabel("A translated label that cannot fit in this narrow row")
    label.resize(20, 24)

    apply_elision_tooltip(label)

    assert label.toolTip() == label.text()


def test_unclipped_label_does_not_gain_a_redundant_tooltip():
    from src.ui.layout_utils import apply_elision_tooltip

    _application()
    label = QLabel("Short label")
    label.resize(300, 24)

    apply_elision_tooltip(label)

    assert label.toolTip() == ""
