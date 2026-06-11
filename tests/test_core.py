import json
import tempfile
import unittest
from pathlib import Path

from multi_agent_system.engine import SimulationEngine
from multi_agent_system.ollama_client import OllamaClient
from multi_agent_system.tools import ToolExecutor
from multi_agent_system.world import WorldState, WorldStore


class FakeOllama(OllamaClient):
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, model: str, prompt: str) -> str:
        self.last_model = model
        self.last_prompt = prompt
        return self.response


class CoreTests(unittest.TestCase):
    def test_message_bus_tracks_direct_and_broadcast_inboxes(self) -> None:
        world = WorldState()
        first = world.add_agent("A", "alpha", "json only")
        second = world.add_agent("B", "beta", "json only")

        direct = world.send_message(first.id, second.id, "hello")
        broadcast = world.send_message("user", "broadcast", "all")

        self.assertIn(direct.id, second.incoming_message_ids)
        self.assertIn(broadcast.id, first.incoming_message_ids)
        self.assertIn(broadcast.id, second.incoming_message_ids)
        self.assertEqual(broadcast.message_type, "broadcast")

    def test_tool_executor_restricts_workspace_and_agent_tools(self) -> None:
        world = WorldState()
        agent = world.add_agent("Writer", "writes", "json only")
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(Path(tmp), world)
            result = executor.execute(agent.id, {"tool": "write_file", "args": {"path": "note.txt", "content": "ok"}})
            self.assertEqual(result, "wrote note.txt")
            self.assertEqual((Path(tmp) / "note.txt").read_text(), "ok")
            with self.assertRaises(ValueError):
                executor.execute(agent.id, {"tool": "read_file", "args": {"path": "../secret.txt"}})
            agent.tools.remove("run_python")
            with self.assertRaises(ValueError):
                executor.execute(agent.id, {"tool": "run_python", "args": {"code": "print(1)"}})

    def test_engine_survives_malformed_model_response(self) -> None:
        world = WorldState(selected_model="local-model")
        agent = world.add_agent("Safe", "handles errors", "json only")
        with tempfile.TemporaryDirectory() as tmp:
            engine = SimulationEngine(world, FakeOllama("not json"), Path(tmp))
            engine.tick()
        self.assertEqual(agent.status, "error")
        self.assertTrue(any("failed safely" in line for line in world.logs))

    def test_engine_applies_structured_messages_and_memory(self) -> None:
        payload = {
            "thought": "plan",
            "actions": [{"tool": "remember", "args": {"content": "important"}}],
            "messages": [{"recipient": "broadcast", "content": "hello peers"}],
        }
        world = WorldState(selected_model="local-model")
        agent = world.add_agent("Actor", "acts", "json only")
        with tempfile.TemporaryDirectory() as tmp:
            engine = SimulationEngine(world, FakeOllama(json.dumps(payload)), Path(tmp))
            engine.tick()
        self.assertEqual(agent.status, "idle")
        self.assertIn("important", agent.long_term_memory)
        self.assertTrue(any(message.content == "hello peers" for message in world.messages.values()))

    def test_world_state_persists_ollama_connection_settings(self) -> None:
        world = WorldState(
            selected_model="local-model",
            ollama_base_url="http://ollama.example:11434",
            ollama_api_key="secret",
            ollama_executable_path="/usr/local/bin/ollama",
        )
        restored = WorldState.from_dict(world.to_dict())
        self.assertEqual(restored.ollama_base_url, "http://ollama.example:11434")
        self.assertEqual(restored.ollama_api_key, "secret")
        self.assertEqual(restored.ollama_executable_path, "/usr/local/bin/ollama")

    def test_ollama_client_normalizes_url_and_auth_header(self) -> None:
        client = OllamaClient("http://ollama.example:11434/", api_key=" token ")
        self.assertEqual(client.base_url, "http://ollama.example:11434")
        self.assertEqual(client._headers()["Authorization"], "Bearer token")
        client.configure("http://127.0.0.1:11434/", "")
        self.assertEqual(client.base_url, "http://127.0.0.1:11434")
        self.assertNotIn("Authorization", client._headers())

    def test_world_store_recovers_from_corrupt_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "world_state.json"
            path.write_text("not-json", encoding="utf-8")
            world = WorldStore(path).load()
            self.assertIsInstance(world, WorldState)
            self.assertFalse(path.exists())
            self.assertTrue(path.with_suffix(".corrupt.json").exists())


if __name__ == "__main__":
    unittest.main()
