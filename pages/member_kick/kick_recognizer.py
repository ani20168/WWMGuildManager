# -*- coding: utf-8 -*-
"""
智慧踢人 — 識別引擎。

識別流程：
  1. 截取遊戲視窗畫面
  2. EasyOCR 識別成員列表（玩家名稱、本週活躍度）
  3. 依 Y 座標排序，取最上方第一列玩家
  4. 若活躍度 ≤ 閾值 → 點擊預定頭像座標 → 等待選單出現（0.8 秒）
  5. 模板匹配找「踢出百業」按鈕 → 點擊 → 按 Space 確認 → 等待 2 秒（名單刷新）
  6. 繼續下一輪識別，直到第一位活躍度 > 閾值（所有低活躍度成員已踢完）或找不到玩家
  7. 識別完全結束後呼叫 on_action_taken callback

注意：需先在遊戲中將成員列表依「本週活躍度」由低到高排序。
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np
import pydirectinput
import win32gui

from core.screen_capture import capture_game_window

pydirectinput.PAUSE = 0.05

# 打包後從 exe 同層目錄讀取（使用者可自行替換圖片）；開發時從專案根目錄讀取
if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(sys.executable)
else:
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IMAGES_DIR        = os.path.join(_ROOT, "images", "member_kick")
KICK_BTN_TEMPLATE = os.path.join(IMAGES_DIR, "kick_button.png")

# ── 表格區域（相對於視窗高度/寬度）─────────────────────────────────────────
# 實測（遊戲視窗）：
#   Header 列 ~15-17%，第一個資料列從 ~18% 開始
#   表格右邊界 ~64%，右側人物詳情面板從 ~65% 開始
Y1R = 0.18   # 跳過 Header 列，從第一筆資料開始
Y2R = 0.83   # 涵蓋全部成員列，避開底部快捷鍵列

# 欄位 X 邊界（相對於視窗寬度）
# 實測：
#   名稱文字 7-18%；職位徽章（社眾/學徒）在 ~21%，需排除
#   本週活躍度「0」資料中心在 ~48%，欄位大致 44-52%
#   右側詳情面板等級圖示在 ~68-70%（舊設定 0.61-0.80 誤判為活躍度的根源）
_COL_NAME_X1         = 0.07
_COL_NAME_X2         = 0.19   # 緊縮上界，排除職位徽章
_COL_CONTRIBUTION_X1 = 0.40   # 本週活躍度欄左界（加寬以涵蓋「0」字符偏移）
_COL_CONTRIBUTION_X2 = 0.53   # 本週活躍度欄右界（避免混入「本週俠境通關」欄）

# OCR 信心閾值
_CONF_NAME         = 0.0
_CONF_CONTRIBUTION = 0.0

# Y 軸分組容忍度（像素）；每列高度在 1080p 約 80-90px，12px 已夠用
_ROW_Y_TOLERANCE = 15

# 表格 Header 關鍵字：出現這些文字的列直接略過
_HEADER_KEYWORDS = {"成員名稱", "職位", "等級", "線上狀態", "本週活躍度", "本週俠境通關"}

# 辨識到玩家但活躍度讀取失敗時，最多重試幾輪
_MAX_RETRY = 3


@dataclass
class KickPlayerInfo:
    name: str = ""
    contribution: int = -1   # -1 = 未識別
    row_y: int = 0
    meets_filter: bool = False


class MemberKickRecognizer:
    def __init__(self, app_controller, config_manager) -> None:
        self._app = app_controller
        self._cfg = config_manager

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._reader = None   # EasyOCR 延遲初始化；False = 載入失敗

        # 模板圖（踢出按鈕）
        self._kick_template: np.ndarray | None = None
        self._load_templates()

        # 回呼
        self.on_players_updated: Callable[[list[KickPlayerInfo]], None] | None = None
        self.on_log:             Callable[[str], None] | None = None
        self.on_status:          Callable[[str], None] | None = None
        self.on_action_taken:    Callable[[], None] | None = None  # 點擊頭像後通知 UI 停止

    def _load_templates(self) -> None:
        if os.path.exists(KICK_BTN_TEMPLATE):
            img = cv2.imread(KICK_BTN_TEMPLATE, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._kick_template = img

    # ── 生命週期 ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._log("識別已啟動")
        self._set_status("識別中...")

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        self._log("識別已停止")
        self._set_status("已停止")

    # ── 內部工具 ─────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self.on_log:
            self.on_log(msg)

    def _set_status(self, msg: str) -> None:
        if self.on_status:
            self.on_status(msg)

    def _init_ocr_reader(self) -> None:
        """延遲初始化 EasyOCR Reader（僅初始化一次）。"""
        if self._reader is not None:
            return
        try:
            import torch
            import easyocr
            use_gpu = torch.cuda.is_available()
            self._log(f"🔧 初始化 EasyOCR（{'GPU' if use_gpu else 'CPU'}）...")
            self._reader = easyocr.Reader(["ch_tra", "en"], gpu=use_gpu, verbose=False)
            self._log("✅ EasyOCR 初始化完成")
        except Exception as e:
            self._reader = False
            self._log(f"❌ EasyOCR 初始化失敗：{e}")

    # ── 主迴圈 ───────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        retry_count = 0   # 活躍度讀取失敗連續次數

        while self._running and not self._stop_event.is_set():
            delay = float(self._cfg.get("recognition_delay", 0.25))
            hdr_mode = bool(self._cfg.get("hdr_mode", False))

            players = self._scan(hdr_mode)

            if players is not None and self.on_players_updated:
                self.on_players_updated(players)

            if not players:
                self._log("⚠ 未識別到任何玩家，識別結束")
                break

            # 取 Y 座標最小（最上方）的玩家
            players.sort(key=lambda p: p.row_y)
            first = players[0]

            threshold = int(self._cfg.get("member_kick.filter_contribution", 500))

            self._log(
                f"📋 第一位：{first.name or '（未識別）'} "
                f"| 活躍度：{first.contribution if first.contribution >= 0 else '未識別'}"
            )

            if first.contribution < 0:
                # 活躍度讀取失敗，重試
                retry_count += 1
                if retry_count >= _MAX_RETRY:
                    self._log(f"⚠ 連續 {_MAX_RETRY} 次無法識別第一位活躍度，停止識別")
                    break
                self._log(f"⚠ 活躍度識別失敗，重試（{retry_count}/{_MAX_RETRY}）...")
                self._stop_event.wait(timeout=delay)
                continue

            retry_count = 0
            first.meets_filter = (first.contribution <= threshold)

            # 更新篩選狀態後再次通知 UI
            if self.on_players_updated:
                self.on_players_updated(players)

            if first.meets_filter:
                avatar_x = int(self._cfg.get("member_kick.avatar_x", 0))
                avatar_y = int(self._cfg.get("member_kick.avatar_y", 0))

                if avatar_x <= 0 or avatar_y <= 0:
                    self._log("❌ 未定義頭像座標，無法執行踢人操作")
                    self._stop_event.wait(timeout=delay)
                    continue

                self._log(
                    f"🎯 {first.name or '（未識別）'} 活躍度 {first.contribution} ≤ {threshold}，"
                    f"點擊頭像座標 ({avatar_x}, {avatar_y})..."
                )
                pydirectinput.click(avatar_x, avatar_y)
                self._log("🖱 已點擊頭像，等待選單出現...")

                # 等待選單動畫
                self._stop_event.wait(timeout=0.8)
                if not self._running:
                    break

                # 在遊戲視窗中找「踢出百業」按鈕並點擊
                kicked = self._click_kick_button()
                if kicked:
                    self._log(
                        f"✅ 已踢出 {first.name or '（未識別）'}，等待名單刷新（2 秒）..."
                    )
                    # 等待名單自動刷新，讓下一輪掃描取得更新後的列表
                    self._stop_event.wait(timeout=2.0)
                else:
                    self._log("⚠ 未找到踢出按鈕，請手動確認選單")
                    break

            else:
                self._log(
                    f"✅ 第一位活躍度 {first.contribution} > {threshold}，無需踢出，識別結束"
                )
                self._set_status("已停止（無需踢出）")
                break

        self._running = False
        self._set_status("已停止")
        if self.on_action_taken:
            self.on_action_taken()

    # ── 模板匹配找踢出按鈕 ───────────────────────────────────────────────────

    def _click_kick_button(self) -> bool:
        """
        截圖後以模板匹配在全視窗搜尋「踢出百業」按鈕並點擊。
        回傳 True = 成功點擊，False = 未找到。
        """
        hwnd = self._app.game_hwnd
        if not hwnd:
            return False

        hdr_mode = bool(self._cfg.get("hdr_mode", False))
        img_gray = capture_game_window(hwnd, hdr_mode=hdr_mode, as_gray=True)
        if img_gray is None:
            return False

        try:
            win_rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return False

        win_left, win_top = win_rect[0], win_rect[1]
        bx, by = self._find_kick_button(img_gray, win_left, win_top)
        if bx == 0 and by == 0:
            return False

        pydirectinput.click(bx, by)
        confirm_delay = float(self._cfg.get("member_kick.confirm_delay", 1.5))
        self._stop_event.wait(timeout=confirm_delay)
        pydirectinput.press("space")
        self._log("✅ 已點踢出，按 Space 確認")
        return True

    def _find_kick_button(
        self,
        full_gray: np.ndarray,
        win_left: int,
        win_top: int,
    ) -> tuple[int, int]:
        """
        在全視窗搜尋踢出按鈕模板（多尺度比對）。
        回傳螢幕絕對座標 (x, y)，失敗時回傳 (0, 0)。
        """
        if self._kick_template is None:
            return 0, 0

        tmpl = self._kick_template
        best_val = 0.0
        best_loc = (0, 0)
        best_scale = 1.0

        # 全視窗搜尋（選單位置不固定）
        for scale in [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]:
            new_h = max(1, int(tmpl.shape[0] * scale))
            new_w = max(1, int(tmpl.shape[1] * scale))
            if new_h > full_gray.shape[0] or new_w > full_gray.shape[1]:
                continue
            resized = cv2.resize(tmpl, (new_w, new_h), interpolation=cv2.INTER_AREA)
            try:
                result = cv2.matchTemplate(full_gray, resized, cv2.TM_CCOEFF_NORMED)
                _, val, _, loc = cv2.minMaxLoc(result)
            except Exception:
                continue
            if val > best_val:
                best_val = val
                best_loc = loc
                best_scale = scale

        self._log(f"🔍 踢出按鈕最佳比對分數：{best_val:.3f}")
        if best_val < 0.38:
            return 0, 0

        tmpl_w = int(tmpl.shape[1] * best_scale)
        tmpl_h = int(tmpl.shape[0] * best_scale)
        abs_x = win_left + best_loc[0] + tmpl_w // 2
        abs_y = win_top + best_loc[1] + tmpl_h // 2
        self._log(f"✅ 踢出按鈕位置：({abs_x}, {abs_y})")
        return abs_x, abs_y

    # ── 截圖 + OCR ───────────────────────────────────────────────────────────

    def _scan(self, hdr_mode: bool) -> list[KickPlayerInfo] | None:
        hwnd = self._app.game_hwnd
        if not hwnd:
            return None

        img_color = capture_game_window(hwnd, hdr_mode=hdr_mode, as_gray=False)
        if img_color is None:
            return None

        try:
            win_rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return None

        win_h, win_w = img_color.shape[:2]
        players = self._ocr_parse(img_color, win_w, win_h)
        return players

    def _ocr_parse(
        self,
        img_color: np.ndarray,
        win_w: int,
        win_h: int,
    ) -> list[KickPlayerInfo]:
        self._init_ocr_reader()
        if not self._reader:
            return []

        # 裁切至表格區域
        y1 = int(win_h * Y1R)
        y2 = int(win_h * Y2R)
        cropped = img_color[y1:y2, :]

        try:
            results = self._reader.readtext(cropped)
        except Exception as e:
            self._log(f"❌ OCR 失敗：{e}")
            return []

        # ── 按 Y 座標分組，欄位由 X 比例判定 ──────────────────────────────
        rows: dict[int, list[tuple[str, str, float, float]]] = {}

        def _merge_result(bbox, text: str, conf: float, col: str, y_offset: int) -> None:
            """將單筆 OCR 結果依欄位與 Y 分組合併至 rows。"""
            pts = np.array(bbox)
            x_mid = float(pts[:, 0].mean())
            y_mid = float(pts[:, 1].mean()) + y_offset
            x_ratio = x_mid / win_w
            y_key = None
            for yk in rows:
                if abs(y_mid - yk) <= _ROW_Y_TOLERANCE:
                    y_key = yk
                    break
            if y_key is None:
                y_key = int(y_mid)
                rows[y_key] = []
            rows[y_key].append((col, text, conf, x_ratio))

        for (bbox, text, conf) in results:
            pts = np.array(bbox)
            x_mid = float(pts[:, 0].mean())
            x_ratio = x_mid / win_w
            y_mid = float(pts[:, 1].mean()) + y1   # 還原至視窗座標

            if _COL_NAME_X1 <= x_ratio < _COL_NAME_X2 and conf >= _CONF_NAME:
                col = "name"
            else:
                continue
            # 注意：contribution 欄位由下方 3x zoom 掃描負責，此處不重複偵測

            # 找匹配的 Y group
            y_key = None
            for yk in rows:
                if abs(y_mid - yk) <= _ROW_Y_TOLERANCE:
                    y_key = yk
                    break
            if y_key is None:
                y_key = int(y_mid)
                rows[y_key] = []
            rows[y_key].append((col, text, conf, x_ratio))

        # ── 活躍度欄放大掃描（3x zoom，提升「0」等單字符偵測率）──────────
        cx1 = int(win_w * _COL_CONTRIBUTION_X1)
        cx2 = int(win_w * _COL_CONTRIBUTION_X2)
        contrib_col = img_color[y1:y2, cx1:cx2]
        contrib_3x = cv2.resize(contrib_col, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        try:
            raw_contrib = self._reader.readtext(contrib_3x, detail=1, paragraph=False)
            for bbox_z, text_z, conf_z in raw_contrib:
                text_z = text_z.strip()
                if not text_z:
                    continue
                digits = re.sub(r"[^\d]", "", text_z)
                if not digits:
                    continue
                pts_z = np.array(bbox_z)
                y_mid_z = float(pts_z[:, 1].mean()) / 3 + y1   # 縮回原始座標
                # 製造虛擬 bbox 供 _merge_result 使用（x_ratio 固定在欄位中間）
                x_center_orig = (cx1 + cx2) / 2
                fake_bbox = [
                    [x_center_orig - 1, y_mid_z - 1],
                    [x_center_orig + 1, y_mid_z - 1],
                    [x_center_orig + 1, y_mid_z + 1],
                    [x_center_orig - 1, y_mid_z + 1],
                ]
                _merge_result(fake_bbox, text_z, conf_z, "contribution", 0)
        except Exception:
            pass

        # ── 組合每列 ────────────────────────────────────────────────────────
        players: list[KickPlayerInfo] = []
        for y_key, items in rows.items():
            name_parts: list[tuple[float, str]] = []
            contrib_parts: list[tuple[float, str]] = []

            for col, text, conf, x in items:
                if col == "name":
                    name_parts.append((x, text))
                elif col == "contribution":
                    contrib_parts.append((x, text))

            if not name_parts and not contrib_parts:
                continue

            # 過濾 Header 列（表格欄位標題）
            all_texts = {t for _, t in name_parts + contrib_parts}
            if all_texts & _HEADER_KEYWORDS:
                continue

            name = " ".join(t for _, t in sorted(name_parts)).strip() if name_parts else ""

            contribution = -1
            if contrib_parts:
                raw = " ".join(t for _, t in sorted(contrib_parts))
                digits = re.sub(r"[^\d]", "", raw)
                if digits:
                    contribution = int(digits)

            players.append(KickPlayerInfo(
                name=name,
                contribution=contribution,
                row_y=y_key,
            ))

        return players
