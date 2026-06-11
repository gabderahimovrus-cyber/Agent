# Multi-Agent Local AI System

A local Tkinter application that runs a tick-based multi-agent simulation with Ollama-backed language models. The system is designed to work on a local computer without mandatory cloud APIs.

## Features

- Graphical interface with agent list, interaction logs, selected-agent chat, model controls, and system status.
- Agent creation, editing, deletion, short-term memory, long-term memory, tools, status, and isolated logical identity.
- Central message bus with direct and broadcast messages.
- Tick-based simulation engine that prompts a selected Ollama model and safely applies structured JSON actions.
- Ollama status checks, model list refresh, model selection, and an install button that opens the official Ollama download page.
- Persistent world state stored in `data/world_state.json` and restored on startup.
- Controlled tools for file reads/writes inside `workspace/`, local Python snippets, memory updates, and inter-agent messages.
- Defensive handling for malformed model responses: errors are logged and the simulation keeps running.

## Run

```bash
python main.py
```

Install Ollama from <https://ollama.com/download>, start Ollama locally, and pull at least one model, for example:

```bash
ollama pull llama3.1
```

Then use **Refresh models** in the application and choose the installed model.

## Agent response format

Agents are instructed to return strict JSON:

```json
{
  "thought": "short private reasoning summary",
  "actions": [
    {"tool": "remember", "args": {"content": "important event"}}
  ],
  "messages": [
    {"recipient": "broadcast", "content": "hello agents"}
  ]
}
```
