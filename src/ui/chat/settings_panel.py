from typing import Optional, List, Dict
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QFileDialog,
)
from src.ui.theme import Theme
from src.ui.i18n_manager import _
from src.agent.api_key_manager import ApiKeyManager
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class EditApiKeyDialog(QDialog):
    def __init__(
        self,
        provider: str,
        model_name: Optional[str],
        api_key_manager: ApiKeyManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._provider = provider
        self._model_name = model_name
        self._manager = api_key_manager
        display_name = f"{provider}/{model_name}" if model_name else provider
        self.setWindowTitle(f'{_("chat_settings.edit_api_key")}: {display_name}')
        self.setModal(True)
        self.resize(450, 250)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QFormLayout(self)

        self._provider_label = QLabel(self._provider)
        layout.addRow(_("chat_settings.provider") + ":", self._provider_label)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(_("chat_settings.enter_new_api_key_optional"))
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(_("chat_settings.api_key") + ":", self._key_input)

        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText(_("chat_settings.enter_base_url_optional"))
        layout.addRow(_("chat_settings.base_url") + ":", self._base_url_input)

        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText(_("chat_settings.enter_model_optional"))
        layout.addRow(_("chat_settings.model_name") + ":", self._model_input)

        # Modal types selection
        self._modal_group = QWidget()
        modal_layout = QHBoxLayout(self._modal_group)
        modal_layout.setContentsMargins(0, 0, 0, 0)
        modal_layout.setSpacing(12)

        self._text_cb = QCheckBox(_("chat_settings.text"))
        self._text_cb.setChecked(True)
        self._text_cb.setEnabled(False)

        self._image_cb = QCheckBox(_("chat_settings.image"))
        self._audio_cb = QCheckBox(_("chat_settings.audio"))
        self._video_cb = QCheckBox(_("chat_settings.video"))

        modal_layout.addWidget(self._text_cb)
        modal_layout.addWidget(self._image_cb)
        modal_layout.addWidget(self._audio_cb)
        modal_layout.addWidget(self._video_cb)
        modal_layout.addStretch()

        layout.addRow(_("chat_settings.supported_types") + ":", self._modal_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())

    def _load_data(self):
        config = self._manager.get_config(self._provider, self._model_name)
        if config:
            if config.get("base_url"):
                self._base_url_input.setText(config["base_url"])
            if config.get("model_name"):
                self._model_input.setText(config["model_name"])

            # Load supported types
            supported_types = config.get("supported_types", ["text"])
            self._image_cb.setChecked("image" in supported_types)
            self._audio_cb.setChecked("audio" in supported_types)
            self._video_cb.setChecked("video" in supported_types)

    def get_values(self) -> tuple[str | None, str | None, str | None, List[str]]:
        """Get dialog values including supported modal types.

        Returns:
            Tuple of (api_key, base_url, model_name, supported_types)
        """
        # Build supported_types list
        supported_types = ["text"]
        if self._image_cb.isChecked():
            supported_types.append("image")
        if self._audio_cb.isChecked():
            supported_types.append("audio")
        if self._video_cb.isChecked():
            supported_types.append("video")

        return (
            self._key_input.text().strip() or None,
            self._base_url_input.text().strip() or None,
            self._model_input.text().strip() or None,
            supported_types,
        )


# 支持的服务商列表
SUPPORTED_PROVIDERS = [
    ("openai", "OpenAI", "https://api.openai.com/v1"),
    ("anthropic", "Anthropic", "https://api.anthropic.com"),
    ("dashscope", "阿里云DashScope (通义千问)", "https://dashscope.aliyuncs.com/v1"),
    ("deepseek", "DeepSeek (深度求索)", "https://api.deepseek.com"),
    ("moonshot", "Moonshot (月之暗面)", "https://api.moonshot.cn/v1"),
    ("zhipu", "智谱AI (GLM)", "https://open.bigmodel.cn/api/paas/v3"),
    ("qwen", "通义千问 (Qwen)", "https://dashscope.aliyuncs.com/v1"),
]


class AddApiKeyDialog(QDialog):
    """添加API密钥对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(_("chat_settings.add_api_key"))
        self.setModal(True)
        self.resize(450, 280)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        # 服务商下拉选择
        self._provider_combo = QComboBox()
        self._provider_combo.addItems([p[1] for p in SUPPORTED_PROVIDERS])
        self._provider_combo.setCurrentIndex(0)
        layout.addRow(_("chat_settings.provider") + ":", self._provider_combo)

        # API密钥输入（带显示/隐藏切换）
        key_layout = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(_("chat_settings.enter_api_key"))
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)

        self._toggle_key_btn = QPushButton()
        self._toggle_key_btn.setText("👁")
        self._toggle_key_btn.setCheckable(False)
        self._toggle_key_btn.setFixedWidth(30)
        self._toggle_key_btn.clicked.connect(self._toggle_password_visibility)
        key_layout.addWidget(self._key_input)
        key_layout.addWidget(self._toggle_key_btn)
        layout.addRow(_("chat_settings.api_key") + ":", key_layout)

        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText(_("chat_settings.enter_base_url_optional"))
        layout.addRow(_("chat_settings.base_url") + ":", self._base_url_input)

        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText(_("chat_settings.enter_model_optional"))
        layout.addRow(_("chat_settings.model_name") + ":", self._model_input)

        # Modal types selection
        self._modal_group = QWidget()
        modal_layout = QHBoxLayout(self._modal_group)
        modal_layout.setContentsMargins(0, 0, 0, 0)
        modal_layout.setSpacing(12)

        self._text_cb = QCheckBox(_("chat_settings.text"))
        self._text_cb.setChecked(True)
        self._text_cb.setEnabled(False)  # Text always required
        self._text_cb.setToolTip(_("chat_settings.text_required"))

        self._image_cb = QCheckBox(_("chat_settings.image"))
        self._image_cb.setToolTip(_("chat_settings.image_support"))

        self._audio_cb = QCheckBox(_("chat_settings.audio"))
        self._audio_cb.setToolTip(_("chat_settings.audio_support"))

        self._video_cb = QCheckBox(_("chat_settings.video"))
        self._video_cb.setToolTip(_("chat_settings.video_support"))

        modal_layout.addWidget(self._text_cb)
        modal_layout.addWidget(self._image_cb)
        modal_layout.addWidget(self._audio_cb)
        modal_layout.addWidget(self._video_cb)
        modal_layout.addStretch()

        layout.addRow(_("chat_settings.supported_types") + ":", self._modal_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())

    def _toggle_password_visibility(self):
        if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_key_btn.setText("🔒")
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_key_btn.setText("👁")

    def get_values(self) -> tuple[str, str, str | None, str | None, List[str]]:
        """Get dialog values including supported modal types.

        Returns:
            Tuple of (provider, api_key, base_url, model_name, supported_types)
        """
        idx = self._provider_combo.currentIndex()
        provider = SUPPORTED_PROVIDERS[idx][0] if idx >= 0 else ""
        key = self._key_input.text().strip()

        # Build supported_types list
        supported_types = ["text"]
        if self._image_cb.isChecked():
            supported_types.append("image")
        if self._audio_cb.isChecked():
            supported_types.append("audio")
        if self._video_cb.isChecked():
            supported_types.append("video")

        return (
            provider,
            key,
            self._base_url_input.text().strip() or None,
            self._model_input.text().strip() or None,
            supported_types,
        )


class ApiKeyPanel(QWidget):
    """API密钥管理面板"""

    key_added = Signal(str, str)
    key_deleted = Signal(str)
    key_toggled = Signal(str, bool)
    key_modified = Signal(str)

    def __init__(self, api_key_manager: ApiKeyManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = api_key_manager
        self._setup_ui()
        self._load_keys()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(_("chat_settings.api_key_management"))
        title.setStyleSheet(Theme.get_title_label_stylesheet())
        layout.addWidget(title)

        self._key_list = QListWidget()
        self._key_list.setStyleSheet(Theme.get_list_widget_stylesheet())
        layout.addWidget(self._key_list, 1)

        button_layout = QHBoxLayout()

        add_btn = QPushButton(_("chat_settings.add"))
        add_btn.clicked.connect(self._add_key)
        add_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        edit_btn = QPushButton(_("chat_settings.edit"))
        edit_btn.clicked.connect(self._edit_key)
        edit_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        delete_btn = QPushButton(_("chat_settings.delete"))
        delete_btn.clicked.connect(self._delete_key)
        delete_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        toggle_btn = QPushButton(_("chat_settings.enable_disable"))
        toggle_btn.clicked.connect(self._toggle_key)
        toggle_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        button_layout.addWidget(add_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(toggle_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

    def _load_keys(self):
        self._key_list.clear()
        configs = self._manager.list_all_configs()
        for config in configs:
            status = "✓" if config["enabled"] else "✗"
            item_text = f"{status} {config['provider']}"
            if config.get("model_name"):
                item_text += f" ({config['model_name']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, config)
            self._key_list.addItem(item)

    def _add_key(self):
        dialog = AddApiKeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            provider, key, base_url, model_name, supported_types = dialog.get_values()
            if not provider or not key:
                QMessageBox.warning(self, _("chat_settings.input_error"), _("chat_settings.please_enter_provider_and_key"))
                return

            try:
                self._manager.store_key(
                    provider,
                    key,
                    base_url=base_url,
                    model_name=model_name,
                    supported_types=supported_types,
                )
                self._load_keys()
                self.key_added.emit(provider, "***")
                _logger.info(
                    f"添加API密钥: {provider}/{model_name or 'default'}, "
                    f"支持类型: {supported_types}"
                )
                QMessageBox.information(self, _("chat_settings.success"), _("chat_settings.api_key_added").format(provider=provider))
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.add_failed") + f": {e}")

    def _edit_key(self):
        current_item = self._key_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, _("chat_settings.input_error"), _("chat_settings.please_select_item"))
            return

        config = current_item.data(Qt.ItemDataRole.UserRole)
        provider = config["provider"]
        model_name = config.get("model_name")

        dialog = EditApiKeyDialog(provider, model_name, self._manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_key, new_base_url, model_name_new, supported_types = dialog.get_values()
            try:
                if new_key:
                    self._manager.store_key(
                        provider,
                        new_key,
                        base_url=new_base_url,
                        model_name=model_name,
                        supported_types=supported_types,
                    )
                else:
                    if new_base_url or model_name_new:
                        update_kwargs = {}
                        if new_base_url:
                            update_kwargs["base_url"] = new_base_url
                        if model_name_new:
                            update_kwargs["model_name"] = model_name_new
                        self._manager.update_config(
                            provider,
                            model_name=model_name,
                            **update_kwargs,
                        )
                    self._manager.update_supported_types(
                        provider,
                        supported_types,
                        model_name=model_name,
                    )

                self._load_keys()
                self.key_modified.emit(provider)
                _logger.info(
                    f"更新API密钥: {provider}/{model_name or 'default'}, "
                    f"支持类型: {supported_types}"
                )
                display_name = f"{provider}/{model_name_new or model_name or 'default'}"
                QMessageBox.information(self, _("chat_settings.success"), _("chat_settings.api_key_updated").format(display_name=display_name))
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.update_failed") + f": {e}")

    def _delete_key(self):
        current_item = self._key_list.currentItem()
        if current_item:
            config = current_item.data(Qt.ItemDataRole.UserRole)
            provider = config["provider"]
            model_name = config.get("model_name")
            display_name = f"{provider}/{model_name}" if model_name else provider
            reply = QMessageBox.question(
                self,
                _("chat_settings.confirm_delete"),
                _("chat_settings.confirm_delete_api_key").format(display_name=display_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._manager.delete_key(provider, model_name)
                    self._load_keys()
                    self.key_deleted.emit(provider)
                except Exception as e:
                    QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.delete_failed") + f": {e}")

    def _toggle_key(self):
        current_item = self._key_list.currentItem()
        if current_item:
            config = current_item.data(Qt.ItemDataRole.UserRole)
            provider = config["provider"]
            model_name = config.get("model_name")
            new_enabled = not config["enabled"]
            try:
                self._manager.set_enabled(provider, new_enabled, model_name)
                self._load_keys()
                display_name = f"{provider}/{model_name}" if model_name else provider
                self.key_toggled.emit(provider, new_enabled)
                status = _("chat_settings.enabled") if new_enabled else _("chat_settings.disabled")
                QMessageBox.information(self, _("chat_settings.success"), f"{status} {display_name}")
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.operation_failed") + f": {e}")


class AddSkillDialog(QDialog):
    """添加Skill对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(_("chat_settings.add_skill"))
        self.setModal(True)
        self.resize(450, 200)
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText(_("chat_settings.skill_name"))
        layout.addRow(_("chat_settings.skill_name") + ":", self._name_input)

        path_layout = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText(_("chat_settings.skill_path"))
        browse_btn = QPushButton(_("chat_settings.browse"))
        browse_btn.clicked.connect(self._browse_directory)
        path_layout.addWidget(self._path_input)
        path_layout.addWidget(browse_btn)
        layout.addRow(_("chat_settings.skill_path") + ":", path_layout)

        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText(_("chat_settings.description") + " (" + _("chat_settings.optional") + ")")
        layout.addRow(_("chat_settings.description") + ":", self._desc_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[str, str, Optional[str]]:
        return (
            self._name_input.text().strip(),
            self._path_input.text().strip(),
            self._desc_input.text().strip() or None,
        )

    def _browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, _("chat_settings.choose_skill_dir"))
        if directory:
            self._path_input.setText(directory)


class EditSkillDialog(QDialog):
    """编辑Skill对话框"""

    def __init__(self, name: str, skill_manager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._name = name
        self._manager = skill_manager
        self.setWindowTitle(f'{_("chat_settings.edit_skill")}: {name}')
        self.setModal(True)
        self.resize(450, 200)
        self._setup_ui()
        self._load_data()

        self._password_visible = True

    def _setup_ui(self):
        layout = QFormLayout(self)

        self._name_label = QLabel(self._name)
        layout.addRow(_("chat_settings.skill_name") + ":", self._name_label)

        path_layout = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText(_("chat_settings.skill_path"))
        browse_btn = QPushButton(_("chat_settings.browse"))
        browse_btn.clicked.connect(self._browse_directory)
        path_layout.addWidget(self._path_input)
        path_layout.addWidget(browse_btn)
        layout.addRow(_("chat_settings.skill_path") + ":", path_layout)

        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText(_("chat_settings.description") + " (" + _("chat_settings.optional") + ")")
        layout.addRow(_("chat_settings.description") + ":", self._desc_input)

        self._password_visible = False

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())

    def _browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, _("chat_settings.choose_skill_dir"))
        if directory:
            self._path_input.setText(directory)

            self._password_visible = True

    def _load_data(self):
        skill = self._manager.get_skill(self._name)
        if skill:
            if skill.get("path"):
                self._path_input.setText(skill["path"])
            if skill.get("description"):
                self._desc_input.setText(skill["description"])
            self._password_visible = True

    def get_values(self) -> tuple[str | None, str | None]:
        return (
            self._path_input.text().strip() or None,
            self._desc_input.text().strip() or None,
        )


class SkillPanel(QWidget):
    """Skill管理面板"""

    skill_added = Signal(str)
    skill_deleted = Signal(str)
    skill_toggled = Signal(str, bool)

    def __init__(self, skill_manager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = skill_manager
        self._setup_ui()
        self._load_skills()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(_("chat_settings.skill_management"))
        title.setStyleSheet(Theme.get_title_label_stylesheet())
        layout.addWidget(title)

        self._skill_list = QListWidget()
        self._skill_list.setStyleSheet(Theme.get_list_widget_stylesheet())
        layout.addWidget(self._skill_list, 1)

        button_layout = QHBoxLayout()

        add_btn = QPushButton(_("chat_settings.add"))
        add_btn.clicked.connect(self._add_skill)
        add_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        edit_btn = QPushButton(_("chat_settings.edit"))
        edit_btn.clicked.connect(self._edit_skill)
        edit_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        delete_btn = QPushButton(_("chat_settings.delete"))
        delete_btn.clicked.connect(self._delete_skill)
        delete_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        toggle_btn = QPushButton(_("chat_settings.enable_disable"))
        toggle_btn.clicked.connect(self._toggle_skill)
        toggle_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        button_layout.addWidget(add_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(toggle_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

    def _load_skills(self):
        self._skill_list.clear()
        skills = self._manager.list_skills()
        for skill in skills:
            status = "✓" if skill["enabled"] else "✗"
            item_text = f"{status} {skill['name']}"
            if skill.get("description"):
                item_text += f" - {skill['description'][:30]}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, skill)
            self._skill_list.addItem(item)

    def _add_skill(self):
        dialog = AddSkillDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, path, description = dialog.get_values()
            if name and path:
                try:
                    self._manager.add_skill(name, path, description)
                    self._load_skills()
                    self.skill_added.emit(name)
                    QMessageBox.information(self, _("chat_settings.success"), _("chat_settings.skill_added").format(name=name))
                except Exception as e:
                    QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.add_failed") + f": {e}")

    def _edit_skill(self):
        current_item = self._skill_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, _("chat_settings.input_error"), _("chat_settings.please_select_item"))
            return

        skill = current_item.data(Qt.ItemDataRole.UserRole)
        name = skill["name"]

        dialog = EditSkillDialog(name, self._manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_path, new_description = dialog.get_values()
            try:
                self._manager.update_skill(name, path=new_path, description=new_description)
                self._load_skills()
                QMessageBox.information(self, _("chat_settings.success"), _("chat_settings.skill_updated").format(name=name))
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.update_failed") + f": {e}")

    def _delete_skill(self):
        current_item = self._skill_list.currentItem()
        if current_item:
            skill = current_item.data(Qt.ItemDataRole.UserRole)
            name = skill["name"]
            reply = QMessageBox.question(
                self,
                _("chat_settings.confirm_delete"),
                _("chat_settings.confirm_delete_skill").format(name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._manager.delete_skill(name)
                    self._load_skills()
                    self.skill_deleted.emit(name)
                except Exception as e:
                    QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.delete_failed") + f": {e}")

    def _toggle_skill(self):
        current_item = self._skill_list.currentItem()
        if current_item:
            skill = current_item.data(Qt.ItemDataRole.UserRole)
            name = skill["name"]
            new_enabled = not skill["enabled"]
            try:
                self._manager.set_enabled(name, new_enabled)
                self._load_skills()
                self.skill_toggled.emit(name, new_enabled)
                status = _("chat_settings.enabled") if new_enabled else _("chat_settings.disabled")
                QMessageBox.information(self, _("chat_settings.success"), f"{status} Skill: {name}")
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.operation_failed") + f": {e}")


class AddMcpServerDialog(QDialog):
    """添加MCP服务器对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(_("chat_settings.add_mcp_server"))
        self.setModal(True)
        self.resize(500, 350)
        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText(_("chat_settings.server_name"))
        form_layout.addRow(_("chat_settings.server_name") + ":", self._name_input)

        self._type_combo = QComboBox()
        self._type_combo.addItems([_("chat_settings.stdio_local"), _("chat_settings.http_remote")])
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        form_layout.addRow(_("chat_settings.server_type") + ":", self._type_combo)

        layout.addLayout(form_layout)

        self._stdio_widget = QWidget()
        stdio_layout = QFormLayout(self._stdio_widget)

        self._command_input = QLineEdit()
        self._command_input.setPlaceholderText(_("chat_settings.command") + ": python")
        stdio_layout.addRow(_("chat_settings.command") + ":", self._command_input)

        self._args_input = QLineEdit()
        self._args_input.setPlaceholderText(f"{_('chat_settings.example')}: [\"-m\", \"server\"] {_('chat_settings.json_array')}")
        stdio_layout.addRow(_("chat_settings.args") + ":", self._args_input)

        self._env_input = QLineEdit()
        self._env_input.setPlaceholderText(f"{_('chat_settings.example')}: {{\"DEBUG\": \"1\"}} {_('chat_settings.json_object')}")
        stdio_layout.addRow(_("chat_settings.env_vars") + ":", self._env_input)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 300)
        self._timeout_spin.setValue(30)
        stdio_layout.addRow(_("chat_settings.timeout_seconds") + ":", self._timeout_spin)

        layout.addWidget(self._stdio_widget)

        self._http_widget = QWidget()
        http_layout = QFormLayout(self._http_widget)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(f"{_('chat_settings.example')}: https://api.example.com/mcp")
        http_layout.addRow(_("chat_settings.url") + ":", self._url_input)

        self._transport_combo = QComboBox()
        self._transport_combo.addItems(["streamable_http", "sse"])
        http_layout.addRow(_("chat_settings.transport") + ":", self._transport_combo)

        self._http_widget.hide()
        layout.addWidget(self._http_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_type_changed(0)

    def _on_type_changed(self, index: int):
        if index == 0:
            self._stdio_widget.show()
            self._http_widget.hide()
        else:
            self._stdio_widget.hide()
            self._http_widget.show()

    def get_values(self) -> dict:
        result = {
            "name": self._name_input.text().strip(),
            "server_type": "stdio" if self._type_combo.currentIndex() == 0 else "http",
        }

        if result["server_type"] == "stdio":
            result["command"] = self._command_input.text().strip()
            args_text = self._args_input.text().strip()
            result["args"] = args_text if args_text else "[]"
            env_text = self._env_input.text().strip()
            result["env"] = env_text if env_text else "{}"
            result["timeout"] = self._timeout_spin.value()
        else:
            result["url"] = self._url_input.text().strip()
            result["transport"] = self._transport_combo.currentText()

        return result


class EditMcpServerDialog(QDialog):
    """编辑MCP服务器对话框"""

    def __init__(self, name: str, mcp_manager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._name = name
        self._manager = mcp_manager
        self.setWindowTitle(f'{_("chat_settings.edit_mcp_server")}: {name}')
        self.setModal(True)
        self.resize(500, 350)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self._name_label = QLabel(self._name)
        form_layout.addRow(_("chat_settings.server_name") + ":", self._name_label)

        self._type_label = QLabel()
        form_layout.addRow(_("chat_settings.server_type") + ":", self._type_label)

        layout.addLayout(form_layout)

        self._stdio_widget = QWidget()
        stdio_layout = QFormLayout(self._stdio_widget)

        self._command_input = QLineEdit()
        self._command_input.setPlaceholderText(_("chat_settings.command") + ": python")
        stdio_layout.addRow(_("chat_settings.command") + ":", self._command_input)

        self._args_input = QLineEdit()
        self._args_input.setPlaceholderText(f"{_('chat_settings.example')}: [\"-m\", \"server\"] {_('chat_settings.json_array')}")
        stdio_layout.addRow(_("chat_settings.args") + ":", self._args_input)

        self._env_input = QLineEdit()
        self._env_input.setPlaceholderText(f"{_('chat_settings.example')}: {{\"DEBUG\": \"1\"}} {_('chat_settings.json_object')}")
        stdio_layout.addRow(_("chat_settings.env_vars") + ":", self._env_input)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 300)
        self._timeout_spin.setValue(30)
        stdio_layout.addRow(_("chat_settings.timeout_seconds") + ":", self._timeout_spin)

        layout.addWidget(self._stdio_widget)

        self._http_widget = QWidget()
        http_layout = QFormLayout(self._http_widget)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText(f"{_('chat_settings.example')}: https://api.example.com/mcp")
        http_layout.addRow(_("chat_settings.url") + ":", self._url_input)

        self._transport_combo = QComboBox()
        self._transport_combo.addItems(["streamable_http", "sse"])
        http_layout.addRow(_("chat_settings.transport") + ":", self._transport_combo)

        self._http_widget.hide()
        layout.addWidget(self._http_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(Theme.get_settings_dialog_stylesheet())

    def _load_data(self):
        server = self._manager.get_server(self._name)
        if not server:
            return

        server_type = server.get("server_type", "stdio")
        self._type_label.setText(f"{server_type} ({_('chat_settings.local') if server_type == 'stdio' else _('chat_settings.remote')})")

        if server_type == "stdio":
            self._stdio_widget.show()
            self._http_widget.hide()
            if server.get("command"):
                self._command_input.setText(server["command"])
            if server.get("args"):
                import json

                self._args_input.setText(json.dumps(server["args"]))
            if server.get("env"):
                import json

                self._env_input.setText(json.dumps(server["env"]))
            if server.get("timeout"):
                self._timeout_spin.setValue(server["timeout"])
        else:
            self._stdio_widget.hide()
            self._http_widget.show()
            if server.get("url"):
                self._url_input.setText(server["url"])
            if server.get("transport"):
                idx = self._transport_combo.findText(server["transport"])
                if idx >= 0:
                    self._transport_combo.setCurrentIndex(idx)

    def get_values(self) -> dict:
        result = {
            "name": self._name,
            "server_type": "stdio" if self._stdio_widget.isVisible() else "http",
        }

        if result["server_type"] == "stdio":
            result["command"] = self._command_input.text().strip()
            args_text = self._args_input.text().strip()
            result["args"] = args_text if args_text else "[]"
            env_text = self._env_input.text().strip()
            result["env"] = env_text if env_text else "{}"
            result["timeout"] = self._timeout_spin.value()
        else:
            result["url"] = self._url_input.text().strip()
            result["transport"] = self._transport_combo.currentText()

        return result


class McpPanel(QWidget):
    """MCP服务管理面板"""

    server_added = Signal(str)
    server_deleted = Signal(str)
    server_toggled = Signal(str, bool)

    def __init__(self, mcp_manager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = mcp_manager
        self._setup_ui()
        self._load_servers()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(_("chat_settings.mcp_management"))
        title.setStyleSheet(Theme.get_title_label_stylesheet())
        layout.addWidget(title)

        self._server_list = QListWidget()
        self._server_list.setStyleSheet(Theme.get_list_widget_stylesheet())
        layout.addWidget(self._server_list, 1)

        button_layout = QHBoxLayout()

        add_btn = QPushButton(_("chat_settings.add"))
        add_btn.clicked.connect(self._add_server)
        add_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        edit_btn = QPushButton(_("chat_settings.edit"))
        edit_btn.clicked.connect(self._edit_server)
        edit_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        delete_btn = QPushButton(_("chat_settings.delete"))
        delete_btn.clicked.connect(self._delete_server)
        delete_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        toggle_btn = QPushButton(_("chat_settings.enable_disable"))
        toggle_btn.clicked.connect(self._toggle_server)
        toggle_btn.setStyleSheet(Theme.get_panel_button_stylesheet())

        button_layout.addWidget(add_btn)
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(toggle_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

    def _load_servers(self):
        self._server_list.clear()
        servers = self._manager.list_servers()
        for server in servers:
            status = "✓" if server["enabled"] else "✗"
            server_type = server["server_type"]
            item_text = f"{status} [{server_type}] {server['name']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, server)
            self._server_list.addItem(item)

    def _add_server(self):
        dialog = AddMcpServerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.get_values()
            name = values.get("name")
            if not name:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.enter_server_name"))
                return

            try:
                if values["server_type"] == "stdio":
                    import json

                    args = json.loads(values["args"]) if values["args"] else []
                    env = json.loads(values["env"]) if values["env"] else {}
                    self._manager.add_stdio_server(
                        name=name,
                        command=values["command"],
                        args=args,
                        env=env,
                        timeout=values["timeout"],
                    )
                else:
                    self._manager.add_http_server(
                        name=name,
                        url=values["url"],
                        transport=values["transport"],
                    )
                self._load_servers()
                self.server_added.emit(name)
                QMessageBox.information(self, _("chat_settings.success"), _("chat_settings.mcp_server_added").format(name=name))
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.add_failed") + f": {e}")

    def _edit_server(self):
        current_item = self._server_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, _("chat_settings.input_error"), _("chat_settings.please_select_item"))
            return

        server = current_item.data(Qt.ItemDataRole.UserRole)
        name = server["name"]

        dialog = EditMcpServerDialog(name, self._manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.get_values()
            try:
                import json

                if values["server_type"] == "stdio":
                    args = json.loads(values["args"]) if values["args"] else []
                    env = json.loads(values["env"]) if values["env"] else {}
                    self._manager.update_stdio_server(
                        name=name,
                        command=values["command"],
                        args=args,
                        env=env,
                        timeout=values["timeout"],
                    )
                else:
                    self._manager.update_http_server(
                        name=name,
                        url=values["url"],
                        transport=values["transport"],
                    )
                self._load_servers()
                QMessageBox.information(self, _("chat_settings.success"), _("chat_settings.mcp_server_updated").format(name=name))
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.update_failed") + f": {e}")

    def _delete_server(self):
        current_item = self._server_list.currentItem()
        if current_item:
            server = current_item.data(Qt.ItemDataRole.UserRole)
            name = server["name"]
            reply = QMessageBox.question(
                self,
                _("chat_settings.confirm_delete"),
                _("chat_settings.confirm_delete_mcp_server").format(name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._manager.delete_server(name)
                    self._load_servers()
                    self.server_deleted.emit(name)
                except Exception as e:
                    QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.delete_failed") + f": {e}")

    def _toggle_server(self):
        current_item = self._server_list.currentItem()
        if current_item:
            server = current_item.data(Qt.ItemDataRole.UserRole)
            name = server["name"]
            new_enabled = not server["enabled"]
            try:
                self._manager.set_enabled(name, new_enabled)
                self._load_servers()
                self.server_toggled.emit(name, new_enabled)
                status = _("chat_settings.enabled") if new_enabled else _("chat_settings.disabled")
                QMessageBox.information(self, _("chat_settings.success"), f"{status} {_('chat_settings.mcp_tab')}: {name}")
            except Exception as e:
                QMessageBox.warning(self, _("chat_settings.error"), _("chat_settings.operation_failed") + f": {e}")


class AgentSettingsDialog(QDialog):
    """AI助手设置对话框"""

    def __init__(
        self,
        api_key_manager: ApiKeyManager,
        mcp_manager=None,
        skill_manager=None,
        on_api_key_changed=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(_("chat_settings.agent_settings"))
        self.setModal(True)
        self.resize(650, 550)
        self._api_key_manager = api_key_manager
        self._mcp_manager = mcp_manager
        self._skill_manager = skill_manager
        self._on_api_key_changed = on_api_key_changed
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(Theme.get_node_tree_stylesheet())

        self._api_key_panel = ApiKeyPanel(self._api_key_manager)
        self._tabs.addTab(self._api_key_panel, _("chat_settings.api_key_tab"))

        if self._on_api_key_changed:
            self._api_key_panel.key_added.connect(lambda p, k: self._on_api_key_changed())
            self._api_key_panel.key_deleted.connect(lambda p: self._on_api_key_changed())
            self._api_key_panel.key_toggled.connect(lambda p, e: self._on_api_key_changed())
            self._api_key_panel.key_modified.connect(lambda p: self._on_api_key_changed())

        if self._skill_manager:
            self._skill_panel = SkillPanel(self._skill_manager)
            self._tabs.addTab(self._skill_panel, _("chat_settings.skills_tab"))

        if self._mcp_manager:
            self._mcp_panel = McpPanel(self._mcp_manager)
            self._tabs.addTab(self._mcp_panel, _("chat_settings.mcp_tab"))

        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
