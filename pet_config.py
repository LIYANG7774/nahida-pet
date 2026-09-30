# -*- coding: utf-8 -*-
"""桌宠配置读写。

配置保存在 %USERPROFILE%\\.nahida_pet\\config.json，
AI Key 属于敏感信息，只存本机，不随素材分发。
"""
import copy
import json
import os
import tempfile

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".nahida_pet")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

NAHIDA_SYSTEM_PROMPT = (
    "你是《原神》里的草神纳西妲（小吉祥草王），现在是用户电脑桌面上的一个小桌宠。"
    "你温柔、好奇、爱用比喻，喜欢把知识比作种子和树木，偶尔带一点孩子气和俏皮。"
    "说话要求：简短口语化，一到三句话；不要用 Markdown 和列表；不要自报是 AI 模型；"
    "像坐在桌角陪你聊天的小朋友那样回应。用户心情低落时要温柔安慰。"
)

PROVIDERS = {
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
    "deepseek": ("DeepSeek 深度求索", "https://api.deepseek.com/v1", "deepseek-chat"),
    "moonshot": ("Kimi 月之暗面", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    "zhipu": ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    "dashscope": ("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    "siliconflow": ("硅基流动", "https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-7B-Instruct"),
    "ollama": ("本地 Ollama", "http://localhost:11434/v1", "qwen2.5:7b"),
    "custom": ("自定义", "", ""),
}

DEFAULTS = {
    "sound": True,           # 互动音效总开关（AI 聊天不做语音朗读）
    "ai": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "temperature": 0.8,
        "system_prompt": NAHIDA_SYSTEM_PROMPT,
    },
    "pet": {
        "size": "中",
        "auto_walk": True,
        "sound_volume": 0.7,   # 0.0 ~ 0.8（上限 0.8，再大就吵了）
    },
}

_STATE = {"mood": 70, "fullness": 70}   # 心情/饱食度运行时状态，持久化在 pet 键下


def _deep_merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load():
    data = {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    cfg = _deep_merge(DEFAULTS, data)
    cfg = _migrate(cfg, data)
    # 心情/饱食度沿用上次保存的值
    saved_state = (data.get("pet") or {}).get("_state") or {}
    _STATE.update({k: saved_state.get(k, v) for k, v in _STATE.items()})
    return cfg


# 已废弃的键：TTS 语音朗读整体下线后清掉，避免配置里堆垃圾
_LEGACY_KEYS = ("tts", "tts_rate", "tts_voice", "speak_chat")


def _migrate(cfg, raw):
    """老配置兜底：清掉废弃键、把过大的音量收回到 0.8 以内（1.0 实在太吵）。"""
    for k in _LEGACY_KEYS:
        cfg.pop(k, None)
    pet = cfg.setdefault("pet", {})
    try:
        vol = float(pet.get("sound_volume", 0.7))
    except (TypeError, ValueError):
        vol = 0.7
    pet["sound_volume"] = max(0.0, min(0.8, vol))
    return cfg


def save(cfg):
    cfg = copy.deepcopy(cfg)
    cfg.setdefault("pet", {})["_state"] = dict(_STATE)
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        pass


def get_state():
    return dict(_STATE)


def update_state(mood=None, fullness=None):
    if mood is not None:
        _STATE["mood"] = max(0, min(100, int(mood)))
    if fullness is not None:
        _STATE["fullness"] = max(0, min(100, int(fullness)))
    return dict(_STATE)
