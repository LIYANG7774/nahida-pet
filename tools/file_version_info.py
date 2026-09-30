# -*- coding: utf-8 -*-
"""用 ctypes 读取 exe/dll 的版本资源（不依赖 pywin32）。

用法：python tools/file_version_info.py <文件路径> [...]
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

ver = ctypes.WinDLL("version")


def _translate(block: bytes, key: str, lang: int) -> str | None:
    q = ctypes.c_uint()
    ver.VerQueryValueW(block, ctypes.c_wchar_p(f"\\StringFileInfo\\{lang:04x}04b0\\{key}"),
                      ctypes.byref(ctypes.c_void_p()), ctypes.byref(q))
    # 需要重新取指针，改用显式缓冲区
    buf = ctypes.c_void_p()
    if not ver.VerQueryValueW(block, ctypes.c_wchar_p(f"\\StringFileInfo\\{lang:04x}04b0\\{key}"),
                              ctypes.byref(buf), ctypes.byref(q)) or not q.value:
        return None
    return ctypes.wstring_at(buf.value, q.value).rstrip("\x00")


def read(path: str):
    size = ver.GetFileVersionInfoSizeW(ctypes.c_wchar_p(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(ctypes.c_wchar_p(path), 0, size, buf):
        return None

    fix = ctypes.c_void_p()
    n = ctypes.c_uint()
    ver.VerQueryValueW(buf, ctypes.c_wchar_p("\\"), ctypes.byref(fix), ctypes.byref(n))
    ffi = ctypes.cast(fix, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
    filever = f"{ffi[2] >> 16}.{ffi[2] & 0xFFFF}.{ffi[3] >> 16}.{ffi[3] & 0xFFFF}"
    prodver = f"{ffi[4] >> 16}.{ffi[4] & 0xFFFF}.{ffi[5] >> 16}.{ffi[5] & 0xFFFF}"

    langs = ctypes.c_void_p()
    ver.VerQueryValueW(buf, ctypes.c_wchar_p("\\VarFileInfo\\Translation"),
                       ctypes.byref(langs), ctypes.byref(n))
    pairs = ctypes.cast(langs, ctypes.POINTER(ctypes.c_uint16 * (n.value // 2))).contents
    lang = pairs[0] if n.value >= 2 else 0x0804

    keys = ["ProductName", "FileDescription", "CompanyName",
            "OriginalFilename", "LegalCopyright", "InternalName"]
    out = {"FileVersion": filever, "ProductVersion": prodver}
    for k in keys:
        v = _translate(buf, k, lang)
        if v:
            out[k] = v
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        info = read(p)
        print(f"== {p}")
        if not info:
            print("   (无版本信息)")
            continue
        for k, v in info.items():
            print(f"   {k:<17}: {v}")
