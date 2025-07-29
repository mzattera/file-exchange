from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Mapping, Type

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Forward references to avoid circular imports
# --------------------------------------------------------------------------- #
if False:  # type-checking only
    from agent import Agent
    from tool_call import ToolCall
    from tool_call_result import ToolCallResult

from json_schema import JsonSchema  # noqa: E402  (local project import)


# --------------------------------------------------------------------------- #
# Tool ­– Python equivalent of the Java interface
# --------------------------------------------------------------------------- #
class Tool(ABC):
    """
    Base protocol for every tool the agent can call.
    Sub-classes must implement :meth:`invoke`.
    """

    # --------------------------------------------------------------------- #
    # Public attributes expected by the agent
    # --------------------------------------------------------------------- #
    id: str
    description: str
    json_parameters: str

    # --------------------------------------------------------------------- #
    # Life-cycle hooks
    # --------------------------------------------------------------------- #
    @abstractmethod
    def is_initialized(self) -> bool: ...

    @abstractmethod
    def is_closed(self) -> bool: ...

    @abstractmethod
    def init(self, agent: "Agent") -> None: ...

    # --------------------------------------------------------------------- #
    # Core functionality
    # --------------------------------------------------------------------- #
    @abstractmethod
    def invoke(self, call: "ToolCall") -> "ToolCallResult": ...

    @abstractmethod
    def close(self) -> None: ...


# --------------------------------------------------------------------------- #
# AbstractTool ­– shared implementation for concrete tools
# --------------------------------------------------------------------------- #
class AbstractTool(Tool):
    """
    Convenient super-class that handles common responsibilities:
    * life-cycle management (`init`, `close`)
    * JSON-schema generation for parameters
    * helper methods to parse arguments passed as strings

    Parameters
    ----------
    id_ : str
        Unique identifier for the tool (used by the agent and the model).
    description : str, optional
        Human-readable description of the tool’s purpose.
    parameters_cls : type
        A class (typically a *pydantic* model) describing the tool parameters.
        Its JSON schema is exposed through :pyattr:`json_parameters`.
    """

    # --------------------------------------------------------------------- #
    # Construction & life-cycle
    # --------------------------------------------------------------------- #
    def __init__(
        self,
        id_: str,
        description: str | None = None,
        parameters_cls: Type | None = None,
    ) -> None:
        if id_ is None:
            raise ValueError("id_ must not be None")
        if parameters_cls is None:
            raise ValueError("parameters_cls must not be None")

        self.id: str = id_
        self.description: str = description or ""
        self.json_parameters: str = JsonSchema.get_json_schema(parameters_cls)

        self._agent: "Agent | None" = None
        self._closed: bool = False

    # --------------------------------------------------------------------- #
    # Life-cycle helpers
    # --------------------------------------------------------------------- #
    def is_initialized(self) -> bool:
        return self._agent is not None

    def is_closed(self) -> bool:
        return self._closed

    def init(self, agent: "Agent") -> None:
        if agent is None:
            raise ValueError("agent must not be None")
        if self.is_initialized():
            raise RuntimeError(f"Tool {self.id} is already initialized")
        if self.is_closed():
            raise RuntimeError(f"Tool {self.id} is already closed")

        self._agent = agent
        logger.debug("Tool %s initialised", self.id)

    def close(self) -> None:
        self._closed = True
        logger.debug("Tool %s closed", self.id)

    # --------------------------------------------------------------------- #
    # Static helpers for argument parsing
    # --------------------------------------------------------------------- #
    @staticmethod
    def get_boolean(name: str, args: Mapping[str, Any], default: bool | None = None) -> bool:
        if name not in args:
            if default is not None:
                return default
            raise ValueError(f'Missing required parameter "{name}".')

        value = args[name]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            s = value.strip().lower()
            if s == "true":
                return True
            if s == "false":
                return False

        raise ValueError(f'Parameter "{name}" is expected to be a boolean value but it is not.')

    @staticmethod
    def get_long(name: str, args: Mapping[str, Any], default: int | None = None) -> int:
        if name not in args:
            if default is not None:
                return default
            raise ValueError(f'Missing required parameter "{name}".')

        try:
            return int(args[name])
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f'Parameter "{name}" is expected to be an integer value but it is not.') from exc

    @staticmethod
    def get_double(name: str, args: Mapping[str, Any], default: float | None = None) -> float:
        if name not in args:
            if default is not None:
                return default
            raise ValueError(f'Missing required parameter "{name}".')

        try:
            return float(args[name])
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f'Parameter "{name}" is expected to be a decimal number but it is not.') from exc

    @staticmethod
    def get_string(name: str, args: Mapping[str, Any], default: str | None = None) -> str | None:
        if name not in args:
            return default
        value = args[name]
        return None if value is None else str(value)
