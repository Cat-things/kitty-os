from dataclasses import dataclass, field


class ProviderError(Exception):
    """A failure talking to a model, worded for the person at the keyboard."""


@dataclass
class ToolCall:
    id: str
    name: str
    args: object  # normally a dict; anything else is rejected when the tool runs


@dataclass
class ToolResult:
    call: ToolCall
    output: str
    is_error: bool = False


@dataclass
class Turn:
    text: str = ""
    tool_calls: list = field(default_factory=list)
    note: str = ""  # e.g. the reply was cut off or declined


class Provider:
    """One conversation with one model."""

    def start(self, system, tools, history=()):
        """Begin a conversation. history is earlier (role, text) pairs."""
        raise NotImplementedError

    def add_user(self, text):
        raise NotImplementedError

    def add_tool_results(self, results):
        raise NotImplementedError

    def run(self, on_text):
        """Ask the model for its next turn, streaming text to on_text."""
        raise NotImplementedError
