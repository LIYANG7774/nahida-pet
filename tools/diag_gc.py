# -*- coding: utf-8 -*-
"""诊断脚本：检查 PhotoImage 是否被回收导致桌宠图像消失。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk

tk.Tk.mainloop = lambda self, *a, **k: None      # 阻止阻塞

import desktop_pet

pet = desktop_pet.Pet()
root = pet.root


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.008)


def report(tag):
    imgs = root.tk.call("image", "names")
    cur = pet.label.cget("image")
    alive = cur in imgs if cur else False
    print("[%s] label.image=%s  存活=%s  Tcl中图片数=%d  粒子=%d  action=%s"
          % (tag, cur, alive, len(imgs), len(pet.particles),
             (pet.action or {}).get("kind")))
    return alive


pump(0.4)
base = report("初始")

print("\n>>> 触发喂食 _feed()")
pet._feed()
pump(0.4)
a = report("喂食中(有粒子)")

pump(0.6)
b = report("喂食中(有粒子)2")

pump(2.5)
c = report("粒子结束后")

print("\n>>> 触发摸头 _pet_head()")
pet._pet_head()
pump(0.4)
d = report("摸头后(有粒子)")

pump(2.5)
e = report("摸头粒子结束后")

root.destroy()
print("\n==== 结论 ====")
print("喂食期间图像被回收:", not a and not b)
print("粒子结束后恢复:", c)
