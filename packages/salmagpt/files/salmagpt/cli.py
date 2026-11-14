"""The salmagpt command."""

import argparse
import sys

from . import __version__, local, providers
from .agent import Agent
from .config import BUILTIN_PROVIDER, PRESETS, Config, ConfigError
from .ui import UI, cwd_label


def make_provider(config, reference):
    name, settings, model = config.resolve(reference)
    if settings["type"] == "builtin":
        try:
            local.ensure_ready()
        except local.LocalError as error:
            raise providers.ProviderError(str(error)) from None
    return f"{name}/{model}", providers.create(settings, model, config.api_key(settings))


def connect(config, ui):
    """Interactive: add a connection to another AI service."""
    names = list(PRESETS)
    for number, name in enumerate(names, 1):
        ui.info(f"  {number}. {PRESETS[name]['label']}")
    choice = ui.ask_plain("Which one? ").strip().lower()
    if choice.isdigit() and 1 <= int(choice) <= len(names):
        choice = names[int(choice) - 1]
    if choice not in PRESETS:
        ui.error("nothing connected: pick a number from the list")
        return None
    preset = PRESETS[choice]
    settings = {"type": preset["type"]}
    name = choice
    if choice == "custom":
        name = ui.ask_plain("Name for this connection (e.g. lmstudio): ").strip().lower()
        if not name or "/" in name or name == BUILTIN_PROVIDER:
            ui.error("nothing connected: the name must be a single word, and not 'local'")
            return None
        settings["base_url"] = ui.ask_plain("Server URL (e.g. http://localhost:1234/v1): ").strip()
    elif "base_url" in preset:
        settings["base_url"] = preset["base_url"]

    variable = preset.get("api_key_env")
    hint = f" (Enter to use ${variable} from the environment)" if variable else " (Enter for none)"
    key = ui.ask_plain(f"API key{hint}: ", secret=True).strip()
    if key:
        settings["api_key"] = key
    elif variable:
        settings["api_key_env"] = variable

    api_key = config.api_key(settings)
    try:
        if settings["type"] == "anthropic":
            from .providers import claude
            available = claude.list_models(api_key)
        else:
            from .providers import openai_compat
            available = openai_compat.list_models(settings["base_url"], api_key)
    except providers.ProviderError as error:
        ui.notice(f"Could not list models ({error}). You can still type a model name.")
        available = []
    if available:
        ui.info("Available: " + ", ".join(available[:40])
                + (f" … and {len(available) - 40} more" if len(available) > 40 else ""))
    suggestion = preset.get("suggest", "")
    typed = ui.ask_plain(f"Model(s) to add, separated by spaces"
                         f"{f' [{suggestion}]' if suggestion else ''}: ").split()
    models = typed or ([suggestion] if suggestion else [])
    if not models:
        ui.error("nothing connected: no model given")
        return None
    settings["models"] = models
    config.providers[name] = settings
    config.save()
    ui.info(f"Connected {name}. Switch with: /model {name}/{models[0]}")
    return f"{name}/{models[0]}"


def setup_builtin(ui):
    try:
        local.setup(say=ui.info)
        return True
    except local.LocalError as error:
        ui.error(str(error))
        return False


class Session:
    def __init__(self, config, ui, auto_approve):
        self.config = config
        self.ui = ui
        self.agent = None
        self.model = None
        self.auto_approve = auto_approve

    def use(self, reference):
        try:
            label, provider = make_provider(self.config, reference)
        except (ConfigError, providers.ProviderError) as error:
            self.ui.error(str(error))
            return False
        if self.agent is None:
            self.agent = Agent(provider, self.ui, self.auto_approve)
            self.agent.start()
        else:
            self.agent.switch(provider)
        self.model = label
        return True

    def command(self, line):
        """Handle a /command. Returns False to leave."""
        word, _, rest = line.partition(" ")
        rest = rest.strip()
        ui = self.ui
        if word in ("/exit", "/quit"):
            return False
        if word == "/help":
            ui.help()
        elif word == "/models":
            for model in self.config.models():
                ui.info(f"{'*' if model == self.model else ' '} {model}")
            ui.info("Add more with /connect.")
        elif word == "/model":
            if not rest:
                ui.info(f"Current model: {self.model or 'none'}. Usage: /model NAME")
            elif self.use(rest):
                self.config.default_model = self.model
                self.config.save()
                ui.info(f"Now using {self.model}.")
        elif word == "/connect":
            try:
                added = connect(self.config, ui)
            except (EOFError, KeyboardInterrupt):
                ui.info("\nCancelled.")
                added = None
            if added and self.use(added):
                self.config.default_model = self.model
                self.config.save()
                ui.info(f"Now using {self.model}.")
        elif word == "/disconnect":
            if rest == BUILTIN_PROVIDER or rest not in self.config.providers:
                ui.error("usage: /disconnect NAME (see /models; 'local' stays)")
            else:
                del self.config.providers[rest]
                if self.config.default_model.startswith(rest + "/"):
                    self.config.default_model = ""
                self.config.save()
                self.config = Config.load()
                ui.info(f"Disconnected {rest}.")
        elif word == "/setup":
            if setup_builtin(ui) and self.agent is None:
                self.use(self.config.default_model)
        elif word == "/yolo":
            self.auto_approve = not self.auto_approve
            if self.agent:
                self.agent.auto_approve = self.auto_approve
            ui.info("Auto-approve is ON: changes and commands run without asking."
                    if self.auto_approve else "Auto-approve is off.")
        elif word == "/clear":
            if self.agent:
                self.agent.clear()
            ui.info("New conversation.")
        else:
            ui.error(f"unknown command {word}. Try /help")
        return True

    def say(self, text):
        if self.agent is None and not self.use(self.config.default_model):
            return False
        try:
            self.agent.send(text)
            return True
        except providers.ProviderError as error:
            self.ui.end_stream()
            self.ui.error(str(error))
        except KeyboardInterrupt:
            self.ui.end_stream()
            self.ui.notice("Interrupted.")
        return False


def repl(session):
    ui = session.ui
    ui.banner(session.config.default_model, cwd_label())
    if not session.use(session.config.default_model):
        ui.info("Run /setup for the free built-in model, or /connect to add another AI.")
    while True:
        try:
            line = ui.ask().strip()
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        if not line:
            continue
        if line.startswith("/"):
            if not session.command(line):
                break
        else:
            session.say(line)
    ui.info("bye 🐾")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="salmagpt",
        description="A coding assistant for your terminal. Connect several AIs, or use "
                    "the built-in SalmaGPT model that runs on your own hardware for free.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-m", "--model", help="model to use, e.g. salmagpt or claude/claude-opus-5-5")
    parser.add_argument("-p", "--print", dest="prompt", metavar="PROMPT",
                        help="answer one prompt and exit (no chat)")
    parser.add_argument("--yolo", action="store_true",
                        help="approve every file change and command automatically")
    parser.add_argument("command", nargs="?", choices=("setup", "models", "connect"),
                        help="setup: get the built-in model; models: list; connect: add an AI")
    args = parser.parse_args(argv)

    try:
        config = Config.load()
    except ConfigError as error:
        print(f"salmagpt: {error}", file=sys.stderr)
        return 2
    if args.model:
        config.default_model = args.model
    ui = UI(interactive=args.prompt is None)
    session = Session(config, ui, args.yolo)

    try:
        if args.command == "setup":
            return 0 if setup_builtin(ui) else 1
        if args.command == "models":
            print("\n".join(config.models()))
            return 0
        if args.command == "connect":
            return 0 if connect(config, ui) else 1
        if args.prompt is not None:
            return 0 if session.say(args.prompt) else 1
        return repl(session)
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
