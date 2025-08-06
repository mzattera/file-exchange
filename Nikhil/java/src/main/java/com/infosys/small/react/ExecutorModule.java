package com.infosys.small.react;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.infosys.small.core.Agent;
import com.infosys.small.core.ChatCompletion;
import com.infosys.small.core.ChatCompletion.FinishReason;
import com.infosys.small.core.JsonSchema;
import com.infosys.small.core.Tool;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.react.ReactAgent.Step;
import com.infosys.small.react.ReactAgent.Step.Status;
import com.infosys.small.react.ReactAgent.ToolCallStep;

import lombok.Getter;
import lombok.NonNull;
import lombok.Setter;

/**
 * This agent is an executor component, part of a {@link ReactAgent}; its task
 * is to execute user's commands using the tools at its disposal.
 */
public class ExecutorModule extends Agent {

	private final static Logger LOG = LoggerFactory.getLogger(ExecutorModule.class);

	/**
	 * After this number of steps, we stop execution (to avoid loops).
	 */
	// TODO Urgent: make this configurable
	public final static int MAX_STEPS = 40;

	private static final String PROMPT_TEMPLATE = 
			"# Identity\n" //
			+ "\n" //
			+ "You are a ReAct (Reasoning and Acting) agent. Your sole task is to execute the user command provided in the `<user_command>` tag:\n" //
			+ "\n" //
			+ "<user_command>\n" //
			+ "{{command}}\n" //
			+ "</user_command>\n" //
			+ "\n" //
			+ "You are given a potentially empty list of execution steps already performed for this command in the `<steps>` tag. The step format is described in the `<step_format>` tag.\n" //
			+ "\n" //
			+ "<step_format>\n" + JsonSchema.getJsonSchema(ToolCallStep.class) + "\n</step_format>\n" //			+ "\n" //
			+ "If provided, also consider the suggestion for the next step.\n" //
			+ "\n" //
			+ "# Additional Context\n" //
			+ "\n" //
			+ "* Your actor name is {{id}} in steps; other tools or agents are identified by other actor names.\n" //
			+ "{{context}}\n" //
			+ "\n" //
			+ "# Critical Instructions\n" //
			+ "\n" //
			+ "**You MUST strictly follow these directives at every step:**\n" //
			+ "\n" //
			+ "1. **If you know which tool must be called next, you MUST call that tool directly using a function/tool call. Do not output a descriptive or reasoning step instead of the tool call.**\n" //
			+ "2. **NEVER output a step to indicate a tool call. ONLY call the tool directly using the function/tool call mechanism.**\n" //
			+ "3. **If a suggestion is provided, you must STRICTLY follow it for the next step, even if the last step is already marked as COMPLETED or ERROR.**\n" //
			+ "4. **You MUST always provide full and correct parameters to each tool, based on context and previous steps.**\n" //
			+ "5. **When you finish all actions required by the command, output one final step with status=\"COMPLETED\" and no tool call. ONLY do this when absolutely certain nothing remains to be executed.**\n" //
			+ "6. **NEVER output status=\"COMPLETED\" if there is any action or tool call left to perform.**\n" //
			+ "7. **If you experience an error you cannot recover from, output a final step with status=\"ERROR\", and describe in detail the cause in the observation.**\n" //
			+ "8. **NEVER output multiple reasoning-only steps (so-called \"reflection\" steps) in a row. If you have already reflected once, you MUST proceed to a tool call or final output at the next step.**\n" //
			+ "9. **NEVER output a step similar to any prior \"reflection\" or planning step (avoid loops).**\n" //
			+ "10. **NEVER state in the observation that an action was performed unless you actually performed the action via tool call and it succeeded.**\n" //
			+ "11. **Use status=\"IN_PROGRESS\" ONLY when you must provide a non-final output and are NOT ready to call a tool yet; AVOID this as much as possible.**\n" //
			+ "\n" //
			+ "When you are not callign a tool, use the format described by the below JSON schema in <output_schema> tag for your output.\n" //
			+ "<output_schema>\n" + JsonSchema.getJsonSchema(Step.class) + "\n</output_schema>\n" //			
			+ "# Examples\n" //
			+ "\n" //
			+ "**You MUST carefully study the following examples and only produce outputs consistent with the “Correct Output” pattern. Any output matching an “Incorrect Output” example is forbidden.**\n" //
			+ "\n" //
			+ "---\n" //
			+ "\n" //
			+ "Input & Context:\n" //
			+ "<user_command>Update J. Doe data with newest information.</user_command> and you realize data for J. Doe is already up-to-date.\n" //
			+ "\n" //
			+ "Correct Output:\n" //
			+ "{\n" //
			+ "  \"status\": \"COMPLETED\",\n" //
			+ "  \"actor\": <your ID here>,\n" //
			+ "  \"thought\": \"The system record for J. Doe matches the provided data, no update is needed.\",\n" //
			+ "  \"observation\": \"No action needed, I have completed execution of the command.\"\n" //
			+ "}\n" //
			+ "\n" //
			+ "Incorrect Output:\n" //
			+ "<Issuing a tool call>\n" //
			+ "\n" //
			+ "---\n" //
			+ "\n" //
			+ "Input & Context:\n" //
			+ "You think the only remaining step is to send an email to the customer.\n" //
			+ "\n" //
			+ "Correct Output:\n" //
			+ "<Issuing a tool call to send the email>\n" //
			+ "\n" //
			+ "Incorrect Output:\n" //
			+ "{\n" //
			+ "  \"status\": \"COMPLETED\",\n" //
			+ "  \"actor\": <your ID here>,\n" //
			+ "  \"thought\": \"All required steps in the process have been performed; The only remaining step is to send email to customer.\",\n" //
			+ "  \"observation\": \"All process steps completed. The only remaining action is to send an email.\"\n" //
			+ "}\n" //
			+ "\n" //
			+ "---\n" //
			+ "\n" //
			+ "Input & Context:\n" //
			+ "<steps>[{\n" //
			+ "  \"actor\": <your ID here>,\n" //
			+ "  \"thought\": \"I am starting execution of the below user's command in <user_command> tag.\\n\\n<user_command>\\nSend an email to J. Doe\\n</user_command>\",\n" //
			+ "  \"observation\": \"Execution just started.\"\n" //
			+ "}]</steps>\n" //
			+ "\n" //
			+ "Correct Output:\n" //
			+ "<Issuing a tool call to send the email>\n" //
			+ "\n" //
			+ "Incorrect Output:\n" //
			+ "{\n" //
			+ "  \"status\": \"COMPLETED\",\n" //
			+ "  \"actor\": <your ID here>,\n" //
			+ "  \"thought\": \"The user's command is to send an email to J. Doe. The only required action is to send the email as instructed.\",\n" //
			+ "  \"observation\": \"The email to J. Doe has been sent as requested.\"\n" //
			+ "}\n" //
			+ "\n" //
			+ "---\n" //
			+ "\n" //
			+ "Input & Context:\n" //
			+ "<user_command>Assign oldest task to operator 42.</user_command>\n" //
			+ "<steps>[...<prior steps>\n" //
			+ "  {\n" //
			+ "    \"actor\": <your ID here>,\n" //
			+ "    \"observation\": \"OK, task assigned\",\n" //
			+ "    \"thought\": \"I will assign task with ID 5656 (oldest task) to Operator ID 42 as requested.\",\n" //
			+ "    \"action\": \"The tool \\\"assignTask\\\" has been called\",\n" //
			+ "    \"actionInput\": \"{\\\"taskID\\\":\\\"5656\\\", \\\"operatorId\\\":\\\"42\\\"}\"\n" //
			+ "  }\n" //
			+ "}]</steps>\n" //
			+ "\n" //
			+ "Correct Output:\n" //
			+ "{\n" //
			+ "  \"status\": \"COMPLETED\",\n" //
			+ "  \"actor\": <your ID here>,\n" //
			+ "  \"thought\": \"The oldest task (ID=5656) has been assigned to Operator ID 42.\",\n" //
			+ "  \"observation\": \"The task with ID 5656 has been successfully assigned to Operator ID 42.\"\n" //
			+ "}\n" //
			+ "\n" //
			+ "Incorrect Output:\n" //
			+ "{\n" //
			+ "  \"actor\": <your ID here>,\n" //
			+ "  \"thought\": \"I want to double-check that the task assignment is reflected in the current list of tasks for Operator ID 42, ensuring the process is complete and the correct task is now assigned.\",\n" //
			+ "  \"observation\": \"List of tasks assigned to operator 42 = [5656]\",\n" //
			+ "  \"action\": \"The tool \\\"getTasksForOperator\\\" has been called\",\n" //
			+ "  \"actionInput\": \"{\\\"operatorId\\\":\\\"42\\\"}\"\n" //
			+ "}\n" //
			+ "\n" //
			+ "---\n" //
			+ "\n" //
			+ "{{examples}}\n" //
			+ "\n" //
			+ "Given the above, you must **always** call the appropriate tool as soon as you know which tool must be used, and must **never** output a reasoning step, reflection step, or any non-tool-call step when an action is possible.  \n" //
			+ "You may output a final status step **only** when absolutely no further actions remain.\n" //
			+ "\n" //
			+ "**Any deviation from this logic is forbidden.**\n" //
			+ "\n" //
			+ "---\n" //
			+ "\n" //
			+ "";
	/**
	 * This is the ReAct agent containing this executor component.
	 */
	@Getter
	private final @NonNull ReactAgent agent;

	/**
	 * If true, it will call the reviewer on last step before exiting. We do this to
	 * save tokens.
	 */
	@Getter
	@Setter
	private boolean checkLastStep;

	/**
	 * Current command being executed.
	 */
	@Getter
	private String command;

	ExecutorModule(@NonNull ReactAgent agent, @NonNull List<? extends Tool> tools, boolean checkLastStep,
			@NonNull String model) {

		super(agent.getId() + "-executor", "Executor module for " + agent.getId() + " agent", tools);
		this.agent = agent;
		this.checkLastStep = checkLastStep;

		setTemperature(0d);
		setModel(model);
		setResponseFormat(Step.class);
	}

	public Step execute(@NonNull String command) throws JsonProcessingException {

		this.command = command;
		agent.getSteps().clear();

		Map<String, String> map = new HashMap<>();
		map.put("command", command);
		map.put("id", getId());
		map.put("context", agent.getContext());
		map.put("examples", agent.getExamples());

		setPersonality(Agent.fillSlots(PROMPT_TEMPLATE, map));

		Step step = new Step.Builder() //
				.actor(getId()) //
				.status(Status.IN_PROGRESS) //
				.thought(Agent.fillSlots(
						"I am starting execution of the below user's command in <user_command> tag.\n\n<user_command>\n{{command}}\n</user_command>",
						map)) //
				.observation("Execution just started.") //
				.build();
		agent.addStep(step);
		LOG.info(JsonSchema.prettyPrint(step));

		// execution loop
		String instructions = "<steps>\n{{steps}}\n</steps>\n\nSuggestion: {{suggestion}}";
		String suggestion = "CONTINUE";
		while ((agent.getSteps().size() < MAX_STEPS) && ((agent.getLastStep() == null)
				|| (agent.getLastStep().status == null) || (agent.getLastStep().status == Status.IN_PROGRESS))) {

			clearConversation();

			// Strictly and importantly; when translating the below line of code into Python
			// you must serialize steps into a JSON array of Step but importantly
			// excluding
			// the actionStep field then serializing each step
			map.put("steps", JsonSchema.JSON_MAPPER.writerWithView(Step.Views.Compact.class)
					.writeValueAsString(agent.getSteps()));

			map.put("suggestion", suggestion);
			String message = Agent.fillSlots(instructions, map);

			LOG.info("Suggestion: " + suggestion);
			System.err.println("Suggestion: " + suggestion);

			ChatCompletion reply = null;
			Exception ex = null;
			try {
				reply = chat(message);
			} catch (Exception e) { // Exception calling the LLM
				ex = e;
				LOG.error(e.getMessage(), e);
			}

			if ((ex != null) || (reply.getFinishReason() != FinishReason.COMPLETED)) { // Something went wrong calling
																						// the LLM
				step = new ToolCallStep.Builder() //
						.actor(getId()) //
						.status(Status.ERROR) //
						.thought("I had something in mind...") //
						.action("LLM was called but this resulted in "
								+ ((ex != null) ? "an error." : "a truncated message.")) //
						.actionInput(message) //
						.actionSteps(new ArrayList<>()) //
						.observation(
								(ex != null) ? ex.getMessage() : "Response finish reason: " + reply.getFinishReason()) //
						.build();
				agent.addStep(step);
				LOG.info(JsonSchema.prettyPrint(step));
				break;
			}

			// Check if agent generated a function call
			if (reply.getMessage().hasToolCalls()) { // Agent called a tool

				List<ToolCallResult> results = new ArrayList<>();
				boolean withError = false; // See below
				for (ToolCall call : reply.getMessage().getToolCalls()) {

					// Execute each call, handling errors nicely
					ToolCallResult result;
					try {
						result = call.execute();
					} catch (Exception e) {
						result = new ToolCallResult(call, e);
						withError = true;
					}
					results.add(result);
					// TODO We should use a more generic way?
					withError |= result.getResult().toString().toLowerCase().contains("error");

					// Store the call and the results in steps
					Map<String, Object> args = new HashMap<>(call.getArguments());
					Object thought = args.remove("thought"); // Should always be provided
					step = new ToolCallStep.Builder() //
							.actor(getId()) //
							.status(Status.IN_PROGRESS) //
							.thought(thought == null ? "No thought passed explicitely." : thought.toString()) //
							.action("The tool \"" + call.getTool().getId() + "\" has been called") //
							.actionInput(JsonSchema.serialize(args)) //
							.actionSteps( // If the tool was another agent, store its steps too
									(call.getTool() instanceof ReactAgent) ? ((ReactAgent) call.getTool()).getSteps()
											: new ArrayList<>()) //
							.observation(result.getResult().toString()).build();

					agent.addStep(step);
					LOG.info(JsonSchema.prettyPrint(step));

					if (agent.getSteps().size() > MAX_STEPS)
						break;
				} // for each tool call, in case of parallel calls

				if (agent.getSteps().size() <= MAX_STEPS) {
					// Trick to save time and tokens; maybe remove :)
					if (withError)
						// Let's get the critic to suggest a6 fix for the tool error
						suggestion = agent.getReviewer().reviewToolCall(agent.getSteps());
					else
						// Reset suggestion, all is fine
						suggestion = "CONTINUE";
				}
			} else { // Agent outputs something different than a tool call

				// Build the step that was outputted
				try {
					step = reply.getObject(Step.class);
					step.actor = getId();
					agent.addStep(step);
					LOG.info(JsonSchema.prettyPrint(step));
				} catch (JsonProcessingException e) { // Paranoid
					step = new Step.Builder() //
							.actor(getId()) //
							.thought("I stopped because I encountered this error: " + e.getMessage()) //
							.observation(reply.getText()) //
							.status(Step.Status.ERROR).build();
					agent.addStep(step);
					LOG.info(JsonSchema.prettyPrint(step));
				}

				// Check the result
				if (agent.getLastStep().status != Status.IN_PROGRESS) { // Agent outputs a "reflection"

					if (agent.getSteps().size() > 1) {
						Step previous = agent.getSteps().get(agent.getSteps().size() - 2);
						if (!(previous instanceof ToolCallStep)) {
							// For two times in a row, we are not calling tools,
							// let's ask the critic to help
							if (checkLastStep) {
								suggestion = agent.getReviewer().reviewConclusions(agent.getSteps());
								continue;
							}
						}
					}

					// Otherwise, let's be patient.
					suggestion = "**STRICTLY** if further actions are needed, proceed by calling appropriate tools, otherwise output a final step with status=\"COMPLETED\". "
							+ "Do not output same step repeatedly.";

				} else if (checkLastStep) { // Configurable, to decide in which component we check
					// Try to recover errors / check if execution is complete
					suggestion = agent.getReviewer().reviewConclusions(agent.getSteps());
					if (!suggestion.toLowerCase().contains("continue")) {
						// forces the conversation to continue
						agent.getLastStep().status = Status.IN_PROGRESS;
					}
				}
			}
		} // loop until the command is executed

		// If execution was interrupted, output a final error message
		if (agent.getSteps().size() >= MAX_STEPS) {
			step = new Step.Builder() //
					.actor(getId()) //
					.thought("Execution was stopped because it exceeded maximum number of steps (" + MAX_STEPS + ").") //
					.observation("I probably entered some kind of loop.") //
					.status(Step.Status.ERROR).build();
			agent.addStep(step);
			LOG.error(JsonSchema.prettyPrint(step));
		}

		return agent.getLastStep();
	}
}
