# -*- coding: utf-8 -*-
"""桌宠音效：合成 + 播放（只做互动音效，不含任何语音朗读）。

设计原则（v2 重新调音）：
- 只用正弦基频 + 少量二次谐波（"柔和"音色），彻底去掉方波/锯齿——那是刺耳的根源；
- 频率全部压在 175~1100 Hz 的中低音区，末尾统一过一道低通，削掉毛刺；
- 包络用升余弦（attack ≥ 20ms），没有咔哒声；峰值做 tanh 软限幅，不会爆音；
- 13 种音效在音高、节奏、音色上互不重叠，闭眼也能分辨出是哪一种互动。

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

# 音效版本：改动合成算法时 +1。文件名里带版本号，旧版 WAV 会被自动清掉，
# 这样打包分发后也不会残留上一版"刺耳"的音效。
SFX_VERSION = 2

NAMES = ("click", "happy", "greet", "pet", "feed", "jump", "land",
         "sad", "sleep", "chat", "send", "magic", "poke")


def sfx_name(name, version=None):
    return "%s.v%d.wav" % (name, version or SFX_VERSION)

# ---------------------------------------------------------------- 合成工具

def _env(i, n, attack=0.03, release=0.5):
    """升余弦 attack / release 包络：平滑起落，不会有咔哒声。"""
    t = i / max(1, n - 1)
    g = 1.0
    a = max(1e-4, attack)
    r = max(1e-4, release)
    if t < a:
        g *= 0.5 - 0.5 * math.cos(math.pi * t / a)
    if t > 1 - r:
        u = min(1.0, (t - (1 - r)) / r)
        g *= 0.5 + 0.5 * math.cos(math.pi * u)
    return g


def _tone(dur, freq, vol=0.7, attack=0.03, release=0.5,
          glide_to=None, vibrato=0.0, vib_hz=5.0, harm=0.22, noise=0.0):
    """生成一段柔和单音，返回 float 列表。

    harm: 二次谐波比例（0 = 纯正弦，越大越"木"；0.3 左右像马林巴，很软）
    """
    n = int(SR * dur)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SR
        f = freq if glide_to is None else freq + (glide_to - freq) * (i / max(1, n - 1))
        if vibrato:
            f *= 1.0 + vibrato * math.sin(2 * math.pi * vib_hz * t)
        phase += 2 * math.pi * f / SR
        # 柔和音色：基频 + 少量谐波（不带方波/锯齿）
        v = math.sin(phase) + harm * math.sin(2 * phase) + 0.06 * harm * math.sin(3 * phase)
        v *= 0.85 / (1 + harm)          # 归一化，避免叠加后变大
        v *= _env(i, n, attack, release) * vol
        if noise:
            v = v * (1 - noise) + random.uniform(-1, 1) * noise * _env(i, n, 0.08, 0.7)
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


def _lowpass(buf, cutoff=3000.0):
    """一阶低通：削掉高频毛刺，声音变"圆"。"""
    k = 1 - math.exp(-2 * math.pi * cutoff / SR)
    y = 0.0
    out = []
    for x in buf:
        y += k * (x - y)
        out.append(y)
    return out


def _finalize(buf, gain=0.6, cutoff=3000.0):
    """低通 + 归一化 + tanh 软限幅（听感更柔和，不会爆音）。"""
    buf = _lowpass(buf, cutoff)
    peak = max(1e-6, max(abs(v) for v in buf))
    k = min(1.0, 0.9 / peak) * gain
    lim = math.tanh(1.15)
    return [math.tanh(max(-3.0, min(3.0, v * k)) * 1.15) / lim for v in buf]


def _write_wav(path, buf):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in buf)
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


def _arp(notes, dur=0.24, gap=0.15, vol=0.5, attack=0.025, harm=0.3, vib=0.0):
    """柔和琶音（马林巴感），音量逐个递减，尾巴自然。"""
    buf = []
    for i, nn in enumerate(notes):
        v = vol * (0.9 ** i)
        _place(buf, _tone(dur, _note(nn), v, attack=attack, release=0.62,
                          harm=harm, vibrato=vib, vib_hz=5.0), i * gap)
    return buf


# ---------------------------------------------------------------- 音效定义

def synth_sound(name):
    """生成一段音效的采样数据（float 列表）。每个状态音高/节奏都不同。"""
    cutoff = 3000.0
    if name == "click":        # 摸头·轻点：软软的"咚"（不会吓一跳）
        buf = _tone(0.20, _note("G4"), 0.60, attack=0.028, release=0.62,
                    glide_to=_note("E4"), harm=0.20)
        cutoff = 2400.0
    elif name == "happy":      # 开心：温柔的上行三音 C5-E5-G5
        buf = _arp(("C5", "E5", "G5"), dur=0.30, gap=0.16, vol=0.50, harm=0.34)
    elif name == "greet":      # 打招呼：G4->C5 两句问候
        buf = _arp(("G4", "C5"), dur=0.34, gap=0.19, vol=0.50, harm=0.28)
    elif name == "pet":        # 摸头：温柔的"嗯~"（很轻的鼻音）
        buf = _tone(0.60, _note("E4"), 0.55, attack=0.14, release=0.55,
                    glide_to=_note("G4"), vibrato=0.014, vib_hz=4.2, harm=0.12)
        cutoff = 2200.0
    elif name == "feed":       # 吃东西：三声低低的"咕"（噪声只留一点点气声）
        buf = []
        for i in range(3):
            _place(buf, _tone(0.16, 174 - i * 12, 0.60, attack=0.02, release=0.55,
                              harm=0.16, noise=0.07), i * 0.20)
        cutoff = 1100.0
    elif name == "jump":       # 跳跃：柔和上滑
        buf = _tone(0.28, 294, 0.55, attack=0.035, release=0.55,
                    glide_to=523, harm=0.14)
    elif name == "land":       # 落地：下滑 + 一点点闷响
        buf = _tone(0.24, 392, 0.50, attack=0.02, release=0.6, glide_to=208, harm=0.12)
        _place(buf, _tone(0.14, 98, 0.36, attack=0.006, release=0.7, harm=0.05), 0.0)
        cutoff = 2000.0
    elif name == "sad":        # 失落：慢下来下行 A4-F4-D4
        buf = _arp(("A4", "F4", "D4"), dur=0.42, gap=0.28, vol=0.40, attack=0.06,
                   harm=0.10, vib=0.006)
        cutoff = 2200.0
    elif name == "sleep":      # 睡觉：长长的一声"呼——"（气声极轻）
        buf = _tone(0.95, 262, 0.45, attack=0.24, release=0.55, glide_to=175,
                    vibrato=0.012, vib_hz=3.4, harm=0.08)
        _place(buf, _tone(0.80, 620, 0.05, attack=0.28, release=0.6, noise=0.20), 0.10)
        cutoff = 1600.0
    elif name == "chat":       # AI 回复来了：木琴双音 E5->G5
        buf = _arp(("E5", "G5"), dur=0.30, gap=0.13, vol=0.46, harm=0.32)
    elif name == "send":       # 发送消息：轻气泡
        buf = _tone(0.14, 523, 0.40, attack=0.012, release=0.6, glide_to=698, harm=0.16)
    elif name == "magic":      # 星星魔法：五声音阶轻风铃（不再是 1.5k~3k 的刺耳高音）
        buf = _arp(("D5", "F5", "A5", "C6"), dur=0.30, gap=0.085, vol=0.30, attack=0.03,
                   harm=0.26)
    elif name == "poke":       # 被戳：俏皮的两跳
        buf = []
        _place(buf, _tone(0.16, _note("Bb4"), 0.50, attack=0.02, release=0.5,
                          harm=0.20, vibrato=0.02, vib_hz=8.0), 0.0)
        _place(buf, _tone(0.26, _note("D5"), 0.46, attack=0.02, release=0.6,
                          harm=0.20, vibrato=0.02, vib_hz=8.0), 0.14)
    else:
        buf = _tone(0.2, _note("G4"), 0.4)

    return _finalize(buf, gain=0.62, cutoff=cutoff)


def ensure_sfx(sfx_dir):
    """确保所有音效 WAV 存在且是当前版本，缺失/过期则现场合成。返回 {name: path}。"""
    os.makedirs(sfx_dir, exist_ok=True)
    current = {sfx_name(n) for n in NAMES}
    # 清掉其它版本的音效与音量副本（升级时不会继续用旧的"刺耳"版本）
    for fn in os.listdir(sfx_dir):
        if fn.endswith(".wav") and fn not in current:
            try:
                os.remove(os.path.join(sfx_dir, fn))
            except OSError:
                pass

    out = {}
    for n in NAMES:
        p = os.path.join(sfx_dir, sfx_name(n))
        if not os.path.exists(p):
            try:
                _write_wav(p, synth_sound(n))
            except Exception:
                continue
        if os.path.exists(p):
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
        self._tmp_dir = os.path.join(sfx_dir, "_vol.v%d" % SFX_VERSION)
        os.makedirs(self._tmp_dir, exist_ok=True)

    def play(self, name):
        cfg = self._cfg()
        if not cfg.get("sound", True):
            return
        path = self.sfx.get(name)
        if not path or winsound is None:
            return
        vol = float((cfg.get("pet") or {}).get("sound_volume", 0.7))
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
