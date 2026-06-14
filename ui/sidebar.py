# -*- coding: utf-8 -*-
"""
左側導覽列。
- 顯示所有分頁按鈕
- 需要遊戲視窗的分頁：未找到時顯示鎖頭並禁用
- 訂閱 AppController 的 game_found 狀態自動更新
"""
from __future__ import annotations
import os
import sys
import customtkinter as ctk
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))

def _bundle_path(relative: str) -> str:
    """打包後從 _MEIPASS 讀取內建資源；開發時從專案根目錄讀取。"""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(_HERE, "..")
    return os.path.join(base, relative)

_ICON_PATH = _bundle_path(os.path.join("images", "other", "icon.png"))

# 顏色常數
CLR_BG = "#1a1a2e"
CLR_BG_ITEM = "#16213e"
CLR_SELECTED = "#0f3460"
CLR_ACCENT = "#e94560"
CLR_TEXT = "#e0e0e0"
CLR_TEXT_DIM = "#888888"
CLR_LOCK = "#666666"

APP_TITLE = "WWM Guild Manager"


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, app_controller, pages_meta: list[dict], on_select, **kwargs):
        """
        Args:
            pages_meta: [{"id": str, "title": str, "icon": str, "requires_game": bool}]
            on_select: callable(page_id: str)
        """
        super().__init__(parent, width=200, fg_color=CLR_BG, corner_radius=0, **kwargs)
        self.grid_propagate(False)

        self._app = app_controller
        self._on_select = on_select
        self._pages_meta = pages_meta
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._current_id: str = ""

        self._build()
        app_controller.on_game_found_change(self._on_game_state_change)

    def _build(self) -> None:
        # 標題區
        title_frame = ctk.CTkFrame(self, fg_color=CLR_BG, corner_radius=0)
        title_frame.pack(fill="x", padx=0, pady=(16, 8))

        # 載入圖示（使用 CTkImage 支援 HiDPI）
        try:
            _pil_icon = Image.open(_ICON_PATH)
            _ctk_icon = ctk.CTkImage(_pil_icon, size=(52, 52))
            ctk.CTkLabel(
                title_frame,
                image=_ctk_icon,
                text="",
            ).pack(padx=16, pady=(0, 4))
        except Exception:
            pass

        ctk.CTkLabel(
            title_frame,
            text="WWM",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=CLR_ACCENT,
        ).pack(padx=16, pady=(0, 2))
        ctk.CTkLabel(
            title_frame,
            text="Guild Manager",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
        ).pack(padx=16)

        # 分隔線
        ctk.CTkFrame(self, height=1, fg_color="#333355", corner_radius=0).pack(
            fill="x", padx=12, pady=(8, 12)
        )

        # 分頁按鈕
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=8)

        for meta in self._pages_meta:
            pid = meta["id"]
            icon = meta.get("icon", "")
            title = meta["title"]
            requires_game = meta.get("requires_game", True)

            label = f"{icon}  {title}" if icon else title

            btn = ctk.CTkButton(
                nav_frame,
                text=label,
                anchor="w",
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                text_color=CLR_TEXT,
                hover_color=CLR_SELECTED,
                corner_radius=8,
                height=40,
                command=lambda p=pid: self._handle_click(p),
            )
            btn.pack(fill="x", pady=2)
            self._buttons[pid] = btn


    def _handle_click(self, page_id: str) -> None:
        meta = next((m for m in self._pages_meta if m["id"] == page_id), None)
        if meta and meta.get("requires_game", True) and not self._app.game_found:
            return  # 鎖定狀態，忽略點擊
        self.select(page_id)
        self._on_select(page_id)

    def select(self, page_id: str) -> None:
        """更新選中狀態的視覺效果"""
        self._current_id = page_id
        for pid, btn in self._buttons.items():
            if pid == page_id:
                btn.configure(fg_color=CLR_SELECTED, text_color=CLR_ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=CLR_TEXT)
        self._update_lock_states()

    def _on_game_state_change(self, found: bool) -> None:
        """game_found 狀態變化時更新所有鎖定按鈕"""
        self._update_lock_states()

    def _update_lock_states(self) -> None:
        game_ok = self._app.game_found
        for meta in self._pages_meta:
            pid = meta["id"]
            requires_game = meta.get("requires_game", True)
            btn = self._buttons.get(pid)
            if btn is None:
                continue

            if requires_game and not game_ok:
                # 鎖定狀態
                icon = meta.get("icon", "")
                title = meta["title"]
                locked_text = f"{icon}  {title}  🔒" if icon else f"{title}  🔒"
                btn.configure(text=locked_text, text_color=CLR_LOCK, state="disabled")
            else:
                icon = meta.get("icon", "")
                title = meta["title"]
                normal_text = f"{icon}  {title}" if icon else title
                is_selected = pid == self._current_id
                btn.configure(
                    text=normal_text,
                    text_color=CLR_ACCENT if is_selected else CLR_TEXT,
                    state="normal",
                )
