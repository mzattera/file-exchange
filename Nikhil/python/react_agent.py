# react_agent.py
from __future__ import annotations

import logging
from typing import List, Sequence, TYPE_CHECKING

from pydantic import BaseModel, Field

from agent import Agent
from json_schema import JsonSchema
from steps import Step
from tool import Tool

if TYPE_CHECKING:  # avoid circular imports at runtime
    from executor_module import ExecutorModule
    from critic_module import CriticModule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class ReactAgent(Agent):
    DEFAULT_MODEL: str = "gpt-4.1"

    class Parameters(BaseModel):
        thought: str = Field(
            ...,
            description="Your reasoning about why this tool has been called.",
        )

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        id_: str,
        description: str,
        tools: Sequence[Tool],
        check_last_step: bool = True,
    ) -> None:
        super().__init__(id_=id_, description=description, tools=[])

        self.model = self.DEFAULT_MODEL
        self.temperature = 0.0

        self._context: str = ""
        self._examples: str = ""

        # list of execution steps moved here
        self._steps: List[Step] = []

        # inner modules
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

    # ------------------------------------------------------------------ #
    # context & examples
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # steps management (now owned by ReactAgent)
    # ------------------------------------------------------------------ #
    @property
    def steps(self) -> List[Step]:
        return self._steps

    def get_last_step(self) -> Step | None:
        return self._steps[-1] if self._steps else None

    def add_step(self, step: Step) -> None:
        self._steps.append(step)
        try:
            logger.info(JsonSchema.serialize(step))
        except Exception:
            logger.exception("Unable to serialise step for logging")

    # ------------------------------------------------------------------ #
    # inner modules (read-only)
    # ------------------------------------------------------------------ #
    @property
    def executor(self):  # -> ExecutorModule
        return self._executor

    @property
    def reviewer(self):  # -> CriticModule
        return self._reviewer

    # ------------------------------------------------------------------ #
    # delegate
    # ------------------------------------------------------------------ #
    def execute(self, command: str) -> Step:
        if command is None:
            raise ValueError("command must not be None")
        logger.info("Executing command: %s", command)
        return self._executor.execute(command)
