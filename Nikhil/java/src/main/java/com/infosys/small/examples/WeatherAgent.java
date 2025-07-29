package com.infosys.small.examples;

import java.util.List;
import java.util.Random;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.core.AbstractTool;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.react.ToolableReactAgent;
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDescription;

import lombok.NonNull;

/**
 * A ReAct agent that can return temperature fro a city.
 */
public class WeatherAgent extends ToolableReactAgent {

	static Random RND = new Random();

	// This is a tool that will be accessible to the agent
	// Notice it must be public.
	public static class GetCurrentWeatherTool extends AbstractTool {

		@JsonSchemaDescription("This is a class describing parameters for GetCurrentWeatherTool")
		public static class Parameters {

			private enum TemperatureUnits {
				CELSIUS, FARENHEIT
			};

			@JsonProperty(required = true)
			@JsonPropertyDescription("The city and state, e.g. San Francisco, CA.")
			public String location;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Your reasoning about why and how accomplish this step.")
			public String thought;

			@JsonPropertyDescription("Temperature unit (CELSIUS or FARENHEIT), defaults to CELSIUS")
			public TemperatureUnits unit;
		}

		public GetCurrentWeatherTool() {
			super("getCurrentWeather", // Function name
					"Get the current weather in a given city.", // Function description
					Parameters.class); // Function parameters
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {

			// Tool implementation goes here.
			// In this example we simply return a random temperature.

			if (!isInitialized())
				throw new IllegalStateException("Tool must be initialized.");

			String location = getString("location", call.getArguments());
			return new ToolCallResult(call, "Temperature in " + location + " is " + (RND.nextInt(10) + 20) + "°C");
		}
	} // GetCurrentWeatherTool class

	public WeatherAgent() {
		super(WeatherAgent.class.getSimpleName(), //
				"This is able to find temperature in a given town.", //
				List.of(new GetCurrentWeatherTool()), false);
	}
}