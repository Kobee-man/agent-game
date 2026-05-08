import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from core.db import get_db
from core.security import get_password_hash, verify_password, create_access_token
from models.db_models import User

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    password: str
    nickname: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v or len(v) < 3 or len(v) > 20:
            raise ValueError("用户名长度3-20位")
        if not v.isalnum():
            raise ValueError("用户名只能包含字母和数字")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError("密码至少6位")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    username: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError("新密码至少6位")
        return v


@router.post("/register", summary="用户注册")
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    db_user = User(
        uid=uuid.uuid4().hex[:12],
        username=user.username,
        nickname=user.nickname,
        password=get_password_hash(user.password),
    )
    db.add(db_user)
    db.commit()
    return {"msg": "注册成功", "username": user.username}


@router.post("/login", summary="登录获取Token")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return {"access_token": create_access_token({"sub": data.username}), "token_type": "bearer"}


@router.post("/forgot-password", summary="重置密码")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password = get_password_hash(req.new_password)
    db.commit()
    return {"msg": "密码重置成功"}
