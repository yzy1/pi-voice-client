from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from agent_base import AgentInterface

# 务必先加载 .env，否则 AGENT_KIND 等只有 openai 分支会读到（因为只有那边 import 了 load_dotenv）
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def create_agent(kind: Optional[str] = None) -> AgentInterface:
    """
    - openai: 使用 OpenAIAdapter
    - local : 使用 LocalAdapter
    - rag_ollama: 使用 Chroma + Ollama 的 RAG
    """
    kind = (kind or os.getenv("AGENT_KIND") or "openai").lower().strip()
    # === DEBUG: 看这里，启动时终端会打印实际读到的 AGENT_KIND 和使用的适配器 ===
    print(f"[Agent] AGENT_KIND (raw env) = {repr(os.getenv('AGENT_KIND'))} -> resolved kind = {repr(kind)}")

    if kind == "openai":
        # === 选择 LLM 位置：OpenAI ===
        print("[Agent] Using OpenAIAdapter")
        from agent_openai import OpenAIAdapter
        return OpenAIAdapter()

    if kind == "local":
        # === 选择 LLM 位置：本地 HTTP 接口 ===
        print("[Agent] Using LocalAdapter")
        from agent_local import LocalAdapter
        return LocalAdapter(
            mode=os.getenv("LOCAL_AGENT_MODE", "http"),
            endpoint=os.getenv("LOCAL_AGENT_ENDPOINT"),
            model=os.getenv("LOCAL_AGENT_MODEL"),
            api_key=os.getenv("LOCAL_AGENT_API_KEY"),
        )

    if kind == "rag_ollama":
        # === 选择 LLM 位置：RAG + Ollama（你的知识库） ===
        print("[Agent] Using RagOllamaAdapter (RAG + Ollama)")
        from rag_main_code import RagOllamaAdapter
        return RagOllamaAdapter()

    raise ValueError(f"Unknown AGENT_KIND: {kind}")
