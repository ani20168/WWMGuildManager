# -*- coding: utf-8 -*-
"""
識別區域視覺化調整視窗。

使用方式：
    from ui.recognition_zone_editor import open_zone_editor
    open_zone_editor(parent_widget, app_controller, config_manager, mode="kick")

mode:
    "kick"  → 智慧踢人識別區域
    "visit" → 自動尋訪識別區域
"""
from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
from typing import Any

import customtkinter as ctk

# PIL 用於半透明疊圖
try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# ── 顏色常數 ────────────────────────────────────────────────────────────────
_CLR_BG     = "#0f1520"
_CLR_CARD   = "#161b27"
_CLR_BORDER = "#2a2d3e"
_CLR_TEXT   = "#e0e0e0"
_CLR_DIM    = "#888888"
_CLR_ACCENT = "#4a9eff"

# ── 踢人頁區域定義 ────────────────────────────────────────────────────────────
# color: (R, G, B)  用於繪製識別框與圖例
KICK_ZONE_DEFS = {
    "y_key_prefix": "kick_zones",
    "y1r_default":  0.18,
    "y2r_default":  0.83,
    "columns": [
        {
            "label":      "名稱",
            "color":      (74, 144, 255),
            "key_x1":     "kick_zones.name_x1",
            "key_x2":     "kick_zones.name_x2",
            "default_x1": 0.07,
            "default_x2": 0.19,
        },
        {
            "label":      "職位",
            "color":      (80, 200, 120),
            "key_x1":     "kick_zones.role_x1",
            "key_x2":     "kick_zones.role_x2",
            "default_x1": 0.19,
            "default_x2": 0.35,
        },
        {
            "label":      "本週活躍度",
            "color":      (255, 160, 0),
            "key_x1":     "kick_zones.contribution_x1",
            "key_x2":     "kick_zones.contribution_x2",
            "default_x1": 0.40,
            "default_x2": 0.53,
        },
    ],
}

# ── 尋訪頁區域定義 ────────────────────────────────────────────────────────────
VISIT_ZONE_DEFS = {
    "y_key_prefix": "visit_zones",
    "y1r_default":  0.12,
    "y2r_default":  0.97,
    "columns": [
        {
            "label":      "名稱",
            "color":      (74, 144, 255),
            "key_x1":     "visit_zones.name_x1",
            "key_x2":     "visit_zones.name_x2",
            "default_x1": 0.03,
            "default_x2": 0.21,
        },
        {
            "label":      "等級",
            "color":      (80, 200, 120),
            "key_x1":     "visit_zones.level_x1",
            "key_x2":     "visit_zones.level_x2",
            "default_x1": 0.22,
            "default_x2": 0.33,
        },
        {
            "label":      "造詣",
            "color":      (255, 160, 0),
            "key_x1":     "visit_zones.power_x1",
            "key_x2":     "visit_zones.power_x2",
            "default_x1": 0.30,
            "default_x2": 0.48,
        },
        {
            "label":      "常用語言",
            "color":      (220, 80, 80),
            "key_x1":     "visit_zones.lang_x1",
            "key_x2":     "visit_zones.lang_x2",
            "default_x1": 0.61,
            "default_x2": 0.83,
        },
    ],
}

_DISPLAY_W = 800   # 預覽截圖固定顯示寬度（像素）
_ALPHA_FILL = 70   # 識別框填色透明度（0~255）
_ALPHA_LINE = 220  # 識別框邊框透明度


def open_zone_editor(
    parent: tk.Widget,
    app_controller,
    config_manager,
    mode: str,
) -> None:
    """
    開啟識別區域調整視窗。

    Args:
        parent:         父視窗 (tk.Widget)
        app_controller: AppController 實例
        config_manager: ConfigManager 實例
        mode:           "kick" 或 "visit"
    """
    RecognitionZoneEditor(parent, app_controller, config_manager, mode)


class RecognitionZoneEditor(tk.Toplevel):
    """識別區域視覺化調整視窗。"""

    def __init__(
        self,
        parent: tk.Widget,
        app_controller,
        config_manager,
        mode: str,
    ) -> None:
        super().__init__(parent)
        self._app  = app_controller
        self._cfg  = config_manager
        self._mode = mode

        self.configure(bg=_CLR_BG)
        title = "調整踢人識別區域" if mode == "kick" else "調整拜訪識別區域"
        self.title(title)
        self.resizable(False, False)

        # 選擇區域定義
        zone_defs = KICK_ZONE_DEFS if mode == "kick" else VISIT_ZONE_DEFS

        # 深複製 columns，加入目前值 x1 / x2
        self._col_defs: list[dict[str, Any]] = []
        for col in zone_defs["columns"]:
            d = dict(col)
            d["x1"] = float(config_manager.get(col["key_x1"], col["default_x1"]))
            d["x2"] = float(config_manager.get(col["key_x2"], col["default_x2"]))
            self._col_defs.append(d)

        prefix = zone_defs["y_key_prefix"]
        self._y1: float = float(config_manager.get(f"{prefix}.y1r", zone_defs["y1r_default"]))
        self._y2: float = float(config_manager.get(f"{prefix}.y2r", zone_defs["y2r_default"]))
        self._y_prefix = prefix

        # 截圖相關
        self._orig_img: Any = None     # PIL Image (RGB)，原始大小
        self._orig_w: int = 1
        self._orig_h: int = 1
        self._display_pil: Any = None  # PIL Image 縮放後
        self._photo: Any = None        # ImageTk.PhotoImage（防止被 GC）
        self._win_rect: tuple = (0, 0, 0, 0)   # 遊戲視窗螢幕座標 (left,top,right,bottom)
        self._win_rect_valid: bool = False         # GetWindowRect 是否成功
        self._scale: float = 1.0               # 截圖縮放比例（display / orig）

        # 頭像間距（僅踢人模式使用）
        self._avatar_interval: int = int(config_manager.get("member_kick.avatar_interval", 130))
        self._avatar_interval_label: tk.Label | None = None

        # 標籤參考（供動態更新）
        self._y1_label: tk.Label | None = None
        self._y2_label: tk.Label | None = None
        self._col_x1_labels: list[tk.Label] = []
        self._col_x2_labels: list[tk.Label] = []

        self._countdown_val: int = 0
        self._build()
        self._start_countdown()

    # ── 建構 UI ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── 截圖預覽 Canvas ─────────────────────────────────────────────────
        self._canvas = tk.Canvas(
            self,
            bg="#050a12",
            highlightthickness=0,
            cursor="crosshair",
        )
        self._canvas.pack(padx=0, pady=0)

        # ── 控制區（滾動框）────────────────────────────────────────────────
        ctrl_outer = tk.Frame(self, bg=_CLR_CARD)
        ctrl_outer.pack(fill="x", padx=0, pady=0)

        # 圖例
        legend_frame = tk.Frame(ctrl_outer, bg=_CLR_CARD)
        legend_frame.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(
            legend_frame,
            text="圖例：",
            bg=_CLR_CARD, fg=_CLR_DIM,
            font=("Microsoft JhengHei UI", 10),
        ).pack(side="left")

        for col in self._col_defs:
            r, g, b = col["color"]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            tk.Label(
                legend_frame,
                text="■",
                bg=_CLR_CARD, fg=hex_color,
                font=("Microsoft JhengHei UI", 12),
            ).pack(side="left", padx=(4, 0))
            tk.Label(
                legend_frame,
                text=col["label"],
                bg=_CLR_CARD, fg=_CLR_TEXT,
                font=("Microsoft JhengHei UI", 10),
            ).pack(side="left", padx=(1, 8))

        # 分隔線
        tk.Frame(ctrl_outer, bg=_CLR_BORDER, height=1).pack(fill="x", padx=8, pady=(4, 8))

        # ── 共用 Y 邊界 ─────────────────────────────────────────────────────
        y_section = tk.Frame(ctrl_outer, bg=_CLR_CARD)
        y_section.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(
            y_section,
            text="表格 Y 範圍",
            bg=_CLR_CARD, fg=_CLR_ACCENT,
            font=("Microsoft JhengHei UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 4))

        # Y1
        self._y1_label = self._build_adjuster_row(
            y_section, row=1,
            label="Y1（上界）",
            get_val=lambda: self._y1,
            on_minus=lambda: self._adjust_y("y1", -1),
            on_plus= lambda: self._adjust_y("y1", +1),
        )
        # Y2
        self._y2_label = self._build_adjuster_row(
            y_section, row=2,
            label="Y2（下界）",
            get_val=lambda: self._y2,
            on_minus=lambda: self._adjust_y("y2", -1),
            on_plus= lambda: self._adjust_y("y2", +1),
        )

        tk.Frame(ctrl_outer, bg=_CLR_BORDER, height=1).pack(fill="x", padx=8, pady=(4, 8))

        # ── 各欄 X 邊界 ──────────────────────────────────────────────────────
        for ci, col in enumerate(self._col_defs):
            r, g, b = col["color"]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"

            col_section = tk.Frame(ctrl_outer, bg=_CLR_CARD)
            col_section.pack(fill="x", padx=12, pady=(0, 4))

            tk.Label(
                col_section,
                text=f"■ {col['label']} 欄位",
                bg=_CLR_CARD, fg=hex_color,
                font=("Microsoft JhengHei UI", 11, "bold"),
            ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 2))

            idx = ci   # capture loop variable
            lbl_x1 = self._build_adjuster_row(
                col_section, row=1,
                label="X1（左界）",
                get_val=lambda i=idx: self._col_defs[i]["x1"],
                on_minus=lambda i=idx: self._adjust_col_x(i, "x1", -1),
                on_plus= lambda i=idx: self._adjust_col_x(i, "x1", +1),
            )
            lbl_x2 = self._build_adjuster_row(
                col_section, row=2,
                label="X2（右界）",
                get_val=lambda i=idx: self._col_defs[i]["x2"],
                on_minus=lambda i=idx: self._adjust_col_x(i, "x2", -1),
                on_plus= lambda i=idx: self._adjust_col_x(i, "x2", +1),
            )
            self._col_x1_labels.append(lbl_x1)
            self._col_x2_labels.append(lbl_x2)

            if ci < len(self._col_defs) - 1:
                tk.Frame(ctrl_outer, bg=_CLR_BORDER, height=1).pack(fill="x", padx=8, pady=(4, 6))

        # ── 踢人模式：頭像點擊位置調整 ──────────────────────────────────────
        if self._mode == "kick":
            tk.Frame(ctrl_outer, bg=_CLR_BORDER, height=1).pack(fill="x", padx=8, pady=(8, 8))
            self._build_kick_avatar_section(ctrl_outer)

        # ── 底部按鈕 ────────────────────────────────────────────────────────
        tk.Frame(ctrl_outer, bg=_CLR_BORDER, height=1).pack(fill="x", padx=8, pady=(8, 4))

        btn_row = tk.Frame(ctrl_outer, bg=_CLR_CARD)
        btn_row.pack(fill="x", padx=12, pady=(4, 12))

        self._save_btn = ctk.CTkButton(
            btn_row,
            text="儲存並關閉",
            width=120,
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1a4a1a",
            hover_color="#256025",
            command=self._save_and_close,
        )
        self._save_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="重新截圖",
            width=100,
            height=34,
            font=ctk.CTkFont(size=12),
            fg_color="#1e3a5f",
            hover_color="#2a4f80",
            command=self._start_countdown,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="重設預設值",
            width=100,
            height=34,
            font=ctk.CTkFont(size=12),
            fg_color="#2a3040",
            hover_color="#3a4050",
            command=self._reset_defaults,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="取消",
            width=80,
            height=34,
            font=ctk.CTkFont(size=12),
            fg_color="#3a1a1a",
            hover_color="#602525",
            command=self.destroy,
        ).pack(side="left")

    def _build_kick_avatar_section(self, parent: tk.Frame) -> None:
        """踢人模式專用：頭像點擊位置資訊 + 間距調整。"""
        section = tk.Frame(parent, bg=_CLR_CARD)
        section.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(
            section,
            text="🖱 頭像點擊位置",
            bg=_CLR_CARD, fg=_CLR_ACCENT,
            font=("Microsoft JhengHei UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 4))

        # 圖例
        legend_row = tk.Frame(section, bg=_CLR_CARD)
        legend_row.grid(row=1, column=0, columnspan=6, sticky="w", pady=(0, 4))
        tk.Label(legend_row, text="●", bg=_CLR_CARD, fg="#3c8cff",
                 font=("Microsoft JhengHei UI", 13)).pack(side="left")
        tk.Label(legend_row, text="第 1 個（user 設定）",
                 bg=_CLR_CARD, fg=_CLR_DIM,
                 font=("Microsoft JhengHei UI", 10)).pack(side="left", padx=(2, 14))
        tk.Label(legend_row, text="●", bg=_CLR_CARD, fg="#dc3232",
                 font=("Microsoft JhengHei UI", 13)).pack(side="left")
        tk.Label(legend_row, text="第 2~6 個（程式計算）",
                 bg=_CLR_CARD, fg=_CLR_DIM,
                 font=("Microsoft JhengHei UI", 10)).pack(side="left", padx=(2, 0))

        # 目前 avatar_x / avatar_y 資訊
        ax = int(self._cfg.get("member_kick.avatar_x", 0))
        ay = int(self._cfg.get("member_kick.avatar_y", 0))
        pos_text = f"第 1 個頭像：X={ax}  Y={ay}" if (ax > 0 and ay > 0) else "尚未定義頭像座標"

        tk.Label(
            section,
            text=pos_text,
            bg=_CLR_CARD, fg=_CLR_DIM,
            font=("Microsoft JhengHei UI", 10),
        ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(0, 6))

        # 頭像間距調整
        self._avatar_interval_label = self._build_adjuster_row(
            section, row=3,
            label="頭像間距",
            get_val=lambda: self._avatar_interval,
            on_minus=lambda: self._adjust_avatar_interval(-1),
            on_plus= lambda: self._adjust_avatar_interval(+1),
        )

        # 6 個頭像的預計 Y 座標列表
        self._avatar_pos_info = tk.Label(
            section,
            text=self._avatar_pos_info_text(ay),
            bg=_CLR_CARD, fg=_CLR_DIM,
            font=("Consolas", 9),
            justify="left",
            anchor="w",
        )
        self._avatar_pos_info.grid(row=4, column=0, columnspan=6, sticky="w", pady=(4, 0))

    def _avatar_pos_info_text(self, base_y: int) -> str:
        parts = []
        for i in range(6):
            y = base_y + i * self._avatar_interval if base_y > 0 else "—"
            parts.append(f"[{i+1}] Y={y}")
        return "  ".join(parts[:3]) + "\n" + "  ".join(parts[3:])

    def _adjust_avatar_interval(self, direction: int) -> None:
        self._avatar_interval = max(10, self._avatar_interval + direction * 10)
        if self._avatar_interval_label:
            self._avatar_interval_label.configure(text=str(self._avatar_interval))
        ay = int(self._cfg.get("member_kick.avatar_y", 0))
        if hasattr(self, "_avatar_pos_info") and self._avatar_pos_info.winfo_exists():
            self._avatar_pos_info.configure(text=self._avatar_pos_info_text(ay))
        self._redraw()

    def _build_adjuster_row(
        self,
        parent: tk.Frame,
        row: int,
        label: str,
        get_val,
        on_minus,
        on_plus,
    ) -> tk.Label:
        """建立單行調整控制項（標籤、◀-10px、數值顯示、+10px▶），回傳數值標籤。"""
        tk.Label(
            parent,
            text=label,
            bg=_CLR_CARD, fg=_CLR_DIM,
            font=("Microsoft JhengHei UI", 10),
            width=10, anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=(0, 6))

        minus_btn = tk.Button(
            parent,
            text="◀ -10px",
            bg="#1e2738", fg=_CLR_TEXT,
            activebackground="#2a3448", activeforeground=_CLR_TEXT,
            relief="flat",
            font=("Microsoft JhengHei UI", 10),
            command=on_minus,
            cursor="hand2",
        )
        minus_btn.grid(row=row, column=1, padx=(0, 4))

        raw = get_val()
        display = str(raw) if isinstance(raw, int) else f"{raw:.4f}"
        val_label = tk.Label(
            parent,
            text=display,
            bg=_CLR_CARD, fg=_CLR_ACCENT,
            font=("Consolas", 11, "bold"),
            width=7, anchor="center",
        )
        val_label.grid(row=row, column=2, padx=(0, 4))

        plus_btn = tk.Button(
            parent,
            text="+10px ▶",
            bg="#1e2738", fg=_CLR_TEXT,
            activebackground="#2a3448", activeforeground=_CLR_TEXT,
            relief="flat",
            font=("Microsoft JhengHei UI", 10),
            command=on_plus,
            cursor="hand2",
        )
        plus_btn.grid(row=row, column=3, padx=(0, 0))

        return val_label

    # ── 截圖擷取與 Canvas 繪製 ───────────────────────────────────────────────

    _COUNTDOWN_SECS = 3  # 倒數秒數

    def _start_countdown(self) -> None:
        """開始倒數，結束後自動截圖。倒數期間 Canvas 顯示提示文字。"""
        # 若上一次倒數還在跑，重置計數器即可（after 回調會自行處理）
        self._countdown_val = self._COUNTDOWN_SECS
        self._canvas.configure(width=_DISPLAY_W, height=160)
        self._canvas.delete("all")
        self._do_countdown_tick()

    def _do_countdown_tick(self) -> None:
        if not self.winfo_exists():
            return
        n = self._countdown_val
        self._canvas.delete("all")
        self._canvas.configure(width=_DISPLAY_W, height=160)
        if n > 0:
            self._canvas.create_text(
                _DISPLAY_W // 2, 60,
                text=f"請切換至遊戲視窗",
                fill=_CLR_TEXT,
                font=("Microsoft JhengHei UI", 14),
            )
            self._canvas.create_text(
                _DISPLAY_W // 2, 100,
                text=f"{n} 秒後自動截圖...",
                fill="#ffcc44",
                font=("Microsoft JhengHei UI", 18, "bold"),
            )
            self._countdown_val -= 1
            self.after(1000, self._do_countdown_tick)
        else:
            self._capture_screenshot()

    def _capture_screenshot(self) -> None:
        """擷取遊戲視窗截圖並顯示在 Canvas 上。"""
        if not _PIL_OK:
            self._show_no_pil_message()
            return

        hwnd = self._app.game_hwnd
        if not hwnd:
            self._show_error_message("未偵測到遊戲視窗（wwm.exe）")
            return

        from core.screen_capture import capture_game_window
        import cv2
        import numpy as np
        import win32gui

        hdr = bool(self._cfg.get("hdr_mode", False))
        img_bgr = capture_game_window(hwnd, hdr_mode=hdr, as_gray=False)
        if img_bgr is None:
            self._show_error_message("截圖失敗，請確認遊戲視窗可見")
            return

        # 轉為 RGB PIL Image
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        self._orig_img = Image.fromarray(img_rgb)
        self._orig_w, self._orig_h = self._orig_img.size

        # 記錄視窗螢幕座標（供頭像位置換算用）
        try:
            self._win_rect = win32gui.GetWindowRect(hwnd)
            self._win_rect_valid = True
        except Exception:
            self._win_rect = (0, 0, 0, 0)
            self._win_rect_valid = False

        # 縮放至顯示寬度 800px
        self._scale = _DISPLAY_W / self._orig_w
        disp_h = int(self._orig_h * self._scale)
        self._display_pil = self._orig_img.resize((_DISPLAY_W, disp_h), Image.LANCZOS)

        # 調整 Canvas 大小
        self._canvas.configure(width=_DISPLAY_W, height=disp_h)

        self._redraw()

        # 截圖完成後將焦點強制拉回調整視窗
        self._force_foreground()

    def _force_foreground(self) -> None:
        """繞過 Windows 焦點保護，強制將視窗帶到最上層。"""
        try:
            import win32gui
            import win32con
            hwnd = self.winfo_id()
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )
        except Exception:
            self.lift()
        self.focus_force()

    def _show_error_message(self, msg: str) -> None:
        """截圖失敗時在 Canvas 上顯示訊息。"""
        self._canvas.configure(width=_DISPLAY_W, height=160)
        self._canvas.create_text(
            _DISPLAY_W // 2, 80,
            text=f"⚠ {msg}",
            fill="#ff8888",
            font=("Microsoft JhengHei UI", 13),
        )

    def _show_no_pil_message(self) -> None:
        self._show_error_message("需要安裝 Pillow（pip install Pillow）才能使用此功能")

    def _redraw(self) -> None:
        """重新繪製 Canvas 上的識別區域疊圖。"""
        if self._display_pil is None or not _PIL_OK:
            return

        disp_w, disp_h = self._display_pil.size

        # 建立 RGBA overlay
        overlay = Image.new("RGBA", (disp_w, disp_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        y1_px = int(self._y1 * disp_h)
        y2_px = int(self._y2 * disp_h)

        for col in self._col_defs:
            x1_px = int(col["x1"] * disp_w)
            x2_px = int(col["x2"] * disp_w)
            r, g, b = col["color"]
            draw.rectangle(
                [x1_px, y1_px, x2_px, y2_px],
                fill=(r, g, b, _ALPHA_FILL),
                outline=(r, g, b, _ALPHA_LINE),
                width=2,
            )
            draw.text(
                (x1_px + 3, y1_px + 3),
                col["label"],
                fill=(r, g, b, 240),
            )

        # ── 踢人模式：頭像點擊位置標記 ──────────────────────────────────────
        if self._mode == "kick" and self._win_rect_valid:
            ax = int(self._cfg.get("member_kick.avatar_x", 0))
            ay = int(self._cfg.get("member_kick.avatar_y", 0))
            if ax > 0 and ay > 0:
                win_left = self._win_rect[0]
                win_top  = self._win_rect[1]
                disp_ax  = (ax - win_left) * self._scale
                r = 7   # 圓形半徑
                for i in range(6):
                    disp_ay = (ay - win_top + i * self._avatar_interval) * self._scale
                    # 第 1 個：藍色實心圓；2~6：紅色實心圓
                    if i == 0:
                        fill_color    = (60, 140, 255, 210)
                        outline_color = (180, 220, 255, 240)
                    else:
                        fill_color    = (220, 50, 50, 180)
                        outline_color = (255, 160, 160, 240)
                    draw.ellipse(
                        [(disp_ax - r, disp_ay - r), (disp_ax + r, disp_ay + r)],
                        fill=fill_color,
                        outline=outline_color,
                        width=2,
                    )
                    # 中心數字標籤
                    draw.text(
                        (disp_ax - 3, disp_ay - 6),
                        str(i + 1),
                        fill=(255, 255, 255, 240),
                    )

        # 合成
        base = self._display_pil.convert("RGBA")
        result = Image.alpha_composite(base, overlay).convert("RGB")
        self._photo = ImageTk.PhotoImage(result)

        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)

    # ── 數值調整 ─────────────────────────────────────────────────────────────

    def _adjust_y(self, which: str, direction: int) -> None:
        """調整 Y 邊界（+1 = +10px，-1 = -10px）。"""
        delta = direction * 10 / max(self._orig_h, 1)
        if which == "y1":
            self._y1 = max(0.0, min(self._y2 - 0.01, self._y1 + delta))
            if self._y1_label:
                self._y1_label.configure(text=f"{self._y1:.4f}")
        else:
            self._y2 = max(self._y1 + 0.01, min(1.0, self._y2 + delta))
            if self._y2_label:
                self._y2_label.configure(text=f"{self._y2:.4f}")
        self._redraw()

    def _adjust_col_x(self, col_idx: int, which: str, direction: int) -> None:
        """調整指定欄位 X 邊界（+1 = +10px，-1 = -10px）。"""
        col = self._col_defs[col_idx]
        delta = direction * 10 / max(self._orig_w, 1)
        if which == "x1":
            col["x1"] = max(0.0, min(col["x2"] - 0.005, col["x1"] + delta))
            lbl = self._col_x1_labels[col_idx] if col_idx < len(self._col_x1_labels) else None
            if lbl:
                lbl.configure(text=f"{col['x1']:.4f}")
        else:
            col["x2"] = max(col["x1"] + 0.005, min(1.0, col["x2"] + delta))
            lbl = self._col_x2_labels[col_idx] if col_idx < len(self._col_x2_labels) else None
            if lbl:
                lbl.configure(text=f"{col['x2']:.4f}")
        self._redraw()

    # ── 儲存 / 重設 ──────────────────────────────────────────────────────────

    def _save_and_close(self) -> None:
        """將當前數值存入 config_manager 後關閉視窗。"""
        prefix = self._y_prefix
        self._cfg.set(f"{prefix}.y1r", round(self._y1, 6))
        self._cfg.set(f"{prefix}.y2r", round(self._y2, 6))
        for col in self._col_defs:
            self._cfg.set(col["key_x1"], round(col["x1"], 6))
            self._cfg.set(col["key_x2"], round(col["x2"], 6))
        if self._mode == "kick":
            self._cfg.set("member_kick.avatar_interval", self._avatar_interval)
        self.destroy()

    def _reset_defaults(self) -> None:
        """將所有數值重設為定義中的預設值。"""
        zone_defs = KICK_ZONE_DEFS if self._mode == "kick" else VISIT_ZONE_DEFS
        self._y1 = zone_defs["y1r_default"]
        self._y2 = zone_defs["y2r_default"]
        if self._y1_label:
            self._y1_label.configure(text=f"{self._y1:.4f}")
        if self._y2_label:
            self._y2_label.configure(text=f"{self._y2:.4f}")
        for ci, col_def in enumerate(self._col_defs):
            col_def["x1"] = col_def["default_x1"]
            col_def["x2"] = col_def["default_x2"]
            if ci < len(self._col_x1_labels):
                self._col_x1_labels[ci].configure(text=f"{col_def['x1']:.4f}")
            if ci < len(self._col_x2_labels):
                self._col_x2_labels[ci].configure(text=f"{col_def['x2']:.4f}")
        if self._mode == "kick":
            self._avatar_interval = 130
            if self._avatar_interval_label:
                self._avatar_interval_label.configure(text="130")
            ay = int(self._cfg.get("member_kick.avatar_y", 0))
            if hasattr(self, "_avatar_pos_info") and self._avatar_pos_info.winfo_exists():
                self._avatar_pos_info.configure(text=self._avatar_pos_info_text(ay))
        self._redraw()
