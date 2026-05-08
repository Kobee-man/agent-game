import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import select

from core.config import SECRET_KEY, ALGORITHM
from core.db import get_db, SessionLocal
from core.security import get_current_user
from models.db_models import User, PublicChatMessage

logger = logging.getLogger(__name__)
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, Dict[str, WebSocket]] = {}  # user_id -> {conn_id: ws}
        self.conn_to_user: Dict[str, str] = {}  # conn_id -> user_id

    async def connect(self, user: User, websocket: WebSocket, db: Session) -> str:
        conn_id = str(uuid.uuid4())
        await websocket.accept()

        uid = str(user.uid)
        if uid not in self.active:
            self.active[uid] = {}
        self.active[uid][conn_id] = websocket
        self.conn_to_user[conn_id] = uid

        # 发送历史消息
        messages = (
            db.query(PublicChatMessage, User)
            .join(User, PublicChatMessage.sender_uid == User.uid)
            .order_by(PublicChatMessage.send_time.desc())
            .limit(50)
            .all()
        )
        messages.reverse()

        history = [
            {
                "type": "system" if msg.is_system else "message",
                "content": msg.content,
                "username": user_row.username,
                "nickname": user_row.nickname or user_row.username,
                "avatar_url": user_row.avatar_url,
                "timestamp": msg.send_time.isoformat(),
            }
            for msg, user_row in messages
        ]

        await websocket.send_json({"type": "history", "messages": history, "timestamp": datetime.now().isoformat()})
        return conn_id

    def disconnect(self, conn_id: str) -> str | None:
        uid = self.conn_to_user.pop(conn_id, None)
        if uid and uid in self.active:
            self.active[uid].pop(conn_id, None)
            if not self.active[uid]:
                del self.active[uid]
        return uid

    async def broadcast(self, message: dict):
        dead = []
        for uid, conns in self.active.items():
            for cid, ws in conns.items():
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    def save_message(self, uid: str, content: str, is_system: bool):
        db = SessionLocal()
        try:
            db.add(PublicChatMessage(sender_uid=uid, content=content, is_system=is_system))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


manager = ConnectionManager()


def _decode_token(token: str, db: Session) -> User:
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


@router.websocket("/ws/chat/{token}")
async def websocket_chat(websocket: WebSocket, token: str):
    db = next(get_db())
    try:
        user = _decode_token(token, db)
    except HTTPException:
        await websocket.close(code=1008, reason="认证失败")
        return

    conn_id = await manager.connect(user, websocket, db)
    uid = str(user.uid)
    display_name = user.nickname or user.username

    # 上线广播
    join_msg = {
        "type": "system",
        "content": f"{display_name} 加入了聊天室",
        "username": user.username,
        "nickname": display_name,
        "avatar_url": user.avatar_url,
        "timestamp": datetime.now().isoformat(),
    }
    await manager.broadcast(join_msg)
    asyncio.get_event_loop().run_in_executor(None, manager.save_message, uid, join_msg["content"], True)

    try:
        while True:
            data = await websocket.receive_json()
            msg = {
                "type": "message",
                "content": data.get("content", ""),
                "username": user.username,
                "nickname": display_name,
                "avatar_url": user.avatar_url,
                "timestamp": datetime.now().isoformat(),
            }
            await manager.broadcast(msg)
            asyncio.get_event_loop().run_in_executor(None, manager.save_message, uid, msg["content"], False)
    except WebSocketDisconnect:
        manager.disconnect(conn_id)
        leave_msg = {
            "type": "system",
            "content": f"{display_name} 离开了聊天室",
            "username": user.username,
            "nickname": display_name,
            "timestamp": datetime.now().isoformat(),
        }
        await manager.broadcast(leave_msg)
        asyncio.get_event_loop().run_in_executor(None, manager.save_message, uid, leave_msg["content"], True)


@router.get("/chat/online-users", summary="在线用户")
def get_online_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seen = set()
    users = []
    for uid in manager.conn_to_user.values():
        if uid in seen:
            continue
        seen.add(uid)
        user = db.query(User).filter(User.uid == uid).first()
        if user:
            users.append({"uid": user.uid, "username": user.username, "nickname": user.nickname or user.username})
    return {"msg": "获取成功", "data": users}


@router.get("/chat/history", summary="聊天历史")
def get_chat_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PublicChatMessage, User)
        .join(User, PublicChatMessage.sender_uid == User.uid)
        .order_by(PublicChatMessage.send_time.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()

    return {
        "msg": "获取成功",
        "data": [
            {
                "type": "system" if msg.is_system else "message",
                "content": msg.content,
                "username": user.username,
                "nickname": user.nickname or user.username,
                "avatar_url": user.avatar_url,
                "timestamp": msg.send_time.isoformat(),
            }
            for msg, user in rows
        ],
    }
