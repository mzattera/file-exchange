# react_agent.py
from __future__ import annotations

import logging
from typing import List, Sequence, TYPE_CHECKING

from pydantic import BaseModel, Field

from agent import Agent
from tool import Tool
from steps import Step  # Step and ToolCallStep are already provided

if TYPE_CHECKING:  # avoid circular imports at runtime
    from executor_module import ExecutorModule
    from critic_module import CriticModule


# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class ReactAgent(Agent):
    """
    Python port of the Java `ReactAgent`.

    A ReAct agent is composed of:
      • an *executor* module in charge of reasoning/acting with tools;
      • a *reviewer* (critic) module that audits the executor’s decisions.

    Only the *executor* receives the tool list; the wrapper itself does **not**
    expose tools directly.
    """

    DEFAULT_MODEL: str = "gpt-4.1"

    # --------------------------------------------------------------------- #
    # Nested helper - Parameters (for tools that wrap the agent)
    # --------------------------------------------------------------------- #
    class Parameters(BaseModel):
        """
        Base parameters for any tool available to a ReAct agent.

        This mirrors the static `Parameters` class defined in the Java version.
        """

        thought: str = Field(
            ...,
            description="Your reasoning about why this tool has been called.",
        )

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #
    def __init__(
        self,
        id_: str,
        description: str,
        tools: Sequence[Tool],
        check_last_step: bool = True,
    ) -> None:
        # --- null-checks (mirrors @NonNull) --------------------------------
        if id_ is None:
            raise ValueError("id_ must not be None")
        if description is None:
            raise ValueError("description must not be None")
        if tools is None:
            raise ValueError("tools must not be None")

        # Initialise the outer Agent **without** tools (only executor uses them)
        super().__init__(id_=id_, description=description, tools=[])

        # Model configuration mirrors the Java defaults
        self.model = self.DEFAULT_MODEL
        self.temperature = 0.0

        # Additional context / few-shot examples the caller can set
        self._context: str = ""
        self._examples: str = ""

        # Create the inner modules (executor & critic).  They are imported
        # lazily to avoid circular-import issues.
        from executor_module import ExecutorModule  # local import
        from critic_module import CriticModule

        self._executor: ExecutorModule = ExecutorModule(
            agent=self,
            tools=list(tools),
            check_last_step=check_last_step,
            model=self.DEFAULT_MODEL,
        )
        self._reviewer: CriticModule = CriticModule(
            agent=self,
            tools=list(tools),
            model=self.DEFAULT_MODEL,
        )

    # --------------------------------------------------------------------- #
    # Public API mirroring Java implementation
    # --------------------------------------------------------------------- #
    # Properties ----------------------------------------------------------- #
    @property
    def context(self) -> str:
        return self._context

    @context.setter
    def context(self, value: str) -> None:
        if value is None:
            raise ValueError("context must not be None")
        self._context = value

    @property
    def examples(self) -> str:
        return self._examples

    @examples.setter
    def examples(self, value: str) -> None:
        if value is None:
            raise ValueError("examples must not be None")
        self._examples = value

    # Accessors for inner modules (read-only) ------------------------------ #
    @property
    def executor(self):  # → ExecutorModule
        return self._executor

    @property
    def reviewer(self):  # → CriticModule
        return self._reviewer

    # Delegated behaviour -------------------------------------------------- #
    def execute(self, command: str) -> Step:
        """
        Execute *command* through the underlying executor module and
        return the final `Step`.
        """
        if command is None:
            raise ValueError("command must not be None")
        logger.info("Executing command: %s", command)
        return self._executor.execute(command)

    def get_steps(self) -> List[Step]:
        """Expose the list of execution steps gathered by the executor."""
        return self._executor.steps
