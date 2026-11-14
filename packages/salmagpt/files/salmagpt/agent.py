"""The agent loop: model turn, run the tools it asked for, repeat."""

import os
import platform

from . import tools as tools_mod
from .providers import ToolResult

MAX_STEPS = 60

SYSTEM_PROMPT = """You are SalmaGPT, a coding assistant working in the user's terminal. \
You are named after Salma, a cat, and you may be a little cat-like in tone, but the \
work comes first: be direct, accurate and brief.

You work on the user's machine through tools: read_file, list_dir, search, \
write_file, edit_file and run_command. Use them instead of guessing. Read a file \
before you change it, make the smallest change that does the job, and run the \
project's tests or the program itself to check your work when you can. The user is \
asked to approve file changes and commands, so a refusal from them is feedback, not \
an error: adjust or ask.

If the request is unclear, ask one short question. When you finish, say what you \
changed and how you checked it, and say plainly if something is unverified or failed.

Working directory: {cwd}
System: {system}
"""


def system_prompt():
    return SYSTEM_PROMPT.format(cwd=os.getcwd(),
                                system=f"{platform.system()} {platform.machine()}")


class Agent:
    def __init__(self, provider, ui, auto_approve=False, tools=tools_mod.TOOLS):
        self.provider = provider
        self.ui = ui
        self.auto_approve = auto_approve
        self.tools = {tool.name: tool for tool in tools}
        self.always = set()   # tool names approved for the rest of the session
        self.history = []     # (role, text), to carry over when the model changes

    def start(self):
        self.provider.start(system_prompt(), list(self.tools.values()), self.history)

    def switch(self, provider):
        self.provider = provider
        self.start()

    def clear(self):
        self.history = []
        self.start()

    def send(self, text):
        """Run one user request to completion. Returns the final text."""
        self.provider.add_user(text)
        self.history.append(("user", text))
        said = []
        for _ in range(MAX_STEPS):
            turn = self.provider.run(self.ui.stream)
            self.ui.end_stream()
            if turn.text:
                said.append(turn.text)
            if turn.note:
                self.ui.notice(turn.note)
            if not turn.tool_calls:
                break
            self.provider.add_tool_results(self._run_tools(turn.tool_calls))
        else:
            self.ui.notice(f"Stopped after {MAX_STEPS} steps. Say 'continue' to keep going.")
        final = "\n\n".join(said)
        if final:
            self.history.append(("assistant", final))
        return final

    def _run_tools(self, calls):
        """Every call gets a result, even after Ctrl-C, so the conversation
        stays valid for the provider."""
        results, interrupted = [], False
        for call in calls:
            if interrupted:
                results.append(ToolResult(call, "Not run: the user interrupted.", True))
                continue
            try:
                results.append(self._run_tool(call))
            except KeyboardInterrupt:
                interrupted = True
                results.append(ToolResult(call, "Interrupted by the user.", True))
        if interrupted:
            self.provider.add_tool_results(results)
            raise KeyboardInterrupt
        return results

    def _run_tool(self, call):
        tool = self.tools.get(call.name)
        if tool is None:
            return ToolResult(call, f"There is no tool called {call.name}.", True)
        if not isinstance(call.args, dict):
            return ToolResult(call, "The tool arguments were not valid JSON.", True)
        self.ui.tool_call(tool.summary(call.args))
        if tool.needs_approval and not self.auto_approve and tool.name not in self.always:
            answer = self.ui.approve(tool, call.args)
            if answer == "always":
                self.always.add(tool.name)
            elif answer != "yes":
                reason = f" They said: {answer[3:]}" if answer.startswith("no:") else ""
                self.ui.tool_result("declined", True)
                return ToolResult(call, f"The user declined this.{reason}", True)
        try:
            output = tools_mod.call(tool, call.args)
        except tools_mod.ToolError as error:
            self.ui.tool_result(str(error), True)
            return ToolResult(call, f"Error: {error}", True)
        self.ui.tool_result(output, False)
        return ToolResult(call, output)
