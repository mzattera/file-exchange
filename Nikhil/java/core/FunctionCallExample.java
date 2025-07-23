package core;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.Scanner;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDescription;

import lombok.NonNull;

public class FunctionCallExample {

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

			@JsonPropertyDescription("Temperature unit (CELSIUS or FARENHEIT), defaults to CELSIUS")
			public TemperatureUnits unit;
		}

		public GetCurrentWeatherTool() throws JsonProcessingException {
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

	public static void main(String[] args) throws Exception {

		Agent agent = new Agent("MyId", "No Description", List.of(new GetCurrentWeatherTool()));
		agent.setPersonality("You are an helpful assistant.");

		// Conversation loop
		try (Scanner console = new Scanner(System.in)) {
			while (true) {
				System.out.print("User     > ");
				String s = console.nextLine();

				ChatCompletion reply = agent.chat(s);

				// Check if agent generated a function call
				while (reply.getMessage().hasToolCalls()) {

					List<ToolCallResult> results = new ArrayList<>();

					// TODO Urgent: display any content that is not a tool call.
					// Add a method to get all and only concatenated text?

					for (ToolCall call : reply.getMessage().getToolCalls()) {

						// Print call for illustrative purposes
						System.out.println("CALL " + " > " + call);

						// Execute call, handling errors nicely
						ToolCallResult result;
						try {
							result = call.execute();
						} catch (Exception e) {
							result = new ToolCallResult(call, e);
						}
						results.add(result);
					}

					// Pass results back to the agent
					// Notice this might in principle generate
					// other tool calls, hence the loop
					reply = agent.chat(new ChatMessage(results));

				} // while we serviced all calls

				System.out.println("Assistant> " + reply.getText());
			}
		}
	}
}