"""Tkinter graphical application for the local multi-agent system."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

from .engine import SimulationEngine
from .ollama_client import OllamaClient
from .world import WorldState, WorldStore


class AgentDialog(simpledialog.Dialog):
    """Modal dialog for creating and editing agents."""

    def __init__(self, parent: tk.Misc, title: str, name: str = "", role: str = "", prompt: str = "") -> None:
        self.initial_name = name
        self.initial_role = role
        self.initial_prompt = prompt
        self.result = None
        super().__init__(parent, title)

    def body(self, master: tk.Misc) -> tk.Widget:
        ttk.Label(master, text="Name").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Label(master, text="Role").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Label(master, text="System prompt").grid(row=2, column=0, sticky="nw", padx=4, pady=4)
        self.name_entry = ttk.Entry(master, width=42)
        self.role_entry = ttk.Entry(master, width=42)
        self.prompt_text = tk.Text(master, width=52, height=8)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.role_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self.prompt_text.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)
        self.name_entry.insert(0, self.initial_name)
        self.role_entry.insert(0, self.initial_role)
        self.prompt_text.insert("1.0", self.initial_prompt)
        return self.name_entry

    def apply(self) -> None:
        self.result = (
            self.name_entry.get(),
            self.role_entry.get(),
            self.prompt_text.get("1.0", "end").strip(),
        )


class MultiAgentApp:
    """Main GUI controller that wires together state, Ollama, and the engine."""

    def __init__(self, root: tk.Tk, state_path: Path, workspace: Path) -> None:
        self.root = root
        self.root.title("Multi-Agent Local AI System")
        self.store = WorldStore(state_path)
        self.world: WorldState = self.store.load()
        self.ollama = OllamaClient()
        self.engine = SimulationEngine(self.world, self.ollama, workspace)
        self.selected_agent_id: Optional[str] = None
        self.tick_interval_ms = 2500
        self._build_ui()
        self.refresh_all()
        self.check_ollama()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(toolbar, text="Create agent", command=self.create_agent).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit agent", command=self.edit_agent).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete agent", command=self.delete_agent).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="Start simulation", command=self.start_engine).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Stop simulation", command=self.stop_engine).pack(side="left", padx=2)
        ttk.Button(toolbar, text="One tick", command=self.run_tick_async).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="Install Ollama", command=self.install_ollama).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Refresh models", command=self.check_ollama).pack(side="left", padx=2)
        self.model_combo = ttk.Combobox(toolbar, width=32, state="readonly")
        self.model_combo.pack(side="left", padx=2)
        self.model_combo.bind("<<ComboboxSelected>>", self.select_model)

        left = ttk.LabelFrame(self.root, text="Agents", padding=6)
        left.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        left.rowconfigure(0, weight=1)
        self.agent_list = tk.Listbox(left, width=30)
        self.agent_list.grid(row=0, column=0, sticky="nsew")
        self.agent_list.bind("<<ListboxSelect>>", self.on_agent_select)

        center = ttk.LabelFrame(self.root, text="Interaction logs", padding=6)
        center.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.log_text = tk.Text(center, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        right = ttk.LabelFrame(self.root, text="Chat with selected agent", padding=6)
        right.grid(row=1, column=2, sticky="nsew", padx=6, pady=6)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self.agent_details = ttk.Label(right, text="No agent selected", justify="left")
        self.agent_details.grid(row=0, column=0, sticky="ew")
        self.chat_text = tk.Text(right, wrap="word", width=42, height=18, state="disabled")
        self.chat_text.grid(row=1, column=0, sticky="nsew", pady=6)
        chat_bar = ttk.Frame(right)
        chat_bar.grid(row=2, column=0, sticky="ew")
        chat_bar.columnconfigure(0, weight=1)
        self.chat_entry = ttk.Entry(chat_bar)
        self.chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.chat_entry.bind("<Return>", lambda _event: self.send_chat())
        ttk.Button(chat_bar, text="Send", command=self.send_chat).grid(row=0, column=1)

        self.status_var = tk.StringVar(value="Starting")
        status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=4)
        status.grid(row=2, column=0, columnspan=3, sticky="ew")

    def refresh_all(self) -> None:
        self.refresh_agents()
        self.refresh_logs()
        self.refresh_chat()
        self.refresh_status()

    def refresh_agents(self) -> None:
        current = self.selected_agent_id
        self.agent_list.delete(0, "end")
        ids = list(self.world.agents.keys())
        for agent_id in ids:
            agent = self.world.agents[agent_id]
            self.agent_list.insert("end", f"{agent.name} — {agent.role} [{agent.status}]")
        if current in ids:
            index = ids.index(current)
            self.agent_list.selection_set(index)
            self.agent_list.see(index)

    def refresh_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", "\n".join(self.world.logs[-300:]))
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def refresh_chat(self) -> None:
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        if self.selected_agent_id and self.selected_agent_id in self.world.agents:
            agent = self.world.agents[self.selected_agent_id]
            self.agent_details.configure(
                text=f"{agent.name}\nRole: {agent.role}\nStatus: {agent.status}\nTools: {', '.join(agent.tools)}"
            )
            related = [m for m in self.world.messages.values() if m.sender == agent.id or m.recipient in {agent.id, "broadcast"}]
            for message in related[-100:]:
                self.chat_text.insert("end", f"{message.timestamp} {message.sender} -> {message.recipient}: {message.content}\n")
        else:
            self.agent_details.configure(text="No agent selected")
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def refresh_status(self) -> None:
        status = self.ollama.status()
        engine = "running" if self.world.engine_running else "stopped"
        model = self.world.selected_model or "no model selected"
        self.status_var.set(
            f"Ollama: {'connected' if status.available else 'offline'} | Engine: {engine} | Model: {model} | "
            f"Agents: {len(self.world.agents)} | Tick: {self.world.tick_count}"
        )

    def on_agent_select(self, _event: object = None) -> None:
        selection = self.agent_list.curselection()
        ids = list(self.world.agents.keys())
        self.selected_agent_id = ids[selection[0]] if selection else None
        self.refresh_chat()

    def create_agent(self) -> None:
        dialog = AgentDialog(self.root, "Create agent", prompt="Return strict JSON actions for the local simulation.")
        if dialog.result:
            self.world.add_agent(*dialog.result)
            self.save_and_refresh()

    def edit_agent(self) -> None:
        if not self.selected_agent_id:
            messagebox.showinfo("Edit agent", "Select an agent first.")
            return
        agent = self.world.agents[self.selected_agent_id]
        dialog = AgentDialog(self.root, "Edit agent", agent.name, agent.role, agent.system_prompt)
        if dialog.result:
            self.world.update_agent(self.selected_agent_id, *dialog.result)
            self.save_and_refresh()

    def delete_agent(self) -> None:
        if not self.selected_agent_id:
            messagebox.showinfo("Delete agent", "Select an agent first.")
            return
        if messagebox.askyesno("Delete agent", "Delete the selected agent?"):
            self.world.delete_agent(self.selected_agent_id)
            self.selected_agent_id = None
            self.save_and_refresh()

    def send_chat(self) -> None:
        content = self.chat_entry.get().strip()
        if not content or not self.selected_agent_id:
            return
        self.world.send_message("user", self.selected_agent_id, content, "chat")
        self.chat_entry.delete(0, "end")
        self.save_and_refresh()

    def check_ollama(self) -> None:
        status = self.ollama.status()
        self.model_combo.configure(values=status.models)
        if self.world.selected_model in status.models:
            self.model_combo.set(self.world.selected_model)
        elif status.models:
            self.world.selected_model = status.models[0]
            self.model_combo.set(status.models[0])
        self.world.add_log(status.message)
        self.save_and_refresh()

    def install_ollama(self) -> None:
        self.ollama.open_install_page()
        self.world.add_log("Opened official Ollama installation page")
        self.save_and_refresh()

    def select_model(self, _event: object = None) -> None:
        self.world.selected_model = self.model_combo.get()
        self.world.add_log(f"Selected model {self.world.selected_model}")
        self.save_and_refresh()

    def start_engine(self) -> None:
        self.world.engine_running = True
        self.world.add_log("Simulation engine started")
        self.save_and_refresh()
        self.root.after(10, self.engine_loop)

    def stop_engine(self) -> None:
        self.world.engine_running = False
        self.world.add_log("Simulation engine stopped")
        self.save_and_refresh()

    def engine_loop(self) -> None:
        if self.world.engine_running:
            self.run_tick_async()
            self.root.after(self.tick_interval_ms, self.engine_loop)

    def run_tick_async(self) -> None:
        threading.Thread(target=self._run_tick_worker, daemon=True).start()

    def _run_tick_worker(self) -> None:
        self.engine.tick()
        self.store.save(self.world)
        self.root.after(0, self.refresh_all)

    def save_and_refresh(self) -> None:
        self.store.save(self.world)
        self.refresh_all()

    def on_close(self) -> None:
        self.world.engine_running = False
        self.store.save(self.world)
        self.root.destroy()
