# executor_module.py
from __future__ import annotations

import json
import logging
from typing import Mapping, Sequence, TYPE_CHECKING

from agent import Agent
from chat_types import ChatCompletion, ToolCallResult
from json_schema import JsonSchema
from steps import Step, ToolCallStep, Status
from tool import Tool

if TYPE_CHECKING:  # avoid runtime circular import
    from react_agent import ReactAgent

# ------------------------------------------------------------------------------
# Logging (equivalent to Java SimpleLogger)
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class ExecutorModule(Agent):
    """
    Python translation of `com.infosys.small.react.ExecutorModule`.

    This component executes a user command by orchestrating calls to the tools
    available to its enclosing `ReactAgent`.
    """

    # After this number of steps, we stop execution (to avoid loops).
    # TODO Urgent: make this configurable
    MAX_STEPS: int = 40

    # Prompt template ported verbatim (with schema slots filled at runtime)
    _PROMPT_TEMPLATE: str = (
        "# Identity\n"
        "\n"
        "You are a ReAct (Reasoning and Acting) agent. Your sole task is to execute the user command provided in the `<user_command>` tag:\n"
        "\n"
        "<user_command>\n"
        "{{command}}\n"
        "</user_command>\n"
        "\n"
        "You are given a potentially empty list of execution steps already performed for this command in the `<steps>` tag. The step format is described in the `<step_format>` tag.\n"
        "\n"
        "<step_format>\n" + JsonSchema.get_json_schema(ToolCallStep) + "\n</step_format>\n"
        "If provided, also consider the suggestion for the next step.\n"
        "\n"
        "# Additional Context\n"
        "\n"
        "* Your actor name is {{id}} in steps; other tools or agents are identified by other actor names.\n"
        "{{context}}\n"
        "\n"
        "# Critical Instructions\n"
        "\n"
        "**You MUST strictly follow these directives at every step:**\n"
        "\n"
        "1. **If you know which tool must be called next, you MUST call that tool directly using a function/tool call. Do not output a descriptive or reasoning step instead of the tool call.**\n"
        "2. **NEVER output a step to indicate a tool call. ONLY call the tool directly using the function/tool call mechanism.**\n"
        "3. **If a suggestion is provided, you must STRICTLY follow it for the next step, even if the last step is already marked as COMPLETED or ERROR.**\n"
        "4. **You MUST always provide full and correct parameters to each tool, based on context and previous steps.**\n"
        "5. **When you finish all actions required by the command, output one final step with status=\"COMPLETED\" and no tool call. ONLY do this when absolutely certain nothing remains to be executed.**\n"
        "6. **NEVER output status=\"COMPLETED\" if there is any action or tool call left to perform.**\n"
        "7. **If you experience an error you cannot recover from, output a final step with status=\"ERROR\", and describe in detail the cause in the observation.**\n"
        "8. **NEVER output multiple reasoning-only steps (so-called \"reflection\" steps) in a row. If you have already reflected once, you MUST proceed to a tool call or final output at the next step.**\n"
        "9. **NEVER output a step similar to any prior \"reflection\" or planning step (avoid loops).**\n"
        "10. **NEVER state in the observation that an action was performed unless you actually performed the action via tool call and it succeeded.**\n"
        "11. **Use status=\"IN_PROGRESS\" ONLY when you must provide a non-final output and are NOT ready to call a tool yet; AVOID this as much as possible.**\n"
        "\n"
        "When you are not callign a tool, use the format described by the below JSON schema in <output_schema> tag for your output.\n"
        "<output_schema>\n" + JsonSchema.get_json_schema(Step) + "\n</output_schema>\n"
        "# Examples\n"
        "\n"
        "**You MUST carefully study the following examples and only produce outputs consistent with the “Correct Output” pattern. Any output matching an “Incorrect Output” example is forbidden.**\n"
        "\n"
        "---\n"
        "\n"
        "Input & Context:\n"
        "<user_command>Update J. Doe data with newest information.</user_command> and you realize data for J. Doe is already up-to-date.\n"
        "\n"
        "Correct Output:\n"
        "{\n"
        '  "status": "COMPLETED",\n'
        '  "actor": <your ID here>,\n'
        '  "thought": "The system record for J. Doe matches the provided data, no update is needed.",\n'
        '  "observation": "No action needed, I have completed execution of the command."\n'
        "}\n"
        "\n"
        "Incorrect Output:\n"
        "<Issuing a tool call>\n"
        "\n"
        "---\n"
        "\n"
        "Input & Context:\n"
        "You think the only remaining step is to send an email to the customer.\n"
        "\n"
        "Correct Output:\n"
        "<Issuing a tool call to send the email>\n"
        "\n"
        "Incorrect Output:\n"
        "{\n"
        '  "status": "COMPLETED",\n'
        '  "actor": <your ID here>,\n'
        '  "thought": "All required steps in the process have been performed; The only remaining step is to send email to customer.",\n'
        '  "observation": "All process steps completed. The only remaining action is to send an email."\n'
        "}\n"
        "\n"
        "---\n"
        "\n"
        "Input & Context:\n"
        "<steps>[{\n"
        '  "actor": <your ID here>,\n'
        '  "thought": "I am starting execution of the below user\'s command in <user_command> tag.\\n\\n<user_command>\\nSend an email to J. Doe\\n</user_command>",\n'
        '  "observation": "Execution just started."\n'
        "}]</steps>\n"
        "\n"
        "Correct Output:\n"
        "<Issuing a tool call to send the email>\n"
        "\n"
        "Incorrect Output:\n"
        "{\n"
        '  "status": "COMPLETED",\n'
        '  "actor": <your ID here>,\n'
        '  "thought": "The user\'s command is to send an email to J. Doe. The only required action is to send the email as instructed.",\n'
        '  "observation": "The email to J. Doe has been sent as requested."\n'
        "}\n"
        "\n"
        "---\n"
        "\n"
        "Input & Context:\n"
        "<user_command>Assign oldest task to operator 42.</user_command>\n"
        "<steps>[...<prior steps>\n"
        "  {\n"
        '    "actor": <your ID here>,\n'
        '    "observation": "OK, task assigned",\n'
        '    "thought": "I will assign task with ID 5656 (oldest task) to Operator ID 42 as requested.",\n'
        '    "action": "The tool \\"assignTask\\" has been called",\n'
        '    "actionInput": "{\\"taskID\\":\\"5656\\", \\"operatorId\\":\\"42\\"}"\n'
        "  }\n"
        "}]</steps>\n"
        "\n"
        "Correct Output:\n"
        "{\n"
        '  "status": "COMPLETED",\n'
        '  "actor": <your ID here>,\n'
        '  "thought": "The oldest task (ID=5656) has been assigned to Operator ID 42.",\n'
        '  "observation": "The task with ID 5656 has been successfully assigned to Operator ID 42."\n'
        "}\n"
        "\n"
        "Incorrect Output:\n"
        "{\n"
        '  "actor": <your ID here>,\n'
        '  "thought": "I want to double-check that the task assignment is reflected in the current list of tasks for Operator ID 42, ensuring the process is complete and the correct task is now assigned.",\n'
        '  "observation": "List of tasks assigned to operator 42 = [5656]",\n'
        '  "action": "The tool \\"getTasksForOperator\\" has been called",\n'
        '  "actionInput": "{\\"operatorId\\":\\"42\\"}"\n'
        "}\n"
        "\n"
        "---\n"
        "\n"
        "{{examples}}\n"
        "\n"
        "Given the above, you must **always** call the appropriate tool as soon as you know which tool must be used, and must **never** output a reasoning step, reflection step, or any non-tool-call step when an action is possible.  \n"
        "You may output a final status step **only** when absolutely no further actions remain.\n"
        "\n"
        "**Any deviation from this logic is forbidden.**\n"
        "\n"
        "---\n"
        "\n"
    )

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        agent: ReactAgent,
        tools: Sequence[Tool],
        check_last_step: bool,
        model: str,
    ) -> None:
        if agent is None:
            raise ValueError("agent must not be None")
        if tools is None:
            raise ValueError("tools must not be None")
        if model is None:
            raise ValueError("model must not be None")

        super().__init__(
            id_=f"{agent.id}-executor",
            description=f"Executor module for {agent.id} agent",
            tools=list(tools),
        )

        self._agent: ReactAgent = agent
        self._check_last_step: bool = bool(check_last_step)
        self._command: str | None = None

        self.set_temperature(0.0)
        self.set_model(model)
        self.set_response_format(Step)

    # ------------------------------------------------------------------ #
    # Read-only / properties
    # ------------------------------------------------------------------ #
    @property
    def agent(self) -> ReactAgent:
        return self._agent

    @property
    def check_last_step(self) -> bool:
        return self._check_last_step

    @check_last_step.setter
    def check_last_step(self, value: bool) -> None:
        self._check_last_step = bool(value)

    @property
    def command(self) -> str | None:
        return self._command

    # ------------------------------------------------------------------ #
    # Main execution loop
    # ------------------------------------------------------------------ #
    def execute(self, command: str) -> Step:
        if command is None:
            raise ValueError("command must not be None")

        self._command = command
        self._agent.steps.clear()

        # Build personality from template
        slots: Mapping[str, str] = {
            "command": command,
            "id": self.id,
            "context": self._agent.context,
            "examples": self._agent.examples,
        }
        self.set_personality(Agent.fill_slots(self._PROMPT_TEMPLATE, slots))

        # First bookkeeping step
        first_step = (
            Step.builder()
            .actor(self.id)
            .status(Status.IN_PROGRESS)
            .thought(
                Agent.fill_slots(
                    (
                        "I am starting execution of the below user's command in the "
                        "<user_command> tag.\n\n<user_command>\n{{command}}\n</user_command>"
                    ),
                    slots,
                )
            )
            .observation("Execution just started.")
            .build()
        )
        self._agent.add_step(first_step)

        # Execution loop
        instructions_tpl = "<steps>\n{{steps}}\n</steps>\n\nSuggestion: {{suggestion}}"
        suggestion = "CONTINUE"

        while (
            len(self._agent.steps) < self.MAX_STEPS
            and (
                self._agent.get_last_step() is None
                or self._agent.get_last_step().status is None
                or self._agent.get_last_step().status == Status.IN_PROGRESS
            )
        ):
            self.clear_conversation()

            # IMPORTANT: serialize steps as a JSON array of Step objects,
            # EXCLUDING the `action_steps` field in ToolCallStep objects.
            steps_json = json.dumps(
                [
                    (
                        s.model_dump(exclude={"action_steps"})
                        if isinstance(s, ToolCallStep)
                        else s.model_dump()
                    )
                    for s in self._agent.steps
                ],
                separators=(",", ":"),
            )

            prompt = Agent.fill_slots(
                instructions_tpl, {"steps": steps_json, "suggestion": suggestion}
            )

            logger.info("Suggestion: %s", suggestion)

            # Call the LLM
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
                self._agent.add_step(error_step)
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
                self._agent.add_step(truncated_step)
                break

            # Check if agent generated a function/tool call
            if reply.message.has_tool_calls():
                with_error = False

                for call in reply.message.get_tool_calls():
                    # Execute each call, handling errors nicely
                    try:
                        result = call.execute()
                    except Exception as exc:
                        result = ToolCallResult.from_exception(call, exc)
                        with_error = True

                    # Fallback heuristic: mark error if result string contains "error"
                    with_error = with_error or (
                        isinstance(result.result, str)
                        and "error" in result.result.lower()
                    )

                    # Store the call and the results in steps
                    args_no_thought = dict(call.arguments)
                    thought = args_no_thought.pop(
                        "thought", "No thought passed explicitely."
                    )

                    call_step = (
                        ToolCallStep.builder()
                        .actor(self.id)
                        .status(Status.IN_PROGRESS)
                        .thought(str(thought))
                        .action(f'The tool "{call.tool.id}" has been called')
                        .action_input(json.dumps(args_no_thought, separators=(",", ":")))
                        .action_steps(
                            # If the tool was another agent, store its steps too
                            call.tool.steps if hasattr(call.tool, "steps") else []
                        )
                        .observation("" if result.result is None else str(result.result))
                        .build()
                    )
                    self._agent.add_step(call_step)

                    if len(self._agent.steps) > self.MAX_STEPS:
                        break

                if len(self._agent.steps) <= self.MAX_STEPS:
                    # Trick to save time and tokens; maybe remove :)
                    suggestion = (
                        self._agent.reviewer.review_tool_call(self._agent.steps)
                        if with_error
                        else "CONTINUE"
                    )

            else:
                # Agent outputs something different than a tool call
                try:
                    step_obj = reply.get_object(Step)
                    step_obj.actor = self.id
                    self._agent.add_step(step_obj)
                except Exception as exc:
                    fallback = (
                        Step.builder()
                        .actor(self.id)
                        .status(Status.ERROR)
                        .thought(f"I stopped because I encountered this error: {exc}")
                        .observation(reply.get_text())
                        .build()
                    )
                    self._agent.add_step(fallback)

                # Check the result
                last = self._agent.get_last_step()
                if last.status != Status.IN_PROGRESS:  # model output is a “reflection”
                    if len(self._agent.steps) > 1:
                        previous = self._agent.steps[-2]
                        if not isinstance(previous, ToolCallStep):
                            # For two times in a row, we are not calling tools,
                            # let's ask the critic to help
                            if self._check_last_step:
                                suggestion = self._agent.reviewer.review_conclusions(
                                    self._agent.steps
                                )
                                continue

                    # Otherwise, let's be patient.
                    suggestion = (
                        '**STRICTLY** if further actions are needed, proceed by calling '
                        'appropriate tools, otherwise output a final step with '
                        'status="COMPLETED". Do not output same step repeatedly.'
                    )

                elif self._check_last_step:
                    # Try to recover errors / check if execution is complete
                    suggestion = self._agent.reviewer.review_conclusions(
                        self._agent.steps
                    )
                    if "continue" not in suggestion.lower():
                        # forces the conversation to continue
                        self._agent.get_last_step().status = Status.IN_PROGRESS

        # If execution was interrupted, output a final error message
        if len(self._agent.steps) >= self.MAX_STEPS:
            overflow = (
                Step.builder()
                .actor(self.id)
                .status(Status.ERROR)
                .thought(
                    f"Execution was stopped because it exceeded maximum number of steps ({self.MAX_STEPS})."
                )
                .observation("I probably entered some kind of loop.")
                .build()
            )
            self._agent.add_step(overflow)
            logger.error("Maximum steps exceeded; aborting execution.")

        return self._agent.get_last_step()  # type: ignore[return-value]
