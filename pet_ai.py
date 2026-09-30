# -*- coding: utf-8 -*-
"""AI 聊天客户端：OpenAI 兼容的 /chat/completions 接口，纯标准库实现。

支持 OpenAI / DeepSeek / Kimi / 智谱 / 通义 / 硅基流动 / 本地 Ollama / 自定义。
"""
import json
import urllib.error
import urllib.request

from pet_config import PROVIDERS

TIMEOUT = 45


def endpoint_for(base_url):
    """把 base_url 归一化成完整的 chat/completions 地址。"""
    base = (base_url or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1") or base.endswith("/v4") or base.endswith("/compatible-mode"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def friendly_error(e):
    """把网络/接口错误翻译成桌宠会说的话。"""
    if isinstance(e, urllib.error.HTTPError):
        code = e.code
        try:
            body = e.read().decode("utf-8", "ignore")[:500]
        except Exception:
            body = ""
        if code in (401, 403):
            return "API Key 好像不对呢，或者没有权限……检查一下设置好吗？"
        if code == 404:
            return "找不到这个接口地址，是不是模型名或 Base URL 填错啦？"
        if code == 429:
            return "请求太快啦，服务器让我等等再说话……"
        if code >= 500:
            return "那边服务器开小差了（%d），等会儿再试试吧。" % code
        return "接口返回了 %d：%s" % (code, body or "未知错误")
    if isinstance(e, urllib.error.URLError):
        reason = str(getattr(e, "reason", e))
        if "getaddrinfo" in reason or "Name or service" in reason:
            return "连不上网络呢……检查一下网络好吗？"
        if "refused" in reason:
            return "连接被拒绝了，服务地址是不是没开呀？"
        return "网络出了点问题：%s" % reason
    if isinstance(e, TimeoutError):
        return "等了好久都没有回应……要不稍后再试一次？"
    return "出错了：%s" % e


class AIClient:
    """线程安全的简单客户端；每次请求开一个临时线程回调。"""

    def __init__(self, config_getter):
        self._cfg = config_getter

    # ---- 同步请求 ----
    def request(self, messages):
        """阻塞式请求，成功返回回复文本，失败抛异常。"""
        ai = self._cfg().get("ai") or {}
        api_key = (ai.get("api_key") or "").strip()
        base_url = (ai.get("base_url") or "").strip()
        model = (ai.get("model") or "").strip()
        if not base_url:
            raise ValueError("还没有配置接口地址哦")
        if not api_key and "ollama" not in base_url:
            raise ValueError("还没有填写 API Key 呢")

        payload = {
            "model": model,
            "messages": messages,
            "temperature": float(ai.get("temperature", 0.8)),
        }
        req = urllib.request.Request(
            endpoint_for(base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer %s" % api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        return (data["choices"][0]["message"]["content"] or "").strip()

    # ---- 异步请求 ----
    def request_async(self, messages, on_done, on_error):
        def run():
            try:
                text = self.request(messages)
            except Exception as e:  # noqa: BLE001
                on_error(friendly_error(e))
            else:
                on_done(text)
        threading_run(run)


def threading_run(fn):
    import threading
    threading.Thread(target=fn, daemon=True).start()


def test_connection(cfg_ai, timeout=20):
    """同步测试连通性，返回 (ok, 描述文本)。"""
    import copy
    client = AIClient(lambda: {"ai": copy.deepcopy(cfg_ai)})
    messages = [
        {"role": "system", "content": "你只回答两个字：你好"},
        {"role": "user", "content": "打个招呼"},
    ]
    try:
        text = client.request(messages)
        return True, "连接成功！模型回复：%s" % (text[:40] or "（空）")
    except Exception as e:  # noqa: BLE001
        return False, friendly_error(e)


def provider_names():
    return [PROVIDERS[k][0] for k in PROVIDERS]


def provider_key_by_name(name):
    for k, v in PROVIDERS.items():
        if v[0] == name:
            return k
    return "custom"
