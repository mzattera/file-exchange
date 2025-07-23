
from __future__ import annotations

import sys
import traceback
from pydantic import BaseModel, Field

from agent import Agent
from json_schema import JsonSchema


class Format(BaseModel):
    """Schema describing the agent’s output."""
    out: str = Field(..., description="Your output message")


def run_agent_demo() -> None:
    """
    Replicates the Java `Agent.main` behaviour:
      1. Instantiates an `Agent`.
      2. Sets its personality and response format.
      3. Sends a greeting and prints the reply.
      4. Ensures resources are released.
    """
    bot: Agent | None = None
    try:
        bot = Agent()
        bot.personality = (
            "Always output messages as described by this schema: "
            f"{JsonSchema.get_json_schema(Format)}"
        )
        bot.set_response_format(Format)
        print(bot.chat("Ciao!").get_text())
    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    finally:
        if bot is not None:
            try:
                bot.close()
            except Exception:
                pass


-- 
This email has been checked for viruses by Avast antivirus software.
www.avast.com
