"""Settings: which AIs are connected and which model is in use.

Stored as JSON in ~/.config/salmagpt/config.json, readable only by you
because it can hold API keys.
"""

import json
import os
from pathlib import Path

BUILTIN_PROVIDER = "local"
BUILTIN_MODEL = "salmagpt"
DEFAULT_MODEL = f"{BUILTIN_PROVIDER}/{BUILTIN_MODEL}"

# Services offered by /connect. "openai" means any OpenAI-compatible API.
PRESETS = {
    "anthropic": {"type": "anthropic", "label": "Anthropic (Claude)",
                  "api_key_env": "ANTHROPIC_API_KEY", "suggest": "claude-opus-5-5"},
    "openai": {"type": "openai", "label": "OpenAI",
               "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
    "openrouter": {"type": "openai", "label": "OpenRouter",
                   "base_url": "https://openrouter.ai/api/v1",
                   "api_key_env": "OPENROUTER_API_KEY"},
    "groq": {"type": "openai", "label": "Groq",
             "base_url": "https://api.groq.com/openai/v1", "api_key_env": "GROQ_API_KEY"},
    "custom": {"type": "openai", "label": "Other OpenAI-compatible server "
               "(Ollama, llama.cpp, LM Studio, vLLM, ...)"},
}


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "salmagpt" / "config.json"


def state_dir():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "salmagpt"


class Config:
    def __init__(self, data=None):
        data = data or {}
        self.default_model = data.get("default_model") or DEFAULT_MODEL
        self.providers = dict(data.get("providers") or {})
        # The built-in model is always there and cannot be removed.
        self.providers[BUILTIN_PROVIDER] = {"type": "builtin", "models": [BUILTIN_MODEL]}

    @classmethod
    def load(cls):
        try:
            return cls(json.loads(config_path().read_text()))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as error:
            raise ConfigError(f"cannot read {config_path()}: {error}") from error

    def save(self):
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        providers = {name: value for name, value in self.providers.items()
                     if name != BUILTIN_PROVIDER}
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump({"default_model": self.default_model, "providers": providers},
                      handle, indent=2)
            handle.write("\n")
        tmp.replace(path)

    def models(self):
        """Every usable model as 'provider/model'."""
        found = []
        for name, provider in self.providers.items():
            found.extend(f"{name}/{model}" for model in provider.get("models", []))
        return found

    def resolve(self, reference):
        """Turn what the user typed into (provider name, settings, model)."""
        reference = reference.strip()
        if reference == BUILTIN_MODEL:
            reference = DEFAULT_MODEL
        if "/" in reference:
            name, model = reference.split("/", 1)
            if name in self.providers and model:
                return name, self.providers[name], model
        matches = [full for full in self.models() if full.split("/", 1)[1] == reference]
        if len(matches) == 1:
            name, model = matches[0].split("/", 1)
            return name, self.providers[name], model
        if len(matches) > 1:
            raise ConfigError(f"'{reference}' is ambiguous: {', '.join(matches)}")
        raise ConfigError(f"unknown model '{reference}'. See /models, or add one with /connect")

    def api_key(self, provider):
        if provider.get("api_key"):
            return provider["api_key"]
        variable = provider.get("api_key_env")
        return os.environ.get(variable) if variable else None


class ConfigError(Exception):
    pass
