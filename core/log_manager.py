# -*- coding: utf-8 -*-
"""
Log 管理器（Singleton）。

- 啟動時自動在 logs/ 建立 YYYYMMDD_HHMMSS.log
- log(message, level) 同時寫入檔案與 print 到 console
- 執行緒安全
- 不依賴任何 GUI 模組
"""
from __future__ import annotations

import os
import sys
import threading
import datetime


def _get_log_dir() -> str:
    """
    取得 logs/ 目錄的絕對路徑。
    - 打包後（frozen）：exe 同層目錄下的 logs/
    - 開發時：專案根目錄下的 logs/
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # 本檔案位於 core/，上一層即為專案根目錄
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "logs")


class LogManager:
    """執行緒安全的 Log 管理器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        log_dir = _get_log_dir()
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"{timestamp}.log")
        self._file = open(log_path, "a", encoding="utf-8")

        self.log("=== WWM Guild Manager 啟動 ===", "INFO")

    def log(self, message: str, level: str = "INFO") -> None:
        """
        寫入一行 log。

        格式：[HH:MM:SS] [LEVEL] message
        同時輸出到 console 與 log 檔案。
        """
        now = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{now}] [{level}] {message}"
        with self._lock:
            print(line)
            try:
                self._file.write(line + "\n")
                self._file.flush()
            except Exception:
                pass

    def close(self) -> None:
        """程式結束時呼叫，確保 log 檔案被正確關閉。"""
        self.log("=== WWM Guild Manager 結束 ===", "INFO")
        with self._lock:
            try:
                self._file.close()
            except Exception:
                pass


# ── Singleton ───────────────────────────────────────────────────────────────

_instance: LogManager | None = None
_init_lock = threading.Lock()


def get_log_manager() -> LogManager:
    """取得全域 LogManager 單例（首次呼叫時自動初始化）。"""
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = LogManager()
    return _instance
