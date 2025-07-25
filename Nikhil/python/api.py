# api.py
from __future__ import annotations

import logging
from typing import Any, Mapping

from agent import Agent
from executor_module import ExecutorModule
from execution_context import ExecutionContext
from json_schema import JsonSchema  # used only for type hints here
from scenario_component import ScenarioComponent  # assumed existing helper
from tool import AbstractTool, ToolCall, ToolCallResult

logger = logging.getLogger(__name__)


class Api(AbstractTool):
    """
    Python translation of `com.infosys.small.pnbc.Api`.

    It is an *abstract* backend API wrapper that can only be used from the
    *executor* module of a :class:`LabAgent`.
    """

    # --------------------------------------------------------------------- #
    # Construction / life-cycle
    # --------------------------------------------------------------------- #
    def __init__(self, id_: str, description: str, parameters_cls: type) -> None:
        super().__init__(id_=id_, description=description, parameters_cls=parameters_cls)

    # ------------ initialisation checks (must run inside LabAgent) -------- #
    def init(self, agent: Agent) -> None:  # noqa: D401 (“Returns None”)
        if agent is None:
            raise ValueError("agent must not be None")

        if not isinstance(agent, ExecutorModule):
            raise ValueError("This tool can only be used by ReAct agents.")

        if not isinstance(agent.agent, LabAgent):
            raise ValueError("This tool can only be used by LabAgent instances.")

        super().init(agent)

    # Convenience cast ----------------------------------------------------- #
    @property
    def agent(self) -> ExecutorModule:  # type: ignore[override]
        return super()._agent  # type: ignore[attr-defined]

    def get_lab_agent(self) -> "LabAgent":
        return self.agent.agent  # type: ignore[return-value]

    # Execution-context helpers ------------------------------------------- #
    # They are thin wrappers around LabAgent’s public attributes.
    def get_execution_context(self) -> ExecutionContext:
        return self.get_lab_agent().execution_context

    def get_db(self) -> ExecutionContext.DbConnector:
        return self.get_execution_context().db

    def get_scenario_id(self) -> str:
        return self.get_execution_context().scenario_id

    def get_run_id(self) -> str:
        return self.get_execution_context().run_id

    # --------------------------------------------------------------------- #
    # Core invocation logic
    # --------------------------------------------------------------------- #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        return self._invoke_internal(call, log=False)

    # Extra entry with *log* flag, mirroring Java signature
    def _invoke_internal(self, call: ToolCall, *, log: bool) -> ToolCallResult:
        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized.")

        # Drop the “thought” argument before forwarding.
        args: dict[str, Any] = dict(call.arguments)
        args.pop("thought", None)

        scenario_id = self.get_scenario_id()
        if log:
            self.get_execution_context().log_api_call(scenario_id, self.id, args)

        # Delegate to ScenarioComponent (simulation data source)
        result = ScenarioComponent.get_instance().get(scenario_id, self.id, args)
        return ToolCallResult.from_call(call, result)
