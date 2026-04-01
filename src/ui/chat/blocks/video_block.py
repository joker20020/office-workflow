# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QPushButton, QVBoxLayout

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
        self._play_btn: QPushButton = None  # type: ignore
        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._video_widget = QVideoWidget()
        self._video_widget.setMaximumSize(400, 300)
        layout.addWidget(self._video_widget)

        self._play_btn = QPushButton("▶ 播放")
        self._play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self._play_btn)

        self._init_media_player()

    def _init_media_player(self) -> None:
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(self._video_widget)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._load_video_source()

    def _load_video_source(self) -> None:
        source = self._block_data.get("source", {})
        source_type = source.get("type", "")

        if source_type == "url":
            url = source.get("url", "")
            if url:
                if url.startswith(("http://", "https://")):
                    self._player.setSource(QUrl(url))
                else:
                    self._player.setSource(QUrl.fromLocalFile(url))
        elif source_type == "base64":
            pass

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
        if self._video_widget:
            self._video_widget.setStyleSheet(f"""
                QVideoWidget {{
                    background-color: {Theme.hex("background_primary")};
                    border: 1px solid {Theme.hex("border_primary")};
                    border-radius: 4px;
                }}
            """)

        if self._play_btn:
            self._play_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.hex("border_focus")};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 13px;
                    min-width: 80px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.hex("accent_hover_bg")};
                }}
                QPushButton:pressed {{
                    background-color: {Theme.hex("accent_pressed_bg")};
                }}
            """)

    def get_content(self) -> str:
        return "[视频]"

    def set_content(self, content: str) -> None:
        pass

    def refresh_theme(self) -> None:
        self._apply_styles()
