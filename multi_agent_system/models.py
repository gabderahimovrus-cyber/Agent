"""Core serializable data models for the multi-agent world."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

MessageType = Literal["direct", "broadcast", "system", "tool", "chat"]
AgentStatus = Literal["idle", "thinking", "error", "disabled"]


def now_iso() -> str:
    """Return a timezone-aware UTC timestamp suitable for persistence."""
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    """Create a short human-readable identifier."""
    return f"{prefix}_{uuid4().hex[:10]}"


@dataclass
class Message:
    """A message transferred through the central message bus."""

    sender: str
    recipient: str
    message_type: MessageType
    content: str
    timestamp: str = field(default_factory=now_iso)
    id: str = field(default_factory=lambda: new_id("msg"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            sender=data.get("sender", "system"),
            recipient=data.get("recipient", "broadcast"),
            message_type=data.get("message_type", "direct"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", now_iso()),
            id=data.get("id", new_id("msg")),
        )


@dataclass
class Agent:
    """A logical autonomous agent in the simulated world."""

    name: str
    role: str
    system_prompt: str
    id: str = field(default_factory=lambda: new_id("agent"))
    short_term_memory: List[Dict[str, Any]] = field(default_factory=list)
    long_term_memory: List[str] = field(default_factory=list)
    incoming_message_ids: List[str] = field(default_factory=list)
    outgoing_message_ids: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=lambda: [
        "read_file",
        "write_file",
        "create_file",
        "send_message",
        "remember",
    ])
    status: AgentStatus = "idle"
    enabled: bool = True

    def remember_short(self, event: Dict[str, Any], limit: int = 20) -> None:
        self.short_term_memory.append(event)
        if len(self.short_term_memory) > limit:
            del self.short_term_memory[:-limit]

    def remember_long(self, event: str, limit: int = 200) -> None:
        self.long_term_memory.append(event)
        if len(self.long_term_memory) > limit:
            del self.long_term_memory[:-limit]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Agent":
        return cls(
            name=data.get("name", "Agent"),
            role=data.get("role", "Assistant"),
            system_prompt=data.get("system_prompt", "You are a helpful local agent."),
            id=data.get("id", new_id("agent")),
            short_term_memory=data.get("short_term_memory", []),
            long_term_memory=data.get("long_term_memory", []),
            incoming_message_ids=data.get("incoming_message_ids", []),
            outgoing_message_ids=data.get("outgoing_message_ids", []),
            tools=data.get("tools") or ["read_file", "write_file", "create_file", "send_message", "remember"],
            status=data.get("status", "idle"),
            enabled=data.get("enabled", True),
        )
