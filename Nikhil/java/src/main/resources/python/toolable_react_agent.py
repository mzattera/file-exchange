from __future__ import annotations

import logging
from typing import Sequence

from pydantic import Field

from agent import Agent  # for type hints only
from react_agent import ReactAgent
from steps import Step, Status
from tool import AbstractTool, Tool, ToolCall, ToolCallResult

# ---------------------------------------------------------------------------#
# Logging configuration (Java-style simple logger)
# ---------------------------------------------------------------------------#
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------#
# ToolableReactAgent
# ---------------------------------------------------------------------------#
class ToolableReactAgent(ReactAgent, AbstractTool):
    """
    A `ReactAgent` that can be used as a `Tool` by another agent.

    It inherits behaviour from both `ReactAgent` (conversation logic) and
    `AbstractTool` (tool life-cycle & helpers).
    """

    # --------------------------- parameters --------------------------- #
    class Parameters(ReactAgent.Parameters):
        """JSON-serialisable parameters for invoking the tool."""

        question: str = Field(
            ...,
            description=(
                "A question that this tool must answer or a command it must execute."
            ),
        )

    # ----------------------------- init ------------------------------- #
    def __init__(
        self,
        id_: str,
        description: str,
        tools: Sequence[Tool],
        check_last_step: bool = True,
    ) -> None:
        # Initialise the ReactAgent part (handles reasoning & tools)
        ReactAgent.__init__(
            self,
            id_=id_,
            description=description,
            tools=tools,
            check_last_step=check_last_step,
        )

        # Initialise the AbstractTool part (exposes tool metadata)
        AbstractTool.__init__(
            self,
            id_=id_,
            description=description,
            parameters_cls=ToolableReactAgent.Parameters,
        )

    # --------------------------- overrides ---------------------------- #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        """
        Execute the wrapped ReAct agent to answer *question*.

        The `question` parameter is mandatory; errors are returned in
        `ToolCallResult` following the Java semantics.
        """
        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized before invocation.")

        question = self.get_string("question", call.arguments)
        if question is None:
            return ToolCallResult.from_call(
                call,
                'ERROR: You must provide a command to execute as "question" parameter.',
            )

        # Delegate to the executor module of the underlying ReactAgent
        result_step: Step = self.execute(question)

        if result_step.status == Status.ERROR:
            return ToolCallResult.from_call(call, f"ERROR: {result_step.observation}")

        return ToolCallResult.from_call(call, result_step.observation)

    # ------------------------------------------------------------------ #
    # Clean-up
    # ------------------------------------------------------------------ #
    def close(self) -> None:
        """Close both the tool and the underlying agent."""
        AbstractTool.close(self)
        ReactAgent.close(self)
