# -*- coding: utf-8 -*-
"""
首頁：
  - 遊戲視窗狀態顯示
  - 快捷鍵設定
  - 識別延遲滑桿
  - HDR 補償開關
"""
from __future__ import annotations
import customtkinter as ctk

from pages.base_page import BasePage

CLR_CARD = "#161b27"
CLR_BORDER = "#2a2d3e"
CLR_SUCCESS = "#4caf50"
CLR_ERROR = "#e94560"
CLR_TEXT = "#e0e0e0"
CLR_TEXT_DIM = "#888888"
CLR_ACCENT = "#4a9eff"


class HomePage(BasePage):
    PAGE_ID = "home"
    PAGE_TITLE = "首頁"
    PAGE_ICON = "🏠"
    REQUIRES_GAME = False

    def __init__(self, parent, app_controller, config_manager, **kwargs):
        super().__init__(parent, app_controller, config_manager, **kwargs)
        self._hotkey_capture_mode = False
        self._build()
        self.app.on_game_found_change(self._on_game_state_change)

    # ── 建構 UI ─────────────────────────────────────────────────────────────
    def _build(self) -> None:
        self.configure(fg_color="transparent")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=20)
        scroll.grid_columnconfigure(0, weight=1)

        row = 0

        # 頁面標題
        ctk.CTkLabel(
            scroll,
            text="基本設定",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=CLR_TEXT,
            anchor="w",
        ).grid(row=row, column=0, sticky="ew", pady=(0, 16))
        row += 1

        # ── 遊戲視窗狀態 ────────────────────────────────────────────────────
        row = self._build_card(
            scroll, row,
            title="遊戲視窗",
            builder=self._build_window_section,
        )

        # ── 快捷鍵設定 ──────────────────────────────────────────────────────
        row = self._build_card(
            scroll, row,
            title="快捷鍵設定",
            builder=self._build_hotkey_section,
        )

        # ── 延遲設定 ────────────────────────────────────────────────────────
        row = self._build_card(
            scroll, row,
            title="延遲設定",
            builder=self._build_delay_section,
        )

        # ── HDR 設定 ────────────────────────────────────────────────────────
        row = self._build_card(
            scroll, row,
            title="顯示設定",
            builder=self._build_hdr_section,
        )

    def _build_card(self, parent, row: int, title: str, builder) -> int:
        """建立有標題的卡片容器，回傳下一個 row index。"""
        # 區段標題
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=CLR_ACCENT,
            anchor="w",
        ).grid(row=row, column=0, sticky="ew", pady=(8, 4))
        row += 1

        card = ctk.CTkFrame(parent, fg_color=CLR_CARD, corner_radius=10, border_width=1, border_color=CLR_BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        card.grid_columnconfigure(0, weight=1)
        builder(card)
        row += 1
        return row

    # ── 遊戲視窗 Section ────────────────────────────────────────────────────
    def _build_window_section(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            inner,
            text="焦點視窗偵測（wwm.exe）",
            font=ctk.CTkFont(size=12),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        ).pack(fill="x")

        self._window_status_label = ctk.CTkLabel(
            inner,
            text="⏳ 偵測中...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        )
        self._window_status_label.pack(fill="x", pady=(6, 0))

        # 立即更新一次
        self._refresh_window_status(self.app.game_found)

    def _on_game_state_change(self, found: bool) -> None:
        self._refresh_window_status(found)

    def _refresh_window_status(self, found: bool) -> None:
        if found:
            self._window_status_label.configure(
                text="✅ 已找到遊戲視窗（wwm.exe）",
                text_color=CLR_SUCCESS,
            )
        else:
            self._window_status_label.configure(
                text="❌ 尚未找到遊戲視窗...",
                text_color=CLR_ERROR,
            )

    # ── 快捷鍵 Section ──────────────────────────────────────────────────────
    def _build_hotkey_section(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        inner.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            inner,
            text="識別畫面切換",
            font=ctk.CTkFont(size=13),
            text_color=CLR_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            inner,
            text="按一下開始識別，再按一下關閉",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 8))

        current_key = self.cfg.get("hotkey_toggle", "f8").upper()
        self._hotkey_btn = ctk.CTkButton(
            inner,
            text=current_key,
            width=100,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1e3a5f",
            hover_color="#2a4f80",
            command=self._start_hotkey_capture,
        )
        self._hotkey_btn.grid(row=0, column=1, padx=(12, 0), sticky="w")

        ctk.CTkLabel(
            inner,
            text="（點擊後按下任意鍵以更改）",
            font=ctk.CTkFont(size=10),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=2, padx=(8, 0), sticky="w")

    def _start_hotkey_capture(self) -> None:
        if self._hotkey_capture_mode:
            return
        self._hotkey_capture_mode = True
        self._hotkey_btn.configure(text="⌨ 等待輸入...", fg_color="#3a2a10")

        if hasattr(self, "_hotkey_manager") and self._hotkey_manager:
            self._hotkey_manager.capture_next_key(self._on_hotkey_captured)

    def _on_hotkey_captured(self, key: str) -> None:
        self._hotkey_capture_mode = False
        display_key = key.upper()
        self._hotkey_btn.configure(text=display_key, fg_color="#1e3a5f")
        if hasattr(self, "_hotkey_manager") and self._hotkey_manager:
            self._hotkey_manager.update_hotkey(key)

    def set_hotkey_manager(self, hm) -> None:
        """由 main.py 注入 HotkeyManager 參考"""
        self._hotkey_manager = hm

    # ── 延遲 Section ────────────────────────────────────────────────────────
    def _build_delay_section(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        inner.grid_columnconfigure(1, weight=1)

        self._build_slider_row(
            inner,
            row=0,
            label="識別延遲",
            desc="每次識別遊戲畫面的間隔時間",
            config_key="recognition_delay",
            from_=0.1,
            to=5.0,
            default=0.25,
            unit="秒",
            resolution=0.05,
        )

        self._build_slider_row(
            inner,
            row=3,
            label="尋訪刷新等待",
            desc="自動尋訪：按 R 刷新成員列表後，等待成員列表更新的時間",
            config_key="refresh_wait",
            from_=0.5,
            to=5.0,
            default=2.0,
            unit="秒",
            resolution=0.25,
        )

    def _build_slider_row(
        self,
        parent,
        row: int,
        label: str,
        desc: str,
        config_key: str,
        from_: float,
        to: float,
        default: float,
        unit: str,
        resolution: float = 0.1,
    ) -> None:
        # 標籤
        ctk.CTkLabel(
            parent,
            text=label,
            font=ctk.CTkFont(size=13),
            text_color=CLR_TEXT,
            anchor="w",
        ).grid(row=row, column=0, columnspan=4, sticky="w")

        ctk.CTkLabel(
            parent,
            text=desc,
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        ).grid(row=row + 1, column=0, columnspan=4, sticky="w", pady=(1, 6))

        # 數值標籤
        current_val = float(self.cfg.get(config_key, default))
        val_label = ctk.CTkLabel(
            parent,
            text=f"{current_val:.2f} {unit}",
            font=ctk.CTkFont(size=12),
            text_color=CLR_ACCENT,
            width=70,
            anchor="e",
        )
        val_label.grid(row=row + 2, column=0, sticky="e", padx=(0, 8))

        # 滑桿
        slider = ctk.CTkSlider(
            parent,
            from_=from_,
            to=to,
            number_of_steps=int((to - from_) / resolution),
            command=lambda v, k=config_key, lbl=val_label, u=unit: self._on_slider_change(v, k, lbl, u),
        )
        slider.set(current_val)
        slider.grid(row=row + 2, column=1, sticky="ew", padx=(0, 8))

        # 預設按鈕
        ctk.CTkButton(
            parent,
            text="預設",
            width=56,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#2a3040",
            hover_color="#3a4050",
            command=lambda k=config_key, s=slider, lbl=val_label, d=default, u=unit: self._reset_slider(k, s, lbl, d, u),
        ).grid(row=row + 2, column=2, padx=(0, 4))

        # 範圍提示
        ctk.CTkLabel(
            parent,
            text=f"({from_}～{to}{unit})",
            font=ctk.CTkFont(size=10),
            text_color=CLR_TEXT_DIM,
        ).grid(row=row + 2, column=3, sticky="w")

    def _on_slider_change(self, value: float, config_key: str, label: ctk.CTkLabel, unit: str) -> None:
        rounded = round(value, 2)
        label.configure(text=f"{rounded:.2f} {unit}")
        self.cfg.set(config_key, rounded)

    def _reset_slider(
        self,
        config_key: str,
        slider: ctk.CTkSlider,
        label: ctk.CTkLabel,
        default: float,
        unit: str,
    ) -> None:
        slider.set(default)
        label.configure(text=f"{default:.2f} {unit}")
        self.cfg.set(config_key, default)

    # ── HDR Section ─────────────────────────────────────────────────────────
    def _build_hdr_section(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        inner.grid_columnconfigure(0, weight=1)

        row_frame = ctk.CTkFrame(inner, fg_color="transparent")
        row_frame.grid(row=0, column=0, sticky="ew")
        row_frame.grid_columnconfigure(0, weight=1)

        text_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        text_frame.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            text_frame,
            text="HDR 補償",
            font=ctk.CTkFont(size=13),
            text_color=CLR_TEXT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_frame,
            text="啟用時對截圖套用 gamma 還原，改善 HDR 螢幕下的識別準確度",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        hdr_val = self.cfg.get("hdr_mode", False)
        self._hdr_switch = ctk.CTkSwitch(
            row_frame,
            text="",
            command=self._on_hdr_toggle,
            onvalue=True,
            offvalue=False,
        )
        if hdr_val:
            self._hdr_switch.select()
        else:
            self._hdr_switch.deselect()
        self._hdr_switch.grid(row=0, column=1, padx=(12, 0))

    def _on_hdr_toggle(self) -> None:
        val = self._hdr_switch.get()
        self.cfg.set("hdr_mode", bool(val))
