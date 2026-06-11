"""Tick-based multi-agent simulation engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .ollama_client import OllamaClient
from .tools import ToolExecutor
from .world import WorldState

ACTION_SCHEMA = {
    "thought": "short private reasoning summary",
    "actions": [{"tool": "remember", "args": {"content": "important event"}}],
    "messages": [{"recipient": "agent_id or broadcast", "content": "message"}],
}


class SimulationEngine:
    """Runs the world one safe tick at a time."""

    def __init__(self, world: WorldState, ollama: OllamaClient, workspace: Path) -> None:
        self.world = world
        self.ollama = ollama
        self.tools = ToolExecutor(workspace, world)
        self._cursor = 0

    def tick(self) -> None:
        enabled_agents = [agent for agent in self.world.agents.values() if agent.enabled]
        if not enabled_agents:
            self.world.add_log("Tick skipped: no enabled agents")
            return
        agent = enabled_agents[self._cursor % len(enabled_agents)]
        self._cursor += 1
        self.world.tick_count += 1
        if not self.world.selected_model:
            self.world.add_log("Tick skipped: no Ollama model selected")
            return
        try:
            agent.status = "thinking"
            prompt = self._build_prompt(agent.id)
            raw = self.ollama.generate(self.world.selected_model, prompt)
            parsed = self._parse_response(raw)
            self._apply_response(agent.id, parsed)
            agent.remember_short({"tick": self.world.tick_count, "response": parsed})
            agent.status = "idle"
            self.world.clear_agent_inbox(agent.id)
            self.world.add_log(f"Tick {self.world.tick_count}: {agent.name} completed actions")
        except Exception as exc:
            agent.status = "error"
            self.world.add_log(f"Tick {self.world.tick_count}: {agent.name} failed safely: {exc}")

    def _build_prompt(self, agent_id: str) -> str:
        agent = self.world.agents[agent_id]
        inbox = [message.to_dict() for message in self.world.get_agent_inbox(agent_id)]
        agents = [{"id": item.id, "name": item.name, "role": item.role} for item in self.world.agents.values()]
        return json.dumps(
            {
                "instruction": "Return one strict JSON object matching the schema. Do not include markdown.",
                "schema": ACTION_SCHEMA,
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "system_prompt": agent.system_prompt,
                    "tools": agent.tools,
                    "short_term_memory": agent.short_term_memory[-10:],
                    "long_term_memory": agent.long_term_memory[-20:],
                },
                "world": {"tick": self.world.tick_count, "agents": agents},
                "inbox": inbox,
            },
            ensure_ascii=False,
        )

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("model did not return JSON")
            parsed = json.loads(raw[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("model response must be a JSON object")
        parsed.setdefault("thought", "")
        parsed.setdefault("actions", [])
        parsed.setdefault("messages", [])
        if not isinstance(parsed["actions"], list) or not isinstance(parsed["messages"], list):
            raise ValueError("actions and messages must be lists")
        return parsed

    def _apply_response(self, agent_id: str, parsed: Dict[str, Any]) -> None:
        thought = str(parsed.get("thought", ""))[:500]
        if thought:
            self.world.agents[agent_id].remember_short({"thought": thought})
            self.world.add_log(f"{self.world.agents[agent_id].name} thought: {thought}")
        for message in parsed.get("messages", []):
            if isinstance(message, dict):
                self.world.send_message(agent_id, message.get("recipient", "broadcast"), message.get("content", ""))
        for action in parsed.get("actions", []):
            if isinstance(action, dict):
                try:
                    result = self.tools.execute(agent_id, action)
                    self.world.add_log(f"Tool result for {agent_id}: {result}")
                except Exception as exc:
                    self.world.add_log(f"Tool error for {agent_id}: {exc}")
