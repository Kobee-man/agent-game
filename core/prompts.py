"""海龟汤游戏 Prompt 模板 — 纯函数，无副作用，可单独测试。"""


def build_puzzle_prompt(difficulty: str) -> tuple[str, str]:
    system = (
        "你是一个专业的海龟汤出题专家。\n"
        "先在<thinking>标签中构思谜题设计，然后用```json包裹输出JSON。\n"
        "JSON之外不要输出任何其他内容。"
    )
    prompt = f"""请生成一个{difficulty}难度的海龟汤谜题。

要求：
1. 情境(situation)：令人困惑但有合理解释的场景，2-4句话
2. 真相(truth)：完整的、逻辑自洽的解释，包含所有关键转折
3. 提示(hints)：3个递进式提示，从模糊到具体
4. 分类(category)：谜题的主题分类

<thinking>
在此构思：人物、事件、转折点、隐藏信息
</thinking>

```json
{{
    "title": "谜题标题",
    "situation": "情境描述",
    "truth": "完整真相",
    "hints": ["提示1", "提示2", "提示3"],
    "category": "分类"
}}
```"""
    return prompt, system


def build_question_judge_prompt(
    question: str, situation: str, truth: str, history: list[str] | None = None
) -> tuple[str, str]:
    recent = history[-5:] if history else []
    history_text = "\n".join(f"- {q}" for q in recent) if recent else "无"

    system = ""
    prompt = f"""# 海龟汤裁判

## 规则
- 只能回答"是"、"否"或"无关"
- 基于真相进行事实性判断
- 保持与历史回答一致

## 情境
{situation}

## 真相
{truth}

## 历史问题
{history_text}

## 玩家问题
{question}

## 输出（严格JSON，不要其他内容）
```json
{{
    "is_relevant": true/false,
    "answer": "是"/"否"/"无关",
    "reason": "判断依据（15-30字）",
    "confidence": 0.7-1.0
}}
```"""
    return prompt, system


def build_answer_check_prompt(answer: str, situation: str, truth: str) -> tuple[str, str]:
    system = ""
    prompt = f"""# 海龟汤答案裁判

评估玩家的推理是否正确揭示了真相。

## 评估维度
1. 核心要素覆盖率（40%）：人物、事件、原因、结果
2. 逻辑连贯性（30%）：因果关系、无矛盾
3. 表述精确度（20%）：关键事实准确
4. 完整性（10%）：无重大遗漏

## 情境
{situation}

## 正确真相
{truth}

## 玩家答案
{answer}

## 判定阈值
- accuracy >= 0.85 → 正确
- accuracy >= 0.70 → 基本正确（允许小瑕疵）
- accuracy < 0.70 → 需继续推理

## 输出（严格JSON）
```json
{{
    "is_correct": true/false,
    "accuracy": 0.0-1.0,
    "matched_facts": ["事实1"],
    "missing_facts": ["缺失1"],
    "feedback": "反馈（50-150字）"
}}
```"""
    return prompt, system
