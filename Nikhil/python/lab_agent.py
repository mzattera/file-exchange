# lab_agent.py
"""
Python translation of `com.infosys.small.pnbc.LabAgent`.

The class extends `ToolableReactAgent` to provide simulation capabilities
through an `ExecutionContext` and can itself be used as a tool.
"""

from __future__ import annotations

import logging
from typing import Sequence

from chat_types import ToolCall, ToolCallResult
from execution_context import ExecutionContext
from steps import Status, Step
from tool import Tool
from toolable_react_agent import ToolableReactAgent

# --------------------------------------------------------------------------- #
# Logging (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# LabAgent
# --------------------------------------------------------------------------- #
class LabAgent(ToolableReactAgent):
    """
    An agent able to orchestrate simulated processes through an
    :class:`ExecutionContext`. The agent can also be invoked as a tool
    by other agents.
    """

    # ----------------------------- init ---------------------------------- #
    def __init__(
        self,
        id_: str,
        description: str,
        tools: Sequence[Tool],
        check_last_step: bool = False,
    ) -> None:
        super().__init__(
            id_=id_,
            description=description,
            tools=tools,
            check_last_step=check_last_step,
        )
        self.execution_context: ExecutionContext | None = None

    # ------------------------ helper accessors --------------------------- #
    def get_db(self) -> ExecutionContext.DbConnector:
        if self.execution_context is None:
            raise RuntimeError("Execution context is not set.")
        return self.execution_context.db

    def get_scenario_id(self) -> str:
        if self.execution_context is None:
            raise RuntimeError("Execution context is not set.")
        return self.execution_context.scenario_id

    def get_run_id(self) -> str:
        if self.execution_context is None:
            raise RuntimeError("Execution context is not set.")
        return self.execution_context.run_id

    def get_lab_agent(self) -> "LabAgent | None":  # noqa: D401
        """
        Return the outermost :class:`LabAgent` in the call chain (may be *self*),
        or *None* if not running under a LabAgent.
        """
        agent = self._agent
        if isinstance(agent, LabAgent):
            return agent
        from executor_module import ExecutorModule  # local import to break cycle

        if isinstance(agent, ExecutorModule):
            inner = agent.agent
            if isinstance(inner, LabAgent):  # pragma: no cover
                return inner
        return None

    # ------------------------- execution wrapper ------------------------- #
    def execute(self, ctx: ExecutionContext, command: str) -> Step:
        """
        Run a single command within the provided *ctx* simulation context.
        """
        if ctx is None:
            raise ValueError("ctx must not be None")
        if command is None:
            raise ValueError("command must not be None")

        self.execution_context = ctx
        return super().execute(command)

    # ------------------------------ invoke ------------------------------- #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        """
        Allow other agents to use this `LabAgent` as a tool.
        """
        if call is None:
            raise ValueError("call must not be None")
        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized before invocation.")

        question = self.get_string("question", call.arguments)
        if question is None:
            return ToolCallResult.from_call(
                call,
                'ERROR: You must provide a command to execute as "question" parameter.',
            )

        parent_lab = self.get_lab_agent()
        if parent_lab is None or parent_lab.execution_context is None:
            return ToolCallResult.from_call(call, "ERROR: Execution context is missing.")

        # Delegate execution within the caller’s context
        step = self.execute(parent_lab.execution_context, question)

        if step.status == Status.ERROR:
            return ToolCallResult.from_call(call, f"ERROR: {step.observation}")

        return ToolCallResult.from_call(call, step.observation)
