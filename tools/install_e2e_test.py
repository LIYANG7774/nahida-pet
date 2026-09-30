# -*- coding: utf-8 -*-
"""安装包端到端自检：静默安装 -> 校验文件/快捷方式/注册表 -> 静默卸载 -> 校验清理。

用法：
    python tools/install_e2e_test.py installer/dist/NahidaPet-Setup-<版本>.exe [安装目录]

说明：
  · 会在当前用户下真实安装一次再卸载（可逆）。
  · NSIS 卸载器默认会把自己复制到 %TEMP%\\~nsu*.tmp 再重新启动，父进程立刻返回；
    沙箱会在调用结束时回收这个子进程，所以这里用 `_?=<目录>` 让卸载器原地运行，
    进程直接挂在本次调用上等待结束。
  · 测试前会备份用户已有的 HKCU Run\\NahidaPet 值，结束后还原。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import winreg

UNINST_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\NahidaPet"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
USER_SHELL_FOLDERS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
APP = "NahidaPet"
STARTMENU_NAME = "纳西妲桌宠"


# ---------------- 注册表小工具 ----------------
def expected_version():
    """从安装脚本里读版本号（别在测试里写死，否则一升级版本就误报失败）。"""
    nsi = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "installer", "NahidaPet.nsi")
    try:
        with open(nsi, encoding="utf-8") as f:
            for line in f:
                if "PRODUCT_VERSION" in line and '"' in line:
                    return line.split('"')[1]
    except OSError:
        pass
    return None


def reg_get(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except FileNotFoundError:
        return None


def reg_set(root, path, name, value):
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def reg_del(root, path, name):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
            return True
    except FileNotFoundError:
        return False


def uninst_exists() -> bool:
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINST_KEY).Close()
        return True
    except FileNotFoundError:
        return False


def desktop_dir() -> str:
    d = reg_get(winreg.HKEY_CURRENT_USER, USER_SHELL_FOLDERS, "Desktop") or ""
    d = d.replace("%USERPROFILE%", os.path.expanduser("~")).replace(
        "%USERPROFILE%".lower(), os.path.expanduser("~"))
    return d or os.path.join(os.path.expanduser("~"), "Desktop")


def run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def wait_until(pred, timeout=45.0, interval=0.5):
    """轮询等待，返回是否在超时前满足。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(interval)
    return pred()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    setup = os.path.abspath(sys.argv[1])
    target = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else \
        os.path.join(os.environ["LOCALAPPDATA"], "Programs", "NahidaPet")

    desktop = desktop_dir()
    startmenu = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows",
                             "Start Menu", "Programs", STARTMENU_NAME)
    results: list[bool] = []

    def check(label, cond, extra=""):
        results.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  {extra}" if extra else ""))

    print(f"安装包：{setup}  ({os.path.getsize(setup):,} bytes)")
    print(f"安装目录：{target}")
    print(f"桌面目录：{desktop}\n")

    # 备份用户原有自启项，测试后还原
    autorun_backup = reg_get(winreg.HKEY_CURRENT_USER, RUN_KEY, APP)

    print("== 1. 静默安装 ==")
    r = run([setup, "/S", "/D=" + target])
    check("安装程序返回 0", r.returncode == 0, f"rc={r.returncode}")

    exe = os.path.join(target, APP + ".exe")
    check("主程序已安装", os.path.exists(exe))
    check("使用说明已安装", os.path.exists(os.path.join(target, "使用说明.txt")))
    check("许可文件已安装", os.path.exists(os.path.join(target, "LICENSE.txt")))
    check("卸载程序已生成", os.path.exists(os.path.join(target, "Uninstall.exe")))

    print("\n== 2. 注册表安装项 ==")
    check("Uninstall 键存在", uninst_exists())
    check("DisplayName", reg_get(winreg.HKEY_CURRENT_USER, UNINST_KEY, "DisplayName")
          == f"{STARTMENU_NAME} (Nahida Pet)",
          str(reg_get(winreg.HKEY_CURRENT_USER, UNINST_KEY, "DisplayName")))
    ver = reg_get(winreg.HKEY_CURRENT_USER, UNINST_KEY, "DisplayVersion")
    check("DisplayVersion", ver == expected_version(), f"{ver}（期望 {expected_version()}）")
    loc = reg_get(winreg.HKEY_CURRENT_USER, UNINST_KEY, "InstallLocation")
    check("InstallLocation 指向目标目录",
          os.path.normcase(loc or "") == os.path.normcase(target), str(loc))
    size = reg_get(winreg.HKEY_CURRENT_USER, UNINST_KEY, "EstimatedSize")
    check("EstimatedSize 已写入", isinstance(size, int) and size > 1000, f"{size} KB")
    check("UninstallString 正确",
          (reg_get(winreg.HKEY_CURRENT_USER, UNINST_KEY, "UninstallString") or "").strip('"')
          == os.path.join(loc or "", "Uninstall.exe"))
    check("未勾选的「开机自启」在静默安装时保持不动",
          reg_get(winreg.HKEY_CURRENT_USER, RUN_KEY, APP) == autorun_backup,
          f"now={reg_get(winreg.HKEY_CURRENT_USER, RUN_KEY, APP)!r}")

    print("\n== 3. 快捷方式 ==")
    check("开始菜单文件夹", os.path.isdir(startmenu))
    check("开始菜单 主程序快捷方式", os.path.exists(os.path.join(startmenu, f"{STARTMENU_NAME}.lnk")))
    check("开始菜单 卸载快捷方式", os.path.exists(os.path.join(startmenu, f"卸载 {STARTMENU_NAME}.lnk")))
    check("桌面快捷方式", os.path.exists(os.path.join(desktop, f"{STARTMENU_NAME}.lnk")))

    print("\n== 4. 静默卸载 ==")
    unins = os.path.join(target, "Uninstall.exe")
    # _?=<目录> 让卸载器原地执行（不复制到 %TEMP%），进程可直接等待结束
    r = run([unins, "/S", "_?=" + target], timeout=180)
    check("卸载程序返回 0", r.returncode == 0, f"rc={r.returncode}")
    done = wait_until(lambda: not os.path.isdir(target) and not uninst_exists(), timeout=40)
    if not done:
        print("      卸载未在 40s 内完成（可能被沙箱回收）")
    check("程序目录已删除", not os.path.isdir(target))
    check("卸载注册项已清除", not uninst_exists())
    check("开始菜单快捷方式已删除", not os.path.isdir(startmenu))
    check("桌面快捷方式已删除", not os.path.exists(os.path.join(desktop, f"{STARTMENU_NAME}.lnk")))
    check("开机自启项已清除", reg_get(winreg.HKEY_CURRENT_USER, RUN_KEY, APP) is None)

    cfg = os.path.join(os.path.expanduser("~"), ".nahida_pet", "config.json")
    print(f"\n  个人配置：{'保留（符合预期）' if os.path.exists(cfg) else '不存在'}  {cfg}")

    # 还原测试前的自启项
    if autorun_backup is not None:
        reg_set(winreg.HKEY_CURRENT_USER, RUN_KEY, APP, autorun_backup)
        print(f"  已还原测试前的开机自启项：{autorun_backup}")

    passed = sum(results)
    print(f"\n结果：{passed}/{len(results)} 项通过 " + ("✔" if passed == len(results) else "✘"))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
