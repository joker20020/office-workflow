# -*- coding: utf-8 -*-
"""
国际化 (i18n) 管理器模块

提供运行时语言切换功能，支持信号通知。

使用方式：
    from src.ui.i18n_manager import I18nManager, _

    # 获取单例实例
    manager = I18nManager.instance()

    # 切换语言
    manager.apply_language("en")

    # 翻译文本
    label.setText(_("app.title"))

    # 连接信号
    manager.language_changed.connect(lambda lang: print(f"语言已切换为: {lang}"))
"""

from typing import Any, Optional, Dict
from pathlib import Path

import yaml
from PySide6.QtCore import QObject, Signal

from src.core.config_manager import get_config_manager
from src.utils.logger import get_logger

_logger = get_logger(__name__)

DEFAULT_LANGUAGE = "zh_CN"

_TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "translations"


class I18nManager(QObject):
    """
    国际化管理器

    管理翻译文件加载和运行时语言切换，提供：
    - 单例模式访问
    - 运行时语言切换
    - 语言变更信号通知
    - 配置持久化

    Attributes:
        language_changed: 语言变更信号，参数为新语言代码
    """

    language_changed = Signal(str)

    _instance: Optional["I18nManager"] = None

    @classmethod
    def instance(cls) -> "I18nManager":
        """
        获取单例实例

        Returns:
            I18nManager 实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """
        初始化国际化管理器

        从 ConfigManager 加载当前语言并加载翻译文件
        """
        super().__init__()
        config = get_config_manager()
        lang = config.get("language", DEFAULT_LANGUAGE)
        self._current_language = lang
        self._translations: Dict[str, str] = {}
        self._load_translations(lang)

    def _load_translations(self, language: str) -> None:
        """
        加载指定语言的翻译文件

        Args:
            language: 语言代码 (如 "zh_CN" 或 "en")
        """
        self._translations = {}
        file_path = _TRANSLATIONS_DIR / f"{language}.yaml"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    self._translations = self._flatten_dict(data)
                _logger.info(f"翻译文件加载成功: {file_path}")
            except Exception as e:
                _logger.error(f"翻译文件加载失败: {e}")
        else:
            _logger.warning(f"翻译文件不存在: {file_path}")

    @staticmethod
    def _flatten_dict(nested: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
        """
        将嵌套字典扁平化为点分键名

        Args:
            nested: 嵌套字典
            prefix: 键名前缀

        Returns:
            扁平化的字典
        """
        items: Dict[str, str] = {}
        for key, value in nested.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                items.update(I18nManager._flatten_dict(value, full_key))
            else:
                items[full_key] = str(value)
        return items

    def apply_language(self, language: str) -> None:
        """
        应用指定语言

        更新翻译数据、保存到配置、发射信号

        Args:
            language: 语言代码 (如 "zh_CN" 或 "en")
        """
        if language not in self.get_available_languages():
            _logger.warning(f"不支持的语言: {language}")
            return

        if self._current_language == language:
            return

        self._current_language = language
        self._load_translations(language)

        config = get_config_manager()
        config.set("language", language)
        config.save()

        self.language_changed.emit(language)
        _logger.info(f"语言已切换为: {language}")

    def get_current_language(self) -> str:
        """
        获取当前语言代码

        Returns:
            当前语言代码
        """
        return self._current_language

    def get_available_languages(self) -> list[str]:
        """
        获取可用语言列表

        Returns:
            可用语言代码列表
        """
        languages = []
        if _TRANSLATIONS_DIR.exists():
            for f in _TRANSLATIONS_DIR.iterdir():
                if f.suffix in (".yaml", ".yml"):
                    languages.append(f.stem)
        if DEFAULT_LANGUAGE not in languages:
            languages.append(DEFAULT_LANGUAGE)
        return sorted(languages)

    def translate(self, key: str, default: Optional[str] = None) -> str:
        """
        获取指定键的翻译文本

        如果当前语言下找不到翻译，且当前语言不是默认语言，
        会尝试回退到默认语言。

        Args:
            key: 翻译键名
            default: 找不到翻译时的默认返回值，默认为键名本身

        Returns:
            翻译后的文本
        """
        if key in self._translations:
            return self._translations[key]

        # 尝试从默认语言回退
        if self._current_language != DEFAULT_LANGUAGE:
            # 临时加载默认语言翻译
            fallback_path = _TRANSLATIONS_DIR / f"{DEFAULT_LANGUAGE}.yaml"
            if fallback_path.exists():
                try:
                    with open(fallback_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        flat = self._flatten_dict(data)
                        if key in flat:
                            return flat[key]
                except Exception:
                    pass

        return default if default is not None else key


def _(key: str, default: Optional[str] = None) -> str:
    """
    便捷翻译函数

    Args:
        key: 翻译键名
        default: 找不到翻译时的默认返回值

    Returns:
        翻译后的文本
    """
    return I18nManager.instance().translate(key, default)


def reset_i18n_manager_for_testing() -> None:
    """
    重置国际化管理器单例

    用于测试隔离
    """
    I18nManager._instance = None
