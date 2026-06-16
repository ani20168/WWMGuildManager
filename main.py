# -*- coding: utf-8 -*-
"""
WWM Guild Manager — 程式進入點。

啟動流程：
  1. 初始化 AppController（全域狀態）
  2. 初始化 ConfigManager（設定讀寫）
  3. 啟動 WindowManager（背景偵測 wwm.exe）
  4. 啟動 HotkeyManager（F8 全域快捷鍵）
  5. 建立 MainWindow 並載入所有分頁
  6. 進入 tkinter 主迴圈
"""
import sys
import os
import ctypes

# 告訴 Windows 這是獨立應用程式，工作列才會顯示自訂圖示而非 python.exe 圖示
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WWMGuildManager.App")
except Exception:
    pass

# 確保專案根目錄在 sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.log_manager import get_log_manager
from core.app_controller import AppController
from core.config_manager import ConfigManager
from core.window_manager import WindowManager
from core.hotkey_manager import HotkeyManager
from ui.main_window import MainWindow
from pages.home.home_page import HomePage
from pages.member_visit.member_visit_page import MemberVisitPage
from pages.member_kick.member_kick_page import MemberKickPage

# ── 分頁清單（依此順序顯示在側邊欄）──────────────────────────────────────────
PAGES = [
    HomePage,
    MemberVisitPage,
    MemberKickPage,
]


def main() -> None:
    log_mgr = get_log_manager()
    log_mgr.log("程式啟動，初始化中...", "INFO")

    app_ctrl = AppController()
    cfg_mgr = ConfigManager()

    # 背景服務
    win_mgr = WindowManager(app_ctrl)
    win_mgr.start()

    hk_mgr = HotkeyManager(app_ctrl, cfg_mgr)
    hk_mgr.start()
    log_mgr.log(f"快捷鍵已註冊：{cfg_mgr.get('hotkey_toggle', 'f8').upper()}", "INFO")

    # 建立主視窗
    window = MainWindow(app_ctrl, cfg_mgr)
    window.build(PAGES)

    # 將 HotkeyManager 注入首頁（用於快捷鍵重設功能）
    home_page = window._pages.get("home")
    if home_page:
        home_page.set_hotkey_manager(hk_mgr)

    log_mgr.log("主視窗已建立，進入事件迴圈", "INFO")

    try:
        window.mainloop()
    finally:
        hk_mgr.stop()
        win_mgr.stop()
        log_mgr.close()


if __name__ == "__main__":
    main()


"""
pyinstaller WWMGuildManager.spec
"""