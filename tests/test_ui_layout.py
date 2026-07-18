"""Regression checks for locale-resilient PySide6 layouts."""

import pytest
from PySide6.QtCore import Qt
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


def test_navigation_rail_uses_a_stable_theme_selector():
    from src.ui.navigation_rail import NavigationRail
    from src.ui.theme import Theme

    _application()
    rail = NavigationRail()

    assert rail.objectName() == "navigationRail"
    assert rail.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert "QWidget#navigationRail" in Theme.get_navigation_rail_stylesheet()


def test_home_quick_actions_use_qt_icons_and_wrapping_descriptions():
    from src.ui.home_page import HomePage

    _application()
    home = HomePage()
    card = home._quick_action_cards[0]

    assert card._icon_label.text() == ""
    assert not card._icon_label.pixmap().isNull()
    assert card._desc_label.wordWrap() is True


@pytest.mark.parametrize(
    "dialog_factory",
    [
        "src.ui.plugins.plugin_panel.PluginInstallDialog",
        "src.ui.plugins.plugin_panel.PluginLocalInstallDialog",
        "src.ui.packages.package_panel.InstallDialog",
        "src.ui.packages.package_panel.LocalInstallDialog",
    ],
)
def test_install_dialogs_keep_text_layout_flexible(dialog_factory):
    import importlib

    _application()
    module_name, class_name = dialog_factory.rsplit(".", 1)
    dialog = getattr(importlib.import_module(module_name), class_name)()

    assert dialog.minimumWidth() >= 450
    assert dialog.maximumWidth() > dialog.minimumWidth()


def test_management_cards_keep_long_descriptions_readable():
    from src.ui.packages.package_panel import PackageItemWidget
    from src.ui.plugins.plugin_panel import PluginItemWidget

    _application()
    description = (
        "A deliberately long localized description that must remain readable "
        "in the management list."
    )
    plugin = PluginItemWidget("demo", {"description": description})
    package = PackageItemWidget({"id": "demo", "description": description})

    assert plugin._desc_label.text() == description
    assert plugin._desc_label.wordWrap() is True
    assert package._desc_label.text() == description
    assert package._desc_label.wordWrap() is True


@pytest.mark.parametrize("locale", ["zh_CN", "en"])
def test_main_window_primary_labels_fit_or_wrap_at_minimum_size(locale):
    from src.ui.chat.chat_panel import ChatPanel
    from src.ui.home_page import HomePage
    from src.ui.navigation_rail import NavigationRail

    application = _application()
    _set_test_language(locale)
    navigation = NavigationRail()
    navigation.resize(200, 600)
    home = HomePage()
    home.resize(600, 600)
    chat = ChatPanel()
    chat.resize(600, 600)
    navigation.show()
    home.show()
    chat.show()
    application.processEvents()

    labels = [
        navigation._title_label,
        chat._title_label,
        chat._status_label,
        home._title_label,
        home._subtitle_label,
    ]
    for label in labels:
        text_width = label.fontMetrics().horizontalAdvance(label.text())
        text_fits = text_width <= label.contentsRect().width()
        assert text_fits or label.wordWrap() or label.toolTip() == label.text()
