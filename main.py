from datetime import datetime
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from core.db import engine, init_db
from core.llm_service import llm_service
from api import auth, user, chat, turtle_soup, room

# 检查 MySQL 连接
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[OK] 数据库连接成功")
except Exception as e:
    print(f"[ERROR] 数据库连接失败: {e}")
    print("请先启动 MySQL 服务，再运行本项目")
    exit(1)

init_db()

app = FastAPI(title="Turtle Soup API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(chat.router)
app.include_router(turtle_soup.router)
app.include_router(room.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0", "llm": "available" if llm_service.is_available() else "not_configured"}


@app.get("/api/status")
async def status():
    return {"status": "online", "version": "2.0.0", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
