# -*- coding: utf-8 -*-
"""
遊戲視窗管理：偵測 wwm.exe、監控焦點切換。
在背景執行緒中每秒輪詢，通知 AppController 狀態變化。
"""
from __future__ import annotations
import threading
import time
import win32gui
import win32process
import win32con
import psutil

TARGET_PROCESS = "wwm.exe"


def _get_process_name(hwnd: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        return proc.name().lower()
    except Exception:
        return ""


def find_game_window() -> int:
    """回傳 wwm.exe 的視窗 handle，找不到回傳 0。"""
    result = [0]

    def callback(hwnd: int, _: None) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if _get_process_name(hwnd) == TARGET_PROCESS:
            result[0] = hwnd
            return False  # 停止列舉
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        # pywin32 在 callback 回傳 False 停止列舉時會拋出 error code 2，屬正常行為
        pass

    return result[0]


def get_foreground_process_name() -> str:
    hwnd = win32gui.GetForegroundWindow()
    return _get_process_name(hwnd)


def _get_foreground_info() -> tuple[str, str]:
    """回傳目前前景視窗的 (process_name, window_title)。"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        proc = _get_process_name(hwnd)
        title = win32gui.GetWindowText(hwnd) or ""
        return proc, title
    except Exception:
        return "", ""


class WindowManager:
    def __init__(self, app_controller) -> None:
        self._app = app_controller
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_focus_proc: str = ""

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _poll_loop(self) -> None:
        from core.log_manager import get_log_manager
        while self._running:
            # ── 前景視窗焦點偵測 ──────────────────────────────────────────
            fg_proc, fg_title = _get_foreground_info()
            if fg_proc and fg_proc != self._last_focus_proc:
                display = fg_title if fg_title else fg_proc
                get_log_manager().log(f"[FOCUS] {display} ({fg_proc})", "INFO")
                self._last_focus_proc = fg_proc

            # ── 遊戲視窗偵測 ──────────────────────────────────────────────
            hwnd = find_game_window()
            if hwnd:
                self._app.game_found = True
                self._app.game_hwnd = hwnd

                # 如果識別中且焦點離開遊戲視窗，自動停止識別
                if self._app.recognition_active:
                    if fg_proc != TARGET_PROCESS:
                        self._app.recognition_active = False
            else:
                self._app.game_found = False
                self._app.game_hwnd = 0

            time.sleep(0.2)

    def get_window_rect(self) -> tuple[int, int, int, int] | None:
        """回傳遊戲視窗的 (left, top, right, bottom)，找不到回傳 None。"""
        hwnd = self._app.game_hwnd
        if not hwnd:
            return None
        try:
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            return None
