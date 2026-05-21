"""Runtime 核心 — 收发任务, 调度LLM, 控制并发, 管理房间。

每个 Room 包含:
  - state_machine: 显式状态机
  - task_queue: 异步任务队列
  - ws_connections: WebSocket连接管理
  - game_data: 游戏数据 (谜题、提问历史等)
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Optional, Any

from fastapi import WebSocket

from core.state_machine import State, StateMachine
from core.task_queue import TaskQueue, Task, TaskType, TaskStatus
from core.agent import agent
from core.llm_service import llm_service, LLMError
from core.json_parser import parse_llm_json
from core.redis_service import redis_service
from core.prompts import build_question_judge_prompt, build_answer_check_prompt

logger = logging.getLogger(__name__)

# ---- 游戏类型注册表（预留扩展） ----
GAME_TYPES: dict[str, dict] = {
    "turtle_soup": {"name": "海龟汤", "min_players": 1, "max_players": 4},
    "undercover": {"name": "谁是卧底", "min_players": 3, "max_players": 10},
}


class Room:
    """一个房间 = 状态机 + 任务队列 + WebSocket连接 + 游戏数据。"""

    def __init__(self, room_id: str, host_uid: str, settings: dict):
        self.room_id = room_id
        self.sm = StateMachine()
        self.queue = TaskQueue(room_id)
        self.host_uid = host_uid

        # 玩家管理: {uid: {"username", "nickname", "joined_at"}}
        self.players: dict[str, dict] = {}
        self.ws_connections: dict[str, dict[str, WebSocket]] = {}  # uid → {conn_id: ws}

        # 游戏数据
        self.game_type: str = settings.get("game_type", "turtle_soup")
        self.settings = {k: v for k, v in settings.items() if k != "game_type"}
        self.puzzle: Optional[dict] = None
        self.question_history: list[dict] = []
        self.question_count = 0
        self.hints_used = 0
        self.winner: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None

        # 注册任务处理器
        self.queue.register_handler(TaskType.CHAT, self._handle_chat)
        self.queue.register_handler(TaskType.JUDGE, self._handle_judge)
        self.queue.register_handler(TaskType.CHECK_ANSWER, self._handle_check_answer)

    # ---- WebSocket 管理 ----

    async def add_connection(self, uid: str, conn_id: str, ws: WebSocket):
        if uid not in self.ws_connections:
            self.ws_connections[uid] = {}
        self.ws_connections[uid][conn_id] = ws

    def remove_connection(self, uid: str, conn_id: str):
        if uid in self.ws_connections:
            self.ws_connections[uid].pop(conn_id, None)
            if not self.ws_connections[uid]:
                del self.ws_connections[uid]

    async def broadcast(self, message: dict, exclude_uid: Optional[str] = None):
        """向房间内所有连接广播消息。"""
        dead = []
        for uid, conns in self.ws_connections.items():
            if uid == exclude_uid:
                continue
            for cid, ws in conns.items():
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append((uid, cid))
        for uid, cid in dead:
            self.remove_connection(uid, cid)

    async def send_to(self, uid: str, message: dict):
        """向指定用户发送消息。"""
        conns = self.ws_connections.get(uid, {})
        dead = []
        for cid, ws in conns.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.remove_connection(uid, cid)

    @property
    def online_users(self) -> list[str]:
        return list(self.ws_connections.keys())

    # ---- 状态转换快捷方法 ----

    def start_game(self):
        self.sm.transition("start")
        self.started_at = datetime.now().isoformat()

    def finish_game(self):
        try:
            self.sm.transition("finish")
        except ValueError:
            if self.sm.state == State.PROCESSING:
                self.sm.transition("task_done")
            self.sm.transition("finish")
        self.finished_at = datetime.now().isoformat()

    # ---- 任务处理器 (async) ----

    async def _handle_chat(self, task: Task) -> dict:
        """处理AI聊天回复任务。"""
        msg = task.payload.get("message", "")
        q_history = [q["question"] for q in self.question_history[-5:]]
        title = self.puzzle.get("title", "") if self.puzzle else ""

        reply = await agent.reply(
            state=self.sm.state,
            user_message=msg,
            puzzle_title=title,
            question_history=q_history,
        )
        return {"reply": reply, "agent_name": agent.name}

    async def _handle_judge(self, task: Task) -> dict:
        """处理提问判断任务 (是/否/无关)。"""
        question = task.payload["question"]
        if not self.puzzle:
            raise ValueError("谜题数据不存在")
        if not llm_service.is_available():
            raise ValueError("LLM服务不可用")

        history = [q["question"] for q in self.question_history]
        prompt, _ = build_question_judge_prompt(
            question, self.puzzle["situation"], self.puzzle["truth"], history
        )

        # 带重试的LLM调用
        last_err = None
        for attempt in range(2):
            try:
                resp = await llm_service.chat(prompt, temperature=0.3)
                parsed = parse_llm_json(resp)
                if parsed and "answer" in parsed:
                    # 记录提问历史
                    record = {
                        "id": f"q_{self.question_count + 1}",
                        "question": question,
                        "answer": parsed.get("answer", "是"),
                        "reason": parsed.get("reason", ""),
                        "player": task.requester_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                    self.question_history.append(record)
                    self.question_count += 1

                    # 写Redis
                    try:
                        redis_service.append_history(
                            self.room_id, question, parsed["answer"], parsed.get("reason", ""),
                            prefix="room:",
                        )
                    except Exception:
                        pass

                    return {
                        "judgment": parsed,
                        "remaining": self.settings.get("max_questions", 20) - self.question_count,
                        "question_id": record["id"],
                    }
                last_err = f"第{attempt+1}次：格式不完整"
            except LLMError as e:
                raise ValueError(f"LLM调用失败: {e}")
        raise ValueError(f"判断失败 ({last_err})")

    async def _handle_check_answer(self, task: Task) -> dict:
        """处理最终答案检查任务。"""
        answer = task.payload["answer"]
        if not self.puzzle:
            raise ValueError("谜题数据不存在")
        if not llm_service.is_available():
            raise ValueError("LLM服务不可用")

        prompt, _ = build_answer_check_prompt(
            answer, self.puzzle["situation"], self.puzzle["truth"]
        )

        last_err = None
        for attempt in range(2):
            try:
                resp = await llm_service.chat(prompt, temperature=0.3)
                parsed = parse_llm_json(resp)
                if parsed and "is_correct" in parsed:
                    if parsed["is_correct"]:
                        self.winner = task.requester_id
                        self.finish_game()
                        # 清理Redis
                        try:
                            redis_service.delete_puzzle(self.room_id, prefix="room:")
                            redis_service.delete_history(self.room_id, prefix="room:")
                        except Exception:
                            pass
                        return {"is_correct": True, "result": parsed, "truth": self.puzzle["truth"]}
                    else:
                        return {
                            "is_correct": False,
                            "result": parsed,
                            "hint": self._next_hint(),
                        }
                last_err = f"第{attempt+1}次：格式不完整"
            except LLMError as e:
                raise ValueError(f"LLM调用失败: {e}")
        raise ValueError(f"答案检查失败 ({last_err})")

    def _next_hint(self) -> Optional[str]:
        if not self.puzzle:
            return None
        hints = self.puzzle.get("hints", [])
        if self.hints_used < len(hints):
            hint = hints[self.hints_used]
            self.hints_used += 1
            return hint
        return None

    def to_status_dict(self) -> dict:
        game_info = GAME_TYPES.get(self.game_type, {})
        return {
            "room_id": self.room_id,
            "state": self.sm.value,
            "host_uid": self.host_uid,
            "game_type": self.game_type,
            "game_name": game_info.get("name", self.game_type),
            "players": list(self.players.values()),
            "online": self.online_users,
            "question_count": self.question_count,
            "max_questions": self.settings.get("max_questions", 20),
            "winner": self.winner,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "puzzle_title": self.puzzle.get("title", "") if self.puzzle else "",
        }

    @property
    def is_stale(self) -> bool:
        """FINISHED 状态超过 5 分钟视为过期。"""
        if self.sm.state != State.FINISHED or not self.finished_at:
            return False
        from datetime import datetime as dt
        try:
            finished = dt.fromisoformat(self.finished_at)
            return (dt.now() - finished).total_seconds() > 300
        except (ValueError, TypeError):
            return False


class Runtime:
    """全局运行时 — 管理所有房间的生命周期。"""

    def __init__(self, max_rooms: int = 50, max_llm_per_room: int = 2):
        self._rooms: dict[str, Room] = {}
        self._max_rooms = max_rooms
        self._max_llm_per_room = max_llm_per_room
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_room(self, host_uid: str, settings: Optional[dict] = None) -> Room:
        """创建新房间, 启动其任务队列。"""
        if len(self._rooms) >= self._max_rooms:
            raise RuntimeError(f"房间数已达上限 ({self._max_rooms})")

        room_id = f"room_{uuid.uuid4().hex[:8]}"
        settings = settings or {"max_questions": 20, "max_players": 4, "difficulty": "medium"}
        room = Room(room_id, host_uid, settings)
        self._rooms[room_id] = room
        self._ensure_cleanup_task()
        logger.info(f"房间创建: {room_id} host={host_uid}")
        return room

    def get_room(self, room_id: str) -> Optional[Room]:
        return self._rooms.get(room_id)

    async def start_room(self, room_id: str):
        """启动房间的任务队列。"""
        room = self._rooms.get(room_id)
        if room:
            await room.queue.start()

    async def close_room(self, room_id: str):
        """关闭并移除房间。"""
        room = self._rooms.pop(room_id, None)
        if room:
            await room.queue.stop()
            # 通知所有连接
            await room.broadcast({"type": "system", "content": "房间已关闭"})
            # 关闭所有WS
            for uid, conns in list(room.ws_connections.items()):
                for cid, ws in list(conns.items()):
                    try:
                        await ws.close(code=1000)
                    except Exception:
                        pass
            room.ws_connections.clear()
            logger.info(f"房间关闭: {room_id}")

    async def submit_task(
        self,
        room_id: str,
        task_type: TaskType,
        payload: dict,
        requester_id: str,
    ) -> Optional[str]:
        """向房间提交任务, 自动触发状态转换。返回 task_id。"""
        room = self._rooms.get(room_id)
        if not room:
            return None

        task = Task(
            type=task_type,
            payload=payload,
            room_id=room_id,
            requester_id=requester_id,
        )

        # 状态转换: RUNNING → PROCESSING
        if room.sm.can("task_submit"):
            try:
                room.sm.transition("task_submit")
            except ValueError:
                pass

        task_id = await room.queue.submit(task)
        return task_id

    async def wait_for_task(self, room_id: str, task_id: str, timeout: float = 30.0) -> Optional[dict]:
        """等待任务完成, 轮询检查。"""
        room = self._rooms.get(room_id)
        if not room:
            return None

        elapsed = 0.0
        interval = 0.2
        while elapsed < timeout:
            task = room.queue.get_task(task_id)
            if not task:
                return None
            if task.status == TaskStatus.DONE:
                if room.sm.can("task_done"):
                    try:
                        room.sm.transition("task_done")
                    except ValueError:
                        pass
                return {"status": "done", "result": task.result}
            if task.status == TaskStatus.FAILED:
                if room.sm.can("task_done"):
                    try:
                        room.sm.transition("task_done")
                    except ValueError:
                        pass
                return {"status": "failed", "error": task.error}
            await asyncio.sleep(interval)
            elapsed += interval

        return {"status": "timeout", "error": f"任务超时 ({timeout}s)"}

    @property
    def room_count(self) -> int:
        return len(self._rooms)

    def list_rooms(self) -> list[dict]:
        return [room.to_status_dict() for room in self._rooms.values()]

    def get_player_room(self, uid: str) -> Optional[str]:
        """查找用户所在的房间。"""
        for rid, room in self._rooms.items():
            if uid in room.players:
                return rid
        return None

    async def _cleanup_loop(self):
        """定时清理过期的已结束房间。"""
        while True:
            await asyncio.sleep(60)
            stale_ids = [rid for rid, room in self._rooms.items() if room.is_stale]
            for rid in stale_ids:
                await self.close_room(rid)
                logger.info(f"自动清理过期房间: {rid}")

    def _ensure_cleanup_task(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._cleanup_loop())
            except RuntimeError:
                pass


# 全局单例
runtime = Runtime()
