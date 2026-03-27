# -*- coding: utf-8 -*-
"""
内置插件目录

存放系统内置插件:
- text_processing: 文本处理插件
- test_widgets: 内联控件测试插件
"""

from plugins.text_processing import TextProcessingPlugin
from plugins.test_widgets import TestWidgetsPlugin

__all__ = [
    "TextProcessingPlugin",
    "TestWidgetsPlugin",
]
