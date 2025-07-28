# capt.py
"""
Python translation of `com.infosys.small.pnbc.Capt`.

Wrapper for the CAPT tool (file upload). Mirrors the original Java behaviour
while following Pythonic conventions and the project’s abstractions.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Mapping

from pydantic import BaseModel, Field

from chat_types import ToolCall, ToolCallResult
from execution_context import ExecutionContext
from react_agent import ReactAgent
from scenario_component import ScenarioComponent
from tool import AbstractTool

# External dependency already ported in the project; do not provide fallbacks.
from peace import Peace  # type: ignore  # Assume available as instructed

# ------------------------------------------------------------------------------
# Logging (equivalent to Java SimpleLogger)
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Capt(AbstractTool):
    """
    CAPT tool: allows uploading files like Proforma Document, Power of Attorney (PoA),
    and Probate Certificate (SKS), making them available to other applications.

    **STRICTLY** do not use this tool to check the type of a document.
    """

    # ------------------------------------------------------------------ #
    # Parameters (JSON-schema via Pydantic)
    # ------------------------------------------------------------------ #
    class Parameters(ReactAgent.Parameters):
        class DocumentType(str, Enum):
            SKS = "SKS"
            POWER_OF_ATTORNEY = "POWER_OF_ATTORNEY"
            PROFORMA_DOCUMENT = "PROFORMA_DOCUMENT"

        customer_number: str = Field(
            ...,
            alias="customerNumber",
            description="Unique customer number of the estate the document refers to.",
        )
        file_name: str = Field(
            ...,
            alias="fileName",
            description="Unique file name for the file to upload.",
        )
        document_type: DocumentType = Field(
            ...,
            alias="documentType",
            description=(
                "The type of the document to be uploaded; the tool trusts you to "
                "provide the right type and it is **NOT** performing any check on "
                "the correctness of provided type."
            ),
        )

        # Accept both field names and aliases when parsing
        model_config = {"populate_by_name": True}

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__(
            id_="CAPT",
            description=(
                "This tool allows uploading files like Proforma Document, Power of "
                "Attorney document (PoA), and Probate Certificate (SKS), that are "
                "then made available to other applications. **STRICTLY** do not use "
                "this tool to check the type of a document."
            ),
            parameters_cls=Capt.Parameters,
        )

    # ------------------------------------------------------------------ #
    # Invoke
    # ------------------------------------------------------------------ #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        """
        Execute the CAPT upload.

        Expected arguments (by alias, as per schema):
          - customerNumber : str
          - fileName       : str
          - documentType   : {"SKS","POWER_OF_ATTORNEY","PROFORMA_DOCUMENT"}

        Notes
        -----
        * The method fetches the file content via the Peace.GetFileContentApi mock,
          using the current scenario, and then stores the content into the
          ExecutionContext according to the selected document type.
        """
        # @NonNull on parameter → explicit check
        if call is None:
            raise ValueError("call must not be None")
        if not self.is_initialized():
            # Java threw IllegalArgumentException; per instructions map to ValueError.
            raise ValueError("Tool must be initialized.")

        # Clone & sanitise arguments (remove LLM's internal 'thought' if present)
        args: dict[str, object] = dict(call.arguments)
        args.pop("thought", None)

        # Required parameters (accept both aliases and snake_case fallbacks)
        customer_number = (
            self.get_string("customerNumber", args)
        )
        if customer_number is None:
            return ToolCallResult.from_call(
                call,
                "ERROR: You must provide Customer Number of the estate the file refers to.",
            )

        file_name = self.get_string("fileName", args)
        if file_name is None:
            return ToolCallResult.from_call(
                call,
                "ERROR: You must provide name of file to upload.",
            )

        # Retrieve file content from the scenario using the dedicated Peace API
        scenario_id = self._require_scenario_id()
        file_content = ScenarioComponent.get_instance().get(
            scenario_id,
            Peace.GetFileContentApi.ID,  # use the specific API as in Java
            args,
        )

        if "error" in file_content.lower():
            return ToolCallResult.from_call(
                call,
                f"ERROR: File {file_name} seems not to exist.",
            )

        # Document type routing (string as provided by the tool call)
        document_type = (
            self.get_string("documentType", args)
            or self.get_string("document_type", args)
        )
        if document_type is None:
            return ToolCallResult.from_call(call, "ERROR: Invalid document type: None")

        ctx = self._require_execution_context()

        if document_type == "SKS":
            ctx.sks[customer_number] = file_content
        elif document_type == "POWER_OF_ATTORNEY":
            ctx.poa[customer_number] = file_content
        elif document_type == "PROFORMA_DOCUMENT":
            ctx.proforma_document[customer_number] = file_content
        else:
            return ToolCallResult.from_call(
                call, f"ERROR: Invalid document type: {document_type}"
            )

        # Log the upload action in the execution context
        ctx.log(
            ExecutionContext.UploadEntry(
                ExecutionContext.LogEntryType.UPLOAD,
                customer_number=customer_number,
                document_type=document_type,
                content=file_content,
            )
        )

        return ToolCallResult.from_call(call, "File was successfully uploaded.")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _require_execution_context(self) -> ExecutionContext:
        lab = self._agent  # set during init(...) in the hosting agent
        from executor_module import ExecutorModule  # local import to avoid cycle
        from lab_agent import LabAgent  # local import to avoid cycle

        if isinstance(lab, LabAgent) and lab.execution_context is not None:
            return lab.execution_context
        if isinstance(lab, ExecutorModule):
            inner = lab.agent
            if isinstance(inner, LabAgent) and inner.execution_context is not None:
                return inner.execution_context
        raise RuntimeError("Execution context is not set.")

    def _require_scenario_id(self) -> str:
        ctx = self._require_execution_context()
        return ctx.scenario_id
