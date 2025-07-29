
"""chat_types.py

Auto‑generated Python translation of several Java classes:

- ChatCompletion
- ChatMessage (+ nested Author)
- MessagePart (interface)
- TextPart
- ToolCall (with fluent Builder)
- ToolCallResult
- FinishReason (nested in ChatCompletion)

The implementation follows the translation guidelines supplied:
* CamelCase → snake_case for identifiers.
* Lombok‑generated boiler‑plate is made explicit.
* Overloaded constructors mapped to a single __init__ with @overload helpers.
* Builder patterns translated into fluent interfaces.
* Java RuntimeException / IllegalArgumentException mapped to Python RuntimeError / ValueError.
* Logging uses Python’s stdlib 'logging' module.
* JSON (de)serialisation leverages the provided JsonSchema helper.

The module purposefully contains **no** external side‑effects.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Mapping, overload, Self, Type, TypeVar

from json_schema import JsonSchema

# Forward‑references to avoid circular imports at type‑checking time
if False:  # pragma: no cover
    from agent import Agent
    from tool import Tool  # AbstractTool & Tool live in the project
    from tool_call_result import ToolCallResult  # noqa: F401

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# MessagePart – marker interface
# --------------------------------------------------------------------------- #
class MessagePart(ABC):
    """A piece of a :class:`ChatMessage`."""

    @abstractmethod
    def get_content(self) -> str:
        """Return a textual representation of this part (best‑effort)."""

    # ------------------------------------------------------------------ #
    # Pythonic alias
    # ------------------------------------------------------------------ #
    def __str__(self) -> str:  # pragma: no cover
        return self.get_content()


# --------------------------------------------------------------------------- #
# TextPart – simple textual message part
# --------------------------------------------------------------------------- #
class TextPart(MessagePart):
    """A :class:`MessagePart` containing plain text."""

    def __init__(self, content: str) -> None:
        if content is None:
            raise ValueError("content must not be None")
        self._content: str = str(content)

    # Property to honour @NonNull semantics
    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        if value is None:
            raise ValueError("content must not be None")
        self._content = str(value)

    # MessagePart ------------------------------------------------------ #
    def get_content(self) -> str:
        return self._content


# --------------------------------------------------------------------------- #
# ToolCall – a single invocation of a Tool
# --------------------------------------------------------------------------- #
class ToolCall(MessagePart):
    """Represents a single invocation of a :class:`Tool`."""

    def __init__(
        self,
        id_: str,
        tool: "Tool",
        arguments: Mapping[str, Any] | None = None,
    ) -> None:
        if id_ is None:
            raise ValueError("id_ must not be None")
        if tool is None:
            raise ValueError("tool must not be None")

        self.id: str = id_
        self.tool: "Tool" = tool
        self.arguments: dict[str, Any] = dict(arguments or {})

    # ----------------------- builder helpers -------------------------- #
    class Builder:
        """Fluent builder replicating the Java pattern."""

        def __init__(self) -> None:
            self._id: str | None = None
            self._tool: "Tool | None" = None
            self._arguments: dict[str, Any] = {}

        # id
        def id(self, id_: str) -> Self:  # noqa: D401 (“Returns self”)
            if id_ is None:
                raise ValueError("id must not be None")
            self._id = id_
            return self

        # tool
        def tool(self, tool: "Tool") -> Self:  # noqa: D401
            if tool is None:
                raise ValueError("tool must not be None")
            self._tool = tool
            return self

        # arguments – mapping
        def arguments(self, args: Mapping[str, Any]) -> Self:  # noqa: D401
            if args is None:
                raise ValueError("args must not be None")
            self._arguments = dict(args)
            return self

        # arguments – JSON string
        def arguments_json(self, json_str: str) -> Self:  # noqa: D401
            from typing import TypeAlias
            import json as _json

            _Map: TypeAlias = dict[str, Any]
            self._arguments = JsonSchema.deserialize(json_str, _Map)  # type: ignore[type-var]
            return self

        # Build
        def build(self) -> "ToolCall":
            return ToolCall(
                id_=self._id or (lambda: (_ for _ in ()).throw(ValueError("id not set")))(),  # trick to raise
                tool=self._tool or (lambda: (_ for _ in ()).throw(ValueError("tool not set")))(),
                arguments=self._arguments,
            )

    # Mimic Java's static builder() method
    @staticmethod
    def builder() -> "ToolCall.Builder":
        return ToolCall.Builder()

    # ------------------------------------------------------------------ #
    # MessagePart
    # ------------------------------------------------------------------ #
    def get_content(self) -> str:
        return f"ToolCall(id={self.id}, tool={self.tool.id}, args={self.arguments})"

    # ------------------------------------------------------------------ #
    # Execution helper
    # ------------------------------------------------------------------ #
    def execute(self) -> "ToolCallResult":
        """Invoke the underlying tool and return its result."""
        if self.tool is None:
            raise RuntimeError("Cannot execute a ToolCall without a bound Tool")
        return self.tool.invoke(self)  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# ToolCallResult – holds the outcome of a ToolCall
# --------------------------------------------------------------------------- #
class ToolCallResult(MessagePart):
    """Result (or error) produced by a :class:`ToolCall`."""

    def __init__(
        self,
        tool_call_id: str,
        tool_id: str,
        result: str | None = None,
        is_error: bool = False,
    ) -> None:
        if tool_call_id is None:
            raise ValueError("tool_call_id must not be None")
        if tool_id is None:
            raise ValueError("tool_id must not be None")

        self.tool_call_id: str = tool_call_id
        self.tool_id: str = tool_id
        self.result: str | None = result
        self.is_error: bool = is_error

    # Convenience constructors matching Java behaviour ----------------- #
    @classmethod
    def from_call(cls, call: ToolCall, result: str | None) -> "ToolCallResult":
        return cls(call.id, call.tool.id, result)

    @classmethod
    def from_exception(cls, call: ToolCall, exc: Exception) -> "ToolCallResult":
        return cls(call.id, call.tool.id, f"Error: {exc}", is_error=True)

    # ------------------------------------------------------------------ #
    # MessagePart
    # ------------------------------------------------------------------ #
    def get_content(self) -> str:
        label = "*ERROR* " if self.is_error else ""
        body = "" if self.result is None else str(self.result)
        return f"ToolCallResult({label}{body})"


# --------------------------------------------------------------------------- #
# ChatMessage – exchanged between user and agent
# --------------------------------------------------------------------------- #
class ChatMessage:
    """A single chat message, possibly composed of multiple parts."""

    # --------------------------- author -------------------------------- #
    class Author(str):
        """Enumeration of possible message authors."""

        USER = "user"
        BOT = "bot"
        DEVELOPER = "developer"

        def __new__(cls, value: str):
            return str.__new__(cls, value)

    # ------------------------- construction ---------------------------- #
    @overload
    def __init__(self, content: str, author: "ChatMessage.Author" = Author.USER) -> None: ...
    @overload
    def __init__(self, part: MessagePart, author: "ChatMessage.Author" = Author.USER) -> None: ...
    @overload
    def __init__(
        self,
        parts: Sequence[MessagePart],
        author: "ChatMessage.Author" = Author.USER,
    ) -> None: ...

    def __init__(
        self,
        first: str | MessagePart | Sequence[MessagePart],
        author: "ChatMessage.Author" = Author.USER,
    ) -> None:
        if author is None:
            raise ValueError("author must not be None")

        self.author: ChatMessage.Author = author
        self.parts: list[MessagePart] = []

        # Normalise input
        if isinstance(first, str):
            self.parts.append(TextPart(first))
        elif isinstance(first, MessagePart):
            self.parts.append(first)
        else:  # iterable of parts
            self.parts.extend(first)

    # ------------------------------------------------------------------ #
    # Public helpers (mirroring Java API)
    # ------------------------------------------------------------------ #
    def is_text(self) -> bool:
        """Return *True* iff every part is a :class:`TextPart`."""
        return all(isinstance(p, TextPart) for p in self.parts)

    def has_text(self) -> bool:
        return any(isinstance(p, TextPart) for p in self.parts)

    def get_text_content(self) -> str:
        return "\n\n".join(p.get_content() for p in self.parts)

    T_co = TypeVar("T_co")

    def get_object_content(self, cls: Type[T_co]) -> T_co:
        return JsonSchema.deserialize(self.get_text_content(), cls)

    # --- tool‑calls ---------------------------------------------------- #
    def has_tool_calls(self) -> bool:
        from tool_call import ToolCall  # local import to avoid cyclic deps

        return any(isinstance(p, ToolCall) for p in self.parts)

    def get_tool_calls(self) -> list["ToolCall"]:
        from tool_call import ToolCall  # local import to avoid cyclic deps

        return [p for p in self.parts if isinstance(p, ToolCall)]

    def has_tool_call_results(self) -> bool:
        from tool_call_result import ToolCallResult  # local import

        return any(isinstance(p, ToolCallResult) for p in self.parts)

    def get_tool_call_results(self) -> list["ToolCallResult"]:
        from tool_call_result import ToolCallResult  # local import

        return [p for p in self.parts if isinstance(p, ToolCallResult)]

    # ------------------------------------------------------------------ #
    # Representation helpers
    # ------------------------------------------------------------------ #
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.author}: {self.get_text_content()}"

    __repr__ = __str__


# --------------------------------------------------------------------------- #
# ChatCompletion – wraps a model’s reply
# --------------------------------------------------------------------------- #
class ChatCompletion:
    """Encapsulates the reply produced by a language‑model."""

    # --------------------------- finish reasons ------------------------ #
    class FinishReason(str):
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        TRUNCATED = "truncated"
        INAPPROPRIATE = "inappropriate"
        OTHER = "other"

        def __new__(cls, value: str):
            return str.__new__(cls, value)

    # --------------------------- life‑cycle ---------------------------- #
    def __init__(
        self,
        finish_reason: "ChatCompletion.FinishReason",
        message: ChatMessage,
    ) -> None:
        if finish_reason is None:
            raise ValueError("finish_reason must not be None")
        if message is None:
            raise ValueError("message must not be None")

        self.finish_reason: ChatCompletion.FinishReason = finish_reason
        self.message: ChatMessage = message

    # ------------------------------------------------------------------ #
    # Convenience
    # ------------------------------------------------------------------ #
    def get_text(self) -> str:
        return self.message.get_text_content()

    T_co = TypeVar("T_co")

    def get_object(self, cls: Type[T_co]) -> T_co:
        """Parse the textual content as JSON into *cls*."""
        return self.message.get_object_content(cls)
