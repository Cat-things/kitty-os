"""Any server that speaks the OpenAI chat completions API: OpenAI,
OpenRouter, Groq, Ollama, llama.cpp, LM Studio, vLLM and many more."""

import json
import urllib.error
import urllib.request

from .base import Provider, ProviderError, ToolCall, Turn

TIMEOUT = 600


def _request(url, api_key, body=None):
    headers = {"Content-Type": "application/json", "User-Agent": "salmagpt"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(body).encode() if body is not None else None
    return urllib.request.Request(url, data=data, headers=headers)


def _explain(error, url):
    if isinstance(error, urllib.error.HTTPError):
        detail = error.read().decode(errors="replace")[:500]
        try:
            detail = json.loads(detail)["error"]
            detail = detail.get("message", detail) if isinstance(detail, dict) else detail
        except (ValueError, KeyError, TypeError):
            pass
        if error.code in (401, 403):
            return f"the server rejected the API key ({error.code}): {detail}"
        if error.code == 404:
            return f"not found (404). Check the model name and URL: {detail}"
        if error.code == 429:
            return f"rate limited or out of credit (429): {detail}"
        return f"server error {error.code}: {detail}"
    reason = getattr(error, "reason", error)
    return f"cannot reach {url}: {reason}"


def list_models(base_url, api_key):
    url = base_url.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(_request(url, api_key), timeout=20) as response:
            data = json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise ProviderError(_explain(error, url)) from None
    return sorted(item["id"] for item in data.get("data", []) if "id" in item)


class OpenAICompatProvider(Provider):
    def __init__(self, model, base_url, api_key):
        if not base_url:
            raise ProviderError("this connection has no URL; run /connect again")
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.messages = []
        self.tools = []

    def start(self, system, tools, history=()):
        self.messages = [{"role": "system", "content": system}]
        self.messages += [{"role": role, "content": text} for role, text in history]
        self.tools = [{"type": "function",
                       "function": {"name": tool.name, "description": tool.description,
                                    "parameters": tool.parameters}} for tool in tools]

    def add_user(self, text):
        self.messages.append({"role": "user", "content": text})

    def add_tool_results(self, results):
        for result in results:
            self.messages.append({"role": "tool", "tool_call_id": result.call.id,
                                  "content": result.output})

    def run(self, on_text):
        body = {"model": self.model, "messages": self.messages, "stream": True}
        if self.tools:
            body["tools"] = self.tools
        text, calls, finish = [], {}, None
        try:
            with urllib.request.urlopen(_request(self.url, self.api_key, body),
                                        timeout=TIMEOUT) as response:
                for raw in response:
                    line = raw.decode(errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except ValueError:
                        continue
                    if chunk.get("error"):
                        error = chunk["error"]
                        raise ProviderError(str(error.get("message", error))
                                            if isinstance(error, dict) else str(error))
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            text.append(delta["content"])
                            on_text(delta["content"])
                        for part in delta.get("tool_calls") or []:
                            slot = calls.setdefault(part.get("index", 0),
                                                    {"id": "", "name": "", "arguments": ""})
                            function = part.get("function") or {}
                            slot["id"] = part.get("id") or slot["id"]
                            slot["name"] += function.get("name") or ""
                            slot["arguments"] += function.get("arguments") or ""
                        finish = choice.get("finish_reason") or finish
        except (urllib.error.URLError, OSError) as error:
            raise ProviderError(_explain(error, self.url)) from None

        turn = Turn(text="".join(text))
        message = {"role": "assistant", "content": turn.text or None}
        if calls:
            message["tool_calls"] = []
            for index in sorted(calls):
                slot = calls[index]
                slot["id"] = slot["id"] or f"call_{len(self.messages)}_{index}"
                try:
                    args = json.loads(slot["arguments"] or "{}")
                except ValueError:
                    args = None  # reported back to the model as a tool error
                turn.tool_calls.append(ToolCall(slot["id"], slot["name"], args))
                message["tool_calls"].append({
                    "id": slot["id"], "type": "function",
                    "function": {"name": slot["name"],
                                 "arguments": slot["arguments"] if args is not None else "{}"}})
        if finish == "length":
            turn.note = "The reply was cut off because it hit the model's length limit."
        elif finish == "content_filter":
            turn.note = "The provider's content filter stopped the reply."
        self.messages.append(message)
        return turn
