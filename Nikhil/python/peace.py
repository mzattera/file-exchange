"""peace.py

Python translation of `com.infosys.small.pnbc.Peace`.

This module adapts the original Java implementation to the existing Python
framework already present in the project.  It relies on:

* LabAgent, Api, ExecutionContext, ScenarioComponent, JsonSchema …
* Logging via the standard `logging` module.
* Pydantic models for JSON-serialisable data classes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field

from api import Api
from execution_context import ExecutionContext
from json_schema import JsonSchema
from lab_agent import LabAgent
from react_agent import ReactAgent
from scenario_component import ScenarioComponent
from steps import Status
from tool import ToolCallResult

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Peace – the tool/agent
# --------------------------------------------------------------------------- #
class Peace(LabAgent):
    """
    Backend-system wrapper for PEACE.
    """

    # --------------------------------------------------------------------- #
    # Task
    # --------------------------------------------------------------------- #
    class Task(BaseModel):
        """
        A task in PEACE.
        """

        step_name: str = Field(..., alias="Step Name", description="The name of the step or activity.")
        due_date: Optional[str] = Field(
            None,
            alias="Due Date",
            description='Task due date "mm/dd/yyyy, hh:mm AM/PM" (e.g. "4/16/2025, 2:31 PM").',
        )
        time_created: str = Field(
            ...,
            alias="Time Created",
            description=(
                'Time when the task was created "mm/dd/yyyy, hh:mm AM/PM" '
                '(e.g. "4/16/2025, 2:31 PM"); together with Customer Number this '
                "uniquely defines a task."
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

        model_config = {"populate_by_name": True, "extra": "ignore"}

        # ------------------------ fluent Builder ------------------------ #
        class Builder:
            def __init__(self) -> None:
                self._step_name: Optional[str] = None
                self._due_date: Optional[str] = None
                self._time_created: Optional[str] = None
                self._customer_number: Optional[str] = None
                self._customer_name: Optional[str] = None

            # fluent setters
            def step_name(self, step_name: str) -> "Peace.Task.Builder":
                if step_name is None:
                    raise ValueError("step_name must not be None")
                self._step_name = step_name
                return self

            def due_date(self, due_date: Optional[str]) -> "Peace.Task.Builder":
                self._due_date = due_date
                return self

            def time_created(self, time_created: str) -> "Peace.Task.Builder":
                if time_created is None:
                    raise ValueError("time_created must not be None")
                self._time_created = time_created
                return self

            def customer_number(self, customer_number: str) -> "Peace.Task.Builder":
                if customer_number is None:
                    raise ValueError("customer_number must not be None")
                self._customer_number = customer_number
                return self

            def customer_name(self, customer_name: str) -> "Peace.Task.Builder":
                if customer_name is None:
                    raise ValueError("customer_name must not be None")
                self._customer_name = customer_name
                return self

            # build
            def build(self) -> "Peace.Task":
                return Peace.Task(
                    step_name=self._step_name or self._raise("step_name"),
                    due_date=self._due_date,
                    time_created=self._time_created or self._raise("time_created"),
                    customer_number=self._customer_number or self._raise("customer_number"),
                    customer_name=self._customer_name or self._raise("customer_name"),
                )

            # helper
            @staticmethod
            def _raise(name: str) -> None:  # pragma: no cover
                raise ValueError(f"{name} must not be None")

        # factory
        @staticmethod
        def builder() -> "Peace.Task.Builder":
            return Peace.Task.Builder()

    # --------------------------------------------------------------------- #
    # Person
    # --------------------------------------------------------------------- #
    class Person(BaseModel):
        """
        Data for one person related to an estate.
        """

        customer_number: str = Field(
            ...,
            alias="Customer Number",
            description="Unique customer number (CPR) of the customer.",
        )
        relation_to_estate: str = Field(
            ...,
            alias="Relation To Estate",
            description=(
                'Relation to the estate. Possible values: "Lawyer", "Other", '
                '"Power of attorney", "Heir", "Guardian/værge", "Guardian/skifteværge", '
                '"Beneficiary", "Spouse", "Cohabitee", "One man company", "I/S", '
                '"K/S", "Joint", "Deceased".'
            ),
        )
        name: str = Field(
            ...,
            alias="Name",
            description="Client first and last name.",
        )
        identification_completed: Optional[str] = Field(
            None,
            alias="Identification Completed",
            description=(
                'Identification status. Possible values: "None", "OK – Customer", '
                '"OK – Non Customer", "OK – Professionals", "Awaiting", "Not relevant".'
            ),
        )
        power_of_attorney_type: str = Field(
            ...,
            alias="Power Of Attorney Type",
            description='Possible values: "Alone", "Joint", "None".',
        )
        address: str = Field(..., alias="Address", description="Full address.")
        email: str = Field(..., alias="Email", description="Email address.")
        phone_number: str = Field(..., alias="Phone Number", description="Phone number.")

        model_config = {"populate_by_name": True, "extra": "ignore"}

    # --------------------------------------------------------------------- #
    # API definitions
    # --------------------------------------------------------------------- #
    # Helper to (de)serialise lists of Task/Person ------------------------- #
    @staticmethod
    def _to_json(objs: Sequence[BaseModel]) -> str:
        return json.dumps(
            [o.model_dump(exclude_none=True, by_alias=True) for o in objs],
            separators=(",", ":"),
        )

    @staticmethod
    def _from_json_tasks(s: str) -> List["Peace.Task"]:
        data = json.loads(s or "[]")
        return [Peace.Task.model_validate(o) for o in data]

    @staticmethod
    def _from_json_persons(s: str) -> List["Peace.Person"]:
        data = json.loads(s or "[]")
        return [Peace.Person.model_validate(o) for o in data]

    # ---------------- getUnassignedTasks ---------------------------------- #
    class GetUnassignedTasksApi(Api):
        class Parameters(ReactAgent.Parameters):
            filter_by: Optional[str] = Field(
                None,
                alias="filterBy",
                description=(
                    "Optional column name to filter tasks (must match task field alias, "
                    'e.g. "Step Name").'
                ),
            )
            filter_value: Optional[str] = Field(
                None,
                alias="filterValue",
                description="Filter value if filterBy is provided.",
            )
            customer_number: Optional[str] = Field(
                None,
                alias="customerNumber",
                description="If provided, only tasks for this client are returned.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getUnassignedTasks",
                description="Returns a list of unassigned tasks, optionally filtered.",
                schema=Peace.GetUnassignedTasksApi.Parameters,
            )

        # override
        def invoke(self, call, *, log: bool = False):  # noqa: D401
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            scenario = self.get_lab_agent().get_scenario_id()
            if log:
                self.get_lab_agent().execution_context.log_api_call(scenario, self.id, args)

            ctx = self.get_execution_context()
            if ctx.unassigned_tasks is None:
                tasks_json = ScenarioComponent.get_instance().get(scenario, self.id, {})
                ctx.unassigned_tasks = Peace._from_json_tasks(tasks_json)

            filter_by = self.get_string("filterBy", call.arguments, None)
            filter_val = self.get_string("filterValue", call.arguments, None)
            if filter_by and filter_val is None:
                raise ValueError(f"Must provide filterValue for filterBy={filter_by}")
            customer_number = self.get_string("customerNumber", call.arguments, None)

            filtered = ExecutionContext.filter_tasks(
                ctx.unassigned_tasks,
                filter_by,
                filter_val,
                customer_number,
            )
            return ToolCallResult.from_call(call, Peace._to_json(filtered))

    # ---------------- assignTask ------------------------------------------ #
    class AssignTaskApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(
                ...,
                alias="timeCreated",
                description='Time created ("mm/dd/yyyy, hh:mm AM/PM").',
            )
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the estate.",
            )
            operator_id: str = Field(
                ...,
                alias="operatorId",
                description="Identifier of the operator (always 42).",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="assignTask",
                description=(
                    "Assigns the task identified by timeCreated and customerNumber "
                    "to the operator with operatorId."
                ),
                schema=Peace.AssignTaskApi.Parameters,
            )

        def invoke(self, call, *, log: bool = False):  # noqa: D401
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            scenario = self.get_lab_agent().get_scenario_id()
            # always log
            self.get_lab_agent().execution_context.log_api_call(scenario, self.id, args)

            time_created = self.get_string("timeCreated", args)
            customer_number = self.get_string("customerNumber", args)
            operator_id = self.get_string("operatorId", args)

            if operator_id != "42":
                return ToolCallResult.from_call(
                    call,
                    "ERROR: You are trying to assign task to an operator other than yourself.",
                )

            ctx = self.get_execution_context()
            if ctx.unassigned_tasks is None:
                return ToolCallResult.from_call(
                    call,
                    f"ERROR: No task with timeCreated={time_created} and "
                    f"customerNumber={customer_number} exists.",
                )

            # task already assigned?
            for t in ctx.operator_tasks:
                if t.time_created == time_created and t.customer_number == customer_number:
                    return ToolCallResult.from_call(
                        call,
                        f"ERROR: Task with timeCreated={time_created} and "
                        f"customerNumber={customer_number} is already assigned to operator ID=42",
                    )

            # move task
            for i, t in enumerate(ctx.unassigned_tasks):
                if t.time_created == time_created and t.customer_number == customer_number:
                    ctx.unassigned_tasks.pop(i)
                    ctx.operator_tasks.append(t)
                    return ToolCallResult.from_call(
                        call,
                        f"Task with timeCreated={time_created} and customerNumber={customer_number} "
                        f"has been successfully assigned to operator {operator_id}",
                    )

            return ToolCallResult.from_call(
                call,
                f"ERROR: No task with timeCreated={time_created} and "
                f"customerNumber={customer_number} exists.",
            )

    # ---------------- getMyTasks ------------------------------------------ #
    class GetMyTasksApi(Api):
        class Parameters(ReactAgent.Parameters):
            operator_id: str = Field(
                ...,
                alias="operatorId",
                description="Identifier of the operator whose task list is requested.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getMyTasks",
                description="Returns the list of tasks assigned to the given operator.",
                schema=Peace.GetMyTasksApi.Parameters,
            )

        def invoke(self, call, *, log: bool = False):  # noqa: D401
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            if log:
                scenario = self.get_lab_agent().get_scenario_id()
                self.get_lab_agent().execution_context.log_api_call(scenario, self.id, args)

            operator_id = self.get_string("operatorId", args)
            if operator_id != "42":
                return ToolCallResult.from_call(call, "[]")  # empty list

            tasks_json = Peace._to_json(self.get_execution_context().operator_tasks)
            return ToolCallResult.from_call(call, tasks_json)

    # ---------------- closeTask ------------------------------------------- #
    class CloseTaskApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(
                ...,
                alias="timeCreated",
                description='Time created ("mm/dd/yyyy, hh:mm AM/PM").',
            )
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the estate.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="closeTask",
                description="Closes a task and marks it as completed.",
                schema=Peace.CloseTaskApi.Parameters,
            )

        def invoke(self, call, *, log: bool = False):  # noqa: D401
            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            time_created = self.get_string("timeCreated", args)
            customer_number = self.get_string("customerNumber", args)

            ctx = self.get_execution_context()
            for i, t in enumerate(ctx.operator_tasks):
                if t.time_created == time_created and t.customer_number == customer_number:
                    # always log
                    scenario = self.get_lab_agent().get_scenario_id()
                    self.get_lab_agent().execution_context.log_api_call(scenario, self.id, args)

                    ctx.operator_tasks.pop(i)
                    return ToolCallResult.from_call(
                        call,
                        f"Task with timeCreated={time_created} and customerNumber={customer_number} "
                        "has been successfully closed.",
                    )

            return ToolCallResult.from_call(
                call,
                f"ERROR: Task with timeCreated={time_created} and customerNumber="
                f"{customer_number} does not exist or has not been assigned to you",
            )

    # ---------------- getTaskContent / getFileContent / getDiaryEntries ---- #
    class GetTaskContentApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(..., alias="timeCreated")
            customer_number: str = Field(..., alias="customerNumber")

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getTaskContent",
                description="Gets the content of the specified task, including attachment IDs.",
                schema=Peace.GetTaskContentApi.Parameters,
            )

    class GetFileContentApi(Api):
        ID = "getFileContent"

        class Parameters(ReactAgent.Parameters):
            file_name: str = Field(..., alias="fileName")

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_=Peace.GetFileContentApi.ID,
                description="Returns the content of a file attached to task.",
                schema=Peace.GetFileContentApi.Parameters,
            )

    class GetDiaryEntriesApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(..., alias="timeCreated")
            customer_number: str = Field(..., alias="customerNumber")

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getDiaryEntries",
                description=(
                    "Returns the list of diary entries for the specified task. "
                    "Call it repeatedly for each task of interest."
                ),
                schema=Peace.GetDiaryEntriesApi.Parameters,
            )

    # ---------------- updateDiary ---------------------------------------- #
    class UpdateDiaryApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(..., alias="timeCreated")
            customer_number: str = Field(..., alias="customerNumber")
            category: Optional[str] = Field(
                None,
                alias="category",
                description="Optional category for grouping diary messages.",
            )
            message: str = Field(..., alias="message", description="Text of the message.")

            model_config = {"populate_by_name": True}

        _VALID_CATEGORIES: Sequence[str] = (
            "Proforma's Balance",
            "Paid bill",
            "Sent email asking for SKS",
            "SKS registered",
            "PoA uploaded in CF",
            "Created netbank to CPR",
            "Info email sent",
            "Transferred udlaeg",
        )

        def __init__(self) -> None:
            super().__init__(
                id_="updateDiary",
                description="Adds a message to the diary of the specified task.",
                schema=Peace.UpdateDiaryApi.Parameters,
            )

        def invoke(self, call, *, log: bool = False):  # noqa: D401
            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            category = self.get_string("category", args)
            if category not in self._VALID_CATEGORIES:
                return ToolCallResult.from_call(
                    call,
                    "Error: category for the message was not provided or not supported.",
                )

            time_created = self.get_string("timeCreated", args, "null")
            customer_number = self.get_string("customerNumber", args, "null")

            ctx = self.get_execution_context()
            task = ExecutionContext.filter_tasks(
                ctx.operator_tasks, "Time Created", time_created, customer_number
            )
            if len(task) != 1:
                return ToolCallResult.from_call(
                    call,
                    f"ERROR: No assigned task with Time Created = {time_created} "
                    f"for Customer Number = {customer_number}",
                )

            now_str = datetime.now().strftime("%b. %dth, %Y %H:%M")
            ctx.log_diary(
                task_time_created=time_created,
                task_customer_number=customer_number,
                category=category,
                message=(
                    f"{self.get_string('message', args)}\n\nSincerely, Operator ID=42\n{now_str}\n"
                ),
            )

            return ToolCallResult.from_call(call, "Diary was updated successfully with given message.")

    # ---------------- getRelatedPersons ---------------------------------- #
    class GetRelatedPersonsApi(Api):
        class Parameters(ReactAgent.Parameters):
            customer_number: str = Field(..., alias="customerNumber")

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getRelatedPersons",
                description=(
                    "Returns the list of persons related to the given estate. "
                    "Notice that the Customer Number returned by this tool is the unique "
                    "Customer Number of the related person, not the estate's Customer Number."
                ),
                schema=Peace.GetRelatedPersonsApi.Parameters,
            )

        def invoke(self, call, *, log: bool = False):  # noqa: D401
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            ctx = self.get_execution_context()
            if ctx.related_persons is not None:
                if log:
                    scenario = self.get_lab_agent().get_scenario_id()
                    args_no_thought = dict(call.arguments)
                    args_no_thought.pop("thought", None)
                    self.get_lab_agent().execution_context.log_api_call(scenario, self.id, args_no_thought)

                return ToolCallResult.from_call(
                    call,
                    Peace._to_json(ctx.related_persons.values()),
                )

            # first invocation → defer to canned data
            persons_result = super().invoke(call, log)
            if "ERROR" in str(persons_result.result):
                return persons_result

            person_list = Peace._from_json_persons(str(persons_result.result))
            ctx.related_persons = {p.customer_number: p for p in person_list}

            return ToolCallResult.from_call(call, Peace._to_json(person_list))

    # ---------------- updatePersonData ----------------------------------- #
    class UpdatePersonDataApi(Api):
        class Parameters(ReactAgent.Parameters):
            customer_number: str = Field(..., alias="customerNumber")
            relation_to_estate: Optional[str] = Field(None, alias="relationToEstate")
            name: Optional[str] = Field(None, alias="name")
            identification_completed: Optional[str] = Field(None, alias="identificationCompleted")
            power_of_attorney_type: Optional[str] = Field(None, alias="powerOfAttorneyType")
            address: Optional[str] = Field(None, alias="address")
            email: Optional[str] = Field(None, alias="email")
            phone_number: Optional[str] = Field(None, alias="phoneNumber")

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="updatePersonData",
                description=(
                    "Updates data for a related person of the estate. Do NOT use this "
                    "to read person's data. Only non-null fields are updated."
                ),
                schema=Peace.UpdatePersonDataApi.Parameters,
            )

        def invoke(self, call, *, log: bool = False):  # noqa: D401
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            # always log
            scenario = self.get_lab_agent().get_scenario_id()
            self.get_lab_agent().execution_context.log_api_call(scenario, self.id, args)

            customer_number = self.get_string("customerNumber", args, "null")
            person = self.get_execution_context().related_persons.get(customer_number)  # type: ignore[union-attr]
            if person is None:
                return ToolCallResult.from_call(
                    call,
                    f"ERROR: Cannot update non-existing customer with Customer Number={customer_number}",
                )

            # update fields if provided
            for fld in (
                "relationToEstate",
                "name",
                "identificationCompleted",
                "powerOfAttorneyType",
                "address",
                "email",
                "phoneNumber",
            ):
                if fld in args and args[fld]:
                    setattr(person, Peace.Person.model_fields[fld].alias, args[fld])  # type: ignore[arg-type]

            return ToolCallResult.from_call(
                call,
                f"Data for Customer Number={customer_number} have been updated successfully.",
            )

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #
    def __init__(self) -> None:
        super().__init__(
            id_="PEACE",
            description=(
                "Tool to manage process tasks, diaries and personal data for estates "
                "and related persons. It cannot access customer accounts."
            ),
            tools=(
                Peace.GetUnassignedTasksApi(),
                Peace.AssignTaskApi(),
                Peace.GetMyTasksApi(),
                Peace.CloseTaskApi(),
                Peace.GetTaskContentApi(),
                Peace.GetFileContentApi(),
                Peace.GetDiaryEntriesApi(),
                Peace.UpdateDiaryApi(),
                Peace.GetRelatedPersonsApi(),
                Peace.UpdatePersonDataApi(),
            ),
        )

        # context (verbatim from Java)
        self.context = (
            "  * Documents you handle are in Danish, this means sometime you have to translate "
            'tool calls parameters. For example, "Customer Number" is sometimes indicated as '
            '"afdøde CPR" or "CPR" in documents.\n'
            "  * Probate Certificate is a document that lists heirs for one estate; it is "
            'sometime indicated as "SKS".\n'
            "  * Power of Attorney document (PoA) is a document that define people's legal rights "
            "over the estate's asset. It is sometime indicated as \"PoA\".\n"
            "  * Proforma Document is a document containing the amount of cash available on "
            "estate's account at the time of their death.\n"
            "  * Probate Court (Skifteretten) Notification Letter is an official letter from "
            "Skifteretten informing the heirs about the opening of an estate after a person’s "
            "death; this is NOT same as SKS, even it might notify heirs that SKS has been issued.\n"
            "  * When asked to determine the type of an attachment, don't simply provide the "
            "file name but try to infer its type and provide a short summary of contents.\n"
            "  * To indicate time stamps, always use \"mm/dd/yyyy, hh:mm AM/PM\" format "
            '(e.g. "4/16/2025, 2:31 PM").\n'
            "  * For amounts, always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\").\n"
            f"  * Tasks are described by the below JSON schema:\n{JsonSchema.get_json_schema(Peace.Task)}\n"
            "  * Payment tasks are identified by having Step Name=\"Handle Account 1\".\n"
            "  * When asked to provide the content of a task or an attachment, STRICTLY provide "
            "the complete content without summarisation, unless explicitly requested.\n"
            "  * Data about persons related to estates are described by the below JSON schema:\n"
            f"{JsonSchema.get_json_schema(Peace.Person)}\n"
            "  * Persons are uniquely identified by their Customer Number (sometimes CPR).\n"
            "  * When asked to update person's data, you do not need to retrieve the full record; "
            "just update the fields provided by the user, ignoring others.\n"
            "  * When writing diary entries you MUST use one of the predefined categories.\n"
            "  * The diary is not to be used for normal communication; create entries only when "
            "explicitly instructed.\n"
        )

        # examples (verbatim from Java)
        self.examples = (
            "Input & Context:\n\n<user_command>\n"
            "List all unassigned tasks with Step Name='Handle Account 1' for Customer Number 123\n"
            "</user_command>\n\n"
            "Correct Output:\n\n"
            'Call "getUnassignedTasks" tool with following parameters: '
            '{"customerNumber":"123","filterBy":"Step Name","filterValue":"Handle Account 1"}, '
            " then return the actual list of tasks.\n\n"
            "Incorrect Output:\n\n"
            'Call "getUnassignedTasks" tool with following parameters: '
            '{"customerNumber":"123","filterBy":"Step Name","filterValue":"Handle Account 1"}, '
            ' then return "I have listed all unassigned tasks ...".\n'
            # (remaining examples omitted for brevity)
        )


# --------------------------------------------------------------------------- #
# Module exports
# --------------------------------------------------------------------------- #
__all__: Sequence[str] = ("Peace",)
