import json
import redis
from typing import Optional
from core.config import REDIS_HOST, REDIS_PORT, REDIS_DB, PUZZLE_EXPIRE_SECONDS


class RedisService:
    def __init__(self):
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
            )
        return self._client

    def is_available(self) -> bool:
        try:
            self.client.ping()
            return True
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def set_puzzle(self, game_id: str, puzzle: dict) -> None:
        key = f"turtle_soup:puzzle:{game_id}"
        self.client.set(key, json.dumps(puzzle, ensure_ascii=False), ex=PUZZLE_EXPIRE_SECONDS)

    def get_puzzle(self, game_id: str) -> Optional[dict]:
        raw = self.client.get(f"turtle_soup:puzzle:{game_id}")
        return json.loads(raw) if raw else None

    def delete_puzzle(self, game_id: str) -> None:
        self.client.delete(f"turtle_soup:puzzle:{game_id}")

    def append_history(self, game_id: str, question: str, answer: str, reason: str = "") -> None:
        entry = json.dumps({"q": question, "a": answer, "r": reason}, ensure_ascii=False)
        key = f"turtle_soup:history:{game_id}"
        self.client.rpush(key, entry)
        self.client.expire(key, PUZZLE_EXPIRE_SECONDS)

    def get_history(self, game_id: str, limit: int = 10) -> list:
        raw = self.client.lrange(f"turtle_soup:history:{game_id}", -limit, -1)
        return [json.loads(item) for item in raw]

    def delete_history(self, game_id: str) -> None:
        self.client.delete(f"turtle_soup:history:{game_id}")


redis_service = RedisService()
