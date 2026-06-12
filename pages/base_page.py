# -*- coding: utf-8 -*-
"""
所有分頁的抽象基底類別。

新增分頁方式：
  1. 在 pages/<name>/ 下建立資料夾
  2. 繼承 BasePage 並設定 PAGE_ID、PAGE_TITLE、REQUIRES_GAME
  3. 在 ui/main_window.py 的 PAGES 清單加入一行
"""
from __future__ import annotations
import customtkinter as ctk


class BasePage(ctk.CTkFrame):
    PAGE_ID: str = ""        # 唯一識別碼，例如 "home"
    PAGE_TITLE: str = ""     # 側邊欄顯示名稱
    PAGE_ICON: str = ""      # Unicode 圖示字符（可選）
    REQUIRES_GAME: bool = True  # 是否需要遊戲視窗才能選取

    def __init__(self, parent, app_controller, config_manager, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.app = app_controller
        self.cfg = config_manager

    def on_show(self) -> None:
        """切換到此分頁時呼叫（可覆寫）"""

    def on_hide(self) -> None:
        """離開此分頁時呼叫（可覆寫）"""
