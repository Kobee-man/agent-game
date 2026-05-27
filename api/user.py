from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, AVATAR_DIR
from core.db import get_db
from core.security import get_current_user
from models.db_models import User

router = APIRouter()


class UserUpdate(BaseModel):
    nickname: str | None = None


@router.get("/profile", summary="当前用户信息")
def profile(current_user: User = Depends(get_current_user)):
    return {
        "msg": "获取成功",
        "data": {
            "uid": current_user.uid,
            "username": current_user.username,
            "nickname": current_user.nickname or current_user.username,
            "avatar_url": current_user.avatar_url,
        },
    }


@router.put("/user/nickname", summary="修改昵称")
def update_nickname(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_update.nickname:
        raise HTTPException(status_code=400, detail="昵称不能为空")
    current_user.nickname = user_update.nickname # type: ignore
    db.commit()
    return {"msg": "昵称修改成功", "data": {"nickname": current_user.nickname}}


@router.post("/user/avatar", summary="上传头像")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or "." not in file.filename:
        raise HTTPException(status_code=400, detail="文件名无效")

    ext = file.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png/gif")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件超过5MB限制")

    save_name = f"{current_user.uid}.{ext}"
    (AVATAR_DIR / save_name).write_bytes(contents)

    current_user.avatar_url = f"/static/avatars/{save_name}" # type: ignore
    db.commit()
    return {"msg": "头像上传成功", "avatar_url": current_user.avatar_url}
