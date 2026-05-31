"""LLM 服务兼容层：保留旧接口，内部调用 LangChain。"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from core.llm_factory import create_llm
from core.config import LLM_MODE, LLM_API_KEY

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用异常（保留兼容）。"""
    pass


class LLMService:
    """向后兼容的 LLM 服务。"""

    def __init__(self):
        self._llm = None

    @property
    def mode(self) -> str:
        return LLM_MODE

    def is_available(self) -> bool:
        if LLM_MODE == "local":
            return True
        return bool(LLM_API_KEY)

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """兼容旧接口：prompt → LangChain messages → invoke。"""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # 主 LLM
        try:
            llm = create_llm(temperature=temperature, max_tokens=max_tokens)
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.warning(f"主 LLM 调用失败 ({type(e).__name__}): {e}")

        # 降级: 切换模式
        fallback_mode = "local" if LLM_MODE == "external" else "external"
        try:
            llm = create_llm(mode=fallback_mode, temperature=temperature, max_tokens=max_tokens)
            response = await llm.ainvoke(messages)
            logger.info(f"降级到 {fallback_mode} 成功")
            return response.content
        except Exception as e:
            logger.warning(f"备用 LLM 也失败 ({type(e).__name__}): {e}")

        # 最终降级: 题库
        from core.puzzle_bank import puzzle_bank
        puzzle = puzzle_bank.get_random()
        if puzzle:
            logger.info("从题库返回随机题目")
            import json
            return json.dumps(puzzle, ensure_ascii=False)

        raise LLMError("所有 LLM 通道不可用且题库为空")


# 全局单例（保持兼容）
llm_service = LLMService()
