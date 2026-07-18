"""Small presentation helpers shared by responsive UI widgets."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton


def apply_elision_tooltip(widget: QLabel | QPushButton) -> None:
    """Expose complete text when a compact one-line control clips it.

    Existing explicit tooltips take precedence.  Wrapping labels should not
    call this helper because their content remains directly readable.
    """

    if widget.toolTip():
        return

    text = widget.text()
    available_width = widget.contentsRect().width()
    if not text or available_width <= 0:
        return

    elided = widget.fontMetrics().elidedText(
        text,
        Qt.TextElideMode.ElideRight,
        available_width,
    )
    if elided != text:
        widget.setToolTip(text)
