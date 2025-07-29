# inspect_bill_tool.py
from __future__ import annotations

import logging
from typing import Mapping

from pydantic import BaseModel, Field

from agent import Agent
from chat_types import ToolCall, ToolCallResult
from json_schema import JsonSchema
from lab_agent import LabAgent
from peace import Peace, Person  # assumes these are available as in the Java project
from steps import Step, Status
from tool import AbstractTool

# -----------------------------------------------------------------------------
# Logging (equivalent to Java SimpleLogger)
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class InspectBillTool(LabAgent):
    """
    Python translation of `com.infosys.small.pnbc.InspectBillTool`.

    This tool inspects one task attachment that is supposed to be a bill/invoice,
    determining whether it needs to be paid and extracting payment details.
    """

    # ----------------------------- Parameters ----------------------------- #
    class Parameters(BaseModel):
        """
        Parameters extend ReactAgent.Parameters in Java; here we inline the required
        fields and keep the same external JSON shape via aliases.
        """

        # ReactAgent.Parameters.thought
        thought: str = Field(
            ...,
            description="Your reasoning about why this tool has been called.",
        )

        estate_name: str = Field(
            ...,
            alias="estateName",
            description="Estate's name.",
        )
        estate_customer_number: str = Field(
            ...,
            alias="estateCustomerNumber",
            description="Estate's unique Customer Number.",
        )
        time_created: str = Field(
            ...,
            alias="timeCreated",
            description='Time the task to inspect was created. Use "mm/dd/yyyy, hh:mm AM/PM" format (e.g. "4/16/2025, 2:31 PM").',
        )
        attachment_file_name: str = Field(
            ...,
            alias="attachmentFileName",
            description="File name of the task attachment to inspect.",
        )

        model_config = {"populate_by_name": True}

    # -------------------------- Response Format --------------------------- #
    class ResponseFormat(BaseModel):
        action: str = Field(
            ...,
            description="The action that must be performed for the provided attachment.",
        )
        estate_name: str = Field(
            ...,
            alias="estateName",
            description="Full name of the estate, as specified in the task.",
        )
        estate_customer_number: str = Field(
            ...,
            alias="estateCustomerNumber",
            description="Estate's unique Customer Number (CPR), as specified in the task.",
        )
        requestor_name: str = Field(
            ...,
            alias="requestorName",
            description="Full name of the person who created the task, as specified in the task.",
        )
        requestor_customer_number: str = Field(
            ...,
            alias="requestorCustomerNumber",
            description="Unique Customer Number (CPR) of the person who created the task, as specified in the task.",
        )
        is_funeral_bill: bool = Field(
            ...,
            alias="isFuneralBill",
            description="True if and only if the attachment is a bill/invoice relative to funeral expenses.",
        )
        issuer: str | None = Field(
            None,
            description="If the attachment is a bill/invoice, this is the person or legal entity that issued the bill/invoice; provide their names and address if possible.",
        )
        invoice_to: str | None = Field(
            None,
            alias="invoiceTo",
            description="If the attachment is a bill/invoice, this is the person the bill was invoiced to.",
        )
        amount: str | None = Field(
            None,
            description='Total amount to be paid, if any, as contained in the attachment, always use the format NNN,NNN.NN CCC (e.g. "2,454.33 DKK").',
        )
        beneficiary: str | None = Field(
            None,
            description="The person or legal entity to which the payment must be made, if any; provide their names and address if possible. This might be different from the issuer if the bill/invoice was already paid by somebody and we must issue a reimbursement to them.",
        )
        from_account: str | None = Field(
            None,
            alias="fromAccount",
            description="Account from where the amount used to pay the bill should be taken, if a payment has to be made.",
        )
        to_account: str | None = Field(
            None,
            alias="toAccount",
            description="Account where the amount should be paid to, if a payment has to be made.",
        )
        invoice_number: str | None = Field(
            None,
            alias="invoiceNumber",
            description='Invoice ("Faktura") number, if the attachment is a bill/invoice.',
        )
        thought: str = Field(
            ...,
            description="The reasoning leading you to this output.",
        )

        model_config = {"populate_by_name": True}

    # ------------------------------ init --------------------------------- #
    def __init__(self) -> None:
        # Tools available to this agent (same as in Java)
        tools = [
            Peace.GetRelatedPersonsApi(),
            Peace.GetTaskContentApi(),
            Peace.GetFileContentApi(),
        ]

        description = (
            "This tool inspects one task attachment that is supposed to be a "
            "bill/invoice determining whether it needs to be paid and corresponding "
            "payment details. **STRICTLY** Do not call this tool on attachments you "
            "know are not bill/invoices or to determine the type of an attachment. "
            "Format of the returned result is described by this JSON Schema:\n"
            + JsonSchema.get_json_schema(InspectBillTool.ResponseFormat)
        )

        super().__init__(
            id_="inspectBillsTool",
            description=description,
            tools=tools,
            check_last_step=False,  # mirrors commented Java line
        )

        # Override parameter schema to our Parameters (Java setJsonParameters)
        self.json_parameters = JsonSchema.get_json_schema(InspectBillTool.Parameters)

        # Additional context (Java setContext)
        self.context = (
            '  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, "Customer Number" is sometimes indicated as "afdøde CPR" or "CPR" in documents.\n'
            "  * Data about persons related to estates are described by the below JSON schema:\n"
            f"{JsonSchema.get_json_schema(Person)}\n"
            "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. Always provide the Customer Number if a tool needs to act on a specific person/client; indicate it as Customer Number and not CPR when passing it to tools.\n"
        )

        # Build the COMMAND template (was a static final String in Java)
        self._command_template: str = (
            "Your task is to decide whether a payment should be fulfilled and extract and return some relevant information for the payment, by following the below instructions.\n"
            '  * In the below instructions, terms "bill", "invoice", "bill/invoice", "attachment", etc. are synonyms.\n'
            '  * Examine the contents of the task with Customer Number="{{estateCustomerNumber}}" ({{name}}) and Time Created="{{timeCreated}}" '
            'and of its attachment with File Name="{{attachmentFileName}}", then extract all information needed to produce the required output.\n'
            '  * Account numbers where payments should be made might come in "payment line" format such as: "+32<000000000063860+94720463" or "+32<000000000063860>+94720463<".\n'
            '  * **STRICTLY**, if and only if task contents provide an account form where to fetch amounts for payments/reimbursements, then use this account for "fromAccount" field in your output both for payments and reimbursements.\n'
            '  * **STRICTLY**, if and only if task contents or the attachment provide an account to where transfer amounts for reimbursements, then use this account for "toAccount" field in your output for reimbursements.\n'
            "  * **STRICTLY**, if any instruction tells you to output a specific value for \"action\" field in your output, then you must create an output with the specified value for \"action\" field.\n"
            "IF the attachment is a letter from Skifteretten mentioning a retsafgift (probate court fee) that may need to be paid THEN the fee must be paid; extract the Skifteretten account for payment, if provided in the document.\n"
            "\n"
            "IF any of the persons related to the estate has some Power of Attorney {\n"
            "\tIF the attachment refers to expenses related to funeral (e.g. cemetery services and fees, church service, flowers, catering, etc.) THEN {\n"
            "\t\tThe attachment must NOT be paid/reimbursed.\n"
            "\t} ELSE {\n"
            "\t\tIF only one person in <people> has power of attorney and their identity has been verified THEN {\n"
            "\t\t\tIF content in <task> requests to pay attached bills/invoices and the task was created by the person with power of attorney THEN {\n"
            "\t\t\t\tThe attachment must be paid/reimbursed.\n"
            "\t\t\t} ELSE {\n"
            "\t\t\t\tThe attachment must NOT be paid/reimbursed.\n"
            "\t\t\t}\n"
            "\t\t} ELSE {\n"
            "\t\t\tThe attachment must NOT be paid/reimbursed.\n"
            "\t\t}\n"
            "\t}\n"
            "}\n"
            "IF none of the persons in <people> has some Power of Attorney {\n"
            "\tDo not consider whether the identity of persons in <people> has been verified or not.\n"
            "\tIF the attachment refers to expenses related to funeral (e.g. cemetery services and fees, church service, flowers, catering, etc.) THEN {\n"
            "\t\tIF content in <task> requests to pay attached bills/invoices THEN {\n"
            '\t\t\tIF (attachment amount is above 15,000.00 DKK) AND (the attachment is specifically related to food catering, gathering after funeral or tombstone costs THEN {\n'
            "\t\t\t\tThe attachment must NOT be paid/reimbursed.\n"
            "\t\t\t} ELSE {\n"
            "\t\t\t\tThe attachment must be paid/reimbursed **EVEN IF** the identity of the person who created the task has not been verified.\n"
            "\t\t\t}\n"
            "\t\t} ELSE {\n"
            "\t\t\tThe attachment must NOT be paid/reimbursed.\n"
            "\t\t}\n"
            "\t} ELSE {\n"
            "\t}\n"
            "}\n"
            "If accordingly to above logic, the attachment must be paid, then if the attachment text indicates that the bill has already been paid, then the \"action\" field in your output **MUST** be to issue a reimbursement to the client.\n"
            "If accordingly to above logic, the attachment must be paid, then if the attachment text indicates that the bill has **NOT** been paid, then the \"action\" field in your output **MUST** be to issue a payment to the person or entity who created the invoice, as specified in the attachment.\n"
            "If accordingly to above logic, the attachment must NOT be paid, then the \"action\" field in your output **MUST** be to NOT issue a payment to the person or entity who created the invoice, as specified in the attachment.\n"
            "  * Output your response as JSON, in the format described by the below JSON schema in <output_schema> tag.\n"
            "\n<output_schema>\n"
            f"{JsonSchema.get_json_schema(InspectBillTool.ResponseFormat)}"
            "\n</output_schema>\n"
        )

    # ------------------------------ invoke -------------------------------- #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        """
        Execute the inspection workflow.

        Returns a JSON string (as per ResponseFormat schema) or an ERROR string.
        """
        # @NonNull check on method parameter
        if call is None:
            raise ValueError("call must not be None")

        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized.")

        # Required arguments (mirror Java getString + error messages)
        estate_name = AbstractTool.get_string("estateName", call.arguments)
        if estate_name is None:
            return ToolCallResult.from_call(call, "ERROR: You must provide the estate's name.")

        estate_customer_number = AbstractTool.get_string("estateCustomerNumber", call.arguments)
        if estate_customer_number is None:
            return ToolCallResult.from_call(call, "ERROR: You must provide the estate's Customer Number.")

        time_created = AbstractTool.get_string("timeCreated", call.arguments)
        if time_created is None:
            return ToolCallResult.from_call(call, "ERROR: You must provide creation time for task to inspect.")

        attachment_file_name = AbstractTool.get_string("attachmentFileName", call.arguments)
        if attachment_file_name is None:
            return ToolCallResult.from_call(call, "ERROR: You must provide file name of the attachment to inspect.")

        # Slot mapping for prompt
        slots: Mapping[str, str] = {
            "estateName": estate_name,
            "estateCustomerNumber": estate_customer_number,
            "timeCreated": time_created,
            "attachmentFileName": attachment_file_name,
            "name": estate_name,  # used by the template alongside Customer Number
        }

        # Retrieve execution context from the outer LabAgent (same as Java)
        parent_lab = self.get_lab_agent()
        if parent_lab is None or parent_lab.execution_context is None:
            return ToolCallResult.from_call(call, "ERROR: Execution context is missing.")

        ctx = parent_lab.execution_context

        # Execute the ReAct flow with the filled command
        command = Agent.fill_slots(self._command_template, slots)
        result: Step = self.execute(ctx, command)

        if result.status == Status.ERROR:
            return ToolCallResult.from_call(call, f"ERROR: {result.observation}")

        return ToolCallResult.from_call(call, result.observation)
