"""房间API — 创建房间, WebSocket聊天, AI回复, 状态机。

数据流:
  WS收到消息 → 放任务队列 → 后台LLM处理 → 广播结果到WS

状态机: WAITING → RUNNING → PROCESSING → FINISHED
"""

import asyncio
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session

from core.config import SECRET_KEY, ALGORITHM
from core.db import get_db, SessionLocal
from core.security import get_current_user
from core.state_machine import State
from core.task_queue import TaskType
from core.runtime import runtime, Room
from core.agent import agent
from core.llm_service import llm_service
from core.json_parser import parse_llm_json
from core.redis_service import redis_service
from core.prompts import build_puzzle_prompt
from models.db_models import User, PublicChatMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/room", tags=["房间"])


# ==================== 请求模型 ====================

from pydantic import BaseModel, Field


class CreateRoomReq(BaseModel):
    difficulty: str = Field(default="medium")
    max_questions: int = Field(default=20, ge=5, le=50)
    max_players: int = Field(default=4, ge=1, le=10)


class JoinRoomReq(BaseModel):
    room_id: str


class StartRoomReq(BaseModel):
    room_id: str


# ==================== 辅助 ====================

def _decode_ws_token(token: str, db: Session) -> User:
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise JWTError()
    except JWTError:
        raise HTTPException(status_code=1008, detail="认证失败")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=1008, detail="用户不存在")
    return user


def _save_message(uid: str, content: str, is_system: bool):
    db = SessionLocal()
    try:
        db.add(PublicChatMessage(sender_uid=uid, content=content, is_system=is_system))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ==================== REST 端点 ====================

@router.post("/create")
async def create_room(
    data: CreateRoomReq,
    current_user: User = Depends(get_current_user),
):
    """创建房间（需要登录）。"""
    # 检查用户是否已在其他房间
    existing = runtime.get_player_room(current_user.uid)
    if existing:
        raise HTTPException(status_code=400, detail=f"已在房间 {existing} 中, 请先离开")

    settings = {
        "difficulty": data.difficulty,
        "max_questions": data.max_questions,
        "max_players": data.max_players,
    }
    room = runtime.create_room(host_uid=current_user.uid, settings=settings)

    # 自动加入
    room.players[current_user.uid] = {
        "uid": current_user.uid,
        "username": current_user.username,
        "nickname": current_user.nickname or current_user.username,
        "joined_at": datetime.now().isoformat(),
    }

    await runtime.start_room(room.room_id)

    return {
        "success": True,
        "room_id": room.room_id,
        "state": room.sm.value,
        "host": current_user.username,
    }


@router.post("/join")
async def join_room(
    data: JoinRoomReq,
    current_user: User = Depends(get_current_user),
):
    """加入房间。"""
    room = runtime.get_room(data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.sm.state not in (State.WAITING, State.RUNNING):
        raise HTTPException(status_code=400, detail=f"房间状态 ({room.sm.value}) 不允许加入")
    if current_user.uid in room.players:
        raise HTTPException(status_code=400, detail="已在房间中")
    if len(room.players) >= room.settings.get("max_players", 4):
        raise HTTPException(status_code=400, detail="房间已满")

    room.players[current_user.uid] = {
        "uid": current_user.uid,
        "username": current_user.username,
        "nickname": current_user.nickname or current_user.username,
        "joined_at": datetime.now().isoformat(),
    }

    return {
        "success": True,
        "room_id": room.room_id,
        "state": room.sm.value,
        "players": len(room.players),
    }


@router.post("/start")
async def start_room(
    data: StartRoomReq,
    current_user: User = Depends(get_current_user),
):
    """房主开始游戏 — LLM生成谜题, 状态转为 RUNNING。"""
    room = runtime.get_room(data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.host_uid != current_user.uid:
        raise HTTPException(status_code=403, detail="仅房主可开始")
    if room.sm.state != State.WAITING:
        raise HTTPException(status_code=400, detail=f"当前状态 ({room.sm.value}) 无法开始")
    if not llm_service.is_available():
        raise HTTPException(status_code=503, detail="LLM服务不可用")

    # LLM生成谜题
    difficulty = room.settings.get("difficulty", "medium")
    prompt, system = build_puzzle_prompt(difficulty)

    puzzle = None
    last_err = None
    for attempt in range(2):
        try:
            resp = await llm_service.chat(prompt, system, temperature=0.6)
            parsed = parse_llm_json(resp)
            if not parsed or not parsed.get("situation") or not parsed.get("truth"):
                last_err = f"第{attempt+1}次：格式不完整"
                continue
            parsed.setdefault("title", "未命名谜题")
            parsed.setdefault("hints", [])
            parsed.setdefault("category", "未分类")
            puzzle = parsed
            break
        except Exception as e:
            last_err = str(e)
            continue

    if not puzzle:
        raise HTTPException(status_code=500, detail=f"题目生成失败 ({last_err})")

    room.puzzle = puzzle

    # Redis备份
    try:
        redis_service.set_puzzle(room.room_id, puzzle)
    except Exception:
        pass

    # 状态转换: WAITING → RUNNING
    room.start_game()

    # 广播游戏开始
    system_msg = await agent.generate_system_message(State.RUNNING, puzzle)
    await room.broadcast({
        "type": "system",
        "content": system_msg,
        "timestamp": datetime.now().isoformat(),
    })

    return {
        "success": True,
        "room_id": room.room_id,
        "state": room.sm.value,
        "puzzle": {
            "title": puzzle["title"],
            "situation": puzzle["situation"],
            "category": puzzle.get("category", ""),
        },
        "players": [p["username"] for p in room.players.values()],
    }


@router.get("/status/{room_id}")
async def room_status(room_id: str):
    """查看房间状态。"""
    room = runtime.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    return room.to_status_dict()


@router.get("/list")
async def list_rooms():
    """列出所有房间。"""
    return {"rooms": runtime.list_rooms(), "total": runtime.room_count}


@router.post("/leave")
async def leave_room(current_user: User = Depends(get_current_user)):
    """离开当前房间。"""
    room_id = runtime.get_player_room(current_user.uid)
    if not room_id:
        raise HTTPException(status_code=400, detail="未在任何房间中")
    room = runtime.get_room(room_id)
    if room:
        del room.players[current_user.uid]
        # 如果房主离开且还有玩家, 转移房主
        if room.host_uid == current_user.uid and room.players:
            room.host_uid = next(iter(room.players))
        # 没有玩家了就关闭
        if not room.players and room.sm.state != State.RUNNING:
            await runtime.close_room(room_id)
    return {"success": True, "left": room_id}


# ==================== WebSocket ====================

@router.websocket("/ws/{room_id}/{token}")
async def websocket_room(ws: WebSocket, room_id: str, token: str):
    """房间WebSocket — 聊天 + AI自动回复 + 任务队列。

    消息格式:
      发送: {"content": "消息内容", "action": "chat"|"ask"|"answer"}
      接收: {"type": "message"|"system"|"ai_reply"|"judgment"|"answer_result", ...}
    """
    db = next(get_db())
    try:
        user = _decode_ws_token(token, db)
    except HTTPException:
        await ws.close(code=1008, reason="认证失败")
        return

    room = runtime.get_room(room_id)
    if not room:
        await ws.close(code=1008, reason="房间不存在")
        return

    # 检查是否已在房间中
    if user.uid not in room.players:
        await ws.close(code=1008, reason="请先通过HTTP接口加入房间")
        return

    conn_id = str(uuid.uuid4())
    await ws.accept()
    await room.add_connection(user.uid, conn_id, ws)

    display_name = user.nickname or user.username
    uid = str(user.uid)

    # 发送当前房间状态
    await ws.send_json({
        "type": "room_state",
        "state": room.sm.value,
        "puzzle_title": room.puzzle.get("title", "") if room.puzzle else "",
        "players": [p["username"] for p in room.players.values()],
        "question_count": room.question_count,
        "max_questions": room.settings.get("max_questions", 20),
        "timestamp": datetime.now().isoformat(),
    })

    # 广播加入
    join_msg = {
        "type": "system",
        "content": f"{display_name} 加入了房间",
        "username": user.username,
        "nickname": display_name,
        "timestamp": datetime.now().isoformat(),
    }
    await room.broadcast(join_msg)
    asyncio.get_event_loop().run_in_executor(None, _save_message, uid, join_msg["content"], True)

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action", "chat")
            content = data.get("content", "").strip()
            if not content:
                continue

            if action == "chat":
                # ---- 普通聊天 ----
                # 广播用户消息
                msg = {
                    "type": "message",
                    "content": content,
                    "username": user.username,
                    "nickname": display_name,
                    "avatar_url": user.avatar_url,
                    "timestamp": datetime.now().isoformat(),
                }
                await room.broadcast(msg)
                asyncio.get_event_loop().run_in_executor(None, _save_message, uid, content, False)

                # 提交AI回复任务到队列
                task_id = await runtime.submit_task(
                    room_id, TaskType.CHAT,
                    {"message": content},
                    requester_id=uid,
                )
                if task_id:
                    # 后台等待结果并广播
                    asyncio.create_task(_broadcast_ai_reply(room, room_id, task_id, user.username))

            elif action == "ask" and room.sm.state == State.RUNNING:
                # ---- 提问 (是/否/无关) ----
                max_q = room.settings.get("max_questions", 20)
                if room.question_count >= max_q:
                    await ws.send_json({
                        "type": "error",
                        "content": f"已达提问上限 ({max_q})",
                    })
                    continue

                # 广播提问消息
                ask_msg = {
                    "type": "message",
                    "content": f"[提问] {content}",
                    "username": user.username,
                    "nickname": display_name,
                    "timestamp": datetime.now().isoformat(),
                }
                await room.broadcast(ask_msg)

                # 提交判断任务
                task_id = await runtime.submit_task(
                    room_id, TaskType.JUDGE,
                    {"question": content},
                    requester_id=uid,
                )
                if task_id:
                    asyncio.create_task(_broadcast_judgment(room, room_id, task_id, content))

            elif action == "answer" and room.sm.state == State.RUNNING:
                # ---- 提交最终答案 ----
                answer_msg = {
                    "type": "message",
                    "content": f"[答题] {content}",
                    "username": user.username,
                    "nickname": display_name,
                    "timestamp": datetime.now().isoformat(),
                }
                await room.broadcast(answer_msg)

                task_id = await runtime.submit_task(
                    room_id, TaskType.CHECK_ANSWER,
                    {"answer": content},
                    requester_id=uid,
                )
                if task_id:
                    asyncio.create_task(_broadcast_answer_result(room, room_id, task_id, display_name))

            elif action == "hint" and room.sm.state == State.RUNNING:
                # ---- 获取提示 ----
                hint = room._next_hint()
                if hint:
                    await room.broadcast({
                        "type": "system",
                        "content": f"提示: {hint}",
                        "timestamp": datetime.now().isoformat(),
                    })
                else:
                    await ws.send_json({"type": "error", "content": "没有更多提示了"})

    except WebSocketDisconnect:
        room.remove_connection(user.uid, conn_id)
        leave_msg = {
            "type": "system",
            "content": f"{display_name} 离开了房间",
            "username": user.username,
            "nickname": display_name,
            "timestamp": datetime.now().isoformat(),
        }
        await room.broadcast(leave_msg)
        asyncio.get_event_loop().run_in_executor(None, _save_message, uid, leave_msg["content"], True)


# ==================== 后台任务回调 ====================

async def _broadcast_ai_reply(room: Room, room_id: str, task_id: str, trigger_user: str):
    """等待AI回复任务完成, 广播结果。"""
    result = await runtime.wait_for_task(room_id, task_id, timeout=30.0)
    if not result or result.get("status") != "done":
        logger.warning(f"AI回复任务失败: {result}")
        return

    reply_text = result["result"].get("reply", "")
    if reply_text:
        await room.broadcast({
            "type": "ai_reply",
            "content": reply_text,
            "username": "ai",
            "nickname": "AI主持人",
            "triggered_by": trigger_user,
            "timestamp": datetime.now().isoformat(),
        })


async def _broadcast_judgment(room: Room, room_id: str, task_id: str, question: str):
    """等待判断任务完成, 广播结果。"""
    result = await runtime.wait_for_task(room_id, task_id, timeout=30.0)
    if not result:
        return

    if result.get("status") == "done":
        judgment = result["result"].get("judgment", {})
        answer = judgment.get("answer", "是")
        remaining = result["result"].get("remaining", 0)
        await room.broadcast({
            "type": "judgment",
            "content": f"Q: {question}\nA: {answer}",
            "question": question,
            "answer": answer,
            "reason": judgment.get("reason", ""),
            "remaining": remaining,
            "timestamp": datetime.now().isoformat(),
        })
    else:
        await room.broadcast({
            "type": "error",
            "content": f"判断失败: {result.get('error', '未知错误')}",
            "timestamp": datetime.now().isoformat(),
        })


async def _broadcast_answer_result(room: Room, room_id: str, task_id: str, player_name: str):
    """等待答案检查完成, 广播结果。"""
    result = await runtime.wait_for_task(room_id, task_id, timeout=30.0)
    if not result:
        return

    if result.get("status") == "done":
        data = result["result"]
        if data.get("is_correct"):
            await room.broadcast({
                "type": "game_over",
                "content": f"{player_name} 答对了！真相已揭开！",
                "winner": player_name,
                "truth": data.get("truth", ""),
                "result": data.get("result", {}),
                "timestamp": datetime.now().isoformat(),
            })
        else:
            await room.broadcast({
                "type": "answer_result",
                "content": f"{player_name} 的答案不太对, 继续推理！",
                "is_correct": False,
                "feedback": data.get("result", {}).get("feedback", ""),
                "hint": data.get("hint"),
                "timestamp": datetime.now().isoformat(),
            })
    else:
        await room.broadcast({
            "type": "error",
            "content": f"答案检查失败: {result.get('error', '未知错误')}",
            "timestamp": datetime.now().isoformat(),
        })
