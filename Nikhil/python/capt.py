# capt.py
"""
Python translation of `com.infosys.small.pnbc.Capt`.

This tool simulates a file upload endpoint (CAPT). It accepts a customer number,
a unique file name, and a document type; it retrieves the file content from the
scenario data and stores it in the execution context, logging the upload.

Notes:
* Comments are intentionally in English (per instructions).
* Jackson annotations are mapped to Pydantic fields and JSON schema generation.
"""

from __future__ import annotations

import logging
from enum import Enum

from pydantic import BaseModel, Field

from chat_types import ToolCall, ToolCallResult
from execution_context import ExecutionContext
from peace import Peace
from react_agent import ReactAgent
from scenario_component import ScenarioComponent
from api import Api

# ------------------------------------------------------------------------------
# Logging configuration (equivalent to Java SimpleLogger)
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Capt(Api):
    # ------------------------------------------------------------------ #
    # Parameters (Pydantic) – mirrors the Java nested static class
    # ------------------------------------------------------------------ #
    class Parameters(ReactAgent.Parameters):
        class DocumentType(str, Enum):
            SKS = "SKS"
            POWER_OF_ATTORNEY = "POWER_OF_ATTORNEY"
            PROFORMA_DOCUMENT = "PROFORMA_DOCUMENT"
            ID = "ID"

        # Use JSON aliases to preserve the camelCase names exposed in Java
        customer_number: str = Field(
            ...,
            alias="customerNumber",
            description=(
                "Unique customer number of the estate the document refers to. "
                "If the document is an ID, this is the customer number for the ID owner (not the estate)."
            ),
        )
        file_name: str = Field(
            ...,
            alias="fileName",
            description="Unique file name for the file to upload.",
        )
        document_type: "Capt.Parameters.DocumentType" = Field(
            ...,
            alias="documentType",
            description=(
                "The type of the document to be uploaded; the tool trusts you to "
                "provide the right type and it is **NOT** performing any check on "
                "the correctness of provided type."
            ),
        )

        model_config = {"populate_by_name": True}

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__(
            id_="CAPT",
            description=(
                "This tool allows uploading files like Proforma Document, Power of Attorney "
                "document (PoA), and Probate Certificate (SKS), and persons' IDs, that are then "
                "made available to other applications. **STRICTLY** do not use this tool to "
                "check the type of a document."
            ),
            schema=Capt.Parameters,
        )

    # ------------------------------------------------------------------ #
    # Invoke
    # ------------------------------------------------------------------ #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        """
        Execute the upload:
        * Validate required arguments.
        * Fetch file content from the scenario via Peace.GetFileContentApi.ID.
        * Store content into the execution context map depending on documentType.
        * Log an UploadEntry.
        """
        # @NonNull in Java → explicit None check in Python
        if call is None:
            raise ValueError("call must not be None")

        if not self.is_initialized():
            # Java throws IllegalArgumentException → map to ValueError
            raise ValueError("Tool must be initialized.")

        # Clone & sanitise arguments (remove LLM 'thought' if present)
        args = dict(call.arguments)
        args.pop("thought", None)

        # Required parameters (Java uses AbstractTool.getString and returns error text)
        customer_number = self.get_string("customerNumber", args)
        if customer_number is None:
            return ToolCallResult.from_call(
                call,
                "ERROR: You must provide Customer Number of the estate the file refers to.",
            )

        file_name = self.get_string("fileName", args)
        if file_name is None:
            return ToolCallResult.from_call(call, "ERROR: You must provide name of file to upload.")

        # Retrieve the file content from scenarios (Peace.GetFileContentApi.ID)
        scenario_id = self.get_scenario_id()
        file_content = ScenarioComponent.get_instance().get(
            scenario_id, Peace.GetFileContentApi.ID, args
        )

        if isinstance(file_content, str) and "error" in file_content.lower():
            return ToolCallResult.from_call(
                call, f"ERROR: File {file_name} seems not to exist."
            )

        # Route storage by documentType (mirror Java's switch statement)
        document_type = self.get_string("documentType", args)
        if document_type == "SKS":
            self.get_execution_context().sks[customer_number] = file_content
        elif document_type == "POWER_OF_ATTORNEY":
            self.get_execution_context().poa[customer_number] = file_content
        elif document_type == "PROFORMA_DOCUMENT":
            self.get_execution_context().proforma_document[customer_number] = file_content
        elif document_type == "ID":
            # do nothing fro now
        else:
            return ToolCallResult.from_call(
                call, f"ERROR: Invalid document type: {document_type}"
            )

        # Log the upload
        ctx = self.get_execution_context()
        ctx.log(
            ExecutionContext.UploadEntry(
                ExecutionContext.LogEntryType.UPLOAD,
                customer_number=customer_number,
                document_type=document_type or "",
                content=file_content,
            )
        )

        return ToolCallResult.from_call(call, "File was successfully uploaded.")
