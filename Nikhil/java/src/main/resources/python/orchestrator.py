# orchestrator.py
"""
Python port of `com.infosys.small.pnbc.Orchestrator`.

It specialises :class:`LabAgent` with a fixed set of tools and a predefined
simulation context.
"""

from __future__ import annotations

import logging
from typing import List

from execution_context import ExecutionContext
from lab_agent import LabAgent
from peace import Peace
from json_schema import JsonSchema
from steps import Step
from tool import Tool

##### --------------------------------------------------------------------------- #
##### Logging configuration (equivalent to Java SimpleLogger)
##### --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Orchestrator(LabAgent):
    """
    First-ever built process orchestrator.
    """

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #
    def __init__(self) -> None:
        tools: List[Tool] = [
            Peace(),
            # CustomerPortal(),
            # OperatorCommunicationTool(),
            # Capt(),
            # FileDownloadTool(),
            # UpdatePoATool(),
            # InspectBillTool(),
        ]

        super().__init__(
            id_="ORCHESTRATOR",
            description="I am the first ever built process orchestrator",
            tools=tools,
            check_last_step=True,
        )

        # ---------- domain context fed to the underlying LLM --------------
        self.context = (
            "  * Documents you handle are in Danish, this means sometime you have to translate "
            'tool calls parameters. For example, "Customer Number" is sometimes indicated as '
            '"afdøde CPR" or "CPR" in documents.\n'
            "  * Probate Certificate is a document that lists heirs for one estate; it is sometime "
            'indicated as "SKS".\n'
            "  * Power of Attorney document (PoA) is a document that define people's legal rights "
            "over the estate's asset. It is sometime indicated as \"PoA\".\n"
            "  * Proforma Document is a document containing the amount of cash available on "
            "estate's account at the time of their death.\n"
            "  * Probate Court (Skifteretten) Notification Letter is an official letter from "
            "Skifteretten informing the heirs about the opening of an estate after a person’s "
            "death; this is **NOT** same as SKS, even it might notify heirs that SKS has been "
            "issued.\n"
            '  * To indicate time stamps, always use "mm/dd/yyyy, hh:mm AM/PM" format '
            '(e.g. "4/16/2025, 2:31 PM").\n'
            '  * For amounts, always use the format NNN,NNN.NN CCC (e.g. "2,454.33 DKK").\n'
            "  * Persons data are described by this JSON schema: "
            f"{JsonSchema.get_json_schema(Peace.Person)}\n"
            "  * Persons are uniquely identified by their Customer Number, sometimes also referred "
            "as CPR. **STRICTLY** always communicate Customer Number to any tool that needs to act "
            "on persons/clients; indicate it as Customer Number and not CPR. Never identify a "
            "person only providing their name or email.\n"
            '  * Tasks are uniquely identified by the combination of their "Customer Number" and '
            '"Time Created" fields. **STRICTLY** always provide these fields if a tool needs to act '
            "on a specific task\n"
            '  * Payment tasks are identified by having Step Name="Handle Account 1".\n'
            "  * When you need to identify yourself as an operator (e.g. when managing tasks), use "
            "Operator ID == 42.\n"
            '  * Accounts can be personal or half-joint. This is indicated by their "JO" field: '
            "JO==N for Personal Accounts and JO==J for Half-Joint accounts.\n"
            "  * Be mindful when calling tools, since each tool has access only to specific "
            "capabilities and data.\n"
        )

    # --------------------------------------------------------------------- #
    # Default process execution
    # --------------------------------------------------------------------- #
    def execute(self, ctx: ExecutionContext) -> Step:  # noqa: D401
        """
        Run the default process inside *ctx*.
        """
        if ctx is None:
            raise ValueError("ctx must not be None")

        process_description = (
            "Run the below process described in pseudo-code inside <process> tag.\n\n"
            "<process>\n"
            'Check for any unassigned payment task (Step Name="Handle Account 1") and assign '
            "the oldest created payment task to you.\n\n"
            'Assign to you any unassigned payment task (Step Name="Handle Account 1") for the '
            "same estate (Client Number).</process>"
        )

        return super().execute(ctx, process_description)

    # --------------------------------------------------------------------- #
    # Entry-point for manual testing (mirrors Java `main`)
    # --------------------------------------------------------------------- #
    @staticmethod
    def _demo() -> None:  # pragma: no cover
        class _Db(ExecutionContext.DbConnector):
            def add_step(self, run_id: str, step: Step) -> None:
                pass  # no-op for demo

        ctx = ExecutionContext(_Db(), "scenario-01", "_run_XXX")

        # Touch Peace so it initialises its description (behavioural parity)
        Peace().get_description()  # type: ignore[attr-defined]

        orchestrator = Orchestrator()
        try:
            orchestrator.execute(ctx)
        finally:
            orchestrator.close()


if __name__ == "__main__":  # pragma: no cover
    Orchestrator._demo()
