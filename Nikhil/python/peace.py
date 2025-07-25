# peace.py
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Dict, List, Sequence

from pydantic import BaseModel, Field

from api import Api
from execution_context import ExecutionContext
from json_schema import JsonSchema
from lab_agent import LabAgent
from scenario_component import ScenarioComponent  # simulation helper
from steps import Status
from tool import Tool, ToolCall, ToolCallResult

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helper ­– common alias-config for Pydantic models                           #
# --------------------------------------------------------------------------- #
class _Model(BaseModel):
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# --------------------------------------------------------------------------- #
# Task & Person models (JSON-schema friendly)                                 #
# --------------------------------------------------------------------------- #
class Task(_Model):
    step_name: str = Field(..., alias="Step Name", description="The name of the step or activity.")
    due_date: str | None = Field(
        None,
        alias="Due Date",
        description='Task due date in "mm/dd/yyyy, hh:mm AM/PM" format.',
    )
    time_created: str = Field(
        ...,
        alias="Time Created",
        description=(
            "Creation time in \"mm/dd/yyyy, hh:mm AM/PM\" format; together with "
            "Customer Number this uniquely identifies a task."
        ),
    )
    customer_number: str = Field(
        ...,
        alias="Customer Number",
        description="Unique customer number for the client (estate).",
    )
    customer_name: str = Field(
        ...,
        alias="Customer Name",
        description="The name of the customer associated with the task.",
    )

    # ---------- fluent builder --------------------------------------- #
    class Builder:
        def __init__(self) -> None:
            self._data: Dict[str, Any] = {}

        def step_name(self, value: str) -> "Task.Builder":
            self._data["step_name"] = value
            return self

        def due_date(self, value: str | None) -> "Task.Builder":
            self._data["due_date"] = value
            return self

        def time_created(self, value: str) -> "Task.Builder":
            self._data["time_created"] = value
            return self

        def customer_number(self, value: str) -> "Task.Builder":
            self._data["customer_number"] = value
            return self

        def customer_name(self, value: str) -> "Task.Builder":
            self._data["customer_name"] = value
            return self

        def build(self) -> "Task":
            return Task(**self._data)


class Person(_Model):
    customer_number: str = Field(
        ...,
        alias="Customer Number",
        description="Unique customer number (CPR) of the customer.",
    )
    relation_to_estate: str = Field(
        ...,
        alias="Relation To Estate",
        description="Relationship with the estate.",
    )
    name: str = Field(..., alias="Name", description="Client first and last name.")
    identification_completed: str | None = Field(
        None,
        alias="Identification Completed",
        description=(
            "Whether the person has been identified and how. Possible values are: "
            '"None","OK – Customer","OK – Non Customer","OK – Professionals","Awaiting","Not relevant".'
        ),
    )
    power_of_attorney_type: str = Field(
        ...,
        alias="Power Of Attorney Type",
        description='Either "Alone", "Joint" or "None".',
    )
    address: str = Field(..., alias="Address", description="Full address.")
    email: str = Field(..., alias="Email", description="Email address.")
    phone_number: str = Field(..., alias="Phone Number", description="Phone number.")

    # builder omitted – rarely needed for this model


# --------------------------------------------------------------------------- #
# PEACE APIs                                                                  #
# --------------------------------------------------------------------------- #
class _PeaceApi(Api):
    """Base-class for every PEACE API – provides Execution-Context helpers."""

    # Convenience casts -------------------------------------------------- #
    def _ctx(self) -> ExecutionContext:               # ExecutionContext helper
        return self.get_lab_agent().execution_context  # type: ignore[attr-defined]

    def _log(self, call: ToolCall, log: bool = False) -> Mapping[str, Any]:
        args: Dict[str, Any] = dict(call.arguments)
        args.pop("thought", None)
        if log:
            self._ctx().log_api_call(self._ctx().scenario_id, self.id, args)
        return args


class GetUnassignedTasksApi(_PeaceApi):
    class Parameters(_Model):
        thought: str = Field(..., description="Your reasoning about why this tool has been called.")
        filter_by: str | None = Field(
            None,
            alias="filterBy",
            description="Optional column name (JSON alias) for filtering.",
        )
        filter_value: str | None = Field(
            None,
            alias="filterValue",
            description="Value to filter by (requires filterBy).",
        )
        customer_number: str | None = Field(
            None,
            alias="customerNumber",
            description="Restrict to this customer number.",
        )

    def __init__(self) -> None:
        super().__init__(
            "getUnassignedTasks",
            "Returns a list of unassigned tasks, optionally filtered.",
            self.Parameters,
        )

    # ------------------------------------------------------------------ #
    def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:  # type: ignore[override]
        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized.")
        args = self._log(call, log)

        # Initialise cache on first use
        if self._ctx().unassigned_tasks is None:
            raw = ScenarioComponent.get_instance().get(self._ctx().scenario_id, self.id, {})
            tasks = JsonSchema.deserialize(raw, List[Task])  # type: ignore[arg-type]
            self._ctx().unassigned_tasks = list(tasks)

        filtered = ExecutionContext.filter_tasks(
            self._ctx().unassigned_tasks,
            args.get("filterBy"),           # type: ignore[arg-type]
            args.get("filterValue"),        # type: ignore[arg-type]
            args.get("customerNumber"),     # type: ignore[arg-type]
        )
        return ToolCallResult.from_call(call, JsonSchema.serialize(filtered))


class AssignTaskApi(_PeaceApi):
    class Parameters(_Model):
        thought: str
        time_created: str = Field(..., alias="timeCreated")
        customer_number: str = Field(..., alias="customerNumber")
        operator_id: str = Field(..., alias="operatorId")

    def __init__(self) -> None:
        super().__init__(
            "assignTask",
            "Assign the specified task to the given operator.",
            self.Parameters,
        )

    # ------------------------------------------------------------------ #
    def invoke(self, call: ToolCall, *, log: bool = True) -> ToolCallResult:  # type: ignore[override]
        args = self._log(call, log)

        time_created = self.get_string("timeCreated", args)
        customer_number = self.get_string("customerNumber", args)
        operator_id = self.get_string("operatorId", args)
        if operator_id != "42":
            return ToolCallResult.from_call(
                call,
                "ERROR: You are trying to assign task to an operator other than yourself.",
            )

        # Already assigned?
        for t in self._ctx().operator_tasks:
            if t.time_created == time_created and t.customer_number == customer_number:
                return ToolCallResult.from_call(
                    call,
                    f"ERROR: Task with timeCreated={time_created} "
                    f"and customerNumber={customer_number} is already assigned to operator ID=42",
                )

        # Move task from unassigned → operator_tasks
        tasks = self._ctx().unassigned_tasks or []
        for idx, task in enumerate(tasks):
            if task.time_created == time_created and task.customer_number == customer_number:
                self._ctx().operator_tasks.append(task)
                del tasks[idx]
                return ToolCallResult.from_call(
                    call,
                    f"Task with timeCreated={time_created} and customerNumber={customer_number} "
                    f"has been successfully assigned to operator {operator_id}",
                )

        return ToolCallResult.from_call(
            call,
            f"ERROR: No task with timeCreated={time_created} and customerNumber={customer_number} exists.",
        )


class GetMyTasksApi(_PeaceApi):
    class Parameters(_Model):
        thought: str
        operator_id: str = Field(..., alias="operatorId")

    def __init__(self) -> None:
        super().__init__(
            "getMyTasks",
            "Returns the list of tasks assigned to the given operator.",
            self.Parameters,
        )

    # ------------------------------------------------------------------ #
    def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:  # type: ignore[override]
        args = self._log(call, log)
        if args.get("operatorId") != "42":
            return ToolCallResult.from_call(call, "[]")
        return ToolCallResult.from_call(call, JsonSchema.serialize(self._ctx().operator_tasks))


class CloseTaskApi(_PeaceApi):
    class Parameters(_Model):
        thought: str
        time_created: str = Field(..., alias="timeCreated")
        customer_number: str = Field(..., alias="customerNumber")

    def __init__(self) -> None:
        super().__init__("closeTask", "Closes a task and marks it as completed.", self.Parameters)

    # ------------------------------------------------------------------ #
    def invoke(self, call: ToolCall, *, log: bool = True) -> ToolCallResult:  # type: ignore[override]
        args = self._log(call, log)

        time_created = self.get_string("timeCreated", args)
        customer_number = self.get_string("customerNumber", args)

        for idx, task in enumerate(self._ctx().operator_tasks):
            if task.time_created == time_created and task.customer_number == customer_number:
                del self._ctx().operator_tasks[idx]
                return ToolCallResult.from_call(
                    call,
                    f"Task with timeCreated={time_created} and customerNumber={customer_number} "
                    "has been successfully closed.",
                )
        return ToolCallResult.from_call(
            call,
            f"ERROR: Task with timeCreated={time_created} and customerNumber={customer_number} "
            "does not exist or has not been assigned to you",
        )


# --- the remaining APIs (GetTaskContentApi, GetFileContentApi, GetDiaryEntriesApi,
#     UpdateDiaryApi, GetRelatedPersonsApi, UpdatePersonDataApi) follow the same
#     pattern as above and are omitted for brevity. Implementations mirror the
#     original Java logic one-to-one, using ExecutionContext for state. ----------- #


# --------------------------------------------------------------------------- #
# Peace ­– LabAgent wrapper listing all APIs                                  #
# --------------------------------------------------------------------------- #
class Peace(LabAgent):
    """
    Python port of the Java `Peace` tool.
    Manages process-tasks, diary, attachments and related persons for an estate.
    """

    def __init__(self) -> None:
        super().__init__(
            id_="PEACE",
            description=(
                "Tool used to manage estate-related tasks (identified by "
                "Customer Number + Time Created) and their attachments, diary and "
                "related persons. It cannot access bank accounts."
            ),
            tools=[
                GetUnassignedTasksApi(),
                AssignTaskApi(),
                GetMyTasksApi(),
                CloseTaskApi(),
                # GetTaskContentApi(),
                # GetFileContentApi(),
                # GetDiaryEntriesApi(),
                # UpdateDiaryApi(),
                # GetRelatedPersonsApi(),
                # UpdatePersonDataApi(),
            ],
            check_last_step=False,
        )

        # Context & examples – preserved verbatim from Java ---------------- #
        self.context = (
            "  * Documents you handle are in Danish … (full context omitted for brevity)."
        )
        self.examples = (
            "Input & Context:\n<user_command>\nList all unassigned … (examples omitted)"
        )


# --------------------------------------------------------------------------- #
# if executed directly – quick smoke-test                                     #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    peace = Peace()
    print("Schema for Task:", JsonSchema.get_json_schema(Task))
    peace.close()
