# server/agent_openai.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from openai import OpenAI

from agent_base import AgentInterface

# 加载 .env
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# 读取环境变量
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or ""
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None      # None = 官方
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set (check server/.env).")

client_kwargs: Dict[str, str] = {"api_key": OPENAI_API_KEY}
if OPENAI_BASE_URL:
    client_kwargs["base_url"] = OPENAI_BASE_URL

_client = OpenAI(**client_kwargs)

def chat_once(user_text: str, system_prompt: Optional[str] = None) -> str:
    # 发一轮对话，返回回复文本。
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})

    resp = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.6,
    )
    # 兼容常见字段
    choice = resp.choices[0]
    reply = (choice.message.content or "").strip()
    return reply

class OpenAIAdapter(AgentInterface):
    # 现有chat_once()包装成统一接口

    def __init__(self):
        # 需要的话这里读取 OPENAI_MODEL / OPENAI_API_KEY 等
        self.model = os.getenv("OPENAI_MODEL")

    def reply(self, text: str, system_prompt: Optional[str] = None) -> str:
        # 直接复用chat_once
        # from agent_openai import chat_once  # 避免循环导入
        return chat_once(text, system_prompt=system_prompt)
