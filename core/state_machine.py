"""显式状态机 — 管理房间/游戏的生命周期。

States: WAITING → RUNNING → PROCESSING → FINISHED
"""

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class State(enum.Enum):
    WAITING = "waiting"        # 等待玩家加入
    RUNNING = "running"        # 游戏进行中，可聊天提问
    PROCESSING = "processing"  # LLM正在处理任务
    FINISHED = "finished"      # 游戏结束


# 合法的状态转换: (from_state, event) → to_state
_TRANSITIONS: dict[tuple[State, str], State] = {
    (State.WAITING, "start"):       State.RUNNING,
    (State.RUNNING, "task_submit"): State.PROCESSING,
    (State.PROCESSING, "task_done"): State.RUNNING,
    (State.RUNNING, "finish"):      State.FINISHED,
    (State.PROCESSING, "finish"):   State.FINISHED,
    (State.FINISHED, "reset"):      State.WAITING,
    (State.WAITING, "cancel"):      State.FINISHED,
}


@dataclass
class TransitionRecord:
    from_state: State
    to_state: State
    event: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class StateMachine:
    """有限状态机，每个房间/游戏实例持有一个。"""

    def __init__(self, initial: State = State.WAITING):
        self._state = initial
        self._history: list[TransitionRecord] = []
        self._listeners: dict[str, list[Callable]] = {}

    @property
    def state(self) -> State:
        return self._state

    @property
    def value(self) -> str:
        return self._state.value

    def can(self, event: str) -> bool:
        """检查当前状态是否允许该事件触发转换。"""
        return (self._state, event) in _TRANSITIONS

    def transition(self, event: str) -> State:
        """执行状态转换。失败抛 ValueError。"""
        key = (self._state, event)
        if key not in _TRANSITIONS:
            raise ValueError(
                f"非法转换: {self._state.value} --[{event}]--> ?  "
                f"合法事件: {self._valid_events()}"
            )
        old = self._state
        new = _TRANSITIONS[key]
        self._state = new

        record = TransitionRecord(from_state=old, to_state=new, event=event)
        self._history.append(record)
        logger.info(f"状态转换: {old.value} --[{event}]--> {new.value}")

        self._fire(event, old, new)
        return new

    def on(self, event: str, callback: Callable):
        """注册状态转换监听器。callback(from_state, to_state)。"""
        self._listeners.setdefault(event, []).append(callback)

    def _fire(self, event: str, old: State, new: State):
        for cb in self._listeners.get(event, []):
            try:
                cb(old, new)
            except Exception:
                logger.exception(f"状态监听器异常: event={event}")

    def _valid_events(self) -> list[str]:
        return [e for (s, e) in _TRANSITIONS if s == self._state]

    @property
    def history(self) -> list[dict]:
        return [
            {"from": r.from_state.value, "to": r.to_state.value,
             "event": r.event, "timestamp": r.timestamp}
            for r in self._history
        ]
