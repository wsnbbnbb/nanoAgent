"""
用户交互工具 - AskUser, Confirm

支持向用户提问和确认操作
"""

import json
from typing import Any, Dict, List, Optional


class UserQuestion:
    """
    用户问题 - 用于向用户请求额外信息

    当 Agent 需要更多信息时会创建此类
    """

    def __init__(
        self,
        question_id: str,
        question: str,
        options: Optional[List[str]] = None,
        default: Optional[str] = None,
        timeout: int = 300,
    ):
        self.question_id = question_id
        self.question = question
        self.options = options
        self.default = default
        self.timeout = timeout
        self.answered = False
        self.answer: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "user_question",
            "question_id": self.question_id,
            "question": self.question,
            "options": self.options,
            "default": self.default,
            "timeout": self.timeout,
        }

    def answer_with(self, answer: str) -> None:
        """设置答案"""
        self.answer = answer
        self.answered = True


_question_store: Dict[str, UserQuestion] = {}


def ask_user(
    question: str,
    question_id: Optional[str] = None,
    options: Optional[List[str]] = None,
    default: Optional[str] = None,
) -> str:
    """
    向用户提问

    Args:
        question: 问题内容
        question_id: 问题 ID（用于后续匹配答案）
        options: 选项列表
        default: 默认答案

    Returns:
        问题 JSON
    """
    if question_id is None:
        question_id = f"q_{len(_question_store)}"

    q = UserQuestion(
        question_id=question_id,
        question=question,
        options=options,
        default=default,
    )
    _question_store[question_id] = q

    return json.dumps(q.to_dict(), ensure_ascii=False)


def confirm(action: str, reason: str = "") -> str:
    """
    请求用户确认操作

    Args:
        action: 操作描述
        reason: 操作原因

    Returns:
        确认请求 JSON
    """
    question = f"确认执行: {action}"
    if reason:
        question += f"\n原因: {reason}"

    return ask_user(
        question=question,
        question_id=f"confirm_{action[:20]}",
        options=["yes", "no"],
        default="no",
    )


def get_answer(question_id: str) -> Optional[str]:
    """
    获取用户对某个问题的回答

    Args:
        question_id: 问题 ID

    Returns:
        用户答案或 None
    """
    if question_id in _question_store:
        q = _question_store[question_id]
        if q.answered:
            return q.answer
    return None


def is_answered(question_id: str) -> bool:
    """检查问题是否已回答"""
    return question_id in _question_store and _question_store[question_id].answered


def clear_question(question_id: str) -> bool:
    """清除问题"""
    if question_id in _question_store:
        del _question_store[question_id]
        return True
    return False


def list_pending_questions() -> List[Dict[str, Any]]:
    """列出待回答的问题"""
    return [
        q.to_dict()
        for q in _question_store.values()
        if not q.answered
    ]
