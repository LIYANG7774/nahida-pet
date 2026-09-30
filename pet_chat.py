# -*- coding: utf-8 -*-
"""聊天窗口 + AI 设置对话框（Tkinter 实现）。"""
import queue
import tkinter as tk
from tkinter import font as tkfont

import pet_config
from pet_ai import AIClient, test_connection, provider_names, provider_key_by_name
from pet_config import PROVIDERS

THEME = {
    "bg": "#f4f9ec",        # 窗口底色（草绿浅）
    "panel": "#ffffff",
    "pet_bubble": "#dcf2c8",  # 纳西妲气泡
    "pet_text": "#2e4a2b",
    "user_bubble": "#e8f4d9",
    "user_text": "#3a3a2e",
    "accent": "#7cb46b",
    "accent_dark": "#5a8f4d",
    "hint": "#8aa08a",
}


class ChatWindow(tk.Toplevel):
    """和纳西妲聊天的窗口。"""

    def __init__(self, pet):
        super().__init__(pet.root)
        self.pet = pet
        self.client = AIClient(pet.cfg_getter)
        self.history = []          # [{role, content}]，发给 AI 的上下文
        self.pending = False
        self.reply_q = queue.Queue()

        self.title("和纳西妲聊天")
        self.configure(bg=THEME["bg"])
        self.geometry("440x560+{}+{}".format(
            max(0, pet.root.winfo_screenwidth() - 480),
            max(0, pet.root.winfo_screenheight() - 640)))
        self.minsize(360, 420)
        try:
            self.attributes("-topmost", pet.root.attributes("-topmost"))
        except tk.TclError:
            pass

        self._build()
        self.bind("<Destroy>", self._on_destroy)
        self.after(80, self._poll_reply)

        # 没配 Key 时先给引导
        ai = pet.cfg_getter().get("ai") or {}
        if not (ai.get("api_key") or "").strip():
            self._sys("还没有配置 AI 呢～点下面的「设置 API Key」，填好 Key 就可以和我聊天啦。")
        else:
            self._sys("想聊什么都行，我就在桌角坐着呢。")
        self.entry.focus_set()

    # ---------------- UI ----------------
    def _build(self):
        pad = {"padx": 10, "pady": 6}

        # 布局策略：先从下往上 pack 底部的工具行 / 输入区 / 快捷词条，
        # 再 pack 标题行和消息区。这样无论窗口多高，输入框和按钮永远可见，
        # 不会被“默认申请高度很大的消息区”挤到窗口外（导致什么都点不了）。

        # 底部工具行（最先 pack，优先保证可见）
        tools = tk.Frame(self, bg=THEME["bg"])
        tools.pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        tk.Button(tools, text="设置 API Key", command=self.open_settings,
                  bg=THEME["bg"], fg=THEME["accent_dark"], relief="flat",
                  font=("Microsoft YaHei UI", 9), cursor="hand2").pack(side="left")
        tk.Button(tools, text="清空记录", command=self.clear,
                  bg=THEME["bg"], fg=THEME["hint"], relief="flat",
                  font=("Microsoft YaHei UI", 9), cursor="hand2").pack(side="right")

        # 输入区
        bottom = tk.Frame(self, bg=THEME["bg"])
        bottom.pack(side="bottom", fill="x", padx=10, pady=6)
        self.entry = tk.Entry(bottom, font=("Microsoft YaHei UI", 10),
                              bg=THEME["panel"], fg=THEME["pet_text"],
                              relief="solid", bd=1, highlightthickness=0)
        self.entry.pack(side="left", fill="both", expand=True, ipady=5)
        self.entry.bind("<Return>", lambda e: self.send())
        send_btn = tk.Button(bottom, text="发送", command=self.send,
                             bg=THEME["accent"], fg="white", activebackground=THEME["accent_dark"],
                             activeforeground="white", relief="flat",
                             font=("Microsoft YaHei UI", 10, "bold"), padx=14, cursor="hand2")
        send_btn.pack(side="left", padx=(8, 0), fill="y")

        # 快捷聊天
        chips = tk.Frame(self, bg=THEME["bg"])
        chips.pack(side="bottom", fill="x", padx=10, pady=(6, 0))
        for label in ("今天好累…", "讲个小知识", "陪我聊聊天", "夸夸我"):
            b = tk.Label(chips, text=label, bg=THEME["panel"], fg=THEME["accent_dark"],
                         font=("Microsoft YaHei UI", 9), padx=8, pady=2,
                         bd=1, relief="solid", cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, t=label: self.send(t))

        # 顶部标题
        header = tk.Frame(self, bg=THEME["bg"])
        header.pack(side="top", fill="x", **pad)
        tk.Label(header, text="🌿 纳西妲", bg=THEME["bg"], fg=THEME["pet_text"],
                 font=("Microsoft YaHei UI", 13, "bold")).pack(side="left")
        self.status = tk.Label(header, text="", bg=THEME["bg"], fg=THEME["hint"],
                               font=("Microsoft YaHei UI", 9))
        self.status.pack(side="right")

        # 消息区（填满剩余空间；height 只影响初始申请值，会随 expand 撑满）
        outer = tk.Frame(self, bg=THEME["panel"], bd=0)
        outer.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 6))
        self.text = tk.Text(outer, wrap="word", bd=0, bg=THEME["panel"],
                            fg=THEME["pet_text"], font=("Microsoft YaHei UI", 10),
                            state="disabled", height=8,
                            padx=12, pady=10, spacing1=4, spacing3=4,
                            insertbackground=THEME["pet_text"])
        scroll = tk.Scrollbar(outer, command=self.text.yview, width=10,
                              bg=THEME["bg"], troughcolor=THEME["bg"],
                              activebackground=THEME["accent"])
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_configure("user", justify="right", lmargin1=60, lmargin2=60, rmargin=8,
                                foreground=THEME["user_text"],
                                font=("Microsoft YaHei UI", 10))
        self.text.tag_configure("pet", justify="left", lmargin1=8, lmargin2=8, rmargin=60,
                                foreground=THEME["pet_text"],
                                font=("Microsoft YaHei UI", 10))
        self.text.tag_configure("sys", justify="center", foreground=THEME["hint"],
                                font=("Microsoft YaHei UI", 9))

    # ---------------- 消息渲染 ----------------
    def _append(self, text, tag):
        self.text.configure(state="normal")
        self.text.insert("end", text + "\n", tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def _sys(self, text):
        self._append("· " + text + " ·", "sys")

    def _user(self, text):
        self._append("我：" + text, "user")

    def _pet(self, text):
        self._append("纳西妲：" + text, "pet")

    # ---------------- 发送 / 接收 ----------------
    def send(self, text=None):
        """发送消息。text 为 None 时取输入框内容（发送按钮 / 回车），
        传入字符串时发送该文本（快捷词条点击）。"""
        if self.pending:
            return
        if isinstance(text, str):
            content = text.strip()
        else:
            content = self.entry.get().strip()
            self.entry.delete(0, "end")
        if not content:
            return
        self._user(content)
        self.history.append({"role": "user", "content": content})
        if len(self.history) > 24:          # 限制上下文长度
            self.history = self.history[-24:]
        self._dispatch()

    def _dispatch(self):
        ai = self.pet.cfg_getter().get("ai") or {}
        if not (ai.get("api_key") or "").strip() and "ollama" not in (ai.get("base_url") or ""):
            self._sys("先在「设置 API Key」里填好 Key，我才能开口说话哦～")
            return
        self.pending = True
        self.status.configure(text="纳西妲正在想…")
        self.pet.set_thinking(True)
        messages = [{"role": "system", "content": ai.get("system_prompt") or pet_config.NAHIDA_SYSTEM_PROMPT}]
        messages += self.history
        self.client.request_async(
            messages,
            on_done=lambda t: self.reply_q.put(("ok", t)),
            on_error=lambda e: self.reply_q.put(("err", e)),
        )

    def _poll_reply(self):
        try:
            kind, payload = self.reply_q.get_nowait()
        except queue.Empty:
            pass
        else:
            self.pending = False
            self.status.configure(text="")
            self.pet.set_thinking(False)
            if kind == "ok":
                reply = payload.strip() or "……"
                self.history.append({"role": "assistant", "content": reply})
                self._pet(reply)
                self.pet.say(reply, chat=True)
                self.pet.react("happy", quiet=True)
            else:
                self._pet(payload)
                self.pet.react("sad", quiet=True)
        if self.winfo_exists():
            self.after(80, self._poll_reply)

    def clear(self):
        self.history.clear()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._sys("聊天记录清空啦，我们重新开始～")

    def open_settings(self):
        AISettingsDialog(self.pet)

    def _on_destroy(self, _e):
        self.pet.on_chat_closed()


class AISettingsDialog(tk.Toplevel):
    """AI 服务配置：服务商预设 / Base URL / Key / 模型 / 温度 / 人设。"""

    def __init__(self, pet):
        super().__init__(pet.root)
        self.pet = pet
        self.title("AI 设置")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.transient(pet.root)
        self.grab_set()

        ai = pet.cfg_getter().get("ai") or {}
        f = tkfont.Font(family="Microsoft YaHei UI", size=10)

        def row(label):
            tk.Label(self, text=label, bg=THEME["bg"], fg=THEME["pet_text"],
                     font=f, anchor="w").pack(fill="x", padx=14, pady=(8, 2))

        row("服务商")
        self.provider_var = tk.StringVar(
            value=PROVIDERS.get(ai.get("provider", "openai"), PROVIDERS["custom"])[0])
        om = tk.OptionMenu(self, self.provider_var, *provider_names(),
                           command=self._on_provider)
        om.configure(bg=THEME["panel"], fg=THEME["pet_text"], relief="solid", bd=1,
                     font=f, anchor="w", highlightthickness=0)
        om.pack(fill="x", padx=14)

        row("接口地址 Base URL")
        self.url_var = tk.StringVar(value=ai.get("base_url", ""))
        tk.Entry(self, textvariable=self.url_var, font=f, bg=THEME["panel"],
                 relief="solid", bd=1, highlightthickness=0).pack(fill="x", padx=14, ipady=3)

        row("API Key")
        self.key_var = tk.StringVar(value=ai.get("api_key", ""))
        key_entry = tk.Entry(self, textvariable=self.key_var, font=f, show="•",
                             bg=THEME["panel"], relief="solid", bd=1, highlightthickness=0)
        key_entry.pack(fill="x", padx=14, ipady=3)

        row("模型")
        self.model_var = tk.StringVar(value=ai.get("model", ""))
        tk.Entry(self, textvariable=self.model_var, font=f, bg=THEME["panel"],
                 relief="solid", bd=1, highlightthickness=0).pack(fill="x", padx=14, ipady=3)

        row("说话风格（人设 System Prompt）")
        self.prompt_txt = tk.Text(self, height=5, font=("Microsoft YaHei UI", 9),
                                  bg=THEME["panel"], fg=THEME["pet_text"],
                                  relief="solid", bd=1, highlightthickness=0, wrap="word")
        self.prompt_txt.insert("1.0", ai.get("system_prompt") or pet_config.NAHIDA_SYSTEM_PROMPT)
        self.prompt_txt.pack(fill="x", padx=14)

        self.test_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.test_var, bg=THEME["bg"], fg=THEME["hint"],
                 font=("Microsoft YaHei UI", 9), wraplength=420, justify="left"
                 ).pack(fill="x", padx=14, pady=(6, 0))

        btns = tk.Frame(self, bg=THEME["bg"])
        btns.pack(fill="x", padx=14, pady=10)
        tk.Button(btns, text="测试连接", command=self._test, relief="flat",
                  bg=THEME["panel"], fg=THEME["accent_dark"], font=f,
                  padx=10, cursor="hand2").pack(side="left")
        tk.Button(btns, text="保存", command=self._save, relief="flat",
                  bg=THEME["accent"], fg="white", font=f,
                  padx=16, cursor="hand2").pack(side="right")
        tk.Button(btns, text="取消", command=self.destroy, relief="flat",
                  bg=THEME["panel"], fg=THEME["hint"], font=f,
                  padx=12, cursor="hand2").pack(side="right", padx=(0, 8))

        self.center()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _on_provider(self, name):
        key = provider_key_by_name(name)
        if key == "custom":
            return
        _, url, model = PROVIDERS[key]
        self.url_var.set(url)
        self.model_var.set(model)

    def _collect(self):
        return {
            "provider": provider_key_by_name(self.provider_var.get()),
            "base_url": self.url_var.get().strip(),
            "api_key": self.key_var.get().strip(),
            "model": self.model_var.get().strip(),
            "system_prompt": self.prompt_txt.get("1.0", "end").strip()
            or pet_config.NAHIDA_SYSTEM_PROMPT,
        }

    def _test(self):
        self.test_var.set("正在连接……")
        self.update_idletasks()

        def run():
            ok, msg = test_connection(self._collect())
            self.after(0, lambda: self.test_var.set(("✅ " if ok else "❌ ") + msg))
        import threading
        threading.Thread(target=run, daemon=True).start()

    def _save(self):
        cfg = self.pet.cfg_getter()
        cfg["ai"].update(self._collect())
        pet_config.save(cfg)
        self.test_var.set("已保存 ✓")
        self.after(500, self.destroy)
        self.pet.say("好啦，记住了哦。")
