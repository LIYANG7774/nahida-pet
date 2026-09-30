# -*- coding: utf-8 -*-
"""端到端验证打包后的 exe：能启动、渲染正常（没有洋红方块）、没有新报错。

用法: python tools/verify_exe.py [exe路径] [运行秒数]
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

EXE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "installer", "build_dist", "NahidaPet.exe")
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 12
LOG = os.path.join(os.path.expanduser("~"), ".nahida_pet", "error.log")

u32 = ctypes.WinDLL("user32", use_last_error=True)
u32.EnumWindows.restype = wintypes.BOOL
u32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
                            wintypes.LPARAM]


def find_pet_windows():
    """找到所有宠物窗口（Tk 顶层窗口 TkTopLevel，尺寸在宠物范围内）。

    注意：PyInstaller 单文件版的 GUI 跑在子进程里，父进程 pid 对不上，所以按窗口特征找。
    """
    found = []

    def cb(hwnd, _l):
        if not u32.IsWindowVisible(hwnd):
            return True
        r = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if not (100 < w < 350 and 100 < h < 420):
            return True
        cls = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, cls, 256)
        if cls.value != "TkTopLevel":
            return True
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.append((hwnd, (r.left, r.top, r.right, r.bottom), cls.value, pid.value))
        return True

    u32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found


def near_magenta(px):
    r, g, b = px[:3]
    return g < 70 and r > 90 and b > 90 and abs(r - b) < 40


def log_lines():
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            return len(f.readlines())
    except OSError:
        return 0


before = log_lines()
pre = {w[3] for w in find_pet_windows()}          # 先记录已经在跑的宠物进程，避免误测
print(f"启动 {os.path.basename(EXE)}（{os.path.getsize(EXE):,} bytes）…")
proc = subprocess.Popen([EXE])
ok = False
try:
    time.sleep(4)
    if proc.poll() is not None:
        print(f"❌ 进程已退出，退出码 {proc.returncode}")
        sys.exit(1)

    end = time.time() + SECONDS
    best = None
    while time.time() < end:
        cand = [w for w in find_pet_windows() if w[3] not in pre]
        if cand:
            best = cand[0]
        time.sleep(1.0)

    if not best:
        print("❌ 没找到宠物窗口（可能启动失败）")
        sys.exit(1)

    hwnd, (x1, y1, x2, y2), cls, tid = best
    w, h = x2 - x1, y2 - y1
    print(f"找到宠物窗口 {cls} {w}x{h} @ ({x1},{y1})")
    time.sleep(0.6)
    im = ImageGrab.grab(bbox=(x1, y1, x2, y2)).convert("RGB")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vshots", "exe_window.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)
    bad = sum(1 for p in im.getdata() if near_magenta(p))
    ratio = bad / (w * h)
    print(f"窗口内洋红家族像素 {bad} / {w * h} = {ratio * 100:.1f}%（角色自身粉紫约 2~3%，>15% 说明底色露出来了）")
    ok = ratio < 0.15
    print("渲染:", "✅ 正常" if ok else "❌ 出现洋红底")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)

after = log_lines()
print(f"error.log 行数 {before} → {after}", "✅ 无新报错" if after <= before else "❌ 有新报错")
print("结论:", "✅ 通过" if (ok and after <= before) else "❌ 未通过")
sys.exit(0 if (ok and after <= before) else 1)
