from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, MutableMapping, Sequence

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Forward references to avoid circular-import issues
# --------------------------------------------------------------------------- #
if TYPE_CHECKING:  # pragma: no cover
    from steps import Step
    from peace import Peace  # for Person, Task  (already ported)
    from peace import Person as _Person
    from peace import Task as _Task


# --------------------------------------------------------------------------- #
# ExecutionContext
# --------------------------------------------------------------------------- #
class ExecutionContext:
    """
    Holds the *mutable* simulation state during a test run and offers
    utilities for logging and task filtering.
    """

    # ------------------------- life-cycle ------------------------------ #
    def __init__(
        self,
        db: "ExecutionContext.DbConnector",
        scenario_id: str,
        run_id: str,
    ) -> None:
        if db is None:
            raise ValueError("db must not be None")
        if scenario_id is None:
            raise ValueError("scenario_id must not be None")
        if run_id is None:
            raise ValueError("run_id must not be None")

        self.db: ExecutionContext.DbConnector = db
        self.scenario_id: str = scenario_id
        self.run_id: str = run_id

        # Dynamic state ------------------------------------------------- #
        self.unassigned_tasks: list["_Task"] | None = None
        self.operator_tasks: list["_Task"] = []
        self.related_persons: dict[str, "_Person"] | None = None

        self.proforma_document: dict[str, str] = {}
        self.sks: dict[str, str] = {}
        self.poa: dict[str, str] = {}

        self.log_entries: list[ExecutionContext.LogEntry] = []

    # ------------------------------------------------------------------ #
    # Database connector (abstract)                                      #
    # ------------------------------------------------------------------ #
    class DbConnector:
        """A pluggable persistence hook used by the simulator."""

        def add_step(self, run_id: str, step: "Step") -> None:  # noqa: D401
            raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Log entries                                                        #
    # ------------------------------------------------------------------ #
    class LogEntryType(str, Enum):
        API_CALL = "API_CALL"
        PAYMENT = "PAYMENT"
        DIARY_ENTRY = "DIARY_ENTRY"
        INTERACTION = "INTERACTION"
        EMAIL = "EMAIL"
        UPLOAD = "UPLOAD"

        def __str__(self) -> str:  # pragma: no cover
            return str(self.value)

    @dataclass
    class LogEntry:
        """Base class for every log entry."""

        type: "ExecutionContext.LogEntryType"

        def __str__(self) -> str:  # pragma: no cover
            return f">>> {self.type} LOGGED"

    # ------------------------- concrete entries ----------------------- #
    @dataclass
    class ApiCallEntry(LogEntry):
        scenario_id: str
        tool_id: str
        args: dict[str, Any] = field(default_factory=dict)

        def __str__(self) -> str:
            args_formatted = " ".join(f'{k}="{v}"' for k, v in self.args.items())
            return (
                f">>> API CALL LOGGED > {self.scenario_id}: {self.tool_id}({args_formatted})"
            )

    @dataclass
    class DiaryEntry(LogEntry):
        task_time_created: str
        task_customer_number: str
        category: str
        message: str

        def __str__(self) -> str:
            return (
                f">>> DIARY ENTRY LOGGED > For task {self.task_customer_number} - "
                f"{self.task_time_created}\n    [{self.category}] {self.message}"
            )

    @dataclass
    class EmailEntry(LogEntry):
        recipient: str
        message: str

        def __str__(self) -> str:
            return (
                f">>> OUTGOING EMAIL LOGGED >  To: {self.recipient}\nContent: {self.message}"
            )

    @dataclass
    class InteractionEntry(LogEntry):
        message: str

        def __str__(self) -> str:
            return f">>> INTERACTION LOGGED > {self.message}"

    @dataclass
    class PaymentEntry(LogEntry):
        amount: str
        message: str

        def __str__(self) -> str:
            return f">>> PAYMENT LOGGED > Amount: {self.amount} -> {self.message}"

    @dataclass
    class UploadEntry(LogEntry):
        customer_number: str
        document_type: str
        content: str

        def __str__(self) -> str:
            return (
                f">>> {self.document_type} FILE UPLOADED > for client "
                f"{self.customer_number} CONTENT -> {self.content}"
            )

    # ------------------------------------------------------------------ #
    # Logging convenience wrappers                                       #
    # ------------------------------------------------------------------ #
    def log(self, entry: "ExecutionContext.LogEntry") -> None:
        if entry is None:
            raise ValueError("entry must not be None")
        self.log_entries.append(entry)
        logger.info("%s", entry)

    # --- overloaded helpers (mirror Java API) ------------------------- #
    def log_api_call(self, scenario_id: str, tool_id: str, args: Mapping[str, Any]) -> None:
        self.log(
            ExecutionContext.ApiCallEntry(
                ExecutionContext.LogEntryType.API_CALL,
                scenario_id,
                tool_id,
                dict(args),
            )
        )

    def log_diary(
        self,
        task_time_created: str,
        task_customer_number: str,
        category: str,
        message: str,
    ) -> None:
        self.log(
            ExecutionContext.DiaryEntry(
                ExecutionContext.LogEntryType.DIARY_ENTRY,
                task_time_created,
                task_customer_number,
                category,
                message,
            )
        )

    def log_interaction(self, message: str) -> None:
        self.log(
            ExecutionContext.InteractionEntry(
                ExecutionContext.LogEntryType.INTERACTION,
                message,
            )
        )

    def log_payment(self, amount: str, message: str) -> None:
        self.log(
            ExecutionContext.PaymentEntry(
                ExecutionContext.LogEntryType.PAYMENT,
                amount,
                message,
            )
        )

    def clear_log(self) -> None:
        self.log_entries.clear()

    # ------------------------------------------------------------------ #
    # Static helpers – task filtering                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def filter_tasks(
        tasks: Sequence["_Task"],
        filter_by: str | None = None,
        filter_value: str | None = None,
        customer_number: str | None = None,
    ) -> list["_Task"]:
        """
        Return tasks matching *customer_number* **and optionally** the
        (*filter_by*, *filter_value*) criterion.

        The filter_by string must correspond to the **JSON alias** of a field
        in the Task model (e.g. ``"Step Name"`` rather than ``step_name``).
        """
        if tasks is None:
            raise ValueError("tasks must not be None")

        def _matches(task: "_Task") -> bool:
            # Filter by customer number first (if provided)
            if customer_number and task.customer_number != customer_number:
                return False

            if filter_by and filter_value is not None:
                # Pydantic exposes alias→field mapping via model_fields
                for fld in task.model_fields.values():  # type: ignore[attr-defined]
                    if fld.alias == filter_by:
                        value = getattr(task, fld.name)
                        return str(value) == filter_value
                # If alias not found, nothing matches
                return False

            return True

        return [t for t in tasks if _matches(t)]
