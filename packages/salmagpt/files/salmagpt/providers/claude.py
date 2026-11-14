"""Claude, through the official Anthropic SDK."""

from .base import Provider, ProviderError, ToolCall, Turn

MAX_TOKENS = 64000


def _sdk():
    try:
        import anthropic
    except ModuleNotFoundError:
        raise ProviderError(
            "Claude needs the Anthropic Python SDK: pip install anthropic") from None
    return anthropic


def list_models(api_key):
    anthropic = _sdk()
    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        return sorted(model.id for model in client.models.list())
    except anthropic.APIError as error:
        raise ProviderError(_explain(anthropic, error)) from None


def _explain(anthropic, error):
    if isinstance(error, anthropic.AuthenticationError):
        return "Anthropic rejected the API key. Run /connect to set a new one."
    if isinstance(error, anthropic.PermissionDeniedError):
        return f"this key may not use that model: {error.message}"
    if isinstance(error, anthropic.NotFoundError):
        return f"Anthropic does not know that model: {error.message}"
    if isinstance(error, anthropic.RateLimitError):
        return "rate limited by Anthropic. Wait a moment and try again."
    if isinstance(error, anthropic.APIStatusError):
        return f"Anthropic API error {error.status_code}: {error.message}"
    if isinstance(error, anthropic.APIConnectionError):
        return "cannot reach the Anthropic API. Check your connection."
    return f"Anthropic API error: {error}"


class ClaudeProvider(Provider):
    def __init__(self, model, api_key):
        self.anthropic = _sdk()
        # Without a key here, the SDK finds credentials itself (environment
        # variables, or a profile from `ant auth login`).
        try:
            self.client = (self.anthropic.Anthropic(api_key=api_key) if api_key
                           else self.anthropic.Anthropic())
        except self.anthropic.AnthropicError as error:
            raise ProviderError(f"no Anthropic credentials: {error}. Run /connect.") from None
        self.model = model
        self.system = ""
        self.tools = []
        self.messages = []

    def start(self, system, tools, history=()):
        self.system = system
        self.tools = [{"name": tool.name, "description": tool.description,
                       "input_schema": tool.parameters} for tool in tools]
        self.messages = [{"role": role, "content": text} for role, text in history]

    def add_user(self, text):
        self.messages.append({"role": "user", "content": text})

    def add_tool_results(self, results):
        # Every result of a turn goes back in one user message.
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": result.call.id,
             "content": result.output, "is_error": result.is_error}
            for result in results]})

    def run(self, on_text):
        try:
            with self.client.messages.stream(
                    model=self.model, max_tokens=MAX_TOKENS, system=self.system,
                    tools=self.tools, messages=self.messages,
                    cache_control={"type": "ephemeral"}) as stream:
                for text in stream.text_stream:
                    on_text(text)
                message = stream.get_final_message()
        except self.anthropic.APIError as error:
            raise ProviderError(_explain(self.anthropic, error)) from None

        turn = Turn(text="".join(b.text for b in message.content if b.type == "text"))
        if message.stop_reason == "refusal":
            turn.note = "Claude declined this request."
            return turn  # nothing is kept from a declined turn
        # Keep the whole content, not just the text: thinking and tool_use
        # blocks must go back unchanged on the next request.
        self.messages.append({"role": "assistant", "content": message.content})
        if message.stop_reason == "max_tokens":
            turn.note = "The reply was cut off because it hit the output limit."
            # A cut-off tool call is incomplete; answer it rather than run it.
            pending = [b for b in message.content if b.type == "tool_use"]
            if pending:
                self.messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                     "content": "Not run: the reply was cut off."} for block in pending]})
            return turn
        turn.tool_calls = [ToolCall(block.id, block.name, block.input)
                           for block in message.content if block.type == "tool_use"]
        return turn
