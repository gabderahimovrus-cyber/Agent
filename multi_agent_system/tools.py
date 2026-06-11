"""Controlled tool execution for agents."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict

from .world import WorldState


class ToolExecutor:
    """Executes a constrained set of local tools on behalf of agents."""

    def __init__(self, workspace: Path, world: WorldState) -> None:
        self.workspace = workspace.resolve()
        self.world = world

    def _safe_path(self, relative_path: str) -> Path:
        path = (self.workspace / relative_path).resolve()
        if self.workspace not in path.parents and path != self.workspace:
            raise ValueError("Tool path escapes the managed workspace")
        return path

    def _ensure_allowed(self, agent_id: str, tool: str) -> None:
        agent = self.world.agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Unknown agent: {agent_id}")
        if tool not in agent.tools:
            raise ValueError(f"Tool is not enabled for this agent: {tool}")

    def execute(self, agent_id: str, action: Dict[str, Any]) -> str:
        tool = str(action.get("tool") or action.get("type") or "")
        if not tool:
            raise ValueError("Action does not specify a tool")
        self._ensure_allowed(agent_id, tool)
        args = action.get("args") or action
        if not isinstance(args, dict):
            raise ValueError("Action args must be an object")
        if tool == "send_message":
            recipient = str(args.get("recipient", "broadcast"))
            content = str(args.get("content", ""))
            self.world.send_message(agent_id, recipient, content)
            return f"sent message to {recipient}"
        if tool == "remember":
            event = str(args.get("content") or args.get("event") or "")
            if not event.strip():
                raise ValueError("Memory event is empty")
            self.world.agents[agent_id].remember_long(event)
            return "stored long-term memory"
        if tool == "read_file":
            path = self._safe_path(str(args.get("path", "")))
            return path.read_text(encoding="utf-8")[:8000]
        if tool in {"write_file", "create_file"}:
            path = self._safe_path(str(args.get("path", "")))
            path.parent.mkdir(parents=True, exist_ok=True)
            content = str(args.get("content", ""))
            path.write_text(content, encoding="utf-8")
            rel = str(path.relative_to(self.workspace))
            self.world.project_files[rel] = content
            self.world.add_log(f"Project file updated by {agent_id}: {rel}")
            return f"wrote {rel}"
        if tool == "run_python":
            code = str(args.get("code", ""))
            if not code.strip():
                raise ValueError("Python code is empty")
            result = subprocess.run(
                ["python", "-c", code],
                cwd=self.workspace,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            return (result.stdout + result.stderr)[-4000:]
        raise ValueError(f"Unknown tool: {tool}")
