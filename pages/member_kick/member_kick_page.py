# -*- coding: utf-8 -*-
"""
智慧踢人分頁。

功能：
  - 識別成員列表中的玩家名稱與本週活躍度
  - 活躍度 ≤ 設定閾值時，點擊第一個玩家頭像座標（需事先定義）
  - 倒數擷取頭像座標（以滑鼠停留位置為準）

注意：使用前請在遊戲中將成員列表依「本週活躍度」由低到高排序。
"""
from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
import datetime

import customtkinter as ctk

from pages.base_page import BasePage
from pages.member_kick.kick_recognizer import MemberKickRecognizer, KickPlayerInfo

CLR_CARD       = "#161b27"
CLR_BORDER     = "#2a2d3e"
CLR_TEXT       = "#e0e0e0"
CLR_TEXT_DIM   = "#888888"
CLR_ACCENT     = "#4a9eff"
CLR_SUCCESS    = "#4caf50"
CLR_WARN       = "#ff9800"
CLR_ERROR      = "#e94560"
CLR_TABLE_BG   = "#0f1520"
CLR_TABLE_ROW  = "#141c2b"
CLR_TABLE_ALT  = "#0f1520"
CLR_TABLE_SEL  = "#1a3a5c"
CLR_TABLE_KICK = "#3a1a1a"   # 符合踢出條件的行（紅色調）


def _apply_dark_treeview_style(style: ttk.Style, style_name: str) -> None:
    style.theme_use("clam")
    style.configure(
        style_name,
        background=CLR_TABLE_BG,
        foreground=CLR_TEXT,
        fieldbackground=CLR_TABLE_BG,
        borderwidth=0,
        rowheight=28,
        font=("Microsoft JhengHei UI", 11),
    )
    style.configure(
        f"{style_name}.Heading",
        background="#1e2738",
        foreground=CLR_ACCENT,
        borderwidth=0,
        font=("Microsoft JhengHei UI", 11, "bold"),
        relief="flat",
    )
    style.map(style_name, background=[("selected", CLR_TABLE_SEL)], foreground=[("selected", "#ffffff")])
    style.map(f"{style_name}.Heading", background=[("active", "#2a3448")])


class MemberKickPage(BasePage):
    PAGE_ID      = "member_kick"
    PAGE_TITLE   = "智慧踢人"
    PAGE_ICON    = "⚔"
    REQUIRES_GAME = True

    def __init__(self, parent, app_controller, config_manager, **kwargs):
        super().__init__(parent, app_controller, config_manager, **kwargs)
        self._is_active = False

        self._recognizer = MemberKickRecognizer(app_controller, config_manager)
        self._recognizer.on_players_updated = self._on_players_updated
        self._recognizer.on_log             = self._on_log
        self._recognizer.on_status          = self._on_status
        self._recognizer.on_action_taken    = self._on_action_taken

        app_controller.on_recognition_change(self._on_recognition_change)

        self._countdown_seconds: int = 0
        self._build()

    # ── 建構 UI ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.configure(fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        # 頁面標題
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            header, text="智慧踢人",
            font=ctk.CTkFont(size=22, weight="bold"), text_color=CLR_TEXT, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="識別成員列表並自動點擊低活躍度成員頭像",
            font=ctk.CTkFont(size=12), text_color=CLR_TEXT_DIM, anchor="w",
        ).grid(row=1, column=0, sticky="w")

        self._status_label = ctk.CTkLabel(
            header, text="● 已停止",
            font=ctk.CTkFont(size=12), text_color=CLR_TEXT_DIM, anchor="e",
        )
        self._status_label.grid(row=0, column=1, sticky="e")

        # 注意事項
        notice_card = ctk.CTkFrame(self, fg_color="#1a1a0a", corner_radius=10,
                                   border_width=1, border_color="#3a3a10")
        notice_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 0))
        notice_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            notice_card,
            text="⚠  使用前請先在遊戲中將成員列表依「本週活躍度」由低到高排序，"
                 "確保貢獻最低的成員排在最上方。",
            font=ctk.CTkFont(size=12),
            text_color="#cccc44",
            anchor="w",
            wraplength=700,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=10)

        # 頭像座標設定 + 篩選條件（同一張卡片）
        ctrl_card = ctk.CTkFrame(self, fg_color=CLR_CARD, corner_radius=10,
                                 border_width=1, border_color=CLR_BORDER)
        ctrl_card.grid(row=2, column=0, sticky="ew", padx=24, pady=12)
        ctrl_card.grid_columnconfigure(0, weight=1)
        self._build_control_card(ctrl_card)

        # 識別結果表格
        table_frame = ctk.CTkFrame(self, fg_color=CLR_CARD, corner_radius=10,
                                   border_width=1, border_color=CLR_BORDER)
        table_frame.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 8))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)
        self._build_table(table_frame)

        # 操作日誌
        log_frame = ctk.CTkFrame(self, fg_color=CLR_CARD, corner_radius=10,
                                 border_width=1, border_color=CLR_BORDER)
        log_frame.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 8))
        log_frame.grid_columnconfigure(0, weight=1)
        self._build_log_section(log_frame)


    def _build_control_card(self, card: ctk.CTkFrame) -> None:
        # ── 區塊標題：頭像座標設定 ──────────────────────────────────────────
        ctk.CTkLabel(
            card, text="頭像座標設定",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=CLR_ACCENT, anchor="w",
        ).grid(row=0, column=0, columnspan=6, sticky="w", padx=14, pady=(12, 4))

        avatar_row = ctk.CTkFrame(card, fg_color="transparent")
        avatar_row.grid(row=1, column=0, columnspan=6, sticky="w", padx=14, pady=(0, 10))

        ctk.CTkLabel(
            avatar_row, text="第一個玩家頭像座標：",
            font=ctk.CTkFont(size=12), text_color=CLR_TEXT,
        ).pack(side="left")

        # 座標顯示標籤
        ax = self.cfg.get("member_kick.avatar_x", 0)
        ay = self.cfg.get("member_kick.avatar_y", 0)
        self._avatar_pos_label = ctk.CTkLabel(
            avatar_row,
            text=self._format_avatar_pos(ax, ay),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=CLR_ACCENT if (ax and ay) else CLR_TEXT_DIM,
        )
        self._avatar_pos_label.pack(side="left", padx=(6, 16))

        self._define_btn = ctk.CTkButton(
            avatar_row,
            text="定義頭像位置",
            width=120,
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color="#1e3a5f",
            hover_color="#2a4f80",
            command=self._start_avatar_capture,
        )
        self._define_btn.pack(side="left")

        # 分隔線
        sep = ctk.CTkFrame(card, fg_color=CLR_BORDER, height=1)
        sep.grid(row=2, column=0, columnspan=6, sticky="ew", padx=14, pady=(0, 8))

        # ── 區塊標題：篩選條件 ───────────────────────────────────────────────
        ctk.CTkLabel(
            card, text="篩選條件",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=CLR_ACCENT, anchor="w",
        ).grid(row=3, column=0, columnspan=6, sticky="w", padx=14, pady=(0, 4))

        filter_row = ctk.CTkFrame(card, fg_color="transparent")
        filter_row.grid(row=4, column=0, columnspan=6, sticky="w", padx=14, pady=(0, 12))

        ctk.CTkLabel(
            filter_row, text="貢獻度小於等於：",
            font=ctk.CTkFont(size=12), text_color=CLR_TEXT,
        ).pack(side="left")

        saved_val = self.cfg.get("member_kick.filter_contribution", 500)
        self._contribution_entry = ctk.CTkEntry(
            filter_row,
            width=90,
            font=ctk.CTkFont(size=12),
            placeholder_text="500",
        )
        self._contribution_entry.insert(0, str(saved_val))
        self._contribution_entry.pack(side="left", padx=(0, 8))
        self._contribution_entry.bind("<FocusOut>", lambda _: self._save_filter())

        ctk.CTkLabel(
            filter_row, text="（整數，必填）",
            font=ctk.CTkFont(size=11), text_color=CLR_TEXT_DIM,
        ).pack(side="left", padx=(0, 24))

        # 開始/停止按鈕
        self._toggle_btn = ctk.CTkButton(
            filter_row,
            text="▶  開始識別",
            width=120,
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1a4a1a",
            hover_color="#256025",
            command=self._toggle_recognition,
        )
        self._toggle_btn.pack(side="left")

        # 初始狀態：若未定義頭像位置則停用開始按鈕
        self._refresh_start_btn_state()

    def _build_table(self, frame: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            frame, text="識別結果",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=CLR_ACCENT, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        tv_frame = tk.Frame(frame, bg=CLR_TABLE_BG)
        tv_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        tv_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        _apply_dark_treeview_style(style, "Kick.Treeview")

        columns = ("name", "contribution", "match")
        self._tree = ttk.Treeview(
            tv_frame,
            columns=columns,
            show="headings",
            style="Kick.Treeview",
            height=6,
        )

        col_cfg = [
            ("name",         "玩家名稱",   260, "w"),
            ("contribution", "本週活躍度", 120, "center"),
            ("match",        "符合踢出",    90, "center"),
        ]
        for col_id, heading, width, anchor in col_cfg:
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, anchor=anchor, stretch=(col_id == "name"))

        self._tree.tag_configure("kick",   background=CLR_TABLE_KICK, foreground="#ff8888")
        self._tree.tag_configure("normal", background=CLR_TABLE_ROW)
        self._tree.tag_configure("alt",    background=CLR_TABLE_ALT)
        self._tree.grid(row=0, column=0, sticky="ew")

        self._table_summary_label = ctk.CTkLabel(
            frame, text="共 0 位玩家",
            font=ctk.CTkFont(size=11), text_color=CLR_TEXT_DIM, anchor="e",
        )
        self._table_summary_label.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 6))

    def _build_log_section(self, frame: ctk.CTkFrame) -> None:
        header_row = ctk.CTkFrame(frame, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            header_row, text="操作日誌",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=CLR_ACCENT,
        ).pack(side="left")

        ctk.CTkButton(
            header_row, text="清除", width=50, height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#2a3040", hover_color="#3a4050",
            command=self._clear_log,
        ).pack(side="right")

        self._log_box = ctk.CTkTextbox(
            frame, height=110,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0f1a", text_color=CLR_TEXT,
            state="disabled", wrap="word",
        )
        self._log_box.pack(fill="x", padx=8, pady=(0, 8))

    # ── 頭像座標擷取（倒數計時）─────────────────────────────────────────────

    def _format_avatar_pos(self, x, y) -> str:
        if x and y and int(x) > 0 and int(y) > 0:
            return f"X: {int(x)}  Y: {int(y)}"
        return "未定義"

    def _start_avatar_capture(self) -> None:
        """開始 5 秒倒數，結束後擷取滑鼠座標。"""
        self._define_btn.configure(state="disabled")
        self._countdown_seconds = 5
        self._do_countdown()

    def _do_countdown(self) -> None:
        if self._countdown_seconds > 0:
            self._avatar_pos_label.configure(
                text=f"⏱ 請將滑鼠移至頭像... {self._countdown_seconds}",
                text_color=CLR_WARN,
            )
            self._countdown_seconds -= 1
            self.after(1000, self._do_countdown)
        else:
            import win32api
            x, y = win32api.GetCursorPos()
            self.cfg.set("member_kick.avatar_x", x)
            self.cfg.set("member_kick.avatar_y", y)
            self._avatar_pos_label.configure(
                text=self._format_avatar_pos(x, y),
                text_color=CLR_ACCENT,
            )
            self._define_btn.configure(state="normal")
            self._refresh_start_btn_state()
            self._append_log(f"📍 頭像座標已設定：X={x}, Y={y}")

    def _refresh_start_btn_state(self) -> None:
        """依據頭像是否已定義，決定開始按鈕是否可按。"""
        ax = self.cfg.get("member_kick.avatar_x", 0)
        ay = self.cfg.get("member_kick.avatar_y", 0)
        defined = int(ax) > 0 and int(ay) > 0
        self._toggle_btn.configure(state="normal" if defined else "disabled")

    # ── 識別控制 ─────────────────────────────────────────────────────────────

    def _toggle_recognition(self) -> None:
        if not self._validate_filter():
            return
        self._save_filter()
        self.app.toggle_recognition()

    def _on_recognition_change(self, active: bool) -> None:
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

    def _on_action_taken(self) -> None:
        """識別器完成動作後，從主執行緒停止識別狀態。"""
        self.after(0, self._stop_recognition_ui)

    def _stop_recognition_ui(self) -> None:
        if self.app.recognition_active:
            self.app.toggle_recognition()

    # ── 篩選驗證與儲存 ───────────────────────────────────────────────────────

    def _validate_filter(self) -> bool:
        val = self._contribution_entry.get().strip()
        if not val:
            self._append_log("❌ 貢獻度閾值為必填")
            return False
        try:
            int(val)
        except ValueError:
            self._append_log("❌ 貢獻度閾值必須為整數")
            return False
        return True

    def _save_filter(self) -> None:
        val = self._contribution_entry.get().strip()
        try:
            self.cfg.set("member_kick.filter_contribution", int(val))
        except ValueError:
            pass

    # ── UI 回呼（由背景執行緒透過 after 切回主執行緒）──────────────────────

    def _on_players_updated(self, players: list[KickPlayerInfo]) -> None:
        self.after(0, self._update_table, players)

    def _on_log(self, msg: str) -> None:
        self.after(0, self._append_log, msg)

    def _on_status(self, status: str) -> None:
        self.after(0, self._update_status, status)

    def _update_table(self, players: list[KickPlayerInfo]) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        threshold = int(self.cfg.get("member_kick.filter_contribution", 500))
        kick_count = 0

        for i, p in enumerate(players):
            meets = p.contribution >= 0 and p.contribution <= threshold
            if p.meets_filter:
                meets = True

            tag = "kick" if meets else ("alt" if i % 2 == 0 else "normal")
            match_text = "🔴 踢出" if meets else "—"
            if meets:
                kick_count += 1

            self._tree.insert(
                "", "end",
                values=(
                    p.name if p.name else "（未識別）",
                    str(p.contribution) if p.contribution >= 0 else "—",
                    match_text,
                ),
                tags=(tag,),
            )

        self._table_summary_label.configure(
            text=f"共 {len(players)} 位玩家 / {kick_count} 位符合踢出",
            text_color=CLR_ERROR if kick_count > 0 else CLR_TEXT_DIM,
        )

    def _append_log(self, msg: str) -> None:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"[{now}] {msg}\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _update_status(self, status: str) -> None:
        color_map = {
            "識別中":   CLR_SUCCESS,
            "已停止":   CLR_TEXT_DIM,
            "等待確認": CLR_WARN,
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
        self._save_filter()
        self._refresh_start_btn_state()
        self._is_active = True
        if self.app.recognition_active:
            self._recognizer.start()

    def on_hide(self) -> None:
        self._is_active = False
        self._recognizer.stop()
