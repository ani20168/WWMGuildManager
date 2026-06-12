# -*- coding: utf-8 -*-
"""
HDR 補償截圖模組。

HDR 問題：Windows 啟用 HDR 時，mss 擷取的像素值可能已被色調映射，
導致顏色偏移，模板匹配失敗。
解決方案：
  1. 轉為灰階，消除大部分色彩偏差
  2. 啟用 HDR 補償時套用 gamma 還原（gamma=2.2）
  3. 模板匹配一律使用 TM_CCOEFF_NORMED（對亮度偏移最不敏感）
"""
from __future__ import annotations
import numpy as np
import cv2
import mss
import win32gui


def capture_game_window(
    hwnd: int,
    hdr_mode: bool = False,
    as_gray: bool = True,
) -> np.ndarray | None:
    """
    擷取遊戲視窗截圖。

    Args:
        hwnd: 遊戲視窗 handle
        hdr_mode: 是否啟用 HDR gamma 補償
        as_gray: 回傳灰階影像（建議識別時使用）

    Returns:
        numpy ndarray (BGR 或 GRAY)，失敗時回傳 None
    """
    if not hwnd:
        return None

    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    except Exception:
        return None

    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None

    monitor = {"left": left, "top": top, "width": width, "height": height}

    try:
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            img = np.array(shot)  # BGRA
    except Exception:
        return None

    # BGRA → BGR
    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    if hdr_mode:
        img = _apply_hdr_compensation(img)

    if as_gray:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    return img


def _apply_hdr_compensation(img: np.ndarray) -> np.ndarray:
    """
    套用反向 gamma 校正，將 HDR 色調映射後的影像還原至接近 SDR 的亮度分布。
    gamma=2.2 為 sRGB 標準值。
    """
    img_f = img.astype(np.float32) / 255.0
    img_f = np.power(img_f, 1.0 / 2.2)
    return (img_f * 255).clip(0, 255).astype(np.uint8)


def capture_region(
    hwnd: int,
    rel_rect: tuple[float, float, float, float],
    hdr_mode: bool = False,
    as_gray: bool = True,
) -> np.ndarray | None:
    """
    擷取視窗內的相對區域截圖。

    Args:
        hwnd: 遊戲視窗 handle
        rel_rect: (x1, y1, x2, y2) 相對座標（0.0～1.0）
        hdr_mode: HDR 補償
        as_gray: 回傳灰階

    Returns:
        裁切後的 numpy ndarray，失敗回傳 None
    """
    full = capture_game_window(hwnd, hdr_mode=hdr_mode, as_gray=False)
    if full is None:
        return None

    h, w = full.shape[:2]
    x1 = int(rel_rect[0] * w)
    y1 = int(rel_rect[1] * h)
    x2 = int(rel_rect[2] * w)
    y2 = int(rel_rect[3] * h)

    cropped = full[y1:y2, x1:x2]
    if as_gray:
        cropped = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    return cropped
