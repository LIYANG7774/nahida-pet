# -*- coding: utf-8 -*-
"""桌宠音效：合成 + 播放（只做互动音效，不含任何语音朗读）。

- 音效全部用标准库（wave + math）现场合成成小 WAV 文件，无第三方依赖；
- 播放用 winsound 异步播放，不阻塞界面；
- 音量通过按需生成"已缩放副本"实现（winsound 本身不支持音量）。
"""
import math
import os
import random
import struct
import wave

try:
    import winsound
except ImportError:      # 非 Windows 环境兜底
    winsound = None

SR = 44100

# ---------------------------------------------------------------- 合成工具

def _env(i, n, attack=0.01, release=0.4):
    """简单的 attack/release 包络（比例参数）。"""
    t = i / max(1, n - 1)
    a = attack if attack > 0 else 1e-6
    r = release if release > 0 else 1e-6
    g = 1.0
    if t < a:
        g = t / a
    elif t > 1 - r:
        g = max(0.0, (1 - t) / r)
    return g


def _tone(dur, freq, wave_kind="sine", vol=1.0, attack=0.01, release=0.35,
          glide_to=None, vibrato=0.0, vib_hz=6.0, noise=0.0):
    """生成一段单音，返回 float 列表。"""
    n = int(SR * dur)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SR
        f = freq
        if glide_to is not None:
            f = freq + (glide_to - freq) * (i / max(1, n - 1))
        if vibrato:
            f *= 1.0 + vibrato * math.sin(2 * math.pi * vib_hz * t)
        phase += 2 * math.pi * f / SR
        ph = phase % (2 * math.pi)
        if wave_kind == "sine":
            v = math.sin(ph)
        elif wave_kind == "triangle":
            v = 2 / math.pi * math.asin(math.sin(ph))
        elif wave_kind == "square":
            v = 1.0 if math.sin(ph) >= 0 else -1.0
        else:  # saw
            v = 2 * (ph / (2 * math.pi)) - 1
        v *= _env(i, n, attack, release) * vol
        if noise:
            v = v * (1 - noise) + random.uniform(-1, 1) * noise * _env(i, n, 0.05, 0.6)
        out.append(v)
    return out


def _place(buf, clip, at):
    """把 clip 混入 buf 的 at 秒处。"""
    start = int(at * SR)
    need = start + len(clip)
    if need > len(buf):
        buf.extend([0.0] * (need - len(buf)))
    for i, v in enumerate(clip):
        buf[start + i] += v


def _finalize(buf, gain=1.0):
    peak = max(1e-6, max(abs(v) for v in buf))
    k = min(1.0, 0.92 / peak) * gain
    return [max(-1.0, min(1.0, v * k)) for v in buf]


def _write_wav(path, buf):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = b"".join(struct.pack("<h", int(v * 32767)) for v in buf)
        w.writeframes(frames)


def _note(name):
    """音名转频率，支持 C5 / Eb5 / F#5 等写法。"""
    semis = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    base = 440.0
    letter = name[0]
    rest = name[1:].replace("#", "+").replace("b", "-")
    m = semis[letter]
    if rest.startswith(("+", "-")):
        m += 1 if rest[0] == "+" else -1
        rest = rest[1:]
    m += (int(rest) - 4) * 12
    return base * (2 ** (m / 12))


# ---------------------------------------------------------------- 音效定义

def synth_sound(name):
    """生成一段音效的采样数据（float 列表）。"""
    if name == "click":        # 轻点：软软的"啵"
        buf = _tone(0.10, 880, "sine", 0.8, 0.005, 0.6, glide_to=660)
    elif name == "happy":      # 开心：上行琶音
        buf = []
        for i, nn in enumerate(("C5", "E5", "G5", "C6")):
            _place(buf, _tone(0.14, _note(nn), "triangle", 0.8, 0.01, 0.5,
                              vibrato=0.012), i * 0.09)
    elif name == "greet":      # 打招呼：两声上扬
        buf = []
        _place(buf, _tone(0.16, _note("G5"), "triangle", 0.85, 0.01, 0.4, vibrato=0.015), 0.0)
        _place(buf, _tone(0.28, _note("C6"), "triangle", 0.9, 0.01, 0.6, vibrato=0.015), 0.14)
    elif name == "pet":        # 摸头：温柔的"嗯~"
        buf = _tone(0.4, 520, "sine", 0.8, 0.06, 0.5, glide_to=640, vibrato=0.02, vib_hz=5)
    elif name == "feed":       # 吃东西：三声"nom"
        buf = []
        for i in range(3):
            _place(buf, _tone(0.09, 300 - i * 30, "sine", 0.9, 0.008, 0.5), i * 0.17)
            _place(buf, _tone(0.05, 150, "sine", 0.5, 0.004, 0.7), i * 0.17 + 0.02)
    elif name == "jump":       # 跳跃：上滑
        buf = _tone(0.20, 420, "triangle", 0.8, 0.01, 0.3, glide_to=920)
    elif name == "land":       # 落地：下滑 + 闷响
        buf = _tone(0.16, 620, "sine", 0.7, 0.005, 0.5, glide_to=240)
        _place(buf, _tone(0.09, 120, "sine", 0.8, 0.004, 0.6), 0.0)
    elif name == "sad":        # 失落：下行小三度
        buf = []
        _place(buf, _tone(0.24, _note("G5"), "sine", 0.7, 0.02, 0.4), 0.0)
        _place(buf, _tone(0.24, _note("Eb5"), "sine", 0.7, 0.02, 0.4), 0.20)
        _place(buf, _tone(0.40, _note("C5"), "sine", 0.7, 0.02, 0.7), 0.40)
    elif name == "sleep":      # 睡觉：缓慢下滑 + 气息
        buf = _tone(0.7, 340, "sine", 0.6, 0.10, 0.55, glide_to=190, vibrato=0.01, vib_hz=4)
        _place(buf, _tone(0.5, 800, "sine", 0.12, 0.15, 0.6, noise=0.5), 0.1)
    elif name == "chat":       # AI 回复到来：清脆双音
        buf = []
        _place(buf, _tone(0.12, _note("E6"), "sine", 0.75, 0.005, 0.4), 0.0)
        _place(buf, _tone(0.26, _note("A6"), "sine", 0.8, 0.005, 0.7), 0.10)
    elif name == "send":       # 发送消息：短促气泡
        buf = _tone(0.09, 700, "sine", 0.6, 0.004, 0.5, glide_to=1050)
    elif name == "magic":      # 星星魔法：高频闪烁
        buf = []
        for i, f in enumerate((1568, 2093, 2637, 3136)):
            _place(buf, _tone(0.16, f, "sine", 0.5, 0.004, 0.75), i * 0.055)
    elif name == "poke":       # 被戳：俏皮"哇"
        buf = _tone(0.22, 1000, "triangle", 0.8, 0.006, 0.5, glide_to=700, vibrato=0.03, vib_hz=9)
    else:
        buf = _tone(0.1, 880)

    return _finalize(buf)


def ensure_sfx(sfx_dir):
    """确保所有音效 WAV 存在，缺失则现场合成。返回 {name: path}。"""
    names = ("click", "happy", "greet", "pet", "feed", "jump", "land",
             "sad", "sleep", "chat", "send", "magic", "poke")
    os.makedirs(sfx_dir, exist_ok=True)
    out = {}
    for n in names:
        p = os.path.join(sfx_dir, n + ".wav")
        if not os.path.exists(p):
            try:
                _write_wav(p, synth_sound(n))
            except Exception:
                continue
        out[n] = p
    return out


def scale_wav(src, dst, gain):
    """按 gain 缩放一个 16bit 单声道 WAV（实现音量）。"""
    if gain >= 0.999:
        return src
    try:
        with wave.open(src, "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())
        samples = struct.unpack("<%dh" % (len(frames) // 2), frames)
        scaled = [max(-32768, min(32767, int(s * gain))) for s in samples]
        with wave.open(dst, "wb") as w:
            w.setparams(params)
            w.writeframes(b"".join(struct.pack("<h", s) for s in scaled))
        return dst
    except Exception:
        return src


# ---------------------------------------------------------------- 播放器

class Audio:
    """互动音效管理器（合成 WAV + 异步播放）。"""

    def __init__(self, cfg_getter, sfx_dir):
        self._cfg = cfg_getter                    # 返回整个 config dict
        self.sfx = ensure_sfx(sfx_dir)
        self._vol_cache = {}                      # (name, vol) -> path
        self._tmp_dir = os.path.join(sfx_dir, "_vol")
        os.makedirs(self._tmp_dir, exist_ok=True)

    def play(self, name):
        cfg = self._cfg()
        if not cfg.get("sound", True):
            return
        path = self.sfx.get(name)
        if not path or winsound is None:
            return
        vol = float((cfg.get("pet") or {}).get("sound_volume", 0.8))
        key = (name, round(vol, 2))
        if key not in self._vol_cache:
            dst = os.path.join(self._tmp_dir, "%s_%d.wav" % (name, round(vol * 100)))
            self._vol_cache[key] = scale_wav(path, dst, vol)
        try:
            winsound.PlaySound(self._vol_cache[key],
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass

    def stop(self):
        """停止当前正在播放的音效（退出时调用）。"""
        if winsound is None:
            return
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
