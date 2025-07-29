package com.infosys.small.pnbc;

import java.util.List;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.infosys.small.core.Tool;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.pnbc.ExecutionContext.DbConnector;
import com.infosys.small.react.ExecutorModule;
import com.infosys.small.react.ToolableReactAgent;

import lombok.Getter;
import lombok.NonNull;

/**
 * This is an agent ({@link ToolableReactAgent}) that can interact with a
 * (simulated) backend system or orchestrate a (simulated) process. In addition,
 * it cna be used as a 6{@link Tool} by other agents.
 */
public class LabAgent extends ToolableReactAgent {

	/**
	 * Current execution context.
	 * 
	 * When set, it allows the agent to run in a simulated environment.
	 * 
	 * Notice this stays set only for the duration of
	 * {@link #execute(ExecutionContext, String)}
	 */
	@Getter
	private @NonNull ExecutionContext executionContext;

	/**
	 * Gets the connection to the database. This is valid only if execution context
	 * has been set.
	 */
	public DbConnector getDb() {
		return executionContext.getDb();
	}

	/**
	 * Gets the ID for the scenario we are currently running. This is valid only if
	 * execution context has been set.
	 */
	public String getScenarioId() {
		return executionContext.getScenarioId();
	}

	/**
	 * Gets the ID for current run. This is valid only if execution context has been
	 * set.
	 */
	public String getRunId() {
		return executionContext.getRunId();
	}

	/**
	 * @return The {@link LabAgent}that is using this tool, or null if it is not
	 *         running inside a LabAgent.
	 */
	public LabAgent getLabAgent() {
		if (getAgent() instanceof LabAgent) // Paranoid, should never be the case
			return (LabAgent) getAgent();
		if (getAgent() instanceof ExecutorModule) { // normally, it's in a ReactAgent inside a LabAgent
			ExecutorModule executor = (ExecutorModule) getAgent();
			if (executor.getAgent() instanceof LabAgent)
				return (LabAgent) executor.getAgent();
		}
		return null;
	}

	public LabAgent(@NonNull String id, @NonNull String description, @NonNull List<? extends Tool> tools) {
		this(id, description, tools, false);
	}

	public LabAgent(@NonNull String id, @NonNull String description, @NonNull List<? extends Tool> tools,
			boolean checkLastStep) {
		super(id, description, tools, checkLastStep);
	}

	/**
	 * Executes one command but it sets execution context first. This allows for
	 * having the agent running in a test (simulated) environment.
	 */
	public Step execute(ExecutionContext ctx, String command) throws JsonProcessingException {
		executionContext = ctx;
		return execute(command);
	}

	/**
	 * When invoked as a tool; it uses current execution context.
	 */
	@Override
	public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {
		if (!isInitialized())
			throw new IllegalStateException("Tool must be initialized.");

		String question = getString("question", call.getArguments());
		if (question == null)
			return new ToolCallResult(call, "ERROR: You must provide a command to execute as \"question\" parameter.");

		ExecutionContext ctx = getLabAgent().getExecutionContext(); // Get execution context from caller
		Step result = execute(ctx, question);
		switch (result.status) {
		case ERROR:
			return new ToolCallResult(call, "ERROR: " + result.observation);
		default:
			return new ToolCallResult(call, result.observation);
		}
	}
}
