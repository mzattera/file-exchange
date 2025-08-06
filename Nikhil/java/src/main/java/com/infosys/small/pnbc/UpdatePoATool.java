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
 * This is a tool used to check SKS and PoA documents and update client
 * information accordingly, as a sub-task.
 */
public class UpdatePoATool extends LabAgent {

	// I want to force specific processing, not generic commands
	public static class Parameters extends ReactAgent.Parameters {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique Client Number for the estate.")
		public String estateCustomerNumber;
	}

	// I want to force specific processing, not generic commands
//	private static final String COMMAND = "Retrieve Probate Certificate (SKS) and Power of Attorney (PoA) documents for estate with Customer Number=\"{{estate}}\", if available.\n" //
//			+ "IF none of the SKS or PoA are provided, THEN end execution.\n"
//			+ "Meticulously compare all information available about the persons related to the estate with corresponding data provided in both SKS or PoA documents "
//			+ "(e.g. check whether email addresses in PoA or SKS is different from that in our systems); "
//			+ "in this step, **STRICTLY** ignore \"Power Of Attorney Type\" and \"Identification Completed\" fields but be very mindful with other fields, "
//			+ "including relation to estate if different than \"Other\" (e.g. if you can infer from SKS or PoA a person is now \"Heir\"). " //
//			+ "IF AND ONLY IF you find any data that is missing or that needs to be updated (considering above exceptions), THEN update the record for the related person, "
//			+ "ELSE do not make any attempt to write, confirm, or update the person's data.\n" //
//			+ "\n" //
//
//			+ "IF PoA is available, THEN {\n"
//			+ "	FOR EACH person who (has received some power of attorney in PoA other than \"None\") AND (hasn't only granted power of attorney to somebody in PoA) {\n"
//			+ "		IF the person has any account in the bank THEN {\n" //
//			+ "			Update person's \"Power Of Attorney Type\" and \"Relation To Estate\" accordingly to PoA and set \"Identification Completed\"=\"OK - Client\".\n" //
//			+ "			Unblock accounts for the estate.\n" //
//			+ "			In your output, notify the user that accounts for estate have been unblocked; provide estate's Customer Number.\n" //
////			+ "			Create an entry in the task diary with category \"Created netbank to CPR\" mentioning that accounts for given estate have been unblocked; provide the estate's Customer Number.\n" //
//			+ "		}\n" //
//			+ "		IF the person does NOT have any account in the bank THEN {\n" //
//			+ "			Communicate to the Operations Officer that that person cannot be identified; clearly specify the power of attorney type they received. End the process execution here.\n" //
//			+ "		}\n" //
//			+ "	}\n" // For each person
//			+ "}\n"; // IF PoA was provided

	private static final String COMMAND = "Retrieve Probate Certificate (SKS) and Power of Attorney (PoA) documents for estate with Customer Number = \"{{estate}}\", if available.\n" //
			+ "IF neither SKS nor PoA is provided, THEN end execution.\n" //
			+ "\n" //
			+ "Compare all available information in our systems about **every person related to the estate** (excluding the deceased) with the data in the SKS and PoA documents:\n" //
			+ "- Ignore the \"Power Of Attorney Type\" and \"Identification Completed\" fields when comparing data.\n" //
			+ "- Be attentive to other fields, especially \"Relation To Estate\" (unless it is \"Other\"), including address.\n" //
			+ "- If and only if you find missing or outdated data (excluding the above exceptions), THEN update the record for that person (e.g., if the SKS lists a person as \"Heir\", set \"Relation To Estate\" to \"Heir\" for that person).\n" //
			+ "\n" //
			+ "IF a PoA is available, THEN:\n" //
			+ "    1. For each person who is **explicitly GRANTED** (receives) any Power of Attorney in the PoA (PoA type other than \"None\"):\n" //
			+ "        a. If this person has any account in the bank:\n" //
			+ "            - Update their \"Relation to Estate\" = \"Power of Attorney\".\n"
			+ "            - Update \"Power Of Attorney Type\" and \"Relation To Estate\" according to the PoA document.\n" //
			+ "            - Set \"Identification Completed\" = \"OK - Client\".\n" //
			+ "            - Unblock accounts for the estate.\n" //
			+ "            - In your output, notify the user that accounts for the estate have been unblocked; provide estate's Customer Number.\n" //
			+ "        b. If this person does NOT have any account in the bank:\n" //
			+ "            - Inform the Operations Officer that this person cannot be identified; specify the Power of Attorney type they received.\n" //
			+ "            - End the process here.\n" //
			+ "    2. **You must NOT update \"Power Of Attorney Type\", \"Identification Completed\", or \"Relation To Estate\" for persons who only GRANT power to others and do NOT themselves receive any Power of Attorney.**\n" //
			+ "";

	public UpdatePoATool() {

		super("updatePoATool", //
				"This tool processes the Probate Certificate (SKS) and Power of Attorney (PoA) documents to perform any required update of client data. "
						+ "**STRICTLY** use this only to process Probate Certificate (SKS) and Power of Attorney (PoA) documents.",
				List.of( //
						new Peace(), //
						new CustomerPortal(), //
						new OperatorCommunicationTool(), //
						new FileDownloadTool() //
				));

		this.getExecutor().setCheckLastStep(true);

		// We want this to have clear parameters definition when invoked and we do not
		// need a command, as we have it already.
		setJsonParameters(Parameters.class);

		setContext(
				"  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, \"Customer Number\" is sometimes indicated as \"afdøde CPR\" or \"CPR\" in documents.\n"
						+ "  * Probate Certificate is a document that lists heirs for one estate; it is sometime indicated as \"SKS\".\n"
						+ "  * Power of Attorney document (PoA) is a document that define people's legal rights over the estate's asset. It is sometime indicated as \"PoA\".\n"

						+ "  * Data about persons related to estates are described by the below JSON schema:\n" //
						+ JsonSchema.getJsonSchema(Person.class) + "\n" //
						+ "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. Always provide the Customer Number if a tool needs to act on a specific person/client; indicate it as Customer Number and not CPR when passing it to tools.\n");
	}

	@Override
	public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {
		if (!isInitialized())
			throw new IllegalStateException("Tool must be initialized.");

		String estate = getString("estateCustomerNumber", call.getArguments());
		if (estate == null)
			return new ToolCallResult(call, "ERROR: You must provide the estate's Customer Number.");

		Map<String, String> map = new HashMap<>();
		map.put("estate", estate);

		ExecutionContext ctx = getLabAgent().getExecutionContext();
		Step result = execute(ctx, Agent.fillSlots(COMMAND, map));
		switch (result.status) {
		case ERROR:
			return new ToolCallResult(call, "ERROR: " + result.observation);
		default:
			return new ToolCallResult(call, result.observation);
		}
	}
}