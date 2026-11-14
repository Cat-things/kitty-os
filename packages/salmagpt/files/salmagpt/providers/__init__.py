"""Connections to models. Each provider keeps the conversation in the
format its API wants; the agent only sees the small interface in base.py."""

from .base import Provider, ProviderError, ToolCall, ToolResult, Turn


def create(settings, model, api_key):
    kind = settings.get("type")
    if kind == "anthropic":
        from .claude import ClaudeProvider
        return ClaudeProvider(model, api_key)
    if kind == "builtin":
        from .. import local
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(model, local.ollama_url() + "/v1", None)
    if kind == "openai":
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(model, settings.get("base_url", ""), api_key)
    raise ProviderError(f"unknown provider type: {kind}")


__all__ = ["Provider", "ProviderError", "ToolCall", "ToolResult", "Turn", "create"]
