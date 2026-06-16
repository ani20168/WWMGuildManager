# -*- coding: utf-8 -*-
"""
全域應用程式狀態管理器（觀察者模式）。
所有模組都可以訂閱狀態變化，而不需要直接互相依賴。
"""
from __future__ import annotations
import time
from typing import Callable


class AppController:
    def __init__(self) -> None:
        self._game_found: bool = False
        self._recognition_active: bool = False
        self.game_hwnd: int = 0
        self.recognition_start_time: float = 0.0  # 識別啟動的時間戳（用於緩衝期）

        # 觀察者回呼列表
        self._on_game_found_callbacks: list[Callable[[bool], None]] = []
        self._on_recognition_callbacks: list[Callable[[bool], None]] = []

    # ── game_found ──────────────────────────────────────────────────────────
    @property
    def game_found(self) -> bool:
        return self._game_found

    @game_found.setter
    def game_found(self, value: bool) -> None:
        if self._game_found != value:
            self._game_found = value
            for cb in self._on_game_found_callbacks:
                cb(value)

    def on_game_found_change(self, callback: Callable[[bool], None]) -> None:
        self._on_game_found_callbacks.append(callback)

    # ── recognition_active ──────────────────────────────────────────────────
    @property
    def recognition_active(self) -> bool:
        return self._recognition_active

    @recognition_active.setter
    def recognition_active(self, value: bool) -> None:
        if self._recognition_active != value:
            self._recognition_active = value
            if value:
                self.recognition_start_time = time.time()
            for cb in self._on_recognition_callbacks:
                cb(value)

    def on_recognition_change(self, callback: Callable[[bool], None]) -> None:
        self._on_recognition_callbacks.append(callback)

    def toggle_recognition(self) -> None:
        """F8 快捷鍵觸發：如果遊戲視窗未找到則不執行"""
        if not self._game_found:
            return
        self.recognition_active = not self._recognition_active
