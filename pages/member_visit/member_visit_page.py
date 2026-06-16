# -*- coding: utf-8 -*-
"""
自動尋訪成員分頁。
- 等級／常用語言篩選框
- 識別結果表格（ttk.Treeview 深色樣式）
- 操作日誌
- 執行狀態列
"""
from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
import datetime

import customtkinter as ctk

from pages.base_page import BasePage
from pages.member_visit.recognizer import MemberRecognizer, PlayerInfo

CLR_CARD = "#161b27"
CLR_BORDER = "#2a2d3e"
CLR_TEXT = "#e0e0e0"
CLR_TEXT_DIM = "#888888"
CLR_ACCENT = "#4a9eff"
CLR_SUCCESS = "#4caf50"
CLR_WARN = "#ff9800"
CLR_ERROR = "#e94560"
CLR_TABLE_BG = "#0f1520"
CLR_TABLE_ROW = "#141c2b"
CLR_TABLE_ROW_ALT = "#0f1520"
CLR_TABLE_SEL = "#1a3a5c"
CLR_TABLE_MATCH = "#1a3a1a"


def _apply_dark_treeview_style(style: ttk.Style) -> None:
    """為 ttk.Treeview 套用深色主題樣式"""
    style.theme_use("clam")
    style.configure(
        "Dark.Treeview",
        background=CLR_TABLE_BG,
        foreground=CLR_TEXT,
        fieldbackground=CLR_TABLE_BG,
        borderwidth=0,
        rowheight=28,
        font=("Microsoft JhengHei UI", 11),
    )
    style.configure(
        "Dark.Treeview.Heading",
        background="#1e2738",
        foreground=CLR_ACCENT,
        borderwidth=0,
        font=("Microsoft JhengHei UI", 11, "bold"),
        relief="flat",
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", CLR_TABLE_SEL)],
        foreground=[("selected", "#ffffff")],
    )
    style.map(
        "Dark.Treeview.Heading",
        background=[("active", "#2a3448")],
    )


class MemberVisitPage(BasePage):
    PAGE_ID = "member_visit"
    PAGE_TITLE = "自動尋訪成員"
    PAGE_ICON = "👥"
    REQUIRES_GAME = True

    def __init__(self, parent, app_controller, config_manager, **kwargs):
        super().__init__(parent, app_controller, config_manager, **kwargs)
        self._is_active = False
        self._recognizer = MemberRecognizer(app_controller, config_manager)
        self._recognizer.on_players_updated = self._on_players_updated
        self._recognizer.on_log = self._on_log
        self._recognizer.on_status = self._on_status

        # 訂閱識別開關
        app_controller.on_recognition_change(self._on_recognition_change)

        self._build()

    # ── 建構 UI ─────────────────────────────────────────────────────────────
    def _build(self) -> None:
        self.configure(fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        # 表格列不再 weight=1，改為固定高度顯示 7 行，不需要捲軸

        # ── 頁面標題 ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            header,
            text="自動尋訪成員",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=CLR_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="自動識別畫面並尋訪符合篩選條件的玩家",
            font=ctk.CTkFont(size=12),
            text_color=CLR_TEXT_DIM,
            anchor="w",
        ).grid(row=1, column=0, sticky="w")

        self._status_label = ctk.CTkLabel(
            header,
            text="● 已停止",
            font=ctk.CTkFont(size=12),
            text_color=CLR_TEXT_DIM,
            anchor="e",
        )
        self._status_label.grid(row=0, column=1, sticky="e")

        # ── 篩選 + 操作區 ───────────────────────────────────────────────────
        ctrl_card = ctk.CTkFrame(self, fg_color=CLR_CARD, corner_radius=10, border_width=1, border_color=CLR_BORDER)
        ctrl_card.grid(row=1, column=0, sticky="ew", padx=24, pady=12)
        ctrl_card.grid_columnconfigure(1, weight=1)
        ctrl_card.grid_columnconfigure(3, weight=1)
        self._build_filter_section(ctrl_card)

        # ── 表格 ────────────────────────────────────────────────────────────
        table_frame = ctk.CTkFrame(self, fg_color=CLR_CARD, corner_radius=10, border_width=1, border_color=CLR_BORDER)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 8))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)
        self._build_table(table_frame)

        # ── 日誌 ────────────────────────────────────────────────────────────
        log_frame = ctk.CTkFrame(self, fg_color=CLR_CARD, corner_radius=10, border_width=1, border_color=CLR_BORDER)
        log_frame.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 8))
        log_frame.grid_columnconfigure(0, weight=1)
        self._build_log_section(log_frame)


    def _build_filter_section(self, card: ctk.CTkFrame) -> None:
        pad = {"padx": 12, "pady": 12}

        ctk.CTkLabel(
            card,
            text="篩選條件",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=CLR_ACCENT,
        ).grid(row=0, column=0, columnspan=6, sticky="w", padx=12, pady=(10, 4))

        # 等級
        ctk.CTkLabel(card, text="最低等級：", font=ctk.CTkFont(size=12), text_color=CLR_TEXT).grid(
            row=1, column=0, sticky="w", padx=(12, 4), pady=(0, 10)
        )
        saved_level = self.cfg.get("member_visit.filter_level", "")
        self._level_entry = ctk.CTkEntry(
            card,
            placeholder_text="留空=不限",
            width=90,
            font=ctk.CTkFont(size=12),
        )
        if saved_level:
            self._level_entry.insert(0, str(saved_level))
        self._level_entry.grid(row=1, column=1, sticky="w", padx=(0, 20), pady=(0, 10))
        self._level_entry.bind("<FocusOut>", lambda _: self._save_filters())

        # 常用語言
        ctk.CTkLabel(card, text="常用語言：", font=ctk.CTkFont(size=12), text_color=CLR_TEXT).grid(
            row=1, column=2, sticky="w", padx=(0, 4), pady=(0, 10)
        )
        saved_lang = self.cfg.get("member_visit.filter_language", "")
        self._lang_entry = ctk.CTkEntry(
            card,
            placeholder_text="如：中文（留空=不限）",
            width=160,
            font=ctk.CTkFont(size=12),
        )
        if saved_lang:
            self._lang_entry.insert(0, str(saved_lang))
        self._lang_entry.grid(row=1, column=3, sticky="w", padx=(0, 20), pady=(0, 10))
        self._lang_entry.bind("<FocusOut>", lambda _: self._save_filters())

        # 啟動 / 停止按鈕
        self._toggle_btn = ctk.CTkButton(
            card,
            text="▶  開始識別",
            width=120,
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1a4a1a",
            hover_color="#256025",
            command=self._toggle_recognition,
        )
        self._toggle_btn.grid(row=1, column=4, padx=(0, 12), pady=(0, 10))

    def _build_table(self, frame: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            frame,
            text="識別結果",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=CLR_ACCENT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        # Treeview 容器（height=7 已固定列數，不需要捲軸）
        tv_frame = tk.Frame(frame, bg=CLR_TABLE_BG)
        tv_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        tv_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        _apply_dark_treeview_style(style)

        columns = ("name", "level", "power", "status", "language", "match")
        self._tree = ttk.Treeview(
            tv_frame,
            columns=columns,
            show="headings",
            style="Dark.Treeview",
            height=7,   # 固定顯示 7 行，不需要捲軸
        )

        col_cfg = [
            ("name",     "玩家名稱",   160, "w"),
            ("level",    "等級",        70, "center"),
            ("power",    "造詣",        90, "center"),
            ("status",   "線上狀態",   80, "center"),
            ("language", "常用語言",   100, "center"),
            ("match",    "符合篩選",   80, "center"),
        ]
        for col_id, heading, width, anchor in col_cfg:
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, anchor=anchor, stretch=(col_id == "name"))

        # 標記符合條件的行（綠色背景）
        self._tree.tag_configure("match", background=CLR_TABLE_MATCH, foreground="#88ff88")
        self._tree.tag_configure("nomatch", background=CLR_TABLE_ROW)
        self._tree.tag_configure("alt", background=CLR_TABLE_ROW_ALT)

        self._tree.grid(row=0, column=0, sticky="ew")

        # 統計標籤
        self._table_summary_label = ctk.CTkLabel(
            frame,
            text="共 0 位玩家 / 0 位符合條件",
            font=ctk.CTkFont(size=11),
            text_color=CLR_TEXT_DIM,
            anchor="e",
        )
        self._table_summary_label.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 6))

    def _build_log_section(self, frame: ctk.CTkFrame) -> None:
        header_row = ctk.CTkFrame(frame, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            header_row,
            text="操作日誌",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=CLR_ACCENT,
        ).pack(side="left")

        ctk.CTkButton(
            header_row,
            text="清除",
            width=50,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#2a3040",
            hover_color="#3a4050",
            command=self._clear_log,
        ).pack(side="right")

        self._log_box = ctk.CTkTextbox(
            frame,
            height=110,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0f1a",
            text_color=CLR_TEXT,
            state="disabled",
            wrap="word",
        )
        self._log_box.pack(fill="x", padx=8, pady=(0, 8))


    # ── 操作 ────────────────────────────────────────────────────────────────
    def _toggle_recognition(self) -> None:
        self._save_filters()
        self.app.toggle_recognition()
        if self.app.recognition_active and self.app.game_hwnd:
            self.after(300, self._focus_game_window)

    def _focus_game_window(self) -> None:
        """將作業系統焦點切到遊戲視窗。"""
        import win32gui
        try:
            win32gui.SetForegroundWindow(self.app.game_hwnd)
        except Exception:
            pass

    def _on_recognition_change(self, active: bool) -> None:
        """識別狀態變化時更新按鈕文字；只在當前頁面可見時才啟停識別器"""
        if active:
            self._toggle_btn.configure(
                text="■  停止識別",
                fg_color="#4a1a1a",
                hover_color="#602525",
            )
            if self._is_active:
                self._recognizer.start()
        else:
            self._toggle_btn.configure(
                text="▶  開始識別",
                fg_color="#1a4a1a",
                hover_color="#256025",
            )
            if self._is_active:
                self._recognizer.stop()

    def _save_filters(self) -> None:
        level = self._level_entry.get().strip()
        lang = self._lang_entry.get().strip()
        self.cfg.set("member_visit.filter_level", level)
        self.cfg.set("member_visit.filter_language", lang)

    # ── 回呼（從背景執行緒呼叫，需透過 after 切回主執行緒）─────────────────
    def _on_players_updated(self, players: list[PlayerInfo]) -> None:
        self.after(0, self._update_table, players)

    def _on_log(self, msg: str) -> None:
        self.after(0, self._append_log, msg)

    def _on_status(self, status: str) -> None:
        self.after(0, self._update_status, status)

    def _update_table(self, players: list[PlayerInfo]) -> None:
        from pages.member_visit.recognizer import MIN_PLAYERS_BEFORE_ACTION

        # 清除舊資料
        for item in self._tree.get_children():
            self._tree.delete(item)

        matched_count = 0
        valid_count = sum(1 for p in players if p.level > 0 or p.power > 0)

        for i, p in enumerate(players):
            tag = "match" if p.matches_filter else ("alt" if i % 2 == 0 else "nomatch")
            match_text = "✅ 符合" if p.matches_filter else "—"
            if p.matches_filter:
                matched_count += 1

            self._tree.insert(
                "",
                "end",
                values=(
                    p.name if p.name else "（未識別）",
                    f"{p.level}級" if p.level else "—",
                    str(p.power) if p.power else "—",
                    p.status or "—",
                    p.language or "—",
                    match_text,
                ),
                tags=(tag,),
            )

        total = len(players)
        if valid_count < MIN_PLAYERS_BEFORE_ACTION:
            summary = (
                f"⚠ 有效玩家 {valid_count} / {MIN_PLAYERS_BEFORE_ACTION}（不足，暫停邀請）"
            )
            self._table_summary_label.configure(text=summary, text_color=CLR_WARN)
        else:
            self._table_summary_label.configure(
                text=f"共 {total} 位玩家 / {matched_count} 位符合條件",
                text_color=CLR_TEXT_DIM,
            )


    def _append_log(self, msg: str) -> None:
        from core.log_manager import get_log_manager
        get_log_manager().log(f"[MemberVisit] {msg}", "INFO")
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"[{now}] {msg}\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _update_status(self, status: str) -> None:
        color_map = {
            "識別中...": CLR_SUCCESS,
            "已停止": CLR_TEXT_DIM,
            "等待中": CLR_WARN,
        }
        color = CLR_TEXT
        for key, clr in color_map.items():
            if key in status:
                color = clr
                break
        self._status_label.configure(text=f"● {status}", text_color=color)

    def _clear_log(self) -> None:
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    # ── 生命週期 ─────────────────────────────────────────────────────────────
    def on_show(self) -> None:
        self._save_filters()
        self._is_active = True
        if self.app.recognition_active:
            self._recognizer.start()

    def on_hide(self) -> None:
        self._is_active = False
        self._recognizer.stop()
