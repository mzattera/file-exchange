package com.infosys.small.pnbc;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.fasterxml.jackson.core.type.TypeReference;
import com.infosys.small.core.JsonSchema;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.react.ReactAgent;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.NonNull;
import lombok.Setter;

/**
 * Backend-system wrapper for PEACE.
 */
public class Peace extends LabAgent {

	/** A Task in PEACE */
	@NoArgsConstructor
	@Getter
	@Setter
	public static class Task {

		@JsonProperty(value = "Step Name", required = true)
		@JsonPropertyDescription("The name of the step or activity.")
		public @NonNull String stepName;

		@JsonProperty("Due Date")
		@JsonPropertyDescription("Task due date \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").")
		public String dueDate;

		@JsonProperty(value = "Time Created", required = true)
		@JsonPropertyDescription("Time when the task was created \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\"); together with Customer Number this uniquely defines a task.")
		public @NonNull String timeCreated;

		@JsonProperty(value = "Customer Number", required = true)
		@JsonPropertyDescription("Unique customer number for the client (estate),")
		public @NonNull String customerNumber;

		@JsonProperty(value = "Customer Name", required = true)
		@JsonPropertyDescription("The name of the customer associated with the task.")
		public @NonNull String customerName;

		// Private constructor to enforce use of the builder
		private Task(Builder builder) {
			this.stepName = Objects.requireNonNull(builder.stepName, "stepName must not be null");
			this.dueDate = builder.dueDate;
			this.timeCreated = Objects.requireNonNull(builder.timeCreated, "timeCreated must not be null");
			this.customerNumber = Objects.requireNonNull(builder.customerNumber, "customerNumber must not be null");
			this.customerName = Objects.requireNonNull(builder.customerName, "customerName must not be null");
		}

		/**
		 * Builder for Task.
		 */
		public static class Builder {
			private String stepName;
			private String dueDate;
			private String timeCreated;
			private String customerNumber;
			private String customerName;

			public Builder stepName(@NonNull String stepName) {
				this.stepName = stepName;
				return this;
			}

			public Builder dueDate(String dueDate) {
				this.dueDate = dueDate;
				return this;
			}

			public Builder timeCreated(@NonNull String timeCreated) {
				this.timeCreated = timeCreated;
				return this;
			}

			public Builder customerNumber(@NonNull String customerNumber) {
				this.customerNumber = customerNumber;
				return this;
			}

			public Builder customerName(@NonNull String customerName) {
				this.customerName = customerName;
				return this;
			}

			public Task build() {
				return new Task(this);
			}
		}
	}

	/* ---------- API DEFINITIONS ---------- */

	// We manage the list of unassigned tasks, since APIs should return different
	// values, based on what has been assigned.

	/** Returns a list of unassigned tasks (optionally filtered). */
	public static class GetUnassignedTasksApi extends Api {

		public static class Parameters extends ReactAgent.Parameters {
			@JsonPropertyDescription("Optional column name to use when filtering tasks. This must match one of task field names, e.g. \"Step Name\" not \"stepName\".")
			public String filterBy;

			@JsonPropertyDescription("Value to use when filtering, if filterBy is provided.")
			public String filterValue;

			@JsonPropertyDescription("If this is provided, only tasks for this client will be returned.")
			public String customerNumber;
		}

		public GetUnassignedTasksApi() {
			super("getUnassignedTasks",
					"Returns a list of unassigned tasks, accordingly to provided filtering criteria.",
					Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			if (!isInitialized()) {
				throw new IllegalArgumentException("Tool must be initialized.");
			}

			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools
			String scenario = getLabAgent().getScenarioId();
			if (log)
				getLabAgent().getExecutionContext().log(scenario, call.getTool().getId(), args);

			if (getExecutionContext().getUnassignedTasks() == null) {
				// This is the first time we call this API; let's get initial list from scenario
				String tasks = ScenarioComponent.getInstance().get( //
						scenario, //
						getId(), //
						new HashMap<>());
				getExecutionContext().setUnassignedTasks(
						new ArrayList<>(JsonSchema.JSON_MAPPER.readValue(tasks, new TypeReference<List<Task>>() {
						})));
			}

			String filterBy = getString("filterBy", call.getArguments(), null);
			String filterValue = getString("filterValue", call.getArguments(), null);
			if ((filterBy != null) && (filterValue == null)) {
				throw new IllegalArgumentException("Must provide a filter value for filter=" + filterBy);
			}
			String customerNumber = getString("customerNumber", call.getArguments(), null);

			return new ToolCallResult(call, JsonSchema.JSON_MAPPER.writeValueAsString(ExecutionContext
					.filterTasks(getExecutionContext().getUnassignedTasks(), filterBy, filterValue, customerNumber)));
		}
	}

	/** Assigns the task matching the identifiers to an operator. */
	public static class AssignTaskApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Time the task was created. Use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").")
			public String timeCreated;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number of the estate.")
			public String customerNumber;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Identifier of the operator receiving the task. Always use 42.")
			public String operatorId;
		}

		public AssignTaskApi() {
			super("assignTask",
					"Assigns the task identified by timeCreated and customerNumber to the operator with operatorId. ",
					Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			if (!isInitialized()) {
				throw new IllegalArgumentException("Tool must be initialized.");
			}

			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools
			String scenario = getLabAgent().getScenarioId();
			if (true) // Always log
				getLabAgent().getExecutionContext().log(scenario, call.getTool().getId(), args);

			String timeCreated = getString("timeCreated", call.getArguments());
			String customerNumber = getString("customerNumber", call.getArguments());
			String operatorId = getString("operatorId", call.getArguments());
			if (!"42".equals(operatorId))
				return new ToolCallResult(call,
						"ERROR: You are trying to assign task to an operator other than yourself.");

			if (getExecutionContext().getUnassignedTasks() == null) {
				return new ToolCallResult(call, "ERROR: No task with timeCreated=" + timeCreated
						+ " and customerNumber=" + customerNumber + " exists.");
			}

			for (int i = 0; i < getExecutionContext().getOperatorTasks().size(); ++i) {
				Task t = getExecutionContext().getOperatorTasks().get(i);
				if (t.timeCreated.equals(timeCreated) && t.customerNumber.equals(customerNumber)) {
					return new ToolCallResult(call, "ERROR: Task with timeCreated=" + timeCreated
							+ " and customerNumber=" + customerNumber + " is already assigned to operator ID=42");
				}
			}

			for (int i = 0; i < getExecutionContext().getUnassignedTasks().size(); ++i) {
				Task t = getExecutionContext().getUnassignedTasks().get(i);
				if (t.timeCreated.equals(timeCreated) && t.customerNumber.equals(customerNumber)) {
					getExecutionContext().getUnassignedTasks().remove(i);
					getExecutionContext().getOperatorTasks().add(t);

					return new ToolCallResult(call, "Task with timeCreated=" + timeCreated + " and customerNumber="
							+ customerNumber + " has been successfully assigned to operator " + operatorId);
				}
			}

			return new ToolCallResult(call, "ERROR: No task with timeCreated=" + timeCreated + " and customerNumber="
					+ customerNumber + " exists.");
		}
	}

	/** Retrieves all tasks assigned to a specific operator. */
	public static class GetMyTasksApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Identifier of the operator whose task list is requested. Always use 42.")
			public String operatorId;
		}

		public GetMyTasksApi() {
			super("getMyTasks", "Returns the list of tasks assigned to the given operator.", Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			if (!isInitialized()) {
				throw new IllegalArgumentException("Tool must be initialized.");
			}

			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools
			String scenario = getLabAgent().getScenarioId();
			if (log)
				getLabAgent().getExecutionContext().log(scenario, call.getTool().getId(), args);

			if (!"42".equals(getString("operatorId", args)))
				return new ToolCallResult(call, "[]"); // empty list

			return new ToolCallResult(call,
					JsonSchema.JSON_MAPPER.writeValueAsString(getExecutionContext().getOperatorTasks()));
		}
	}

	/** Closes a task and marks it completed. */
	public static class CloseTaskApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Time the task was created. Use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").")
			public String timeCreated;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number of the estate.")
			public String customerNumber;
		}

		public CloseTaskApi() {
			super("closeTask", "Closes a task and marks it as completed.", Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools

			String timeCreated = getString("timeCreated", args);
			String customerNumber = getString("customerNumber", args);
			for (int i = 0; i < getExecutionContext().getOperatorTasks().size(); ++i) {
				Task t = getExecutionContext().getOperatorTasks().get(i);
				if (t.timeCreated.equals(timeCreated) && t.customerNumber.equals(customerNumber)) {

					getLabAgent().getExecutionContext().log( // Always log
							getLabAgent().getScenarioId(), //
							this.getId(), //
							args);

					getExecutionContext().getOperatorTasks().remove(i); // Remove closed task

					return new ToolCallResult(call, "Task with timeCreated=" + timeCreated + " and customerNumber="
							+ customerNumber + " has been successfully closed.");
				}
			}

			return new ToolCallResult(call, "ERROR: Task with timeCreated=" + timeCreated + " and customerNumber="
					+ customerNumber + " does not exist or has not been assigned to you");
		}
	}

	/** Returns the content (text and attachment IDs) of the specified task. */
	public static class GetTaskContentApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Time the task was created. Use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").")
			public String timeCreated;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number of the estate.")
			public String customerNumber;
		}

		public GetTaskContentApi() {
			super("getTaskContent", "Gets the content of the specified task, including attachment IDs.",
					Parameters.class);
		}
	}

	/** Retrieves the textual content of an attached file. */
	public static class GetFileContentApi extends Api {
		public final static String ID = "getFileContent";

		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			public String fileName;
		}

		public GetFileContentApi() {
			super(ID, "Returns the content of a file attached to task.", Parameters.class);
		}
	}

	/** Fetches all diary entries attached to a task. */
	public static class GetDiaryEntriesApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Time the task was created. Use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").")
			public String timeCreated;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number of the estate.")
			public String customerNumber;
		}

		public GetDiaryEntriesApi() {
			super("getDiaryEntries", "Returns the list of diary entries for the specified task. "
					+ " As it is not possible to have all entries for a client or operator, this must be called repeatedly for each task of interest.",
					Parameters.class);
		}
	}

	/** Appends a message to a task diary, optionally in a category. */
	public static class UpdateDiaryApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Time the task was created. Use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").")
			public String timeCreated;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number of the estate the task refers to.")
			public String customerNumber;

			@JsonPropertyDescription("Optional category used to group diary messages.")
			public String category;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Text of the message.")
			public String message;
		}

		public UpdateDiaryApi() {
			super("updateDiary", "Adds a message to the diary of the specified task.", Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools

			String category = getString("category", args);
			if (!List
					.of("Proforma's Balance", "Paid bill", "Sent email asking for SKS", "SKS registered",
							"PoA uploaded in CF", "Created netbank to CPR", "Info email sent", "Transferred udlaeg")
					.contains(category))
				return new ToolCallResult(call, "Error: category for the message was not provided or not supported.");

			String timeCreated = getString("timeCreated", args, "null");
			String customerNumber = getString("customerNumber", args, "null");
			List<Task> task = ExecutionContext.filterTasks(getExecutionContext().getOperatorTasks(), "Time Created",
					timeCreated, customerNumber);
			if (task.size() != 1)
				return new ToolCallResult(call, "ERROR: No assigned task with Time Created = " + timeCreated
						+ " for Customer Number = " + customerNumber);

			getLabAgent().getExecutionContext().log( // Always log
					timeCreated, //
					customerNumber, //
					category, //
					getString("message", args) + "\n\nSincerely, Operator ID=42\n" + java.time.LocalDateTime.now()
							.format(java.time.format.DateTimeFormatter.ofPattern("MMM. d'th', yyyy HH:mm")) + "\n");

			return new ToolCallResult(call, "Diary was updated successfully with given message.");
		}
	}

	/** Data for one person */
	@NoArgsConstructor
	@Getter
	@Setter
	public static class Person {

		@JsonProperty(value = "Customer Number", required = true)
		@JsonPropertyDescription("Unique string identifier with customer number (CPR) of the customer. Customers are uniquely defined by this field.")
		public @NonNull String customerNumber;

		@JsonProperty(value = "Relation To Estate", required = true)
		@JsonPropertyDescription("The relation between this person and their related estate. Possible values are: \"Lawyer\", \"Other\",\"Power of attorney\",\"Heir\",\"Guardian/værge\",\"Guardian/skifteværge\",\"Beneficiary\",\"Spouse\",\"Cohabitee\",\"One man company\",\"I/S\",\"K/S\",\"Joint\",\"Deceased\".")
		public @NonNull String relationToEstate;

		@JsonProperty(value = "Name", required = true)
		@JsonPropertyDescription("Client first and last name.")
		public @NonNull String name;

		@JsonProperty(value = "Identification Completed", required = true)
		@JsonPropertyDescription("An indicator whether the person has been identified and how. Possible values are: \"None\",\"OK – Customer\",\"OK – Non Customer\",\"OK – Professionals\",\"Awaiting\",\"Not relevant\"; this field can be updated if and only if instructed by the user and only after identification has been performed by an Operations Officer.")
		public String identificationCompleted;

		@JsonProperty(value = "Power Of Attorney Type", required = true)
		@JsonPropertyDescription("The person might have a power of attorney on the estate's assets; this fields describes it. Possible values are: \"Alone\" when only this person has power of attorney, \"Joint\" when power of attorney is shared between this person and another individual, \"None\" in  all other cases.")
		public @NonNull String powerOfAttorneyType;

		@JsonProperty(value = "Address", required = true)
		@JsonPropertyDescription("The person's full address.")
		public @NonNull String address;

		@JsonProperty(value = "Email", required = true)
		@JsonPropertyDescription("The person's email.")
		public @NonNull String email;

		@JsonProperty(value = "Phone Number", required = true)
		@JsonPropertyDescription("The person's phone number.")
		public @NonNull String phoneNumber;
	}

	/** Retrieves the people related to an estate. */
	public static class GetRelatedPersonsApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number of the estate.")
			public String customerNumber;
		}

		public GetRelatedPersonsApi() {
			super("getRelatedPersons",
					"Returns the list of persons related to the given estate. Notice that the Customer Number returned by this tool is the unique Customer Number of the related person, not the estate's Customer number.",
					Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			if (!isInitialized()) {
				throw new IllegalArgumentException("Tool must be initialized.");
			}

			if (getExecutionContext().getRelatedPersons() != null) {
				// List has been already initialised

				Map<String, Object> args = new HashMap<>(call.getArguments());
				args.remove("thought"); // As we are passing it, we must remove or it won't match tools
				String scenario = getLabAgent().getScenarioId();
				if (log)
					getLabAgent().getExecutionContext().log(scenario, call.getTool().getId(), args);

				return new ToolCallResult(call,
						JsonSchema.JSON_MAPPER.writeValueAsString(getExecutionContext().getRelatedPersons().values()));
			}

			// First invocation
			ToolCallResult persons = super.invoke(call, log);
			if (persons.getResult().toString().contains("ERROR")) {
				return persons;
			}
			List<Person> l = new ArrayList<>(
					JsonSchema.JSON_MAPPER.readValue(persons.getResult().toString(), new TypeReference<List<Person>>() {
					}));
			getExecutionContext().setRelatedPersons(new HashMap<>(l.size()));
			for (Person p : l)
				getExecutionContext().getRelatedPersons().put(p.customerNumber, p);

			return new ToolCallResult(call, JsonSchema.JSON_MAPPER.writeValueAsString(l));
		}
	}

	/** Updates information for a single related person. */
	public static class UpdatePersonDataApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number of the customer to update.")
			public String customerNumber;

			@JsonPropertyDescription("The relation between this person and their related estate. Possible values are: \"Lawyer\", \"Other\",\"Power of attorney\",\"Heir\",\"Guardian/værge\",\"Guardian/skifteværge\",\"Beneficiary\",\"Spouse\",\"Cohabitee\",\"One man company\",\"I/S\",\"K/S\",\"Joint\",\"Deceased\". Translate any other value provided in a different language before calling this tool.")
			public String relationToEstate;

			@JsonPropertyDescription("The person's name.")
			public String name;

			@JsonPropertyDescription("An indicator whether the person has been identified and how. Possible values are: \"None\",\"OK – Customer\",\"OK – Non Customer\",\"OK – Professionals\",\"Awaiting\",\"Not relevant\". Translate any other value provided in a different language before calling this tool.")
			public String identificationCompleted;

			@JsonPropertyDescription("The person might have a power of attorney on the estate's assets; this fields describes it. Possible values are: \"Alone\" when only this person has power of attorney, \"Joint\" when power of attorney is shared between this person and another individual, \"None\" in  all other cases. Translate any other value provided in a different language before calling this tool.")
			public String powerOfAttorneyType;

			@JsonPropertyDescription("The person's home address.")
			public String address;

			@JsonPropertyDescription("The person's email address.")
			public String email;

			@JsonPropertyDescription("The person's phone number.")
			public String phoneNumber;
		}

		public UpdatePersonDataApi() {
			super("updatePersonData",
					"Updates data for a related person of the estate. Do *NOT* use this to read person's data. "
							+ "Only fields that are not null are updated; other fields values remain unchanged.",
					Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			if (!isInitialized()) {
				throw new IllegalArgumentException("Tool must be initialized.");
			}

			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools
			String scenario = getLabAgent().getScenarioId();
			if (true) // Always log updates
				getLabAgent().getExecutionContext().log(scenario, call.getTool().getId(), args);

			String customerNumber = getString("customerNumber", args, "null");
			Person person = getExecutionContext().getRelatedPersons().get(customerNumber);
			// TODO URGENT, related persons might not have been called already....unlikely
			// but....
			if (person == null)
				return new ToolCallResult(call,
						"ERROR: Cannot update non-existing customer with Customer Number=" + customerNumber);

			if (args.containsKey("relationToEstate")) {
				String value = (String) args.get("relationToEstate");
				if (value != null && !value.isEmpty()) {
					person.setRelationToEstate(value);
				}
			}
			if (args.containsKey("name")) {
				String value = (String) args.get("name");
				if (value != null && !value.isEmpty()) {
					person.setName(value);
				}
			}
			if (args.containsKey("identificationCompleted")) {
				String value = (String) args.get("identificationCompleted");
				if (value != null && !value.isEmpty()) {
					person.setIdentificationCompleted(value);
				}
			}
			if (args.containsKey("powerOfAttorneyType")) {
				String value = (String) args.get("powerOfAttorneyType");
				if (value != null && !value.isEmpty()) {
					person.setPowerOfAttorneyType(value);
				}
			}
			if (args.containsKey("address")) {
				String value = (String) args.get("address");
				if (value != null && !value.isEmpty()) {
					person.setAddress(value);
				}
			}
			if (args.containsKey("email")) {
				String value = (String) args.get("email");
				if (value != null && !value.isEmpty()) {
					person.setEmail(value);
				}
			}
			if (args.containsKey("phoneNumber")) {
				String value = (String) args.get("phoneNumber");
				if (value != null && !value.isEmpty()) {
					person.setPhoneNumber(value);
				}
			}

			return new ToolCallResult(call,
					"Data for Customer Number=" + customerNumber + " have been updated successfully.");
		}
	}

	/* ---------- CONSTRUCTOR ---------- */

	public Peace() {
		super("PEACE",
				"This tool is used to manage process tasks, each task being uniquely identified by the combination of 'Time Created' and 'Client Number'; "
						+ "this includes assigning tasks to an operator and marking tasks closed, and managing task attachments. " //
						+ "It can also be used to retrieve conent of files attached to tasks. " //
						+ "It also stores a diary used to log specific task steps and their outcomes; notice diaries are associated to tasks, so they can be retrieved only through a task. "
						+ "It can create diary entries but only one at a time and for a specific task. "
						+ "The diary is not to be used for normal communication, it must be used only when mandated by a business process. " //
						+ "It also contains personal data for estates and their related persons, both identified by their unique customer numbers; " //
						+ "however, this tool has no access to people's accounts; **STRICTLY** do not use this tool to check if a person has an account or other relationship with the bank. ", //
				List.of( //
						new GetUnassignedTasksApi(), //
						new AssignTaskApi(), //
						new GetMyTasksApi(), //
						new CloseTaskApi(), //
						new GetTaskContentApi(), //
						new GetFileContentApi(), //
						new GetDiaryEntriesApi(), //
						new UpdateDiaryApi(), //
						new GetRelatedPersonsApi(), //
						new UpdatePersonDataApi() //
				));

		setContext(
				"  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, \"Customer Number\" is sometimes indicated as \"afdøde CPR\" or \"CPR\" in documents.\n"
						+ "  * Probate Certificate is a document that lists heirs for one estate; it is sometime indicated as \"SKS\".\n"
						+ "  * Power of Attorney document (PoA) is a document that define people's legal rights over the estate's asset. It is sometime indicated as \"PoA\".\n"
						+ "  * Proforma Document is a document containing the amount of cash available on estate's account at the time of their death.\n"
						+ "  * Probate Court (Skifteretten) Notification Letter is an official letter from Skifteretten informing the heirs about the opening of an estate after a person’s death; this is **NOT** same as SKS, even it might notify heirs that SKS has been issued.\n"
//						+ "  * When asked to determine the type of a file, use the above document types if and only if any matches, if none of the above document type matches, check if the file can be categorised as a bill/invoice; if not, return a short description of the document contents and the best definition of its type you can come up with.\n"
						+ "  * When asked to determine the type of an attachment, don't simply provide the file name but try to infer its type and provide a short summary of contents.\n"

						+ "  * To indicate time stamps, always use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").\n"
						+ "  * For amounts, always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\")."

						+ "  * Tasks are described by the below JSON schema:\n" //
						+ JsonSchema.getJsonSchema(Task.class) + "\n" //
						+ "  * Payment tasks are identified by having Step Name=\"Handle Account 1\".\n"
						+ "  * When asked to provide the content of a task or an attachment, **STRICTLY** provide the complete content without performing any summarisation, unless explicitly requested by the user.\n"
						+ "  * Do not make any assumption about format (e.g. image, audio,etc.) or nature (e.g. scanned document) of files or attachments; just use the proper tool to provide content of files when required to do so.\n"

						// TODO URGENT This is necessary because assigning tasks does not change the
						// list of unassigned tasks.
						// TODO URGENT Add logic to return variable results.
//						+ "  * Once you have assigned tasks to an operator without receiving an error message from \"assignTask\" tool, there is no need to verify if tasks where assigned correctly or if there are more tasks to assign; " //
//						+ "strictly **DO NOT** verify if all unassigned tasks have been assigned, or if more unassigned tasks remains after you called \"assignTask\" tool.\n" //

						+ "  * Data about persons related to estates are described by the below JSON schema: "
						+ "**STRICTLY** when asked to provide people data, always follow this schema for your output:\n" //
						+ JsonSchema.getJsonSchema(Person.class) + "\n" //
						+ "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. Always provide the Customer Number if a tool needs to act on a specific person/client; indicate it as Customer Number and not CPR when passing it to tools.\n"
						+ "  * When asked to update person's data, you do not need to retrieve the full record for the person record; just updates the fields provided by the user ignoring others.\n"

						+ "  * When asked to check customers' accounts return an error stating that you do not have access to customer accounts..\n"

						+ "  * When writing diary entries you **MUST** use one of the following categories for the entry:\n"
						+ "         \"Proforma's Balance\" to record balance available in the Proforma Document.\n"
						+ "         \"Paid bill\": to record a payment that was made.\n"
						+ "         \"Transferred udlaeg\": to record a reimbursment/transfer that was made.\n"
						+ "         \"Info email sent\": to record that an email was sent to client after processing a task.\n"
						+ "         \"Sent email asking for SKS\": to record that an email was sent to client asking for missign SKS document.\n"
						+ "         \"SKS registered\": to record that SKS document was uploaded.\\n"
						+ "         \"PoA uploaded in CF\": to record that Power of Attorney document was uploaded.\n"
						+ "         \"Created netbank to CPR\": to record that accounts for one estate have been unblocked.\n"
						+ "  * All entries in the diary should be in English.\n"
						+ "  * The diary is not to be used for communication with users; you must create entries in the diary only when required to do so.\n"
						+ "  * **STRICTLY** Never create diary entries, unless instructed by the user. Do not create entries to document activities you have done, unless instructed to do so.\n" //
		);

		setExamples("Input & Context:\n\n" //
				+ "<user_command>\nList all unassigned tasks with Step Name='Handle Account 1' for Customer Number 123\n</user_command>" //
				+ "\nCorrect Output:\n\n" //
				+ "Call \"getUnassignedTasks\" tool with following parameters: {\"customerNumber\":\"123\",\"filterBy\":\"Step Name\",\"filterValue\":\"Handle Account 1\"}, " //
				+ " then return the actual list of tasks.\n" //
				+ "\nIncorrect Output:\n\n" //
				+ "Call \"getUnassignedTasks\" tool with following parameters: {\"customerNumber\":\"123\",\"filterBy\":\"Step Name\",\"filterValue\":\"Handle Account 1\"}, " //
				+ " then return \"I have listed all unassigned tasks with Step Name='Handle Account 1' for Customer Number 123\".\n" //
				+ "\n---\n\n" //
				+ "Input & Context:\n\n" //
				+ "<user_command>\nAssign all remaining unassigned tasks with Step Name='Handle Account 1' for Customer Number 123 to myself (operator 42)\n</user_command>" //
				+ "\nCorrect Output:\n\n" //
				+ "Call \"getUnassignedTasks\" tool with following parameters: {\"customerNumber\":\"123\",\"filterBy\":\"Step Name\",\"filterValue\":\"Handle Account 1\"}, "
				+ "Then, for each task returned, call \"assignTask\" tool with following parameters: {\"customerNumber\":\"123\",\"timeCreated\":<creation time of task>,\"operatorId\":\"42\"}, "
				+ "\n---\n\n" //
				+ "Input & Context:\n\n" //
				+ "Your thought is: \"I have retrieved the current data for the client. All fields match the provided task data. No update is needed, so I will complete the process."
				+ "\nCorrect Output:\n\n" //
				+ "	{\n" //
				+ "	  \"status\" : \"COMPLETED\",\n" //
				+ "	  \"actor\" : <your ID here>,\n" //
				+ "	  \"thought\" : \"I have retrieved the current data for the client. All fields match the provided task data. No update is needed, so I will complete the process.\",\n" //
				+ "	  \"observation\" : \"Process has been completed.\",\n" //
				+ "	}\n" //
				+ "\nIncorrect Output:\n\n" //
				+ "Call \"updatePersonData\" tool." //
				+ "\n---\n\n" //
				+ "Input & Context:\n\n" //
				+ "<steps> contains the following steps:\n" //
				+ "[{\n" //
				+ "    \"status\" : \"IN_PROGRESS\",\n" //
				+ "    \"actor\" : <your ID here>,\n" //
				+ "    \"thought\" : \"I am starting execution of the below user's command in <user_command> tag.\\n\\n<user_command>\\nAssign all other unassigned tasks with Step Name = 'Handle Account 1' and Customer Number = 656565 to Operator ID 11.\\n</user_command>\",\n" //
				+ "    \"observation\" : \"Execution just started.\"\n" //
				+ "  }, {\n" //
				+ "    \"status\" : \"IN_PROGRESS\",\n" //
				+ "    \"actor\" : <your ID here>,\n" //
				+ "    \"thought\" : \"I need to retrieve all unassigned tasks with Step Name = 'Handle Account 1' and Customer Number = 656565 in order to assign them to Operator ID 11.\",\n" //
				+ "    \"observation\" : \"[{\\\"Step Name\\\":\\\"Handle Account 1\\\",\\\"Due Date\\\":\\\"4/23/2025, 3:00 PM\\\",\\\"Time Created\\\":\\\"4/16/2025, 3:00 PM\\\"}]\",\n" //
				+ "    \"action\" : \"The tool \\\"getUnassignedTasks\\\" has been called\",\n" //
				+ "    \"action_input\" : \"{\\\"filterBy\\\":\\\"Step Name\\\",\\\"filterValue\\\":\\\"Handle Account 1\\\",\\\"customerNumber\\\":\\\"656565\\\"}\",\n" //
				+ "    \"action_steps\" : [ ]\n" //
				+ "  }, {\n" //
				+ "    \"status\" : \"IN_PROGRESS\",\n" //
				+ "    \"actor\" : <your ID here>,\n" //
				+ "    \"thought\" : \"I have identified an unassigned task with Step Name = 'Handle Account 1' and Customer Number = 656565. I will assign this task to Operator ID 11 as requested.\",\n" //
				+ "    \"observation\" : \"Task with timeCreated=4/16/2025, 3:00 PM and customerNumber=656565 has been successfully assigned to operator 11\",\n" //
				+ "    \"action\" : \"The tool \\\"assignTask\\\" has been called\",\n" //
				+ "    \"action_input\" : \"{\\\"timeCreated\\\":\\\"4/16/2025, 3:00 PM\\\",\\\"customerNumber\\\":\\\"656565\\\",\\\"operatorId\\\":\\\"11\\\"}\",\n" //
				+ "    \"action_steps\" : [ ]\n" //
				+ "  }]\n" //
				+ "\nCorrect Output:\n\n" //
				+ "  {\n" //
				+ "    \"status\" : \"COMPLETED\",\n" //
				+ "    \"actor\" : <your ID here>,\n" //
				+ "    \"thought\" : \"I have assigned tasks with Step Name = 'Handle Account 1' and Customer Number = 656565to Operator ID 11 as requested.\",\n" //
				+ "    \"observation\" : \"All unassigned tasks with Step Name = 'Handle Account 1' and Customer Number = 656565 have been assigned to Operator ID 11. No further action is needed.\"\n" //
				+ "  }\n" //
				+ "\nIncorrect Output:\n\n" //
				+ "  {\n" //
				+ "    \"status\" : \"IN_PROGRESS\",\n" //
				+ "    \"actor\" : <your ID here>,\n" //
				+ "    \"thought\" : \"I need to verify if there are any remaining unassigned tasks with Step Name = 'Handle Account 1' and Customer Number = 656565, to ensure all such tasks are assigned to Operator ID 11.\",\n" //
				+ "    \"observation\" : \"[]\",\n" //
				+ "    \"action\" : \"The tool \\\"getUnassignedTasks\\\" has been called\",\n" //
				+ "    \"action_input\" : \"{\\\"filterBy\\\":\\\"Step Name\\\",\\\"filterValue\\\":\\\"Handle Account 1\\\",\\\"customerNumber\\\":\\\"656565\\\"}\",\n" //
				+ "    \"action_steps\" : [ ]\n" //
				+ "  }\n" //
				+ "" + "\n---\n\n" //
				+ "Given the above examples, provide only the Correct Output for future inputs and context.\n" //
		);
	}
}
