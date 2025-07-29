package com.infosys.small.pnbc;

import java.util.HashMap;
import java.util.Map;

import com.infosys.small.core.AbstractTool;
import com.infosys.small.core.Tool;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.pnbc.ExecutionContext.DbConnector;
import com.infosys.small.react.ExecutorModule;

import lombok.NonNull;

/**
 * This is a {@link Tool} represents an API call for a simulated backend system.
 */
public abstract class Api extends AbstractTool {

	/**
	 * @param id
	 * @param description
	 * @param schema
	 */
	public Api(@NonNull String id, String description, @NonNull Class<?> schema) {
		super(id, description, schema);
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

	/**
	 * @return Current execution context (or null if it is not set).
	 */
	public ExecutionContext getExecutionContext() {
		if (getLabAgent() != null)
			return getLabAgent().getExecutionContext();
		return null;
	}

	/**
	 * Gets the connection to the database. This is valid only if execution context
	 * has been set.
	 */
	public DbConnector getDb() {
		return getExecutionContext().getDb();
	}

	/**
	 * Gets the ID for the scenario we are currently running. This is valid only if
	 * execution context has been set.
	 */
	public String getScenarioId() {
		return getExecutionContext().getScenarioId();
	}

	/**
	 * Gets the ID for current run. This is valid only if execution context has been
	 * set.
	 */
	public String getRunId() {
		return getExecutionContext().getRunId();
	}

	@Override
	public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {
		return invoke(call, false);
	}

	/**
	 * Same as {@link #invoke(ToolCall)} but logs the call.
	 */
	public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
		if (!isInitialized()) {
			throw new IllegalArgumentException("Tool must be initialized.");
		}

		Map<String, Object> args = new HashMap<>(call.getArguments());
		args.remove("thought"); // As we are passing it, we must remove or it won't match tools

		String scenario = getLabAgent().getScenarioId();
		if (log)
			getLabAgent().getExecutionContext().log(scenario, call.getTool().getId(), args);

		String result = ScenarioComponent.getInstance().get( //
				scenario, //
				getId(), //
				args);
		return new ToolCallResult(call, result);
	}
}
