"""Regression checks for locale-resilient PySide6 layouts."""

from PySide6.QtWidgets import QApplication, QLabel, QStyle

from src.ui.i18n_manager import I18nManager


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _set_test_language(language: str) -> None:
    manager = I18nManager.instance()
    manager._current_language = language
    manager._load_translations(language)


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


def test_chat_header_and_attachment_controls_use_translated_flexible_labels():
    from src.ui.chat.chat_panel import ChatPanel

    _application()
    _set_test_language("en")
    panel = ChatPanel()

    assert panel._artifacts_btn.text() == "Artifacts"
    assert panel._image_btn.maximumWidth() > panel._image_btn.minimumWidth()
    assert panel._audio_btn.maximumWidth() > panel._audio_btn.minimumWidth()
    assert panel._video_btn.maximumWidth() > panel._video_btn.minimumWidth()


def test_navigation_item_renders_a_qt_icon_without_emoji_text():
    from src.ui.navigation_rail import NavigationRail

    application = _application()
    rail = NavigationRail()
    icon = application.style().standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon)

    rail.add_item("home", "Home", icon)

    icon_label = rail._items["home"]._icon_label
    assert icon_label.text() == ""
    assert not icon_label.pixmap().isNull()


def test_home_quick_actions_use_qt_icons_and_wrapping_descriptions():
    from src.ui.home_page import HomePage

    _application()
    home = HomePage()
    card = home._quick_action_cards[0]

    assert card._icon_label.text() == ""
    assert not card._icon_label.pixmap().isNull()
    assert card._desc_label.wordWrap() is True
