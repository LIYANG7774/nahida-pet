# -*- coding: utf-8 -*-
"""预生成全部音效 WAV 到 assets/sfx/（构建期执行，运行时缺失也能自动补）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pet_audio import ensure_sfx  # noqa: E402

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "sfx")
    paths = ensure_sfx(out)
    for name, path in sorted(paths.items()):
        print("%-8s %6d bytes  %s" % (name, os.path.getsize(path), path))
