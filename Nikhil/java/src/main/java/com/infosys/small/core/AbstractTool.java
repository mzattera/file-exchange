package com.infosys.small.core;

import java.util.Map;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NonNull;
import lombok.Setter;

/**
 * This is an abstract class that implementations of {@link Tool}s can extend.
 * It mostly provides methods to read and cast arguments parameters into the
 * right type.
 * 
 * @author Massimiliano "Maxi" Zattera
 */
public abstract class AbstractTool implements Tool {

	/**
	 * Unique Tool ID.
	 */
	@Getter
	private final String id;

	/**
	 * Description for this tool.
	 */
	@Getter
	private String description = "";

	/**
	 * JSON schema describing parameters for this tool.
	 */
	@Getter
	private final String jsonParameters;

	/**
	 * The agent using this tool.
	 */
	@Getter
	private Agent agent;

	/**
	 * True if this tool has been closed already.
	 */
	@Getter
	@Setter(AccessLevel.PROTECTED)
	private boolean closed = false;

	/**
	 * @return True if the tool has been initialized.
	 */
	@Override
	public boolean isInitialized() {
		return (agent != null);
	}

	@Override
	public void init(@NonNull Agent agent) {
		if (isInitialized())
			throw new RuntimeException("Tool " + id + " is already initialized");
		if (closed)
			throw new RuntimeException("Tool " + id + " is already closed");
		this.agent = agent;
	}

	protected AbstractTool(@NonNull String id, @NonNull String description, @NonNull Class<?> c) {
		this.id = id;
		this.description = description;
		this.jsonParameters = JsonSchema.getJsonSchema(c);
	}

	@Override
	public void close() {
		closed = true;
	}

	//
	// Below there are utility methods to read parameters.
	// When translating these into Python you need to check whether parameters are
	// of desired type OR
	// they are string values that can be parsed into instances of given type.
	//
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
