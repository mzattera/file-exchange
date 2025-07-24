# react_agent_test.py
from __future__ import annotations

from react_agent import ReactAgent
from person_locator_agent import PersonLocatorAgent
from weather_agent import WeatherAgent

if __name__ == "__main__":
    agent = ReactAgent(
        id_="Orchestrator",
        description="Test ReAct Agent",
        tools=[PersonLocatorAgent(), WeatherAgent()],
        check_last_step=False,
    )

    final_step = agent.execute(
        "Determine whether the temperature in the town where Maxi is located is the same as in Copenhagen."
    )

    # Print final observation to console
    print(final_step.observation)
