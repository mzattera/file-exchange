from __future__ import annotations

import logging
import random
from enum import Enum
from typing import Optional, Sequence

from pydantic import BaseModel, Field

from agent import Agent
from chat_types import ChatMessage, ToolCall, ToolCallResult
from tool import AbstractTool

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tool definition
# --------------------------------------------------------------------------- #
class GetCurrentWeatherTool(AbstractTool):
    """Python port of the Java GetCurrentWeatherTool."""

    # ----------------------------- Parameters --------------------------- #
    class TemperatureUnits(str, Enum):
        CELSIUS = "CELSIUS"
        FARENHEIT = "FARENHEIT"

    class Parameters(BaseModel):
        """This is a class describing parameters for GetCurrentWeatherTool"""

        location: str = Field(
            ...,
            description="The city and state, e.g. San Francisco, CA.",
        )
        unit: Optional["GetCurrentWeatherTool.TemperatureUnits"] = Field(
            default=TemperatureUnits.CELSIUS,
            description="Temperature unit (CELSIUS or FARENHEIT), defaults to CELSIUS",
        )

    _rnd = random.Random()

    # ----------------------------- Life-cycle --------------------------- #
    def __init__(self) -> None:
        super().__init__(
            id_="getCurrentWeather",
            description="Get the current weather in a given city.",
            parameters_cls=GetCurrentWeatherTool.Parameters,
        )

    # ----------------------------- Execution --------------------------- #
    def invoke(self, call: ToolCall) -> ToolCallResult:  # type: ignore[override]
        if call is None:
            raise ValueError("call must not be None")
        if not self.is_initialized():
            raise RuntimeError("Tool must be initialized.")

        location = self.get_string("location", call.arguments)
        temperature = self._rnd.randint(20, 29)  # 20-29 °C for demo purposes
        result = f"Temperature in {location} is {temperature}°C"
        return ToolCallResult.from_call(call, result)


# --------------------------------------------------------------------------- #
# Demo / CLI loop
# --------------------------------------------------------------------------- #
def main() -> None:
    agent = Agent("MyId", "No Description", [GetCurrentWeatherTool()])
    agent.personality = "You are an helpful assistant."

    try:
        while True:
            user_input = input("User     > ")
            reply = agent.chat(user_input)

            # Service any tool calls
            while reply.message.has_tool_calls():
                results: list[ToolCallResult] = []

                for call in reply.message.get_tool_calls():
                    print(f"CALL     > {call}")

                    try:
                        result = call.execute()
                    except Exception as exc:  # noqa: BLE001
                        result = ToolCallResult.from_exception(call, exc)
                    results.append(result)

                reply = agent.chat(ChatMessage(results))  # pass results back

            print("Assistant> " + reply.get_text())
    finally:
        agent.close()


if __name__ == "__main__":
    main()
