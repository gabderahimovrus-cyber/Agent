"""Tkinter graphical application for the local multi-agent system."""

from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional

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

        self.name_entry = ttk.Entry(master, width=42)
        self.role_entry = ttk.Entry(master, width=42)
        self.prompt_text = tk.Text(master, width=52, height=8, wrap="word", undo=True)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        self.role_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        self.prompt_text.grid(row=2, column=1, sticky="nsew", padx=8, pady=6)
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


class SettingsDialog(simpledialog.Dialog):
    """Modal dialog for editing application settings."""

 main
    def validate(self) -> bool:
        value = self.ollama_url_entry.get().strip()
        if not value:
            messagebox.showerror("Настройки", "Введите адрес API Ollama.")
            return False
        if not value.startswith(("http://", "https://")):
            messagebox.showerror("Настройки", "Адрес API Ollama должен начинаться с http:// или https://.")
            return False
        return True

    def apply(self) -> None:
in


class MultiAgentApp:
    """Main GUI controller that wires together state, Ollama, and the engine."""

    def __init__(self, root: tk.Tk, state_path: Path, workspace: Path) -> None:
        self.root = root
        self.root.title("Локальная многоагентная ИИ-система")

        self.engine = SimulationEngine(self.world, self.ollama, workspace)
        self.selected_agent_id: Optional[str] = None
        self.tick_interval_ms = 2500
        self.ollama_available = False
        self._tick_lock = threading.Lock()
        self._animation_step = 0
        self._ollama_process: Optional[subprocess.Popen[str]] = None
        self._build_ui()
        self._install_clipboard_shortcuts()
        self.refresh_all()
        self.check_ollama()
        self._animate_header()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self._configure_style()
        self.root.configure(bg="#0f172a")
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
 main
        left.rowconfigure(0, weight=1)
        self.agent_list = tk.Listbox(
            left,
            width=32,
            bg="#111827",
            fg="#e5e7eb",
            selectbackground="#2563eb",
            selectforeground="#ffffff",
            activestyle="none",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
        )
        self.agent_list.grid(row=0, column=0, sticky="nsew")
        self.agent_list.bind("<<ListboxSelect>>", self.on_agent_select)
        self._attach_context_menu(self.agent_list)

 main
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.log_text = tk.Text(
            center,
            wrap="word",
            state="disabled",
            bg="#020617",
            fg="#cbd5e1",
            insertbackground="#93c5fd",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self._attach_context_menu(self.log_text)


        self.agent_details.grid(row=0, column=0, sticky="ew")
        self.chat_text = tk.Text(
            right,
            wrap="word",
            width=44,
            height=18,
            state="disabled",
            bg="#020617",
            fg="#e2e8f0",
            insertbackground="#93c5fd",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.chat_text.grid(row=1, column=0, sticky="nsew", pady=8)
        self._attach_context_menu(self.chat_text)
        chat_bar = ttk.Frame(right, style="Card.TFrame")
        chat_bar.grid(row=2, column=0, sticky="ew")
        chat_bar.columnconfigure(0, weight=1)
        self.chat_entry = ttk.Entry(chat_bar)
        self.chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.chat_entry.bind("<Return>", lambda _event: self.send_chat())
 main

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
            status_icon = {"idle": "🟢", "thinking": "🔵", "error": "🔴", "disabled": "⚫"}.get(agent.status, "⚪")
            self.agent_list.insert("end", f"{status_icon} {agent.name} — {agent.role} [{agent.status}]")
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
                text=f"{agent.name}\nРоль: {agent.role}\nСтатус: {agent.status}\nИнструменты: {', '.join(agent.tools)}"
            )
            related = [m for m in self.world.messages.values() if m.sender == agent.id or m.recipient in {agent.id, "broadcast"}]
            for message in related[-100:]:
                self.chat_text.insert("end", f"{message.timestamp} {message.sender} → {message.recipient}: {message.content}\n")
        else:
            self.agent_details.configure(text="Агент не выбран")
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def refresh_status(self) -> None:
        engine = "работает" if self.world.engine_running else "остановлен"
        model = self.world.selected_model or "модель не выбрана"

            f"Агенты: {len(self.world.agents)} | Шаг: {self.world.tick_count}"
        )

    def on_agent_select(self, _event: object = None) -> None:
        selection = self.agent_list.curselection()
        ids = list(self.world.agents.keys())
        self.selected_agent_id = ids[selection[0]] if selection else None
        self.refresh_chat()

    def create_agent(self) -> None:
        dialog = AgentDialog(self.root, "Создать агента", prompt="Возвращай строгий JSON с действиями для локальной симуляции.")
        if dialog.result:
            self.world.add_agent(*dialog.result)
            self.save_and_refresh()

    def edit_agent(self) -> None:
        if not self.selected_agent_id:
            messagebox.showinfo("Изменить агента", "Сначала выберите агента.")
            return
        agent = self.world.agents[self.selected_agent_id]
        dialog = AgentDialog(self.root, "Изменить агента", agent.name, agent.role, agent.system_prompt)
        if dialog.result:
            self.world.update_agent(self.selected_agent_id, *dialog.result)
            self.save_and_refresh()

    def delete_agent(self) -> None:
        if not self.selected_agent_id:
            messagebox.showinfo("Удалить агента", "Сначала выберите агента.")
            return
        if messagebox.askyesno("Удалить агента", "Удалить выбранного агента?"):
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

    def open_settings(self) -> None:

            self.save_and_refresh()
            self.check_ollama()

    def check_ollama(self) -> None:
        status = self.ollama.status()
        self.ollama_available = status.available
        self._apply_model_list(status.models)
        self.world.add_log(status.message)
        self.save_and_refresh()

    def refresh_models(self) -> None:
        self.check_ollama()

    def _apply_model_list(self, models: list[str]) -> None:
        self.model_combo.configure(values=models)
        if self.world.selected_model in models:
            self.model_combo.set(self.world.selected_model)
        elif models:
            self.world.selected_model = models[0]
            self.model_combo.set(models[0])
        else:
            self.world.selected_model = ""
            self.model_combo.set("")

    def start_ollama_service(self) -> None:
        command = self.world.ollama_executable_path.strip() or "ollama"
        try:
            if self._ollama_process and self._ollama_process.poll() is None:
                self.world.add_log("Ollama уже запущена из этого приложения")
            else:
                self._ollama_process = subprocess.Popen(
                    [command, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                self.world.add_log(f"Запуск Ollama: {command} serve")
            self.save_and_refresh()
            self.root.after(1800, self.check_ollama)
        except FileNotFoundError:
            messagebox.showerror(
                "Запуск Ollama",
                "Файл Ollama не найден. Укажите путь в Меню → Настройки Ollama или добавьте команду `ollama` в PATH.",
            )
            self.world.add_log(f"Не удалось запустить Ollama: файл не найден ({command})")
            self.save_and_refresh()
        except Exception as exc:
            messagebox.showerror("Запуск Ollama", f"Не удалось запустить Ollama: {exc}")
            self.world.add_log(f"Не удалось запустить Ollama: {exc}")
            self.save_and_refresh()

    def install_ollama(self) -> None:
        self.ollama.open_install_page()
        messagebox.showinfo("Установить Ollama", self.ollama.install_instructions())
        self.world.add_log("Открыта официальная страница установки Ollama и показаны инструкции")
        self.save_and_refresh()

    def select_model(self, _event: object = None) -> None:
        self.world.selected_model = self.model_combo.get()
        self.world.add_log(f"Выбрана модель {self.world.selected_model}")
        self.save_and_refresh()

    def start_engine(self) -> None:
        self.world.engine_running = True
        self.world.add_log("Движок симуляции запущен")
        self.save_and_refresh()
        self.root.after(10, self.engine_loop)

    def stop_engine(self) -> None:
        self.world.engine_running = False
        self.world.add_log("Движок симуляции остановлен")
        self.save_and_refresh()

    def engine_loop(self) -> None:
        if self.world.engine_running:
            self.run_tick_async()
            self.root.after(self.tick_interval_ms, self.engine_loop)

    def run_tick_async(self) -> None:
        threading.Thread(target=self._run_tick_worker, daemon=True).start()

    def _run_tick_worker(self) -> None:
        if not self._tick_lock.acquire(blocking=False):
            self.world.add_log("Шаг пропущен: предыдущий шаг ещё выполняется")
            self.store.save(self.world)
            self.root.after(0, self.refresh_all)
            return
        try:
            self.engine.tick()
            self.store.save(self.world)
        finally:
            self._tick_lock.release()
        self.root.after(0, self.refresh_all)

    def save_and_refresh(self) -> None:
        self.store.save(self.world)
        self.refresh_all()

    def on_close(self) -> None:
        self.world.engine_running = False
        self.store.save(self.world)
        self.root.destroy()
