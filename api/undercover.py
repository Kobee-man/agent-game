"""谁是卧底 REST API — 与海龟汤平等的独立路由。

端点:
  POST /undercover/start           房主开游戏、分配词语
  POST /undercover/describe        提交描述（敏感词自动过滤）
  POST /undercover/vote            投票
  GET  /undercover/status/{room_id} 房间内游戏状态（需登录）
  GET  /undercover/rules           游戏规则
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.security import get_current_user
from core.runtime import runtime
from core.undercover import UndercoverGame
from core.ai_player import AIThinker
from models.db_models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/undercover", tags=["谁是卧底"])


# ==================== 请求模型 ====================

class StartGameReq(BaseModel):
    room_id: str


class DescribeReq(BaseModel):
    room_id: str
    description: str = Field(..., min_length=1, max_length=200)


class VoteReq(BaseModel):
    room_id: str
    target_uid: str


class AddAIReq(BaseModel):
    room_id: str
    count: int = Field(default=1, ge=1, le=7, description="添加几个AI玩家")


# ==================== 辅助 ====================

def _get_room_and_game(room_id: str):
    room = runtime.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    game: UndercoverGame | None = getattr(room, "undercover_game", None)
    if not game:
        raise HTTPException(status_code=400, detail="游戏尚未开始")
    return room, game


async def _broadcast_game_start(room, game):
    """广播游戏开始：私发每人词语，广播状态。"""
    for p_uid in room.players:
        await room.send_to(p_uid, {
            "type": "word_assigned",
            "word": game.get_word(p_uid),
            "role": game.get_role(p_uid),
            "round": game.round_num,
            "phase": game.phase,
        })
    await room.broadcast({
        "type": "undercover_state",
        "phase": "describing",
        "round": game.round_num,
        "turn_order": game.turn_order,
        "current_turn": game.get_next_describer(),
        "alive_count": len(game.alive_players),
    })


async def _broadcast_described(room, game, uid, username, nickname, filtered, is_violation):
    """广播一条描述，描述完毕自动广播投票开始。"""
    await room.broadcast({
        "type": "player_described",
        "uid": uid,
        "username": username,
        "nickname": nickname,
        "description": filtered,
        "has_violation": is_violation,
        "round": game.round_num,
    })
    if game.phase == "voting":
        await room.broadcast({
            "type": "vote_start",
            "round": game.round_num,
            "alive_players": [
                {"uid": p, "username": room.players[p].get("username", p)}
                for p in game.alive_players
            ],
        })
    else:
        await room.broadcast({
            "type": "undercover_state",
            "phase": "describing",
            "round": game.round_num,
            "current_turn": game.get_next_describer(),
            "described_count": len(game.descriptions),
            "alive_count": len(game.alive_players),
        })


async def _broadcast_vote_settled(room, game):
    """投票结算后广播结果（淘汰 / 游戏结束 / 下一轮）。"""
    counts = game.get_vote_counts()
    eliminated = game.eliminated[-1]
    eliminated_name = room.players.get(eliminated, {}).get("username", eliminated)

    await room.broadcast({
        "type": "vote_result",
        "round": game.round_num,
        "vote_counts": {
            room.players.get(t, {}).get("username", t): c
            for t, c in counts.items()
        },
        "eliminated_uid": eliminated,
        "eliminated_name": eliminated_name,
        "eliminated_role": game.get_role(eliminated),
        "eliminated_word": game.get_word(eliminated),
    })

    if game.is_finished:
        undercover_uid = next(
            (u for u, r in game.player_role.items() if r == "undercover"), None
        )
        undercover_name = room.players.get(undercover_uid, {}).get("username", "未知") if undercover_uid else "未知"
        await room.broadcast({
            "type": "game_over",
            "content": f"游戏结束！{'卧底被淘汰，平民获胜！' if game.winner == 'civilian' else '卧底存活到最后，卧底获胜！'}",
            "winner": game.winner,
            "undercover_uid": undercover_uid,
            "undercover_name": undercover_name,
            "undercover_word": game.get_word(undercover_uid) if undercover_uid else "",
            "civilian_word": game.word_pair["civilian"],
            "eliminated": game.eliminated,
            "timestamp": datetime.now().isoformat(),
        })
    else:
        game.start_describing()
        await room.broadcast({
            "type": "undercover_state",
            "phase": "describing",
            "round": game.round_num,
            "turn_order": game.turn_order,
            "current_turn": game.get_next_describer(),
            "alive_count": len(game.alive_players),
        })


# ==================== AI 自动行动 ====================

async def auto_play_ai_descriptions(room, game, room_id: str):
    """自动处理所有待描述的AI玩家（串行，一个接一个）。"""
    while game.phase == "describing":
        next_uid = game.get_next_describer()
        if not next_uid or not game.is_ai(next_uid):
            break

        ai_name = room.players.get(next_uid, {}).get("username", next_uid)

        # 收集本轮其他人已描述的内容
        others = []
        for d_uid, desc in game.descriptions.items():
            speaker = room.players.get(d_uid, {}).get("username", d_uid)
            others.append({"speaker": speaker, "description": desc})

        # AI生成描述
        desc = await AIThinker.think_describe(
            game_id=room_id,
            role_id=next_uid,
            word=game.get_word(next_uid),
            role=game.get_role(next_uid),
            forbidden=game.get_forbidden(next_uid),
            round_num=game.round_num,
            others_descriptions=others,
        )

        game.describe(next_uid, desc)

        # 更新其他AI的记忆
        for ai_uid in game.ai_players:
            if ai_uid != next_uid and ai_uid in game.alive_players:
                AIThinker.record_heard(game_id=room_id, role_id=ai_uid,
                                       round_num=game.round_num, speaker=ai_name, description=desc)

        # 广播AI描述
        await room.broadcast({
            "type": "player_described",
            "uid": next_uid,
            "username": ai_name,
            "nickname": ai_name,
            "description": desc,
            "has_violation": False,
            "round": game.round_num,
            "is_ai": True,
        })

        # 描述完毕，进入投票
        if game.phase == "voting":
            await room.broadcast({
                "type": "vote_start",
                "round": game.round_num,
                "alive_players": [
                    {"uid": p, "username": room.players[p].get("username", p)}
                    for p in game.alive_players
                ],
            })
        else:
            await room.broadcast({
                "type": "undercover_state",
                "phase": "describing",
                "round": game.round_num,
                "current_turn": game.get_next_describer(),
                "described_count": len(game.descriptions),
                "alive_count": len(game.alive_players),
            })


async def auto_play_ai_votes(room, game, room_id: str):
    """自动处理所有待投票的AI玩家。"""
    while game.phase == "voting":
        ai_to_vote = [
            uid for uid in game.alive_players
            if game.is_ai(uid) and uid not in game.votes
        ]
        if not ai_to_vote:
            break

        ai_uid = ai_to_vote[0]
        ai_name = room.players.get(ai_uid, {}).get("username", ai_uid)

        # 收集本轮描述
        descriptions = []
        for d_uid, desc in game.descriptions.items():
            speaker = room.players.get(d_uid, {}).get("username", d_uid)
            descriptions.append({"speaker": speaker, "description": desc})

        alive_info = [
            {"uid": uid, "display_name": room.players.get(uid, {}).get("username", uid)}
            for uid in game.alive_players
        ]

        target = await AIThinker.think_vote(
            game_id=room_id,
            role_id=ai_uid,
            word=game.get_word(ai_uid),
            role=game.get_role(ai_uid),
            round_num=game.round_num,
            alive_players=alive_info,
            descriptions=descriptions,
        )

        game.vote(ai_uid, target)
        target_name = room.players.get(target, {}).get("username", target)

        # 广播投票
        await room.broadcast({
            "type": "player_voted",
            "voter_uid": ai_uid,
            "voter_name": ai_name,
            "target_uid": target,
            "target_name": target_name,
            "round": game.round_num,
            "is_ai": True,
        })

    # 投票结束 → 结算
    if game.phase != "voting":
        await _broadcast_vote_settled(room, game)


# ==================== 端点 ====================

@router.post("/add-ai")
async def add_ai_players(
    data: AddAIReq,
    current_user: User = Depends(get_current_user),
):
    """添加AI玩家到房间（仅房主，WAITING状态）。"""
    room = runtime.get_room(data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.game_type != "undercover":
        raise HTTPException(status_code=400, detail="当前房间不是谁是卧底游戏")
    if room.host_uid != current_user.uid:
        raise HTTPException(status_code=403, detail="仅房主可操作")
    if room.sm.state.name != "WAITING":
        raise HTTPException(status_code=400, detail=f"房间状态 ({room.sm.value}) 不允许添加AI")

    existing_ai = getattr(room, 'ai_player_uids', set())
    existing_count = len(existing_ai)
    human_count = len(room.players) - existing_count
    total_after = human_count + existing_count + data.count
    if total_after > 10:
        raise HTTPException(status_code=400, detail=f"总玩家数不能超过10人（当前{len(room.players)}人）")

    # 生成AI uid
    added = []
    for i in range(data.count):
        idx = existing_count + i + 1
        ai_uid = f"ai_{idx}"
        ai_name = f"AI-{idx}"
        room.players[ai_uid] = {
            "uid": ai_uid,
            "username": ai_name,
            "nickname": ai_name,
            "joined_at": datetime.now().isoformat(),
            "is_ai": True,
        }
        existing_ai.add(ai_uid)
        added.append({"uid": ai_uid, "username": ai_name})

    room.ai_player_uids = existing_ai

    # 广播加入
    for ai in added:
        await room.broadcast({
            "type": "system",
            "content": f"{ai['username']} 加入了房间（AI玩家）",
            "timestamp": datetime.now().isoformat(),
        })

    return {
        "success": True,
        "added": added,
        "total_ai": len(existing_ai),
        "total_players": len(room.players),
    }


@router.post("/start")
async def start_game(
    data: StartGameReq,
    current_user: User = Depends(get_current_user),
):
    """房主开始谁是卧底 — 分配词语，进入描述阶段。"""
    room = runtime.get_room(data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.game_type != "undercover":
        raise HTTPException(status_code=400, detail="当前房间不是谁是卧底游戏")
    if room.host_uid != current_user.uid:
        raise HTTPException(status_code=403, detail="仅房主可开始")
    if room.sm.value != "running":
        raise HTTPException(status_code=400, detail=f"房间状态 ({room.sm.value}) 无法开始")

    uids = list(room.players.keys())
    if len(uids) < 3:
        raise HTTPException(status_code=400, detail=f"至少需要3名玩家，当前{len(uids)}人")

    ai_uids = getattr(room, 'ai_player_uids', set())
    game = UndercoverGame(uids, ai_players=ai_uids)
    room.undercover_game = game
    game.start_describing()

    await _broadcast_game_start(room, game)

    return {
        "success": True,
        "room_id": room.room_id,
        "round": game.round_num,
        "phase": game.phase,
        "your_word": game.get_word(current_user.uid),
        "your_role": game.get_role(current_user.uid),
        "turn_order": game.turn_order,
        "alive_count": len(game.alive_players),
    }


@router.post("/describe")
async def describe(
    data: DescribeReq,
    current_user: User = Depends(get_current_user),
):
    """提交描述（自动检测敏感词）。"""
    room, game = _get_room_and_game(data.room_id)

    if current_user.uid not in room.players:
        raise HTTPException(status_code=403, detail="你不在该房间中")
    if game.phase != "describing":
        raise HTTPException(status_code=400, detail="当前不在描述阶段")
    if game.get_next_describer() != current_user.uid:
        raise HTTPException(status_code=400, detail="还没轮到你描述")

    # 敏感词检测
    filtered, is_violation = game.check_sensitive(current_user.uid, data.description)
    game.describe(current_user.uid, filtered)

    username = current_user.nickname or current_user.username

    # 更新AI记忆
    for ai_uid in game.ai_players:
        if ai_uid in game.alive_players:
            AIThinker.record_heard(
                game_id=data.room_id, role_id=ai_uid,
                round_num=game.round_num, speaker=username, description=filtered,
            )

    await _broadcast_described(
        room, game, current_user.uid, current_user.username, username,
        filtered, is_violation,
    )

    # 自动触发AI描述
    await auto_play_ai_descriptions(room, game, data.room_id)

    return {
        "success": True,
        "round": game.round_num,
        "phase": game.phase,
        "description": filtered,
        "has_violation": is_violation,
        "violation_warning": "你的描述包含敏感词，已自动过滤" if is_violation else None,
        "next_turn": game.get_next_describer(),
    }


@router.post("/vote")
async def vote(
    data: VoteReq,
    current_user: User = Depends(get_current_user),
):
    """投票淘汰。"""
    room, game = _get_room_and_game(data.room_id)

    if current_user.uid not in room.players:
        raise HTTPException(status_code=403, detail="你不在该房间中")
    if game.phase != "voting":
        raise HTTPException(status_code=400, detail="当前不在投票阶段")
    if data.target_uid not in game.alive_players:
        raise HTTPException(status_code=400, detail="投票目标无效")

    if not game.vote(current_user.uid, data.target_uid):
        raise HTTPException(status_code=400, detail="投票失败（可能已投票）")

    # 广播投票动作
    username = current_user.nickname or current_user.username
    target_name = room.players.get(data.target_uid, {}).get("username", data.target_uid)
    await room.broadcast({
        "type": "player_voted",
        "voter_uid": current_user.uid,
        "voter_name": username,
        "target_uid": data.target_uid,
        "target_name": target_name,
        "round": game.round_num,
    })

    # 自动触发AI投票
    await auto_play_ai_votes(room, game, data.room_id)

    result = {
        "success": True,
        "round": game.round_num,
        "votes_so_far": len(game.votes),
        "total_needed": len(game.alive_players),
    }

    # 投票结束 → 结算（auto_play_ai_votes 内部已处理）
    if game.phase != "voting":
        result["phase"] = game.phase
        result["eliminated"] = game.eliminated[-1] if game.eliminated else None
        result["is_finished"] = game.is_finished
        result["winner"] = game.winner

    return result


@router.get("/status/{room_id}")
async def game_status(
    room_id: str,
    current_user: User = Depends(get_current_user),
):
    """查看当前谁是卧底游戏状态（个人视角）。"""
    room, game = _get_room_and_game(room_id)

    if current_user.uid not in room.players:
        raise HTTPException(status_code=403, detail="你不在该房间中")

    return {
        "room_id": room_id,
        "state": room.sm.value,
        "game": game.get_game_info(current_user.uid),
        "players": [
            {
                "uid": uid,
                "username": info.get("username", uid),
                "nickname": info.get("nickname", ""),
                "is_eliminated": uid in game.eliminated,
            }
            for uid, info in room.players.items()
        ],
    }


@router.get("/rules")
async def rules():
    """谁是卧底游戏规则。"""
    return {
        "rules": (
            "## 谁是卧底规则\n"
            "1. 系统给每位玩家分配一个词语，大部分玩家拿到相同的「平民词」，"
            "1名玩家拿到相近但不同的「卧底词」\n"
            "2. 轮流用一句话描述自己的词语，但不能说出词语本身\n"
            "3. 描述完毕后所有人投票，选出你认为的卧底\n"
            "4. 得票最多的玩家被淘汰并公布身份\n"
            "5. 卧底被全部淘汰 → 平民获胜；卧底存活到最后 → 卧底获胜"
        ),
        "tips": [
            "描述要含糊但有指向性，避免暴露自己的词",
            "注意观察其他玩家的描述是否和你的词有出入",
            "卧底要尽量模仿平民的描述方向",
        ],
        "player_range": "3-10人",
        "sensitive_word_rule": "描述和聊天中不能出现自己的词语（含谐音和拆字），系统会自动过滤",
    }
