# -*- coding: utf-8 -*-
"""诊断脚本：打开 AI 聊天窗口，截图并检查可交互性。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk

tk.Tk.mainloop = lambda self, *a, **k: None

import desktop_pet

pet = desktop_pet.Pet()
root = pet.root


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.008)


pump(0.6)
print("pet 窗口几何:", root.winfo_geometry(), "topmost=", root.attributes("-topmost"),
      "override=", root.overrideredirect())

print("\n>>> 打开聊天窗口")
pet.open_chat()
win = pet.chat_win
pump(1.2)

print("chat: exists=%s mapped=%s viewable=%s state=%s geom=%s"
      % (win.winfo_exists(), win.winfo_ismapped(), win.winfo_viewable(),
         win.wm_state(), win.winfo_geometry()))
print("chat 子控件:", [type(c).__name__ for c in win.winfo_children()])
print("当前 grab:", root.grab_current())

# 检查 entry 位置
print("entry 屏幕坐标:", win.entry.winfo_rootx(), win.entry.winfo_rooty(),
      win.entry.winfo_width(), win.entry.winfo_height())

from PIL import ImageGrab
shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_chat.png")
img = ImageGrab.grab()
img.save(shot)
print("已截图:", shot, img.size)

# 模拟真实鼠标点击聊天窗口输入框
import ctypes

user32 = ctypes.windll.user32


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
    time.sleep(0.25)


ex = win.entry.winfo_rootx() + win.entry.winfo_width() // 2
ey = win.entry.winfo_rooty() + win.entry.winfo_height() // 2
print("\n>>> 模拟点击输入框:", ex, ey)
click(ex, ey)
pump(0.4)
print("点击后焦点:", root.focus_get())
print("点击后输入框内容可写测试:", win.entry.get())

# 模拟点击快捷词条
chips = [c for c in win.winfo_children()]
print("\n>>> 直接调用 send 测试")
win.entry.insert(0, "你好")
win.send()
pump(1.0)
print("history:", win.history)

root.destroy()
print("done")
