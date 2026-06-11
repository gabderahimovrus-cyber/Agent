"""Application entry point for Multi-Agent Local AI System."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from multi_agent_system import MultiAgentApp


def main() -> None:
    """Initialize local storage, check services through the GUI, and start Tk."""
    root = tk.Tk()
    base_dir = Path(__file__).resolve().parent
    state_path = base_dir / "data" / "world_state.json"
    workspace = base_dir / "workspace"
    workspace.mkdir(exist_ok=True)
    MultiAgentApp(root, state_path, workspace)
    root.mainloop()


if __name__ == "__main__":
    main()
