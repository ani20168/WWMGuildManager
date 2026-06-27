# -*- coding: utf-8 -*-
"""
首頁：
  - 遊戲視窗狀態顯示
  - 快捷鍵設定
  - 識別延遲滑桿
  - HDR 補償開關
  - OCR 測試
"""
from __future__ import annotations
import os
import sys
import threading
import customtkinter as ctk

from pages.base_page import BasePage

_HERE = os.path.dirname(os.path.abspath(__file__))


def _external_path(relative: str) -> str:
    """取得不打包進 exe 的外部資源路徑（與 exe 同層目錄）。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # pages/home/ -> project root（上兩層）
        base = os.path.normpath(os.path.join(_HERE, "..", ".."))
    return os.path.normpath(os.path.join(base, relative))

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

        # ── 識別區域調整 ────────────────────────────────────────────────────
        row = self._build_card(
            scroll, row,
            title="識別區域調整",
            builder=self._build_zone_adjust_section,
        )

        # ── 模型設定 ────────────────────────────────────────────────────────
        row = self._build_card(
            scroll, row,
            title="模型設定",
            builder=self._build_model_section,
        )

        # ── OCR 測試 ────────────────────────────────────────────────────────
        row = self._build_card(
            scroll, row,
            title="OCR 測試",
            builder=self._build_ocr_test_section,
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
        self._refresh_zone_buttons_state(found)

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

        self._build_slider_row(
            inner,
            row=6,
            label="踢出確認延遲",
            desc="智慧踢人：點擊踢出按鈕後，等待確認彈窗出現的時間",
            config_key="member_kick.confirm_delay",
            from_=0.2,
            to=3.0,
            default=1.5,
            unit="秒",
            resolution=0.1,
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

    # ── 識別區域調整 Section ────────────────────────────────────────────────
    def _build_zone_adjust_section(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        inner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            inner,
            text="視覺化調整各功能頁的 OCR 識別框位置。需要偵測到遊戲視窗（wwm.exe）才能截圖。",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="w",
            wraplength=600,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="w")

        game_found = self.app.game_found

        self._zone_kick_btn = ctk.CTkButton(
            btn_row,
            text="🗡 調整踢人識別區域",
            width=170,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1e3a5f",
            hover_color="#2a4f80",
            state="normal" if game_found else "disabled",
            command=self._open_kick_zone_editor,
        )
        self._zone_kick_btn.pack(side="left", padx=(0, 10))

        self._zone_visit_btn = ctk.CTkButton(
            btn_row,
            text="🌿 調整尋訪清單識別區域",
            width=170,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1e3a5f",
            hover_color="#2a4f80",
            state="normal" if game_found else "disabled",
            command=self._open_visit_zone_editor,
        )
        self._zone_visit_btn.pack(side="left")

        self._zone_hint_label = ctk.CTkLabel(
            inner,
            text="（請先啟動遊戲）" if not game_found else "",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        )
        self._zone_hint_label.grid(row=2, column=0, sticky="w", pady=(6, 0))

    def _refresh_zone_buttons_state(self, found: bool) -> None:
        """遊戲視窗狀態變更時同步更新按鈕啟用/停用。"""
        if not hasattr(self, "_zone_kick_btn"):
            return
        state = "normal" if found else "disabled"
        self._zone_kick_btn.configure(state=state)
        self._zone_visit_btn.configure(state=state)
        self._zone_hint_label.configure(text="" if found else "（請先啟動遊戲）")

    def _open_kick_zone_editor(self) -> None:
        from ui.recognition_zone_editor import open_zone_editor
        open_zone_editor(self, self.app, self.cfg, mode="kick")

    def _open_visit_zone_editor(self) -> None:
        from ui.recognition_zone_editor import open_zone_editor
        open_zone_editor(self, self.app, self.cfg, mode="visit")

    # ── 模型設定 Section ────────────────────────────────────────────────────
    def _build_model_section(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        inner.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            inner,
            text="批次大小（batch_size）",
            font=ctk.CTkFont(size=13),
            text_color=CLR_TEXT,
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, sticky="w")

        ctk.CTkLabel(
            inner,
            text="Recognizer 每次處理的文字框數，較大值可提升速度但增加記憶體使用量",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(1, 6))

        current_bs = int(self.cfg.get("ocr_batch_size", 1))

        bs_val_label = ctk.CTkLabel(
            inner,
            text=str(current_bs),
            font=ctk.CTkFont(size=12),
            text_color=CLR_ACCENT,
            width=70,
            anchor="e",
        )
        bs_val_label.grid(row=2, column=0, sticky="e", padx=(0, 8))

        bs_slider = ctk.CTkSlider(
            inner,
            from_=1,
            to=16,
            number_of_steps=15,
            command=lambda v, lbl=bs_val_label: self._on_batch_size_change(v, lbl),
        )
        bs_slider.set(current_bs)
        bs_slider.grid(row=2, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            inner,
            text="預設",
            width=56,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#2a3040",
            hover_color="#3a4050",
            command=lambda s=bs_slider, lbl=bs_val_label: self._reset_batch_size(s, lbl),
        ).grid(row=2, column=2, padx=(0, 4))

        ctk.CTkLabel(
            inner,
            text="(1～16)",
            font=ctk.CTkFont(size=10),
            text_color=CLR_TEXT_DIM,
        ).grid(row=2, column=3, sticky="w")

    def _on_batch_size_change(self, value: float, label: ctk.CTkLabel) -> None:
        v = max(1, int(round(value)))
        label.configure(text=str(v))
        self.cfg.set("ocr_batch_size", v)

    def _reset_batch_size(self, slider: ctk.CTkSlider, label: ctk.CTkLabel) -> None:
        slider.set(1)
        label.configure(text="1")
        self.cfg.set("ocr_batch_size", 1)

    # ── OCR 測試 Section ────────────────────────────────────────────────────
    def _build_ocr_test_section(self, card: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        inner.grid_columnconfigure(0, weight=1)

        # 說明文字
        ctk.CTkLabel(
            inner,
            text="使用測試圖片（images/member_kick/member_list_example.png）驗證 EasyOCR 是否正常運作",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="w",
            wraplength=600,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        # 按鈕 + 狀態列
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._ocr_test_btn = ctk.CTkButton(
            btn_row,
            text="測試",
            width=80,
            height=30,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1e3a5f",
            hover_color="#2a4f80",
            command=self._start_ocr_test,
        )
        self._ocr_test_btn.pack(side="left")

        self._ocr_status_label = ctk.CTkLabel(
            btn_row,
            text="尚未測試",
            font=ctk.CTkFont(size=12),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        )
        self._ocr_status_label.pack(side="left", padx=(12, 0))

        # 操作日誌文字框（唯讀）
        self._ocr_log_box = ctk.CTkTextbox(
            inner,
            height=150,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0f1a",
            text_color=CLR_TEXT,
            state="disabled",
            wrap="word",
        )
        self._ocr_log_box.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _ocr_log(self, msg: str) -> None:
        """寫入 OCR 測試日誌框，同時寫入 LogManager。需在主執行緒呼叫。"""
        from core.log_manager import get_log_manager
        get_log_manager().log(f"[OCRTest] {msg}", "INFO")
        self._ocr_log_box.configure(state="normal")
        self._ocr_log_box.insert("end", f"{msg}\n")
        self._ocr_log_box.see("end")
        self._ocr_log_box.configure(state="disabled")

    def _ocr_log_from_thread(self, msg: str) -> None:
        """從背景執行緒安全地寫入 OCR 日誌框（透過 after 排程至主執行緒）。"""
        self.after(0, self._ocr_log, msg)

    def _ocr_set_status(self, text: str, color: str) -> None:
        """設定狀態標籤，需在主執行緒呼叫。"""
        self._ocr_status_label.configure(text=text, text_color=color)

    def _start_ocr_test(self) -> None:
        """按下「測試」按鈕：清空日誌、禁用按鈕、啟動背景執行緒。"""
        self._ocr_test_btn.configure(state="disabled")
        self._ocr_log_box.configure(state="normal")
        self._ocr_log_box.delete("1.0", "end")
        self._ocr_log_box.configure(state="disabled")
        self._ocr_set_status("測試中...", CLR_TEXT_DIM)

        t = threading.Thread(target=self._run_ocr_test, daemon=True)
        t.start()

    def _run_ocr_test(self) -> None:
        """OCR 測試主流程（在背景執行緒執行）。"""
        try:
            # 步驟 a：初始化 OCR 引擎
            self._ocr_log_from_thread("正在初始化 OCR 引擎...")
            import easyocr
            import torch
            use_gpu = torch.cuda.is_available()
            self._ocr_log_from_thread(f"運算模式：{'GPU (' + torch.cuda.get_device_name(0) + ')' if use_gpu else 'CPU（未偵測到 CUDA GPU）'}")
            reader = easyocr.Reader(["ch_tra", "en"], gpu=use_gpu, verbose=False)
            self._ocr_log_from_thread("OCR 引擎載入完成")

            # 步驟 d：讀取測試圖片
            self._ocr_log_from_thread("正在讀取測試圖片...")
            import time
            import numpy as np
            from PIL import Image as _PILImage
            img_path = _external_path(
                os.path.join("images", "member_kick", "member_list_example.png")
            )
            if not os.path.exists(img_path):
                raise FileNotFoundError(f"找不到測試圖片：{img_path}")
            self._ocr_log_from_thread(f"圖片路徑：{img_path}")
            img_array = np.array(_PILImage.open(img_path).convert("RGB"))
            self._ocr_log_from_thread("圖片已載入，正在識別內容...")

            # 步驟 f：執行 OCR 識別（此時才開始計時）
            _t_start = time.perf_counter()
            results = reader.readtext(img_array, detail=0, batch_size=int(self.cfg.get("ocr_batch_size", 1)))
            _elapsed = time.perf_counter() - _t_start

            # 步驟 h/i：處理結果
            if results:
                count = len(results)
                self.after(
                    0, self._ocr_set_status, "✓ OCR 測試成功", CLR_SUCCESS
                )
                self._ocr_log_from_thread(f"識別成功，共識別到 {count} 個文字區塊")
                self._ocr_log_from_thread(f"識別花費時間：{_elapsed:.2f} 秒")
                preview = results[:5]
                self._ocr_log_from_thread(f"識別內容（前5項）: {preview}")
            else:
                self.after(
                    0, self._ocr_set_status, "✗ OCR 無法識別任何內容", CLR_ERROR
                )
                self._ocr_log_from_thread("OCR 識別完成，但未識別到任何文字")

        except Exception as exc:
            err_msg = str(exc)
            self.after(
                0, self._ocr_set_status, f"✗ 錯誤: {err_msg[:60]}", CLR_ERROR
            )
            self._ocr_log_from_thread(f"錯誤詳情：{err_msg}")
        finally:
            self.after(0, lambda: self._ocr_test_btn.configure(state="normal"))
