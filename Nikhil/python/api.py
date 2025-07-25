# api.py
"""
Python translation of `com.infosys.small.pnbc.Api` – revised.

A single `invoke(...)` method now handles both normal and logged calls by means
of an optional `log` keyword-only flag.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, TYPE_CHECKING

from chat_types import ToolCall, ToolCallResult
from execution_context import ExecutionContext
from executor_module import ExecutorModule
from scenario_component import ScenarioComponent
from tool import AbstractTool

if TYPE_CHECKING:
    from lab_agent import LabAgent

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Api(AbstractTool):
    """Abstract tool representing a simulated backend API."""

    # --------------------------- construction --------------------------- #
    def __init__(self, id_: str, description: str, schema: type) -> None:
        if id_ is None:
            raise ValueError("id_ must not be None")
        if schema is None:
            raise ValueError("schema must not be None")

        super().__init__(id_=id_, description=description, parameters_cls=schema)

    # ------------------------ helper accessors ------------------------- #
    def get_lab_agent(self) -> "LabAgent | None":
        agent = self._agent
        if isinstance(agent, LabAgent):  # type: ignore[name-defined]
            return agent
        if isinstance(agent, ExecutorModule):
            inner = agent.agent
            if isinstance(inner, LabAgent):  # type: ignore[name-defined]
                return inner
        return None

    def get_execution_context(self) -> ExecutionContext | None:
        lab = self.get_lab_agent()
        return lab.execution_context if lab else None

    def get_db(self) -> ExecutionContext.DbConnector:
        ctx = self.get_execution_context()
        if ctx is None:
            raise RuntimeError("Execution context is not set.")
        return ctx.db

    def get_scenario_id(self) -> str:
        ctx = self.get_execution_context()
        if ctx is None:
            raise RuntimeError("Execution context is not set.")
        return ctx.scenario_id

    def get_run_id(self) -> str:
        ctx = self.get_execution_context()
        if ctx is None:
            raise RuntimeError("Execution context is not set.")
        return ctx.run_id

    # ------------------------------ invoke ----------------------------- #
    def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:  # noqa: D401
        """
        Execute the API.  
        Set `log=True` to record the call in the current ExecutionContext.
        """
        if call is None:
            raise ValueError("call must not be None")
        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized before invocation.")

        # Clone & sanitise arguments
        args: dict[str, Any] = dict(call.arguments)
        args.pop("thought", None)  # remove LLM’s thought if present

        lab_agent = self.get_lab_agent()
        if lab_agent is None:
            raise RuntimeError("Unable to locate LabAgent in call hierarchy.")

        scenario_id = lab_agent.get_scenario_id()

        if log:
            lab_agent.execution_context.log_api_call(  # type: ignore[arg-type]
                scenario_id,
                self.id,
                args,
            )

        # Retrieve canned result
        result = ScenarioComponent.get_instance().get(scenario_id, self.id, args)
        return ToolCallResult.from_call(call, result)
