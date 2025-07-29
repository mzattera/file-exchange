# executor_module.py
from __future__ import annotations

import json
import logging
from typing import List, Mapping, Sequence, TYPE_CHECKING

from agent import Agent
from chat_types import ChatCompletion, ToolCall, ToolCallResult
from json_schema import JsonSchema
from steps import Step, ToolCallStep, Status
from tool import Tool

if TYPE_CHECKING:
    from react_agent import ReactAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class ExecutorModule(Agent):

    # ------------------------------------------------------------------ #
    # Constants
    # ------------------------------------------------------------------ #
    MAX_STEPS: int = 40  # hard stop to avoid infinite loops

    _PROMPT_TEMPLATE: str = (
        "# Identity\n\n"
        "You are a ReAct (Reasoning and Acting) agent; your task is to execute "
        "the below user command in <user_command> tag.\n"
        "\n<user_command>\n{{command}}\n</user_command>\n\n"
        "You will be provided by the user with a potentially empty list of execution "
        "steps, in <steps> tag, that you have already performed in an attempt to "
        "execute the user's command. The format of these steps is provided as a JSON "
        "schema in <step_format> tag below.\n"
        "\n<step_format>\n"
        + JsonSchema.get_json_schema(ToolCallStep)
        + "\n</step_format>\n\n"
        "Together with the list of steps, the user might provide a suggestion about "
        "how to execute the next step.\n"
        "\n# Additional Context and Information\n\n"
        " * You are identified with actor=={{id}} in execution steps."
        "{{context}}\n\n"
        "\n# Instructions\n\n"
        "  * Carefully plan the steps required to execute the user's command, think "
        "it step by step.\n"
        "  * If the user provided a suggestion about how to progress execution, then "
        "**STRICTLY** follow that suggestion when planning the next step. The "
        "suggestion applies only to the very next step.\n"
        "  * At each step use the most suitable tool at your disposal. **NEVER** "
        "output a step to *describe* a tool call – call the tool directly.\n"
        "  * Your tools have no access to <steps>; therefore pass every required "
        "parameter explicitly.\n"
        "  * When you are completely done, output a final step with status="
        "\"COMPLETED\". Do **NOT** output status=\"COMPLETED\" if work remains.\n"
        "  * If you encounter an unrecoverable error, output a final step with "
        "status=\"ERROR\" and provide a detailed explanation in the \"observation\" "
        "field. Otherwise use status=\"IN_PROGRESS\" sparingly.\n"
        "  * The final step **MUST** match the JSON schema in <output_schema>.\n"
        "\n<output_schema>\n"
        + JsonSchema.get_json_schema(Step)
        + "\n</output_schema>\n"
        "\n## Other Examples\n\n"
        "{{examples}}\n"
    )

    def __init__(
        self,
        agent: "ReactAgent",
        tools: Sequence[Tool],
        check_last_step: bool,
        model: str,
    ) -> None:
        super().__init__(
            id_=f"{agent.id}-executor",
            description=f"Executor module for {agent.id} agent",
            tools=list(tools),
        )

        self._agent: ReactAgent = agent
        self._check_last_step: bool = bool(check_last_step)
        self._command: str | None = None

        self.temperature = 0.0
        self.model = model
        self.set_response_format(Step)

    # ------------------------------------------------------------------ #
    # convenience wrappers (delegate to ReactAgent)
    # ------------------------------------------------------------------ #
    @property
    def command(self) -> str | None:
        return self._command

    def _add_step(self, step: Step) -> None:
        self._agent.add_step(step)

    def _last_step(self) -> Step | None:
        return self._agent.get_last_step()

    # ------------------------------------------------------------------ #
    # main execution loop
    # ------------------------------------------------------------------ #
    def execute(self, command: str) -> Step:
        if command is None:
            raise ValueError("command must not be None")

        self._command = command
        self._agent.steps.clear()

        # --- personality & first bookkeeping step -------------------- #
        slots: Mapping[str, str] = {
            "command": command,
            "id": self.id,
            "context": self._agent.context,
            "examples": self._agent.examples,
        }
        self.personality = Agent.fill_slots(self._PROMPT_TEMPLATE, slots)

        first_step = (
            Step.builder()
            .actor(self.id)
            .status(Status.IN_PROGRESS)
            .thought(
                Agent.fill_slots(
                    (
                        "I am starting execution of the below user's command in "
                        "<user_command>\n\n<user_command>\n{{command}}\n</user_command>"
                    ),
                    slots,
                )
            )
            .observation("Execution just started.")
            .build()
        )
        self._add_step(first_step)

        suggestion = (
            "No suggestions. Proceed as you see best, using the tools at your disposal."
        )
        instructions_tpl = "<steps>\n{{steps}}\n</steps>\n\nSuggestion: {{suggestion}}"

        # --------------------- loop ----------------------------------- #
        while (
            len(self._agent.steps) < self.MAX_STEPS
            and (
                self._last_step() is None
                or self._last_step().status is None
                or self._last_step().status == Status.IN_PROGRESS
            )
        ):
            self.clear_conversation()

            steps_json = json.dumps(
                [
                    s.model_dump(exclude={"action_steps"})
                    if isinstance(s, ToolCallStep)
                    else s.model_dump()
                    for s in self._agent.steps
                ],
                separators=(",", ":"),
            )

            prompt = Agent.fill_slots(
                instructions_tpl,
                {"steps": steps_json, "suggestion": suggestion},
            )

            try:
                reply = self.chat(prompt)
            except Exception as exc:
                error_step = (
                    ToolCallStep.builder()
                    .actor(self.id)
                    .status(Status.ERROR)
                    .thought("I had something in mind...")
                    .action("LLM was called but this resulted in an error.")
                    .action_input(prompt)
                    .action_steps([])
                    .observation(str(exc))
                    .build()
                )
                self._add_step(error_step)
                break

            if reply.finish_reason != ChatCompletion.FinishReason.COMPLETED:
                truncated_step = (
                    ToolCallStep.builder()
                    .actor(self.id)
                    .status(Status.ERROR)
                    .thought("I had something in mind...")
                    .action("LLM was called but this resulted in a truncated message.")
                    .action_input(prompt)
                    .action_steps([])
                    .observation(f"Response finish reason: {reply.finish_reason}")
                    .build()
                )
                self._add_step(truncated_step)
                break

            # ------------------- handle model output ------------------ #
            if reply.message.has_tool_calls():
                with_error = False
                for call in reply.message.get_tool_calls():
                    try:
                        result = call.execute()
                    except Exception as exc:
                        result = ToolCallResult.from_exception(call, exc)
                        with_error = True
                    else:
                        with_error |= (
                            isinstance(result.result, str)
                            and "error" in result.result.lower()
                        )

                    args_no_thought = dict(call.arguments)
                    thought = args_no_thought.pop("thought", "No thought passed explicitly.")
                    call_step = (
                        ToolCallStep.builder()
                        .actor(self.id)
                        .status(Status.IN_PROGRESS)
                        .thought(str(thought))
                        .action(f'The tool "{call.tool.id}" has been called')
                        .action_input(JsonSchema.serialize(args_no_thought))
                        .action_steps(
                            call.tool.agent.steps  # type: ignore[attr-defined]
                            if hasattr(call.tool, "agent")
                            else []
                        )
                        .observation(str(result.result))
                        .build()
                    )
                    self._add_step(call_step)

                    if len(self._agent.steps) > self.MAX_STEPS:
                        break

                suggestion = (
                    self._agent.reviewer.review_tool_call(self._agent.steps)
                    if with_error
                    else "CONTINUE"
                )
            else:
                try:
                    step_obj = reply.get_object(Step)
                    step_obj.actor = self.id
                    self._add_step(step_obj)
                except Exception as exc:
                    fallback = (
                        Step.builder()
                        .actor(self.id)
                        .status(Status.ERROR)
                        .thought(f"I stopped because I encountered this error: {exc}")
                        .observation(reply.get_text())
                        .build()
                    )
                    self._add_step(fallback)

                if self._last_step().status == Status.IN_PROGRESS:
                    suggestion = (
                        "**STRICTLY** proceed with next steps, by calling appropriate tools."
                    )
                elif self._check_last_step:
                    suggestion = self._agent.reviewer.review_conclusions(self._agent.steps)
                    if "continue" not in suggestion.lower():
                        self._last_step().status = Status.IN_PROGRESS

        # --------------------- overflow ------------------------------- #
        if len(self._agent.steps) >= self.MAX_STEPS:
            overflow_step = (
                Step.builder()
                .actor(self.id)
                .status(Status.ERROR)
                .thought(
                    f"Execution was stopped because it exceeded maximum number of steps "
                    f"({self.MAX_STEPS})."
                )
                .observation("I probably entered some kind of loop.")
                .build()
            )
            self._add_step(overflow_step)
            logger.error("Maximum steps exceeded; aborting execution.")

        return self._last_step()  # type: ignore[return-value]
