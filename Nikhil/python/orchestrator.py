from __future__ import annotations

import logging
from typing import Optional

from lab_agent import LabAgent
from peace import Peace
from execution_context import ExecutionContext
from steps import Step
from json_schema import JsonSchema

# --------------------------------------------------------------------------- #
# Logging configuration (equivalente al Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Orchestrator(LabAgent):
    """
    Python port of the Java `Orchestrator` class.

    It inherits from `LabAgent` and initialises itself with a single `Peace`
    tool.  A rich execution context is set in the constructor.
    """

    # ------------------------------ init --------------------------------- #
    def __init__(self) -> None:
        # initialise superclass ------------------------------------------------
        super().__init__(
            id_="ORCHESTRATOR",
            description="I am the first ever built process orchestrator",
            tools=[Peace()],
            check_last_step=True,
        )

        # build contextual knowledge ------------------------------------------
        self.context = (
            "  * Documents you handle are in Danish; you may need to translate tool "
            'parameters. For instance, "Customer Number" might appear as '
            '"afdøde CPR" or "CPR" in documents.\n'
            "  * Probate Certificate identifies heirs for an estate (often called "
            '"SKS").\n'
            "  * Power of Attorney (PoA) defines a person's legal rights over the "
            "estate’s assets.\n"
            "  * A Proforma Document lists the cash on estate accounts at the date "
            "of death.\n"
            "  * A Probate Court (Skifteretten) Notification Letter opens an estate; "
            "it is **NOT** the same as SKS, though it may mention that SKS was "
            "issued.\n"
            "  * Timestamps **must** use the format \"mm/dd/yyyy, hh:mm AM/PM\" "
            "(e.g. \"4/16/2025, 2:31 PM\").\n"
            "  * Amounts **must** use the format NNN,NNN.NN CCC "
            "(e.g. \"2,454.33 DKK\").\n"
            "  * Person data JSON schema:\n"
            f"{JsonSchema.get_json_schema(Peace.Person)}\n"
            "  * Persons are uniquely identified by **Customer Number** (also known "
            "as CPR). Always include Customer Number when a tool acts on a person; "
            "never identify by name or email only.\n"
            '  * Tasks are uniquely identified by "Customer Number" + '
            '"Time Created". Always provide both when a tool acts on a task.\n'
            '  * Payment tasks have Step Name="Handle Account 1".\n'
            "  * Use Operator ID==42 when identifying yourself as an operator.\n"
            '  * Accounts: personal (JO=="N") or half-joint (JO=="J").\n'
            "  * Each tool exposes limited capabilities—call only the appropriate "
            "tool for the data you need.\n"
        )

    # ------------------------------ API ---------------------------------- #
    def execute(
        self,
        ctx: ExecutionContext,
        command: Optional[str] = None,
    ) -> Step:
        """
        Run the default process unless *command* is provided.

        Parameters
        ----------
        ctx : ExecutionContext
            The simulation context in which to operate.
        command : str | None
            Optional custom command (overrides the default pseudo-code).
        """
        if ctx is None:
            raise ValueError("ctx must not be None")

        default_command = (
            "Run the below process described in pseudo-code inside <process> tag.\n\n"
            "<process>\n"
            "Check for any unassigned payment task (Step Name=\"Handle Account 1\") "
            "and assign the oldest created payment task to you.\n"
            "</process>"
        )

        return super().execute(ctx, command or default_command)
