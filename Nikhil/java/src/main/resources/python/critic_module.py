# critic_module.py
from __future__ import annotations

import logging
from typing import List, Mapping

from agent import Agent
from json_schema import JsonSchema
from react_agent import ReactAgent
from steps import Step, ToolCallStep
from tool import Tool

# --------------------------------------------------------------------------- #
# Logging configuration (equivalent to Java SimpleLogger)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class CriticModule(Agent):
    """
    Critic component of a `ReactAgent`.

    It reviews the executor’s actions and suggests improvements when necessary.
    """

    # --------------------------------------------------------------------- #
    # Prompt templates
    # --------------------------------------------------------------------- #
    _PROMPT_TEMPLATE: str = (
        "# Identity\n\n"
        "You are a reviewer agent; your task is to monitor how an executor agent "
        "tries to execute user's commands and provide suggestion to improve execution.\n"
        "The specific user's command the executor is trying to execute is provided "
        "in the below <user_command> tag.\n"
        "\n<user_command>\n{{command}}\n</user_command>\n\n"
        "You will be provided by the user with a potentially empty list of execution "
        "steps, in <steps> tag, that have been already performed by the executor in "
        "its attempt to execute the user's command. The format of these steps is "
        "provided as a JSON schema in <step_format> tag below. In these steps, the "
        'executor agent is identified with actor=="{{executor_id}}".\n'
        "\n<step_format>\n"
        + JsonSchema.get_json_schema(ToolCallStep) +
        "\n</step_format>\n\n"
        "\n# Additional Context and Information\n\n"
        "  * In order to execute the command, the executor agent has the tools "
        "described in the below <tools> tag at its disposal:\n\n"
        "<tools>\n{{tools}}\n</tools>\n\n"
        "{{context}}\n"
    )

    _REVIEW_TOOL_CALL_TEMPLATE: str = (
        _PROMPT_TEMPLATE
        + "\n# Instructions\n\n"
        "  * If the steps contain evidence that the executor entered a loop calling "
        "the same tool repeatedly with identical parameters, suggest strictly calling "
        "another tool for the next step.\n"
        "  * If and only if the last step contains a tool call that resulted in an "
        "error, inspect the tool definition and check for missing or unsupported "
        "parameters; attempt to retrieve missing parameter values from previous "
        'steps’ "observation" fields. Suggest repeating the call with the recovered '
        "values and flag unsupported parameters.\n"
        '  * **IMPORTANT** In every other case, or when no relevant advice applies, '
        'output exactly "CONTINUE". Do not add comments when outputting "CONTINUE", '
        "and do not output \"CONTINUE\" when you have a suggestion."
    )

    _REVIEW_CONCLUSIONS_TEMPLATE: str = (
        _PROMPT_TEMPLATE
        + "\n# Instructions\n\n"
        '  * If, and only if, the last step has status="ERROR", carefully inspect all '
        "steps to identify the root cause and provide a remediation suggestion.\n"
        '  * If, and only if, the last step has status="COMPLETED", verify through '
        '"observation" or "thought" fields that no further work is pending; if more '
        "actions are required, suggest those actions.\n"
        '  * **IMPORTANT** In every other scenario, or when no advice is relevant, '
        'output exactly "CONTINUE". Do not add comments when outputting "CONTINUE".\n'
        '  * Consider a tool invocation valid evidence only when an "action" field '
        "explicitly references a tool; ignore claims in \"thought\" or \"observation\" "
        "that are not backed by such evidence.\n"
        "{{examples}}\n"
    )

    # --------------------------------------------------------------------- #
    # Constructor
    # --------------------------------------------------------------------- #
    def __init__(
        self,
        agent: ReactAgent,
        tools: List[Tool],
        model: str,
    ) -> None:
        if agent is None:
            raise ValueError("agent must not be None")
        if tools is None:
            raise ValueError("tools must not be None")
        if model is None:
            raise ValueError("model must not be None")

        # The critic does not call any tool, therefore `tools=[]`
        super().__init__(
            id_=f"{agent.id}-critic",
            description=f"Critic module for {agent.id} agent",
            tools=[],
        )
        self._agent: ReactAgent = agent
        self._tools: List[Tool] = list(tools)

        self.temperature = 0.0
        self.model = model

    # ------------------------------------------------------------------ #
    # Read-only properties
    # ------------------------------------------------------------------ #
    @property
    def agent(self) -> ReactAgent:  # noqa: D401
        """Return the parent `ReactAgent`."""
        return self._agent

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def review_tool_call(self, steps: List[Step]) -> str:
        """Review the latest tool call performed by the executor."""
        return self._review(self._REVIEW_TOOL_CALL_TEMPLATE, steps)

    def review_conclusions(self, steps: List[Step]) -> str:
        """Review the executor’s final conclusions."""
        return self._review(self._REVIEW_CONCLUSIONS_TEMPLATE, steps)

    # ------------------------------------------------------------------ #
    # Internal logic
    # ------------------------------------------------------------------ #
    def _review(self, template: str, steps: List[Step]) -> str:
        if steps is None:
            raise ValueError("steps must not be None")

        # Prepare placeholders for the prompt
        mapping: Mapping[str, str] = {
            "command": self._agent.executor.command,
            "executor_id": self._agent.executor.id,
            "context": self._agent.context,
            "tools": self._build_tool_description(self._tools),
            "steps": JsonSchema.serialize(steps),
        }

        # Set critic personality
        self.personality = Agent.fill_slots(template, mapping)

        # As in Java: send the same message twice
        self.clear_conversation()
        prompt = Agent.fill_slots("<steps>\n{{steps}}\n</steps>", mapping)
        suggestion = self.chat(prompt).get_text()
        logger.debug("**** Suggestion: %s", suggestion)

        # Second call (mirrors original behaviour)
        return self.chat(prompt).get_text()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_tool_description(tools: List[Tool]) -> str:
        """
        Build a human-readable description of the tools available to the executor.
        """
        sections: List[str] = []
        for tool in tools:
            sections.extend(
                [
                    "## Tool\n\n",
                    f"### Tool ID: {tool.id}\n",
                    "### Tool Description\n",
                    f"{tool.description}\n",
                    "### Tool Parameters (as JSON schema)\n",
                    f"{tool.json_parameters}\n\n",
                ]
            )
        return "".join(sections)
