# server/agent_base.py
from __future__ import annotations
import abc
from typing import AsyncIterator, Optional

class AgentInterface(abc.ABC):
    # Agent接口：问答 + 流式可选

    @abc.abstractmethod
    def reply(self, text: str, system_prompt: Optional[str] = None) -> str:
        # 输入用户文本，返回完整回答文本
        raise NotImplementedError

    async def reply_async(self, text: str, system_prompt: Optional[str] = None) -> str:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.reply, text, system_prompt)

    async def stream_reply(self, text: str, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        # 可选：流式输出 token/chunk。默认退化为一次性输出。
        yield await self.reply_async(text, system_prompt)
