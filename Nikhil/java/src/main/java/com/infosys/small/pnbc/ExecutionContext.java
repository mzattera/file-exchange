/**
 * 
 */
package com.infosys.small.pnbc;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.pnbc.Peace.Person;
import com.infosys.small.pnbc.Peace.Task;
import com.infosys.small.react.ReactAgent.Step;
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDescription;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import lombok.ToString;

/**
 * This stores the execution context, that is all scenario data in the
 * simulation layer that can change during execution. In addition, it allows
 * logging information during the execution of a process that can then be used
 * for debug and testing.
 */
@RequiredArgsConstructor
public class ExecutionContext {

	/**
	 * This is a placeholder for integrating with the database and storing steps.
	 */
	public static abstract class DbConnector {

		/**
		 * Saves one execution step for the given run in the Database.
		 * 
		 * @param runId Unique ID for the current run.
		 * @param step  Step to save.
		 */
		public abstract void addStep(String runId, Step step);
	}

	@Getter
	@Setter
	@AllArgsConstructor(access = AccessLevel.PROTECTED)
	@ToString
	public abstract static class LogEntry {

		public enum Type {
			API_CALL, PAYMENT, DIARY_ENTRY, INTERACTION, EMAIL, UPLOAD
		}

		@JsonProperty(required = true)
		@JsonPropertyDescription("Type of entry.")
		public @NonNull Type type;
	}

	@Getter
	@Setter
	@JsonSchemaDescription("This is the schema for log entries with type==API_CALL; these entries represents tool calls the agent performed.")
	public static class ApiCallEntry extends LogEntry {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Simulated scenario (for testing purposes).")
		private @NonNull String scenarioId;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique ID of a tool being invoked by the agent.")
		private @NonNull String toolId;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Parameters passed to the tool.")
		private @NonNull Map<String, Object> args;

		public ApiCallEntry(@NonNull String scenarioId, @NonNull String toolId, @NonNull Map<String, Object> args) {
			super(Type.API_CALL);
			this.scenarioId = scenarioId;
			this.toolId = toolId;
			this.args = new HashMap<>(args);
		}

		@Override
		public String toString() {
			StringBuilder sb = new StringBuilder();
			sb.append(">>> API CALL LOGGED > ").append(scenarioId).append(": ").append(toolId).append("(");
			for (Entry<String, Object> e : args.entrySet()) {
				Object value = e.getValue();
				sb.append(e.getKey()).append("=\"").append(value == null ? "null" : value.toString()).append("\" ");
			}
			sb.append(")");

			return sb.toString();
		}
	}

	@Getter
	@Setter
	@JsonSchemaDescription("This is the schema for log entries with type==DIARY_ENTRY; these are notes registering relevant informations or events for auditing purposes.")
	public static class DiaryEntry extends LogEntry {

		@JsonProperty(required = true)
		@JsonPropertyDescription("The time when the task associated to this entry was created; together with customer number this uniquely identifies a task..")
		public @NonNull String taskTimeCreated;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The customer number for the task associated to this entry; together with creation time this uniquely identifies a task.")
		public @NonNull String taskCustomerNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The category associated to the diary entry.")
		public String category;
		public @NonNull String message;

		public DiaryEntry(@NonNull String taskTimeCreated, @NonNull String taskCustomerNumber, @NonNull String category,
				@NonNull String message) {

			super(Type.DIARY_ENTRY);
			this.taskTimeCreated = taskTimeCreated;
			this.taskCustomerNumber = taskCustomerNumber;
			this.category = category;
			this.message = message;
		}

		@Override
		public String toString() {
			StringBuilder sb = new StringBuilder();
			sb.append(">>> DIARY ENTRY LOGGED > For task ").append(taskCustomerNumber).append(" - ")
					.append(taskTimeCreated).append("\n");
			sb.append("    [").append(category).append("] ").append(message);
			return sb.toString();
		}
	}

	@Getter
	@Setter
	@JsonSchemaDescription("This is the schema for log entries with type==EMAL; these register emails sent out to clients or other entities.")
	public static class EmailEntry extends LogEntry {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Recipient of the email; this can be an email address, a person's name, or a unique customer number, among other things.")
		public String recipient;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The message that you need to send.")
		public String message;

		public EmailEntry(@NonNull String customerNumber, @NonNull String message) {

			super(Type.EMAIL);
			this.recipient = customerNumber;
			this.message = message;
		}

		@Override
		public String toString() {
			StringBuilder sb = new StringBuilder();
			sb.append(">>> OUTGOING EMAIL LOGGED >  To: ").append(message).append("\nContent: ").append(message);
			return sb.toString();
		}
	}

	@Getter
	@Setter
	@JsonSchemaDescription("This is the schema for log entries with type==INTERACTION; these register interactions with operations officer (human in the loop) where they are asked for information, checks, etc.)")
	public static class InteractionEntry extends LogEntry {

		@JsonProperty(required = true)
		@JsonPropertyDescription("A query or message sent to the operations officer (human in the loop).")
		public @NonNull String message;

		public InteractionEntry(@NonNull String message) {

			super(Type.INTERACTION);
			this.message = message;
		}

		@Override
		public String toString() {
			StringBuilder sb = new StringBuilder();
			sb.append(">>> INTERACTION LOGGED ").append(message);
			return sb.toString();
		}
	}

	@Getter
	@Setter
	@JsonSchemaDescription("This is the schema for log entries with type==PAYMENT; these entries instruct the Operations Officer to issue a payment.")
	public static class PaymentEntry extends LogEntry {

		@JsonProperty(required = true)
		@JsonPropertyDescription("An amount that the Operations Officer (human in the loop)was requested to pay.")
		public @NonNull String amount;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Payment details for the operations officer (human in the loop).")
		public @NonNull String message;

		public PaymentEntry(@NonNull String amount, @NonNull String message) {

			super(Type.PAYMENT);
			this.amount = amount;
			this.message = message;
		}

		@Override
		public String toString() {
			StringBuilder sb = new StringBuilder();
			sb.append(">>> PAYMENT LOGGED > Amount: ").append(amount).append(" -> ").append(message);
			return sb.toString();
		}
	}

	@Getter
	@Setter
	@JsonSchemaDescription("This is the schema for log entries with type==UPLOAD; these entries logs a file upload in any system.")
	public static class UploadEntry extends LogEntry {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique customer number for the estate this dcoument refers to.")
		public @NonNull String customerNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Type of document being uploaded.")
		public @NonNull String documentType;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The content of the document being uploaded.")
		public @NonNull String content;

		public UploadEntry(@NonNull String customerNumber, @NonNull String documentType, @NonNull String content) {
			super(Type.UPLOAD);
			this.customerNumber = customerNumber;
			this.documentType = documentType;
			this.content = content;
		}

		@Override
		public String toString() {
			StringBuilder sb = new StringBuilder();
			sb.append(">>> ").append(documentType).append(" FILE UPLOADED > for client ").append(customerNumber)
					.append(" CONTENT -> ").append(content);
			return sb.toString();
		}
	}

	/**
	 * Connector to the database (for storing execution state).
	 */
	@Getter
	private final DbConnector db;

	/**
	 * Unique ID for the scenario we are running.
	 */
	@Getter
	private final String scenarioId;

	/**
	 * Unique ID for the current run.
	 */
	@Getter
	private final String runId;

	/**
	 * List of unassigned tasks; it contains ALL unassigned tasks (non filtered).
	 */
	@Getter
	@Setter
	private List<Task> unassignedTasks = null;

	/**
	 * List of tasks assigned to operator 42.
	 */
	@Getter
	@Setter
	private List<Task> operatorTasks = new ArrayList<>();

	/** All persons related to the estate, by their Customer Number. */
	@Getter
	@Setter
	private Map<String, Person> relatedPersons = null;

	/** Proforma Document, if provided, by customer number. */
	@Getter
	private final Map<String, String> proformaDocument = new HashMap<>();

	/** SKS (Probate document), if provided, by customer number. */
	@Getter
	private final Map<String, String> SKS = new HashMap<>();

	/** Power of Attorney document, if provided by customer number. */
	@Getter
	private final Map<String, String> PoA = new HashMap<>();

	/** List of log entries. */
	@Getter
	private List<LogEntry> logEntries = new ArrayList<>();

	public void log(@NonNull LogEntry entry) {
		logEntries.add(entry);
		System.err.println(entry.toString());
	}

	/**
	 * Logs an API call.
	 */
	public void log(@NonNull String scenarioId, @NonNull String toolId, @NonNull Map<String, Object> args) {
		log(new ApiCallEntry(scenarioId, toolId, args));
	}

	/**
	 * Logs a diary entry.
	 */
	public void log(@NonNull String taskTimeCreated, @NonNull String taskCustomerNumber, @NonNull String category,
			@NonNull String message) {
		log(new DiaryEntry(taskTimeCreated, taskCustomerNumber, category, message));
	}

	/**
	 * Logs an interaction with the client.
	 */
	public void log(@NonNull String message) {
		log(new InteractionEntry(message));
	}

	/**
	 * Logs a payment.
	 */
	public void log(@NonNull String amount, @NonNull String message) {
		log(new PaymentEntry(amount, message));
	}

	public void clearLog() {
		logEntries.clear();
	}

	public static List<Task> filterTasks(List<Task> tasks, String filterBy, String filterValue, String customerNumber) {
		Stream<Task> stream = tasks.stream();

		// Always filter by customerNumber if provided
		if (customerNumber != null && !customerNumber.isEmpty()) {
			stream = stream.filter(task -> customerNumber.equals(task.customerNumber));
		}

		// Optionally filter by any other column (by JSON name)
		if (filterBy != null && !filterBy.isEmpty() && filterValue != null && !filterValue.isEmpty()) {

			// Find the field in Task with matching @JsonProperty value
			Field matchedField = Arrays.stream(Task.class.getDeclaredFields()).filter(f -> {
				JsonProperty ann = f.getAnnotation(JsonProperty.class);
				return ann != null && filterBy.equals(ann.value());
			}).findFirst().orElse(null);

			if (matchedField != null) {
				matchedField.setAccessible(true);
				stream = stream.filter(task -> {
					try {
						Object value = matchedField.get(task);
						return filterValue.equals(value != null ? value.toString() : null);
					} catch (IllegalAccessException e) {
						// Ignore and skip this filter if reflection fails
						return false;
					}
				});
			}
		}

		return stream.collect(Collectors.toList());
	}
}
