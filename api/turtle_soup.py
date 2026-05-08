import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.llm_service import llm_service, LLMError
from core.redis_service import redis_service
from core.json_parser import parse_llm_json
from api.prompts import build_puzzle_prompt, build_question_judge_prompt, build_answer_check_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/turtle-soup", tags=["海龟汤游戏"])

# 内存游戏状态（重启丢失）
games_db: dict = {}


# ==================== 请求模型 ====================

class GameCreate(BaseModel):
    difficulty: str = Field(default="medium")
    max_questions: int = Field(default=20, ge=5, le=50)
    max_players: int = Field(default=4, ge=1, le=10)


class PlayerJoin(BaseModel):
    game_id: str
    player_username: str


class QuestionSubmit(BaseModel):
    game_id: str
    question: str
    player_username: str


class AnswerJudge(BaseModel):
    game_id: str
    answer: str
    player_username: str


class SinglePlayerJudge(BaseModel):
    game_id: str
    question: str
    question_history: list[str] = []


# ==================== 辅助 ====================

def _puzzle(game_id: str) -> Optional[dict]:
    game = games_db.get(game_id)
    if game and game.get("_puzzle"):
        return game["_puzzle"]
    return redis_service.get_puzzle(game_id)


def _next_hint(game: dict) -> Optional[str]:
    puzzle = game.get("_puzzle") or {}
    hints = puzzle.get("hints", [])
    if game["hints_used"] < len(hints):
        hint = hints[game["hints_used"]]
        game["hints_used"] += 1
        return hint
    return None


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
        redis_service.append_history(game_id, question, answer, reason)
    except Exception:
        logger.warning(f"Redis历史写入失败: {game_id}")


# ==================== 端点 ====================

@router.post("/create-game")
async def create_game(data: GameCreate):
    """创建游戏 — LLM生成题目"""
    if not llm_service.is_available():
        raise HTTPException(status_code=503, detail="LLM服务不可用")

    game_id = f"game_{uuid.uuid4().hex[:8]}"
    prompt, system = build_puzzle_prompt(data.difficulty)

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
        except LLMError as e:
            raise HTTPException(status_code=503, detail=f"LLM失败: {e}")

    if not puzzle:
        raise HTTPException(status_code=500, detail=f"题目生成失败 ({last_err})")

    redis_service.set_puzzle(game_id, puzzle)

    games_db[game_id] = {
        "id": game_id,
        "status": "waiting",
        "settings": {"difficulty": data.difficulty, "max_questions": data.max_questions, "max_players": data.max_players},
        "players": [],
        "host": None,
        "questions": [],
        "question_count": 0,
        "hints_used": 0,
        "winner": None,
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "finished_at": None,
        "_puzzle": puzzle,
    }

    return {
        "success": True,
        "game_id": game_id,
        "puzzle_preview": {
            "title": puzzle["title"],
            "situation": puzzle["situation"],
            "difficulty": puzzle.get("difficulty", data.difficulty),
            "category": puzzle.get("category", ""),
        },
    }


@router.post("/join-game")
async def join_game(data: PlayerJoin):
    game = games_db.get(data.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    if len(game["players"]) >= game["settings"]["max_players"]:
        raise HTTPException(status_code=400, detail="游戏已满")
    if any(p["username"] == data.player_username for p in game["players"]):
        raise HTTPException(status_code=400, detail="已在游戏中")

    game["players"].append({"username": data.player_username, "joined_at": datetime.now().isoformat(), "score": 0})
    if len(game["players"]) == 1:
        game["host"] = data.player_username

    return {"success": True, "players": len(game["players"]), "max": game["settings"]["max_players"]}


class StartGameReq(BaseModel):
    game_id: str
    host_username: str


@router.post("/start-game")
async def start_game(req: StartGameReq):
    game = games_db.get(req.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    if game["host"] != req.host_username:
        raise HTTPException(status_code=403, detail="仅房主可开始")
    if len(game["players"]) < 1:
        raise HTTPException(status_code=400, detail="至少需要1名玩家")

    game["status"] = "playing"
    game["started_at"] = datetime.now().isoformat()
    puzzle = _puzzle(req.game_id) or {}

    return {
        "success": True,
        "puzzle": {"title": puzzle.get("title", ""), "situation": puzzle.get("situation", "")},
        "players": [p["username"] for p in game["players"]],
    }


@router.post("/ask-question")
async def ask_question(data: QuestionSubmit):
    """提问 — LLM判断"""
    game = games_db.get(data.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    if game["status"] != "playing":
        raise HTTPException(status_code=400, detail="游戏未开始")
    if game["question_count"] >= game["settings"]["max_questions"]:
        raise HTTPException(status_code=400, detail="已达提问上限")
    if not llm_service.is_available():
        raise HTTPException(status_code=503, detail="LLM不可用")

    puzzle = _puzzle(data.game_id)
    if not puzzle:
        raise HTTPException(status_code=500, detail="题目数据丢失")

    history = [q["question"] for q in game["questions"]]
    prompt, _ = build_question_judge_prompt(data.question, puzzle["situation"], puzzle["truth"], history)

    judgment = await _llm_judge(prompt, "answer")

    record = {
        "id": f"q_{len(game['questions'])+1}",
        "question": data.question,
        "answer": judgment.get("answer", "是"),
        "reason": judgment.get("reason", ""),
        "player": data.player_username,
        "timestamp": datetime.now().isoformat(),
    }
    game["questions"].append(record)
    game["question_count"] += 1

    _save_history(data.game_id, data.question, record["answer"], record["reason"])

    return {
        "success": True,
        "judgment": judgment,
        "remaining": game["settings"]["max_questions"] - game["question_count"],
    }


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
            "timestamp": datetime.now().isoformat(),
        })
        game["question_count"] += 1

    return {"success": True, "judgment": judgment}


@router.post("/submit-answer")
async def submit_answer(data: AnswerJudge):
    """提交最终答案"""
    game = games_db.get(data.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    if game["status"] not in ("playing", "waiting"):
        raise HTTPException(status_code=400, detail="游戏未在进行中")
    if game["status"] == "waiting":
        game["status"] = "playing"
        game["started_at"] = datetime.now().isoformat()
    if not llm_service.is_available():
        raise HTTPException(status_code=503, detail="LLM不可用")

    puzzle = _puzzle(data.game_id)
    if not puzzle:
        raise HTTPException(status_code=500, detail="题目数据丢失")

    prompt, _ = build_answer_check_prompt(data.answer, puzzle["situation"], puzzle["truth"])
    result = await _llm_judge(prompt, "is_correct")

    if result.get("is_correct"):
        game["status"] = "finished"
        game["winner"] = data.player_username
        game["finished_at"] = datetime.now().isoformat()

        redis_service.delete_puzzle(data.game_id)
        try:
            redis_service.delete_history(data.game_id)
        except Exception:
            pass

        return {"success": True, "is_correct": True, "result": result, "truth": puzzle["truth"]}

    return {"success": True, "is_correct": False, "result": result, "hint": _next_hint(game)}


@router.get("/hint")
async def get_hint(game_id: str):
    game = games_db.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    puzzle = _puzzle(game_id) or {}
    hint = _next_hint(game)
    if hint:
        return {"success": True, "hint": hint, "remaining": len(puzzle.get("hints", [])) - game["hints_used"]}
    return {"success": False, "message": "没有更多提示"}


@router.get("/game-status/{game_id}")
async def game_status(game_id: str):
    game = games_db.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    puzzle = _puzzle(game_id) or {}
    return {
        "game_id": game_id,
        "status": game["status"],
        "puzzle": {
            "title": puzzle.get("title", ""),
            "situation": puzzle.get("situation") if game["status"] != "waiting" else None,
            "truth": puzzle.get("truth") if game["status"] == "finished" else None,
        },
        "players": game["players"],
        "question_count": game["question_count"],
        "recent_questions": game["questions"][-5:],
        "winner": game["winner"],
    }


@router.delete("/game/{game_id}")
async def delete_game(game_id: str):
    if game_id not in games_db:
        raise HTTPException(status_code=404, detail="游戏不存在")
    del games_db[game_id]
    redis_service.delete_puzzle(game_id)
    try:
        redis_service.delete_history(game_id)
    except Exception:
        pass
    return {"success": True}


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
