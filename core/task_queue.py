"""异步任务队列 — WS消息 → 任务入队 → 后台LLM处理 → 返回结果。

任务生命周期: pending → processing → done / failed
"""

import asyncio
import enum
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class TaskStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class TaskType(enum.Enum):
    CHAT = "chat"              # AI聊天回复
    JUDGE = "judge"            # 判断提问（是/否/无关）
    CHECK_ANSWER = "check_answer"  # 检查最终答案
    GENERATE_PUZZLE = "generate_puzzle"  # 生成谜题


@dataclass
class Task:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: TaskType = TaskType.CHAT
    payload: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    room_id: Optional[str] = None
    requester_id: Optional[str] = None  # 谁提交的任务

    def mark_processing(self):
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.now().isoformat()

    def mark_done(self, result: Any):
        self.status = TaskStatus.DONE
        self.result = result
        self.finished_at = datetime.now().isoformat()

    def mark_failed(self, error: str):
        self.status = TaskStatus.FAILED
        self.error = error
        self.finished_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "room_id": self.room_id,
            "requester_id": self.requester_id,
        }


# 处理函数签名: async (task) → result
TaskHandler = Callable[[Task], Awaitable[Any]]


class TaskQueue:
    """每房间一个任务队列，控制LLM并发处理。"""

    def __init__(self, room_id: str, max_concurrent: int = 2):
        self.room_id = room_id
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._tasks: dict[str, Task] = {}          # task_id → Task
        self._handlers: dict[TaskType, TaskHandler] = {}
        self._workers: list[asyncio.Task] = []
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False

    def register_handler(self, task_type: TaskType, handler: TaskHandler):
        """注册任务类型对应的处理函数。"""
        self._handlers[task_type] = handler

    async def submit(self, task: Task) -> str:
        """提交任务，返回 task_id。"""
        self._tasks[task.id] = task
        await self._queue.put(task)
        logger.info(f"[{self.room_id}] 任务入队: {task.id} type={task.type.value}")
        return task.id

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    async def start(self):
        """启动后台worker。"""
        if self._running:
            return
        self._running = True
        for i in range(self._max_concurrent):
            worker = asyncio.create_task(self._worker(f"w-{i}"))
            self._workers.append(worker)
        logger.info(f"[{self.room_id}] 任务队列启动, workers={self._max_concurrent}")

    async def stop(self):
        """停止所有worker。"""
        self._running = False
        for w in self._workers:
            w.cancel()
        self._workers.clear()
        logger.info(f"[{self.room_id}] 任务队列停止")

    async def _worker(self, name: str):
        """后台工作协程。"""
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            async with self._semaphore:
                handler = self._handlers.get(task.type)
                if not handler:
                    task.mark_failed(f"未注册的处理器: {task.type.value}")
                    logger.error(f"[{self.room_id}] {name} 无处理器: {task.type.value}")
                    continue

                task.mark_processing()
                logger.info(f"[{self.room_id}] {name} 处理: {task.id} type={task.type.value}")
                try:
                    result = await handler(task)
                    task.mark_done(result)
                    logger.info(f"[{self.room_id}] {name} 完成: {task.id}")
                except Exception as e:
                    task.mark_failed(str(e))
                    logger.exception(f"[{self.room_id}] {name} 失败: {task.id} {e}")

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    @property
    def is_busy(self) -> bool:
        return any(t.status == TaskStatus.PROCESSING for t in self._tasks.values())
