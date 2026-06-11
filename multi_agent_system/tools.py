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

    def execute(self, agent_id: str, action: Dict[str, Any]) -> str:
        tool = action.get("tool") or action.get("type")
        args = action.get("args") or action
        if tool == "send_message":
            recipient = args.get("recipient", "broadcast")
            content = args.get("content", "")
            self.world.send_message(agent_id, recipient, content)
            return f"sent message to {recipient}"
        if tool == "remember":
            event = args.get("content") or args.get("event") or ""
            self.world.agents[agent_id].remember_long(event)
            return "stored long-term memory"
        if tool == "read_file":
            path = self._safe_path(args.get("path", ""))
            return path.read_text(encoding="utf-8")[:8000]
        if tool in {"write_file", "create_file"}:
            path = self._safe_path(args.get("path", ""))
            path.parent.mkdir(parents=True, exist_ok=True)
            content = args.get("content", "")
            path.write_text(content, encoding="utf-8")
            rel = str(path.relative_to(self.workspace))
            self.world.project_files[rel] = content
            return f"wrote {rel}"
        if tool == "run_python":
            code = args.get("code", "")
            result = subprocess.run(
                ["python", "-c", code],
                cwd=self.workspace,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            return (result.stdout + result.stderr)[-4000:]
        raise ValueError(f"Unknown or unavailable tool: {tool}")
