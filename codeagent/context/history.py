"""History management - Improved version"""
import time
import json
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class HistoryManager:
    """
    History manager - Improved version
    Features:
    - Round boundary detection
    - Message compression (based on token threshold)
    - Truncation to disk
    """

    def __init__(
        self,
        max_length: int = 100,
        context_window: int = 128000,
        compression_threshold: float = 0.8,
    ):
        self._messages: List[Dict[str, Any]] = []
        self.max_length = max_length
        self.context_window = context_window
        self.compression_threshold = compression_threshold
        self._last_usage_tokens = 0
        self._total_usage_tokens = 0

    def append_user(self, content: str, metadata: Optional[Dict] = None) -> None:
        """Add user message"""
        msg = {
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self._messages.append(msg)

    def append_assistant(
        self,
        content: str,
        metadata: Optional[Dict] = None,
        tool_calls: Optional[List] = None,
    ) -> None:
        """Add assistant message"""
        msg = {
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self._messages.append(msg)

    def append_tool(
        self,
        tool_call_id: str,
        tool_name: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Add tool message"""
        msg = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {"tool_name": tool_name}
        }
        self._messages.append(msg)

    def append_summary(self, content: str) -> None:
        """Add summary message"""
        msg = {
            "role": "system",
            "content": f"[Summary] {content}",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"type": "summary"}
        }
        self._messages.append(msg)

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get all messages"""
        return self._messages.copy()

    def get_messages_for_api(self) -> List[Dict[str, Any]]:
        """Get messages suitable for API"""
        result = []
        for msg in self._messages:
            api_msg = {"role": msg["role"], "content": msg["content"]}
            if msg["role"] == "tool":
                api_msg["tool_call_id"] = msg["tool_call_id"]
            if "tool_calls" in msg:
                api_msg["tool_calls"] = msg["tool_calls"]
            result.append(api_msg)
        return result

    def should_compress(self, current_usage: int) -> bool:
        """Check if compression is needed"""
        if len(self._messages) < 3:
            return False
        estimated_total = self._total_usage_tokens + current_usage
        threshold = self.context_window * self.compression_threshold
        return estimated_total >= threshold

    def compress(
        self,
        summary_generator: Optional[Callable[[List[Dict]], str]] = None,
        retain_rounds: int = 3,
    ) -> str:
        """
        Compress history

        Preserve recent N rounds + generate summary
        """
        if len(self._messages) <= retain_rounds * 3:
            return ""

        preserved = self._messages[-retain_rounds * 3:]
        to_summarize = self._messages[:-retain_rounds * 3]

        summary_content = ""
        if summary_generator and to_summarize:
            summary_content = summary_generator(to_summarize)

        if summary_content:
            self._messages = [{"role": "system", "content": f"[Previous Context Summary]\n{summary_content}"}] + preserved
        else:
            self._messages = preserved

        return summary_content

    def clear(self) -> None:
        """Clear history"""
        self._messages.clear()
        self._total_usage_tokens = 0
        self._last_usage_tokens = 0

    def update_usage(self, tokens: int) -> None:
        """Update token usage"""
        self._last_usage_tokens = tokens
        self._total_usage_tokens += tokens

    def __len__(self) -> int:
        return len(self._messages)
