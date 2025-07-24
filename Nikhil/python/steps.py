# react_step.py
from __future__ import annotations

import logging
from enum import Enum
from typing import List, Self

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class Status(str, Enum):
    """Execution status for a ReAct step."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class Step(BaseModel):
    """
    Python equivalent of `ReactAgent.Step`.

    Fields
    ------
    status       : optional execution status.
    actor        : identifier of the agent/tool performing the step.
    thought      : reasoning for this step.
    observation  : outcome, error details, or any additional data.
    """

    status: Status | None = Field(
        default=None,
        description=(
            "If you finish the execution or experience an unrecoverable error, "
            "set this to either COMPLETED or ERROR respectively."
        ),
    )
    actor: str = Field(..., description="The tool or agent that executed this step.")
    thought: str = Field(
        ...,
        description="Your reasoning about why and how you accomplish this step.",
    )
    observation: str = Field(
        ...,
        description="Any additional data, like step outcomes, error messages, etc.",
    )

    # ------------------------------------------------------------------ #
    # Fluent builder pattern
    # ------------------------------------------------------------------ #
    class Builder:
        def __init__(self) -> None:
            self._status: Status | None = None
            self._actor: str | None = None
            self._thought: str | None = None
            self._observation: str | None = None

        # --- fluent setters ------------------------------------------- #
        def status(self, status: Status) -> Self:  # noqa: D401
            self._status = status
            return self

        def actor(self, actor: str) -> Self:  # noqa: D401
            if actor is None:
                raise ValueError("actor must not be None")
            self._actor = actor
            return self

        def thought(self, thought: str) -> Self:  # noqa: D401
            if thought is None:
                raise ValueError("thought must not be None")
            self._thought = thought
            return self

        def observation(self, observation: str) -> Self:  # noqa: D401
            if observation is None:
                raise ValueError("observation must not be None")
            self._observation = observation
            return self

        # --- build ----------------------------------------------------- #
        def build(self) -> "Step":
            return Step(
                status=self._status,
                actor=self._actor or self._raise("actor"),
                thought=self._thought or self._raise("thought"),
                observation=self._observation or self._raise("observation"),
            )

        # --- helpers --------------------------------------------------- #
        @staticmethod
        def _raise(field_name: str) -> None:
            raise ValueError(f"{field_name} must not be None")

    # Provide static factory for parity with Java
    @staticmethod
    def builder() -> "Step.Builder":
        return Step.Builder()


class ToolCallStep(Step):
    """
    Python equivalent of `ReactAgent.ToolCallStep`, extending `Step`.
    """

    action: str = Field(
        ...,
        description="The action that was taken at this step. Typically a tool invocation.",
    )
    action_input: str = Field(
        ...,
        alias="action_input",
        description="Input for the action.",
    )
    action_steps: List[Step] = Field(
        default_factory=list,
        alias="action_steps",
        description=(
            "If the action was delegated to another agent, this is the list "
            "of steps that agent performed."
        ),
    )

    # ------------------------------------------------------------------ #
    # Fluent builder pattern
    # ------------------------------------------------------------------ #
    class Builder(Step.Builder):
        def __init__(self) -> None:
            super().__init__()
            self._action: str | None = None
            self._action_input: str | None = None
            self._action_steps: List[Step] = []

        # --- fluent setters ------------------------------------------- #
        def action(self, action: str) -> Self:  # noqa: D401
            if action is None:
                raise ValueError("action must not be None")
            self._action = action
            return self

        def action_input(self, action_input: str) -> Self:  # noqa: D401
            if action_input is None:
                raise ValueError("action_input must not be None")
            self._action_input = action_input
            return self

        def action_steps(self, steps: List[Step]) -> Self:  # noqa: D401
            self._action_steps = list(steps)
            return self

        def add_step(self, step: Step) -> Self:  # noqa: D401
            self._action_steps.append(step)
            return self

        # --- build ----------------------------------------------------- #
        def build(self) -> "ToolCallStep":
            return ToolCallStep(
                status=self._status,
                actor=self._actor or self._raise("actor"),
                thought=self._thought or self._raise("thought"),
                observation=self._observation or self._raise("observation"),
                action=self._action or self._raise("action"),
                action_input=self._action_input or self._raise("action_input"),
                action_steps=self._action_steps,
            )

    # Provide static factory for parity with Java
    @staticmethod
    def builder() -> "ToolCallStep.Builder":
        return ToolCallStep.Builder()

    # ------------------------------------------------------------------ #
    # Ensure alias names work both ways
    # ------------------------------------------------------------------ #
    model_config = {"populate_by_name": True}

    # ------------------------------------------------------------------ #
    # Validation to keep `status` optional but consistent
    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def _check_required(cls, values):  # noqa: N805
        # actor, thought, observation, action, action_input are ensured by Pydantic
        return values
