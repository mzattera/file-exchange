# update_poa_tool.py
"""
Python translation of `com.infosys.small.pnbc.UpdatePoATool`.

The class specializes `LabAgent` to orchestrate a very specific process:
- Retrieve SKS / PoA documents for an estate (by Customer Number).
- Compare persons' data across systems and documents.
- Apply updates under the rules specified in the embedded COMMAND.
- Optionally unblock accounts and notify the operator as directed.

Notes
-----
* Field and method names follow Python conventions (snake_case).
* Java Lombok-generated code and annotations have been translated accordingly.
* Logging uses Python's stdlib `logging` module.
* All comments are in English, as required.
"""

from __future__ import annotations

import logging
from typing import Mapping

from pydantic import BaseModel, Field

from agent import Agent
from chat_types import ToolCall, ToolCallResult
from json_schema import JsonSchema
from lab_agent import LabAgent
from steps import Step, Status

# External tools & models already ported elsewhere in the project.
# We only import them (no fallback code).
from peace import Peace, Person  # Person schema used in context
from customer_portal import CustomerPortal
from operator_communication_tool import OperatorCommunicationTool
from file_download_tool import FileDownloadTool

##### --------------------------------------------------------------------------- #
##### Logging configuration (equivalent to Java SimpleLogger)
##### --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class UpdatePoATool(LabAgent):
    """
    Tool that processes Probate Certificate (SKS) and Power of Attorney (PoA)
    documents to perform the required update of client data.

    It exposes a fixed command flow; callers must provide only the estate's
    Customer Number (via the `estateCustomerNumber` parameter).
    """

    # ------------------------- Parameters schema ------------------------- #
    class Parameters(BaseModel):
        """
        Parameters expected by this tool when invoked by an agent.

        Inherit the `thought` field semantics from ReactAgent.Parameters in spirit:
        our tool is *not* a generic Q/A, so we only require the estate identifier.
        """

        estate_customer_number: str = Field(
            ...,
            alias="estateCustomerNumber",
            description="Unique Client Number for the estate.",
        )

        # Allow population via either field-name or alias
        model_config = {"populate_by_name": True}

    # --------------------------- fixed command --------------------------- #
    COMMAND: str = (
        'Retrieve Probate Certificate (SKS) and Power of Attorney (PoA) documents for estate with Customer Number="{{estate}}", if available.\n'
        "IF none of the SKS or PoA are provided, THEN end execution.\n"
        "Meticulously compare all information available about the persons related to the estate with corresponding data provided in both SKS or PoA documents "
        "(e.g. check whether email addresses in PoA or SKS is different from that in our systems); "
        'in this step, **STRICTLY** ignore "Power Of Attorney Type" and "Identification Completed" fields but be very mindful with other fields, '
        'including relation to estate if different than "Other" (e.g. if you can infer from SKS or PoA a person is now "Heir"). '
        "IF AND ONLY IF you find any data that is missing or that needs to be updated (considering above exceptions), THEN update the record for the related person, "
        "ELSE do not make any attempt to write, confirm, or update the person's data.\n"
        "\n"
        "IF PoA is available, THEN {\n"
        '    FOR EACH person who (has received some power of attorney in PoA other than "None") AND (hasn\'t only granted power of attorney to somebody in PoA) {\n'
        "        IF the person has any account in the bank THEN {\n"
        '            Update person\'s "Power Of Attorney Type" and "Relation To Estate" accordingly to PoA and set "Identification Completed"="OK - Client".\n'
        "            Unblock accounts for the estate.\n"
        "            In your output, notify the user that accounts for estate have been unblocked; provide estate's Customer Number.\n"
        "        }\n"
        "        IF the person does NOT have any account in the bank THEN {\n"
        "            Communicate to the Operations Officer that that person cannot be identified; clearly specify the power of attorney type they received. End the process execution here.\n"
        "        }\n"
        "    }\n"
        "}\n"
    )

    # ------------------------------ init -------------------------------- #
    def __init__(self) -> None:
        super().__init__(
            id_="updatePoATool",
            description=(
                "This tool processes the Probate Certificate (SKS) and Power of Attorney (PoA) "
                "documents to perform any required update of client data. **STRICTLY** use this "
                "only to process Probate Certificate (SKS) and Power of Attorney (PoA) documents."
            ),
            tools=[
                Peace(),
                CustomerPortal(),
                OperatorCommunicationTool(),
                FileDownloadTool(),
            ],
            check_last_step=True,  # mirror Java: getExecutor().setCheckLastStep(true)
        )

        # Override tool parameter schema to our custom Parameters (not the generic React one)
        self.json_parameters = JsonSchema.get_json_schema(UpdatePoATool.Parameters)

        # Provide execution context/person schema to the underlying ReAct agent
        self.context = (
            '  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, "Customer Number" is sometimes indicated as "afdøde CPR" or "CPR" in documents.\n'
            "  * Probate Certificate is a document that lists heirs for one estate; it is sometime indicated as \"SKS\".\n"
            "  * Power of Attorney document (PoA) is a document that define people's legal rights over the estate's asset. It is sometime indicated as \"PoA\".\n"
            "\n"
            "  * Data about persons related to estates are described by the below JSON schema:\n"
            f"{JsonSchema.get_json_schema(Person)}\n"
            "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. Always provide the Customer Number if a tool needs to act on a specific person/client; indicate it as Customer Number and not CPR when passing it to tools.\n"
        )

    # ------------------------------ invoke ------------------------------ #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        """
        Execute the fixed PoA/SKS processing routine for the provided estate.

        Required argument (by alias): ``estateCustomerNumber``.
        """
        # @NonNull on parameter → defensive check
        if call is None:
            raise ValueError("call must not be None")

        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized.")

        # Pull required argument using the JSON alias as per schema
        estate = self.get_string("estateCustomerNumber", call.arguments)
        if estate is None:
            return ToolCallResult.from_call(
                call, "ERROR: You must provide the estate's Customer Number."
            )

        # Resolve the outer LabAgent & its ExecutionContext (must exist)
        lab = self.get_lab_agent()
        if lab is None or lab.execution_context is None:
            return ToolCallResult.from_call(call, "ERROR: Execution context is missing.")

        # Fill slots and run the orchestrated command within the caller's context
        mapping: Mapping[str, str] = {"estate": estate}
        command: str = Agent.fill_slots(self.COMMAND, mapping)

        result: Step = self.execute(lab.execution_context, command)

        if result.status == Status.ERROR:
            return ToolCallResult.from_call(call, f"ERROR: {result.observation}")
        return ToolCallResult.from_call(call, result.observation)
