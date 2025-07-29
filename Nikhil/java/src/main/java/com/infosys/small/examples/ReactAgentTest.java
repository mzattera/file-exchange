package com.infosys.small.examples;

import java.util.List;

import com.infosys.small.react.ReactAgent;

public class ReactAgentTest {

	public static void main(String[] args) throws Exception {

		ReactAgent agent = new ReactAgent("Orchestrator", "Test ReAct Agent",
				List.of(new PersonLocatorAgent(), new WeatherAgent()), false);

		agent.execute("Determine whether the temperature in the town where Maxi is located the same as in Copenhagen.");

		System.out.println("//////////////////////////////////////////////////////////////////////");

//		System.out.println(agent.getPersonality());
//		System.out.println();
//		System.out
//				.println(JsonSchema.JSON_MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(agent.getSteps()));
	} 
}
