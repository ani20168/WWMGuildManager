# -*- coding: utf-8 -*-
"""
自動尋訪成員 — 識別引擎。

識別流程：
  1. 截取遊戲視窗畫面
  2. OCR 識別玩家列表區域文字
  3. 解析每列玩家資訊（名稱、等級、造詣、語言）
  4. 根據篩選條件找出符合玩家
  5. 模板匹配找到對應列的「+」按鈕並點擊
  6. 無符合玩家時按 R 刷新（最短 3 秒間隔）
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np
import pydirectinput
import win32gui

from core.screen_capture import capture_game_window

# 關閉 pydirectinput 的預設延遲（預設 0.1s，會使點擊/按鍵變慢）
pydirectinput.PAUSE = 0.05

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "images", "member_visit")
PLUS_BTN_TEMPLATE = os.path.join(IMAGES_DIR, "plus_button.png")

# 刷新最短間隔
MIN_REFRESH_INTERVAL = 3.0


# 識別到的玩家數量低於此值時，不執行邀請（避免 OCR 漏掃就亂邀）
# 「有效玩家」定義：至少識別出等級（level > 0），名稱不一定需要
MIN_PLAYERS_BEFORE_ACTION = 7

# 表格標題關鍵字，出現這些字的行直接略過
_HEADER_KEYWORDS = {"玩家名稱", "等級", "造詣", "線上狀態", "常用語言", "邀請加入", "邀 全"}

# Y 軸分組容忍度（原始像素）：同一列的文字 Y 中心差距在此範圍內視為同一行
_ROW_Y_TOLERANCE = 10


@dataclass
class PlayerInfo:
    name: str = ""
    level: int = 0
    power: int = 0
    status: str = ""
    language: str = ""
    row_y: int = 0          # 在截圖中的 Y 座標（用於定位按鈕）
    plus_x: int = 0         # 「+」按鈕 X 座標（螢幕絕對座標）
    plus_y: int = 0         # 「+」按鈕 Y 座標（螢幕絕對座標）
    matches_filter: bool = False


class MemberRecognizer:
    def __init__(self, app_controller, config_manager) -> None:
        self._app = app_controller
        self._cfg = config_manager

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._last_refresh_time: float = 0.0
        self._first_scan_done: bool = False

        # 回呼：讓 UI 更新
        self.on_players_updated: Callable[[list[PlayerInfo]], None] | None = None
        self.on_log: Callable[[str], None] | None = None
        self.on_status: Callable[[str], None] | None = None

        # EasyOCR Reader（延遲初始化：首次執行 _scan 時載入，避免阻塞 UI 啟動）
        self._reader = None   # None = 未初始化；False = 載入失敗

        # 模板圖（延遲載入）
        self._plus_template: np.ndarray | None = None
        self._load_templates()

    def _load_templates(self) -> None:
        if os.path.exists(PLUS_BTN_TEMPLATE):
            img = cv2.imread(PLUS_BTN_TEMPLATE, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._plus_template = img

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._first_scan_done = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._log("識別已啟動")
        self._set_status("識別中...")

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        self._log("識別已停止")
        self._set_status("已停止")

    def _loop(self) -> None:
        refreshed_this_cycle = False   # 本輪是否已按過 R（已等待刷新）

        while self._running and not self._stop_event.is_set():
            delay = float(self._cfg.get("recognition_delay", 0.25))
            hdr_mode = bool(self._cfg.get("hdr_mode", False))

            players = self._scan(hdr_mode)
            self._first_scan_done = True
            refreshed_this_cycle = False

            if players is not None:
                if self.on_players_updated:
                    self.on_players_updated(players)

                # 「有效玩家」：識別出等級 OR 造詣，名稱識別不出來也算
                valid_count = sum(1 for p in players if p.level > 0 or p.power > 0)
                matched = [p for p in players if p.matches_filter]

                if valid_count < MIN_PLAYERS_BEFORE_ACTION:
                    if valid_count >= 1:
                        # 識別到部分玩家（1 ~ n-1）→ 畫面可能未載入完全，刷新等待
                        self._log(
                            f"⚠ 僅識別到 {valid_count}/{MIN_PLAYERS_BEFORE_ACTION} 位玩家，"
                            "刷新等待完整名單"
                        )
                        self._try_refresh()
                        refreshed_this_cycle = True
                    else:
                        # 完全沒有識別到 → 可能不在尋訪頁面，不刷新
                        self._log(
                            f"⚠ 未識別到任何玩家（需 {MIN_PLAYERS_BEFORE_ACTION} 位），"
                            "請確認是否在尋訪頁面"
                        )
                elif matched:
                    for p in matched:
                        if not self._running:
                            break
                        self._click_plus(p)
                        time.sleep(0.5)
                    # 邀完所有符合條件的人後，刷新列表以取得新的候選人
                    if self._running:
                        self._try_refresh()
                        refreshed_this_cycle = True
                elif players:
                    # 有玩家但全部不符合條件 → 刷新找新人
                    self._try_refresh()
                    refreshed_this_cycle = True
                else:
                    # players 為空串列 → OCR 完全沒輸出，不刷新
                    self._log("未識別到玩家列表，請確認是否在尋訪頁面")

            # 已執行刷新且等待完畢（_try_refresh 內已 wait REFRESH_WAIT），
            # 不再額外等 delay，直接進下一輪掃描
            if not refreshed_this_cycle:
                self._stop_event.wait(timeout=delay)

    # ── 截圖與 OCR ──────────────────────────────────────────────────────────
    def _scan(self, hdr_mode: bool) -> list[PlayerInfo] | None:
        hwnd = self._app.game_hwnd
        if not hwnd:
            return None

        # EasyOCR 使用彩色圖辨識效果較好
        img_color = capture_game_window(hwnd, hdr_mode=hdr_mode, as_gray=False)
        if img_color is None:
            return None

        # 灰度圖僅供模板匹配（找「+」按鈕）
        img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

        try:
            win_rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return None

        win_left, win_top = win_rect[0], win_rect[1]
        win_h, win_w = img_color.shape[:2]

        players = self._ocr_parse(img_color, img_gray, win_w, win_h, win_left, win_top)

        # 套用篩選
        filter_level = self._cfg.get("member_visit.filter_level", "")
        filter_lang = self._cfg.get("member_visit.filter_language", "")
        self._apply_filter(players, filter_level, filter_lang)

        return players

    # ── EasyOCR 初始化與識別核心 ─────────────────────────────────────────────

    def _init_ocr_reader(self) -> None:
        """延遲初始化 EasyOCR Reader（首次識別時執行，約需 5-15 秒）。"""
        if self._reader is not None:
            return
        self._set_status("正在載入 OCR 模型（首次約需 10 秒）...")
        try:
            import easyocr  # noqa: PLC0415
            import torch as _torch  # noqa: PLC0415
            use_gpu = _torch.cuda.is_available()
            self._reader = easyocr.Reader(
                ["ch_tra", "en"],
                gpu=use_gpu,        # 有 CUDA GPU 就自動啟用
                verbose=False,      # 不印進度訊息到 console
            )
            mode = "GPU" if use_gpu else "CPU"
            self._set_status(f"OCR 模型載入完成（{mode} 模式）")
        except Exception as exc:
            self._log(f"EasyOCR 載入失敗：{exc}")
            self._reader = False

    def _group_by_y(
        self, words: list[tuple[int, int, str]], tol: int
    ) -> list[tuple[int, list[str]]]:
        """
        將 (y, x, text) 列表按 Y 鄰近性分桶。
        同一桶內依 X 排序（確保左→右文字順序），
        回傳 [(y_bucket, [texts_sorted_by_x...])] 已依 Y 排序。
        """
        buckets: dict[int, list[tuple[int, str]]] = {}   # y_key → [(x, text)]
        for y, x, text in words:
            matched = None
            for ky in buckets:
                if abs(ky - y) <= tol:
                    matched = ky
                    break
            if matched is None:
                buckets[y] = [(x, text)]
            else:
                buckets[matched].append((x, text))

        result = []
        for ky in sorted(buckets):
            sorted_by_x = sorted(buckets[ky], key=lambda p: p[0])
            result.append((ky, [t for _, t in sorted_by_x]))
        return result

    def _match_near_y(
        self,
        col_data: list[tuple[int, int, str]],
        target_y: int,
        half_h: int,
    ) -> list[str]:
        """
        回傳 col_data 中 Y 在 [target_y - half_h, target_y + half_h] 內的所有文字。
        依 X 升序排列，確保左→右讀取（解決「文中」↔「中文」反轉問題）。
        """
        matched = [(x, t) for y, x, t in col_data if abs(y - target_y) <= half_h]
        matched.sort(key=lambda p: p[0])
        return [t for _, t in matched]

    def _ocr_parse(
        self,
        img_color: np.ndarray,
        img_gray: np.ndarray,
        win_w: int,
        win_h: int,
        win_left: int,
        win_top: int,
    ) -> list[PlayerInfo]:
        """
        EasyOCR 一次辨識整個表格區域，透過 bounding box x 座標分配至各欄。

        策略：
        1. 裁出表格 Y 範圍（12%–97%），全寬傳給 EasyOCR
        2. 依 x_ratio 將每個詞分配到 power / level / language / name 欄
        3. 以造詣欄（數字，最可靠）建立 7 個 Y 錨點
        4. 逐行匹配其他欄資料，重建 PlayerInfo
        """
        # 延遲初始化
        if self._reader is None:
            self._init_ocr_reader()
        if not self._reader:
            return []

        # 裁出表格 Y 範圍（跳過表頭；0.97 確保第 7 列不被裁掉）
        Y1R, Y2R = 0.12, 0.97
        ty1 = int(win_h * Y1R)
        ty2 = int(win_h * Y2R)
        table_img = img_color[ty1:ty2, :]

        try:
            raw = self._reader.readtext(table_img, detail=1, paragraph=False)
        except Exception as exc:
            self._log(f"OCR 失敗：{exc}")
            return []

        # 將 EasyOCR 結果轉換為 (y_orig, x_orig, text) 並依 x_ratio 分欄
        # EasyOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
        # 等級/名稱欄置信度常低（遊戲 UI 字型），用 0.0 接受所有偵測
        # 造詣欄只要數字準確即可，置信度不重要
        CONF_THR_POWER = 0.1   # 造詣：嚴格一點，避免雜訊
        CONF_THR_LEVEL = 0.0   # 等級：接受低置信度（字型特殊）
        CONF_THR_NAME  = 0.0   # 名稱：同上
        CONF_THR_LANG  = 0.3   # 語言：單獨高倍掃描，較高準確

        power_words: list[tuple[int, int, str]] = []
        level_words: list[tuple[int, int, str]] = []
        lang_words:  list[tuple[int, int, str]] = []
        name_words:  list[tuple[int, int, str]] = []

        for bbox, text, conf in raw:
            text = text.strip()
            if not text:
                continue
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            cx = sum(xs) / 4
            cy = sum(ys) / 4
            x_orig = int(cx)
            y_orig = int(cy) + ty1          # 轉回原始座標系
            xr = x_orig / win_w             # x 比例（用於欄位判斷）

            if 0.30 <= xr <= 0.48 and conf >= CONF_THR_POWER:
                power_words.append((y_orig, x_orig, text))
            elif 0.22 <= xr <= 0.33 and conf >= CONF_THR_LEVEL:
                level_words.append((y_orig, x_orig, text))
            elif 0.03 <= xr <= 0.21 and conf >= CONF_THR_NAME:
                name_words.append((y_orig, x_orig, text))
            # 語言欄由下方獨立高倍掃描取代（EasyOCR 對短中文字偵測率低）

        # ── 語言欄獨立高倍掃描（3x zoom，提升短中文字偵測率）──────────────
        lx1 = int(win_w * 0.61)
        lx2 = int(win_w * 0.83)
        lang_col = img_color[ty1:ty2, lx1:lx2]
        lang_col_3x = cv2.resize(lang_col, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        try:
            raw_lang = self._reader.readtext(lang_col_3x, detail=1, paragraph=False)
            for bbox, text, conf in raw_lang:
                text = text.strip()
                if not text or conf < CONF_THR_LANG:
                    continue
                ys = [p[1] for p in bbox]
                cy = sum(ys) / 4
                y_orig = int(cy / 3) + ty1
                lang_words.append((y_orig, int((lx1 + lx2) / 2), text))
        except Exception:
            pass

        # 造詣欄 → Y 錨點（只保留 3-6 位純數字的行）
        power_rows = self._group_by_y(power_words, tol=_ROW_Y_TOLERANCE)

        def _is_power_row(ws: list[str]) -> bool:
            if any(re.match(r"^\d{3,6}$", w) for w in ws):
                return True
            merged = "".join(w for w in ws if re.match(r"^\d+$", w))
            return bool(re.match(r"^\d{3,6}$", merged))

        power_rows = [(y, ws) for y, ws in power_rows if _is_power_row(ws)]
        if not power_rows:
            return []

        # 計算半行高（用於跨欄 Y 匹配）
        if len(power_rows) > 1:
            ys = [y for y, _ in power_rows]
            half_h = int((ys[-1] - ys[0]) / (len(ys) - 1) / 2)
        else:
            half_h = 60
        half_h = max(half_h, 35)

        # 逐行建構 PlayerInfo
        players: list[PlayerInfo] = []
        for row_y, power_ws in power_rows:
            # 造詣：合併純數字詞
            power_digits = "".join(w for w in power_ws if re.match(r"^\d+$", w))
            if not power_digits:
                power_digits = re.sub(r"[^\d]", "", " ".join(power_ws))
            power = int(power_digits[:6]) if power_digits.isdigit() and power_digits else 0

            # 等級
            level_ws  = self._match_near_y(level_words, row_y, half_h)
            level     = self._parse_level(" ".join(level_ws))

            # 語言
            lang_ws   = self._match_near_y(lang_words, row_y, half_h)
            language  = self._parse_language(" ".join(lang_ws))

            # 名稱
            name_ws   = self._match_near_y(name_words, row_y, half_h)
            name      = self._clean_name(" ".join(name_ws))

            if power == 0:
                continue

            p = PlayerInfo(
                name=name, level=level, power=power,
                status="線上", language=language,
            )
            p.row_y = row_y

            abs_x, abs_y = self._find_plus_button(img_gray, row_y, win_left, win_top)
            p.plus_x = abs_x
            p.plus_y = abs_y

            players.append(p)

        return players

    def _parse_level(self, text: str) -> int:
        """
        從等級欄 OCR 文字中提取等級數字。

        常見 OCR 問題：
        - 「24級」→「242%」：「級」字被誤讀成「2%」，導致抓到 242
          修正：若抓到的數字 > 200 且沒有明確的「級」字，取前 2 位
        - 「81」有時完全識別不到（字體問題）→ 返回 0，以 power > 0 計為有效行
        """
        # 合併被空格拆開的數字
        text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
        text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)

        # 有「級」字（或常被誤讀成 m/k/h/%/B 等的字符）：取前面的數字
        # 例：「95m」「44%」「89B」「41k」→ 視同「95級」
        m = re.search(r"(\d{1,3})\s*[級级mkKhHbB%＃\*#]", text)
        if m:
            v = int(m.group(1))
            # 同樣做 > 200 保護，以防造詣數字滲入
            if v > 200:
                trimmed = int(str(v)[:2])
                return trimmed if 1 <= trimmed <= 99 else 0
            return v

        # 無「級」字：「級」可能被 OCR 誤讀成「2%」「B」等符號
        # 取第一個出現的 1-3 位數字
        nums = re.findall(r"\d{1,3}", text)
        for n in nums:
            v = int(n)
            if 1 <= v <= 999:
                # 若 > 200 且沒有「級」字，很可能是「XX級」被誤讀成「XX2%」等
                # 取前 2 位作為等級（例如 242 → 24）
                if v > 200:
                    trimmed = int(str(v)[:2])
                    if 1 <= trimmed <= 99:
                        return trimmed
                return v
        return 0

    def _parse_language(self, text: str) -> str:
        """從語言欄 OCR 文字中提取語言標籤。"""
        lang_patterns = [
            (r"中\s*文",                    "中文"),
            (r"英\s*文",                    "英文"),
            (r"日\s*文",                    "日文"),
            (r"韓\s*文",                    "韓文"),
            (r"越\s*南\s*[語文]",           "越南語"),
            (r"越\s*語",                    "越南語"),
            (r"泰\s*文",                    "泰文"),
            (r"印\s*尼\s*文",               "印尼文"),
            (r"德\s*文",                    "德文"),
            (r"法\s*文",                    "法文"),
            (r"西\s*班\s*牙\s*文",          "西班牙文"),
            (r"葡\s*萄\s*牙\s*文",          "葡萄牙文"),
            (r"[Рр]усский",                 "俄文"),
            (r"[\u0400-\u04FF]{3,}",        "俄文"),
            # 遊戲顯示語言原文（非漢字標籤）
            (r"[Ff]ran[çcÇCGg]ais",          "法文"),
            # ñ / o / l 被誤讀時用寬鬆模式（EasyOCR: "Espafo|" / "Espafo1"）
            (r"[Ee]spa[ñnÑNfF][iI]?o[lL|1]",   "西班牙文"),
            (r"[Ee]spa[ñnÑN]",              "西班牙文"),
            # "(Latino)" 可能被讀成 "Lilin0)" 或 "Lit1no"
            (r"[Ll][ia][dt][iI][nNm][oO0]", "西班牙文"),
            (r"[Ll]atino",                  "西班牙文"),
            (r"[Pp]ortuguês",               "葡萄牙文"),
            (r"[Tt]iếng\s*[Vv]iệt",         "越南語"),
            (r"[Ii]ndonesia",               "印尼文"),
            (r"[Dd]eutsch",                 "德文"),
            # OCR 把「英文」誤讀成「KX」、「kX」等（英→K，文→X）
            (r"^[Kk][Xx]$",                 "英文"),
            # OCR 把「中文」誤讀成「PX」、「pX」等（中→P，文→X）
            (r"^[Pp][Xx]$",                 "中文"),
        ]
        for pat, display in lang_patterns:
            if re.search(pat, text):
                return display
        return ""

    def _clean_name(self, text: str) -> str:
        """清理名稱欄 OCR 文字，移除雜訊。"""
        for kw in _HEADER_KEYWORDS:
            text = text.replace(kw, " ")
        text = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    # ── 篩選 ────────────────────────────────────────────────────────────────
    def _apply_filter(
        self,
        players: list[PlayerInfo],
        filter_level: str,
        filter_lang: str,
    ) -> None:
        min_level = 0
        if filter_level.strip().isdigit():
            min_level = int(filter_level.strip())

        for p in players:
            level_ok = (min_level == 0) or (p.level >= min_level)
            # 語言比對：雙向包含（使用者輸入「中」也能匹配「中文」）
            fl = filter_lang.strip()
            lang_ok = (not fl) or (fl in p.language) or (p.language in fl and p.language)
            p.matches_filter = level_ok and lang_ok

    # ── 模板匹配找「+」按鈕 ─────────────────────────────────────────────────
    def _find_plus_button(
        self,
        full_gray: np.ndarray,
        row_y: int,
        win_left: int,
        win_top: int,
        search_margin: int = 50,
    ) -> tuple[int, int]:
        """
        在 row_y 附近的右側區域搜尋「+」按鈕模板（多尺度比對）。
        回傳螢幕絕對座標 (x, y)，失敗時回傳 (0, 0)。

        多尺度原因：遊戲視窗大小不同時，按鈕的像素尺寸會跟模板有差異，
        多尺度比對可以容錯 ±20% 的縮放。
        """
        if self._plus_template is None:
            return 0, 0

        h, w = full_gray.shape[:2]

        # 搜尋區域：右側 75%~100%，row_y 上下各 margin
        x1 = int(w * 0.75)
        x2 = w
        y1 = max(0, row_y - search_margin)
        y2 = min(h, row_y + search_margin)

        if y2 <= y1 or x2 <= x1:
            return 0, 0

        roi = full_gray[y1:y2, x1:x2]
        tmpl = self._plus_template

        best_val = 0.0
        best_loc = (0, 0)
        best_scale = 1.0

        # 多尺度：0.8x ~ 1.3x，步進 0.1
        for scale in [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
            new_h = max(1, int(tmpl.shape[0] * scale))
            new_w = max(1, int(tmpl.shape[1] * scale))
            if new_h > roi.shape[0] or new_w > roi.shape[1]:
                continue
            resized = cv2.resize(tmpl, (new_w, new_h), interpolation=cv2.INTER_AREA)
            try:
                result = cv2.matchTemplate(roi, resized, cv2.TM_CCOEFF_NORMED)
                _, val, _, loc = cv2.minMaxLoc(result)
            except Exception:
                continue
            if val > best_val:
                best_val = val
                best_loc = loc
                best_scale = scale

        if best_val < 0.55:
            return 0, 0

        tmpl_w = int(tmpl.shape[1] * best_scale)
        tmpl_h = int(tmpl.shape[0] * best_scale)
        btn_x_in_roi = best_loc[0] + tmpl_w // 2
        btn_y_in_roi = best_loc[1] + tmpl_h // 2

        abs_x = win_left + x1 + btn_x_in_roi
        abs_y = win_top + y1 + btn_y_in_roi
        return abs_x, abs_y

    # ── 點擊「+」按鈕 ────────────────────────────────────────────────────────
    def _click_plus(self, player: PlayerInfo) -> None:
        if player.plus_x == 0 and player.plus_y == 0:
            self._log(f"⚠ 找不到 {player.name} 的邀請按鈕")
            return
        try:
            # pydirectinput 使用硬體掃描碼，相容 DirectX 遊戲
            pydirectinput.click(player.plus_x, player.plus_y)
            self._log(f"✅ 已尋訪：{player.name}（{player.level}級 / {player.language}）")
        except Exception as e:
            self._log(f"點擊失敗：{e}")

    # ── 刷新成員 ────────────────────────────────────────────────────────────
    def _try_refresh(self) -> None:
        now = time.time()
        if now - self._last_refresh_time < MIN_REFRESH_INTERVAL:
            remaining = MIN_REFRESH_INTERVAL - (now - self._last_refresh_time)
            self._log(f"⏳ 等待刷新冷卻中（剩餘 {remaining:.1f} 秒）")
            return

        self._last_refresh_time = now
        try:
            hwnd = self._app.game_hwnd
            if hwnd:
                # 先嘗試將遊戲視窗帶至前台（需要的話）
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                time.sleep(0.15)
                # pydirectinput 使用掃描碼模擬按鍵，相容 DirectX 遊戲
                # pyautogui 走 WM_KEYDOWN 訊息，DirectInput 遊戲不一定能接收
                pydirectinput.press("r")
                refresh_wait = float(self._cfg.get("refresh_wait", 2.0))
                self._log(f"🔄 已按下 R 刷新成員列表，等待 {refresh_wait:.1f} 秒...")
                # 等待遊戲畫面刷新完成，避免立刻截到舊畫面導致重複邀請
                self._stop_event.wait(timeout=refresh_wait)
        except Exception as e:
            self._log(f"刷新失敗：{e}")

    # ── 工具方法 ────────────────────────────────────────────────────────────
    def _log(self, msg: str) -> None:
        if self.on_log:
            self.on_log(msg)

    def _set_status(self, status: str) -> None:
        if self.on_status:
            self.on_status(status)
