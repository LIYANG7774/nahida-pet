# -*- coding: utf-8 -*-
"""处理桌宠素材 v2：清除画进图里的棋盘格背景 -> 裁剪 -> 缩放 -> 边缘羽化。

思路：棋盘格是浅灰/白交替且大面积与图像边缘相连，人物有深色描边。
从四边开始 BFS 泛洪，凡是"浅色低饱和"或"半透明"的像素都视为背景删除，
人物内部的白裙因有描边包围不会被波及。
"""
from PIL import Image, ImageFilter
from collections import deque
import os

RAW = os.path.join(os.path.dirname(__file__), "assets_raw")
OUT = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(OUT, exist_ok=True)

TARGET = 320
frames = ["frame_idle.png", "frame_blink.png", "frame_happy.png"]


def is_bg(r, g, b, a):
    """判定是否为背景类像素：浅色低饱和（棋盘格白/灰）或明显半透明。"""
    if a < 250:
        return True
    mx, mn = max(r, g, b), min(r, g, b)
    return mn >= 185 and (mx - mn) <= 18


def clean(img):
    w, h = img.size
    px = img.load()
    removed = [[False] * w for _ in range(h)]
    q = deque()
    # 所有边缘上的背景类像素作为种子
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(*px[x, y]):
                q.append((x, y)); removed[y][x] = True
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(*px[x, y]):
                q.append((x, y)); removed[y][x] = True
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not removed[ny][nx]:
                if is_bg(*px[nx, ny]):
                    removed[ny][nx] = True
                    q.append((nx, ny))
    # 应用删除 + 生成保留掩码
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if removed[y][x]:
                px[x, y] = (0, 0, 0, 0)
            else:
                r, g, b, a = px[x, y]
                mp[x, y] = a
    # 软边处理：模糊后的保留掩码取 min，去掉浅色描边光晕
    soft = mask.filter(ImageFilter.GaussianBlur(1.2))
    sp = soft.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            na = min(a, sp[x, y])
            if na != a:
                px[x, y] = (r, g, b, na)
    return img


for name in frames:
    img = Image.open(os.path.join(RAW, name)).convert("RGBA")
    img = clean(img)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    scale = TARGET / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img.save(os.path.join(OUT, name))
    print(f"{name}: {img.size}")

sheet = Image.new("RGBA", (TARGET * 3 + 80, TARGET + 40), (245, 245, 245, 255))
x = 20
for name in frames:
    f = Image.open(os.path.join(OUT, name))
    sheet.paste(f, (x, 20), f)
    x += TARGET + 20
sheet.convert("RGB").save(os.path.join(OUT, "_preview.jpg"), quality=90)
print("preview saved")
