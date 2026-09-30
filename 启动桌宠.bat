@echo off
rem 优先使用 PATH 里的 pythonw，找不到时回退到本机虚拟环境（换台机器改这行路径即可）
where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw "%~dp0desktop_pet.py"
    exit /b
)
start "" "C:\Users\19835\.workbuddy\binaries\python\envs\pet\Scripts\pythonw.exe" "%~dp0desktop_pet.py"
