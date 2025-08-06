/**
 * 
 */
package com.infosys.small.pnbc;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.core.Agent;
import com.infosys.small.core.JsonSchema;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.pnbc.Peace.Person;
import com.infosys.small.react.ReactAgent;

import lombok.NonNull;

/**
 * This is a tool used to check whether bills should be paid, as a sub-task.
 */
public class InspectBillTool extends LabAgent {

	// I want to force specific processing, not generic commands
	public static class Parameters extends ReactAgent.Parameters {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Estate's name.")
		public String estateName;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Estate's unique Customer Number.")
		public String estateCustomerNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Time the task to inspect was created. Use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").")
		public String timeCreated;

		@JsonProperty(required = true)
		@JsonPropertyDescription("File name of the task attachment to inspect.")
		public String attachmentFileName;
	}

	public static class Response {

		@JsonProperty(required = true)
		@JsonPropertyDescription("The action that must be performed for the provided attachment.")
		public String action;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Full name of the estate, as specified in the task.")
		public String estateName;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Estate's unique Customer Number (CPR), as specified in the task.")
		public String estateCustomerNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Full name of the person who created the task, as specified in the task.")
		public String requestorName;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique Customer Number (CPR) of the person who created the task, as specified in the task.")
		public String requestorCustomerNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("True if and only if the attachment is a bill/invoice relative to funeral expenses.")
		public boolean isFuneralBill;

		@JsonPropertyDescription("If the attachment is a bill/invoice, this is the person or legal entity that issued the bill/invoice; provide their names and address if possible.")
		public String issuer;

		@JsonPropertyDescription("If the attachment is a bill/invoice, this is the person the bill was invoiced to.")
		public String invoiceTo;

		@JsonPropertyDescription("Total amount to be paid, if any, as contained in the attachment, always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\").")
		public String amount;

		@JsonPropertyDescription("The person or legal entity to which the payment must be made, if any; provide their names and address if possible. This might be different from the issuer if the bill/invoice was already paid by somebody and we must issue a reimbursement to them.")
		public String beneficiary;

		@JsonPropertyDescription("Account from where the amount used to pay the bill should be taken, if a payment has to be made.")
		public String fromAccount;

		@JsonPropertyDescription("Account where the amount should be paid to, if a payment has to be made.")
		public String toAccount;

		@JsonPropertyDescription("Invoice (\"Faktura\") number, if the attachment is a bill/invoice.")
		public String invoiceNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The reasoning leading you to this output.")
		public String thought;
	}

	// I want to force specific processing, not generic commands
	private static final String COMMAND = "Your task is to decide whether a payment should be fulfilled and extract and return some relevant information for the payment, by following the below instructions.\n"

			+ "  * In the below instructions, terms \"bill\", \"invoice\", \"bill/invoice\", \"attachment\", etc. are synonyms.\n"
			+ "  * Examine the contents of the task with Customer Number=\"{{estateCustomerNumber}}\" ({{name}}) and Time Created=\"{{timeCreated}}\" "
			+ "and of its attachment with File Name=\"{{attachmentFileName}}\", then extract all information needed to produce the required output.\n"
			+ "  * Account numbers where payments should be made might come in \"payment line\" format such as: \"+32<000000000063860+94720463\" or \"+32<000000000063860>+94720463<\".\n"
			+ "  * **STRICTLY**, if and only if task contents provide an account form where to fetch amounts for payments/reimbursements, then use this account for \"fromAccount\" field in your output both for payments and reimbursements.\n"
			+ "  * **STRICTLY**, if and only if task contents or the attachment provide an account to where transfer amounts for reimbursements, then use this account for \"toAccount\" field in your output for reimbursements.\n"

			+ "  * **STRICTLY**, if any instruction tells you to output a specific value for \"action\" field in your output, then you must create an output with the specified value for \"action\" field.\n"

			// Dunno why it was there; it is not stated anywhere it hass to be like
			// this.....
//			+ "  * IF the attachment is a bill/invoice AND it is NOT invoiced to the estate, THEN corresponding \"action\" field in your output **MUST** be to not to execute any payment; leave optional response fields empty.\n"

			// TODO URGENT: Clarify how to handle this
			+ "IF the attachment is a letter from Skifteretten mentioning a retsafgift (probate court fee) that may need to be paid "
			+ "THEN the fee must be paid; extract the Skifteretten account for payment, if provided in the document.\n"
			+ "\n" //

			+ "IF any of the persons related to the estate has some Power of Attorney {\n"
			+ "	IF the attachment refers to expenses related to funeral (e.g. cemetery services and fees, church service, flowers, catering, etc.) THEN {\n" //
			+ "		The attachment must NOT be paid/reimbursed.\n" // TODO Updated when new scenarios are coming
			+ "	} ELSE {\n" //
			+ "		IF only one person in <people> has power of attorney and their identity has been verified THEN {\n" //
			+ "			IF content in <task> requests to pay attached bills/invoices and the task was created by the person with power of attorney THEN {\n" //
			+ "				The attachment must be paid/reimbursed.\n" //
			+ "			} ELSE {\n" //
			+ "				The attachment must NOT be paid/reimbursed.\n" // TODO Updated when new scenarios are coming
			+ "			}\n" //
			+ "		} ELSE {\n" //
			+ "			The attachment must NOT be paid/reimbursed.\n" // TODO Updated when new scenarios are coming
			+ "		}\n" //
			+ "	}\n" //
			+ "}\n" //
			// Keep these two separate, as it performs better than single
			// IF...THEN...ELSE... statement
			+ "IF none of the persons in <people> has some Power of Attorney {\n"
			+ "	Do not consider whether the identity of persons in <people> has been verified or not.\n" //
			+ "	IF the attachment refers to expenses related to funeral (e.g. cemetery services and fees, church service, flowers, catering, etc.) THEN {\n" //
			+ "		IF content in <task> requests to pay attached bills/invoices THEN {\n" //
			+ "			IF (attachment amount is above 15,000.00 DKK) AND (the attachment is specifically related to food catering, gathering after funeral or tombstone costs THEN {\n" //
			+ "				The attachment must NOT be paid/reimbursed.\n" //
			+ "			} ELSE {\n" //
			+ "				The attachment must be paid/reimbursed **EVEN IF** the identity of the person who created the task has not been verified.\n" //
			+ "			}\n" //
			+ "		} ELSE {\n" //
			+ "			The attachment must NOT be paid/reimbursed.\n" // TODO Updated when new scenarios are coming
			+ "		}\n" //
			+ "	} ELSE {\n" //
			+ "	}\n" //
			+ "}\n" //

			+ "If accordingly to above logic, the attachment must be paid, then if the attachment text indicates that the bill has already been paid, then the \"action\" field in your output **MUST** be to issue a reimbursement to the client.\n"
			+ "If accordingly to above logic, the attachment must be paid, then if the attachment text indicates that the bill has **NOT** been paid, then the \"action\" field in your output **MUST** be to issue a payment to the person or entity who created the invoice, as specified in the attachment.\n"
			+ "If accordingly to above logic, the attachment must NOT be paid, then the \"action\" field in your output **MUST** be to NOT issue a payment to the person or entity who created the invoice, as specified in the attachment.\n"

			+ "**STRICTLY AND ALWAYS** Output your final \"observation\" as JSON, in the format described by the below JSON schema in <output_schema> tag.\n" //
			+ "\n<output_schema>\n" + JsonSchema.getJsonSchema(Response.class) + "\n</output_schema>\n";

	public InspectBillTool() {

		super("inspectBillsTool", //
				"This tool inspects one task attachment that is supposed to be a bill/invoice determining whether it needs to be paid and corresponding payment details. "
						+ "**STRICTLY** Do not call this tool on attachments you know are not bill/invoices or to determine the type of an attachment. "
						+ "Format of the returned result is described by this JSON Schema:\n"
						+ JsonSchema.getJsonSchema(Response.class),
				List.of( //
						new Peace.GetRelatedPersonsApi(), //
						new Peace.GetTaskContentApi(), //
						new Peace.GetFileContentApi()));

//		this.getExecutor().setCheckLastStep(true);

		// We want this to have clear parameters definition when invoked and we do not
		// need a command, as we have it already.
		setJsonParameters(Parameters.class);

		// Cannot do as this output steps
//		setResponseFormat(ResponseFormat.class);

		setContext(
				"  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, \"Customer Number\" is sometimes indicated as \"afdøde CPR\" or \"CPR\" in documents.\n"

						+ "  * Data about persons related to estates are described by the below JSON schema:\n" //
						+ JsonSchema.getJsonSchema(Person.class) + "\n" //
						+ "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. Always provide the Customer Number if a tool needs to act on a specific person/client; indicate it as Customer Number and not CPR when passing it to tools.\n");
	}

	@Override
	public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {
		if (!isInitialized())
			throw new IllegalStateException("Tool must be initialized.");

		String estateName = getString("estateName", call.getArguments());
		if (estateName == null)
			return new ToolCallResult(call, "ERROR: You must provide the estate's name.");

		String estateCustomerNumber = getString("estateCustomerNumber", call.getArguments());
		if (estateCustomerNumber == null)
			return new ToolCallResult(call, "ERROR: You must provide the estate's Customer Number.");

		String timeCreated = getString("timeCreated", call.getArguments());
		if (timeCreated == null)
			return new ToolCallResult(call, "ERROR: You must provide creation time for task to inspect.");

		String attachmentFileName = getString("attachmentFileName", call.getArguments());
		if (attachmentFileName == null)
			return new ToolCallResult(call, "ERROR: You must provide file name of the attachment to inspect.");

		Map<String, String> map = new HashMap<>();
		map.put("estateName", estateName);
		map.put("estateCustomerNumber", estateCustomerNumber);
		map.put("timeCreated", timeCreated);
		map.put("attachmentFileName", attachmentFileName);

		ExecutionContext ctx = getLabAgent().getExecutionContext();
		Step lastStep = execute(ctx, Agent.fillSlots(COMMAND, map));

		switch (lastStep.status) {
		case ERROR:
			return new ToolCallResult(call, "ERROR: " + lastStep.observation);
		default:
			Response result = null;
			try {
				result = JsonSchema.deserialize(lastStep.observation, Response.class);
			} catch (Exception e) {
				// The agent did not return proper JSON in observation.....
				return new ToolCallResult(call,
						"ERROR: I encountered an error; it might be temporary and fixed if you call me again with same parameters. Do not try multiple calls more than 3 times.");
			}
			return new ToolCallResult(call, JsonSchema.serialize(result));
		}
	}
}