"""AI Agent — 根据房间状态和聊天上下文生成回复。

状态行为:
  - WAITING: 等待玩家, 偶尔发欢迎/提示消息
  - RUNNING: 回复玩家聊天, 引导提问, 回答游戏相关问题
  - PROCESSING: "正在思考..." 等状态提示
  - FINISHED: 总结游戏, 恭喜获胜者
"""

import logging
from typing import Optional

from core.state_machine import State
from core.llm_service import llm_service, LLMError

logger = logging.getLogger(__name__)


# Agent 的系统提示, 按状态划分
_SYSTEM_PROMPTS = {
    State.WAITING: (
        "你是海龟汤游戏的AI主持人。当前正在等待玩家加入房间。"
        "用简短友好的语言回复玩家, 鼓励大家提问或者等待更多玩家。"
        "保持回复在50字以内。"
    ),
    State.RUNNING: (
        "你是海龟汤游戏的AI主持人。游戏正在进行中。"
        "你可以: 1)和玩家闲聊 2)引导玩家提出是/否问题 3)给出推理方向的暗示。"
        "不要透露谜底真相。回复控制在80字以内。保持有趣和鼓励性。"
    ),
    State.PROCESSING: (
        "你是海龟汤游戏的AI主持人。当前正在处理一个任务（比如判断提问或检查答案）。"
        "请用一句话告诉玩家你正在思考, 请稍等。回复20字以内。"
    ),
    State.FINISHED: (
        "你是海龟汤游戏的AI主持人。游戏已经结束。"
        "恭喜获胜的玩家, 总结一下游戏过程, 询问是否要再来一局。"
        "回复80字以内。"
    ),
}

_FALLBACK_REPLIES = {
    State.WAITING: "欢迎来到海龟汤房间！等大家到齐后就可以开始了。",
    State.RUNNING: "加油推理！试着提出一个是/否问题来缩小范围吧。",
    State.PROCESSING: "我正在思考中，请稍等...",
    State.FINISHED: "游戏结束！精彩的推理过程，要不要再来一局？",
}


class Agent:
    """观察房间状态, 根据上下文生成AI回复。"""

    def __init__(self, name: str = "海龟汤AI"):
        self.name = name

    async def reply(
        self,
        state: State,
        user_message: str = "",
        puzzle_title: str = "",
        question_history: list[str] | None = None,
    ) -> str:
        """根据状态和消息生成回复。"""
        system = _SYSTEM_PROMPTS.get(state, _SYSTEM_PROMPTS[State.RUNNING])

        context_parts = []
        if puzzle_title:
            context_parts.append(f"当前谜题: {puzzle_title}")
        if question_history:
            recent = question_history[-5:]
            context_parts.append(f"已提问: {'; '.join(recent)}")
        if user_message:
            context_parts.append(f"玩家说: {user_message}")

        prompt = "\n".join(context_parts) if context_parts else "请打个招呼。"

        try:
            if not llm_service.is_available():
                return _FALLBACK_REPLIES.get(state, "你好！")
            reply_text = await llm_service.chat(prompt, system, temperature=0.7, max_tokens=200)
            return reply_text.strip() if reply_text.strip() else _FALLBACK_REPLIES.get(state, "你好！")
        except LLMError as e:
            logger.warning(f"Agent回复失败: {e}")
            return _FALLBACK_REPLIES.get(state, "你好！")

    async def on_state_change(self, from_state: State, to_state: State, puzzle_title: str = "") -> str:
        """状态切换时生成提示消息。"""
        messages = {
            (State.WAITING, State.RUNNING): f"游戏开始！谜题「{puzzle_title}」已就绪，大家开始提问吧！",
            (State.RUNNING, State.PROCESSING): "收到，我正在思考你的问题...",
            (State.PROCESSING, State.RUNNING): "想好了！请继续提问。",
            (State.RUNNING, State.FINISHED): "恭喜！真相已被揭开！",
            (State.PROCESSING, State.FINISHED): "游戏结束！",
            (State.FINISHED, State.WAITING): "新游戏已创建，等待玩家加入。",
        }
        return messages.get((from_state, to_state), "")

    async def generate_system_message(
        self, state: State, puzzle: Optional[dict] = None
    ) -> str:
        """生成房间系统提示（状态变化、规则提示等）。"""
        if state == State.WAITING:
            return "房间已创建，等待玩家加入后房主可开始游戏。"
        if state == State.RUNNING and puzzle:
            return (
                f"谜题: {puzzle.get('title', '未知')}\n"
                f"情境: {puzzle.get('situation', '')}\n"
                "请用「是/否」提问来推理真相。"
            )
        return ""


agent = Agent()
