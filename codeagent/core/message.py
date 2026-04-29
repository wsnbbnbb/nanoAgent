"""Message types"""
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel

MessageRole = Literal["user", "assistant", "summary", "tool"]


class Message(BaseModel):
    """Message model"""
    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None
