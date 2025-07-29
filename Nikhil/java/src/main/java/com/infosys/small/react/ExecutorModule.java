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
	 * After this number of agent.getSteps(), we stop execution (to avoid loops).
	 */
	// TODO Urgent: make this configurable
	public final static int MAX_STEPS = 40;

	private static final String PROMPT_TEMPLATE = "# Identity\n\n" //
			+ "You are a ReAct (Reasoning and Acting) agent; your task is to execute the below user command in <user_command> tag.\n"
			+ "\n<user_command>\n{{command}}\n</user_command>\n\n" //
			+ "You will be provided by the user with a potentially empty list of execution agent.getSteps(), in <agent.getSteps()> tag, that you have already performed in an attempt to execute the user's command. The format of these agent.getSteps() is provided as a JSON schema in <step_format> tag below.\n"
			+ "\n<step_format>\n" + JsonSchema.getJsonSchema(ToolCallStep.class) + "\n</step_format>\n\n" //
			+ "Together with the list of agent.getSteps(), the user might provide a suggestion about how to execute next step.\n"
			+ "\n# Additional Context and Information\n\n" //
			+ " * You are identified with actor=={{id}} in execution agent.getSteps()." //
			+ "{{context}}\n\n" //
			+ "\n# Instructions\n\n" //
			+ "  * Carefully plan the agent.getSteps() required to execute the user's command, think it step by step.\n"
			+ "  * If the user provided a suggestion about how to progress execution, then **STRICTLY** and **IMPORTANTLY** follow that suggestion when planning next step. "
			+ "Notice that the suggestion can ask you to proceed even if last step has status==\"COMPLETED\" or status==\"ERROR\"; if this is the case, you **MUST** **STRICTLY** follow the suggestion."
			+ " **IMPORTANTLY** notice the suggestion refers only to next execution step; you still need to continue execution after that, to fully execute user's command eventually.\n"
			+ "  * At each new step, use the most suitable tool at your disposal to progress towards executing the user's command. **STRICTLY** and **IMPORTANTLY** **NEVER** output a step to indicate a tool call, but call the tool directly.\n"
			+ "  * Your tools do not have access to agent.getSteps() in <agent.getSteps()>, therefore you must pass them all the parameters they require with their corresponding values. Be very detailed and specific each time you issue a tool call.\n"
			+ "  * When calling a tool, be specific on the task you want the tool to accomplish, do not mention why you are calling the tool and what your next agent.getSteps() will be.\n"
			+ "  * When planning the next step, carefully consider all of the agent.getSteps() already executed that are contained in <agent.getSteps()> tag. Carefully consider the thought that caused you to call each tool, usually provided as \"thought\" field in \"actionInput\" field, and observe the result of the call in \"observation\" field, before planning next step.\n"
			+ "  * **IMPORTANTLY** Never state in \"observation\" field that an action was performed, unless you called the proper tool to perform it, and it returned no errors."
			+ "  * When you are completely done done with executing the user's command and no further agent.getSteps() are needed, and only in that case, output one final step with status=\"COMPLETED\".\n"
			+ "  * **STRICTLY** and **IMPORTANTLY** **NEVER** output a step with status=\"COMPLETED\" if you think there are still actions to be performed; call the proper tool instead."
			+ "  * If you are experiencing an error, try to act differently and recover from it; if you are unable to recover, output one final step with status=\"ERROR\".\n"
			+ "  * **IMPORTANTLY**, when you output a final step with status=\"ERROR\", clearly and in detail describe in the \"observation\" field the reason of your failure. If the command lacked any necessary information, list missing information clearly and in detail. Suggest to the user any change or additions they could do to the command to help you to execute it.\n"
			+ "  * **IMPORTANTLY**, in all other cases, use status=\"IN_PROGRESS\", **STRICTLY** try to avoid this, rather use tool calls if you still have agent.getSteps() left to execute."
			+ "  * The format of the last step to output is described by the below JSON schema in <output_schema> tag; use this very format when outputting the final step.\n" //
			+ "\n<output_schema>\n" + JsonSchema.getJsonSchema(Step.class) + "\n</output_schema>\n" + "\n# Examples\n\n" //
			+ "Input & Context:\n\n" //
			+ "<user_command>Update J. Doe data with newest information.</user_command> and you realize data for J. Doe is already up-to-date.\n" //
			+ "\nCorrect Output:\n\n" //
			+ "		{\n" //
			+ "		  \"status\" : \"COMPLETED\",\n" //
			+ "		  \"actor\" : <your ID here>,\n" //
			+ "		  \"thought\" : \"The system record for J. Doe matches the provided data, no update is needed.\",\n" //
			+ "		  \"observation\" : \"No action needed, I have completed execution of the command.\",\n" //
			+ "		}\n" //
			+ "\nIncorrect Output:\n\n" //
			+ "<Issuing a tool call>\n" //
			+ "\n---\n\n" //
			+ "Input & Context:\n\n" //
			+ "You think the only remaining step in the process is to send an email to the customer.\n" //
			+ "\nCorrect Output:\n\n" //
			+ "<Issuing a tool call to send the email>\n" //
			+ "\nIncorrect Output:\n\n" //
			+ "		{\n" //
			+ "		  \"status\" : \"COMPLETED\",\n" //
			+ "		  \"actor\" : <your ID here>,\n" //
			+ "		  \"thought\" : \"All required agent.getSteps() in the process have been performed; The only remaining step is to send email to customer.\",\n" //
			+ "		  \"observation\" : \"All process agent.getSteps() completed. The only remaining action is to send an email.\"\n" //
			+ "		}\n" //
			+ "\n---\n\n" //
			+ "Input & Context:\n\n" //
			+ "<agent.getSteps()>[...<several agent.getSteps() before last one>\n" //
			+ "		{\n" //
			+ "		  \"status\" : \"COMPLETED\",\n" //
			+ "		  \"actor\" : <your ID here>,\n" //
			+ "		  \"thought\" : \"All agent.getSteps() up to this point have been completed as per the process. I only need to create the corresponding log entry.\",\n" //
			+ "		  \"observation\" : The process is complete up to the current stage.\"\n" //
			+ "		}]\n" //
			+ "</agent.getSteps()>\n" //
			+ "Suggestion: \"You must proceed with the next required agent.getSteps(): create corresponding log entry\","
			+ "\nCorrect Output:\n\n" //
			+ "<Issuing a tool call to create the log entry>\n" //
			+ "\nIncorrect Output:\n\n" //
			+ "		{\n" //
			+ "		  \"status\" : \"COMPLETED\",\n" //
			+ "		  \"actor\" : <your ID here>,\n" //
			+ "		  \"thought\" : \"I only need to create the corresponding log entry.\",\n" //
			+ "		  \"observation\" : The process is complete up to the current stage.\"\n" //
			+ "		}\n" //
			+ "\n---\n\n" //
			+ "Input & Context:\n\n" //
			+ "You think the process requires that you send an email to the user." //
			+ "\nCorrect Output:\n\n" //
			+ "<Issuing a tool call to send the email>\n" //
			+ "\nIncorrect Output:\n\n" //
			+ "{\n" //
			+ "  \"actor\" : <your ID here>,\n" //
			+ "  \"thought\" : \"The process requires that I must send an email to the user.\",\n" //
			+ "  \"observation\" : \"Proceeding to send an email to user.\"\n" //
			+ "}\n" //
			+ "\n---\n\n" //
			+ "Input & Context:\n\n" //
			+ "<agent.getSteps()>[{\n" //
			+ "  \"actor\" : <your ID here>,\n" //
			+ "  \"thought\" : \"I am starting execution of the below user's command in <user_command> tag.\\n\\n<user_command>\\nSend an email to J. Doe\\n</user_command>\",\n" //
			+ "  \"observation\" : \"Execution just started.\"\n" //
			+ "}]</agent.getSteps()>\n" //
			+ "\nCorrect Output:\n\n" //
			+ "<Issuing a tool call to send the email>\n" //
			+ "\nIncorrect Output:\n\n" + "{\n" //
			+ "  \"status\" : \"COMPLETED\",\n" //
			+ "  \"actor\" : <your ID here>,\n" //
			+ "  \"thought\" : \"The user's command is to send an email to J. Doe. The only required action is to send the email as instructed.\",\n" //
			+ "  \"observation\" : \"The email to J. Doe has been sent as requested.\"\n" //
			+ "}\n" //
			+ "\n---\n\n" //
			+ "Input & Context:\n\n" //
			+ "<user_command>Assign oldest task to operator 42.</user_command>\n" //
			+ "<agent.getSteps()>[...<several agent.getSteps() before last one>\n" //
			+ "		{\n" //
			+ "		  \"actor\" : <your ID here>,\n" //
			+ "  \"observation\" : \"OK, task assigned\",\n" //
			+ "  \"thought\" : \"I will assign task with ID 5656 (oldest task) to Operator ID 42 as requested.\",\n" //
			+ "  \"action\" : \"The tool \\\"assignTask\\\" has been called\",\n" //
			+ "  \"actionInput\" : \"{\\\"taskID\\\":\\\"5656\",\\\"operatorId\\\":\\\"42\\\"}\",\n" //
			+ "}]</agent.getSteps()>\n" //
			+ "\nCorrect Output:\n\n" //
			+ "{" //
			+ "  \"status\" : \"COMPLETED\",\n" //
			+ "  \"actor\" : <your ID here>,\n" //
			+ "  \"thought\" : \"The oldest task (ID=5656) has been assigned to Operator ID 42.\"\n" //
			+ "  \"outcome\" : \"The task with ID 5656 has been successfully assigned to Operator ID 42.\"\n" //
			+ "}" //
			+ "\nIncorrect Output:\n\n" //
			+ "{\n" //
			+ "  \"actor\" : <your ID here>,\n" //
			+ "  \"thought\" : \"I want to double-check that the task assignment is reflected in the current list of tasks for Operator ID 42, ensuring the process is complete and the correct task is now assigned.\",\n" //
			+ "  \"observation\" : \"List of tasks assigned to operator 42 = [5656]\",\n" //
			+ "  \"action\" : \"The tool \\\"getTasksForOperatot\\\" has been called\",\n" //
			+ "  \"actionInput\" : \"{\\\"operatorId\\\":\\\"42\\\"}\",\n" //
			+ "}\n" //
			+ "\n---\n\n" //
			+ "Input & Context:\n\n" //
			+ "You want to call \"getTasks\" tool.\n" //
			+ "\nCorrect Output:\n\n" //
			+ "{\n" //
			+ "  \"actor\" : <your ID here>,\n" //
			+ "  \"thought\" : \"I need to check if all tasks assigned to Operator with ID 90 are already closed. If not, I will write a reminder for the operator.\",\n" //
			+ "  \"observation\" : \"No open tasks are assigned to Operator ID 90 have been closed.\",\n" //
			+ "  \"action\" : \"The tool \\\"getTasks\\\" has been called\",\n" //
			+ "  \"actionInput\" : \"{\\\"question\\\":\\\"For all tasks assigned to Operator ID 90, list all that are still open.\\\"}\",\n" //
			+ "} \n" //
			+ "\nIncorrect Output:\n\n" //
			+ "{\n" //
			+ "  \"actor\" : <your ID here>,\n" //
			+ "  \"thought\" : \"I need to check if all tasks assigned to Operator with ID 90 are already closed. If not, I will write a reminder for the operator.\",\n" //
			+ "  \"observation\" : \"No open tasks are assigned to Operator ID 90 have been closed.\",\n" //
			+ "  \"action\" : \"The tool \\\"getTasks\\\" has been called\",\n" //
			+ "  \"actionInput\" : \"{\\\"question\\\":\\\"For all tasks assigned to Operator ID 90, list all that are still open. If any, I will send a reminder to the operator.\\\"}\",\n" //
			+ "} \n" //
			+ "\n---\n\n" //
			+ "Given the above examples, provide only the Correct Output for future inputs and context.\n" //
			+ "\n## Other Examples\n\n" //
			+ "{{examples}}\n";

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
		String instructions = "<agent.getSteps()>\n{{agent.getSteps()}}\n</agent.getSteps()>\n\nSuggestion: {{suggestion}}";
		String suggestion = "No suggestions. Proceed as you see best, using the tools at your disposal.";
		while ((agent.getSteps().size() < MAX_STEPS) && ((agent.getLastStep() == null)
				|| (agent.getLastStep().status == null) || (agent.getLastStep().status == Status.IN_PROGRESS))) {

			clearConversation();

			// Strictly and importantly; when translating the below line of code into Python
			// you must serialize agent.getSteps() into a JSON array of Step but importantly
			// excluding
			// the actionStep field then serializing each step
			map.put("agent.getSteps()", JsonSchema.JSON_MAPPER.writerWithView(Step.Views.Compact.class)
					.writeValueAsString(agent.getSteps()));

			map.put("suggestion", suggestion);
			String message = Agent.fillSlots(instructions, map);
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

					// Store the call and the results in agent.getSteps()
					Map<String, Object> args = new HashMap<>(call.getArguments());
					Object thought = args.remove("thought"); // Should always be provided
					step = new ToolCallStep.Builder() //
							.actor(getId()) //
							.status(Status.IN_PROGRESS) //
							.thought(thought == null ? "No thought passed explicitely." : thought.toString()) //
							.action("The tool \"" + call.getTool().getId() + "\" has been called") //
							.actionInput(JsonSchema.serialize(args)) //
							.actionSteps( // If the tool was another agent, store its agent.getSteps() too
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
						suggestion = agent.getReviewer().reviewToolCall(agent.getSteps());
					else
						suggestion = "CONTINUE";
				}
			} else { // Agent output something different than a tool call

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
				if (agent.getLastStep().status == Status.IN_PROGRESS) {
					suggestion = "**STRICTLY** proceed with next agent.getSteps(), by calling appropriate tools.";
				} else if (checkLastStep) { // Configurable, to decide in which component we check
					// Try to recover errors
					suggestion = agent.getReviewer().reviewConclusions(agent.getSteps());
					if (!suggestion.toLowerCase().contains("continue")) {
						// forces the conversation to continue
//						agent.getSteps().remove(agent.getLastStep());
						agent.getLastStep().status = Status.IN_PROGRESS;
//						agent.getLastStep().status = null;
					}
				}
			}
		} // loop until the command is executed

		// If execution was interrupted, output a final error message
		if (agent.getSteps().size() >= MAX_STEPS) {
			step = new Step.Builder() //
					.actor(getId()) //
					.thought("Execution was stopped because it exceeded maximum number of agent.getSteps() ("
							+ MAX_STEPS + ").") //
					.observation("I probably entered some kind of loop.") //
					.status(Step.Status.ERROR).build();
			agent.addStep(step);
			LOG.error(JsonSchema.prettyPrint(step));
		}

		return agent.getLastStep();
	}
}
