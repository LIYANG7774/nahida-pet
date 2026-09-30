# 纳西妲桌宠 Nahida Pet

一个常驻 Windows 桌面的纳西妲小桌宠。全透明窗口、置顶显示，会呼吸浮动、眨眼、自己在桌面散步，
也能被拎起来、被摸头、被喂点心，还可以调用你自己的 AI 接口跟她聊天。

> 非商业同人作品，仅供个人学习交流使用，与米哈游 / HoYoverse 无关，角色形象版权归原厂所有。

## 功能

- **桌面常驻**：背景透明、置顶、无边框，可拖动；呼吸浮动 + 定时眨眼 + 落地弹跳（squash/stretch）
- **互动**：摸头（连戳 5 次有彩蛋）、喂点心、逗她玩、讲故事、猜谜语、拖起来会挣扎、滚轮调大小
- **状态系统**：心情 / 饱食度随时间衰减，长时间不理她会睡着，持续不理会闹脾气
- **互动音效**：13 个音效全部用标准库实时合成（无外部音频文件依赖），每个状态音高/节奏都不同，
  音色以中低音区的正弦+少量谐波为主（刻意避开方波与高频，听感柔和），winsound 异步播放，音量可调
- **AI 聊天**：右键「和我聊天」弹出聊天窗，支持 OpenAI / DeepSeek / Kimi / 智谱 / 通义千问 / 硅基流动 / 本地 Ollama
  等任意 OpenAI 兼容接口，自带服务商预设与「测试连接」
- **右键菜单**：AI 设置、开机自启、音效开关、退出等

## 快速开始（源码运行）

```bash
pip install pillow
python desktop_pet.py              # 正常运行
python desktop_pet.py --smoke-test # 冒烟测试，2.5 秒后自动退出
```

Windows 下也可以直接双击 `启动桌宠.bat`（脚本里写死了本机虚拟环境路径，按需修改）。

## 打包

```bash
# 主程序（onefile exe）
pyinstaller --noconfirm NahidaPet.spec

# 安装包（需要 NSIS，见 installer/build_installer.py 里的查找逻辑）
python installer/build_installer.py
```

产物：

| 路径 | 说明 |
|---|---|
| `installer/build_dist/NahidaPet.exe` | 免安装单文件主程序 |
| `installer/dist/NahidaPet-Setup-1.0.1.exe` | NSIS 安装包（免管理员权限、开始菜单/桌面快捷方式、控制面板可卸载） |

## 目录结构

```
desktop_pet.py       主程序：窗口、动画、互动、右键菜单
pet_ai.py            OpenAI 兼容聊天客户端（纯 urllib，无第三方依赖）
pet_audio.py         音效合成 + 播放（纯标准库）
pet_chat.py          聊天窗口 + AI 设置对话框
pet_config.py        配置读写（%USERPROFILE%\.nahida_pet\config.json）
process_assets.py    素材预处理：抠图、派生帧（眨眼/开心/hang/squash）
assets/              运行时素材（角色帧、图标、音效）
installer/           NSIS 安装包脚本与构建脚本
tools/               开发期诊断脚本（端到端安装测试、版本信息、截图等）
```

## 配置与隐私

配置保存在 `%USERPROFILE%\.nahida_pet\config.json`，**API Key 只留在本机**，不会上传到任何地方；
只有你主动使用聊天功能时，程序才会把对话内容直接发给你自己配置的 AI 服务商。

## 更新日志

### v1.0.1

- **修复透明背景偶发失效**：长时间不理会、她进入「睡着 / 难过」状态后，桌面上会冒出一整块洋红方块
  （拖动一下才恢复）。根因是这两种状态给画面做去饱和时把背景 alpha 从 0 变成了半透明，
  与关键色叠加后不再是「纯洋红」，色键失效。现在改为保留原图 alpha，并按 alpha 掩码贴到关键色底上，
  同时把角色自身的颜色向羽化区外扩，连角色周围原本的粉紫描边也一并去掉了。
- **重做全部互动音效**：原来的音色偏刺耳（方波/锯齿 + 1.5k~3k 高频）。新版全部改为中低音区的
  正弦 + 少量谐波，统一过低通、用升余弦包络、tanh 软限幅；13 个音效在音高/节奏/音色上互不重叠，
  平均过零率从 1029 Hz 降到 480 Hz。音效文件名带版本号，升级后旧文件会被自动清理。
- 音量上限收紧到 0.8（原来 1.0 太吵），并自动清理配置里已废弃的 TTS 相关键。

## 端到端自检

```bash
python tools/install_e2e_test.py installer/dist/NahidaPet-Setup-1.0.1.exe
```

会真实安装一次再卸载，校验文件、注册表卸载项、快捷方式与清理结果（22 项检查），
测试前后的个人配置与开机自启项都会被保留/还原。
