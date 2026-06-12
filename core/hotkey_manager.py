# -*- coding: utf-8 -*-
"""
全域快捷鍵管理。
支援動態重設快捷鍵（變更設定後 unhook 再重新 hook）。
"""
from __future__ import annotations
import threading
import keyboard


class HotkeyManager:
    def __init__(self, app_controller, config_manager) -> None:
        self._app = app_controller
        self._cfg = config_manager
        self._current_hotkey: str = ""
        self._lock = threading.Lock()

    def start(self) -> None:
        hotkey = self._cfg.get("hotkey_toggle", "f8")
        self._register(hotkey)

    def stop(self) -> None:
        self._unregister()

    def update_hotkey(self, new_hotkey: str) -> None:
        """首頁設定變更快捷鍵時呼叫"""
        with self._lock:
            self._unregister()
            self._register(new_hotkey)
        self._cfg.set("hotkey_toggle", new_hotkey)

    def _register(self, hotkey: str) -> None:
        if not hotkey:
            return
        try:
            keyboard.add_hotkey(hotkey, self._app.toggle_recognition, suppress=False)
            self._current_hotkey = hotkey
        except Exception:
            pass

    def _unregister(self) -> None:
        if self._current_hotkey:
            try:
                keyboard.remove_hotkey(self._current_hotkey)
            except Exception:
                pass
            self._current_hotkey = ""

    def capture_next_key(self, callback) -> None:
        """
        非阻塞方式等待使用者按下一個鍵，回呼傳入鍵名字串。
        用於首頁「點擊後等待輸入」的快捷鍵設定功能。
        """
        def _wait():
            event = keyboard.read_event(suppress=True)
            if event.event_type == keyboard.KEY_DOWN:
                callback(event.name)

        t = threading.Thread(target=_wait, daemon=True)
        t.start()
