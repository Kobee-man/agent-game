"""谁是卧底 — 游戏逻辑、词库、敏感词过滤。

核心流程:
  assign_words → describing → voting → elimination → (循环或结束)
  平民词 vs 卧底词，投票淘汰得票最多的人。
"""

import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ==================== 词库 ====================

WORD_PAIRS = [
    {"civilian": "洗发水", "undercover": "沐浴露", "category": "日用品"},
    {"civilian": "面包", "undercover": "包子", "category": "食物"},
    {"civilian": "手机", "undercover": "电脑", "category": "电子产品"},
    {"civilian": "牛奶", "undercover": "豆浆", "category": "饮品"},
    {"civilian": "电梯", "undercover": "楼梯", "category": "建筑"},
    {"civilian": "眼镜", "undercover": "墨镜", "category": "日用品"},
    {"civilian": "键盘", "undercover": "鼠标", "category": "电子产品"},
    {"civilian": "饺子", "undercover": "馄饨", "category": "食物"},
    {"civilian": "火车", "undercover": "地铁", "category": "交通"},
    {"civilian": "枕头", "undercover": "抱枕", "category": "日用品"},
    {"civilian": "火锅", "undercover": "烧烤", "category": "食物"},
    {"civilian": "吉他", "undercover": "尤克里里", "category": "乐器"},
    {"civilian": "雨伞", "undercover": "雨衣", "category": "日用品"},
    {"civilian": "薯片", "undercover": "饼干", "category": "零食"},
    {"civilian": "班主任", "undercover": "教导主任", "category": "学校"},
    {"civilian": "快递", "undercover": "外卖", "category": "服务"},
    {"civilian": "口红", "undercover": "唇膏", "category": "化妆品"},
    {"civilian": "公园", "undercover": "广场", "category": "场所"},
    {"civilian": "豆浆", "undercover": "豆腐脑", "category": "食物"},
    {"civilian": "气球", "undercover": "泡泡", "category": "玩具"},
    {"civilian": "汉堡", "undercover": "三明治", "category": "食物"},
    {"civilian": "游泳", "undercover": "潜水", "category": "运动"},
    {"civilian": "红包", "undercover": "转账", "category": "社交"},
    {"civilian": "电影", "undercover": "电视剧", "category": "娱乐"},
    {"civilian": "空调", "undercover": "风扇", "category": "电器"},
    {"civilian": "牙刷", "undercover": "牙线", "category": "日用品"},
    {"civilian": "筷子", "undercover": "勺子", "category": "餐具"},
    {"civilian": "蜜蜂", "undercover": "蝴蝶", "category": "动物"},
    {"civilian": "闹钟", "undercover": "日历", "category": "工具"},
    {"civilian": "奶茶", "undercover": "咖啡", "category": "饮品"},
    {"civilian": "微信", "undercover": "QQ", "category": "社交"},
    {"civilian": "铅笔", "undercover": "钢笔", "category": "文具"},
    {"civilian": "西瓜", "undercover": "哈密瓜", "category": "水果"},
    {"civilian": "篮球", "undercover": "足球", "category": "运动"},
    {"civilian": "月饼", "undercover": "汤圆", "category": "食物"},
    {"civilian": "出租车", "undercover": "网约车", "category": "交通"},
    {"civilian": "超市", "undercover": "便利店", "category": "场所"},
    {"civilian": "相机", "undercover": "摄像机", "category": "电子产品"},
    {"civilian": "烤鸭", "undercover": "烧鸡", "category": "食物"},
    {"civilian": "被子", "undercover": "毯子", "category": "日用品"},
    {"civilian": "蛋糕", "undercover": "面包", "category": "食物"},
    {"civilian": "蜡烛", "undercover": "灯笼", "category": "照明"},
    {"civilian": "围巾", "undercover": "围脖", "category": "服饰"},
    {"civilian": "狮子", "undercover": "老虎", "category": "动物"},
    {"civilian": "葡萄", "undercover": "蓝莓", "category": "水果"},
    {"civilian": "汤勺", "undercover": "锅铲", "category": "厨具"},
    {"civilian": "雪碧", "undercover": "可乐", "category": "饮品"},
    {"civilian": "白菜", "undercover": "生菜", "category": "蔬菜"},
    {"civilian": "坦克", "undercover": "装甲车", "category": "军事"},
    {"civilian": "手套", "undercover": "袜子", "category": "服饰"},
]

# 常见谐音字/拆字映射（敏感词扩展检测）
_HOMOPHONE_MAP: dict[str, list[str]] = {
    "洗发水": ["喜发水", "西发水"],
    "沐浴露": ["木鱼露", "目玉露"],
    "面包": ["面胞", "面保"],
    "包子": ["包紫", "包仔"],
    "牛奶": ["牛来", "流奶"],
    "豆浆": ["豆将", "斗浆"],
    "手机": ["守机", "手鸡"],
    "电脑": ["电恼", "点脑"],
    "火锅": ["火祸", "祸锅"],
    "烧烤": ["少考", "烧靠"],
    "快递": ["快弟", "块递"],
    "外卖": ["外买", "歪卖"],
    "电影": ["电应", "殿影"],
    "电视剧": ["电视句", "点是剧"],
    "微信": ["危信", "为信"],
    "QQ": ["扣扣", "秋秋"],
    "奶茶": ["乃茶", "奶查"],
    "咖啡": ["咖非", "卡飞"],
    "西瓜": ["西刮", "习瓜"],
    "哈密瓜": ["哈蜜瓜", "哈密刮"],
    "篮球": ["蓝球", "拦球"],
    "足球": ["足囚", "族球"],
    "微信": ["危信", "为信"],
}

# 单字拆分检测（多字词会拆成单字，这些单字也应被过滤）
_SPLIT_DETECTION: dict[str, list[str]] = {}


def get_random_pair() -> dict:
    return random.choice(WORD_PAIRS).copy()


# ==================== 敏感词过滤 ====================

def build_forbidden_set(word: str) -> set[str]:
    """构建该词的禁止词集合（含谐音、拆字）。"""
    forbidden: set[str] = set()
    # 原词
    forbidden.add(word)
    # 多字词：每个单字也禁止（防拆字规避）
    if len(word) > 1:
        for ch in word:
            forbidden.add(ch)
    # 谐音
    for hom in _HOMOPHONE_MAP.get(word, []):
        forbidden.add(hom)
    return forbidden


def filter_message(message: str, forbidden: set[str]) -> tuple[str, bool]:
    """过滤消息中的敏感词。

    Returns:
        (filtered_message, has_violation)
    """
    filtered = message
    violation = False
    # 按长度降序，先替换长的防止部分替换导致残留
    for word in sorted(forbidden, key=len, reverse=True):
        if word in filtered:
            filtered = filtered.replace(word, "*" * len(word))
            violation = True
    return filtered, violation


# ==================== 游戏引擎 ====================

class UndercoverGame:
    """谁是卧底游戏实例，每个房间持有一个。"""

    def __init__(self, player_uids: list[str], word_pair: Optional[dict] = None,
                 ai_players: Optional[set[str]] = None):
        self.word_pair = word_pair or get_random_pair()
        self.player_words: dict[str, str] = {}          # uid → word
        self.player_role: dict[str, str] = {}           # uid → "civilian" | "undercover"
        self.forbidden_sets: dict[str, set[str]] = {}   # uid → forbidden words
        self.ai_players: set[str] = ai_players or set() # AI玩家uid集合
        self.descriptions: dict[str, str] = {}          # uid → description (本轮)
        self.votes: dict[str, str] = {}                 # uid → voted_uid (本轮)
        self.eliminated: list[str] = []                 # 已淘汰 uid 顺序
        self.round_num: int = 0
        self.phase: str = "waiting"  # waiting → describing → voting → (循环)
        self.turn_order: list[str] = []                 # 描述顺序
        self.current_turn: int = 0                      # 当前描述者索引
        self.is_finished: bool = False
        self.winner: Optional[str] = None               # "civilian" | "undercover"
        self._assign_words(player_uids)

    def _assign_words(self, uids: list[str]):
        """分配角色和词语：1名卧底，其余平民。"""
        if len(uids) < 3:
            raise ValueError("至少需要3名玩家")

        undercover_uid = random.choice(uids)
        for uid in uids:
            if uid == undercover_uid:
                self.player_words[uid] = self.word_pair["undercover"]
                self.player_role[uid] = "undercover"
            else:
                self.player_words[uid] = self.word_pair["civilian"]
                self.player_role[uid] = "civilian"
            self.forbidden_sets[uid] = build_forbidden_set(self.player_words[uid])

    # ---- 阶段控制 ----

    def start_describing(self):
        """开始新一轮描述。"""
        if self.is_finished:
            return
        self.round_num += 1
        self.phase = "describing"
        self.descriptions.clear()
        self.votes.clear()
        self.current_turn = 0
        # 未淘汰的玩家随机顺序
        alive = self.alive_players
        random.shuffle(alive)
        self.turn_order = alive

    def describe(self, uid: str, description: str) -> bool:
        """玩家提交描述。"""
        if self.phase != "describing" or uid not in self.alive_players:
            return False
        if uid in self.descriptions:
            return False
        self.descriptions[uid] = description
        # 前进到下一个未描述的玩家
        self._advance_turn()
        # 所有人都描述完毕 → 进入投票
        if len(self.descriptions) >= len(self.alive_players):
            self.phase = "voting"
        return True

    def _advance_turn(self):
        """推进到下一个需要描述的玩家。"""
        while self.current_turn < len(self.turn_order):
            uid = self.turn_order[self.current_turn]
            if uid not in self.descriptions:
                return
            self.current_turn += 1

    def vote(self, voter_uid: str, target_uid: str) -> bool:
        """投票。"""
        if self.phase != "voting":
            return False
        if voter_uid not in self.alive_players or target_uid not in self.alive_players:
            return False
        self.votes[voter_uid] = target_uid
        # 所有存活玩家都投票了 → 结算
        if len(self.votes) >= len(self.alive_players):
            return self._resolve_votes()
        return True

    def _resolve_votes(self) -> bool:
        """结算投票，淘汰得票最多的人。"""
        counts: dict[str, int] = {}
        for target in self.votes.values():
            counts[target] = counts.get(target, 0) + 1

        max_votes = max(counts.values())
        # 得票最多的人可能并列
        candidates = [uid for uid, c in counts.items() if c == max_votes]

        eliminated: Optional[str] = None
        if len(candidates) == 1:
            eliminated = candidates[0]
        else:
            # 并列：随机选一个淘汰
            eliminated = random.choice(candidates)

        self.eliminated.append(eliminated)

        # 检查游戏是否结束
        alive = self.alive_players
        undercover_alive = sum(
            1 for uid in alive if self.player_role.get(uid) == "undercover"
        )

        if undercover_alive == 0:
            self.is_finished = True
            self.winner = "civilian"
            self.phase = "finished"
        elif len(alive) <= 2:
            self.is_finished = True
            self.winner = "undercover"
            self.phase = "finished"

        return True

    # ---- 查询 ----

    @property
    def alive_players(self) -> list[str]:
        return [uid for uid in self.player_words if uid not in self.eliminated]

    def get_vote_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for target in self.votes.values():
            counts[target] = counts.get(target, 0) + 1
        return counts

    def get_word(self, uid: str) -> Optional[str]:
        return self.player_words.get(uid)

    def get_role(self, uid: str) -> Optional[str]:
        return self.player_role.get(uid)

    def get_forbidden(self, uid: str) -> set[str]:
        return self.forbidden_sets.get(uid, set())

    def check_sensitive(self, uid: str, message: str) -> tuple[str, bool]:
        """检查消息是否包含敏感词。"""
        forbidden = self.get_forbidden(uid)
        if not forbidden:
            return message, False
        return filter_message(message, forbidden)

    def is_ai(self, uid: str) -> bool:
        return uid in self.ai_players

    def get_next_describer(self) -> Optional[str]:
        """获取下一个需要描述的玩家uid。"""
        if self.phase != "describing":
            return None
        for uid in self.turn_order:
            if uid not in self.descriptions:
                return uid
        return None

    def get_game_info(self, for_uid: str) -> dict:
        """获取该玩家视角的游戏状态。"""
        return {
            "round": self.round_num,
            "phase": self.phase,
            "your_word": self.get_word(for_uid),
            "your_role": self.get_role(for_uid),
            "alive_count": len(self.alive_players),
            "total_players": len(self.player_words),
            "eliminated": [
                {
                    "uid": uid,
                    "role": self.get_role(uid),
                    "word": self.get_word(uid),
                }
                for uid in self.eliminated
            ],
            "descriptions": dict(self.descriptions),
            "vote_counts": self.get_vote_counts(),
            "is_finished": self.is_finished,
            "winner": self.winner,
        }
