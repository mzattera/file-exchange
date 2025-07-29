package com.infosys.small.pnbc;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.NonNull;

/**
 * This is used to access scenarios.
 */
public class ScenarioComponent {

	private final static Logger LOG = LoggerFactory.getLogger(ScenarioComponent.class);

	@Data
	@NoArgsConstructor
	@AllArgsConstructor
	public static class Scenario {
		private String id;
		private String description;

		@JsonProperty("success_criteria")
		private String successCriteria;

		@JsonProperty("tool_calls")
		private List<ScenarioToolCall> toolCalls;
	}

	@Data
	@NoArgsConstructor
	@AllArgsConstructor
	public static class ScenarioToolCall {
		@JsonProperty("tool_id")
		private String toolId;

		private Map<String, Object> input;
		private List<Output> output;
	}

	@Data
	@NoArgsConstructor
	@AllArgsConstructor
	public static class Output {
		private String type;
		private String value;
	}

	@Data
	@AllArgsConstructor
	public static class ScenarioMetadata {
		@JsonProperty("id")
		private String id;

		@JsonProperty("description")
		private String description;
	}

	private final File scenarioFolder;
	private final ObjectMapper objectMapper = new ObjectMapper();
	private final List<Scenario> scenarios = new ArrayList<>();

	public static ScenarioComponent getInstance() throws IOException {
		return new ScenarioComponent(
				new File("D:\\Users\\mzatt\\Projects\\DELETEME PnBC\\pnbc-services\\src\\main\\resources\\scenarios"));
	}

	public ScenarioComponent(@NonNull File folder) throws IOException {
		this.scenarioFolder = folder;

		File[] files = scenarioFolder.listFiles((dir, name) -> name.endsWith(".json"));
		if (files == null)
			throw new IOException("Scenario folder is empty or inaccessible");

		for (File file : files) {
			try {
				scenarios.addAll(objectMapper.readValue(file, new TypeReference<List<Scenario>>() {
				}));
			} catch (IOException e) {
				LOG.error("Error parsing scenario " + file.getName(), e);
				throw e;
			}
		}
	}

	public List<Scenario> listScenarios() {
		return new ArrayList<>(scenarios);
	}

	/**
	 * 
	 * @param scenarioId
	 * @return Given scenario, or null if it cannot be found.
	 */
	public Scenario getScenario(@NonNull String scenarioId) throws IOException {

		for (Scenario s : listScenarios())
			if (scenarioId.equals(s.getId())) {
				return s;
			}
		return null;
	}

	public String getSuccessCriteria(@NonNull String scenarioId) {

		Scenario scenario = null;
		try {
			scenario = getScenario(scenarioId);
		} catch (IOException e) {
			return null;
		}

		if (scenario == null)
			return null;
		return scenario.getSuccessCriteria();
	}

	public String get(@NonNull String scenarioId, @NonNull String toolId, @NonNull Map<String, Object> args)
			throws IOException {

		Scenario scenario = getScenario(scenarioId);

		if (scenario == null)
			return "ERROR: Scenario " + scenarioId + " does not exist.";

		for (ScenarioToolCall call : scenario.getToolCalls()) {
			if (!toolId.equals(call.getToolId()))
				continue;

			if (!matched(call.getInput(), args))
				continue;

			return call.getOutput().stream().filter(output -> "text".equals(output.getType())).map(Output::getValue)
					.reduce("", (a, b) -> a + b);
		}

		return "ERROR: System failure, wrong API call parameters.";
	}

	private static Map<String, String> transformMap(Map<String, Object> input) {
		Map<String, String> result = new java.util.HashMap<>();
		for (Map.Entry<String, Object> entry : input.entrySet()) {
			String newKey = entry.getKey() == null ? "" : entry.getKey().toLowerCase().trim();
			String newValue = entry.getValue() == null ? "" : entry.getValue().toString().toLowerCase().trim();
			result.put(newKey, newValue);
		}
		return result;
	}

	private static boolean matched(Map<String, Object> map1, Map<String, Object> map2) {
		Map<String, String> t1 = transformMap(map1);
		Map<String, String> t2 = transformMap(map2);
		for (Map.Entry<String, String> entry : t1.entrySet()) {
			if (!t2.containsKey(entry.getKey()) || !t2.get(entry.getKey()).equals(entry.getValue())) {
				return false;
			}
		}
		return true;
	}

	public static void main(String args[]) throws IOException {
		ScenarioComponent instance = ScenarioComponent.getInstance();
		System.out.println(instance.get("scenario-01", "getUnassignedTasks", new HashMap<>()));
	}
}
