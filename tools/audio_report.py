# -*- coding: utf-8 -*-
"""音效体检：对比一组 WAV 的时长、响度、过零率（越高越"刺耳"）。

用法: python tools/audio_report.py assets/sfx [对比目录]
"""
import math
import os
import struct
import sys
import wave


def stats(path):
    with wave.open(path, "rb") as w:
        n, sr = w.getnframes(), w.getframerate()
        raw = w.readframes(n)
    s = struct.unpack("<%dh" % (len(raw) // 2), raw)
    if not s:
        return None
    peak = max(abs(v) for v in s) / 32767
    rms = math.sqrt(sum(v * v for v in s) / len(s)) / 32767
    zc = sum(1 for i in range(1, len(s)) if (s[i - 1] < 0) != (s[i] < 0))
    # 过零率换算成"主导频率"的粗略估计
    zcr_hz = zc / 2 / (len(s) / sr)
    return dict(dur=len(s) / sr, peak=peak, rms=rms, zcr=zcr_hz)


def report(d):
    out = {}
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".wav"):
            st = stats(os.path.join(d, fn))
            if st:
                out[fn[:-4]] = st
    return out


def show(title, data):
    print(f"\n== {title} ==")
    print(f"{'音效':<8}{'时长s':>7}{'峰值':>8}{'RMS':>8}{'过零率Hz':>10}")
    for k in sorted(data):
        s = data[k]
        print(f"{k:<8}{s['dur']:>7.2f}{s['peak']:>8.2f}{s['rms']:>8.3f}{s['zcr']:>10.0f}")


if __name__ == "__main__":
    new_dir = sys.argv[1]
    new = report(new_dir)
    show("新版", new)
    if len(sys.argv) > 2:
        old = report(sys.argv[2])
        show("旧版", old)
        print(f"\n{'音效':<8}{'旧过零率':>10}{'新过零率':>10}{'变化':>10}{'旧峰值':>9}{'新峰值':>9}")
        for k in sorted(set(new) & set(old)):
            o, n = old[k], new[k]
            print(f"{k:<8}{o['zcr']:>10.0f}{n['zcr']:>10.0f}"
                  f"{(n['zcr'] / max(1, o['zcr']) - 1) * 100:>9.0f}%"
                  f"{o['peak']:>9.2f}{n['peak']:>9.2f}")
        avg_o = sum(v["zcr"] for v in old.values()) / max(1, len(old))
        avg_n = sum(v["zcr"] for v in new.values()) / max(1, len(new))
        print(f"\n平均过零率：旧 {avg_o:.0f} Hz → 新 {avg_n:.0f} Hz"
              f"（{(avg_n / max(1, avg_o) - 1) * 100:+.0f}%，越低越柔和）")
