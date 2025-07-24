# person_locator_agent.py
from __future__ import annotations

import logging
from pydantic import BaseModel, Field

from toolable_react_agent import ToolableReactAgent
from tool import AbstractTool
from tool_call import ToolCall
from tool_call_result import ToolCallResult

# Logging configuration (mirrors project-wide settings)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class PersonLocatorAgent(ToolableReactAgent):
    """ReAct agent able to locate a person’s city."""

    # ------------------------------------------------------------------ #
    # Nested tool
    # ------------------------------------------------------------------ #
    class LocatePersonTool(AbstractTool):
        """Tool that returns a hard-coded location for a person."""

        # ---------- parameters schema (Pydantic) ---------------------- #
        class Parameters(BaseModel):
            person: str = Field(
                ...,
                description="The name of the person you want to locate.",
            )
            thought: str = Field(
                ...,
                description="Your reasoning about why and how accomplish this step.",
            )

        # ---------- construction ------------------------------------- #
        def __init__(self) -> None:
            super().__init__(
                id_="locatePersonTool",
                description="Returns the city where a person is located.",
                parameters_cls=PersonLocatorAgent.LocatePersonTool.Parameters,
            )

        # ---------- invocation --------------------------------------- #
        def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
            if not self.is_initialized():
                raise RuntimeError("Tool must be initialized.")

            person = self.get_string("person", call.arguments)
            return ToolCallResult.from_call(
                call,
                f"{person} is currently located in Padua, Italy.",
            )

    # ------------------------------------------------------------------ #
    # Agent initialisation
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__(
            id_=self.__class__.__name__,
            description="This tool is able to find a person's location.",
            tools=[PersonLocatorAgent.LocatePersonTool()],
            check_last_step=False,
        )
