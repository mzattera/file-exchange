"""
customer_portal.py

Python translation of `com.infosys.small.pnbc.CustomerPortal`.

- Mirrors the original class structure and behaviour.
- Uses Pydantic to model tool parameter schemas (Jackson → Pydantic).
- Follows snake_case naming, type hints, and logging conventions.
- Lombok-generated behaviour is implemented explicitly where needed.
- @JsonView annotations are intentionally ignored per instructions.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping, Sequence

from pydantic import Field

from api import Api
from chat_types import ToolCall, ToolCallResult
from execution_context import ExecutionContext
from lab_agent import LabAgent
from react_agent import ReactAgent

# --------------------------------------------------------------------------- #
# Logging (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# CustomerPortal
# --------------------------------------------------------------------------- #
class CustomerPortal(LabAgent):
    """
    Backend-system wrapper for the Customer Portal.
    """

    # ----------------------------- APIs ---------------------------------- #
    class GetAccountsApi(Api):
        class Parameters(ReactAgent.Parameters):
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getAccounts",
                description="Returns a list of bank accounts for the specified customer.",
                schema=CustomerPortal.GetAccountsApi.Parameters,
            )

    class UnblockAccountsApi(Api):
        class Parameters(ReactAgent.Parameters):
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="unblockAccounts",
                description="Unblocks all accounts belonging to the specified customer.",
                schema=CustomerPortal.UnblockAccountsApi.Parameters,
            )

        # NOTE: The Java method is `invoke(@NonNull ToolCall call, boolean log)`.
        # We mirror it with a keyword-only `log` flag and explicit @NonNull checks.
        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:  # noqa: D401
            if call is None:  # @NonNull enforcement
                raise ValueError("call must not be None")
            if not self.is_initialized():
                # Java throws IllegalArgumentException → map to ValueError
                raise ValueError("Tool must be initialized.")

            # Clone & sanitise arguments (remove LLM 'thought' as per Java)
            args: dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            customer_number = self.get_string("customerNumber", args)
            if customer_number is None:
                return ToolCallResult.from_call(call, "ERROR: Customer Number must be provided.")

            # Always log (matches Java's "Always Log")
            lab = self.get_lab_agent()
            scenario = lab.get_scenario_id() if lab is not None else "UNKNOWN"
            ctx = self.get_execution_context()
            ctx.log_api_call(scenario, self.id, args)  # type: ignore[arg-type]

            return ToolCallResult.from_call(
                call,
                f"All accounts for customer {customer_number} have been unblocked.",
            )

    class GetTransactionsApi(Api):
        class Parameters(ReactAgent.Parameters):
            account_number: str = Field(
                ...,
                alias="accountNumber",
                description="Unique account number.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="getTransactions",
                description="Returns transactions for the specified account.",
                schema=CustomerPortal.GetTransactionsApi.Parameters,
            )

    class SendCommunicationApi(Api):
        class Parameters(ReactAgent.Parameters):
            customer_number: str = Field(
                ...,
                alias="customerNumber",
                description="Unique customer number for the email recipient.",
            )
            message: str = Field(
                ...,
                description="The message that you need to send.",
            )

            model_config = {"populate_by_name": True}

        def __init__(self) -> None:
            super().__init__(
                id_="sendCommunication",
                description="Sends an email message to the specified customer.",
                schema=CustomerPortal.SendCommunicationApi.Parameters,
            )

        # Custom behaviour as in Java
        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:  # noqa: D401
            if call is None:  # @NonNull enforcement
                raise ValueError("call must not be None")

            args: dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)  # remove LLM thought if present

            # Default "*" when missing (matches Java `getString(..., "*")`)
            customer_number = self.get_string("customerNumber", args, "*")
            if not re.fullmatch(r"\d+", customer_number or ""):
                # Same error message as the Java code
                return ToolCallResult.from_call(
                    call, "Error: System failure, wrong API call parameters."
                )

            message = self.get_string("message", args)

            # Always log the outgoing email
            ctx = self.get_execution_context()
            ctx.log(
                ExecutionContext.EmailEntry(
                    ExecutionContext.LogEntryType.EMAIL,
                    customer_number,
                    message or "",
                )
            )

            # Preserve the original (typo included) success message
            return ToolCallResult.from_call(
                call, f"Email for client{customer_number} sent succeessfully."
            )

    # ---------------------------- constructor ---------------------------- #
    def __init__(self) -> None:
        super().__init__(
            id_="CUSTOMER_PORTAL",
            description=(
                "This tool is the only point to access customers' bank accounts and "
                "corresponding transactions; however it cannot be used to access or update "
                "other customers' data such as their address, email, etc.. It also allows "
                "you to send emails to clients; if you use this capability, provide the "
                "Customer Number for the recipient (**NOT** their email). "
            ),
            tools=(
                CustomerPortal.GetAccountsApi(),
                CustomerPortal.UnblockAccountsApi(),
                CustomerPortal.GetTransactionsApi(),
                CustomerPortal.SendCommunicationApi(),
            ),
            check_last_step=False,
        )

        # Context text (verbatim semantics from Java `setContext(...)`)
        self.context = (
            "  * Documents you handle are in Danish, this means sometime you have to translate "
            'tool calls parameters. For example, "Customer Number" is sometimes indicated as '
            '"afdøde CPR" or "CPR" in documents.\n'
            "\n"
            "  * Persons are uniquely identified by their Customer Number, sometimes also referred "
            "as CPR. **STRICTLY** always communicate Customer Number to any tool that needs to act "
            "on persons/clients; indicate it as Customer Number and not CPR. Never identify a person "
            "only providing their name or email.\n"
            "  * When asked to provide or update customers' data such as their address, email, etc. "
            "return an error message, stating that you do not have access to such data.\n"
            "\n"
            '  * Account are uniquely identified by their account numbers; notice that spaces in account numbers are relevant.\n'
            '  * Accounts can be personal or half-joint. This is indicated by their "JO" field: JO==N for Personal Accounts and JO==J for Half-Joint accounts.\n'
            "\n"
            '  * To indicate time stamps, always use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").\n'
            '  * For amounts, always use the format NNN,NNN.NN CCC (e.g. "2,454.33 DKK").\n'
            "\n"
            "  * **STRICTLY** **NEVER** send emails to people, unless you are explicitly instructed to do so.\n"
        )
