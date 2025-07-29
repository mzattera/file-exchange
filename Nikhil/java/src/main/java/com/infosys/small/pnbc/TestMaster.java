package com.infosys.small.pnbc;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileWriter;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVPrinter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.infosys.small.core.Agent;
import com.infosys.small.core.JsonSchema;
import com.infosys.small.pnbc.ExecutionContext.ApiCallEntry;
import com.infosys.small.pnbc.ExecutionContext.DbConnector;
import com.infosys.small.pnbc.ExecutionContext.DiaryEntry;
import com.infosys.small.pnbc.ExecutionContext.EmailEntry;
import com.infosys.small.pnbc.ExecutionContext.InteractionEntry;
import com.infosys.small.pnbc.ExecutionContext.PaymentEntry;
import com.infosys.small.pnbc.ExecutionContext.UploadEntry;
import com.infosys.small.react.ReactAgent.Step;
import com.infosys.small.react.ReactAgent.ToolCallStep;
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDescription;

import ch.qos.logback.classic.LoggerContext;
import ch.qos.logback.classic.encoder.PatternLayoutEncoder;
import ch.qos.logback.classic.sift.MDCBasedDiscriminator;
import ch.qos.logback.classic.sift.SiftingAppender;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.FileAppender;
import lombok.Data;
import lombok.NonNull;

/**
 * This is an agent that checks process runs output and measures total accuracy
 * (number of times a process was correctly executed).
 */
public class TestMaster extends Agent {

	private final static Logger LOG = LoggerFactory.getLogger(TestMaster.class);

	public static final File OUTPUT_FOLDER = new File("D:\\DELETEME - pnbc test");

	// Scenarios to use when testing
	public static final List<String> SCENARIOS = List.of(//
			"scenario-01", //
			"scenario-02a", //
			"scenario-02b" //
	);

	// # Tests to execute (for each scenario)
	private static final int NUM_TEST = 1;

	// Parallel execution threads, to speed things up
	private static final int NUM_THREADS = Math.min(NUM_TEST * SCENARIOS.size(), 15);

	private static final String[] HEADERS = { "Scenario", "Run#", "Model", "Orchestrator Steps", "Total Steps",
			"Result", "Confidence", "Passed", "Reasoning" };

	@JsonSchemaDescription("This is a class describing the response the TestMaster returns.")
	public static class Response {

		@JsonProperty(required = true)
		@JsonPropertyDescription("True if and only if you think the success criteria was matched.")
		public boolean success;

		public enum Level {
			VERY_HIGH, HIGH, MEDIUM, LOW, VERY_LOW
		}

		@JsonProperty(required = true)
		@JsonPropertyDescription("How confident you are that your assessment about the success criteria is correct.")
		public @NonNull Level confidenceLevel;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The rationale about your decision whether the success criteria was met.")
		public @NonNull String rationale;
	}

	@JsonSchemaDescription("This is a class describing results for one test run.")
	@Data
	public static class TestResult {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Scenario used fo rthis test.")
		private final @NonNull String scenarioId;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique test ID, for this scenario.")
		private final @NonNull String runId;

		@JsonPropertyDescription("Result of the test.")
		private final Response result;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Model the agent used.")
		private final @NonNull String model;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Execution steps performed by the agnt in this run.")
		private final @NonNull List<Step> steps;

		@JsonPropertyDescription("Unrecoverable execution error.")
		private final Exception error;
	}

	/**
	 * @param ep
	 */
	public TestMaster() {
		this(DEFAULT_MODEL);
	}

	/**
	 * @param ep
	 * @param model
	 */
	public TestMaster(@NonNull String model) {
		super("TestMaseter", "This is a test harness", new ArrayList<>());

		setModel(model);
		setTemperature(0d);
		setResponseFormat(Response.class);
		setPersonality("# Identity\n" //
				+ "\n" //
				+ "You are an AI agent, monitoring performances of other agents.\n" //
				+ "\n" //
				+ "You will be provided with a list of steps, inside a <steps> tag that the other agent undertook in order to complete the task assigned to it.\n" //
				+ "\n" //
				+ "The format of each step is described by the JSON schema below:\n" //
				+ "\n" //
				+ JsonSchema.getJsonSchema(ToolCallStep.class) + "\n" //
				+ "You will also be provided with a list of log entries created by the agent, inside a <log> tag.\n" //
				+ "Log entries have different formats, each is described by one of the below JSON schema.\n" //
				+ "\n" //
				+ JsonSchema.getJsonSchema(ApiCallEntry.class) + "\n" //
				+ JsonSchema.getJsonSchema(DiaryEntry.class) + "\n" //
				+ JsonSchema.getJsonSchema(InteractionEntry.class) + "\n" //
				+ JsonSchema.getJsonSchema(PaymentEntry.class) + "\n" //
				+ JsonSchema.getJsonSchema(EmailEntry.class) + "\n" //
				+ JsonSchema.getJsonSchema(UploadEntry.class) + "\n" //
				+ "\n" //
				+ "Finally, you will be provided with a success criteria, inside a <criteria> tag.\n" //
				+ "\n" //
				+ "\n" //
				+ "# Instructions\n" //
				+ "\n" //
				+ "Your task is to carefully read the steps and log entries provided to you and determine if the corresponding success criteria was met.\n" //
				+ "  * When evaluating success criteria, evaluate each point separately, think though carefully whether that point was actually addressed based only on the evidence you have.\n" //
				+ "  * When evaluating success criteria, strictly base your results only on the content of the steps and the log. For example, do not infer that a payment was made, rather check if the payment was logged.\n" //
				+ "  * Your task is not to evaluate if the agent worked properly, rather to check if each and all the points in the success criteria are satisfied.\n" //
				+ "  * Your task is not to evaluate if the pseudo code was followed diligently by the agent; just check if each and all the points in the success criteria are satisfied.\n" //
				+ "  * Failure to fulfill a single point in the success criteria, means the whole success criteria were **NOT** met; in this case success **MUST** be false in your output.\n" //
				+ "  * When outputting your rationale, address each point in the success criteria individually\n" //
				+ "  * **STRICTLY** Use the below format when outputting your results:\n" //
				+ "\n" //
				+ JsonSchema.getJsonSchema(Response.class));
	}

	private final static String INPUT_TEMPLATE = "<steps>\n" //
			+ "{{steps}}\n" //
			+ "</steps>\n" //
			+ "\n" //
			+ "<log>\n" //
			+ "{{log}}\n" //
			+ "</log>\n" //
			+ "\n" //
			+ "<criteria>\n" //
			+ "{{criteria}}\n" //
			+ "</criteria>";

	public Response check(@NonNull ExecutionContext log, @NonNull List<Step> steps, @NonNull String criteria)
			throws JsonProcessingException {
		return check(log.getLogEntries(), steps, criteria);
	}

	public Response check(@NonNull List<? extends ExecutionContext.LogEntry> logEntries,
			@NonNull List<? extends Step> steps, @NonNull String criteria) throws JsonProcessingException {

		Map<String, String> map = new HashMap<>();
		map.put("steps", JsonSchema.JSON_MAPPER.writerWithView(Step.Views.Compact.class).withDefaultPrettyPrinter()
				.writeValueAsString(steps));
		map.put("log", JsonSchema.serialize(logEntries));
		map.put("criteria", JsonSchema.serialize(criteria));

		String prompt = Agent.fillSlots(INPUT_TEMPLATE, map);
		return complete(prompt).getObject(Response.class);
	}

	private static int countNestedSteps(List<? extends Step> steps) {
		int tot = 0;
		for (Step s : steps) {
			if (s instanceof ToolCallStep) {
				ToolCallStep tcs = (ToolCallStep) s;
				tot += (countNestedSteps(tcs.actionSteps) + 1);
			}
		}
		return tot;
	}

	/**
	 * Executes a single test returning its result.
	 * 
	 * @param endpoint
	 * @param runId
	 * @param outFolder
	 * @return
	 * @throws IOException
	 * @throws ToolInitializationException
	 */
	private static TestResult executeTest(String scenarioId, String runId, File outFolder) throws IOException {

		String model = "-";

		try {
			Orchestrator agent = new Orchestrator();
			TestMaster tester = new TestMaster();

			model = agent.getModel();
			String successCriteria = ScenarioComponent.getInstance().getSuccessCriteria(scenarioId);
			MDC.put("runId", runId); // Log per thread

			ExecutionContext ctx = new ExecutionContext(new DbConnector() {
				@Override
				public void addStep(String runId, Step step) { // Do nothing
				}
			}, scenarioId, runId);
			agent.execute(ctx);

			// Records output (API CALLS) to file
			File apiOutput = new File(outFolder, runId + "_calls.txt");
			writeFile(apiOutput, JsonSchema.JSON_MAPPER.writerWithDefaultPrettyPrinter()
					.writeValueAsString(agent.getExecutionContext().getLogEntries()));

			// Records output (STEPS) to file
			File agentOutput = new File(outFolder, runId + "_steps.txt");
			writeFile(agentOutput, JsonSchema.JSON_MAPPER.writerWithView(Step.Views.Compact.class)
					.withDefaultPrettyPrinter().writeValueAsString(agent.getSteps()));

			// Records output (STEPS) to file
			agentOutput = new File(outFolder, runId + "_steps_ALL.txt");
			writeFile(agentOutput,
					JsonSchema.JSON_MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(agent.getSteps()));

			Response resp = tester.check(ctx, new ArrayList<>(), successCriteria);
			System.err.println(runId + ": " + resp.success + " " + resp.confidenceLevel);
			return new TestResult(scenarioId, runId, resp, agent.getModel(), agent.getSteps(), null);
		} catch (Exception e) {
			LOG.error(e.getMessage(), e);
			return new TestResult(scenarioId, runId, null, model, new ArrayList<>(), e);
		}
	}

	/**
	 * Write text to given file, in UTF-8 encoding.
	 */
	private static void writeFile(@NonNull File file, @NonNull String text) throws IOException {
		try (BufferedWriter writer = new BufferedWriter(
				new OutputStreamWriter(new FileOutputStream(file), StandardCharsets.UTF_8))) {
			writer.write(text);
		}
	}

	public static void main(String[] args) {

		// Opens CSV file to collect results
		try {

			if (!OUTPUT_FOLDER.isDirectory() || !OUTPUT_FOLDER.canWrite())
				throw new IOException("Output folder not accessible");

			String testId = Long.toString(System.currentTimeMillis());
			File outFolder = new File(OUTPUT_FOLDER, "Test_" + testId);
			if (!outFolder.mkdirs())
				throw new IOException("Cannot create subfolders");

			// CSV file to log results
			File csvFile = new File(outFolder, testId + "-summary.csv");
			CSVFormat format = CSVFormat.DEFAULT.builder() //
					.setHeader(HEADERS) //
					.setSkipHeaderRecord(true) //
					.build();

			// Automatically create a log for each runId
			LoggerContext ctx = (LoggerContext) LoggerFactory.getILoggerFactory();
			SiftingAppender sift = new SiftingAppender();
			sift.setContext(ctx);
			MDCBasedDiscriminator disc = new MDCBasedDiscriminator();
			disc.setKey("runId");
			disc.setDefaultValue("unknown");
			disc.start();
			sift.setDiscriminator(disc);

			// each new runId creates its own FileAppender
			sift.setAppenderFactory((ctx1, runId) -> {
				PatternLayoutEncoder enc = new PatternLayoutEncoder();
				enc.setContext(ctx1);
				enc.setPattern("%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n");
				enc.start();

				FileAppender<ILoggingEvent> fa = new FileAppender<>();
				fa.setContext(ctx1);
				fa.setName("FILE-" + runId);
				File logOutput = new File(outFolder, runId + ".log");
				try {
					fa.setFile(logOutput.getCanonicalPath());
				} catch (IOException e) {
					throw new RuntimeException(e);
				}
				fa.setEncoder(enc);
				fa.start();

				return fa;
			});

			sift.start();
			ctx.getLogger("ROOT").addAppender(sift);

			try (BufferedWriter writer = new BufferedWriter(new FileWriter(csvFile, false));
					CSVPrinter csvPrinter = new CSVPrinter(writer, format)) {

				csvPrinter.printRecord(HEADERS);
				int successes = 0, failures = 0;
				ExecutorService executor = null;
				try {
					executor = Executors.newFixedThreadPool(NUM_THREADS);

					// Create tasks for parallel execution
					List<Callable<TestResult>> tasks = new ArrayList<>();
					for (String scenarioId : SCENARIOS) {
						for (int i = 1; i <= NUM_TEST; ++i) {
							String runId = scenarioId + String.format("-%04d", i);
							tasks.add(() -> executeTest(scenarioId, runId, outFolder));
						}
					}

					// Parallel execution
					List<Future<TestResult>> results = executor.invokeAll(tasks);

					// Read Results
					for (Future<TestResult> result : results) {
						Response resp = result.get().getResult();
						String scenarioId = result.get().getScenarioId();
						String runId = result.get().getRunId();
						String model = result.get().getModel();
						List<Step> steps = result.get().getSteps();

						if (resp == null) {
							// Critical Error
							csvPrinter.printRecord(scenarioId, runId, model,
									"Critical error: " + result.get().getError().getMessage());
							continue;
						}

						// Output execution statistics
						boolean succeeded = (resp.success && ((resp.confidenceLevel == Response.Level.VERY_HIGH)
								|| (resp.confidenceLevel == Response.Level.HIGH)));
						csvPrinter.printRecord(scenarioId, runId, model, steps.size() - 2, countNestedSteps(steps),
								resp.success, resp.confidenceLevel, succeeded, resp.rationale);
						csvPrinter.flush();
						if (succeeded)
							++successes;
						else
							++failures;
					}
				} finally {
					if (executor != null)
						executor.shutdown();
				}

				// Output summary
				csvPrinter.printRecord("Success:", successes);
				csvPrinter.printRecord("Failure:", failures);
				csvPrinter.printRecord("Accuracy:",
						(failures == 0 ? 1d : ((double) successes) / (successes + failures)));
			}
		} catch (Exception e) {
			e.printStackTrace(System.err);
		}
	}
}
