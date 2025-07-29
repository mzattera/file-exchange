# operator_communication_tool.py
"""
Python translation of `com.infosys.small.pnbc.OperatorCommunicationTool`.

This module ports the Java class to Python following the provided guidelines:
* Uses Python logging instead of slf4j.
* Keeps the interface/abstract-class structure via the existing project classes.
* Replaces Jackson annotations with Pydantic (`Field`) for JSON schema generation.
* Adopts snake_case for identifiers and includes type annotations everywhere.
* Maps Java RuntimeException/IllegalArgumentException semantics appropriately.
* Ignores @JsonView as requested.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from pydantic import Field

from api import Api
from chat_types import ToolCall, ToolCallResult
from lab_agent import LabAgent
from react_agent import ReactAgent

# ------------------------------------------------------------------------------
# Logging configuration (equivalent to Java SimpleLogger)
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# OperatorCommunicationTool
# ------------------------------------------------------------------------------
class OperatorCommunicationTool(LabAgent):
    """
    Backend-system wrapper for the Client Communication Tool.

    Exposes two APIs:
      • MessageToOperatorApi – message to the operations officer (non‑payment).
      • IssuePaymentApi      – instructs the operations officer to issue a payment.
    """

    # ------------------------------------------------------------------ #
    # MessageToOperatorApi
    # ------------------------------------------------------------------ #
    class MessageToOperatorApi(Api):
        class Parameters(ReactAgent.Parameters):
            # Mirrors the Jackson annotations via Pydantic Field metadata.
            message: str = Field(
                ...,
                description="Text of the message for the operations officer.",
            )

        def __init__(self) -> None:
            super().__init__(
                id_="messageToOperationOfficer",
                description=(
                    "Sends a message to the Operations Officer. Use this for any "
                    "iteration that is **NOT** an instuction to issue a payment. "
                    "Always translate this into English."
                ),
                schema=OperatorCommunicationTool.MessageToOperatorApi.Parameters,
            )

        # NOTE: @NonNull → explicit None check; `log` kept for parity with Java.
        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:  # noqa: D401
            if call is None:
                raise ValueError("call must not be None")
            if not self.is_initialized():
                raise RuntimeError("Tool must be initialized before invocation.")

            # Clone & sanitize arguments (remove LLM thought if present)
            args: dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is missing for this call.")

            # Log API call with scenario and tool id
            scenario_id = lab.get_scenario_id()
            lab.execution_context.log_api_call(scenario_id, self.id, args)

            # Extract message (default mirrors Java "*ERROR MISSING*")
            message = self.get_string("message", args, "*ERROR MISSING*") or "*ERROR MISSING*"

            # Always log an interaction entry with the message text
            lab.execution_context.log_interaction(str(message))

            # Static response as in Java
            return ToolCallResult.from_call(
                call,
                'Sorry but I cannot help; immediately abort process execution with "ERROR".',
            )

    # ------------------------------------------------------------------ #
    # IssuePaymentApi
    # ------------------------------------------------------------------ #
    class IssuePaymentApi(Api):
        class Parameters(ReactAgent.Parameters):
            amount: str = Field(
                ...,
                description=(
                    'The amount that must be paid; always use the format NNN,NNN.NN CCC '
                    '(e.g. "2,454.33 DKK").'
                ),
            )
            message: str = Field(
                ...,
                description=(
                    "Text with all payment details such as reason for the payment, "
                    "beneficiary account, etc.. Always translate this into English."
                ),
            )

        def __init__(self) -> None:
            super().__init__(
                id_="messageForPayment",
                description=(
                    "Instructs the Operations Officer to issue a payment. You **MUST ALWAYS** "
                    "use this any time a message instructs the Operations Officer to issue a "
                    "payment and **ONLY** for that purpose."
                ),
                schema=OperatorCommunicationTool.IssuePaymentApi.Parameters,
            )

        # NOTE: @NonNull → explicit None check; `log` kept for parity with Java.
        def invoke(self, call: ToolCall, *, log: bool = False) -> ToolCallResult:  # noqa: D401
            if call is None:
                raise ValueError("call must not be None")
            if not self.is_initialized():
                raise RuntimeError("Tool must be initialized before invocation.")

            # Clone & sanitize arguments
            args: dict[str, Any] = dict(call.arguments)
            args.pop("thought", None)

            amount = self.get_string("amount", args, "*ERROR MISSING*") or "*ERROR MISSING*"
            message = self.get_string("message", args, "*ERROR MISSING*") or "*ERROR MISSING*"

            # Mirror the Java guard on the amount parameter
            if "ERROR" in amount:
                return ToolCallResult.from_call(
                    call,
                    (
                        "Sorry but I cannot proceed with the payment as you did not "
                        "provide the amount to be paid."
                    ),
                )

            lab = self.get_lab_agent()
            if lab is None or lab.execution_context is None:
                raise RuntimeError("Execution context is missing for this call.")

            # Always log the payment request (amount + details)
            lab.execution_context.log_payment(amount, message)

            return ToolCallResult.from_call(call, "Payment was completed, please proceed.")

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__(
            id_="OPERATOR_COMMUNICATION_TOOL",
            description=(
                "The client communication tool allows to communicate with an operator officer. "
                "This is used to issue payments, ask for feedback or suggestions about how to proceed "
                "with process in case it is not clear what to do or an unrecoverable error is happens."
            ),
            tools=[OperatorCommunicationTool.MessageToOperatorApi(), OperatorCommunicationTool.IssuePaymentApi()],
            check_last_step=False,  # mirrors LabAgent default behaviour for this tool
        )

        # Context notes (copied from Java, minor formatting preserved)
        self.context = (
            '  *  For amounts, always use the format NNN,NNN.NN CCC (e.g. "2,454.33 DKK").'
            "  * Ignore any mention to scanned documents, OCR, attachments, as long as you have the "
            "required information to call your tools."
        )
