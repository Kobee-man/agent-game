import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.llm_service import llm_service, LLMError
from core.redis_service import redis_service
from core.json_parser import parse_llm_json
from core.prompts import build_question_judge_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/turtle-soup", tags=["海龟汤游戏"])

# 内存游戏状态（仅单人模式使用）
games_db: dict = {}


# ==================== 请求模型 ====================

class SinglePlayerJudge(BaseModel):
    game_id: str
    question: str
    question_history: list[str] = []


# ==================== 辅助 ====================

def _puzzle(game_id: str) -> Optional[dict]:
    game = games_db.get(game_id)
    if game and game.get("_puzzle"):
        return game["_puzzle"]
    return redis_service.get_puzzle(game_id, prefix="single:") # type: ignore


async def _llm_judge(prompt: str, required_key: str, retries: int = 2) -> dict:
    """调用LLM并解析JSON，带重试。"""
    last_err = None
    for attempt in range(retries):
        try:
            resp = await llm_service.chat(prompt, temperature=0.3)
            parsed = parse_llm_json(resp)
            if parsed and required_key in parsed:
                return parsed
            last_err = f"第{attempt+1}次：缺少 {required_key}"
        except LLMError as e:
            raise HTTPException(status_code=503, detail=f"LLM调用失败: {e}")
    raise HTTPException(status_code=500, detail=f"LLM返回异常 ({last_err})")


def _save_history(game_id: str, question: str, answer: str, reason: str = ""):
    try:
        redis_service.append_history(game_id, question, answer, reason, prefix="single:") # type: ignore
    except Exception:
        logger.warning(f"Redis历史写入失败: {game_id}")


# ==================== 端点 ====================

@router.post("/judge-question")
async def judge_question(data: SinglePlayerJudge):
    """单人模式提问"""
    if not llm_service.is_available():
        raise HTTPException(status_code=503, detail="LLM不可用")

    puzzle = _puzzle(data.game_id)
    if not puzzle:
        raise HTTPException(status_code=404, detail="题目不存在或已过期")

    prompt, _ = build_question_judge_prompt(data.question, puzzle["situation"], puzzle["truth"], data.question_history)
    judgment = await _llm_judge(prompt, "answer")

    _save_history(data.game_id, data.question, judgment.get("answer", "是"), judgment.get("reason", ""))

    # 同步到内存
    game = games_db.get(data.game_id)
    if game:
        game["questions"].append({
            "id": f"q_{len(game['questions'])+1}",
            "question": data.question,
            "answer": judgment.get("answer", "是"),
            "player": "single",
        })
        game["question_count"] += 1

    return {"success": True, "judgment": judgment}


@router.get("/rules")
async def rules():
    return {
        "rules": (
            "## 海龟汤规则\n"
            "1. AI生成一个令人困惑的情境\n"
            "2. 玩家提问只能用'是/否/无关'回答\n"
            "3. 通过推理还原真相\n"
            "4. 第一个正确说出真相的玩家获胜"
        ),
        "tips": ["从'为什么'开始提问", "注意时间地点人物关系", "卡住时使用提示"],
    }
