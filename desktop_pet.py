# -*- coding: utf-8 -*-
"""
纳西妲桌宠 v2 —— 取材自桌面壁纸形象
功能：
  - 桌面常驻、置顶、背景透明，呼吸浮动 + 眨眼
  - 声音：合成互动音效（摸头/喂食/跳跃/聊天…），不含语音朗读
  - AI 聊天：右键「和我聊天」，在设置里填任意 OpenAI 兼容 API Key
    （OpenAI / DeepSeek / Kimi / 智谱 / 通义 / 硅基流动 / 本地 Ollama）
  - 更多互动：摸头、喂点心、逗她玩、讲故事、猜谜语、拖起来会挣扎、
    落地会弹跳、心情/饱食度系统、长时间不理她会睡着
用法：
  python desktop_pet.py              # 正常运行
  python desktop_pet.py --smoke-test # 冒烟测试，2.5 秒后自动退出
"""
import math
import os
import random
import sys
import tkinter as tk

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageTk

import pet_config
from pet_audio import Audio
from pet_chat import ChatWindow


def _res(rel):
    """兼容源码运行与 PyInstaller 打包后的资源路径。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = _res("assets")
SFX = _res(os.path.join("assets", "sfx"))

KEY = "magenta"            # 抠透明用的关键色（素材中不存在）
KEY_RGB = (255, 0, 255)    # 关键色的 RGB：背景像素必须与之"完全相等"，差一点都不透明

# 边缘处理参数（关键色是硬色键，任何"和关键色混合过的像素"都会显形成粉紫描边）：
_ALPHA_CUT = 96      # 比这个还淡的像素直接当全透明（裁掉原图的柔光/阴影晕圈）
_ALPHA_FULL = 176    # 到这个透明度就是实心，中间做一段平滑过渡，避免锯齿


def _extend_colors(img, rounds=3):
    """把角色自身的颜色向外扩几圈，替换掉羽化区里"其实看不太出来"的颜色。

    否则羽化像素会和关键色混成粉紫，在角色周围留下明显的紫色描边。
    """
    rgb = img.convert("RGB")
    solid = img.getchannel("A").point(lambda v: 255 if v >= 200 else 0)
    for _ in range(rounds):
        grown_rgb = rgb.filter(ImageFilter.MaxFilter(3))
        grown_solid = solid.filter(ImageFilter.MaxFilter(3))
        newly = ImageChops.subtract(grown_solid, solid)     # 这一圈新扩出来的像素
        rgb = Image.composite(grown_rgb, rgb, newly)
        solid = grown_solid
    return rgb


def _composite_on_key(img):
    """把 RGBA 帧叠到关键色底上，保证"该透明的地方"严格等于关键色。

    这是透明能生效的前提：Tk 的 -transparentcolor 是精确色键，
    背景像素但凡不是 (255,0,255)，整块背景就会显形。
    """
    span = max(1, _ALPHA_FULL - _ALPHA_CUT)
    alpha = img.getchannel("A").point(
        lambda v: 0 if v < _ALPHA_CUT else (255 if v >= _ALPHA_FULL
                                            else int((v - _ALPHA_CUT) * 255 / span)))
    bg = Image.new("RGB", img.size, KEY_RGB)
    bg.paste(_extend_colors(img), (0, 0), alpha)
    return bg


def _gray_mix(img, amount):
    """按 amount 混入灰度（去饱和），且保留原图 alpha。

    坑：ImageOps.grayscale(img).convert("RGBA") 会把 alpha 全部变成 255，
    与它 blend 之后整张图的背景都变成半透明 —— 色键失效、桌面露出一块洋红。
    """
    gray = ImageOps.grayscale(img).convert("RGBA")
    gray.putalpha(img.getchannel("A"))
    return Image.blend(img, gray, amount)

# ---------------- 台词库 ----------------
QUOTES = [
    "世界如此美丽，你不打算多看看吗？",
    "知识就像种子，需要耐心浇灌哦。",
    "今天有什么开心的事，愿意讲给我听吗？",
    "休息一下也好，梦里会有新的智慧。",
    "草木会记得每一个温柔的人。",
    "要不要一起读会儿书？",
    "你在想什么呢？说来听听嘛。",
    "再忙，也别忘了看看窗外的天空哦。",
    "嘿嘿，被你发现啦。",
    "刚才是不是有只蝴蝶飞过去啦？",
    "虚空在唱歌呢，你听到了吗？",
    "我把今天的阳光存起来了一点，送给你。",
]

PET_LINES = [          # 摸头反应
    "呜嘿嘿……好舒服呀。",
    "头、头发会乱掉的啦～",
    "再摸的话……我就要睡着了哦。",
    "你今天心情很好嘛？",
    "像被春风吹过一样，暖暖的。",
    "摸头可以，知识也要一起分享哦。",
    "唔……被看穿了其实我很喜欢这样。",
]

POKE_LINES = [         # 连续戳
    "别戳啦别戳啦，要漏气了！",
    "呜哇——再戳我就要发芽了！",
    "好痒好痒！休想从我这里挖走小秘密～",
    "再、再戳就要生气了哦……才怪。",
]

DRAG_LINES = [         # 被拎起来
    "呜哇！我要掉下去啦！",
    "放、放我下来～这样很害羞的！",
    "飞起来啦……可是好可怕呀！",
    "提着后领不算抱的！",
]

DROP_LINES = [
    "安全落地！刚才好刺激……",
    "下次记得用两只手抱我嘛。",
    "唔，晕乎乎的……",
]

HUNGRY_LINES = [
    "肚子咕噜咕噜叫了……有吃的吗？",
    "好想吃甜的呀，比如甜甜花……",
    "闻到点心的味道了吗？是我饿了。",
]

SAD_LINES = [
    "有点没精神……摸摸我就会好起来哦。",
    "今天的风有点凉呢。",
    "心情像缺水的植物……需要浇灌一下。",
]

WAKE_LINES = [
    "唔……我睡过头了吗？",
    "梦到一棵好大好大的树……",
    "早安……咦，现在几点啦？",
]

FEED_LINES = [
    "开动啦！唔唔，好好吃！",
    "这个世界上的点心真是伟大的发明。",
    "谢谢款待！幸福指数上升中～",
]

STORIES = [
    "从前有一粒种子，被埋在最黑的土里。它没有哭，只是安静地往下扎根、往上发芽。"
    "很多年后，路过的旅人在树下乘凉，笑着说：真是一棵好树啊。——所以呀，慢慢来，没关系的。",
    "有个小沙弥问老树：您站了一千年，不无聊吗？老树说：我把根伸进大地，把枝叶交给天空，"
    "鸟儿的歌、路人的话，都是讲给我听的故事呢。",
    "传说每颗星星都是一个没说完的愿望。所以下次许愿的时候，记得把结尾也讲完哦。",
]

RIDDLES = [
    ("什么东西越洗越脏？", "水呀～"),
    ("什么植物最会说话？", "含羞草，一碰就害羞啦。"),
    ("什么东西不问不说、一问就说？", "秘密哦。"),
    ("什么门永远关不上？", "球门呀！"),
    ("什么东西天气越热爬得越高？", "温度计哦。"),
]


class Pet:
    SIZES = {"小": 160, "中": 240, "大": 320}
    VOL_PRESET = {"小": 0.4, "中": 0.7, "大": 1.0}

    def __init__(self, smoke_test=False):
        self.smoke_test = smoke_test
        self.cfg = pet_config.load()

        # ---- 运行状态 ----
        self.state = "idle"            # idle / happy / sad / sleep
        self.state_until = 0
        self.action = None             # {"kind","until",...} 覆盖表情的动作
        self.bubble_until = 0
        self.walk_until = 0
        self.walk_dir = 1
        self.phase = 0.0
        self.base_y = 0                # 脚底"地面"的屏幕 y
        self.x = 0
        self.particles = []            # 粒子特效
        self._fx_photo = None          # 持有特效帧的引用，防止被 GC 回收导致宠物消失
        self.click_times = []          # 连击检测
        self.last_interact = 0         # 最后交互时刻
        self.thinking = False
        self.chat_win = None

        st = pet_config.get_state()
        self.mood = st["mood"]
        self.fullness = st["fullness"]

        # ---- 素材 ----
        self.src = {}
        for name in ("idle", "blink", "happy"):
            self.src[name] = Image.open(os.path.join(ASSETS, "frame_%s.png" % name)).convert("RGBA")
        self.cache = {}       # (key,size) -> PhotoImage
        self.rgba = {}        # (key,size) -> RGBA Image（供粒子合成）

        # ---- 音频 ----
        self.audio = Audio(lambda: self.cfg, SFX)

        # ---- 主窗口 ----
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=KEY)
        try:
            self.root.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass

        self.label = tk.Label(self.root, bg=KEY, bd=0)
        self.label.pack()

        # ---- 气泡 ----
        self.bubble = tk.Toplevel(self.root)
        self.bubble.overrideredirect(True)
        self.bubble.attributes("-topmost", True)
        self.bubble_label = tk.Label(
            self.bubble, text="", bg="#fffbe6", fg="#3a5a40",
            font=("Microsoft YaHei UI", 10), wraplength=250, justify="left",
            padx=10, pady=6, bd=1, relief="solid",
        )
        self.bubble_label.pack()
        self.bubble.withdraw()

        # ---- 交互绑定 ----
        self.label.bind("<Button-1>", self._on_press)
        self.label.bind("<B1-Motion>", self._on_drag)
        self.label.bind("<ButtonRelease-1>", self._on_release)
        self.label.bind("<Double-Button-1>", self._on_double)
        self.label.bind("<Button-3>", self._on_menu)
        self.label.bind("<Enter>", self._on_hover)
        self.label.bind("<MouseWheel>", self._on_wheel)
        self.menu = self._build_menu()

        # ---- 初始位置：屏幕右下 ----
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.x = sw - 280
        self.base_y = sh - 110
        self._apply_size(self.cfg.get("pet", {}).get("size", "中"))
        self.root.geometry(f"+{self.x}+{self.base_y}")

        # ---- 定时器 ----
        now = self._now()
        self.last_interact = now
        self.next_blink = self._after_ms(random.randint(2000, 5000))
        self._blink_end = 0
        self.walk_next = 0
        self._save_job = None
        self.root.after(random.randint(12000, 20000), self._idle_action)
        self.root.after(60000, self._decay_tick)

        self._tick()
        if smoke_test:
            self.root.after(2500, self.root.destroy)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.report_callback_exception = _log_exception
        self.root.mainloop()

    # ================= 工具 =================
    def _now(self):
        return int(self.root.tk.call("clock", "milliseconds"))

    def _after_ms(self, ms):
        return self._now() + ms

    def cfg_getter(self):
        return self.cfg

    def _touch(self):
        self.last_interact = self._now()
        if self.state == "sleep":
            self.state = "idle"
            self.say(random.choice(WAKE_LINES))
            self.audio.play("greet")

    # ================= 帧生成 =================
    def _make_frame(self, key, target):
        """按 key 生成指定尺寸的 RGBA 帧（未合成背景色）。"""
        if key in ("idle", "blink", "happy"):
            img = self.src[key].copy()
        elif key == "sad":
            img = self.src["idle"].copy()
            img = _gray_mix(img, 0.45)
            img = ImageEnhance.Brightness(img).enhance(0.9)
        elif key == "sleep":
            img = self.src["blink"].copy()
            img = _gray_mix(img, 0.25)
            img = ImageEnhance.Brightness(img).enhance(0.72)
            img = img.rotate(-8, expand=True, resample=Image.BICUBIC)
        elif key == "hang":
            img = self.src["happy"].copy().rotate(6, expand=True, resample=Image.BICUBIC)
        elif key == "squash":
            img = self.src["happy"].copy()
        elif key == "stretch":
            img = self.src["idle"].copy()
        elif key == "excited":
            img = ImageEnhance.Brightness(self.src["happy"].copy()).enhance(1.05)
        elif key.startswith("rot"):
            ang = int(key[3:])
            img = self.src["happy"].copy().rotate(ang, expand=True, resample=Image.BICUBIC)
        else:
            img = self.src["idle"].copy()

        if key == "squash":
            img = img.resize((int(img.width * 1.10), int(img.height * 0.88)), Image.LANCZOS)
        elif key == "stretch":
            img = img.resize((int(img.width * 0.92), int(img.height * 1.10)), Image.LANCZOS)
        elif key == "excited":
            s = 1.05
            img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)

        scale = target / max(img.size)
        if scale != 1:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                             Image.LANCZOS)
        return img

    def _rgba(self, key):
        target = self.SIZES[self.size_name]
        ck = (key, target)
        if ck not in self.rgba:
            self.rgba[ck] = self._make_frame(key, target)
        return self.rgba[ck]

    def _photo(self, key):
        """返回合成到关键色上的 PhotoImage。"""
        target = self.SIZES[self.size_name]
        ck = (key, target)
        if ck not in self.cache:
            self.cache[ck] = ImageTk.PhotoImage(_composite_on_key(self._rgba(key).copy()))
        return self.cache[ck]

    def _photo_fx(self, key):
        """带粒子特效的帧（每帧重建，仅特效期间调用）。"""
        img = self._rgba(key).copy()
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        for p in self.particles:
            self._draw_particle(d, p)
        img.alpha_composite(overlay)
        return ImageTk.PhotoImage(_composite_on_key(img))

    @staticmethod
    def _draw_particle(d, p):
        x, y = p["x"], p["y"]
        life = p["life"] / max(1, p["max"])
        # 只在最后 35% 的生命里淡出：半透明像素和关键色混合会露出洋红边
        a = 255 if life > 0.35 else int(255 * (life / 0.35))
        kind = p["kind"]
        if kind == "heart":
            s = int(p["s"] * (0.6 + 0.4 * life))
            col = (255, 120, 150, a)
            d.ellipse([x - s, y - s, x, y], fill=col)
            d.ellipse([x, y - s, x + s, y], fill=col)
            d.polygon([(x - s, y - s * 0.35), (x + s, y - s * 0.35), (x, y + s)], fill=col)
        elif kind == "star":
            s = p["s"] * (0.6 + 0.4 * life)
            pts = []
            for i in range(10):
                ang = math.pi / 5 * i - math.pi / 2
                r = s if i % 2 == 0 else s * 0.45
                pts.append((x + r * math.cos(ang), y + r * math.sin(ang)))
            d.polygon(pts, fill=(255, 214, 90, a))
        elif kind == "sparkle":
            s = p["s"] * life
            pts = [(x, y - s), (x + s * 0.28, y - s * 0.28), (x + s, y),
                   (x + s * 0.28, y + s * 0.28), (x, y + s), (x - s * 0.28, y + s * 0.28),
                   (x - s, y), (x - s * 0.28, y - s * 0.28)]
            d.polygon(pts, fill=(190, 255, 170, a))
        elif kind == "zzz":
            fsize = max(9, int(10 + (1 - life) * 8))
            try:
                font = ImageFont.truetype("arial.ttf", fsize)
            except Exception:
                font = ImageFont.load_default()
            d.text((x, y), "z", font=font, fill=(130, 150, 200, a))
        elif kind == "crumb":
            s = max(1, int(p["s"] * life))
            d.ellipse([x - s, y - s, x + s, y + s], fill=(150, 190, 100, a))

    def _spawn(self, kind, n=1, region="head"):
        w = self.root.winfo_width() or self.SIZES[self.size_name]
        h = self.root.winfo_height() or self.SIZES[self.size_name]
        for _ in range(n):
            if region == "head":
                px, py = random.uniform(w * 0.35, w * 0.65), random.uniform(h * 0.08, h * 0.22)
            elif region == "mouth":
                px, py = w * 0.5 + random.uniform(-8, 8), random.uniform(h * 0.45, h * 0.55)
            else:
                px, py = random.uniform(w * 0.2, w * 0.8), random.uniform(h * 0.3, h * 0.6)
            p = {"x": px, "y": py, "kind": kind, "max": random.randint(12, 20), "life": 0}
            if kind == "heart":
                p.update(vx=random.uniform(-0.4, 0.4), vy=random.uniform(-1.4, -0.8), s=random.uniform(4, 7))
            elif kind == "star":
                p.update(vx=random.uniform(-0.7, 0.7), vy=random.uniform(-1.6, -0.9), s=random.uniform(4, 8))
            elif kind == "sparkle":
                p.update(vx=random.uniform(-0.5, 0.5), vy=random.uniform(-1.2, -0.5), s=random.uniform(5, 9))
            elif kind == "zzz":
                p.update(vx=0.5, vy=-0.35, s=6)
            elif kind == "crumb":
                p.update(vx=random.uniform(-0.5, 0.5), vy=random.uniform(0.5, 1.2), s=random.uniform(2, 3.5))
            self.particles.append(p)

    def _apply_size(self, name):
        self.size_name = name
        self.cfg.setdefault("pet", {})["size"] = name
        self.cache.clear()
        self.rgba.clear()
        ph = self._photo("idle")
        self.root.geometry(f"{ph.width()}x{ph.height()}")
        self._assert_transparent()

    def _assert_transparent(self):
        """重申色键。窗口重建/重绘后色键偶尔会掉，掉了就会露出一整块洋红底。"""
        try:
            self.root.config(bg=KEY)
            self.label.config(bg=KEY)
            self.root.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass

    # ================= 动作 =================
    def _do(self, kind, dur_ms, **data):
        self.action = {"kind": kind, "until": self._after_ms(dur_ms), "t0": self._now()}
        self.action.update(data)

    def react(self, kind, dur=2000, quiet=False):
        """kind: happy / sad / excited / sleep"""
        self.state = kind
        self.state_until = self._after_ms(dur)
        if not quiet:
            sound = {"happy": "happy", "excited": "magic", "sad": "sad", "sleep": "sleep"}.get(kind)
            if sound:
                self.audio.play(sound)
            if kind == "happy":
                self._spawn("heart", random.randint(2, 4))
            elif kind == "excited":
                self._spawn("star", random.randint(3, 5))
                self._spawn("sparkle", random.randint(3, 5))

    def jump(self, times=1):
        self._do("jump", 520 * times, times=times, t0=self._now())
        self.audio.play("jump")

    def spin(self):
        self._do("spin", 900)
        self.audio.play("magic")
        self._spawn("star", 4)

    # ================= 台词 / 气泡 =================
    def say(self, text, chat=False):
        self.bubble_label.config(text=text)
        self.bubble.deiconify()
        self.bubble.update_idletasks()
        bx = self.x + (self.root.winfo_width() - self.bubble.winfo_width()) // 2
        by = (self.base_y - self.root.winfo_height()) - self.bubble.winfo_height() - 6
        self.bubble.geometry(f"+{max(0, bx)}+{max(0, by)}")
        ms = min(15000, 3200 + len(text) * 85)
        if chat:
            ms = min(20000, 5000 + len(text) * 60)
        self.bubble_until = self._after_ms(ms)

    def set_thinking(self, on):
        self.thinking = on
        if on:
            self.bubble_label.config(text="让我想想……💭")
            self.bubble.deiconify()
            self.bubble_until = 0
        else:
            self.bubble_until = self._after_ms(500)

    def on_chat_closed(self):
        self.chat_win = None

    # ================= 事件 =================
    def _on_press(self, e):
        self._touch()
        self._dx = e.x
        self._dy = e.y
        self._moved = False
        self._press_y_root = e.y_root

    def _on_drag(self, e):
        if not getattr(self, "_moved", False):
            if abs(e.x - self._dx) > 5 or abs(e.y - self._dy) > 5:
                self._moved = True
            else:
                return
        self.x = e.x_root - self._dx
        h = self.root.winfo_height() or self.SIZES[self.size_name]
        self.base_y = (e.y_root - self._dy) + h
        if not (self.action and self.action.get("kind") == "hang"):
            self.action = None
            self._do("hang", 10 ** 7)
            self.audio.play("poke")
            self.say(random.choice(DRAG_LINES))
        elif random.random() < 0.008:
            self.say(random.choice(DRAG_LINES))

    def _on_release(self, e):
        self._touch()
        if getattr(self, "_moved", False):
            self._moved = False
            self.action = None
            self.audio.play("land")
            sh = self.root.winfo_screenheight()
            if self.base_y > sh:
                self.base_y = sh - 110
            # 落地小弹跳：压扁 -> 拉伸
            self._do("squash", 160)
            self.root.after(160, self._land_bounce2)
            if random.random() < 0.4:
                self.root.after(600, lambda: self.say(random.choice(DROP_LINES)))
            self._save_soon()
            return
        # 单击 = 摸头
        now = self._now()
        self.click_times = [t for t in self.click_times if now - t < 1500] + [now]
        self.audio.play("click")
        if len(self.click_times) >= 5:
            self.click_times.clear()
            self.audio.play("poke")
            self.say(random.choice(POKE_LINES))
            self._spawn("star", 3)
            self.mood = pet_config.update_state(mood=self.mood - 2)["mood"]
            return
        self._pet_head()

    def _land_bounce2(self):
        if self.action and self.action.get("kind") == "squash":
            self._do("stretch", 160)

    def _pet_head(self):
        self.audio.play("pet")
        self._spawn("heart", random.randint(2, 4))
        self.mood = pet_config.update_state(mood=self.mood + 3)["mood"]
        r = random.random()
        if self.fullness < 25:
            self.say("摸头好舒服……可是肚子还是好饿呀……")
        elif r < 0.55:
            self.say(random.choice(PET_LINES))
            self.react("happy", quiet=True)
        else:
            self.react("happy", dur=1500, quiet=True)
            self.root.after(1600, lambda: self.say(random.choice(QUOTES)))

    def _on_double(self, _e):
        self._touch()
        self.audio.play("greet")
        self.react("happy")
        self.say("嗨～今天也一起加油吧！")

    def _on_hover(self, _e):
        if random.random() < 0.06 and self._now() > self.bubble_until:
            self.say(random.choice(QUOTES))

    def _on_wheel(self, e):
        sizes = list(self.SIZES)
        idx = sizes.index(self.size_name)
        if e.delta > 0 and idx < len(sizes) - 1:
            idx += 1
        elif e.delta < 0 and idx > 0:
            idx -= 1
        else:
            return
        self._apply_size(sizes[idx])

    # ================= 右键菜单 =================
    def _build_menu(self):
        m = tk.Menu(self.root, tearoff=0)

        m.add_command(label="摸摸头", command=self._pet_head)
        m.add_command(label="打个招呼", command=self._on_double2)
        m.add_command(label="喂点心 🍡", command=self._feed)
        m.add_command(label="逗她玩 ✨", command=self._play)
        m.add_command(label="讲个故事", command=self._story)
        m.add_command(label="猜个谜语", command=self._riddle)

        m.add_separator()
        m.add_command(label="和我聊天 (AI) 💬", command=self.open_chat)
        m.add_command(label="设置 AI Key…", command=self.open_settings)

        m.add_separator()
        self.var_sound = tk.BooleanVar(value=bool(self.cfg.get("sound", True)))
        self.var_walk = tk.BooleanVar(value=bool(self.cfg.get("pet", {}).get("auto_walk", True)))
        m.add_checkbutton(label="音效", variable=self.var_sound, command=self._toggle_sound)
        vol = tk.Menu(m, tearoff=0)
        for name in ("小", "中", "大"):
            vol.add_command(label=name, command=lambda n=name: self._set_volume(n))
        m.add_cascade(label="音量", menu=vol)

        m.add_separator()
        size_menu = tk.Menu(m, tearoff=0)
        for name in self.SIZES:
            size_menu.add_command(label=name, command=lambda n=name: self._apply_size(n))
        m.add_cascade(label="大小", menu=size_menu)
        m.add_checkbutton(label="自动走动", variable=self.var_walk, command=self._toggle_walk)
        pos = tk.Menu(m, tearoff=0)
        pos.add_command(label="屏幕左边", command=lambda: self._move_to(0.06))
        pos.add_command(label="屏幕中间", command=lambda: self._move_to(0.46))
        pos.add_command(label="屏幕右边", command=lambda: self._move_to(0.85))
        m.add_cascade(label="位置", menu=pos)
        m.add_command(label="现在的心情…", command=self._show_status)

        m.add_separator()
        m.add_command(label="开机自启", command=self._toggle_autostart)
        m.add_command(label="退出", command=self._quit)
        return m

    def _on_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _on_double2(self):
        self.audio.play("greet")
        self.react("happy")
        self.say("嗨～嘿嘿。")

    # ---------------- 菜单动作 ----------------
    def _feed(self):
        self._touch()
        if self.fullness > 92:
            self.audio.play("sad")
            self.say("唔……肚子饱饱的，吃不下更多啦。")
            return
        self.audio.play("feed")
        self._do("eat", 2200)
        self._spawn("crumb", 8, region="mouth")
        self.fullness = pet_config.update_state(fullness=self.fullness + 14)["fullness"]
        self.mood = pet_config.update_state(mood=self.mood + 5)["mood"]
        self.root.after(2300, lambda: self.say(random.choice(FEED_LINES)))
        self.root.after(2300, lambda: self._spawn("heart", 2))

    def _play(self):
        self._touch()
        r = random.random()
        if r < 0.34:
            self.spin()
            self.say("转圈圈～看我的新魔法！")
        elif r < 0.67:
            self.jump(2)
            self.say("看我跳得多高！")
        else:
            self.audio.play("magic")
            self.react("excited", 2200)
            self.say("变——变出一颗星星送给你！")
            self._spawn("star", 6)
        self.mood = pet_config.update_state(mood=self.mood + 4)["mood"]

    def _story(self):
        self._touch()
        self.audio.play("greet")
        self.say(random.choice(STORIES))

    def _riddle(self):
        self._touch()
        q, a = random.choice(RIDDLES)
        self.say("考考你：" + q)
        self.root.after(6000, lambda: self.say("答案揭晓：" + a))

    def _show_status(self):
        mood, full = self.mood, self.fullness
        face = "😊" if mood >= 70 else ("🙂" if mood >= 40 else "🥀")
        self.say("心情：%d/100 %s\n饱食度：%d/100" % (mood, face, full))

    def _move_to(self, ratio):
        sw = self.root.winfo_screenwidth()
        self.x = int(sw * ratio)
        self.audio.play("jump")

    def _toggle_sound(self):
        self.cfg["sound"] = self.var_sound.get()
        pet_config.save(self.cfg)
        if self.cfg["sound"]:
            self.audio.play("happy")

    def _set_volume(self, name):
        self.cfg.setdefault("pet", {})["sound_volume"] = self.VOL_PRESET[name]
        pet_config.save(self.cfg)
        self.audio.play("greet")

    def _toggle_walk(self):
        self.cfg.setdefault("pet", {})["auto_walk"] = self.var_walk.get()
        pet_config.save(self.cfg)

    def open_chat(self):
        if self.chat_win and self.chat_win.winfo_exists():
            self.chat_win.deiconify()
            self.chat_win.lift()
            self.chat_win.focus_set()
        else:
            self.chat_win = ChatWindow(self)
            self.audio.play("chat")

    def open_settings(self):
        from pet_chat import AISettingsDialog
        AISettingsDialog(self)

    # ================= 定时系统 =================
    def _decay_tick(self):
        """每 60s：心情/饱食度衰减，太低会闹情绪；太久没交互会睡着。"""
        self.mood = pet_config.update_state(mood=self.mood - 1)["mood"]
        self.fullness = pet_config.update_state(fullness=self.fullness - 1)["fullness"]
        idle_ms = self._now() - self.last_interact

        if idle_ms > 180000 and self.state != "sleep" and not self.thinking:
            self.audio.play("sleep")
            self.state = "sleep"
            self.state_until = 0
            self.walk_until = 0
        elif self.state != "sleep":
            if self.fullness < 25 and random.random() < 0.5:
                self.audio.play("sad")
                self.say(random.choice(HUNGRY_LINES))
            elif self.mood < 25 and random.random() < 0.5:
                self.say(random.choice(SAD_LINES))
                self.react("sad", dur=4000, quiet=True)

        self._save_soon()
        self.root.after(60000, self._decay_tick)

    def _save_soon(self):
        if getattr(self, "_save_job", None):
            return
        self._save_job = self.root.after(3000, self._do_save)

    def _do_save(self):
        self._save_job = None
        self.cfg.setdefault("pet", {})["auto_walk"] = self.var_walk.get()
        pet_config.save(self.cfg)

    def _idle_action(self):
        """随机小动作。"""
        self.root.after(random.randint(15000, 35000), self._idle_action)
        if self.state == "sleep" or self.action or self.thinking:
            return
        r = random.random()
        if self.fullness < 30 and r < 0.4:
            self.say(random.choice(HUNGRY_LINES))
        elif r < 0.30:
            self.say(random.choice(QUOTES))
        elif r < 0.45:
            self.jump()
        elif r < 0.58:
            self.spin()
        elif r < 0.72:
            self.react("happy", dur=1800, quiet=True)
            self.root.after(1900, lambda: self.say(random.choice(QUOTES)))
        elif r < 0.85:
            self._do("stretch", 700)
        # 剩下：什么都不做，发呆也是一种状态

    # ================= 主循环 =================
    def _tick(self):
        """驱动帧循环；任何一帧出错都不允许中断整个循环，否则宠物会定格消失。"""
        try:
            self._tick_frame()
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self.root.after(50, self._tick)

    def _tick_frame(self):
        now = self._now()

        # 每 5 秒重申一次色键（保险；正常情况下不会掉）
        if now - getattr(self, "_key_check", 0) > 5000:
            self._key_check = now
            self._assert_transparent()

        # 状态超时回落
        if self.state in ("happy", "sad") and self.state_until and now >= self.state_until:
            self.state = "idle"

        # 动作结束
        if self.action and now >= self.action.get("until", 0):
            kind = self.action.get("kind")
            self.action = None
            if kind == "eat":
                self.react("happy", dur=1200, quiet=True)

        # 呼吸浮动
        self.phase += 0.08
        bob = int(math.sin(self.phase) * 4)
        y_ground = self.base_y + bob

        # 随机开始一段走动（睡觉/动作中不走）
        if (self.cfg.get("pet", {}).get("auto_walk", True) and self.state != "sleep"
                and not self.action and now >= getattr(self, "walk_next", 0)):
            self.walk_until = now + random.randint(1500, 4000)
            self.walk_dir = random.choice((-1, 1))
            self.walk_next = now + random.randint(6000, 14000)

        # 走动中
        if self.state != "sleep" and not self.action and now < self.walk_until:
            self.x += self.walk_dir * 2
            sw = self.root.winfo_screenwidth()
            w = self.root.winfo_width() or self.SIZES[self.size_name]
            if self.x <= 0 or self.x >= sw - w:
                self.walk_dir *= -1
            self.x = max(0, min(self.x, sw - w))

        # 跳跃动画的纵向偏移
        dy = 0
        if self.action:
            k = self.action.get("kind")
            if k == "jump":
                t = (now - self.action["t0"]) % 520 / 520.0
                dy = -int(math.sin(t * math.pi) * (self.root.winfo_height() * 0.35))
            elif k == "spin" and random.random() < 0.3:
                self._spawn("sparkle", 1)

        # 睡觉时冒 zzz
        if self.state == "sleep" and random.random() < 0.06:
            self._spawn("zzz", 1)

        # 选择当前帧
        if self.action:
            k = self.action["kind"]
            if k == "hang":
                key = "hang"
            elif k == "eat":
                key = "happy" if (now // 300) % 2 else "squash"
            elif k == "squash":
                key = "squash"
            elif k == "stretch":
                key = "stretch"
            elif k == "jump":
                key = "stretch"
            elif k == "spin":
                key = "rot%d" % (min(24, int((now - self.action["t0"]) / 75)) * 15 % 360)
            else:
                key = "idle"
        elif self.state == "happy":
            key = "happy"
        elif self.state == "sad":
            key = "sad"
        elif self.state == "sleep":
            key = "sleep"
        else:
            if now >= self.next_blink:
                self._blink_end = now + 160
                self.next_blink = now + random.randint(2200, 5200)
            key = "blink" if now < getattr(self, "_blink_end", 0) else "idle"

        # 粒子更新
        fx = bool(self.particles)
        if fx:
            alive = []
            for p in self.particles:
                p["life"] += 1
                p["x"] += p.get("vx", 0)
                p["y"] += p.get("vy", 0)
                if p["life"] < p["max"]:
                    alive.append(p)
            self.particles = alive
            fx = bool(alive)

        # 渲染（特效帧必须保存引用，否则 PhotoImage 会被 GC 回收、宠物图像消失）
        if fx:
            self._fx_photo = self._photo_fx(key)
            ph = self._fx_photo
        else:
            ph = self._photo(key)
        self.label.config(image=ph)
        top = y_ground - ph.height() + dy
        self.root.geometry(f"{ph.width()}x{ph.height()}+{self.x}+{top}")

        # 气泡跟随 + 超时
        if self.bubble_until and now >= self.bubble_until and not self.thinking:
            self.bubble.withdraw()
            self.bubble_until = 0
        if self.bubble.winfo_manager():
            bx = self.x + (ph.width() - self.bubble.winfo_width()) // 2
            by = top - self.bubble.winfo_height() - 6
            self.bubble.geometry(f"+{max(0, bx)}+{max(0, by)}")

    # ================= 其他 =================
    def _toggle_autostart(self):
        try:
            import winreg
            run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
                try:
                    winreg.QueryValueEx(k, "NahidaPet")
                    exists = True
                except FileNotFoundError:
                    exists = False
                if exists:
                    winreg.DeleteValue(k, "NahidaPet")
                    self.say("好的，下次开机我不出现啦。")
                else:
                    if getattr(sys, "frozen", False):
                        cmd = f'"{sys.executable}"'
                    else:
                        pyw = sys.executable.replace("python.exe", "pythonw.exe")
                        cmd = f'"{pyw}" "{os.path.join(BASE, "desktop_pet.py")}"'
                    winreg.SetValueEx(k, "NahidaPet", 0, winreg.REG_SZ, cmd)
                    self.say("好呀，以后开机我就会来看你～")
        except Exception:
            self.say("设置开机自启失败了……")

    def _quit(self):
        try:
            self.cfg.setdefault("pet", {})["auto_walk"] = self.var_walk.get()
            pet_config.save(self.cfg)
            self.audio.stop()
        except Exception:
            pass
        self.root.destroy()


def _log_exception(*args):
    """把未捕获异常写入 %USERPROFILE%\\.nahida_pet\\error.log。"""
    import traceback
    try:
        log = os.path.join(pet_config.CONFIG_DIR, "error.log")
        with open(log, "a", encoding="utf-8") as f:
            import datetime
            f.write("\n[%s]\n" % datetime.datetime.now().isoformat())
            traceback.print_exception(*args, file=f)
    except Exception:
        pass


if __name__ == "__main__":
    sys.excepthook = _log_exception
    Pet(smoke_test="--smoke-test" in sys.argv)
