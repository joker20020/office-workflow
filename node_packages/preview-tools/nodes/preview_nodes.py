# -*- coding: utf-8 -*-
"""
预览节点定义

提供各种数据类型的可视化预览功能，支持非模态窗口、多窗口显示。
每种类型对应一个 Dialog 类 + 一个执行函数 + 一个 NodeDefinition。
"""

import os
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from PySide6.QtCore import Qt, QUrl, QTimer, Signal, QObject, Slot
from PySide6.QtGui import QFont, QPixmap, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QToolBar,
    QWidget,
    QApplication,
    QLabel,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QSplitter,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QProgressBar,
)

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.ui.theme import Theme
from src.ui.theme_aware import ThemeAwareMixin
from src.utils.logger import get_logger

_logger = get_logger(__name__)

_active_dialogs: list = []


# ==================== 线程安全的 Dialog 创建桥接 ====================


class _DialogShower(QObject):
    """将 Dialog 创建/显示调度到主线程。

    工作线程中不能直接创建 QWidget，通过 Signal + QueuedConnection
    将创建操作安全地转移到主线程事件循环中执行。
    """

    _show_request = Signal(object)  # 传入一个无参 callable

    def __init__(self):
        super().__init__()
        # 自身必须存活在主线程
        self._show_request.connect(self._on_show, Qt.ConnectionType.QueuedConnection)

    def show(self, create_func: Callable[[], None]) -> None:
        """线程安全地请求在主线程创建并显示 Dialog。"""
        self._show_request.emit(create_func)

    @Slot(object)
    def _on_show(self, func: Callable[[], None]) -> None:
        try:
            func()
        except Exception as e:
            _logger.error(f"主线程创建预览窗口失败: {e}", exc_info=True)


# 懒初始化单例
_dialog_shower: Optional[_DialogShower] = None
_dialog_shower_lock = threading.Lock()


def _get_dialog_shower() -> _DialogShower:
    global _dialog_shower
    if _dialog_shower is None:
        with _dialog_shower_lock:
            if _dialog_shower is None:
                # 确保 QObject 创建在主线程
                app = QApplication.instance()
                shower = _DialogShower()
                if app and threading.current_thread() is not threading.main_thread():
                    shower.moveToThread(app.thread())
                _dialog_shower = shower
    return _dialog_shower


def _show_dialog(create_func: Callable[[], None]) -> None:
    """线程安全地创建并显示预览 Dialog。

    若当前已在主线程则直接调用；否则通过 _DialogShower 调度到主线程。
    """
    if threading.current_thread() is threading.main_thread():
        create_func()
    else:
        _get_dialog_shower().show(create_func)


# ==================== 公共基类 ====================


class _BasePreviewDialog(QDialog, ThemeAwareMixin):
    """所有预览 Dialog 的公共基类，提供统一的窗口设置和主题支持。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._setup_theme_awareness()
        self.setWindowTitle(title)
        self.setMinimumSize(420, 320)
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

    def _base_stylesheet(self) -> str:
        return f"""
            QDialog {{
                background-color: {Theme.hex("background_primary")};
            }}
        """

    def _toolbar_stylesheet(self) -> str:
        return f"""
            QToolBar {{
                background-color: {Theme.hex("background_secondary")};
                border: none;
                padding: 4px;
                spacing: 4px;
            }}
            QToolBar QToolButton {{
                background-color: transparent;
                border: 1px solid {Theme.hex("border_primary")};
                border-radius: 3px;
                padding: 4px 8px;
                color: {Theme.hex("text_primary")};
            }}
            QToolBar QToolButton:hover {{
                background-color: {Theme.hex("background_hover")};
                border-color: {Theme.hex("border_hover")};
            }}
            QToolBar QToolButton:pressed {{
                background-color: {Theme.hex("background_pressed")};
            }}
        """

    def _close_button_stylesheet(self) -> str:
        return f"""
            QPushButton {{
                background-color: {Theme.hex("background_tertiary")};
                color: {Theme.hex("text_primary")};
                border: 1px solid {Theme.hex("border_primary")};
                border-radius: 3px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background-color: {Theme.hex("background_hover")};
                border-color: {Theme.hex("border_hover")};
            }}
        """

    def _status_label_stylesheet(self) -> str:
        return f"""
            QLabel {{
                background-color: transparent;
                color: {Theme.hex("text_secondary")};
                border: none;
                font-size: 11px;
            }}
        """

    def refresh_theme(self) -> None:
        self.setStyleSheet(self._base_stylesheet())


def _register_dialog(dialog: QDialog) -> None:
    """注册活跃预览窗口并清理已关闭的。"""
    global _active_dialogs
    _active_dialogs.append(dialog)
    _active_dialogs = [d for d in _active_dialogs if d.isVisible()]


def _create_and_show(dialog_class, *args, **kwargs) -> None:
    """创建 Dialog 实例、显示并注册。必须在主线程调用。"""
    dialog = dialog_class(*args, **kwargs)
    dialog.show()
    _register_dialog(dialog)


# ==================== 1. 文本预览 ====================


class TextPreviewDialog(_BasePreviewDialog):
    """文本预览对话框 — 支持复制、自动换行切换、等宽字体。"""

    def __init__(self, text: str, parent=None):
        super().__init__("文本预览", parent)
        self._text = text
        self._word_wrap_enabled = True
        self.resize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet(self._toolbar_stylesheet())
        copy_action = toolbar.addAction("📋 复制")
        copy_action.setToolTip("复制全部文本到剪贴板")
        copy_action.triggered.connect(self._copy_to_clipboard)
        toolbar.addSeparator()
        self._wrap_action = toolbar.addAction("↩️ 自动换行")
        self._wrap_action.setCheckable(True)
        self._wrap_action.setChecked(True)
        self._wrap_action.triggered.connect(self._toggle_word_wrap)
        layout.addWidget(toolbar)

        # 文本区
        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(self._text)
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._text_edit.setFont(font)
        self._text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.hex("background_primary")};
                color: {Theme.hex("text_primary")};
                border: none;
                padding: 8px;
            }}
        """)
        layout.addWidget(self._text_edit)

        # 状态栏
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 4, 8, 4)
        info = QLabel(f"字符: {len(self._text)} | 行数: {self._text.count(chr(10)) + 1}")
        info.setStyleSheet(self._status_label_stylesheet())
        sl.addWidget(info)
        sl.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        sl.addWidget(close_btn)
        layout.addWidget(status)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self._text)
        self._wrap_action.setText("✓ 已复制!")
        QTimer.singleShot(2000, lambda: self._wrap_action.setText("↩️ 自动换行"))

    def _toggle_word_wrap(self, checked: bool):
        self._text_edit.setLineWrapMode(
            QTextEdit.LineWrapMode.WidgetWidth if checked
            else QTextEdit.LineWrapMode.NoWrap
        )


def _preview_text(text: str) -> Dict[str, Any]:
    if text is None:
        _logger.warning("文本预览: 输入为空")
        return {"text_out": ""}
    _show_dialog(lambda: _create_and_show(TextPreviewDialog, text))
    _logger.info(f"文本预览窗口已打开: {len(text)} 字符")
    return {"text_out": text}


text_preview = NodeDefinition(
    node_type="preview.text",
    display_name="文本预览",
    description="打开可视化窗口预览文本内容，支持复制和换行切换",
    category="preview",
    icon="👁️",
    inputs=[PortDefinition("text", PortType.STRING, "要预览的文本")],
    outputs=[PortDefinition("text_out", PortType.STRING, "预览的文本（透传）")],
    execute=_preview_text,
)


# ==================== 2. 图像预览 ====================


class ImagePreviewDialog(_BasePreviewDialog):
    """图像预览对话框 — 支持适应窗口/原始大小切换。"""

    def __init__(self, image_path: str, parent=None):
        super().__init__("图像预览", parent)
        self._image_path = image_path
        self._fit_mode = True
        self._pixmap = QPixmap(image_path)
        self.resize(700, 550)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet(self._toolbar_stylesheet())
        fit_action = toolbar.addAction("⊞ 适应窗口")
        fit_action.triggered.connect(self._toggle_fit)
        toolbar.addSeparator()
        info_label = QLabel(f" {Path(self._image_path).name} ")
        info_label.setStyleSheet(self._status_label_stylesheet())
        toolbar.addWidget(info_label)
        layout.addWidget(toolbar)

        # 图像区
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Theme.hex("background_primary")};
                border: none;
            }}
        """)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: transparent;")
        if self._pixmap.isNull():
            self._image_label.setText(f"⚠ 无法加载图像:\n{self._image_path}")
        else:
            self._update_image()
        self._scroll.setWidget(self._image_label)
        layout.addWidget(self._scroll, 1)

        # 底部
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 4, 8, 4)
        if not self._pixmap.isNull():
            size_info = QLabel(
                f"尺寸: {self._pixmap.width()} × {self._pixmap.height()} | "
                f"文件: {Path(self._image_path).name}"
            )
        else:
            size_info = QLabel("加载失败")
        size_info.setStyleSheet(self._status_label_stylesheet())
        sl.addWidget(size_info)
        sl.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        sl.addWidget(close_btn)
        layout.addWidget(status)

    def _update_image(self):
        if self._pixmap.isNull():
            return
        if self._fit_mode:
            scaled = self._pixmap.scaled(
                self._scroll.viewport().size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image_label.setPixmap(scaled)
        else:
            self._image_label.setPixmap(self._pixmap)

    def _toggle_fit(self):
        self._fit_mode = not self._fit_mode
        self._update_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode:
            self._update_image()


def _preview_image(image: str) -> Dict[str, Any]:
    if image is None:
        _logger.warning("图像预览: 输入为空")
        return {"image_out": ""}
    _show_dialog(lambda: _create_and_show(ImagePreviewDialog, image))
    _logger.info(f"图像预览窗口已打开: {image}")
    return {"image_out": image}


image_preview = NodeDefinition(
    node_type="preview.image",
    display_name="图像预览",
    description="打开窗口预览图像文件，支持缩放和适应窗口",
    category="preview",
    icon="🖼️",
    inputs=[PortDefinition("image", PortType.IMAGE, "图像文件路径")],
    outputs=[PortDefinition("image_out", PortType.IMAGE, "图像路径（透传）")],
    execute=_preview_image,
)


# ==================== 3. 音频预览 ====================


class AudioPreviewDialog(_BasePreviewDialog):
    """音频预览对话框 — QMediaPlayer 播放控制。"""

    def __init__(self, audio_path: str, parent=None):
        super().__init__("音频预览", parent)
        self._audio_path = audio_path
        self.resize(500, 180)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 文件名标题
        title = QLabel(f"🎵 {Path(self._audio_path).name}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("text_primary")};
                padding: 16px;
                font-size: 14px;
                font-weight: bold;
                background-color: {Theme.hex("background_primary")};
            }}
        """)
        layout.addWidget(title)

        # 播放控件
        controls = QWidget()
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(8, 4, 8, 8)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(40)
        self._play_btn.setStyleSheet(self._close_button_stylesheet())
        cl.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {Theme.hex("background_tertiary")};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                margin: -4px 0;
                background: {Theme.hex("accent_primary")};
                border-radius: 7px;
            }}
        """)
        cl.addWidget(self._slider, 1)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet(self._status_label_stylesheet())
        cl.addWidget(self._time_label)

        volume_label = QLabel("🔊")
        volume_label.setStyleSheet(f"color: {Theme.hex('text_secondary')};")
        cl.addWidget(volume_label)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(80)
        self._volume_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: {Theme.hex("background_tertiary")};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 10px;
                margin: -3px 0;
                background: {Theme.hex("text_secondary")};
                border-radius: 5px;
            }}
        """)
        cl.addWidget(self._volume_slider)

        layout.addWidget(controls)

        # MediaPlayer
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(self._audio_path))
        self._audio_output.setVolume(0.8)

        self._play_btn.clicked.connect(self._toggle_play)
        self._slider.sliderMoved.connect(self._player.setPosition)
        self._volume_slider.valueChanged.connect(
            lambda v: self._audio_output.setVolume(v / 100.0)
        )
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)

    @staticmethod
    def _format_ms(ms: int) -> str:
        s = max(ms // 1000, 0)
        return f"{s // 60}:{s % 60:02d}"

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_btn.setText("▶")
        else:
            self._player.play()
            self._play_btn.setText("⏸")

    def _on_position_changed(self, pos: int):
        self._slider.setValue(pos)
        self._time_label.setText(
            f"{self._format_ms(pos)} / {self._format_ms(self._player.duration())}"
        )

    def _on_duration_changed(self, dur: int):
        self._slider.setRange(0, dur)

    def closeEvent(self, event):
        self._player.stop()
        super().closeEvent(event)


def _preview_audio(audio: str) -> Dict[str, Any]:
    if audio is None:
        _logger.warning("音频预览: 输入为空")
        return {"audio_out": ""}
    _show_dialog(lambda: _create_and_show(AudioPreviewDialog, audio))
    _logger.info(f"音频预览窗口已打开: {audio}")
    return {"audio_out": audio}


audio_preview = NodeDefinition(
    node_type="preview.audio",
    display_name="音频预览",
    description="打开窗口播放音频文件，支持播放控制",
    category="preview",
    icon="🎵",
    inputs=[PortDefinition("audio", PortType.AUDIO, "音频文件路径")],
    outputs=[PortDefinition("audio_out", PortType.AUDIO, "音频路径（透传）")],
    execute=_preview_audio,
)


# ==================== 4. 视频预览 ====================


class VideoPreviewDialog(_BasePreviewDialog):
    """视频预览对话框 — QMediaPlayer + QVideoWidget 内嵌播放。"""

    def __init__(self, video_path: str, parent=None):
        super().__init__("视频预览", parent)
        self._video_path = video_path
        self.resize(800, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 视频区
        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet(
            f"background-color: #000000;"
        )
        layout.addWidget(self._video_widget, 1)

        # 控制栏
        controls = QWidget()
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(8, 4, 8, 4)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(40)
        self._play_btn.setStyleSheet(self._close_button_stylesheet())
        cl.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {Theme.hex("background_tertiary")};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                margin: -4px 0;
                background: {Theme.hex("accent_primary")};
                border-radius: 7px;
            }}
        """)
        cl.addWidget(self._slider, 1)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet(self._status_label_stylesheet())
        cl.addWidget(self._time_label)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        cl.addWidget(close_btn)

        layout.addWidget(controls)

        # MediaPlayer
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(self._video_widget)
        self._player.setSource(QUrl.fromLocalFile(self._video_path))

        self._play_btn.clicked.connect(self._toggle_play)
        self._slider.sliderMoved.connect(self._player.setPosition)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)

    @staticmethod
    def _format_ms(ms: int) -> str:
        s = max(ms // 1000, 0)
        return f"{s // 60}:{s % 60:02d}"

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_btn.setText("▶")
        else:
            self._player.play()
            self._play_btn.setText("⏸")

    def _on_position_changed(self, pos: int):
        self._slider.setValue(pos)
        self._time_label.setText(
            f"{self._format_ms(pos)} / {self._format_ms(self._player.duration())}"
        )

    def _on_duration_changed(self, dur: int):
        self._slider.setRange(0, dur)

    def closeEvent(self, event):
        self._player.stop()
        super().closeEvent(event)


def _preview_video(video: str) -> Dict[str, Any]:
    if video is None:
        _logger.warning("视频预览: 输入为空")
        return {"video_out": ""}
    _show_dialog(lambda: _create_and_show(VideoPreviewDialog, video))
    _logger.info(f"视频预览窗口已打开: {video}")
    return {"video_out": video}


video_preview = NodeDefinition(
    node_type="preview.video",
    display_name="视频预览",
    description="打开窗口播放视频文件，内嵌播放器和进度控制",
    category="preview",
    icon="🎬",
    inputs=[PortDefinition("video", PortType.VIDEO, "视频文件路径")],
    outputs=[PortDefinition("video_out", PortType.VIDEO, "视频路径（透传）")],
    execute=_preview_video,
)


# ==================== 5. 数字预览 ====================


class NumberPreviewDialog(_BasePreviewDialog):
    """数字预览对话框 — 大字体显示，科学计数法切换。"""

    def __init__(self, number: float, parent=None):
        super().__init__("数字预览", parent)
        self._number = number
        self._scientific = False
        self.resize(400, 280)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet(self._toolbar_stylesheet())
        sci_action = toolbar.addAction("科学计数法")
        sci_action.setCheckable(True)
        sci_action.triggered.connect(self._toggle_scientific)
        layout.addWidget(toolbar)

        # 数字显示
        self._number_label = QLabel()
        self._number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_display()
        layout.addWidget(self._number_label, 1)

        # 底部
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 4, 8, 4)
        type_info = QLabel(
            f"类型: {'整数' if isinstance(self._number, int) or self._number == int(self._number) else '浮点数'}"
        )
        type_info.setStyleSheet(self._status_label_stylesheet())
        sl.addWidget(type_info)
        sl.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        sl.addWidget(close_btn)
        layout.addWidget(status)

    def _update_display(self):
        if self._scientific:
            text = f"{self._number:.6e}"
        else:
            if isinstance(self._number, float) and self._number == int(self._number):
                text = f"{int(self._number)}"
            else:
                text = str(self._number)
        self._number_label.setText(text)
        self._number_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("accent_primary")};
                font-size: 36px;
                font-weight: bold;
                background-color: {Theme.hex("background_primary")};
                padding: 20px;
            }}
        """)

    def _toggle_scientific(self, checked: bool):
        self._scientific = checked
        self._update_display()


def _preview_number(number: float) -> Dict[str, Any]:
    if number is None:
        _logger.warning("数字预览: 输入为空")
        return {"number_out": 0}
    _show_dialog(lambda: _create_and_show(NumberPreviewDialog, number))
    _logger.info(f"数字预览窗口已打开: {number}")
    return {"number_out": number}


number_preview = NodeDefinition(
    node_type="preview.number",
    display_name="数字预览",
    description="可视化预览数字，支持科学计数法切换",
    category="preview",
    icon="🔢",
    inputs=[PortDefinition("number", PortType.FLOAT, "要预览的数字")],
    outputs=[PortDefinition("number_out", PortType.FLOAT, "数字（透传）")],
    execute=_preview_number,
)


# ==================== 6. 布尔预览 ====================


class BooleanPreviewDialog(_BasePreviewDialog):
    """布尔预览对话框 — 大号 ✓/✗ 图标。"""

    def __init__(self, value: bool, parent=None):
        super().__init__("布尔预览", parent)
        self._value = value
        self.resize(360, 260)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 图标
        icon_text = "✓" if self._value else "✗"
        icon_color = Theme.hex("success_accent") if self._value else Theme.hex("error_accent")
        icon_label = QLabel(icon_text)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: {icon_color};
                font-size: 72px;
                font-weight: bold;
                background-color: transparent;
                {Theme.emoji_font_css()}
            }}
        """)
        layout.addWidget(icon_label, 1)

        # 文字
        text_label = QLabel("True" if self._value else "False")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(f"""
            QLabel {{
                color: {icon_color};
                font-size: 20px;
                font-weight: bold;
                background-color: transparent;
                padding-bottom: 12px;
            }}
        """)
        layout.addWidget(text_label)

        # 底部
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(80)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(close_btn)
        hbox.addStretch()
        layout.addLayout(hbox)


def _preview_boolean(value: bool) -> Dict[str, Any]:
    if value is None:
        _logger.warning("布尔预览: 输入为空")
        return {"value_out": False}
    _show_dialog(lambda: _create_and_show(BooleanPreviewDialog, value))
    _logger.info(f"布尔预览窗口已打开: {value}")
    return {"value_out": value}


boolean_preview = NodeDefinition(
    node_type="preview.boolean",
    display_name="布尔预览",
    description="可视化预览布尔值，显示 ✓/✗ 图标",
    category="preview",
    icon="⚡",
    inputs=[PortDefinition("value", PortType.BOOLEAN, "要预览的布尔值")],
    outputs=[PortDefinition("value_out", PortType.BOOLEAN, "布尔值（透传）")],
    execute=_preview_boolean,
)


# ==================== 7. 列表预览 ====================


class ListPreviewDialog(_BasePreviewDialog):
    """列表预览对话框 — 表格展示索引/值。"""

    def __init__(self, data: list, parent=None):
        super().__init__("列表预览", parent)
        self._data = data
        self.resize(600, 450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet(self._toolbar_stylesheet())
        copy_action = toolbar.addAction("📋 复制 JSON")
        copy_action.triggered.connect(self._copy_json)
        layout.addWidget(toolbar)

        # 表格
        self._table = QTableWidget(len(self._data), 2)
        self._table.setHorizontalHeaderLabels(["#", "值"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Theme.hex("background_primary")};
                color: {Theme.hex("text_primary")};
                border: none;
                gridline-color: {Theme.hex("border_primary")};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QHeaderView::section {{
                background-color: {Theme.hex("background_secondary")};
                color: {Theme.hex("text_primary")};
                border: none;
                border-bottom: 1px solid {Theme.hex("border_primary")};
                padding: 4px 8px;
                font-weight: bold;
            }}
        """)

        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        for i, item in enumerate(self._data):
            idx_item = QTableWidgetItem(str(i))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, idx_item)
            val_text = json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item
            val_item = QTableWidgetItem(val_text)
            val_item.setFont(font)
            self._table.setItem(i, 1, val_item)

        layout.addWidget(self._table, 1)

        # 状态栏
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 4, 8, 4)
        info = QLabel(f"共 {len(self._data)} 条")
        info.setStyleSheet(self._status_label_stylesheet())
        sl.addWidget(info)
        sl.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        sl.addWidget(close_btn)
        layout.addWidget(status)

    def _copy_json(self):
        QApplication.clipboard().setText(json.dumps(self._data, ensure_ascii=False, indent=2))


def _preview_list(data: list) -> Dict[str, Any]:
    if data is None:
        _logger.warning("列表预览: 输入为空")
        return {"data_out": [], "length": 0}
    _show_dialog(lambda: _create_and_show(ListPreviewDialog, data))
    _logger.info(f"列表预览窗口已打开: {len(data)} 条")
    return {"data_out": data, "length": len(data)}


list_preview = NodeDefinition(
    node_type="preview.list",
    display_name="列表预览",
    description="以表格形式预览列表数据，显示索引和值",
    category="preview",
    icon="📋",
    inputs=[PortDefinition("data", PortType.LIST, "要预览的列表")],
    outputs=[
        PortDefinition("data_out", PortType.LIST, "列表（透传）"),
        PortDefinition("length", PortType.INTEGER, "列表长度"),
    ],
    execute=_preview_list,
)


# ==================== 8. 字典预览 ====================


class DictPreviewDialog(_BasePreviewDialog):
    """字典预览对话框 — 树形 JSON 展示。"""

    def __init__(self, data: dict, parent=None):
        super().__init__("字典预览", parent)
        self._data = data
        self.resize(650, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet(self._toolbar_stylesheet())
        expand_action = toolbar.addAction("展开全部")
        expand_action.triggered.connect(self._expand_all)
        collapse_action = toolbar.addAction("折叠全部")
        collapse_action.triggered.connect(self._collapse_all)
        toolbar.addSeparator()
        copy_action = toolbar.addAction("📋 复制 JSON")
        copy_action.triggered.connect(self._copy_json)
        layout.addWidget(toolbar)

        # 树
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["键", "值"])
        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {Theme.hex("background_primary")};
                color: {Theme.hex("text_primary")};
                border: none;
                font-family: Consolas, monospace;
            }}
            QTreeWidget::item {{
                padding: 2px 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: {Theme.hex("background_hover")};
            }}
            QHeaderView::section {{
                background-color: {Theme.hex("background_secondary")};
                color: {Theme.hex("text_primary")};
                border: none;
                border-bottom: 1px solid {Theme.hex("border_primary")};
                padding: 4px 8px;
                font-weight: bold;
            }}
        """)
        self._populate_tree(self._data, self._tree.invisibleRootItem())
        self._tree.expandToDepth(0)
        layout.addWidget(self._tree, 1)

        # 状态栏
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 4, 8, 4)
        info = QLabel(f"键数: {len(self._data)}")
        info.setStyleSheet(self._status_label_stylesheet())
        sl.addWidget(info)
        sl.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        sl.addWidget(close_btn)
        layout.addWidget(status)

    def _populate_tree(self, data: Any, parent: QTreeWidgetItem):
        if isinstance(data, dict):
            for key, value in data.items():
                item = QTreeWidgetItem([str(key), ""])
                if not isinstance(value, (dict, list)):
                    item.setText(1, json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)
                else:
                    item.setText(1, f"({type(value).__name__}, {len(value)} 项)")
                parent.addChild(item)
                self._populate_tree(value, item)
        elif isinstance(data, list):
            for i, value in enumerate(data):
                item = QTreeWidgetItem([f"[{i}]", ""])
                if not isinstance(value, (dict, list)):
                    item.setText(1, json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)
                else:
                    item.setText(1, f"({type(value).__name__}, {len(value)} 项)")
                parent.addChild(item)
                self._populate_tree(value, item)

    def _expand_all(self):
        self._tree.expandAll()

    def _collapse_all(self):
        self._tree.collapseAll()

    def _copy_json(self):
        QApplication.clipboard().setText(json.dumps(self._data, ensure_ascii=False, indent=2))


def _preview_dict(data: dict) -> Dict[str, Any]:
    if data is None:
        _logger.warning("字典预览: 输入为空")
        return {"data_out": {}, "keys": []}
    _show_dialog(lambda: _create_and_show(DictPreviewDialog, data))
    _logger.info(f"字典预览窗口已打开: {len(data)} 个键")
    return {"data_out": data, "keys": list(data.keys())}


dict_preview = NodeDefinition(
    node_type="preview.dict",
    display_name="字典预览",
    description="以树形结构预览字典/JSON数据，支持展开折叠",
    category="preview",
    icon="📝",
    inputs=[PortDefinition("data", PortType.DICT, "要预览的字典")],
    outputs=[
        PortDefinition("data_out", PortType.DICT, "字典（透传）"),
        PortDefinition("keys", PortType.LIST, "键列表"),
    ],
    execute=_preview_dict,
)


# ==================== 9. 文件预览 ====================


class FilePreviewDialog(_BasePreviewDialog):
    """文件预览对话框 — 文件元信息 + 文本内容预览。"""

    _TEXT_EXTENSIONS = {
        ".txt", ".md", ".py", ".js", ".ts", ".json", ".xml", ".yaml", ".yml",
        ".csv", ".html", ".css", ".scss", ".sql", ".sh", ".bat", ".ini",
        ".cfg", ".conf", ".log", ".toml", ".rs", ".go", ".java", ".c",
        ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
    }

    def __init__(self, file_path: str, parent=None):
        super().__init__("文件预览", parent)
        self._file_path = file_path
        self.resize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        path = Path(self._file_path)

        # 文件元信息
        meta = QWidget()
        ml = QVBoxLayout(meta)
        ml.setContentsMargins(12, 8, 12, 4)
        ml.setSpacing(2)

        name_label = QLabel(f"📄 {path.name}")
        name_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("text_primary")};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        ml.addWidget(name_label)

        stat = path.stat() if path.exists() else None
        info_parts = []
        if stat:
            size_str = self._human_size(stat.st_size)
            info_parts.append(f"大小: {size_str}")
            import time
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            info_parts.append(f"修改: {mtime}")
        info_parts.append(f"路径: {path}")
        info_label = QLabel("  |  ".join(info_parts))
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.hex("text_secondary")};
                font-size: 11px;
            }}
        """)
        ml.addWidget(info_label)
        meta.setStyleSheet(f"background-color: {Theme.hex('background_secondary')};")
        layout.addWidget(meta)

        # 内容预览
        is_text = path.suffix.lower() in self._TEXT_EXTENSIONS

        if is_text and path.exists():
            self._content_edit = QTextEdit()
            self._content_edit.setReadOnly(True)
            font = QFont("Consolas", 10)
            font.setStyleHint(QFont.StyleHint.Monospace)
            self._content_edit.setFont(font)
            self._content_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {Theme.hex("background_primary")};
                    color: {Theme.hex("text_primary")};
                    border: none;
                    padding: 8px;
                }}
            """)
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                self._content_edit.setPlainText(content[:102400])
            except Exception:
                self._content_edit.setPlainText("无法读取文件内容")
            layout.addWidget(self._content_edit, 1)
        else:
            placeholder = QLabel(
                "二进制文件，不支持内容预览" if path.exists() else "文件不存在"
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(f"""
                QLabel {{
                    color: {Theme.hex("text_hint")};
                    font-size: 14px;
                    background-color: {Theme.hex("background_primary")};
                }}
            """)
            layout.addWidget(placeholder, 1)

        # 底部
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 4, 8, 4)
        sl.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        sl.addWidget(close_btn)
        layout.addWidget(status)

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


def _preview_file(file_path: str) -> Dict[str, Any]:
    if file_path is None:
        _logger.warning("文件预览: 输入为空")
        return {"file_path_out": ""}
    _show_dialog(lambda: _create_and_show(FilePreviewDialog, file_path))
    _logger.info(f"文件预览窗口已打开: {file_path}")
    return {"file_path_out": file_path}


file_preview = NodeDefinition(
    node_type="preview.file",
    display_name="文件预览",
    description="预览文件元信息和文本内容",
    category="preview",
    icon="📂",
    inputs=[PortDefinition("file_path", PortType.FILE, "文件路径")],
    outputs=[PortDefinition("file_path_out", PortType.FILE, "文件路径（透传）")],
    execute=_preview_file,
)


# ==================== 10. 数据表预览 ====================


class DataFramePreviewDialog(_BasePreviewDialog):
    """数据表预览对话框 — QTableWidget 表格展示。"""

    def __init__(self, data: dict, parent=None):
        super().__init__("数据表预览", parent)
        self._data = data
        self.resize(750, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        columns: List[str] = self._data.get("columns", [])
        rows: List[list] = self._data.get("data", [])

        self._table = QTableWidget(len(rows), len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Theme.hex("background_primary")};
                color: {Theme.hex("text_primary")};
                border: none;
                gridline-color: {Theme.hex("border_primary")};
                alternate-background-color: {Theme.hex("background_secondary")};
            }}
            QTableWidget::item {{
                padding: 2px 6px;
            }}
            QHeaderView::section {{
                background-color: {Theme.hex("background_secondary")};
                color: {Theme.hex("text_primary")};
                border: none;
                border-bottom: 1px solid {Theme.hex("border_primary")};
                padding: 4px 8px;
                font-weight: bold;
            }}
        """)

        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                text = "" if val is None else str(val)
                item = QTableWidgetItem(text)
                self._table.setItem(r, c, item)

        layout.addWidget(self._table, 1)

        # 状态栏
        status = QWidget()
        sl = QHBoxLayout(status)
        sl.setContentsMargins(8, 4, 8, 4)
        info = QLabel(f"行: {len(rows)} | 列: {len(columns)}")
        info.setStyleSheet(self._status_label_stylesheet())
        sl.addWidget(info)
        sl.addStretch()
        copy_action = QPushButton("📋 复制")
        copy_action.setStyleSheet(self._close_button_stylesheet())
        copy_action.clicked.connect(self._copy_table)
        sl.addWidget(copy_action)
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._close_button_stylesheet())
        close_btn.clicked.connect(self.close)
        sl.addWidget(close_btn)
        layout.addWidget(status)

    def _copy_table(self):
        columns: List[str] = self._data.get("columns", [])
        rows: List[list] = self._data.get("data", [])
        lines = ["\t".join(columns)]
        for row in rows:
            lines.append("\t".join(str(v) if v is not None else "" for v in row))
        QApplication.clipboard().setText("\n".join(lines))


def _preview_dataframe(data: dict) -> Dict[str, Any]:
    if data is None:
        _logger.warning("数据表预览: 输入为空")
        return {"data_out": {}, "rows": 0, "columns": 0}
    _show_dialog(lambda: _create_and_show(DataFramePreviewDialog, data))
    columns = data.get("columns", [])
    rows = data.get("data", [])
    _logger.info(f"数据表预览窗口已打开: {len(rows)} 行 × {len(columns)} 列")
    return {
        "data_out": data,
        "rows": len(rows),
        "columns": len(columns),
    }


dataframe_preview = NodeDefinition(
    node_type="preview.dataframe",
    display_name="数据表预览",
    description="以表格形式预览数据表，支持交替行颜色",
    category="preview",
    icon="📊",
    inputs=[PortDefinition("data", PortType.DATAFRAME, "数据表 (columns + data)")],
    outputs=[
        PortDefinition("data_out", PortType.DATAFRAME, "数据表（透传）"),
        PortDefinition("rows", PortType.INTEGER, "行数"),
        PortDefinition("columns", PortType.INTEGER, "列数"),
    ],
    execute=_preview_dataframe,
)
