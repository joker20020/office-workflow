# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.theme import Theme


class VideoBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "video"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None
        self._video_widget: Optional[QVideoWidget] = None
        self._placeholder_label: Optional[QLabel] = None
        self._play_btn: QPushButton = None  # type: ignore
        self._has_source = False
        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        source = self._block_data.get("source", {})
        source_type = source.get("type", "")
        url = source.get("url", "") if source_type == "url" else ""

        if not url:
            # Show placeholder instead of video widget
            self._placeholder_label = QLabel("🎬 视频 (无来源)")
            self._placeholder_label.setMinimumSize(200, 150)
            self._placeholder_label.setMaximumSize(400, 300)
            self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._placeholder_label)
        else:
            self._has_source = True
            self._video_widget = QVideoWidget()
            self._video_widget.setMinimumSize(200, 150)
            self._video_widget.setMaximumSize(400, 300)
            layout.addWidget(self._video_widget)

        self._play_btn = QPushButton("▶ 播放")
        self._play_btn.clicked.connect(self._toggle_play)
        if not self._has_source:
            self._play_btn.setEnabled(False)
        layout.addWidget(self._play_btn)

        if self._has_source:
            self._init_media_player(url)

    def _init_media_player(self, url: str) -> None:
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(self._video_widget)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)

        if url.startswith(("http://", "https://")):
            self._player.setSource(QUrl(url))
        else:
            self._player.setSource(QUrl.fromLocalFile(url))

    def _toggle_play(self) -> None:
        if not self._player:
            return

        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸ 暂停")
        else:
            self._play_btn.setText("▶ 播放")

    def _apply_styles(self) -> None:
        bg = Theme.hex("background_secondary")
        border = Theme.hex("border_primary")

        if self._video_widget:
            self._video_widget.setStyleSheet(f"""
                QVideoWidget {{
                    background-color: {Theme.hex("background_primary")};
                    border: 1px solid {border};
                    border-radius: 4px;
                }}
            """)

        if self._placeholder_label:
            self._placeholder_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 4px;
                    color: {Theme.hex("text_hint")};
                    font-size: 28px;
                    {Theme.emoji_font_css()}
                }}
            """)

        if self._play_btn:
            self._play_btn.setStyleSheet(Theme.get_media_play_button_stylesheet())

    def get_content(self) -> str:
        return "[视频]"

    def set_content(self, content: str) -> None:
        pass

    def refresh_theme(self) -> None:
        self._apply_styles()
