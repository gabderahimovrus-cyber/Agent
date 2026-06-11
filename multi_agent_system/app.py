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
        master.columnconfigure(1, weight=1)
        ttk.Label(master, text="Имя").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Label(master, text="Роль").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Label(master, text="Системный промпт").grid(row=2, column=0, sticky="nw", padx=8, pady=6)
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

    def __init__(self, parent: tk.Misc, *, ollama_base_url: str, ollama_api_key: str, ollama_executable_path: str) -> None:
        self.initial_ollama_base_url = ollama_base_url
        self.initial_ollama_api_key = ollama_api_key
        self.initial_ollama_executable_path = ollama_executable_path
        self.result: Optional[dict[str, str]] = None
        super().__init__(parent, "Настройки Ollama")

    def body(self, master: tk.Misc) -> tk.Widget:
        master.columnconfigure(1, weight=1)
        ttk.Label(master, text="API Ollama").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.ollama_url_entry = ttk.Entry(master, width=54)
        self.ollama_url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=6)
        self.ollama_url_entry.insert(0, self.initial_ollama_base_url)
        ttk.Label(master, text="Например: http://127.0.0.1:11434", foreground="#6b7280").grid(
            row=1, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 8)
        )

        ttk.Label(master, text="API ключ").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.ollama_key_entry = ttk.Entry(master, width=54, show="•")
        self.ollama_key_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=6)
        self.ollama_key_entry.insert(0, self.initial_ollama_api_key)
        ttk.Label(master, text="Обычно не нужен для локальной Ollama; нужен для прокси/удалённого API.", foreground="#6b7280").grid(
            row=3, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 8)
        )

        ttk.Label(master, text="Путь к Ollama").grid(row=4, column=0, sticky="w", padx=8, pady=6)
        self.ollama_path_entry = ttk.Entry(master, width=54)
        self.ollama_path_entry.grid(row=4, column=1, sticky="ew", padx=8, pady=6)
        self.ollama_path_entry.insert(0, self.initial_ollama_executable_path)
        ttk.Button(master, text="Выбрать…", command=self.browse_ollama_path).grid(row=4, column=2, sticky="ew", padx=8, pady=6)
        ttk.Label(master, text="Можно оставить пустым, если команда `ollama` доступна в PATH.", foreground="#6b7280").grid(
            row=5, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 8)
        )
        return self.ollama_url_entry

    def browse_ollama_path(self) -> None:
        path = filedialog.askopenfilename(title="Выберите исполняемый файл Ollama")
        if path:
            self.ollama_path_entry.delete(0, "end")
            self.ollama_path_entry.insert(0, path)

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
        self.result = {
            "ollama_base_url": self.ollama_url_entry.get().strip().rstrip("/"),
            "ollama_api_key": self.ollama_key_entry.get().strip(),
            "ollama_executable_path": self.ollama_path_entry.get().strip(),
        }


class MultiAgentApp:
    """Main GUI controller that wires together state, Ollama, and the engine."""

    def __init__(self, root: tk.Tk, state_path: Path, workspace: Path) -> None:
        self.root = root
        self.root.title("Локальная многоагентная ИИ-система")
        self.root.minsize(1120, 700)
        self.store = WorldStore(state_path)
        self.world: WorldState = self.store.load()
        self.ollama = OllamaClient(self.world.ollama_base_url, api_key=self.world.ollama_api_key)
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
        self.root.columnconfigure(2, weight=0)
        self.root.rowconfigure(2, weight=1)

        menu_bar = tk.Menu(self.root)
        settings_menu = tk.Menu(menu_bar, tearoff=False)
        settings_menu.add_command(label="Настройки Ollama", command=self.open_settings)
        settings_menu.add_command(label="Запустить Ollama", command=self.start_ollama_service)
        menu_bar.add_cascade(label="Меню", menu=settings_menu)
        edit_menu = tk.Menu(menu_bar, tearoff=False)
        edit_menu.add_command(label="Копировать", accelerator="Ctrl+C", command=self.copy_selection)
        edit_menu.add_command(label="Вставить", accelerator="Ctrl+V", command=self.paste_clipboard)
        edit_menu.add_command(label="Вырезать", accelerator="Ctrl+X", command=self.cut_selection)
        edit_menu.add_command(label="Выделить всё", accelerator="Ctrl+A", command=self.select_all)
        menu_bar.add_cascade(label="Правка", menu=edit_menu)
        self.root.config(menu=menu_bar)

        self.header_canvas = tk.Canvas(self.root, height=92, bg="#111827", highlightthickness=0)
        self.header_canvas.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.header_canvas.bind("<Configure>", self._draw_header)

        toolbar = ttk.Frame(self.root, padding=(10, 8), style="Toolbar.TFrame")
        toolbar.grid(row=1, column=0, columnspan=3, sticky="ew")
        ttk.Button(toolbar, text="✨ Создать", style="Accent.TButton", command=self.create_agent).pack(side="left", padx=3)
        ttk.Button(toolbar, text="✏️ Изменить", command=self.edit_agent).pack(side="left", padx=3)
        ttk.Button(toolbar, text="🗑 Удалить", command=self.delete_agent).pack(side="left", padx=3)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="▶ Запустить", style="Success.TButton", command=self.start_engine).pack(side="left", padx=3)
        ttk.Button(toolbar, text="⏸ Остановить", command=self.stop_engine).pack(side="left", padx=3)
        ttk.Button(toolbar, text="⚡ Один шаг", command=self.run_tick_async).pack(side="left", padx=3)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="🚀 Запустить Ollama", command=self.start_ollama_service).pack(side="left", padx=3)
        ttk.Button(toolbar, text="⬇ Установить", command=self.install_ollama).pack(side="left", padx=3)
        ttk.Button(toolbar, text="🔍 Проверить", command=self.check_ollama).pack(side="left", padx=3)
        ttk.Button(toolbar, text="↻ Модели", command=self.refresh_models).pack(side="left", padx=3)
        ttk.Button(toolbar, text="⚙ Настройки", command=self.open_settings).pack(side="left", padx=3)
        self.model_combo = ttk.Combobox(toolbar, width=30, state="readonly")
        self.model_combo.pack(side="left", padx=(10, 3))
        self.model_combo.bind("<<ComboboxSelected>>", self.select_model)

        left = ttk.LabelFrame(self.root, text="🤖 Агенты", padding=10, style="Card.TLabelframe")
        left.grid(row=2, column=0, sticky="nsew", padx=(10, 5), pady=10)
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

        center = ttk.LabelFrame(self.root, text="📡 Журнал взаимодействий", padding=10, style="Card.TLabelframe")
        center.grid(row=2, column=1, sticky="nsew", padx=5, pady=10)
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

        right = ttk.LabelFrame(self.root, text="💬 Чат с выбранным агентом", padding=10, style="Card.TLabelframe")
        right.grid(row=2, column=2, sticky="nsew", padx=(5, 10), pady=10)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self.agent_details = ttk.Label(right, text="Агент не выбран", justify="left", style="Muted.TLabel")
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
        self._attach_context_menu(self.chat_entry)
        ttk.Button(chat_bar, text="Отправить", style="Accent.TButton", command=self.send_chat).grid(row=0, column=1)

        status_frame = ttk.Frame(self.root, padding=(10, 6), style="Status.TFrame")
        status_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.status_dot = ttk.Label(status_frame, text="●", style="StatusDot.TLabel")
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status_var = tk.StringVar(value="Запуск")
        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel").pack(side="left", fill="x", expand=True)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("Toolbar.TFrame", background="#1e293b")
        style.configure("Card.TFrame", background="#0f172a")
        style.configure("Card.TLabelframe", background="#0f172a", foreground="#e5e7eb", bordercolor="#334155")
        style.configure("Card.TLabelframe.Label", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 11, "bold"))
        style.configure("TButton", padding=(10, 6), background="#334155", foreground="#f8fafc", bordercolor="#475569")
        style.map("TButton", background=[("active", "#475569")], foreground=[("disabled", "#94a3b8")])
        style.configure("Accent.TButton", background="#2563eb", foreground="#ffffff", bordercolor="#3b82f6")
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])
        style.configure("Success.TButton", background="#059669", foreground="#ffffff", bordercolor="#10b981")
        style.map("Success.TButton", background=[("active", "#047857")])
        style.configure("TLabel", background="#0f172a", foreground="#e5e7eb")
        style.configure("Muted.TLabel", background="#0f172a", foreground="#cbd5e1")
        style.configure("Status.TFrame", background="#020617")
        style.configure("Status.TLabel", background="#020617", foreground="#cbd5e1")
        style.configure("StatusDot.TLabel", background="#020617", foreground="#ef4444", font=("Segoe UI", 13, "bold"))
        style.configure("TEntry", fieldbackground="#f8fafc", foreground="#0f172a")

    def _draw_header(self, _event: object = None) -> None:
        width = max(self.header_canvas.winfo_width(), 1)
        self.header_canvas.delete("all")
        self.header_canvas.create_rectangle(0, 0, width, 92, fill="#111827", outline="")
        self.header_canvas.create_oval(width - 220, -100, width + 90, 160, fill="#1d4ed8", outline="")
        self.header_canvas.create_oval(width - 360, 18, width - 160, 130, fill="#7c3aed", outline="")
        self.header_canvas.create_text(
            24,
            30,
            anchor="w",
            text="Локальная многоагентная ИИ-система",
            fill="#f8fafc",
            font=("Segoe UI", 20, "bold"),
        )
        self.header_canvas.create_text(
            26,
            62,
            anchor="w",
            text="Ollama • агенты • локальный рабочий процесс",
            fill="#93c5fd",
            font=("Segoe UI", 10),
        )
        for index, x in enumerate((width - 300, width - 250, width - 200, width - 150, width - 100)):
            y = 42 + ((index + self._animation_step) % 3) * 8
            color = ("#93c5fd", "#a78bfa", "#34d399")[(index + self._animation_step) % 3]
            self.header_canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="")
            if index:
                self.header_canvas.create_line(x - 50, 50 + ((index - 1 + self._animation_step) % 3) * 8, x, y, fill="#475569", width=2)

    def _animate_header(self) -> None:
        self._animation_step = (self._animation_step + 1) % 6
        self._draw_header()
        status_color = "#22c55e" if self.ollama_available else "#ef4444"
        if self.world.engine_running and self._animation_step % 2 == 0:
            status_color = "#60a5fa"
        self.status_dot.configure(foreground=status_color)
        self.root.after(450, self._animate_header)

    def _install_clipboard_shortcuts(self) -> None:
        for sequence in ("<Control-c>", "<Control-C>", "<Command-c>", "<Command-C>"):
            self.root.bind_all(sequence, lambda event: self.copy_selection(event), add="+")
        for sequence in ("<Control-v>", "<Control-V>", "<Command-v>", "<Command-V>"):
            self.root.bind_all(sequence, lambda event: self.paste_clipboard(event), add="+")
        for sequence in ("<Control-x>", "<Control-X>", "<Command-x>", "<Command-X>"):
            self.root.bind_all(sequence, lambda event: self.cut_selection(event), add="+")
        for sequence in ("<Control-a>", "<Control-A>", "<Command-a>", "<Command-A>"):
            self.root.bind_all(sequence, lambda event: self.select_all(event), add="+")

    def _attach_context_menu(self, widget: tk.Widget) -> None:
        widget.bind("<Button-3>", self.show_context_menu, add="+")
        widget.bind("<Button-2>", self.show_context_menu, add="+")

    def show_context_menu(self, event: tk.Event[Any]) -> str:
        event.widget.focus_set()
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Копировать", command=self.copy_selection)
        menu.add_command(label="Вставить", command=self.paste_clipboard)
        menu.add_command(label="Вырезать", command=self.cut_selection)
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=self.select_all)
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def copy_selection(self, _event: object = None) -> str:
        widget = self.root.focus_get()
        try:
            if isinstance(widget, tk.Listbox):
                selected = [widget.get(index) for index in widget.curselection()]
                text = "\n".join(selected)
            elif isinstance(widget, tk.Text):
                text = widget.get("sel.first", "sel.last")
            elif isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                text = widget.selection_get()
            else:
                return "break"
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            pass
        return "break"

    def paste_clipboard(self, _event: object = None) -> str:
        widget = self.root.focus_get()
        try:
            text = self.root.clipboard_get()
            if isinstance(widget, tk.Text) and str(widget.cget("state")) != "disabled":
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert("insert", text)
            elif isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert("insert", text)
        except tk.TclError:
            pass
        return "break"

    def cut_selection(self, _event: object = None) -> str:
        widget = self.root.focus_get()
        self.copy_selection()
        try:
            if isinstance(widget, tk.Text) and str(widget.cget("state")) != "disabled":
                widget.delete("sel.first", "sel.last")
            elif isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                widget.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        return "break"

    def select_all(self, _event: object = None) -> str:
        widget = self.root.focus_get()
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
        elif isinstance(widget, tk.Listbox):
            widget.selection_set(0, "end")
        elif isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
            widget.selection_range(0, "end")
            widget.icursor("end")
        return "break"

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
        api_key = "ключ задан" if self.world.ollama_api_key else "без ключа"
        executable = self.world.ollama_executable_path or "ollama из PATH"
        self.status_var.set(
            f"Ollama: {'подключена' if self.ollama_available else 'не в сети'} | API: {self.world.ollama_base_url} | "
            f"{api_key} | Путь: {executable} | Движок: {engine} | Модель: {model} | "
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
        dialog = SettingsDialog(
            self.root,
            ollama_base_url=self.world.ollama_base_url,
            ollama_api_key=self.world.ollama_api_key,
            ollama_executable_path=self.world.ollama_executable_path,
        )
        if dialog.result:
            self.world.ollama_base_url = dialog.result["ollama_base_url"]
            self.world.ollama_api_key = dialog.result["ollama_api_key"]
            self.world.ollama_executable_path = dialog.result["ollama_executable_path"]
            self.ollama.configure(self.world.ollama_base_url, self.world.ollama_api_key)
            self.world.add_log(f"Настройки Ollama обновлены: API {self.world.ollama_base_url}")
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
