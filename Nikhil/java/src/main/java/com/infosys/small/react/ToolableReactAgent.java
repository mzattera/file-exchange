package com.infosys.small.react;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.core.Agent;
import com.infosys.small.core.JsonSchema;
import com.infosys.small.core.Tool;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDescription;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NonNull;
import lombok.Setter;

/**
 * This is a {@link ReactAgent} wrapped into a {@link Tool}, so it can be used
 * as a tool by other agents.
 */
public class ToolableReactAgent extends ReactAgent implements Tool {

	// TODO Maybe merge with ReactAgent? Might be a 6good idea to keep 7tool
	// interface separated though
	// TODO Maybe better to have a Tool wrapped as inner class rather than implement
	// all get methods?

	@JsonSchemaDescription("This describes parameters needed to call an execution agent")
	public static class Parameters extends ReactAgent.Parameters {

		@JsonProperty(required = true)
		@JsonPropertyDescription("A question that this tool must answer or a command it must execute.")
		public String question;
	}

	/**
	 * JSON schema describing parameters for this tool.
	 */
	@Getter
	private String jsonParameters;

	protected void setJsonParameters(Class<?> schema) {
		jsonParameters = JsonSchema.getJsonSchema(schema);
	}
	
	/**
	 * True if this tool has been closed already.
	 */
	@Getter
	@Setter(AccessLevel.PROTECTED)
	private boolean closed = false;

	/**
	 * Agent using this tool.
	 */
	@Getter
	private Agent agent;

	/**
	 * @return True if the tool has been initialized.
	 */
	@Override
	public boolean isInitialized() {
		return (getAgent() != null);
	}

	@Override
	public void init(@NonNull Agent agent) {
		if (isInitialized())
			throw new RuntimeException("Tool " + getId() + " is already initialized");
		if (closed)
			throw new RuntimeException("Tool " + getId() + " is already closed");
		this.agent = agent;
	}

	public ToolableReactAgent(@NonNull String id, @NonNull String description, @NonNull List<? extends Tool> tools,
			boolean checkLastStep) {

		super(id, description, tools, checkLastStep);
		jsonParameters = JsonSchema.getJsonSchema(Parameters.class);
	}

	@Override
	public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {
		if (!isInitialized())
			throw new IllegalStateException("Tool must be initialized.");

		String question = getString("question", call.getArguments());
		if (question == null)
			return new ToolCallResult(call, "ERROR: You must provide a command to execute as \"question\" parameter.");

		Step result = execute(question);
		switch (result.status) {
		case ERROR:
			return new ToolCallResult(call, "ERROR: " + result.observation);
		default:
			return new ToolCallResult(call, result.observation);
		}
	}

	@Override
	public void close() {
		closed = true;
		super.close();
	}

	// Utility methods to read parameters
	// TODO URGENT be smarter
	// ////////////////////////////////////////////////////////////////////////////////////////////

	protected static boolean getBoolean(String name, Map<String, ? extends Object> args) {
		if (args.containsKey(name))
			return getBoolean(name, args.get(name));
		throw new IllegalArgumentException("Missing required parameter \"" + name + "\".");
	}

	protected static boolean getBoolean(String name, Map<String, ? extends Object> args, boolean def) {
		if (!args.containsKey(name))
			return def;
		return getBoolean(name, args.get(name));
	}

	private static boolean getBoolean(String name, Object value) {
		String s = value.toString();
		if ("true".equals(s.trim().toLowerCase()))
			return true;
		if ("false".equals(s.trim().toLowerCase()))
			return false;

		throw new IllegalArgumentException(
				"Parameter \"" + name + "\" is expected to be a boolean value but it is not.");
	}

	protected static long getLong(String name, Map<String, ? extends Object> args) {
		if (args.containsKey(name))
			return getLong(name, args.get(name));
		throw new IllegalArgumentException("Missing required parameter \"" + name + "\".");
	}

	protected static long getLong(String name, Map<String, ? extends Object> args, long def) {
		if (!args.containsKey(name))
			return def;
		return getLong(name, args.get(name));
	}

	private static long getLong(String name, Object value) {
		try {
			return Long.parseLong(value.toString());
		} catch (Exception e) {
			throw new IllegalArgumentException(
					"Parameter \"" + name + "\" is expected to be a integer value but it is not.");
		}
	}

	protected static double getDouble(String name, Map<String, ? extends Object> args) {
		if (args.containsKey(name))
			return getDouble(name, args.get(name));
		throw new IllegalArgumentException("Missing required parameter \"" + name + "\".");
	}

	protected static double getDouble(String name, Map<String, ? extends Object> args, double def) {
		if (!args.containsKey(name))
			return def;
		return getDouble(name, args.get(name));
	}

	protected static double getDouble(String name, Object value) {
		try {
			return Double.parseDouble(value.toString());
		} catch (Exception e) {
			throw new IllegalArgumentException(
					"Parameter \"" + name + "\" is expected to be a decimal number but it is not.");
		}
	}

	protected static String getString(String name, Map<String, ? extends Object> args) {
		Object result = args.get(name);
		if (result == null)
			return null;
		return result.toString();
	}

	protected static String getString(String name, Map<String, ? extends Object> args, String def) {
		if (!args.containsKey(name))
			return def;
		return getString(name, args);
	}
}