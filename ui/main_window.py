# -*- coding: utf-8 -*-
"""
主視窗：左側 Sidebar + 右側內容區。
切換分頁時僅替換右側內容，不重建視窗。
"""
from __future__ import annotations
import os
import sys
import customtkinter as ctk

from ui.sidebar import Sidebar

_HERE = os.path.dirname(os.path.abspath(__file__))

def _bundle_path(relative: str) -> str:
    """打包後從 _MEIPASS 讀取內建資源；開發時從專案根目錄讀取。"""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(_HERE, "..")
    return os.path.join(base, relative)

_ICON_ICO = _bundle_path(os.path.join("images", "other", "icon.ico"))

CLR_CONTENT_BG = "#0d1117"


class MainWindow(ctk.CTk):
    def __init__(self, app_controller, config_manager) -> None:
        super().__init__()

        self._app = app_controller
        self._cfg = config_manager
        self._pages: dict[str, any] = {}
        self._current_page_id: str = ""

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("WWM Guild Manager")
        self.geometry("1000x830")
        self.minsize(800, 710)
        self.configure(fg_color=CLR_CONTENT_BG)

        # 設定視窗圖示
        try:
            self.iconbitmap(_ICON_ICO)
        except Exception:
            pass

        # 防止視窗消失時仍在跑背景執行緒
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def build(self, pages_classes: list) -> None:
        """
        呼叫時機：所有頁面類別都準備好後呼叫。

        Args:
            pages_classes: List of BasePage subclasses (未實例化)
        """
        pages_meta = [
            {
                "id": cls.PAGE_ID,
                "title": cls.PAGE_TITLE,
                "icon": cls.PAGE_ICON,
                "requires_game": cls.REQUIRES_GAME,
            }
            for cls in pages_classes
        ]

        # 版面：側邊欄 | 內容區
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._sidebar = Sidebar(
            self,
            self._app,
            pages_meta,
            on_select=self._switch_page,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        self._content_frame = ctk.CTkFrame(
            self, fg_color=CLR_CONTENT_BG, corner_radius=0
        )
        self._content_frame.grid(row=0, column=1, sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # 實例化所有分頁（預先建立，切換時 show/hide）
        for cls in pages_classes:
            page = cls(
                self._content_frame,
                self._app,
                self._cfg,
            )
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()  # 先全部隱藏
            self._pages[cls.PAGE_ID] = page

        # 預設顯示第一個分頁
        if pages_classes:
            first_id = pages_classes[0].PAGE_ID
            self._current_page_id = ""  # 確保 _switch_page 不會因相同 id 跳過
            self._switch_page(first_id)
            self._sidebar.select(first_id)

    def _switch_page(self, page_id: str) -> None:
        if self._current_page_id == page_id:
            return

        # 隱藏目前分頁
        if self._current_page_id and self._current_page_id in self._pages:
            self._pages[self._current_page_id].on_hide()
            self._pages[self._current_page_id].grid_remove()

        # 顯示新分頁
        if page_id in self._pages:
            self._pages[page_id].grid()
            self._pages[page_id].on_show()
            self._current_page_id = page_id

    def _on_close(self) -> None:
        self._app.recognition_active = False
        self.destroy()
