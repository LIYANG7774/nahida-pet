# -*- coding: utf-8 -*-
"""启动安装程序，逐页截图，用于人工检查中文界面渲染与排版。

用法：python tools/shot_installer.py <安装包路径> <输出目录>
说明：向向导窗口发送回车（触发默认按钮「下一步/我接受」）翻页，
      截完图后强制结束安装程序，不会真的安装。
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time

from PIL import ImageGrab

u32 = ctypes.windll.user32


def find_wizard(timeout=15.0):
    """找到标题含「纳西妲」的顶层对话框窗口。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(hwnd, _):
            if u32.IsWindowVisible(hwnd):
                n = u32.GetWindowTextLengthW(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u32.GetWindowTextW(hwnd, buf, n + 1)
                    if "纳西妲" in buf.value:
                        r = ctypes.wintypes.RECT()
                        u32.GetWindowRect(hwnd, ctypes.byref(r))
                        found.append((hwnd, buf.value,
                                      (r.left, r.top, r.right, r.bottom)))
            return True

        u32.EnumWindows(cb, 0)
        # 排除主程序（当且仅当窗口宽度像向导）
        for hwnd, title, rect in found:
            if rect[2] - rect[0] > 200:
                return hwnd, title, rect
        time.sleep(0.5)
    return None, None, None


def press_enter(hwnd):
    u32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    u32.PostMessageW(hwnd, 0x0100, 0x0D, 0)   # WM_KEYDOWN VK_RETURN
    u32.PostMessageW(hwnd, 0x0101, 0x0D, 0)   # WM_KEYUP


def main() -> int:
    setup, outdir = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    os.makedirs(outdir, exist_ok=True)
    proc = subprocess.Popen([setup])
    try:
        hwnd, title, rect = find_wizard()
        if not hwnd:
            print("[x] 没找到向导窗口")
            return 1
        print(f"窗口：{title!r} rect={rect}")
        for i in range(5):
            time.sleep(1.2)
            img = ImageGrab.grab(bbox=rect)
            path = os.path.join(outdir, f"page{i}.png")
            img.save(path)
            print(f"  page{i}: {img.size} -> {path}")
            press_enter(hwnd)
    finally:
        time.sleep(0.5)
        proc.kill()
        subprocess.run(["taskkill", "/F", "/IM", os.path.basename(setup)],
                       capture_output=True)
        print("已结束安装程序进程")
    return 0


if __name__ == "__main__":
    import ctypes.wintypes  # noqa: F401  (RECT 依赖)
    sys.exit(main())
