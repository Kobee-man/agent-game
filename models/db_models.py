from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime
from core.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(12), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    nickname = Column(String(50), default="")
    avatar_url = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    last_login = Column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_uid = Column(String(12), ForeignKey("users.uid"), nullable=False)
    room_id = Column(String(32), nullable=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)


class PuzzleBank(Base):
    """题库表 — LLM降级时使用，上限50道，FIFO淘汰。"""
    __tablename__ = "puzzle_bank"

    idx = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, default="未命名谜题")
    situation = Column(Text, nullable=False)
    truth = Column(Text, nullable=False)
    category = Column(String(50), default="未分类")
    hints = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
