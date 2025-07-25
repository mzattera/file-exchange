# lab_agent.py
from __future__ import annotations

import logging
from typing import Sequence

from executor_module import ExecutorModule
from execution_context import ExecutionContext
from react_agent import Step
from steps import Status
from tool import Tool, ToolCall, ToolCallResult
from toolable_react_agent import ToolableReactAgent

logger = logging.getLogger(__name__)


class LabAgent(ToolableReactAgent):
    """
    Python translation of `com.infosys.small.pnbc.LabAgent`.

    A *ReAct* agent able to execute commands in a **simulated** environment
    through an :class:`ExecutionContext`.  It can also be exposed as a *tool*
    for use by other agents.
    """

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
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
        self._execution_context: ExecutionContext | None = None

    # ------------------------------------------------------------------ #
    # Execution-context property (read-only from outside)
    # ------------------------------------------------------------------ #
    @property
    def execution_context(self) -> ExecutionContext:
        if self._execution_context is None:
            raise RuntimeError("ExecutionContext is not set.")
        return self._execution_context

    # ------------------------------------------------------------------ #
    # Database / scenario helpers
    # ------------------------------------------------------------------ #
    def get_db(self) -> ExecutionContext.DbConnector:
        return self.execution_context.db

    def get_scenario_id(self) -> str:
        return self.execution_context.scenario_id

    def get_run_id(self) -> str:
        return self.execution_context.run_id

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def execute(self, ctx: ExecutionContext, command: str) -> Step:
        """
        Run *command* inside *ctx* (simulation environment).

        The context is attached for the duration of the call and cleared
        afterwards, mimicking the Java `try/finally` behaviour.
        """
        self._execution_context = ctx
        try:
            return super().execute(command)
        finally:
            self._execution_context = None

    # ------------------------------------------------------------------ #
    # Tool life-cycle overrides (when LabAgent is itself used as a tool)
    # ------------------------------------------------------------------ #
    def init(self, agent: "Agent") -> None:  # type: ignore[override]
        if not isinstance(agent, ExecutorModule):
            raise ValueError("This tool can only be used by ReAct agents.")
        if not isinstance(agent.agent, LabAgent):
            raise ValueError("This tool can only be used by LabAgent instances.")
        super().init(agent)

    @property
    def agent(self) -> ExecutorModule:  # type: ignore[override]
        return super()._agent  # type: ignore[attr-defined]

    def get_lab_agent(self) -> "LabAgent":
        return self.agent.agent  # type: ignore[return-value]

    # ------------------------------------------------------------------ #
    # Tool invocation (when wrapped as a Tool)
    # ------------------------------------------------------------------ #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized.")

        question = self.get_string("question", call.arguments)
        if question is None:
            return ToolCallResult.from_call(
                call,
                'ERROR: You must provide a command to execute as "question" parameter.',
            )

        ctx = self.get_lab_agent().execution_context
        step = self.execute(ctx, question)

        if step.status == Status.ERROR:
            return ToolCallResult.from_call(call, f"ERROR: {step.observation}")

        return ToolCallResult.from_call(call, step.observation)
