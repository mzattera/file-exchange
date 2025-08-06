package com.infosys.small.pnbc;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.pnbc.ExecutionContext.EmailEntry;
import com.infosys.small.react.ReactAgent;

import lombok.NonNull;

/**
 * Backend-system wrapper for the Customer Portal.
 */
public class CustomerPortal extends LabAgent {

	/* ---------- API DEFINITIONS ---------- */

	/** Lists the accounts belonging to a customer. */
	public static class GetAccountsApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number.")
			public String customerNumber;
		}

		public GetAccountsApi() {
			super("getAccounts", //
					"Returns a list of bank accounts for the specified customer.", Parameters.class);
		}
	}

	/** Unblock all accounts belonging to a customer. */
	public static class UnblockAccountsApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number.")
			public String customerNumber;
		}

		public UnblockAccountsApi() {
			super("unblockAccounts", //
					"Unblocks all accounts belonging to the specified customer.", Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			if (!isInitialized()) {
				throw new IllegalArgumentException("Tool must be initialized.");
			}

			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools

			String customerNumber = getString("customerNumber", args);
			if (customerNumber == null)
				return new ToolCallResult(call, "ERROR: Customer Number must be provided.");

			String scenario = getLabAgent().getScenarioId();
			if (true) // Always Log
				getExecutionContext().log(scenario, call.getTool().getId(), args);

			return new ToolCallResult(call, "All accounts for customer " + customerNumber + " have been unblocked.");
		}
	}

	/** Retrieves all transactions for a given account. */
	public static class GetTransactionsApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique account number.")
			public String accountNumber;
		}

		public GetTransactionsApi() {
			super("getTransactions", "Returns transactions for the specified account.", Parameters.class);
		}
	}

	/** Sends an email / communication to the customer. */
	public static class SendCommunicationApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Unique customer number for the email recipient.")
			public String customerNumber;

			@JsonProperty(required = true)
			@JsonPropertyDescription("The message that you need to send.")
			public String message;
		}

		public SendCommunicationApi() {
			super("sendCommunication", "Sends an email message to the specified customer. **STRICTLY** use this tool ONLY when EXPLICITLY instructed by the user to send an email", Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools

			String customerNumber = getString("customerNumber", args, "*");
			if (!customerNumber.matches("\\d+"))
				return new ToolCallResult(call, "Error: System failure, wrong API call parameters.");

			getExecutionContext().log(new EmailEntry( // Always log
					customerNumber, //
					getString("message", args)));

			return new ToolCallResult(call,
					"Email for client" + getString("customerNumber", args) + " sent succeessfully.");
		}
	}

	/* ---------- CONSTRUCTOR ---------- */

	public CustomerPortal() {
		super("CUSTOMER_PORTAL", //
				"This tool provides access to customers' bank accounts and corresponding transactions. "
						+ "In addition, it allows you to send emails to clients; if you use this capability, provide the Customer Number for the recipient (**NOT** their email). "
						+ "This tool CANNOT be used to access or update customer's data other than their bank accounts.",
				List.of( //
						new GetAccountsApi(), //
						new UnblockAccountsApi(), //
						new GetTransactionsApi(), //
						new SendCommunicationApi() //
				));

		setContext(
				// TODO URGENT things like IDs and stuff maybe should be shared in a global
				// context
				"  * Documents you handle are in Danish, this means sometime you have to translate tool calls parameters. For example, \"Customer Number\" is sometimes indicated as \"afdøde CPR\" or \"CPR\" in documents.\n"

						+ "  * Persons are uniquely identified by their Customer Number, sometimes also referred as CPR. **STRICTLY** always communicate Customer Number to any tool that needs to act on persons/clients; indicate it as Customer Number and not CPR. "
						+ "Never identify a person only providing their name or email.\n"
						+ "  * When asked to provide or update customers' data such as their address, email, etc. return an error message, stating that you do not have access to such data.\n"
						+ "  * When asked to provide any customer related document, return an error message, stating that you do not have access to such data.\n"

						+ "  * Account are uniquely identified by their account numbers; notice that spaces in account numbers are relevant.\n"
						+ "  * Accounts can be personal or half-joint. This is indicated by their \"JO\" field: JO==N for Personal Accounts and JO==J for Half-Joint accounts.\n"

						+ "  * To indicate time stamps, always use \"mm/dd/yyyy, hh:mm AM/PM\" format (e.g. \"4/16/2025, 2:31 PM\").\n"
						+ "  * For amounts, always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\").\n"

						+ "  * **STRICTLY** **NEVER** send emails to people, unless you are explicitly instructed to do so.\n");
	}
}
