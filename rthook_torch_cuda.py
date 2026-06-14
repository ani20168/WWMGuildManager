# -*- coding: utf-8 -*-
"""
PyInstaller runtime hook — 修正打包後 torch CUDA 無法偵測的問題。

打包後 torch\lib 裡的 CUDA DLL（cudart64_12.dll 等）不在系統 PATH，
導致 torch.cuda.is_available() 回傳 False。
此 hook 在 exe 啟動最早期執行，將 torch\lib 加入 PATH。
"""
import os
import sys

if getattr(sys, "frozen", False):
    torch_lib = os.path.join(sys._MEIPASS, "torch", "lib")
    if os.path.isdir(torch_lib):
        os.add_dll_directory(torch_lib)
        os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
