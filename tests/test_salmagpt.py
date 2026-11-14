import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "packages/salmagpt/files"))

from salmagpt import cli, local, tools
from salmagpt.agent import Agent
from salmagpt.config import Config, ConfigError
from salmagpt.providers import ProviderError, ToolCall, ToolResult
from salmagpt.providers.openai_compat import OpenAICompatProvider, list_models

TOOL = {tool.name: tool for tool in tools.TOOLS}


class QuietUI:
    """Stands in for the terminal and remembers what happened."""

    interactive = False

    def __init__(self, answers=()):
        self.text, self.calls, self.results, self.notices = [], [], [], []
        self.answers = list(answers)

    def stream(self, text):
        self.text.append(text)

    def end_stream(self):
        pass

    def notice(self, text):
        self.notices.append(text)

    info = error = notice

    def tool_call(self, summary):
        self.calls.append(summary)

    def tool_result(self, output, is_error):
        self.results.append((output, is_error))

    def approve(self, tool, args):
        return self.answers.pop(0)


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        patcher = mock.patch.dict(os.environ, {
            "XDG_CONFIG_HOME": str(self.tmp / "config"),
            "XDG_STATE_HOME": str(self.tmp / "state")})
        patcher.start()
        self.addCleanup(patcher.stop)


class ToolsTest(TempDirTest):
    def test_write_read_edit(self):
        self.assertIn("Created", tools.call(TOOL["write_file"], {"path": "a/b.py", "content": "x = 1\ny = 2\n"}))
        self.assertEqual(tools.call(TOOL["read_file"], {"path": "a/b.py"}), "    1  x = 1\n    2  y = 2")
        tools.call(TOOL["edit_file"], {"path": "a/b.py", "old_text": "y = 2", "new_text": "y = 3"})
        self.assertEqual(Path("a/b.py").read_text(), "x = 1\ny = 3\n")

    def test_read_window(self):
        Path("big.txt").write_text("".join(f"line {i}\n" for i in range(1, 51)))
        out = tools.call(TOOL["read_file"], {"path": "big.txt", "offset": 10, "limit": 2})
        self.assertIn("   10  line 10\n   11  line 11", out)
        self.assertIn("showing lines 10-11 of 50", out)

    def test_edit_must_be_exact_and_unique(self):
        Path("f.txt").write_text("cat\ncat\n")
        with self.assertRaisesRegex(tools.ToolError, "not found"):
            tools.call(TOOL["edit_file"], {"path": "f.txt", "old_text": "dog", "new_text": "x"})
        with self.assertRaisesRegex(tools.ToolError, "appears 2 times"):
            tools.call(TOOL["edit_file"], {"path": "f.txt", "old_text": "cat", "new_text": "x"})
        tools.call(TOOL["edit_file"], {"path": "f.txt", "old_text": "cat", "new_text": "x", "replace_all": True})
        self.assertEqual(Path("f.txt").read_text(), "x\nx\n")

    def test_search_and_list(self):
        Path("src").mkdir()
        Path("src/app.py").write_text("def meow():\n    return 'meo-meo-meow'\n")
        Path("notes.md").write_text("meow\n")
        Path(".git").mkdir()
        Path(".git/config").write_text("meow\n")
        out = tools.call(TOOL["search"], {"pattern": "meow", "glob": "*.py"})
        self.assertEqual(out.splitlines(), ["src/app.py:1: def meow():", "src/app.py:2:     return 'meo-meo-meow'"])
        self.assertNotIn(".git", tools.call(TOOL["search"], {"pattern": "meow"}))
        self.assertEqual(tools.call(TOOL["list_dir"], {}), ".git/\nsrc/\nnotes.md")
        self.assertEqual(tools.call(TOOL["search"], {"pattern": "woof"}), "No matches.")

    def test_run_command(self):
        self.assertEqual(tools.call(TOOL["run_command"], {"command": "echo hi; exit 3"}), "hi\n[exit code 3]")
        with self.assertRaisesRegex(tools.ToolError, "stopped after 1 seconds"):
            tools.call(TOOL["run_command"], {"command": "sleep 5", "timeout": 1})

    def test_arguments_are_checked(self):
        for args, message in (({}, "missing argument: path"),
                              ({"path": 3}, "must be a string"),
                              ({"path": "x", "nope": 1}, "unknown argument"),
                              ({"path": "x", "offset": True}, "must be a integer"),
                              ("oops", "JSON object")):
            with self.assertRaisesRegex(tools.ToolError, message):
                tools.call(TOOL["read_file"], args)
        with self.assertRaisesRegex(tools.ToolError, "cannot read"):
            tools.call(TOOL["read_file"], {"path": "missing.txt"})

    def test_long_output_is_clipped_with_a_note(self):
        clipped = tools.clip("a" * 100_000)
        self.assertLess(len(clipped), 31_000)
        self.assertIn("characters left out", clipped)


class ConfigTest(TempDirTest):
    def test_builtin_model_is_the_default(self):
        config = Config.load()
        self.assertEqual(config.models(), ["local/salmagpt"])
        self.assertEqual(config.resolve("salmagpt")[2], "salmagpt")
        self.assertEqual(config.resolve(config.default_model)[1]["type"], "builtin")

    def test_save_and_resolve(self):
        config = Config.load()
        config.providers["claude"] = {"type": "anthropic", "api_key": "secret", "models": ["claude-opus-5-5"]}
        config.providers["groq"] = {"type": "openai", "base_url": "http://x/v1",
                                    "api_key_env": "TEST_GROQ_KEY", "models": ["m1", "claude-opus-5-5"]}
        config.default_model = "claude/claude-opus-5-5"
        config.save()
        path = self.tmp / "config/salmagpt/config.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("local", json.loads(path.read_text())["providers"])
        loaded = Config.load()
        self.assertEqual(loaded.default_model, "claude/claude-opus-5-5")
        self.assertEqual(loaded.resolve("m1")[0], "groq")
        self.assertEqual(loaded.api_key(loaded.providers["claude"]), "secret")
        with mock.patch.dict(os.environ, {"TEST_GROQ_KEY": "from-env"}):
            self.assertEqual(loaded.api_key(loaded.providers["groq"]), "from-env")
        with self.assertRaisesRegex(ConfigError, "ambiguous"):
            loaded.resolve("claude-opus-5-5")
        with self.assertRaisesRegex(ConfigError, "unknown model"):
            loaded.resolve("gpt-9000")


class FakeServer:
    """A tiny OpenAI-compatible server that replays scripted streams."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self._send(200, "application/json", json.dumps({"data": [{"id": "b"}, {"id": "a"}]}))

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((dict(self.headers), body))
                reply = outer.replies.pop(0)
                if isinstance(reply, int):
                    self._send(reply, "application/json", json.dumps({"error": {"message": "bad key"}}))
                    return
                lines = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in reply) + "data: [DONE]\n\n"
                self._send(200, "text/event-stream", lines)

            def _send(self, status, kind, text):
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def text_chunks(*parts, finish="stop"):
    chunks = [{"choices": [{"delta": {"content": part}}]} for part in parts]
    return chunks + [{"choices": [{"delta": {}, "finish_reason": finish}]}]


def tool_chunks(name, args, call_id="call_1"):
    encoded = json.dumps(args)
    half = len(encoded) // 2
    return [
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": call_id, "type": "function",
                                                 "function": {"name": name, "arguments": ""}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": encoded[:half]}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": encoded[half:]}}]}}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    ]


class AgentTest(TempDirTest):
    def serve(self, *replies):
        server = FakeServer(replies)
        self.addCleanup(server.close)
        return server

    def agent(self, server, ui, **kwargs):
        agent = Agent(OpenAICompatProvider("test-model", server.url, "sk-test"), ui, **kwargs)
        agent.start()
        return agent

    def test_tool_loop(self):
        server = self.serve(
            tool_chunks("write_file", {"path": "hello.py", "content": "print('meow')\n"}),
            tool_chunks("run_command", {"command": "python3 hello.py"}, "call_2"),
            text_chunks("Done: ", "it prints meow."))
        ui = QuietUI()
        final = self.agent(server, ui, auto_approve=True).send("write hello.py and run it")
        self.assertEqual(final, "Done: it prints meow.")
        self.assertEqual("".join(ui.text), "Done: it prints meow.")
        self.assertEqual(Path("hello.py").read_text(), "print('meow')\n")
        self.assertEqual(ui.results[1], ("meow\n[exit code 0]", False))

        headers, first = server.requests[0]
        self.assertEqual(headers["Authorization"], "Bearer sk-test")
        self.assertEqual(first["model"], "test-model")
        self.assertEqual([m["role"] for m in first["messages"]], ["system", "user"])
        self.assertEqual(len(first["tools"]), len(tools.TOOLS))
        last = server.requests[2][1]["messages"]
        self.assertEqual([m["role"] for m in last],
                         ["system", "user", "assistant", "tool", "assistant", "tool"])
        self.assertEqual(last[3], {"role": "tool", "tool_call_id": "call_1", "content": "Created hello.py (1 lines)"})
        self.assertEqual(last[2]["tool_calls"][0]["function"]["name"], "write_file")

    def test_declined_change_is_not_made(self):
        server = self.serve(tool_chunks("write_file", {"path": "x.txt", "content": "x"}),
                            text_chunks("Okay, leaving it."))
        ui = QuietUI(answers=["no:use y.txt instead"])
        self.agent(server, ui).send("make x.txt")
        self.assertFalse(Path("x.txt").exists())
        self.assertEqual(server.requests[1][1]["messages"][-1]["content"],
                         "The user declined this. They said: use y.txt instead")

    def test_always_approves_the_rest_of_the_session(self):
        server = self.serve(tool_chunks("write_file", {"path": "1.txt", "content": "1"}),
                            tool_chunks("write_file", {"path": "2.txt", "content": "2"}, "call_2"),
                            text_chunks("ok"))
        self.agent(server, QuietUI(answers=["always"])).send("go")
        self.assertTrue(Path("1.txt").exists() and Path("2.txt").exists())

    def test_reading_needs_no_approval(self):
        Path("r.txt").write_text("hi\n")
        server = self.serve(tool_chunks("read_file", {"path": "r.txt"}), text_chunks("ok"))
        self.agent(server, QuietUI()).send("read it")  # would fail on approve() otherwise

    def test_bad_tool_calls_go_back_as_errors(self):
        broken = [{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {
            "name": "read_file", "arguments": "{not json"}}]}}]}]
        server = self.serve(broken, tool_chunks("fly", {}, "c2"),
                            tool_chunks("read_file", {"path": "nope.txt"}, "c3"), text_chunks("ok"))
        self.agent(server, QuietUI()).send("go")
        contents = [m["content"] for m in server.requests[-1][1]["messages"] if m["role"] == "tool"]
        self.assertEqual(contents[0], "The tool arguments were not valid JSON.")
        self.assertEqual(contents[1], "There is no tool called fly.")
        self.assertIn("cannot read nope.txt", contents[2])

    def test_switching_model_keeps_the_conversation(self):
        first, second = self.serve(text_chunks("I am one.")), self.serve(text_chunks("I am two."))
        agent = self.agent(first, QuietUI())
        agent.send("who are you?")
        agent.switch(OpenAICompatProvider("other", second.url, None))
        agent.send("and now?")
        sent = second.requests[0][1]["messages"]
        self.assertEqual([(m["role"], m["content"]) for m in sent[1:]],
                         [("user", "who are you?"), ("assistant", "I am one."), ("user", "and now?")])
        self.assertNotIn("Authorization", second.requests[0][0])

    def test_errors_are_explained(self):
        server = self.serve(401)
        with self.assertRaisesRegex(ProviderError, "rejected the API key.*bad key"):
            self.agent(server, QuietUI()).send("hi")
        dead = Agent(OpenAICompatProvider("m", "http://127.0.0.1:9/v1", None), QuietUI())
        dead.start()
        with self.assertRaisesRegex(ProviderError, "cannot reach"):
            dead.send("hi")

    def test_cut_off_reply_is_reported(self):
        ui = QuietUI()
        self.agent(self.serve(text_chunks("half an ans", finish="length")), ui).send("hi")
        self.assertIn("cut off", ui.notices[0])

    def test_list_models(self):
        self.assertEqual(list_models(self.serve().url, None), ["a", "b"])

    def test_one_shot_cli(self):
        server = self.serve(text_chunks("meow"))
        config = Config.load()
        config.providers["fake"] = {"type": "openai", "base_url": server.url, "models": ["m"]}
        config.save()
        with mock.patch("sys.stdout.write"):
            self.assertEqual(cli.main(["-m", "fake/m", "-p", "say meow"]), 0)
        self.assertEqual(server.requests[0][1]["messages"][-1]["content"], "say meow")


class ClaudeProviderTest(unittest.TestCase):
    """The Claude provider against a stand-in for the SDK client."""

    def provider(self, *messages):
        try:
            from salmagpt.providers.claude import ClaudeProvider
            provider = ClaudeProvider("claude-opus-5-5", "sk-ant-test")
        except ProviderError:
            self.skipTest("the anthropic SDK is not installed")
        queue, self.sent = list(messages), []

        class Stream:
            def __init__(self, message):
                self.message = message
                self.text_stream = [b.text for b in message.content if b.type == "text"]

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get_final_message(self):
                return self.message

        def stream(**kwargs):
            self.sent.append({**kwargs, "messages": list(kwargs["messages"])})
            return Stream(queue.pop(0))

        provider.client = SimpleNamespace(messages=SimpleNamespace(stream=stream))
        provider.start("system text", tools.TOOLS)
        return provider

    @staticmethod
    def message(stop_reason, *blocks):
        return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))

    def test_tool_round_trip(self):
        thinking = SimpleNamespace(type="thinking", thinking="")
        use = SimpleNamespace(type="tool_use", id="toolu_1", name="list_dir", input={"path": "."})
        first = self.message("tool_use", thinking, SimpleNamespace(type="text", text="Looking."), use)
        provider = self.provider(first, self.message("end_turn", SimpleNamespace(type="text", text="Done.")))
        provider.add_user("what is here?")
        heard = []
        turn = provider.run(heard.append)
        self.assertEqual((turn.text, heard), ("Looking.", ["Looking."]))
        self.assertEqual(turn.tool_calls, [ToolCall("toolu_1", "list_dir", {"path": "."})])
        provider.add_tool_results([ToolResult(turn.tool_calls[0], "a.py"),])
        self.assertEqual(provider.run(heard.append).text, "Done.")

        request = self.sent[0]
        self.assertEqual((request["model"], request["system"]), ("claude-opus-5-5", "system text"))
        self.assertEqual(request["tools"][0], {"name": "read_file", "description": tools.TOOLS[0].description,
                                               "input_schema": tools.TOOLS[0].parameters})
        second = self.sent[1]["messages"]
        self.assertIs(second[1]["content"], first.content)  # thinking block goes back untouched
        self.assertEqual(second[2], {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "a.py", "is_error": False}]})

    def test_refusal_and_cut_off(self):
        use = SimpleNamespace(type="tool_use", id="toolu_9", name="write_file", input={})
        provider = self.provider(self.message("refusal"), self.message("max_tokens", use))
        provider.add_user("hi")
        declined = provider.run(lambda text: None)
        self.assertIn("declined", declined.note)
        self.assertEqual(len(provider.messages), 1)
        cut = provider.run(lambda text: None)
        self.assertEqual(cut.tool_calls, [])
        self.assertIn("cut off", cut.note)
        self.assertEqual(provider.messages[-1]["content"][0]["tool_use_id"], "toolu_9")


class LocalModelTest(unittest.TestCase):
    def test_base_model_fits_the_memory(self):
        with mock.patch.dict(os.environ, clear=False):
            os.environ.pop("SALMAGPT_BASE_MODEL", None)
            self.assertEqual(local.pick_base(32)[0], "qwen2.5-coder:7b")
            self.assertEqual(local.pick_base(8)[0], "qwen2.5-coder:1.5b")
            os.environ["SALMAGPT_BASE_MODEL"] = "mine:latest"
            self.assertEqual(local.pick_base(32)[0], "mine:latest")

    def test_ollama_url(self):
        with mock.patch.dict(os.environ, {"OLLAMA_HOST": "10.0.0.5:1234"}):
            self.assertEqual(local.ollama_url(), "http://10.0.0.5:1234")

    def test_missing_ollama_is_explained(self):
        with mock.patch.object(local, "installed", return_value=False), \
                mock.patch.object(local, "server_running", return_value=False):
            with self.assertRaisesRegex(local.LocalError, "pacman -S ollama"):
                local.ensure_ready()


if __name__ == "__main__":
    unittest.main()
