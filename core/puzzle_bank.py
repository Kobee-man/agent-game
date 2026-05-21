"""题库管理 — 上限50道，FIFO淘汰，用于LLM降级。"""

import json
import logging
import random
from typing import Optional

from sqlalchemy import func

from core.db import SessionLocal
from models.db_models import PuzzleBank

logger = logging.getLogger(__name__)

MAX_SIZE = 50


class PuzzleBankService:

    @staticmethod
    def add(puzzle: dict) -> Optional[int]:
        """添加题目到题库，超出上限删除最早的，返回新idx。"""
        db = SessionLocal()
        try:
            # FIFO: 删除最旧的直到 < MAX_SIZE
            overflow = db.query(PuzzleBank).order_by(PuzzleBank.created_at).limit(
                max(0, db.query(PuzzleBank).count() - MAX_SIZE + 1)
            ).all()
            for row in overflow:
                db.delete(row)
            db.flush()

            record = PuzzleBank(
                title=puzzle.get("title", "未命名谜题"),
                situation=puzzle["situation"],
                truth=puzzle["truth"],
                category=puzzle.get("category", "未分类"),
                hints=json.dumps(puzzle.get("hints", []), ensure_ascii=False),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(f"题库添加: idx={record.idx}, title={record.title}")
            return record.idx
        except Exception:
            db.rollback()
            logger.exception("题库添加失败")
            return None
        finally:
            db.close()

    @staticmethod
    def get_random() -> Optional[dict]:
        """随机取一道题，返回dict格式（与LLM生成一致）。"""
        db = SessionLocal()
        try:
            record = db.query(PuzzleBank).order_by(func.rand()).first()
            if not record:
                return None
            return {
                "title": record.title,
                "situation": record.situation,
                "truth": record.truth,
                "category": record.category,
                "hints": json.loads(record.hints) if record.hints else [],
            }
        except Exception:
            logger.exception("题库读取失败")
            return None
        finally:
            db.close()

    @staticmethod
    def get_by_idx(idx: int) -> Optional[dict]:
        """按索引取题。"""
        db = SessionLocal()
        try:
            record = db.query(PuzzleBank).filter(PuzzleBank.idx == idx).first()
            if not record:
                return None
            return {
                "title": record.title,
                "situation": record.situation,
                "truth": record.truth,
                "category": record.category,
                "hints": json.loads(record.hints) if record.hints else [],
            }
        except Exception:
            logger.exception("题库读取失败")
            return None
        finally:
            db.close()

    @staticmethod
    def count() -> int:
        db = SessionLocal()
        try:
            return db.query(PuzzleBank).count()
        finally:
            db.close()


puzzle_bank = PuzzleBankService()
