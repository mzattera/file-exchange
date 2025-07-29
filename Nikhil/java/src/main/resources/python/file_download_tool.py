from __future__ import annotations

"""
file_download_tool.py

Python translation of `com.infosys.small.pnbc.FileDownloadTool`.

This tool exposes files uploaded through CAPT and caches them in the
current ExecutionContext (per customer number and document type).
"""

import logging
from typing import Any, Mapping

from pydantic import BaseModel, Field

from api import Api
from chat_types import ToolCall, ToolCallResult
from react_agent import ReactAgent
from scenario_component import ScenarioComponent

# NOTE: This module is expected to be available in the project. Do NOT provide fallbacks.
from capt import Capt  # noqa: F401

# ------------------------------------------------------------------------------
# Logging (equivalent to Java SimpleLogger)
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class FileDownloadTool(Api):
    """
    Provides access to files that have been uploaded through CAPT, such as:
    - Proforma Document
    - Power of Attorney (PoA)
    - Probate Certificate (SKS)
    """

    # ---------------------------- parameters ---------------------------- #
    class Parameters(ReactAgent.Parameters):
        """
        Parameters schema mirroring the Java class, with JSON aliases matching the
        original @JsonProperty names.
        """

        customer_number: str = Field(
            ...,
            alias="customerNumber",
            description="Unique customer number of the estate the document refers to.",
        )
        document_type: "Capt.Parameters.DocumentType" = Field(  # type: ignore[name-defined]
            ...,
            alias="documentType",
            description="The type of the document to download.",
        )

        # accept both alias and field name at runtime
        model_config = {"populate_by_name": True}

    # ---------------------------- construction -------------------------- #
    def __init__(self) -> None:
        super().__init__(
            id_="fileDownload",
            description=(
                "This tool allows downloading files like Proforma Document, "
                "Power of Attorney document (PoA) and Probate Certificate (SKS), if available."
            ),
            schema=FileDownloadTool.Parameters,
        )

    # ------------------------------ invoke ------------------------------ #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
        """
        Execute the file retrieval, caching per (customer_number, document_type).

        Java semantics mirrored:
        * Ensure tool is initialized.
        * Remove LLM-only arguments (e.g., thought).
        * Validate required inputs.
        * Use the ExecutionContext caches (SKS / PoA / Proforma).
        * If first call for the given (customer_number, type), fetch from ScenarioComponent.
        """
        if call is None:  # @NonNull translation
            raise ValueError("call must not be None")
        if not self.is_initialized():
            # Java: IllegalArgumentException → Python: ValueError
            raise ValueError("Tool must be initialized.")

        # Clone & sanitise arguments
        args: dict[str, Any] = dict(call.arguments)
        args.pop("thought", None)  # remove LLM internal field, if present

        # Required parameters (names follow the JSON alias used in Java)
        customer_number = self.get_string("customerNumber", args)
        if customer_number is None:
            return ToolCallResult.from_call(
                call,
                "ERROR: You must provide Customer Number of the estate the file refers to.",
            )

        document_type = self.get_string("documentType", args)
        # Do not pass documentType to underlying scenario tools (match Java)
        args.pop("documentType", None)

        # Access execution context caches
        ctx = self.get_execution_context()
        if ctx is None:
            return ToolCallResult.from_call(call, "ERROR: Execution context is missing.")

        # Route by document type
        if document_type == "SKS":
            if ctx.sks.get(customer_number) is None:
                ctx.sks[customer_number] = ScenarioComponent.get_instance().get(
                    self.get_scenario_id(),
                    "getSKS",
                    args,
                )
            return ToolCallResult.from_call(call, ctx.sks.get(customer_number))

        if document_type == "POWER_OF_ATTORNEY":
            if ctx.poa.get(customer_number) is None:
                ctx.poa[customer_number] = ScenarioComponent.get_instance().get(
                    self.get_scenario_id(),
                    "getPoA",
                    args,
                )
            return ToolCallResult.from_call(call, ctx.poa.get(customer_number))

        if document_type == "PROFORMA_DOCUMENT":
            if ctx.proforma_document.get(customer_number) is None:
                ctx.proforma_document[customer_number] = ScenarioComponent.get_instance().get(
                    self.get_scenario_id(),
                    "getProformaDocument",
                    args,
                )
            return ToolCallResult.from_call(
                call, ctx.proforma_document.get(customer_number)
            )

        # Fallback: invalid type
        return ToolCallResult.from_call(
            call, f"ERROR: Invalid document type: {document_type}"
        )
