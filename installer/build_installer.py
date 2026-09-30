# -*- coding: utf-8 -*-
"""一条命令产出 Windows 安装包。

用法（在项目任意位置执行都行）：
    python installer/build_installer.py              # 重新打包 exe + 编译安装包
    python installer/build_installer.py --skip-exe   # 跳过 PyInstaller，直接用已有 build_dist
    python installer/build_installer.py --selftest   # 额外产出一个自检包（不写快捷方式/注册表）

产物：
    installer/dist/NahidaPet-Setup-1.0.0.exe
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPEC = os.path.join(ROOT, "NahidaPet.spec")
NSI = os.path.join(HERE, "NahidaPet.nsi")
PAYLOAD = os.path.join(HERE, "build_dist", "NahidaPet.exe")
OUT_DIR = os.path.join(HERE, "dist")

# 唯一装了 Pillow + PyInstaller 的解释器（托管环境里没有 Pillow）
PYI_CANDIDATES = [
    r"C:\Users\19835\.workbuddy\binaries\python\envs\pet\Scripts\pyinstaller.exe",
    os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "python",
                 "envs", "pet", "Scripts", "pyinstaller.exe"),
]


def find_pyinstaller() -> str:
    for p in PYI_CANDIDATES:
        if os.path.exists(p):
            return p
    found = shutil.which("pyinstaller")
    if found:
        return found
    sys.exit("[x] 找不到 pyinstaller：请先 pip install pyinstaller 到带 Pillow 的环境。")


def find_makensis() -> str:
    candidates = [
        os.path.join(ROOT, "build", "nsis", "makensis.exe"),
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    found = shutil.which("makensis")
    if found:
        return found
    sys.exit("[x] 找不到 makensis：请安装 NSIS，或把便携版解压到 build/nsis/ 下。")


def build_exe() -> None:
    pyi = find_pyinstaller()
    print(f"[1/2] PyInstaller 打包主程序 ……\n      {pyi}")
    cmd = [pyi, "--noconfirm", "--distpath", os.path.join(HERE, "build_dist"),
           "--workpath", os.path.join(ROOT, "build", "pyi"), SPEC]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = "\n".join((r.stdout or "").strip().splitlines()[-6:])
    print(tail)
    if r.returncode != 0 or not os.path.exists(PAYLOAD):
        sys.exit("[x] 主程序打包失败。")
    print(f"      ok -> {PAYLOAD} ({os.path.getsize(PAYLOAD):,} bytes)")


def build_setup(selftest: bool = False) -> str:
    mk = find_makensis()
    os.makedirs(OUT_DIR, exist_ok=True)
    defines = [f"/DSRCROOT={ROOT}"]
    if selftest:
        defines.append("/DTESTBUILD")
    print(f"[2/2] 编译安装包 ……\n      {mk}")
    cmd = [mk, "-INPUTCHARSET", "UTF8", *defines, NSI]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or "Error in script" in out:
        print(out[-2500:])
        sys.exit("[x] 安装包编译失败。")
    name = "_selftest-setup.exe" if selftest else "NahidaPet-Setup-1.0.0.exe"
    out_file = os.path.join(OUT_DIR, name)
    print(f"      ok -> {out_file} ({os.path.getsize(out_file):,} bytes)")
    return out_file


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-exe", action="store_true", help="跳过主程序打包")
    ap.add_argument("--selftest", action="store_true", help="额外产出不写注册表的自检包")
    args = ap.parse_args()

    if not args.skip_exe:
        build_exe()
    elif not os.path.exists(PAYLOAD):
        sys.exit(f"[x] 没有可用的主程序：{PAYLOAD}")

    build_setup(selftest=args.selftest)


if __name__ == "__main__":
    main()
