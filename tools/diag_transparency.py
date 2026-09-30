# -*- coding: utf-8 -*-
"""诊断脚本：检查各帧合成到关键色后的背景是否还是"纯洋红"。

Tk 的 -transparentcolor 是精确色键：只要背景像素不是 255,0,255，整块背景就会显形。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from PIL import Image

tk.Tk.mainloop = lambda self, *a, **k: None      # 阻止阻塞

import desktop_pet
from desktop_pet import KEY

pet = desktop_pet.Pet()
root = pet.root

MAGENTA = (255, 0, 255)
KEYS = ["idle", "blink", "happy", "sad", "sleep", "hang", "squash", "stretch",
        "excited", "rot15", "rot90", "rot270"]

print(f"Tk 认为的关键色 KEY={KEY!r} -> {root.winfo_rgb(KEY)}")
print(f"窗口 transparentcolor = {root.attributes('-transparentcolor')!r}\n")
print(f"{'帧':<9}{'尺寸':<12}{'角点RGBA':<22}{'合成后角点':<16}{'是否纯洋红':<10}{'背景alpha范围'}")
print("-" * 92)


def analyze(key):
    img = pet._rgba(key).copy()                     # RGBA 原始帧
    w, h = img.size
    px = img.load()
    # 采样四角与边缘中点的 alpha，判断背景是否真的全透明
    pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1)]
    alphas = [px[p][0] and px[p][3] for p in pts]
    a_min, a_max = min(alphas), max(alphas)

    bg = Image.new("RGBA", img.size, MAGENTA + (255,))
    bg.alpha_composite(img)
    rgb = bg.convert("RGB")
    corner = rgb.load()[0, 0]
    exact = corner == MAGENTA
    # 统计"看起来是洋红但不是纯洋红"的像素个数（这些会把色键打穿）
    near = 0
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            r, g, b = rgb.load()[x, y]
            if r > 150 and b > 150 and g < 200 and (r, g, b) != MAGENTA:
                near += 1
    return img.size, corner, exact, (a_min, a_max), near


for k in KEYS:
    try:
        size, corner, exact, arange, near = analyze(k)
        flag = "✅" if exact else "❌ 会露馅"
        print(f"{k:<9}{str(size):<12}{str(corner):<22}{str(corner):<16}{flag:<10}alpha={arange} 近洋红像素={near}")
    except Exception as e:
        print(f"{k:<9}错误: {e}")

print("\n=== 粒子特效帧（模拟 zzz 睡觉特效）===")
pet.size_name = pet.size_name
pet.state = "sleep"
pet.particles = []
pet._spawn("zzz", 3)
img = pet._rgba("sleep").copy()
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
from PIL import ImageDraw
d = ImageDraw.Draw(overlay)
for p in pet.particles:
    pet._draw_particle(d, p)
img.alpha_composite(overlay)
bg = Image.new("RGBA", img.size, MAGENTA + (255,))
bg.alpha_composite(img)
rgb = bg.convert("RGB")
print("特效帧角点:", rgb.load()[0, 0], "→", "✅ 纯洋红" if rgb.load()[0, 0] == MAGENTA else "❌ 不是纯洋红")

root.destroy()
