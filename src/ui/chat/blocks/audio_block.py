# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from src.ui.chat.blocks.base import BaseBlockWidget
from src.ui.theme import Theme


class AudioBlockWidget(BaseBlockWidget):
    BLOCK_TYPE = "audio"

    def __init__(
        self,
        block_data: Dict[str, Any],
        parent=None,
    ):
        self._player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None
        self._info_label: QLabel = None  # type: ignore
        self._play_btn: QPushButton = None  # type: ignore
        self._has_source = False
        super().__init__(block_data, parent)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._info_label = QLabel("🎵 音频")
        layout.addWidget(self._info_label)

        self._play_btn = QPushButton("▶ 播放")
        self._play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self._play_btn)

        self._init_media_player()

    def _init_media_player(self) -> None:
        source = self._block_data.get("source", {})
        source_type = source.get("type", "")
        url = source.get("url", "") if source_type == "url" else ""

        if not url:
            self._info_label.setText("🎵 音频 (无来源)")
            self._play_btn.setEnabled(False)
            return

        self._has_source = True
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)

        if url.startswith(("http://", "https://")):
            self._player.setSource(QUrl(url))
            self._info_label.setText(f"🎵 音频")
        else:
            self._player.setSource(QUrl.fromLocalFile(url))
            self._info_label.setText("🎵 音频")

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

        if self._info_label:
            color = Theme.hex("text_hint") if not self._has_source else Theme.hex("text_primary")
            self._info_label.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    font-size: 13px;
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 4px;
                    padding: 8px;
                }}
            """)

        if self._play_btn:
            self._play_btn.setStyleSheet(Theme.get_media_play_button_stylesheet())

    def get_content(self) -> str:
        return "[音频]"

    def set_content(self, content: str) -> None:
        pass

    def refresh_theme(self) -> None:
        self._apply_styles()
