from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey
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
    created_at = Column(TIMESTAMP, default=datetime.now, nullable=False)
    last_login_at = Column(TIMESTAMP, nullable=True)


class PublicChatMessage(Base):
    __tablename__ = "public_chat_messages"

    msg_id = Column(Integer, primary_key=True, autoincrement=True)
    sender_uid = Column(String(12), ForeignKey("users.uid"), nullable=False)
    content = Column(Text, nullable=False)
    send_time = Column(TIMESTAMP, default=datetime.now, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
