# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包設定
執行方式：pyinstaller WWMGuildManager.spec
輸出路徑：dist/WWMGuildManager/（資料夾模式）

注意事項：
  - 首次執行時 EasyOCR 會自動下載 OCR 模型（約 50MB，存至 %USERPROFILE%\.EasyOCR）
  - 打包後 config.json 位於 exe 同層目錄，使用者可自行修改
  - 最終資料夾大小約 600MB～1.5GB（依 PyTorch 版本而異）
"""
from PyInstaller.utils.hooks import collect_data_files, collect_all

# ── 資料檔 ─────────────────────────────────────────────────────────────────
datas = []

# customtkinter：主題 JSON / 圖片資源
datas += collect_data_files("customtkinter")

# easyocr：語言設定、字元表等（OCR 權重模型在執行時才下載，不打包）
datas += collect_data_files("easyocr")

# 遊戲截圖模板（加號按鈕、踢出按鈕等 PNG）
datas += [("images", "images")]

# ── 隱式 import（PyInstaller 靜態分析可能漏掉的模組）────────────────────────
hiddenimports = [
    # pywin32
    "win32api",
    "win32con",
    "win32gui",
    "win32process",
    "win32security",
    "pywintypes",
    # Pillow
    "PIL._tkinter_finder",
    # tkinter
    "tkinter",
    "tkinter.ttk",
    "_tkinter",
]

# ── 排除不需要的大型套件（減小打包體積）──────────────────────────────────────
excludes = [
    "matplotlib",
    "scipy",
    "pandas",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "unittest",
    "caffe2",
    "torch.testing",
    "torch.distributed",
    "torch.utils.tensorboard",
    "torchvision.datasets",
]

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WWMGuildManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # 不顯示黑色命令列視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="images/icon.ico",  # 若有 icon 請取消此行註解
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WWMGuildManager",
)
