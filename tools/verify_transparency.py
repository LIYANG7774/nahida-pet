# -*- coding: utf-8 -*-
"""验证透明色修复：洋红方块（色键失效）是否彻底消失。

两个层面：
  A. 图像层：逐帧比较"旧合成方式"与"新合成方式"产生的背景污染像素数；
  B. 屏幕层：真跑起来、强制进入 sad/sleep + 粒子特效，截屏窗户区域数洋红像素。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from PIL import Image, ImageDraw, ImageGrab

tk.Tk.mainloop = lambda self, *a, **k: None      # 阻止阻塞

import desktop_pet
from desktop_pet import KEY_RGB, _composite_on_key

# --before：把合成方式还原成"修复前"，用于对照（证明差异）
BEFORE = "--before" in sys.argv
if BEFORE:
    from PIL import ImageOps

    def _old_composite(img):
        bg = Image.new("RGBA", img.size, KEY_RGB + (255,))
        bg.alpha_composite(img)
        return bg.convert("RGB")

    desktop_pet._composite_on_key = _old_composite
    desktop_pet._gray_mix = lambda img, amount: Image.blend(
        img, ImageOps.grayscale(img).convert("RGBA"), amount)
    print(">>> 对照模式：使用【修复前】的合成方式\n")

FULL = tk.Tk                                          # 保留真 Tk 以便建临时窗口
pet = desktop_pet.Pet()
root = pet.root

KEYS = ["idle", "blink", "happy", "sad", "sleep", "hang", "squash", "stretch", "excited"]
MAG = KEY_RGB
SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vshots")

# 记录当前实际显示的是哪一帧
_current = {"key": "idle"}
_photo, _photo_fx = pet._photo, pet._photo_fx


def _rec_photo(key):
    _current["key"] = key
    return _photo(key)


def _rec_fx(key):
    _current["key"] = key
    return _photo_fx(key)


pet._photo, pet._photo_fx = _rec_photo, _rec_fx


def near_magenta(px):
    """洋红家族的判据：绿色通道极低、红蓝接近且都高。

    注意不能太宽松 —— 角色本身的淡紫/粉白（例如 (200,180,220)）不是色键失效，
    真正的故障色是 (255,0,255) 及其变暗版本 (192,0,192) / (141,0,141) 这类"绿=0"的色块。
    """
    r, g, b = px[:3]
    return g < 70 and r > 90 and b > 90 and abs(r - b) < 40


def count_bad(img, step=2):
    """统计"看起来是洋红但不是纯关键色"的像素：这些就是会打穿色键的元凶。"""
    w, h = img.size
    bad = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            p = img.load()[x, y]
            if near_magenta(p) and tuple(p[:3]) != MAG:
                bad += 1
    return bad


print("=== A. 图像层：背景污染像素（越小越好）===")
print(f"{'帧':<9}{'旧合成(alpha_composite)':>26}{'新合成(paste+mask)':>22}")
print("-" * 60)
for k in KEYS:
    rgba = pet._rgba(k).copy()
    old = Image.new("RGBA", rgba.size, MAG + (255,))
    old.alpha_composite(rgba)
    old = old.convert("RGB")
    new = _composite_on_key(rgba)
    print(f"{k:<9}{count_bad(old):>26}{count_bad(new):>22}")

print("\n=== B. 屏幕层：真实窗口截屏 ===")


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def shot(tag):
    """截取宠物窗口区域，只统计"本应透明"的像素里有没有露出洋红。"""
    root.update_idletasks()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    time.sleep(0.25)
    im = ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert("RGB")
    os.makedirs(SHOT_DIR, exist_ok=True)
    safe = "".join(ch for ch in tag if ch.isalnum() or ch in "_+") or "shot"
    im.save(os.path.join(SHOT_DIR, safe + ".png"))

    # 关键：只看"帧里 alpha=0（本该完全透明）"的那些位置
    frame = pet._rgba(_current["key"]).convert("RGBA")
    alpha = frame.getchannel("A")
    px, spx = alpha.load(), im.load()
    fw, fh = frame.size
    bad = tot = 0
    for yy in range(0, min(fh, h)):
        for xx in range(0, min(fw, w)):
            if px[xx, yy] < 250:      # 背景/羽化区（角色主体是 255，不计入）
                tot += 1
                if near_magenta(spx[xx, yy]):
                    bad += 1
    print(f"  {tag:<26} 窗口 {w}x{h}  背景区像素 {tot:>6}  其中露洋红 {bad:>6}  "
          f"({bad / max(1, tot) * 100:5.2f}%)")
    return bad / max(1, tot)


results = {}
pump(0.6)
results["idle"] = shot("idle")
pet.state = "sleep"
pet.state_until = 0
pet.walk_until = 0
pump(0.4)
results["sleep"] = shot("sleep（就是出问题那个）")
pet.particles = []
for _ in range(6):
    pet._spawn("zzz", 1)
pump(0.4)
results["sleep+zzz"] = shot("sleep + 睡觉粒子")
pet.state = "sad"
pet.state_until = pet._now() + 100000
pump(0.5)
results["sad"] = shot("sad")
pet.particles = []
pet._spawn("heart", 5)
pet._spawn("star", 5)
pump(0.4)
results["sad+粒子"] = shot("sad + 爱心/星星")

root.destroy()

print("\n==== 结论 ====")
worst = max(results.items(), key=lambda kv: kv[1])
ok = worst[1] < 0.02
print(f"最差情形：{worst[0]} → 洋红占比 {worst[1] * 100:.1f}%")
print("透明色修复:", "✅ 通过（都是角色自身的粉紫色调，没有整块底）" if ok
      else "❌ 仍有大面积洋红底色")
sys.exit(0 if ok else 1)
