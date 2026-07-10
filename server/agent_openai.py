# server/agent_openai.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from openai import OpenAI

from agent_base import AgentInterface

# Load .env
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Read environment variables for DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or ""
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"

if not DEEPSEEK_API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY is not set (check server/.env or Railway variables).")

# Initialize DeepSeek client (OpenAI-compatible)
client_kwargs: Dict[str, str] = {
    "api_key": DEEPSEEK_API_KEY,
    "base_url": DEEPSEEK_BASE_URL
}

_client = OpenAI(**client_kwargs)

def chat_once(user_text: str, system_prompt: Optional[str] = None) -> str:
    """Send a single chat message and return the response text."""
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})

    resp = _client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=messages,
        temperature=0.6,
    )
    choice = resp.choices[0]
    reply = (choice.message.content or "").strip()
    return reply

class OpenAIAdapter(AgentInterface):
    """Adapter for DeepSeek API (OpenAI-compatible)."""

    def __init__(self):
        self.model = os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"

    def reply(self, text: str, system_prompt: Optional[str] = None) -> str:
        return chat_once(text, system_prompt=system_prompt)
