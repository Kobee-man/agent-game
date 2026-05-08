import json
import re
from typing import Optional


def parse_llm_json(text: str) -> Optional[dict]:
    """从LLM响应中提取JSON，多策略降级。"""
    if not text or not text.strip():
        return None

    cleaned = text.strip()

    # 去除 <thinking>...</thinking>
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL)
    # 去除 markdown 代码块
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip())
    # 去除 json/JSON: 前缀
    cleaned = re.sub(r"^\s*(?:json|JSON)\s*:?\s*\n?", "", cleaned)

    # 直接解析
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 括号计数法提取
    block = _extract_brace_block(cleaned)
    if block:
        for attempt in (block, _fix_trailing_commas(block)):
            try:
                data = json.loads(attempt)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue

    return None


def _extract_brace_block(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _fix_trailing_commas(raw: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", raw)
