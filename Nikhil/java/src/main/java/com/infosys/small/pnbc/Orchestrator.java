package com.infosys.small.pnbc;

import java.util.List;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.infosys.small.core.JsonSchema;
import com.infosys.small.pnbc.ExecutionContext.DbConnector;

public class Orchestrator extends LabAgent {

	public Orchestrator() {

		super("ORCHESTRATOR", "I am the first ever built process orchestrator", List.of( //
				new Peace(), //
				new CustomerPortal(), //
				new OperatorCommunicationTool(), //
				new Capt(), //

				new FileDownloadTool(), //
				new UpdatePoATool(), //
				new InspectBillTool() //
		), true);

		setContext(
				"  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, \"Customer Number\" is sometimes indicated as \"afdøde CPR\" or \"CPR\" in documents.\n"
						+ "  * Probate Certificate is a document that lists heirs for one estate; it is sometime indicated as \"SKS\".\n"
						+ "  * Power of Attorney document (PoA) is a document that define people's legal rights over the estate's asset. It is sometime indicated as \"PoA\".\n"
						+ "  * Proforma Document is a document containing the amount of cash available on estate's account at the time of their death.\n"
						+ "  * Probate Court (Skifteretten) Notification Letter is an official letter from Skifteretten informing the heirs about the opening of an estate after a person’s death; this is **NOT** same as SKS, even it might notify heirs that SKS has been issued.\n"

//						+ "  * Sometimes, the bills you are provided might contain the indication they have been paid, this means one person related to the estate paid the bill and they are requesting you to reimburse them of the amount. "
//						+ "If this is the case, the payment needs to be done to the person sending the request. In all other cases (where the bill is not marked as paid), the bill must be paid the entity who created it, as indicated in the bill itself.\n"

						+ "  * To indicate time stamps, always use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").\n"
						+ "  * For amounts, always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\").\n"

						+ "  * Persons data are described by this JSON schema: "
						+ JsonSchema.getJsonSchema(Peace.Person.class) + "\n"
						+ "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. **STRICTLY** always communicate Customer Number to any tool that needs to act on persons/clients; indicate it as Customer Number and not CPR. "
						+ "Never identify a person only providing their name or email.\n"

						+ "  * Tasks are uniquely identified by the combination of their \"Customer Number\" and \"Time Created\" fields. **STRICTLY** always provide these fields if a tool needs to act on a specific task\n"
						+ "  * Payment tasks are identified by having Step Name=\"Handle Account 1\".\n"

						+ "  * When you need to identify yourself as an operator (e.g. when managing tasks), use Operator ID == 42.\n"

						+ "  * Accounts can be personal or half-joint. This is indicated by their \"JO\" field: JO==N for Personal Accounts and JO==J for Half-Joint accounts.\n"

						// TODO try to save calls by using data in steps
						+ "  * Be mindful when calling tools, since each tool has access only to specific capabilities and data.\n");
	}

	/**
	 * Runs the "default" process.
	 * 
	 * @return
	 * @throws JsonProcessingException
	 */
	public Step execute(ExecutionContext ctx) throws JsonProcessingException {
		return execute(ctx, "Run the below process described in pseudo-code inside <process> tag.\n" //
				+ "\n<process>\n" //
				+ "Check for any unassigned payment task (Step Name=\"Handle Account 1\") and assign the oldest created payment task to you.\n" //
				+ "\n" //
				+ "Assign to you any unassigned payment task (Step Name=\"Handle Account 1\") for the same estate (Client Number)." //
				+ "\n" //

				+ "Read content of attachments for tasks assigned to you to verify if the Probate Certificate (SKS) or the Power of Attorney (PoA) documents are attached."
				+ "IF SKS or PoA are attached, THEN {.\n" //
				+ "	Upload attached Probate Certificate (SKS) and Power of Attorney (PoA) documents, when provided.\n" //
				+ "	IF SKS was uploaded, THEN create an entry in the task diary for the task where SKS was attached with category \"SKS registered\" mentioning that Probate Certificate was uploaded.\n" //
				+ "	IF PoA was uploaded, THEN create an entry in the task diary for the task where PoA was attached with category \"PoA uploaded in CF\" mentioning that Power of Attorney document was uploaded.\n" //
				+ "	Process the attached Probate Certificate (SKS) and Power of Attorney (PoA) documents to perform any required update of client data; "
				+ "IF this resulted in estate's account being unblocked, THEN create an entry in the task diary for the task where PoA was attached with category \"Created netbank to CPR\" mentioning that accounts for given estate have been unblocked.\n" //
				+ "}\n" // IF SKS/PoA provided

				+ "If Proforma Document is not in any attachment, try to download it; IF it is available  THEN {\n" //
				+ "\n" //
				+ "		IF none of the diaries associated to tasks assigned to you mentions the available balance in the Proforma document, THEN {\n" //
				+ "			Write in diary that Proforma balance is available in AHK and record the available balance,\n" //
				+ "			as provided by the Proforma Document. Use category = \"Proforma's Balance\" to create the entry in the diary.\n" //
				+ "		If you do not know the Proforma balance, do **NOT** update the diary.\n" //
				+ "		}\n" //
				+ "} ELSE { \n" //
				+ "		The Proforma Document is not available, do **NOT** update the diary.\n" //
				+ "	}\n" //
				+ "\n" //

				+ "FOR EACH task assigned to you {\n" //
				+ "\n" //
				+ "Meticulously compare any information about the person who created the task, as described in task contents and its attachments, "
				+ "with the data in the system about people related to the estate. In this step, **STRICTLY** ignore relationship to estate, power of attorney and identification fields.\n" //
				+ "IF AND ONLY IF you find any data that is missing or that needs to be updated (considering above exceptions), THEN update the record for the related person, "
				+ "ELSE do not make any attempt to write, confirm, or update the person's data.\n" //
				+ "\n" //
				+ "	FOR EACH single attachment of the task {\n" //
				+ "\n" //
				+ "		Inspect the content of the task and the attachment to determine whether the attachment is a bill that needs to be paid or reimbursed and corresponding payment details. " //
				+ "**STRICTLY** follow instructions contained in payment details about how to perform the payment (e.g. from and to accounts to use for the payment).\n" //
				+ "\n" //
				+ "		IF the attachment is a bill that must be paid or reimbursed, THEN {\n" //
				+ "				Check in the task diary: IF the bill is already being paid, THEN {\n" //
				+ "					The bill must not be paid nor reimbursed.\n" //
				+ "				} ELSE {\n" //
				+ "					Check transaction in estate accounts for any transaction which amount could indicate the bill has already been paid or reimbursed. " //
				+ "Use only transaction data to determine if the bill has already been paid or reimbursed.\n" //
				+ "					IF you find a matching amount, THEN {\n" //
				+ "						The bill must not be paid nor reimbursed.\n" //
				+ "					} ELSE {\n" //
				+ "					\n" //
				+ "						Consider if enough cash is available to pay/reimburse the bill; you must consider the entire sum available \n" //
				+ "						in each personal account, plus half of the sum available in each half-joined account, regardless whether the account are frozen."
				+ "                     Also, subtract any amount you paid as result of running this process.\n" //
				+ "						\n" //
				+ "						IF there is enough cash left to pay the bill, THEN {\n" //
				+ "							Instruct the Operations Officer to pay/reimburse the bill; provided estate name, their customer number,\n" //
				+ "							account number(s) to use for the payments (as instructed in task), amount to be paid, and the reason for the payment\n" //
				+ "							(as provided in the bill). "
				+ "**STRICTLY** never ask Operator Officer which account to use but follow indications in the task, as resulting from inspeciton, if provided. " //
				+ "Assume the payment is done if they tell you to proceed.\n" //
				+ "							" //
				+ "							Update the diary with the payment details; create an entry with payment details, including amount, invoice number, issuer, and beneficiary (who can be different from the issuer in case of a reimbursement). "
				+ "IF you instructed the Operations Officer to perform a reimbursement, THEN use category \"Transferred from\", ELSE use category = \"Paid bill\" for the entry. Create a separate diary entry for each bill.\n" //
				+ "						}\n" //
				+ "					}\n" //
				+ "				}\n" //
				+ "		} ELSE {\n" //
				+ "			Do not pay anything for this attachment.\n" //
				+ "		}\n" //
				+ "	}\n" // For each attachment in the task
				+ "	\n" //
				+ "Send an email to the person who created the task; specify their Customer Number; (**DO NOT** send the email using the estate Customer Number). "
				+ "In the message, enter details about all of the bills that were paid, " //
				+ "their individual and total amounts and the accounts they were paid from and into (if available). " //
				+ "In the mail also list bills that were not paid and explain why they were not paid. "
				+ "IF the Probate Certificate (SKS) for the estate is not available, THEN add a request to send the SKS to the email. "
				+ "IF estate's account were unblocked, mention that access to online bank has been granted in the email. "
				+ "Send only one email per task.\n" //
				+ "\n" //
				+ "After sending the email, update the task diary logging email content; use category = \"Info email sent\".\n" //
				+ "\n" //
				+ "After sending the email, if you requested to send the SKS THEN Update the task diary logging that email request has been sent. " //
				+ "Use category = \"Sent email asking for SKS\".\n" //
				+ "\n" //
				+ "	After all above steps are completed, close the task you just processed; the task must be closed and cannot be assumed it is closed already. "
				+ " Check the response from corresponding tool to ensure the task was indeed closed.\n" //
				+ "}\n" // For each task
				+ "	\n" //
				+ "</process>");
	}
	
	public static void main(String[] args) {
		ExecutionContext ctx = new ExecutionContext(new DbConnector() {
			@Override
			public void addStep(String runId, Step step) {
			}}, "scenario-01","_run_XXX");
		
		Peace p = new Peace();
		p.getDescription();
		
		Orchestrator o = new Orchestrator();
		try {
			o.execute(ctx);
		} catch (JsonProcessingException e) {
			e.printStackTrace(System.err);
		} finally {
			o.close();
		}
	}
}