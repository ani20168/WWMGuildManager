# -*- coding: utf-8 -*-
"""
check_dll_deps.py — 打包後 CUDA DLL 依賴完整性檢查

掃描 dist 裡 torch\\lib 的所有 DLL，找出「依賴了包外 DLL」的情況，
提前發現會在無 CUDA 電腦上失敗的問題。

使用方式：
  python check_dll_deps.py
  python check_dll_deps.py --dist dist\\WWMGuildManager
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path

# Windows 終端機強制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def ensure_pefile() -> bool:
    try:
        import pefile  # noqa
        return True
    except ImportError:
        print("安裝 pefile 解析工具...")
        ret = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pefile", "--quiet"],
            capture_output=True,
        )
        if ret.returncode != 0:
            print("pefile 安裝失敗，略過 DLL 依賴檢查")
            return False
        return True


# Windows 系統 DLL 前綴白名單
SYSTEM_PREFIXES = (
    "kernel32", "ntdll", "user32", "gdi32", "advapi32", "shell32",
    "ole32", "oleaut32", "ws2_32", "msvcp", "msvcr", "vcruntime",
    "ucrtbase", "api-ms-win", "ext-ms-win",
    "bcrypt", "crypt32", "secur32", "shlwapi", "comctl32", "comdlg32",
    "winspool", "imm32", "winmm", "setupapi", "cfgmgr32", "wintrust",
    "version", "psapi", "iphlpapi", "dnsapi", "netapi32", "userenv",
    "uxtheme", "dwmapi", "dbghelp", "imagehlp", "rpcrt4", "ndfapi",
    "normaliz", "wldap32", "clbcatq", "d3d", "dxgi", "opengl32",
    # Python runtime
    "python3", "python311", "python312", "python313",
)


def is_system_dll(name: str) -> bool:
    n = name.lower()
    return any(n.startswith(p) for p in SYSTEM_PREFIXES)


def get_dll_imports(path: Path) -> tuple[list[str], list[str]]:
    """用 pefile 讀取 DLL 的 Import Table。

    回傳 (regular_imports, delay_load_imports)：
    - regular_imports：普通 PE import，DLL 載入時就必須存在，缺了會立刻失敗
    - delay_load_imports：延遲載入，只在實際呼叫到對應函式時才載入，
                          缺了不影響 DLL 本身載入（例如 torch_cuda.dll 對
                          cuFFT/cuSolver/cuSPARSE 的依賴，EasyOCR 推論不會觸發）
    """
    import pefile
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
        ])
        regular = []
        if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
            regular = [e.dll.decode("ascii", errors="ignore")
                       for e in pe.DIRECTORY_ENTRY_IMPORT if e.dll]
        delayed = []
        if hasattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT"):
            delayed = [e.dll.decode("ascii", errors="ignore")
                       for e in pe.DIRECTORY_ENTRY_DELAY_IMPORT if e.dll]
        # 從普通 import 中移除同時出現在 delay-load 的項目（pefile 有時會重複）
        delayed_lower = {d.lower() for d in delayed}
        regular = [r for r in regular if r.lower() not in delayed_lower]
        return regular, delayed
    except Exception:
        return [], []


def check(dist_dir: Path) -> bool:
    if not ensure_pefile():
        return True  # 無法檢查就放行

    torch_lib = dist_dir / "_internal" / "torch" / "lib"
    if not torch_lib.exists():
        print(f"找不到 torch\\lib 目錄：{torch_lib}")
        return True

    # 包內所有 DLL 名稱（不分子目錄，全部小寫）
    all_dlls = {p.name.lower() for p in (dist_dir / "_internal").rglob("*.dll")}
    all_dlls |= {p.name.lower() for p in dist_dir.glob("*.dll")}

    print(f"掃描目錄：{torch_lib}")
    print(f"torch\\lib 共有 {len(list(torch_lib.glob('*.dll')))} 個 DLL，包內共 {len(all_dlls)} 個 DLL\n")

    issues: list[tuple[str, str]] = []       # 普通 import 缺失 → 會 crash
    warnings: list[tuple[str, str]] = []    # delay-load 缺失 → 僅功能受限

    for dll_path in sorted(torch_lib.glob("*.dll")):
        regular, delayed = get_dll_imports(dll_path)

        for dep in regular:
            dep_lower = dep.lower()
            if dep_lower in all_dlls or is_system_dll(dep):
                continue
            issues.append((dll_path.name, dep))

        for dep in delayed:
            dep_lower = dep.lower()
            if dep_lower in all_dlls or is_system_dll(dep):
                continue
            warnings.append((dll_path.name, dep))

    from collections import defaultdict

    def print_group(label: str, data: list[tuple[str, str]]) -> None:
        by_missing: dict[str, list[str]] = defaultdict(list)
        for owner, missing in data:
            by_missing[missing].append(owner)
        for missing in sorted(by_missing):
            owners = by_missing[missing]
            print(f"  {label} {missing}")
            for o in owners[:3]:
                print(f"         <- 被 {o} 依賴")
            if len(owners) > 3:
                print(f"         <- 還有 {len(owners)-3} 個 DLL 依賴它")

    if warnings:
        print(f"[WARN] {len(warnings)} 個 Delay-Load 依賴不在包內"
              f"（EasyOCR 推論不呼叫這些路徑，不影響執行）：\n")
        print_group("[delay]", warnings)
        print()

    if not issues:
        print("[OK] 無普通 import 缺失，在沒有 CUDA 的電腦上可以正常執行。")
        return True

    print(f"[FAIL] 發現 {len(issues)} 個普通 import 缺失（在無 CUDA 的電腦上會 crash）：\n")
    print_group("[缺少]", issues)
    print()
    print("修復方式：這些 DLL 是 DLL 啟動時就需要載入的，必須打包進來。")
    print("請從 spec 的 _EXCLUDE_PATTERNS 移除對應的排除規則。")
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="檢查打包後 CUDA DLL 依賴完整性")
    parser.add_argument("--dist", default=r"dist\WWMGuildManager",
                        help="dist 資料夾路徑（預設：dist\\WWMGuildManager）")
    args = parser.parse_args()

    dist_path = Path(args.dist)
    if not dist_path.exists():
        print(f"找不到 dist 資料夾：{dist_path}")
        sys.exit(1)

    ok = check(dist_path)
    sys.exit(0 if ok else 1)
