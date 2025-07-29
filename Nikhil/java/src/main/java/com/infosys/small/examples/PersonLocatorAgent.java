package com.infosys.small.examples;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.core.AbstractTool;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.react.ToolableReactAgent;
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDescription;

import lombok.NonNull;

/**
 * A ReAct agent that can return location of a person.
 */
public class PersonLocatorAgent extends ToolableReactAgent {

	public static class LocatePersonTool extends AbstractTool {

		@JsonSchemaDescription("This is a class describing parameters for LocatePersonTool")
		public static class Parameters {

			@JsonProperty(required = true)
			@JsonPropertyDescription("The name of the person you want to locate.")
			public String person;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Your reasoning about why and how accomplish this step.")
			public String thought;
		}

		public LocatePersonTool() {
			super("locatePersonTool", // Function name
					"Returns the city where a person is located.", // Function description
					LocatePersonTool.Parameters.class); // Function parameters
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {

			// Tool implementation goes here.
			// In this example we simply return a random temperature.

			if (!isInitialized())
				throw new IllegalStateException("Tool must be initialized.");

			String person = getString("person", call.getArguments());
			return new ToolCallResult(call, person + " is currently located in Padua, Italy.");
		}
	} // GetCurrentWeatherTool class

	public PersonLocatorAgent() {
		super(PersonLocatorAgent.class.getSimpleName(), //
				"This tool is able to find temperature in a given town.", //
				List.of(new LocatePersonTool()), false);
	}
}