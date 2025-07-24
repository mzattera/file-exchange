# weather_agent.py
from __future__ import annotations

import logging
import random
from enum import Enum
from pydantic import BaseModel, Field

from toolable_react_agent import ToolableReactAgent
from tool import AbstractTool
from tool_call import ToolCall
from tool_call_result import ToolCallResult

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_RND = random.Random()


class WeatherAgent(ToolableReactAgent):
    """ReAct agent able to return the current temperature for a city."""

    # ------------------------------------------------------------------ #
    # Nested tool
    # ------------------------------------------------------------------ #
    class GetCurrentWeatherTool(AbstractTool):
        """Tool that returns a faux current temperature."""

        # ---------- enums & parameters ------------------------------- #
        class TemperatureUnits(str, Enum):
            CELSIUS = "CELSIUS"
            FARENHEIT = "FARENHEIT"

        class Parameters(BaseModel):
            location: str = Field(
                ...,
                description="The city and state, e.g. San Francisco, CA.",
            )
            thought: str = Field(
                ...,
                description="Your reasoning about why and how accomplish this step.",
            )
            unit: TemperatureUnits | None = Field(
                default=TemperatureUnits.CELSIUS,
                description="Temperature unit (CELSIUS or FARENHEIT), defaults to CELSIUS",
            )

        # ---------- construction ------------------------------------- #
        def __init__(self) -> None:
            super().__init__(
                id_="getCurrentWeather",
                description="Get the current weather in a given city.",
                parameters_cls=WeatherAgent.GetCurrentWeatherTool.Parameters,
            )

        # ---------- invocation --------------------------------------- #
        def invoke(self, call: ToolCall) -> ToolCallResult:  # noqa: D401
            if not self.is_initialized():
                raise RuntimeError("Tool must be initialized.")

            location = self.get_string("location", call.arguments)
            temperature = _RND.randint(20, 29)  # simple mock
            return ToolCallResult.from_call(
                call,
                f"Temperature in {location} is {temperature}°C",
            )

    # ------------------------------------------------------------------ #
    # Agent initialisation
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        super().__init__(
            id_=self.__class__.__name__,
            description="This agent can find temperature in a given town.",
            tools=[WeatherAgent.GetCurrentWeatherTool()],
            check_last_step=False,
        )
