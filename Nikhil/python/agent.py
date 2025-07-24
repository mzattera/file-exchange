"""agent.py

Python translation of the Java `Agent` class.

The implementation mirrors the original behaviour while embracing Pythonic
conventions and the `openai` Python SDK.

Dependencies
------------
- openai                (official OpenAI SDK)
- json                  (standard library)
- logging               (standard library)
- chat_types.ChatMessage, chat_types.ChatCompletion,
  chat_types.ToolCall, chat_types.ToolCallResult, chat_types.TextPart
- tool.Tool             (protocol / abstract base class for tools)
- json_schema.JsonSchema
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable, Sequence
from typing import Any, Dict, List, Mapping, MutableMapping, Type

import openai

from chat_types import (
    ChatCompletion,
    ChatMessage,
    TextPart,
    ToolCall,
    ToolCallResult,
)
from json_schema import JsonSchema
from tool import Tool

# --------------------------------------------------------------------------- #
# Logging (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class Agent:
    """
    An *Agent* that uses OpenAI’s Chat Completions API.

    Parameters
    ----------
    id_ : str
        Unique identifier for the agent.
    description : str
        Human-readable description of the agent’s capabilities.
    tools : Iterable[Tool], optional
        Tools that the agent can invoke.
    """

    DEFAULT_MODEL: str = "gpt-4.1"

    # -------------------------- construction --------------------------- #
    def __init__(
        self,
        id_: str = "OpenAIChatCompletionService",
        description: str = "Test agent",
        tools: Iterable[Tool] | None = None,
    ) -> None:
        if id_ is None:
            raise ValueError("id_ must not be None")
        if description is None:
            raise ValueError("description must not be None")

        self.id: str = id_
        self.description: str = description

        # Tools --------------------------------------------------------- #
        self._tool_map: Dict[str, Tool] = {}
        for tool in tools or []:
            if tool is None:
                raise ValueError("tools must not contain None")
            tool.init(self)
            self._tool_map[tool.id] = tool

        # Conversation state ------------------------------------------- #
        self.history: List[ChatMessage] = []
        self.max_history_length: int = float("inf")  # no hard limit
        self.max_conversation_steps: int = float("inf")

        # Model configuration ------------------------------------------ #
        self.model: str = self.DEFAULT_MODEL
        self.temperature: float = 0.0
        self.personality: str | None = None
        self._response_format: str | None = None

        # OpenAI configuration ----------------------------------------- #
        # Expect OPENAI_API_KEY in the environment
        openai.api_key = os.getenv("OPENAI_API_KEY")

    # --------------------------- utils -------------------------------- #
    # Conversation helpers ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def clear_conversation(self) -> None:
        """Start a new chat (clears stored history)."""
        self.history.clear()

    # Personality / response-format ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def response_format(self) -> str | None:
        return self._response_format

    def set_response_format(self, schema: Type) -> None:
        """Define an explicit JSON schema for model outputs."""
        if schema is None:
            raise ValueError("schema must not be None")
        self._response_format = JsonSchema.get_json_schema(schema)

    # --------------------- public chat API ---------------------------- #
    def chat(self, message: str | ChatMessage | Sequence[ChatMessage]) -> ChatCompletion:
        """
        Continue the ongoing conversation with *message*.

        The provided message(s) are appended to the conversation, the LLM is
        queried, and the reply is stored in the history.
        """
        # Normalise input
        if isinstance(message, str):
            new_messages = [ChatMessage(message)]
        elif isinstance(message, ChatMessage):
            new_messages = [message]
        else:
            new_messages = list(message)

        # Build conversation context
        conversation: List[ChatMessage] = list(self.history) + new_messages
        self._trim_conversation(conversation)

        # Call the model
        completion = self._chat_completion(conversation)

        # Update history (respecting max_history_length)
        self.history.extend(new_messages)
        self.history.append(completion.message)
        if len(self.history) > self.max_history_length:
            del self.history[: len(self.history) - self.max_history_length]

        return completion

    # ------------------------------------------------------------------ #
    # One-shot completion (ignores history) ---------------------------- #
    def complete(self, prompt: str | ChatMessage) -> ChatCompletion:
        """Run *prompt* outside the conversation (history is untouched)."""
        single = ChatMessage(prompt) if isinstance(prompt, str) else prompt
        conversation = [single]
        self._trim_conversation(conversation)
        return self._chat_completion(conversation)

    # -------------------------- internals ----------------------------- #
    # Trim conversation to honour limits and add personality ~~~~~~~~~~~ #
    def _trim_conversation(self, messages: List[ChatMessage]) -> None:
        """Mutate *messages* so it respects configured limits."""
        # Remove leading tool-results without matching calls
        while messages and messages[0].has_tool_call_results():
            messages.pop(0)

        # Enforce max steps
        if len(messages) > self.max_conversation_steps:
            del messages[: len(messages) - self.max_conversation_steps]

        if not messages:
            raise ValueError("No messages left in conversation after trimming")

        # Inject personality (developer role) as first message
        if self.personality:
            messages.insert(0, ChatMessage(self.personality, ChatMessage.Author.DEVELOPER))

    # Convert ChatMessage → OpenAI message dict ~~~~~~~~~~~~~~~~~~~~~~~~ #
    def _from_chat_message(self, msg: ChatMessage) -> List[Dict[str, Any]]:
        if msg.has_tool_calls():
            tool_calls = []
            for call in msg.get_tool_calls():
                tool_calls.append(
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.tool.id,
                            "arguments": json.dumps(call.arguments, separators=(",", ":")),
                        },
                    }
                )
            return [{"role": "assistant", "content": None, "tool_calls": tool_calls}]

        if msg.has_tool_call_results():
            return [
                {
                    "role": "tool",
                    "tool_call_id": r.tool_call_id,
                    "content": r.result,
                }
                for r in msg.get_tool_call_results()
            ]

        # Plain text
        if not msg.is_text():
            raise ValueError("Message must be text, a tool call, or tool call results")

        role_map = {
            ChatMessage.Author.USER: "user",
            ChatMessage.Author.BOT: "assistant",
            ChatMessage.Author.DEVELOPER: "system",  # OpenAI 'developer' maps to 'system'
        }
        return [{"role": role_map[msg.author], "content": msg.get_text_content()}]

    # Convert OpenAI message → ChatMessage ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def _from_openai_message(self, message: Mapping[str, Any]) -> ChatMessage:
        if "tool_calls" in message:
            calls: List[ToolCall] = []
            for tc in message["tool_calls"]:
                tool_id = tc["function"]["name"]
                tool = self._tool_map.get(tool_id)
                if tool is None:
                    raise ValueError(f"No tool registered with id '{tool_id}'")

                calls.append(
                    ToolCall(
                        id_=tc["id"],
                        tool=tool,
                        arguments=json.loads(tc["function"]["arguments"]),
                    )
                )
            return ChatMessage(ChatMessage.Author.BOT, calls)

        parts: List[TextPart] = []
        if content := message.get("content"):
            parts.append(TextPart(str(content)))
        if message.get("role") == "assistant" and message.get("content") is None:
            parts.append(TextPart("**The model generated an empty response**"))

        return ChatMessage(ChatMessage.Author.BOT, parts)

    # Prepare response_format / tools for OpenAI call ~~~~~~~~~~~~~~~~~~ #
    def _create_response_format(self) -> Dict[str, Any] | None:
        if self._response_format is None:
            return None
        return {
            "type": "json_object",
            "schema": json.loads(self._response_format),
        }

    def _create_tool_definitions(self) -> List[Dict[str, Any]] | None:
        if not self._tool_map:
            return None
        tools = []
        for t in self._tool_map.values():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.id,
                        "description": t.description,
                        "parameters": json.loads(t.json_parameters),
                    },
                }
            )
        return tools

    # Core: call OpenAI and wrap result ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def _chat_completion(self, messages: Sequence[ChatMessage]) -> ChatCompletion:
        openai_messages: List[Dict[str, Any]] = []
        for m in messages:
            openai_messages.extend(self._from_chat_message(m))

        req: Dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
        }

        if (rf := self._create_response_format()) is not None:
            req["response_format"] = rf
        if (td := self._create_tool_definitions()) is not None:
            req["tools"] = td

        logger.info("OpenAI request: %s", req)

        resp = openai.ChatCompletion.create(**req)
        choice = resp.choices[0]
        finish_reason = self._map_finish_reason(choice.finish_reason)

        chat_message = self._from_openai_message(choice.message)
        return ChatCompletion(finish_reason, chat_message)

    # Finish-reason mapping ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @staticmethod
    def _map_finish_reason(finish: str | None) -> ChatCompletion.FinishReason:
        mapping = {
            "stop": ChatCompletion.FinishReason.COMPLETED,
            "tool_calls": ChatCompletion.FinishReason.COMPLETED,
            "function_call": ChatCompletion.FinishReason.COMPLETED,
            "length": ChatCompletion.FinishReason.TRUNCATED,
            "content_filter": ChatCompletion.FinishReason.INAPPROPRIATE,
        }
        return mapping.get(finish, ChatCompletion.FinishReason.OTHER)

	# Finish-reason mapping ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #      
    @staticmethod
    def fill_slots(template: str, slots: Mapping[str, Any]) -> str:  
        """
        Replace every ``{{key}}`` in *template* with the corresponding value
        from *slots*. Unknown keys are left untouched; *None* is replaced by
        the empty string.

        Parameters
        ----------
        template : str
            A string containing ``{{placeholders}}``.
        slots : Mapping[str, Any]
            Values to inject into the template.

        Returns
        -------
        str
            The rendered string.
        """
        if template is None:
            raise ValueError("template must not be None")
        if slots is None:
            raise ValueError("slots must not be None")

        def _sub(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            value = slots.get(key)
            return "" if value is None else str(value)

        return re.sub(r"\{\{([^}]+)\}\}", _sub, template)
        
    # --------------------------- teardown ----------------------------- #
    def close(self) -> None:
        """Close all tools; nothing required for *openai* client."""
        for tool in self._tool_map.values():
            try:
                tool.close()
            except Exception:  # noqa: BLE001
                logger.exception("Error while closing tool %s", tool.id)
