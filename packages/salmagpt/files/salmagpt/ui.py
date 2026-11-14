"""What you see: rich for output, prompt_toolkit for the input line.
Both are optional; without them SalmaGPT falls back to plain text."""

import os
import sys

from . import config as config_mod

try:
    from rich.console import Console
    from rich.markup import escape
    from rich.panel import Panel
except ModuleNotFoundError:  # plain fallback
    Console = None

ACCENT = "#fab387"
CAT = r""" /\_/\
( ^.^ )
 > ^ <"""

COMMANDS = {
    "/help": "show this",
    "/models": "list connected models",
    "/model NAME": "switch model (the conversation carries over)",
    "/connect": "connect another AI (Claude, OpenAI, OpenRouter, Groq, any OpenAI-compatible server)",
    "/disconnect NAME": "remove a connection",
    "/setup": "download or update the built-in SalmaGPT model",
    "/yolo": "toggle approving every file change and command automatically",
    "/clear": "start a new conversation",
    "/exit": "leave",
}


class UI:
    def __init__(self, interactive=True):
        self.interactive = interactive
        self.console = Console(highlight=False) if Console else None
        self._streaming = False
        self._session = None
        if interactive:
            self._session = self._make_session()

    def _make_session(self):
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.completion import WordCompleter
            from prompt_toolkit.history import FileHistory
        except ModuleNotFoundError:
            return None
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return None
        directory = config_mod.state_dir()
        directory.mkdir(parents=True, exist_ok=True)
        words = [command.split()[0] for command in COMMANDS]
        return PromptSession(history=FileHistory(str(directory / "history")),
                             completer=WordCompleter(words, sentence=True))

    # --- output -------------------------------------------------------------

    def _print(self, text="", style=None):
        if self.console:
            self.console.print(escape(text), style=style)
        else:
            print(text)

    def banner(self, model, cwd):
        if self.console:
            body = (f"[bold {ACCENT}]{escape(CAT)}[/]\n\n[bold]SalmaGPT[/]  coding assistant\n"
                    f"model  [bold]{escape(model)}[/]\ncwd    {escape(cwd)}\n\n"
                    "[dim]/help for commands · Ctrl-C stops a reply · Ctrl-D leaves[/]")
            self.console.print(Panel(body, border_style=ACCENT, expand=False))
        else:
            print(f"{CAT}\nSalmaGPT  model {model}  cwd {cwd}\n/help for commands")

    def stream(self, text):
        self._streaming = True
        sys.stdout.write(text)
        sys.stdout.flush()

    def end_stream(self):
        if self._streaming:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._streaming = False

    def info(self, text):
        self._print(text)

    def notice(self, text):
        self._print(f"! {text}", "yellow")

    def error(self, text):
        self._print(f"error: {text}", "bold red")

    def tool_call(self, summary):
        self._print(f"● {summary}", ACCENT)

    def tool_result(self, output, is_error):
        lines = output.strip().splitlines() or [""]
        shown = lines[0][:120]
        more = f"  (+{len(lines) - 1} lines)" if len(lines) > 1 else ""
        self._print(f"  └ {shown}{more}", "red" if is_error else "dim")

    def help(self):
        for command, what in COMMANDS.items():
            self._print(f"  {command:<18} {what}")

    # --- input --------------------------------------------------------------

    def ask(self, prompt="🐾 > "):
        """Read a line. Raises EOFError on Ctrl-D."""
        if self._session:
            return self._session.prompt(prompt)
        return input(prompt)

    def ask_plain(self, prompt, secret=False):
        if secret and sys.stdin.isatty():
            import getpass
            return getpass.getpass(prompt)
        return input(prompt)

    def approve(self, tool, args):
        """Returns 'yes', 'always', 'no' or 'no:<what the user said instead>'."""
        if not self.interactive:
            return "no:approval is not possible in a non-interactive run (use --yolo)"
        self._preview(tool, args)
        try:
            answer = input("  allow? [y]es / [a]lways / [n]o, or say what to do instead: ").strip()
        except EOFError:
            return "no"
        lowered = answer.lower()
        if lowered in ("", "y", "yes"):
            return "yes"
        if lowered in ("a", "always"):
            return "always"
        if lowered in ("n", "no"):
            return "no"
        return f"no:{answer}"

    def _preview(self, tool, args):
        if tool.name == "run_command":
            self._print(f"  $ {args.get('command', '')}", "bold")
        elif tool.name == "write_file":
            content = str(args.get("content", ""))
            self._print(f"  write {args.get('path')} ({len(content.splitlines())} lines)", "bold")
            self._snippet(content, "green", "+")
        elif tool.name == "edit_file":
            self._print(f"  edit {args.get('path')}", "bold")
            self._snippet(str(args.get("old_text", "")), "red", "-")
            self._snippet(str(args.get("new_text", "")), "green", "+")

    def _snippet(self, text, style, sign, limit=12):
        lines = text.splitlines()
        for line in lines[:limit]:
            self._print(f"  {sign} {line[:160]}", style)
        if len(lines) > limit:
            self._print(f"  {sign} … {len(lines) - limit} more lines", "dim")


def cwd_label():
    cwd, home = os.getcwd(), os.path.expanduser("~")
    return "~" + cwd[len(home):] if cwd == home or cwd.startswith(home + os.sep) else cwd
