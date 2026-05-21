"""谁是卧底 AI 玩家 — 每个AI有独立记忆（Redis），严格prompt控制发言。

Redis Key: undercover:{game_id}:ai_memory:{role_id}
"""

import json
import logging
from typing import Optional

from core.redis_service import redis_service
from core.llm_service import llm_service, LLMError
from core.undercover import filter_message, build_forbidden_set

logger = logging.getLogger(__name__)

MEMORY_EXPIRE = 7200  # 2小时，与游戏同步


class AIMemory:
    """单个AI玩家的Redis记忆。Key = undercover:{game_id}:ai_memory:{role_id}"""

    def __init__(self, game_id: str, role_id: str):
        self.key = f"undercover:{game_id}:ai_memory:{role_id}"

    def load(self) -> list[dict]:
        raw = redis_service.client.get(self.key)
        return json.loads(raw) if raw else []

    def save(self, entries: list[dict]):
        redis_service.client.set(
            self.key, json.dumps(entries, ensure_ascii=False), ex=MEMORY_EXPIRE
        )

    def append(self, entry: dict):
        entries = self.load()
        entries.append(entry)
        self.save(entries)

    def clear(self):
        redis_service.client.delete(self.key)


# ==================== Prompt 构建 ====================

def _build_describe_prompt(
    word: str,
    role: str,
    forbidden: set[str],
    round_num: int,
    others_descriptions: list[dict],
    memory: list[dict],
) -> tuple[str, str]:
    """构建描述阶段的 system + user prompt。"""
    forbidden_list = "、".join(sorted(forbidden))

    history_lines = []
    for m in memory[-5:]:
        if m.get("type") == "describe":
            history_lines.append(f"第{m['round']}轮 你: {m['description']}")
        elif m.get("type") == "heard":
            history_lines.append(f"第{m['round']}轮 {m['speaker']}: {m['description']}")
    history_text = "\n".join(history_lines) if history_lines else "无"

    others_lines = []
    for d in others_descriptions:
        others_lines.append(f"  {d['speaker']}: {d['description']}")
    others_text = "\n".join(others_lines) if others_lines else "  （本轮你是第一个描述）"

    role_hint = ""
    if role == "undercover":
        role_hint = "你是卧底，你的词和别人的相近但不同。模仿平民的描述方向，但不要暴露你的词。"
    else:
        role_hint = "你是平民，你的词和其他平民一样。描述要帮助同伴识别卧底。"

    system = (
        "你是谁是卧底游戏中的一名玩家。你的任务是用一句话描述你的词语。\n"
        "【绝对禁止】\n"
        "- 不得说出你的词语本身\n"
        f"- 不得使用以下任何字/词/谐音: {forbidden_list}\n"
        "- 不得拆字、注音、用拼音、英文暗示\n"
        "- 不得说「我不能说X」或类似否定式暴露\n"
        "【必须遵守】\n"
        "- 只输出一句10-30字的描述，不加任何前缀/后缀/解释\n"
        "- 描述要含糊但有方向性，不要太明显也不要太离谱\n"
        "- 不要重复别人说过的描述角度"
    )

    prompt = f"""你的词语: {word}
你的身份: {role_hint}

当前: 第{round_num}轮描述阶段

本轮其他人已说:
{others_text}

你之前的记忆:
{history_text}

请用一句话描述你的词语（10-30字）:"""

    return prompt, system


def _build_vote_prompt(
    word: str,
    role: str,
    round_num: int,
    alive_players: list[dict],
    descriptions: list[dict],
    memory: list[dict],
) -> tuple[str, str]:
    """构建投票阶段的 prompt。"""
    players_text = "\n".join(
        f"  {p['uid']}: {p['display_name']}" for p in alive_players
    )
    desc_text = "\n".join(
        f"  {d['speaker']}: {d['description']}" for d in descriptions
    )

    history_lines = []
    for m in memory[-5:]:
        if m.get("type") == "vote":
            history_lines.append(f"第{m['round']}轮 你投了 {m['target_name']}")
        elif m.get("type") == "result":
            history_lines.append(f"第{m['round']}轮 淘汰了 {m['eliminated_name']} ({m['role']})")
    history_text = "\n".join(history_lines) if history_lines else "无"

    role_hint = ""
    if role == "undercover":
        role_hint = "你是卧底，要避免被发现，尽量引导投票投给平民。"
    else:
        role_hint = "你是平民，要找出卧底，投票给描述可疑的人。"

    system = (
        "你是谁是卧底游戏中的一名玩家。你的任务是投票选出你认为的卧底。\n"
        "【必须遵守】\n"
        "- 只输出你要投票的玩家uid，不加任何其他文字\n"
        "- 从存活玩家列表中选择一个uid\n"
        "- 不要输出解释、理由或任何额外文字"
    )

    prompt = f"""你的词语: {word}
你的身份: {role_hint}

当前: 第{round_num}轮投票阶段

存活玩家:
{players_text}

本轮描述:
{desc_text}

历史记忆:
{history_text}

请从存活玩家中选择你要投票的uid（只输出uid）:"""

    return prompt, system


# ==================== AI 行为 ====================

class AIThinker:
    """AI玩家行为决策，基于LLM + Redis记忆。"""

    @staticmethod
    async def think_describe(
        game_id: str,
        role_id: str,
        word: str,
        role: str,
        forbidden: set[str],
        round_num: int,
        others_descriptions: list[dict],
    ) -> str:
        """AI生成描述。返回过滤后的描述文本。"""
        memory = AIMemory(game_id, role_id).load()
        prompt, system = _build_describe_prompt(
            word, role, forbidden, round_num, others_descriptions, memory
        )

        try:
            raw = await llm_service.chat(prompt, system, temperature=0.7, max_tokens=100)
            desc = raw.strip().strip('"').strip("'").strip("。") + "。"
            # 安全截断
            if len(desc) > 60:
                desc = desc[:57] + "..."
        except LLMError as e:
            logger.warning(f"AI描述生成失败 ({role_id}): {e}")
            desc = _fallback_describe(role)

        # 敏感词过滤（AI也应该被过滤，确保安全）
        filtered, _ = filter_message(desc, forbidden)

        # 记忆
        AIMemory(game_id, role_id).append({
            "type": "describe",
            "round": round_num,
            "description": filtered,
        })

        return filtered

    @staticmethod
    async def think_vote(
        game_id: str,
        role_id: str,
        word: str,
        role: str,
        round_num: int,
        alive_players: list[dict],
        descriptions: list[dict],
    ) -> str:
        """AI投票决策。返回目标uid。"""
        memory = AIMemory(game_id, role_id).load()
        prompt, system = _build_vote_prompt(
            word, role, round_num, alive_players, descriptions, memory
        )

        try:
            raw = await llm_service.chat(prompt, system, temperature=0.5, max_tokens=20)
            target = raw.strip()
            # 校验返回的是有效uid
            valid_uids = {p["uid"] for p in alive_players}
            if target not in valid_uids:
                # 尝试从返回中提取uid
                for uid in valid_uids:
                    if uid in target:
                        target = uid
                        break
                else:
                    target = _fallback_vote(role_id, alive_players)
        except LLMError as e:
            logger.warning(f"AI投票决策失败 ({role_id}): {e}")
            target = _fallback_vote(role_id, alive_players)

        # 记忆
        target_name = next(
            (p["display_name"] for p in alive_players if p["uid"] == target), target
        )
        AIMemory(game_id, role_id).append({
            "type": "vote",
            "round": round_num,
            "target": target,
            "target_name": target_name,
        })

        return target

    @staticmethod
    def record_heard(game_id: str, role_id: str, round_num: int, speaker: str, description: str):
        """记录听到的别人描述。"""
        AIMemory(game_id, role_id).append({
            "type": "heard",
            "round": round_num,
            "speaker": speaker,
            "description": description,
        })

    @staticmethod
    def record_vote_result(game_id: str, role_id: str, round_num: int, eliminated_name: str, role: str):
        """记录投票结果。"""
        AIMemory(game_id, role_id).append({
            "type": "result",
            "round": round_num,
            "eliminated_name": eliminated_name,
            "role": role,
        })

    @staticmethod
    def clear_memory(game_id: str, role_id: str):
        AIMemory(game_id, role_id).clear()


# ==================== Fallback ====================

_FALLBACK_DESCRIBE_CIVILIAN = [
    "这个东西很常见，几乎每天都会用到。",
    "生活中离不开它，用起来很舒服。",
    "和卫生有关，让人感觉清爽。",
    "放在那里不起眼，但缺了它会很不方便。",
    "体积不大，但用途很广。",
]

_FALLBACK_DESCRIBE_UNDERCOVER = [
    "这个东西和另一个很像，但还是有区别。",
    "用起来感觉差不多，但细节不同。",
    "经常被搞混，其实不太一样。",
    "功能相似，但使用场景略有不同。",
]


def _fallback_describe(role: str) -> str:
    import random
    pool = _FALLBACK_DESCRIBE_UNDERCOVER if role == "undercover" else _FALLBACK_DESCRIBE_CIVILIAN
    return random.choice(pool)


def _fallback_vote(role_id: str, alive_players: list[dict]) -> str:
    """Fallback: 随机投票（排除自己）。"""
    import random
    others = [p for p in alive_players if p["uid"] != role_id]
    if others:
        return random.choice(others)["uid"]
    return alive_players[0]["uid"]
