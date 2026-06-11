"""Persistent world state and message bus."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import Agent, Message, now_iso


@dataclass
class WorldState:
    """Serializable state for agents, messages, files, logs, and runtime settings."""

    agents: Dict[str, Agent] = field(default_factory=dict)
    messages: Dict[str, Message] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    selected_model: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_api_key: str = ""
    ollama_executable_path: str = ""
    engine_running: bool = False
    tick_count: int = 0
    project_files: Dict[str, str] = field(default_factory=dict)

    def add_log(self, line: str) -> None:
        self.logs.append(f"[{now_iso()}] {line}")
        if len(self.logs) > 1000:
            del self.logs[:-1000]

    def add_agent(self, name: str, role: str, system_prompt: str) -> Agent:
        agent = Agent(name=name.strip() or "Агент", role=role.strip() or "Ассистент", system_prompt=system_prompt.strip())
        self.agents[agent.id] = agent
        self.add_log(f"Создан агент {agent.name} ({agent.id})")
        return agent

    def update_agent(self, agent_id: str, name: str, role: str, system_prompt: str) -> None:
        agent = self.agents[agent_id]
        agent.name = name.strip() or agent.name
        agent.role = role.strip() or agent.role
        agent.system_prompt = system_prompt.strip() or agent.system_prompt
        self.add_log(f"Обновлён агент {agent.name} ({agent.id})")

    def delete_agent(self, agent_id: str) -> None:
        agent = self.agents.pop(agent_id, None)
        if agent:
            self.add_log(f"Удалён агент {agent.name} ({agent.id})")

    def send_message(self, sender: str, recipient: str, content: str, message_type: str = "direct") -> Message:
        if recipient == "broadcast":
            message_type = "broadcast"
        message = Message(sender=sender, recipient=recipient, message_type=message_type, content=content)
        self.messages[message.id] = message
        if sender in self.agents:
            self.agents[sender].outgoing_message_ids.append(message.id)
        recipients: Iterable[str]
        if recipient == "broadcast":
            recipients = [agent_id for agent_id in self.agents if agent_id != sender]
        else:
            recipients = [recipient]
        for agent_id in recipients:
            if agent_id in self.agents:
                self.agents[agent_id].incoming_message_ids.append(message.id)
        self.add_log(f"Сообщение {message.message_type}: {sender} -> {recipient}: {content[:160]}")
        return message

    def get_agent_inbox(self, agent_id: str) -> List[Message]:
        agent = self.agents[agent_id]
        return [self.messages[mid] for mid in agent.incoming_message_ids if mid in self.messages]

    def clear_agent_inbox(self, agent_id: str) -> None:
        if agent_id in self.agents:
            self.agents[agent_id].incoming_message_ids.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agents": {key: agent.to_dict() for key, agent in self.agents.items()},
            "messages": {key: message.to_dict() for key, message in self.messages.items()},
            "logs": self.logs,
            "selected_model": self.selected_model,
            "ollama_base_url": self.ollama_base_url,
            "ollama_api_key": self.ollama_api_key,
            "ollama_executable_path": self.ollama_executable_path,
            "engine_running": self.engine_running,
            "tick_count": self.tick_count,
            "project_files": self.project_files,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldState":
        return cls(
            agents={key: Agent.from_dict(value) for key, value in data.get("agents", {}).items()},
            messages={key: Message.from_dict(value) for key, value in data.get("messages", {}).items()},
            logs=data.get("logs", []),
            selected_model=data.get("selected_model", ""),
            ollama_base_url=data.get("ollama_base_url", "http://127.0.0.1:11434"),
            ollama_api_key=data.get("ollama_api_key", ""),
            ollama_executable_path=data.get("ollama_executable_path", ""),
            engine_running=False,
            tick_count=data.get("tick_count", 0),
            project_files=data.get("project_files", {}),
        )


class WorldStore:
    """Load and save the world state as local JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> WorldState:
        if not self.path.exists():
            world = WorldState()
            world.add_agent(
                "Координатор",
                "Планирует взаимодействие агентов",
                "Ты координируешь локальный многоагентный мир. Отвечай только строгим JSON.",
            )
            world.add_agent(
                "Исследователь",
                "Анализирует входящие задачи и сообщает результаты",
                "Ты исследуешь задачи внутри симуляции. Отвечай только строгим JSON.",
            )
            world.add_log("Создано новое состояние мира")
            return world
        try:
            return WorldState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except Exception as exc:  # defensive persistence recovery
            backup = self.path.with_suffix(".corrupt.json")
            self.path.replace(backup)
            world = WorldState()
            world.add_log(f"Не удалось загрузить состояние; повреждённый файл перенесён в {backup.name}: {exc}")
            return world

    def save(self, world: WorldState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(world.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
