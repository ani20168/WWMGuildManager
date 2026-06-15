# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包設定
執行方式：pyinstaller WWMGuildManager.spec
輸出路徑：dist/WWMGuildManager/（資料夾模式）

注意事項：
  - 首次執行時 EasyOCR 會自動下載 OCR 模型（約 50MB，存至 %USERPROFILE%\.EasyOCR）
  - 打包後 config.json 位於 exe 同層目錄，使用者可自行修改
  - 最終資料夾大小約 2.5GB～3GB（含 CUDA，排除不必要的 CUDA DLL 後）
"""
import os
import re
from PyInstaller.utils.hooks import collect_data_files, collect_all

# ── 資料檔 ─────────────────────────────────────────────────────────────────
datas = []

# customtkinter：主題 JSON / 圖片資源
datas += collect_data_files("customtkinter")

# easyocr：語言設定、字元表等（OCR 權重模型在執行時才下載，不打包）
datas += collect_data_files("easyocr")

# images/other/（app icon）打包進 _internal，供程式碼用 sys._MEIPASS 讀取
datas += [("images/other", "images/other")]

# images/member_kick、images/member_visit 不打包進去，讓使用者可以自行替換模板圖片
# build.yml 會在打包後把這兩個子資料夾複製到 dist 根目錄

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
    # torch（EasyOCR 初始化時需要）
    "torch.distributed",
]

# ── 排除不需要的大型套件（減小打包體積）──────────────────────────────────────
# 僅排除與本程式完全無關、且確認不被 EasyOCR/torch/torchvision 間接依賴的套件
excludes = [
    "matplotlib",
    "pandas",
    "IPython",
    "jupyter",
    "notebook",
    "caffe2",
]

block_cipher = None

# ── EasyOCR 推論不需要的 CUDA DLL（排除以減少打包體積）──────────────────────
# 保留：torch_cuda / torch_cpu / c10 / c10_cuda / cudart / cublas(Lt) /
#        cudnn_ops / cudnn_cnn / cudnn_adv(LSTM) / cudnn_heuristic /
#        cudnn_engines_precompiled / cudnn_engines_runtime_compiled /
#        libiomp5md / zlibwapi / uv
#
# 排除理由：
#   cuSPARSE / cuFFT / cuSOLVER → 稀疏矩陣、FFT、線性求解，純推論不使用
#                                  注意：cuSPARSE 與 cuSOLVER 互相依賴，必須同時排除或同時保留
#   cuRAND                       → 亂數生成，訓練用
#   nvrtc / nvJitLink            → torch.compile / JIT 編譯，EasyOCR 不使用
#   nvperf / cupti / nvToolsExt  → NVIDIA 效能分析工具
#
# 使用前綴正則比對，避免因 CUDA 版本不同（如 _11.dll vs _12.dll）造成漏排
_EXCLUDE_PATTERNS = re.compile(
    r"^("
    r"cusparse\d"           # cuSPARSE（所有版本號）
    r"|cufft[w]?\d"         # cuFFT / cuFFTW
    r"|cusolver\d"          # cuSOLVER
    r"|cusolverMg\d"        # cuSOLVER Multi-GPU
    r"|curand\d"            # cuRAND
    r"|nvrtc[\d\-]"         # NVRTC JIT 編譯器（nvrtc64_xxx / nvrtc-builtins）
    r"|nvJitLink"           # nvJitLink
    r"|caffe2_nvrtc"        # Caffe2 NVRTC
    r"|nvperf_host"         # NVIDIA 效能分析
    r"|cupti\d"             # CUPTI Profiling
    r"|nvToolsExt\d"        # NVTX
    r").*\.dll$",
    re.IGNORECASE,
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["rthook_torch_cuda.py"],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 過濾掉不需要的 CUDA DLL（正則前綴比對，不受 CUDA 版本號影響）
a.binaries = TOC([
    b for b in a.binaries
    if not _EXCLUDE_PATTERNS.match(os.path.basename(b[0]))
])

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
    icon="images/other/icon.ico",
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
