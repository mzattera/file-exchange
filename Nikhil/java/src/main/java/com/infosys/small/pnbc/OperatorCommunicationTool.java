package com.infosys.small.pnbc;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.react.ReactAgent;

import lombok.NonNull;

/**
 * Backend-system wrapper for the Client Communication Tool.
 */
public class OperatorCommunicationTool extends LabAgent {

	/** Sends a message to the OO, optionally blocking execution until a reply. */
	public static class MessageToOperatorApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("Text of the message for the operations officer.")
			public String message;
		}

		public MessageToOperatorApi() {
			super("messageToOperationOfficer",
					"Sends a message to the Operations Officer. Use this for any iteration that is **NOT** an instuction to issue a payment. Always translate this into English.",
					Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools

			String scenario = getLabAgent().getScenarioId();
			getLabAgent().getExecutionContext().log(scenario, call.getTool().getId(), args);

			String message = getString("message", args, "*ERROR MISSING*");
			getLabAgent().getExecutionContext().log(message); // Always log

			return new ToolCallResult(call,
					"Sorry but I cannot help; immediately abort process execution with \"ERROR\".");
		}
	}

	/** Tells the operations officer to issue a payment . */
	public static class IssuePaymentApi extends Api {
		public static class Parameters extends ReactAgent.Parameters {
			@JsonProperty(required = true)
			@JsonPropertyDescription("The amount that must be paid; always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\").")
			public String amount;

			@JsonProperty(required = true)
			@JsonPropertyDescription("Text with all payment details such as reason for the payment, beneficiary account, etc.. Always translate this into English.")
			public String message;
		}

		public IssuePaymentApi() {
			super("messageForPayment",
					"Instructs the Operations Officer to issue a payment. You **MUST ALWAYS** use this any time a message instructs toe Operations Officer to issue a payment and **ONLY** for that purpose.",
					Parameters.class);
		}

		@Override
		public ToolCallResult invoke(@NonNull ToolCall call, boolean log) throws Exception {
			Map<String, Object> args = new HashMap<>(call.getArguments());
			args.remove("thought"); // As we are passing it, we must remove or it won't match tools

			String amount = getString("amount", args, "*ERROR MISSING*");
			String message = getString("message", args, "*ERROR MISSING*");

			if (amount.contains("ERROR"))
				return new ToolCallResult(call,
						"Sorry but I cannot proceed with the payment as you did not provide the amount to be paid.");

			getLabAgent().getExecutionContext().log(amount, message); // Always log
			return new ToolCallResult(call, "Payment was completed, please proceed.");
		}
	}

	/* ---------- CONSTRUCTOR ---------- */

	// TODO URGENT Do some heavy renaming here.
	public OperatorCommunicationTool() {
		super("OPERATOR_COMMUNICATION_TOOL",
				"The client communication tool allows to communicate with an operator officer. "
						+ "This is used to issue payments, ask for feedback or suggestions about how to proceed with process in case it is not clear what to do or an unrecoverable error is happens.",
				List.of(new MessageToOperatorApi(), new IssuePaymentApi()));
		setContext( //
				"  *  For amounts, always use the format NNN,NNN.NN CCC (e.g. \"2,454.33 DKK\")." //
						+ "  * Ignore any mention to scanned documents, OCR, attachments, as long as you have the required information to call your tools." //
		);
	}
}
