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


def get_dll_imports(path: Path) -> list[str]:
    """用 pefile 讀取 DLL 的 Import Table，回傳依賴的 DLL 名稱清單。"""
    import pefile
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        if not hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
            return []
        return [entry.dll.decode("ascii", errors="ignore")
                for entry in pe.DIRECTORY_ENTRY_IMPORT
                if entry.dll]
    except Exception:
        return []


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

    issues: list[tuple[str, str]] = []

    for dll_path in sorted(torch_lib.glob("*.dll")):
        for dep in get_dll_imports(dll_path):
            dep_lower = dep.lower()
            if dep_lower in all_dlls:
                continue
            if is_system_dll(dep):
                continue
            issues.append((dll_path.name, dep))

    if not issues:
        print("[OK] torch\\lib 所有 DLL 依賴都在包內或系統白名單，無問題！")
        print("     在沒有 CUDA 的電腦上應該也可以正常執行。")
        return True

    print(f"[FAIL] 發現 {len(issues)} 個依賴問題（在無 CUDA 的電腦上會失敗）：\n")

    # 以「缺少的 DLL」分組
    from collections import defaultdict
    by_missing: dict[str, list[str]] = defaultdict(list)
    for owner, missing in issues:
        by_missing[missing].append(owner)

    for missing in sorted(by_missing):
        owners = by_missing[missing]
        print(f"  [缺少] {missing}")
        for o in owners[:5]:  # 最多顯示 5 個依賴方
            print(f"         <- 被 {o} 依賴")
        if len(owners) > 5:
            print(f"         <- 還有 {len(owners)-5} 個 DLL 依賴它")

    print()
    print("修復方式：確認上方缺少的 DLL 是否應該打包進來，")
    print("若是不需要的 CUDA 工具庫，請同時排除 [缺少的 DLL] 和 [依賴它的 DLL]。")
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
