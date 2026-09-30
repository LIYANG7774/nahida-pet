# -*- coding: utf-8 -*-
"""收尾：结束源码版桌宠 -> 部署 exe 到桌面 -> 启动 exe。"""
import os
import shutil
import subprocess
import sys

SRC = r"C:\Users\19835\WorkBuddy\2026-09-30-16-08-35\nahida_pet\dist\NahidaPet.exe"
DESKTOP = r"D:\Users\19835\Desktop"
TARGET = os.path.join(DESKTOP, "纳西妲桌宠.exe")

# 1) 结束仍在运行的源码版桌宠（仅匹配 desktop_pet.py）
try:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or Name='python.exe'\" | "
         "Where-Object { $_.CommandLine -like '*desktop_pet.py*' } | "
         "Select-Object -ExpandProperty ProcessId"],
        capture_output=True, text=True, timeout=30,
    ).stdout.split()
    killed = []
    for pid in out:
        subprocess.run(["taskkill", "/PID", pid.strip(), "/F"], capture_output=True)
        killed.append(pid.strip())
    print("killed source-version pids:", killed or "none")
except Exception as e:
    print("kill step skipped:", e)

# 2) 部署到桌面
os.makedirs(DESKTOP, exist_ok=True)
if os.path.exists(TARGET):
    os.remove(TARGET)
shutil.copy2(SRC, TARGET)
print("deployed:", TARGET, os.path.getsize(TARGET), "bytes")

# 3) 启动
os.startfile(TARGET)
print("launched")
