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
				"  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, \"Customer Number\" is sometimes indicated as \"afdøde CPR\" or \"CPR\" in documents.\n" //
						+ "  * Probate Certificate is a document that lists heirs for one estate; it is sometime indicated as \"SKS\".\n" //
						+ "  * Power of Attorney document (PoA) is a document that define people's legal rights over the estate's asset. It is sometime indicated as \"PoA\".\n" //
						+ "  * Proforma Document is a document containing the amount of cash available on estate's account at the time of their death.\n" //
						+ "  * Probate Court (Skifteretten) Notification Letter is an official letter from Skifteretten informing the heirs about the opening of an estate after a person’s death; this is **NOT** same as SKS, even it might notify heirs that SKS has been issued.\n" //

//						+ "  * Sometimes, the bills you are provided might contain the indication they have been paid, this means one person related to the estate paid the bill and they are requesting you to reimburse them of the amount. "
//						+ "If this is the case, the payment needs to be done to the person sending the request. In all other cases (where the bill is not marked as paid), the bill must be paid the entity who created it, as indicated in the bill itself.\n" //

						+ "  * To indicate time stamps, always use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").\n" //
						+ "  * For amounts, always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\").\n" //

						+ "  * Persons data are described by this JSON schema: "
						+ JsonSchema.getJsonSchema(Peace.Person.class) + "\n" //
						+ "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. **STRICTLY** always communicate Customer Number to any tool that needs to act on persons/clients; indicate it as Customer Number and not CPR. "
						+ "Never identify a person only providing their name or email.\n" //

						+ "  * Tasks are uniquely identified by the combination of their \"Customer Number\" and \"Time Created\" fields. **STRICTLY** always provide these fields if a tool needs to act on a specific task\n" //
						+ "  * Payment tasks are identified by having Step Name=\"Handle Account 1\".\n" //

						+ "  * When you need to identify yourself as an operator (e.g. when managing tasks), use Operator ID == 42.\n" //

						+ "  * Accounts can be personal or half-joint. This is indicated by their \"JO\" field: JO==N for Personal Accounts and JO==J for Half-Joint accounts.\n" //

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
		return execute(ctx, "Run the following process described in <process>:\n" //
				+ "\n" //
				+ "<process>\n" //
				+ "1. Assign to yourself (Operator ID=42) the oldest unassigned payment task with Step Name \"Handle Account 1\". This is the \"main task\".\n" //
				+ "2. Assign to yourself any other unassigned payment task with Step Name \"Handle Account 1\" for the same Client Number as the main task.\n" //
				+ "\n" //
				+ "3. For each task assigned to you (\"current task\"):\n" //
				+ "\n" //
				+ "    a. Identify **all persons related to the estate**, including:\n" //
				+ "        - All persons currently registered as related to the estate in the system\n" //
				+ "        - The creator of the task (even if not yet registered as related)\n" //
				+ "    b. For each identified person:\n" //
				+ "        - If the person is **not present** in the system, create a new related person record using all available data (name, address, email, phone, etc.).\n" //
				+ "        - Compare the person’s data from all sources (task content, attachments, SKS, PoA) with their system record. Ignore \"Power of Attorney Type\" and \"Identification Completed\" fields.\n" //
				+ "        - If and only if any data (except the above) is missing or outdated, update the record for that person.\n" //
				+ "        - Ignore the deceased person for all these checks and updates.\n" //
				+ "    c. For each attachment in the task:\n" //
				+ "        i. Determine the document type (Probate Certificate, Power of Attorney, Probate Court Notification, ID, Bill/Invoice, Proforma Document, Other).\n" //
				+ "\n" //
				+ "        ii. If the attachment is an ID document for a person, follow these steps **exactly in this order**:\n" //
				+ "            A. **Check if \"Identification Completed\" for the person is \"OK – Customer\":**\n" //
				+ "                - If YES, do **NOT** upload the ID. Stop here.\n" //
				+ "                - If NO, continue.\n" //
				+ "            B. **Check if the ID document has an expiration date:**\n" //
				+ "                - If NO expiration date is present, do **NOT** upload the ID. Stop here.\n" //
				+ "                - If an expiration date exists, continue.\n" //
				+ "            C. **Search the diary entries of ALL your assigned tasks for any note or instruction stating that the ID for this person should NOT be uploaded:**\n" //
				+ "                - If ANY diary entry in ANY assigned task says not to upload the ID, do **NOT** upload the ID. Stop here.\n" //
				+ "                - If NO such diary entry exists, proceed to the next step.\n" //
				+ "            D. **Only if ALL above checks are passed (none of the previous \"stop here\" conditions are met), upload the ID document.**\n" //
				+ "        **You MUST strictly follow **all** these steps IN ORDER. You MUST NOT upload the ID unless all previous checks are performed and allow it.**\n" //
				+ "\n" //
				+ "        iii. For Probate Certificate (SKS): upload and process to perform all required updates (including \"Relation To Estate\" for any new heir),\n" //
				+ "and log an entry **only** in the diary of the current task (category = \"SKS registered\").\n" //
				+ "        iv. For Power of Attorney (PoA): upload and process, updating only \"Power Of Attorney Type\", \"Identification Completed,\" and \"Relation To Estate\"\n" //
				+ "**for the recipient(s)** of power, **not the grantor(s)**. Log an entry **only** in the diary of the current task (category = \"PoA uploaded in CF\").\n" //
				+ "        v. If the SKS or PoA processing results in estate accounts being unblocked, log an entry only in the diary for the current task (category = \"Created netbank to CPR\").\n" //
				+ "        vi. For Proforma Document: upload the document.\n" //			
				+ "\n" //
				+ "4. **Before processing any bill or invoice for payment or reimbursement:**\n" //
				+ "    a. **Attempt to download the Proforma Document from backend systems and extract the Proforma balance.**\n" //
				+ "        - If Proforma Document is available, extract and record the Proforma balance **only** in diary for **main** task  (category = \"Proforma's Balance\").\n" //
				+ "        - If not available, search in diary entries of your tasks for the latest Proforma balance.\n" //
				+ "    b. **The Proforma balance is a strict payment ceiling:**  \n" //
				+ "       - **If a Proforma balance is known, you must NEVER pay or reimburse any bill where the bill's total amount (or the reimbursement amount) exceeds the Proforma balance.**\n" //
				+ "       - If the Proforma balance is not known, this restriction does not apply and you may proceed.\n" //
				+ "\n" //
				+ "5. **For each attachment that is a bill/invoice or Probate Court Notification Letter:**\n" //
				+ "    a. Extract all payment details and instructions.\n" //
				+ "    b. **If the payment is requested:**  \n" //
				+ "        i. First, check diary for the task where the attachment comes from: if the bill is already recorded as paid, do not pay/reimburse it.\n" //
				+ "        ii. Then, check all estate account transactions: if a payment matching the bill exists, do not pay/reimburse it.\n" //
				+ "        iii. **Next, strictly check the Proforma balance:**\n" //
				+ "            - **If the Proforma balance is known, and the bill amount exceeds the Proforma balance, do NOT pay or reimburse the bill, even if there is enough cash. "
				+ "            - If the Proforma balance is not known, proceed to the next check.\n" //
				+ "        iv. Check cash availability (full personal account balances + half of half-joint account balances, regardless if accounts are frozen).\n" //
				+ "            - If not enough cash is available, do not pay/reimburse the bill; log the rejection.\n" //
				+ "        v. If all above checks are passed, instruct the Operations Officer to pay or reimburse as per **ALL the extracted payment details and instructions**.\n" //
				+ "        vi. Log the payment **only** in the diary for the task where the attachment is cominig from (category = \"Paid bill\" or \"Transferred udlaeg\"), ALWAYS include all the payment details above.\n" //
				+ "            **Never omit issuer, invoice number, invoice recipient, beneficiary, amount, account(s), payment reference, or any available field. If a field is missing, state “Not provided”.**\n" //
				+ "        vii. When you process a bill/invoice and do not pay/reimburse it for any reason, always create an entry **only** in the diary for the task where the attachment is cominig from (category = \"Rejected to pay bill to\") explaining the reason.\n" //
				+"              When logging the rejection, include all the payment details listed above, plus the reason for rejection. Never omit issuer, invoice number, beneficiary, amount, or account(s).\n" //
				+ "\n" //
				+ "6. After processing all tasks and attachments, send one final recap email to the person who created the main task (not the estate); when preparing this email:\n" //
				+"    - List all bills that were paid, and for each, include **all the following payment details (when available):**\n" //
				+ "        - Invoice/bill issuer (name and address)\n" //
				+ "        - Invoice recipient\n" //
				+ "        - Invoice number and date\n" //
				+ "        - Amount and currency\n" //
				+ "        - Account(s) paid from and to\n" //
				+ "        - Beneficiary (name and address)\n" //
				+ "        - Payment reference or OCR line\n" //
				+ "        - Short description of goods/services\n" //
				+ "    - List all bills not paid, with **the same details as above**, plus the reason for rejection.\n" //
				+ "    - **Never omit any available detail. If a payment field is missing, state “Not provided”.**\n" //
				+ "    - You MUST check, with maximum accuracy, whether a Probate Certificate (SKS) mention is present among all execution steps. "
				+ "If the SKS is NOT mentioned as available or uploaded at any step or is mentioned as missing, "
				+ "you MUST include in the email a request for the sender to provide the Probate Certificate (SKS) for the estate.\n" //
				+ "    - If estate accounts were unblocked, mention that online banking access was granted.\n" //
				+ "\n" //
				+ "7. After sending the recap email, log the email content in the main task diary (category = \"Info email sent\").\n" //
				+ "   **If and only if the email included a request for the Probate Certificate (SKS), "
				+ "you MUST ALSO log this as a separate entry in main task diary (category = \"Sent email asking for SKS\"), clearly stating that such a request was sent. Never skip this separate entry.**\n" //
				+ "\n" //
				+ "8. For every task you processed (including the main task and any additional tasks):\n" //
				+ "    a. Explicitly close the task by calling the appropriate tool with all required identifiers (such as Client Number and Time Created).\n" //
				+ "    b. After each close action, confirm that the tool reports success before proceeding.\n" //
				+ "    c. If any close action fails, do NOT proceed to completion; handle or report the failure.\n" //
				+ "    d. Only when all processed tasks are closed successfully, you may proceed to output the final step with status=\"COMPLETED\".\n" //
				+ "\n" //
				+ "Additional instructions: **never** contact the Operations Officer or a client if not **explicitly** instructed to do so in the above process."
				+ "</process>\n");	}
	
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