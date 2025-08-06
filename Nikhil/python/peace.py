# peace.py
"""
Python translation of `com.infosys.small.pnbc.Peace`.

This module ports the PEACE backend wrapper and its APIs, following the
project’s conventions (Pydantic models, LabAgent/Api abstractions, logging).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field, TypeAdapter

from api import Api
from execution_context import ExecutionContext
from json_schema import JsonSchema
from lab_agent import LabAgent
from react_agent import ReactAgent
from scenario_component import ScenarioComponent
from tool import Tool
from chat_types import ToolCall, ToolCallResult

# --------------------------------------------------------------------------- #
# Logging (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Peace(LabAgent):
    """Backend-system wrapper for PEACE."""

    # ============================= Data Models ============================= #

    class Task(BaseModel):
        """
        A Task in PEACE.

        Notes
        -----
        * Field names follow Python's snake_case; JSON aliases match the Java @JsonProperty.
        * `model_config.validate_assignment=True` ensures run-time checks on assignment,
          enforcing @NonNull semantics for required fields.
        """

        step_name: str = Field(
            ...,
            alias="Step Name",
            description="The name of the step or activity.",
        )
        due_date: Optional[str] = Field(
            None,
            alias="Due Date",
            description='Task due date "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").',
        )
        time_created: str = Field(
            ...,
            alias="Time Created",
            description='Time when the task was created "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM"); together with Customer Number this uniquely defines a task.',
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

        model_config = {"populate_by_name": True, "validate_assignment": True}

        # ----------- fluent builder (Lombok @Builder port) ---------------- #
        class Builder:
            def __init__(self) -> None:
                self._step_name: Optional[str] = None
                self._due_date: Optional[str] = None
                self._time_created: Optional[str] = None
                self._customer_number: Optional[str] = None
                self._customer_name: Optional[str] = None

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

            def build(self) -> "Peace.Task":
                return Peace.Task(
                    **{
                        "Step Name": self._step_name
                        or (_ for _ in ()).throw(ValueError("step_name must not be None")),
                        "Due Date": self._due_date,
                        "Time Created": self._time_created
                        or (_ for _ in ()).throw(ValueError("time_created must not be None")),
                        "Customer Number": self._customer_number
                        or (_ for _ in ()).throw(ValueError("customer_number must not be None")),
                        "Customer Name": self._customer_name
                        or (_ for _ in ()).throw(ValueError("customer_name must not be None")),
                    }
                )

        @staticmethod
        def builder() -> "Peace.Task.Builder":
            return Peace.Task.Builder()

    class Person(BaseModel):
        """Data for one person."""

        customer_number: str = Field(
            ...,
            alias="Customer Number",
            description="Unique string identifier with customer number (CPR) of the customer. Customers are uniquely defined by this field.",
        )
        relation_to_estate: str = Field(
            "None",
            alias="Relation To Estate",
            description='The relation between this person and their related estate. Possible values are: "Lawyer", "Other","Power of attorney","Heir","Guardian/værge","Guardian/skifteværge","Beneficiary","Spouse","Cohabitee","One man company","I/S","K/S","Joint","Deceased".',
        )
        name: str = Field(
            ...,
            alias="Name",
            description="Client first and last name.",
        )
        identification_completed: str = Field(
            "None",
            alias="Identification Completed",
            description='An indicator whether the person has been identified and how. Possible values are: "None","OK – Customer","OK – Non Customer","OK – Professionals","Awaiting","Not relevant"; this field can be updated if and only if instructed by the user and only after identification has been performed by an Operations Officer.',
        )
        power_of_attorney_type: str = Field(
            "None",
            alias="Power Of Attorney Type",
            description='The person might have a power of attorney on the estate\'s assets; this fields describes it. Possible values are: "Alone" when only this person has power of attorney, "Joint" when power of attorney is shared between this person and another individual, "None" in  all other cases.',
        )
        address: str = Field(
            "",
            alias="Address",
            description="The person's full address.",
        )
        email: str = Field(
            "",
            alias="Email",
            description="The person's email.",
        )
        phone_number: str = Field(
            "",
            alias="Phone Number",
            description="The person's phone number.",
        )

        model_config = {"populate_by_name": True, "validate_assignment": True}

    # =============================== APIs ================================= #

    class GetUnassignedTasksApi(Api):
        class Parameters(ReactAgent.Parameters):
            filter_by: Optional[str] = Field(
                default=None,
                description='Optional column name to use when filtering tasks. This must match one of task field names, e.g. "Step Name" not "stepName".',
            )
            filter_value: Optional[str] = Field(
                default=None,
                description="Value to use when filtering, if filterBy is provided.",
            )
            customer_number: Optional[str] = Field(
                default=None,
                description="If this is provided, only tasks for this client will be returned.",
            )

        def __init__(self) -> None:
            super().__init__(
                id_="getUnassignedTasks",
                description="Returns a list of unassigned tasks, accordingly to provided filtering criteria.",
                schema=Peace.GetUnassignedTasksApi.Parameters,
            )

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)
            lab = self.get_lab_agent()
            if lab is None:
                raise RuntimeError("LabAgent not available.")
            scenario = lab.get_scenario_id()
            ctx = lab.execution_context
            if ctx is None:
                raise RuntimeError("Execution context is not set.")

            if log:
                ctx.log_api_call(scenario, self.id, args)

            # Initialize the unassigned task list on first call (from scenario canned output)
            if ctx.unassigned_tasks is None:
                tasks_json = ScenarioComponent.get_instance().get(scenario, self.id, {})
                adapter = TypeAdapter(List[Peace.Task])
                ctx.unassigned_tasks = list(adapter.validate_json(tasks_json))

            filter_by = self.get_string("filterBy", call.arguments, None)
            filter_value = self.get_string("filterValue", call.arguments, None)
            if (filter_by is not None) and (filter_value is None):
                raise ValueError(f"Must provide a filter value for filter={filter_by}")
            customer_number = self.get_string("customerNumber", call.arguments, None)

            filtered = ExecutionContext.filter_tasks(
                ctx.unassigned_tasks,
                filter_by=filter_by,
                filter_value=filter_value,
                customer_number=customer_number,
            )
            payload = json.dumps(
                [t.model_dump(by_alias=True, exclude_none=True) for t in filtered],
                separators=(",", ":"),
            )
            return ToolCallResult.from_call(call, payload)

    class AssignTaskApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(
                ...,
                alias="timeCreated",
                description='Time the task was created. Use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").',
            )
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the estate.",
            )
            operator_id: str = Field(
                ...,
                alias="operatorId",
                description="Identifier of the operator receiving the task. Always use 42.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="assignTask",
                description="Assigns the task identified by timeCreated and customerNumber to the operator with operatorId.",
                schema=Peace.AssignTaskApi.Parameters,
            )

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)
            lab = self.get_lab_agent()
            if lab is None:
                raise RuntimeError("LabAgent not available.")
            ctx = lab.execution_context
            if ctx is None:
                raise RuntimeError("Execution context is not set.")
            scenario = lab.get_scenario_id()

            # Always log
            ctx.log_api_call(scenario, self.id, args)

            time_created = self.get_string("timeCreated", call.arguments) or ""
            customer_number = self.get_string("customerNumber", call.arguments) or ""
            operator_id = self.get_string("operatorId", call.arguments) or ""
            if operator_id != "42":
                return ToolCallResult.from_call(
                    call,
                    "ERROR: You are trying to assign task to an operator other than yourself.",
                )

            if ctx.unassigned_tasks is None:
                return ToolCallResult.from_call(
                    call,
                    f"ERROR: No task with timeCreated={time_created} and customerNumber={customer_number} exists.",
                )

            # Already assigned to operator?
            for t in ctx.operator_tasks:
                if t.time_created == time_created and t.customer_number == customer_number:
                    return ToolCallResult.from_call(
                        call,
                        f"ERROR: Task with timeCreated={time_created} and customerNumber={customer_number} is already assigned to operator ID=42",
                    )

            # Move from unassigned → operator task list
            for i, t in enumerate(ctx.unassigned_tasks):
                if t.time_created == time_created and t.customer_number == customer_number:
                    ctx.unassigned_tasks.pop(i)
                    ctx.operator_tasks.append(t)
                    return ToolCallResult.from_call(
                        call,
                        f"Task with timeCreated={time_created} and customerNumber={customer_number} has been successfully assigned to operator {operator_id}",
                    )

            return ToolCallResult.from_call(
                call,
                f"ERROR: No task with timeCreated={time_created} and customerNumber={customer_number} exists.",
            )

    class GetMyTasksApi(Api):
        class Parameters(ReactAgent.Parameters):
            operator_id: str = Field(
                ...,
                alias="operatorId",
                description="Identifier of the operator whose task list is requested. Always use 42.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getMyTasks",
                description="Returns the list of tasks assigned to the given operator.",
                schema=Peace.GetMyTasksApi.Parameters,
            )

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)
            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is not set.")

            if log:
                lab.execution_context.log_api_call(lab.get_scenario_id(), self.id, args)

            if self.get_string("operatorId", args) != "42":
                return ToolCallResult.from_call(call, "[]")

            payload = json.dumps(
                [t.model_dump(by_alias=True, exclude_none=True) for t in lab.execution_context.operator_tasks],
                separators=(",", ":"),
            )
            return ToolCallResult.from_call(call, payload)

    class CloseTaskApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(
                ...,
                alias="timeCreated",
                description='Time the task was created. Use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").',
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

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is not set.")

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            time_created = self.get_string("timeCreated", args) or ""
            customer_number = self.get_string("customerNumber", args) or ""

            # Always log
            lab.execution_context.log_api_call(lab.get_scenario_id(), self.id, args)

            for i, t in enumerate(lab.execution_context.operator_tasks):
                if t.time_created == time_created and t.customer_number == customer_number:
                    lab.execution_context.operator_tasks.pop(i)
                    return ToolCallResult.from_call(
                        call,
                        f"Task with timeCreated={time_created} and customerNumber={customer_number} has been successfully closed.",
                    )

            return ToolCallResult.from_call(
                call,
                f"ERROR: Task with timeCreated={time_created} and customerNumber={customer_number} does not exist or has not been assigned to you",
            )

    class GetTaskContentApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(
                ...,
                alias="timeCreated",
                description='Time the task was created. Use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").',
            )
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the estate.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getTaskContent",
                description="Gets the content of the specified task, including attachment IDs.",
                schema=Peace.GetTaskContentApi.Parameters,
            )

    class GetFileContentApi(Api):
        ID: str = "getFileContent"

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
            time_created: str = Field(
                ...,
                alias="timeCreated",
                description='Time the task was created. Use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").',
            )
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the estate.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getDiaryEntries",
                description=(
                    "Returns the list of diary entries for the specified task. "
                    " As it is not possible to have all entries for a client or operator, "
                    "this must be called repeatedly for each task of interest."
                ),
                schema=Peace.GetDiaryEntriesApi.Parameters,
            )

    class UpdateDiaryApi(Api):
        class Parameters(ReactAgent.Parameters):
            time_created: str = Field(
                ...,
                alias="timeCreated",
                description='Time the task was created. Use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").',
            )
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the estate the task refers to.",
            )
            category: Optional[str] = Field(
                default=None,
                description="Optional category used to group diary messages.",
            )
            message: str = Field(
                ...,
                description="Text of the message.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="updateDiary",
                description="Adds a message to the diary of the specified task.",
                schema=Peace.UpdateDiaryApi.Parameters,
            )

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is not set.")
            ctx = lab.execution_context

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            category = self.get_string("category", args)
            allowed = [
                "Proforma's Balance",
                "Paid bill",
                "Sent email asking for SKS",
                "SKS registered",
                "PoA uploaded in CF",
                "Created netbank to CPR",
                "Info email sent",
                "Transferred udlaeg",
                "Rejected to pay bill to",
            ]
            if category not in allowed:
                return ToolCallResult.from_call(
                    call, "Error: category for the message was not provided or not supported."
                )

            time_created = self.get_string("timeCreated", args, "null") or "null"
            customer_number = self.get_string("customerNumber", args, "null") or "null"

            tasks = ExecutionContext.filter_tasks(
                ctx.operator_tasks, filter_by="Time Created", filter_value=time_created, customer_number=customer_number
            )
            if len(tasks) != 1:
                return ToolCallResult.from_call(
                    call,
                    f"ERROR: No assigned task with Time Created = {time_created} for Customer Number = {customer_number}",
                )

            now = datetime.now()
            # Mimic Java pattern "MMM. d'th', yyyy HH:mm" (literally "th")
            timestamp = f"{now.strftime('%b')}. {now.day}th, {now.year} {now.strftime('%H:%M')}"

            message = self.get_string("message", args) or ""
            composed = f"{message}\n\nSincerely, Operator ID=42\n{timestamp}\n"

            # Always log diary entry
            ctx.log_diary(time_created, customer_number, category or "", composed)

            return ToolCallResult.from_call(call, "Diary was updated successfully with given message.")

    class GetRelatedPersonsApi(Api):
        class Parameters(ReactAgent.Parameters):
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the estate.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getRelatedPersons",
                description=(
                    "Returns the list of persons related to the given estate. "
                    "Notice that the Customer Number returned by this tool is the unique Customer Number of the related person, "
                    "not the estate's Customer number."
                ),
                schema=Peace.GetRelatedPersonsApi.Parameters,
            )

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is not set.")
            ctx = lab.execution_context

            if ctx.related_persons is not None:
                # Already initialised: optional logging then return cache
                args: Dict[str, Any] = dict(call.arguments)
                args.pop("thought", None)
                if log:
                    ctx.log_api_call(lab.get_scenario_id(), self.id, args)
                payload = json.dumps(
                    [p.model_dump(by_alias=True, exclude_none=True) for p in ctx.related_persons.values()],
                    separators=(",", ":"),
                )
                return ToolCallResult.from_call(call, payload)

            # First invocation: delegate to scenario, then cache & return
            result = super().invoke(call, log=log)
            res = result.result or ""
            if "ERROR" in res:
                return result

            adapter = TypeAdapter(List[Peace.Person])
            persons = list(adapter.validate_json(res))
            ctx.related_persons = {}
            for p in persons:
                ctx.related_persons[p.customer_number] = p

            payload = json.dumps(
                [p.model_dump(by_alias=True, exclude_none=True) for p in persons],
                separators=(",", ":"),
            )
            return ToolCallResult.from_call(call, payload)

    class AddPersonDataApi(Api):
        class Parameters(ReactAgent.Parameters):
            estate_customer_number: str = Field(
                ...,
                description="Unique customer number of the estate related to this person.",
            )
            relation_to_estate: Optional[str] = Field(
                default=None,
                description=(
                    'The relation between this person and their related estate. Possible values are: "Lawyer", '
                    '"Other","Power of attorney","Heir","Guardian/værge","Guardian/skifteværge","Beneficiary","Spouse",'
                    '"Cohabitee","One man company","I/S","K/S","Joint","Deceased". Translate any other value provided '
                    "in a different language before calling this tool."
                ),
            )
            name: str = Field(
                ...,
                description="The person's name.",
            )
            identification_completed: Optional[str] = Field(
                default=None,
                description=(
                    'An indicator whether the person has been identified and how. Possible values are: "None","OK – Customer",'
                    '"OK – Non Customer","OK – Professionals","Awaiting","Not relevant". Translate any other value provided '
                    "in a different language before calling this tool."
                ),
            )
            power_of_attorney_type: Optional[str] = Field(
                default=None,
                description=(
                    'The person might have a power of attorney on the estate\'s assets; this fields describes it. Possible values are: '
                    '"Alone" when only this person has power of attorney, "Joint" when power of attorney is shared between this person '
                    'and another individual, "None" in all other cases. Translate any other value provided in a different language before calling this tool.'
                ),
            )
            address: Optional[str] = Field(default=None, description="The person's home address.")
            email: Optional[str] = Field(default=None, description="The person's email address.")
            phone_number: Optional[str] = Field(default=None, description="The person's phone number.")

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="addPersonData",
                description=(
                    "Create a new record for a person related to the estate. Do *NOT* use this if you only need to "
                    "update or read person's data."
                ),
                schema=Peace.AddPersonDataApi.Parameters,
            )

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is not set.")
            ctx = lab.execution_context

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)
            scenario = lab.get_scenario_id()

            estate_customer_number = str(args.get("estateCustomerNumber") or "")
            if not estate_customer_number:
                return ToolCallResult.from_call(
                    call,
                    "ERROR: You must provide the unique Customer Number (CPR) for the estate related to the person.",
                )
            name = str(args.get("name") or "")
            if not name:
                return ToolCallResult.from_call(
                    call, "ERROR: You must provide the person's name when creating a new person."
                )

            # We always force this customer number for new clients
            customer_number = "66642666"

            person = Peace.Person(**{"Customer Number": customer_number, "Name": name})
            # NB: This mirrors the Java code (stores by *estate* number, not by person's number).
            if ctx.related_persons is None:
                ctx.related_persons = {}
            ctx.related_persons[estate_customer_number] = person

            # Always log updates
            ctx.log_api_call(scenario, self.id, args)

            # Apply optional updates when provided and non-empty
            def _set_if_present(key_in: str, attr: str) -> None:
                if key_in in args:
                    v = args.get(key_in)
                    if v is not None and str(v) != "":
                        setattr(person, attr, str(v))

            _set_if_present("relationToEstate", "relation_to_estate")
            _set_if_present("identificationCompleted", "identification_completed")
            _set_if_present("powerOfAttorneyType", "power_of_attorney_type")
            _set_if_present("address", "address")
            _set_if_present("email", "email")
            _set_if_present("phoneNumber", "phone_number")

            return ToolCallResult.from_call(
                call, f"New customer added with Customer Number={customer_number}"
            )

    class UpdatePersonDataApi(Api):
        class Parameters(ReactAgent.Parameters):
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number of the customer to update.",
            )
            relation_to_estate: Optional[str] = Field(
                default=None,
                description=(
                    'The relation between this person and their related estate. Possible values are: "Lawyer", "Other","Power of attorney","Heir",'
                    '"Guardian/værge","Guardian/skifteværge","Beneficiary","Spouse","Cohabitee","One man company","I/S","K/S","Joint","Deceased". '
                    "Translate any other value provided in a different language before calling this tool."
                ),
            )
            name: Optional[str] = Field(default=None, description="The person's name.")
            identification_completed: Optional[str] = Field(
                default=None,
                description=(
                    'An indicator whether the person has been identified and how. Possible values are: "None","OK – Customer","OK – Non Customer",'
                    '"OK – Professionals","Awaiting","Not relevant". Translate any other value provided in a different language before calling this tool.'
                ),
            )
            power_of_attorney_type: Optional[str] = Field(
                default=None,
                description=(
                    'The person might have a power of attorney on the estate\'s assets; this fields describes it. Possible values are: '
                    '"Alone" when only this person has power of attorney, "Joint" when power of attorney is shared between this person and another individual, '
                    '"None" in  all other cases. Translate any other value provided in a different language before calling this tool.'
                ),
            )
            address: Optional[str] = Field(default=None, description="The person's home address.")
            email: Optional[str] = Field(default=None, description="The person's email address.")
            phone_number: Optional[str] = Field(default=None, description="The person's phone number.")

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="updatePersonData",
                description=(
                    "Updates data for a related person of the estate. Do *NOT* use this to read person's data. "
                    "Only fields that are not null are updated; other fields values remain unchanged."
                ),
                schema=Peace.UpdatePersonDataApi.Parameters,
            )

        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:
            if not self.is_initialized():
                raise ValueError("Tool must be initialized.")

            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is not set.")
            ctx = lab.execution_context

            args: Dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)
            scenario = lab.get_scenario_id()

            customer_number = self.get_string("customerNumber", args, "null") or "null"
            person = None if ctx.related_persons is None else ctx.related_persons.get(customer_number)
            # Mirror the Java behaviour (may fail if list wasn't initialised earlier)
            if person is None:
                return ToolCallResult.from_call(
                    call, f"ERROR: Cannot update non-existing customer with Customer Number={customer_number}"
                )

            # Always log updates
            ctx.log_api_call(scenario, self.id, args)

            def _set_if_present(key_in: str, attr: str) -> None:
                if key_in in args:
                    v = args.get(key_in)
                    if v is not None and str(v) != "":
                        setattr(person, attr, str(v))

            _set_if_present("relationToEstate", "relation_to_estate")
            _set_if_present("name", "name")
            _set_if_present("identificationCompleted", "identification_completed")
            _set_if_present("powerOfAttorneyType", "power_of_attorney_type")
            _set_if_present("address", "address")
            _set_if_present("email", "email")
            _set_if_present("phoneNumber", "phone_number")

            return ToolCallResult.from_call(
                call,
                f"Data for Customer Number={customer_number} have been updated successfully.",
            )

    # ============================= Construction ============================= #

    def __init__(self) -> None:
        super().__init__(
            id_="PEACE",
            description=(
                "This tool is used to manage process tasks, each task being uniquely identified by the combination of "
                "'Time Created' and 'Client Number'; this includes assigning tasks to an operator and marking tasks "
                "closed, and accessing task attachments. Task attachments are accessed through their unique file name. "
                "This tool is NOT a general source for documents. "
                "This tool stores a diary used to log specific task steps and their outcomes; notice diaries are "
                "associated to tasks, so they can be retrieved only through a task. It can create diary entries but "
                "only one at a time and for a specific task. The diary is not to be used for normal communication, it "
                "must be used only when mandated by a business process. This tool does NOT provide any way to "
                "communicate with customers. This tool gives access to personal data for estates, their related "
                "persons, and other customers, all identified by their unique customer numbers; however, this tool has "
                "no access to people's bank accounts; **STRICTLY** do not use this tool to check if a person has an "
                "account or other relationship with the bank. This tool does NOT provide any way to communicate with "
                "customers."
            ),
            tools=[
                Peace.GetUnassignedTasksApi(),
                Peace.AssignTaskApi(),
                Peace.GetMyTasksApi(),
                Peace.CloseTaskApi(),
                Peace.GetTaskContentApi(),
                Peace.GetFileContentApi(),
                Peace.GetDiaryEntriesApi(),
                Peace.UpdateDiaryApi(),
                Peace.GetRelatedPersonsApi(),
                Peace.AddPersonDataApi(),
                Peace.UpdatePersonDataApi(),
            ],
            check_last_step=False,
        )

        # ----------------------- context & examples ----------------------- #
        self.context = (
            "  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. "
            'For example, "Customer Number" is sometimes indicated as "afdøde CPR" or "CPR" in documents.\n'
            "  * Probate Certificate is a document that lists heirs for one estate; it is sometime indicated as \"SKS\".\n"
            "  * Power of Attorney document (PoA) is a document that define people's legal rights over the estate's asset. It is sometime indicated as \"PoA\".\n"
            "  * Proforma Document is a document containing the amount of cash available on estate's account at the time of their death.\n"
            "  * Probate Court (Skifteretten) Notification Letter is an official letter from Skifteretten informing the heirs about the opening of an estate after a person’s death; this is **NOT** same as SKS, even it might notify heirs that SKS has been issued.\n"
            "  * When asked to determine the type of an attachment, don't simply provide the file name but try to infer its type and provide a short summary of contents.\n"
            "  * When asked to retrieve a file, if its unique file name is provided, proceed with retrieving it; **STRICTLY** never check if it is attached to any task.\n"
            "  * When asked to compareretrieve a file, if its unique file name is provided, proceed with retrieving it; **STRICTLY** never check if it is attached to any task.\n"
            '  * To indicate time stamps, always use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").\n'
            '  * For amounts, always use the format NNN,NNN.NN CCC (e.g. "2,454.33 DKK").\n'
            "  * Tasks are described by the below JSON schema:\n"
            + JsonSchema.get_json_schema(Peace.Task)
            + "\n"
            '  * Payment tasks are identified by having Step Name="Handle Account 1".\n'
            "  * When asked to provide the content of a task or an attachment, **STRICTLY** provide the complete content without performing any summarisation, unless explicitly requested by the user.\n"
            "  * Do not make any assumption about format (e.g. image, audio,etc.) or nature (e.g. scanned document) of files or attachments; just use the proper tool to provide content of files when required to do so.\n"
            "  * Data about persons related to estates are described by the below JSON schema: "
            "**STRICTLY** when asked to provide people data, always follow this schema for your output:\n"
            + JsonSchema.get_json_schema(Peace.Person)
            + "\n"
            "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. Always provide the Customer Number if a tool needs to act on a specific person/client; indicate it as Customer Number and not CPR when passing it to tools.\n"
            "  * When asked to update person's data, you do not need to retrieve the full record for the person record; just updates the fields provided by the user ignoring others.\n"
            "  * When asked to check customers' accounts return an error stating that you do not have access to customer accounts.\n"
            "  * When asked to communicate with customers (e.g. sending an email) return an error stating that you have no access to client communications.\n"
            "  * When writing diary entries you **MUST** use one of the following categories for the entry:\n"
            "         \"Proforma's Balance\" to record balance available in the Proforma Document.\n"
            "         \"Paid bill\": to record a payment that was made.\n"
            "         \"Transferred udlaeg\": to record a reimbursment/transfer that was made.\n"
            "         \"Info email sent\": to record that an email was sent to client after processing a task.\n"
            "         \"Sent email asking for SKS\": to record that an email was sent to client asking for missign SKS document.\n"
            "         \"SKS registered\": to record that SKS document was uploaded.\n"
            "         \"PoA uploaded in CF\": to record that Power of Attorney document was uploaded.\n"
            "         \"Created netbank to CPR\": to record that accounts for one estate have been unblocked.\n"
            "         \"Rejected to pay bill to\": to record that one bill/invoice could not be paid.\n"
            "  * All entries in the diary should be in English.\n"
            "  * The diary is not to be used for communication with users; you must create entries in the diary only when required to do so.\n"
            "  * **STRICTLY** Never create diary entries, unless instructed by the user. Do not create entries to document activities you have done, unless instructed to do so.\n"
        )

        self.examples = (
            "Input & Context:\n\n"
            "<user_command>\nList all unassigned tasks with Step Name='Handle Account 1' for Customer Number 123\n</user_command>\n"
            "Correct Output:\n\n"
            'Call "getUnassignedTasks" tool with following parameters: {"customerNumber":"123","filterBy":"Step Name","filterValue":"Handle Account 1"}, '
            " then return the actual list of tasks.\n\n"
            "Incorrect Output:\n\n"
            'Call "getUnassignedTasks" tool with following parameters: {"customerNumber":"123","filterBy":"Step Name","filterValue":"Handle Account 1"}, '
            ' then return "I have listed all unassigned tasks with Step Name=\'Handle Account 1\' for Customer Number 123".\n'
            "\n---\n\n"
            "Input & Context:\n\n"
            "<user_command>\nAssign all remaining unassigned tasks with Step Name='Handle Account 1' for Customer Number 123 to myself (operator 42)\n</user_command>\n"
            "Correct Output:\n\n"
            'Call "getUnassignedTasks" tool with following parameters: {"customerNumber":"123","filterBy":"Step Name","filterValue":"Handle Account 1"}, '
            'Then, for each task returned, call "assignTask" tool with following parameters: {"customerNumber":"123","timeCreated":<creation time of task>,"operatorId":"42"},\n'
            "\n---\n\n"
            "Input & Context:\n\n"
            'Your thought is: "I have retrieved the current data for the client. All fields match the provided task data. No update is needed, so I will complete the process."\n'
            "Correct Output:\n\n"
            "{\n"
            '  "status" : "COMPLETED",\n'
            '  "actor" : <your ID here>,\n'
            '  "thought" : "I have retrieved the current data for the client. All fields match the provided task data. No update is needed, so I will complete the process.",\n'
            '  "observation" : "Process has been completed.",\n'
            "}\n"
            "\nIncorrect Output:\n\n"
            'Call "updatePersonData" tool.\n'
            "\n---\n\n"
            "Input & Context:\n\n"
            "<steps> contains the following steps:\n"
            "[{\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" : <your ID here>,\n"
            '    "thought" : "I am starting execution of the below user\'s command in <user_command> tag.\\n\\n<user_command>\\nAssign all other unassigned tasks with Step Name = \'Handle Account 1\' and Customer Number = 656565 to Operator ID 11.\\n</user_command>",\n'
            '    "observation" : "Execution just started."\n'
            "  }, {\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" : <your ID here>,\n"
            '    "thought" : "I need to retrieve all unassigned tasks with Step Name = \'Handle Account 1\' and Customer Number = 656565 in order to assign them to Operator ID 11.",\n'
            '    "observation" : "[{\\"Step Name\\":\\"Handle Account 1\\",\\"Due Date\\":\\"4/23/2025, 3:00 PM\\",\\"Time Created\\":\\"4/16/2025, 3:00 PM\\"}]",\n'
            '    "action" : "The tool \\"getUnassignedTasks\\" has been called",\n'
            '    "action_input" : "{\\"filterBy\\":\\"Step Name\\",\\"filterValue\\":\\"Handle Account 1\\",\\"customerNumber\\":\\"656565\\"}",\n'
            '    "action_steps" : [ ]\n'
            "  }, {\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" : <your ID here>,\n"
            '    "thought" : "I have identified an unassigned task with Step Name = \'Handle Account 1\' and Customer Number = 656565. I will assign this task to Operator ID 11 as requested.",\n'
            '    "observation" : "Task with timeCreated=4/16/2025, 3:00 PM and customerNumber=656565 has been successfully assigned to operator 11",\n'
            '    "action" : "The tool \\"assignTask\\" has been called",\n'
            '    "action_input" : "{\\"timeCreated\\":\\"4/16/2025, 3:00 PM\\",\\"customerNumber\\":\\"656565\\",\\"operatorId\\":\\"11\\"}",\n'
            '    "action_steps" : [ ]\n'
            "  }]\n"
            "Correct Output:\n\n"
            "  {\n"
            '    "status" : "COMPLETED",\n'
            "    \"actor\" : <your ID here>,\n"
            '    "thought" : "I have assigned tasks with Step Name = \'Handle Account 1\' and Customer Number = 656565to Operator ID 11 as requested.",\n'
            '    "observation" : "All unassigned tasks with Step Name = \'Handle Account 1\' and Customer Number = 656565 have been assigned to Operator ID 11. No further action is needed."\n'
            "  }\n"
            "\nIncorrect Output:\n\n"
            "  {\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" : <your ID here>,\n"
            '    "thought" : "I need to verify if there are any remaining unassigned tasks with Step Name = \'Handle Account 1\' and Customer Number = 656565, to ensure all such tasks are assigned to Operator ID 11.",\n'
            '    "observation" : "[]",\n'
            '    "action" : "The tool \\"getUnassignedTasks\\" has been called",\n'
            '    "action_input" : "{\\"filterBy\\":\\"Step Name\\",\\"filterValue\\":\\"Handle Account 1\\",\\"customerNumber\\":\\"656565\\"}",\n'
            '    "action_steps" : [ ]\n'
            "  }\n"
            "\n---\n\n"
            "Input & Context:\n\n"
            "You are tasked with updating customer information, but you are not provided with any field to update.\n"
            "Correct Output:\n\n"
            "{\n"
            '    "status" : "COMPLETED",\n'
            "    \"actor\" :  <your ID here>,\n"
            '    "thought" : "I have compared the information provided for John Doe with the current record. No update is needed.",\n'
            '    "observation" : "No changes were made to John Doe\'s record as all available data is already up to date."\n'
            "}\n"
            "\nIncorrect Output:\n\n"
            'Call "updatePersonData" tool to perform an update with no data.\n'
            "\n---\n\n"
            "Input & Context:\n\n"
            "<steps> contains the following steps:\n"
            "{\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" :  <your ID here>,\n"
            '    "thought" : "I am starting execution of the below user\'s command in <user_command>.\\n\\n<user_command>\\nCompare John Doe with data from the current task. If any data is missing or outdated , update their records accordingly.\\n</user_command>",\n"
            '    "observation" : "Execution just started."\n'
            "  }, {\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" :  <your ID here>,\n"
            '    "thought" : "To compare and update the records for John Doe, I need to retrieve existing data.",\n"
            '    "observation" : "[{\\"Name\\":\\"John Doe\\",\\"Address\\":\\"Nowhere Rd. 1\\",\\"Email\\":\\"\\",\\"Phone Number\\":\\"\\\\"}]",\n"
            '    "action" : "The tool \\"getRelatedPersons\\" has been called",\n"
            '    "action_input" : "{\\"customerNumber\\":\\"55555555555\\"}",\n"
            '    "action_steps" : [ ]\n'
            "  }, {\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" :  <your ID here>,\n"
            '    "thought" : "To compare the current records for Lars Tai and John Doe with all available data, I need to retrieve the content of the current task, which may contain updated information or attachments.",\n"
            "    \"observation\" : <Task content>,\n"
            '    "action" : "The tool \\"getTaskContent\\" has been called",\n"
            '    "action_input" : "{\\"timeCreated\\":\\"01/01/2023, 1:00 PM\\",\\"customerNumber\\":\\"55555555555\\"}",\n"
            '    "action_steps" : [ ]\n'
            "  }\n"
            "Correct Output:\n\n"
            "  {\n"
            '    "status" : "COMPLETED",\n'
            "    \"actor\" :  <your ID here>,\n"
            '    "thought" : "I have compared the record for John Doe with all available data from the current task; no new data is mavailable, no update needed.",\n'
            '    "observation" : "All available data has been reviewed and updated where possible. No further action is required."\n'
            "  }\n"
            "\nIncorrect Output:\n\n"
            'Call "updatePersonData" tool to perform an update like below.\n'
            "  {\n"
            '    "status" : "IN_PROGRESS",\n'
            "    \"actor\" :  <your ID here>,\n"
            '    "thought" : "For John Doe, the email field is missing in the system and not present in the task, so no update is possible.",\n'
            '    "observation" : "Data for Customer Number=55555555555 have been updated successfully.",\n'
            '    "action" : "The tool \\"updatePersonData\\" has been called",\n'
            '    "action_input" : "{\\"Name\\":\\"John Doe\\",\\"Address\\":\\"Nowhere Rd. 1\\",\\"Email\\":\\"\\",\\"Phone Number\\":\\"\\",\\"customerNumber\\":\\"55555555555\\"\\"}",\n'
            '    "action_steps" : [ ]\n'
            "  }\n"
            "\n---\n\n"
            "Given the above examples, provide only the Correct Output for future inputs and context.\n"
        )
