/**
 * 
 */
package com.infosys.small.pnbc;

import java.util.HashMap;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.infosys.small.core.ToolCall;
import com.infosys.small.core.ToolCallResult;
import com.infosys.small.pnbc.Capt.Parameters.DocumentType;
import com.infosys.small.react.ReactAgent;

import lombok.NonNull;

/**
 * This tool gives you access to files that have been uploaded through CAPT.
 * This is because asking agents to provide files, sometimes results in a file
 * summary.
 */
public class FileDownloadTool extends Api {

	public static class Parameters extends ReactAgent.Parameters {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique customer number of the estate the document refers to.")
		public String customerNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The type of the document to download.")
		public DocumentType documentType;
	}

	@Override
	public ToolCallResult invoke(@NonNull ToolCall call) throws Exception {
		if (!isInitialized()) {
			throw new IllegalArgumentException("Tool must be initialized.");
		}

		Map<String, Object> args = new HashMap<>(call.getArguments());
		args.remove("thought"); // As we are passing it, we must remove or it won't match tools

		String customerNumber = getString("customerNumber", args);
		if (customerNumber == null)
			return new ToolCallResult(call,
					"ERROR: You must provide Customer Number of the estate the file refers to.");

		String documentType = getString("documentType", args);
		args.remove("documentType"); // As we are passing it to tools, we must remove or it won't match tools
		switch (documentType) {
		case "SKS":
			if (getExecutionContext().getSKS().get(customerNumber) == null) {
				// This is the first time we call this API; let's get value from scenario
				getExecutionContext().getSKS().put(customerNumber, ScenarioComponent.getInstance().get( //
						getScenarioId(), //
						"getSKS", //
						args));
			}
			return new ToolCallResult(call, getExecutionContext().getSKS().get(customerNumber));
		case "POWER_OF_ATTORNEY":
			if (getExecutionContext().getPoA().get(customerNumber) == null) {
				// This is the first time we call this API; let's get value from scenario
				getExecutionContext().getPoA().put(customerNumber, ScenarioComponent.getInstance().get( //
						getScenarioId(), //
						"getPoA", //
						args));
			}
			return new ToolCallResult(call, getExecutionContext().getPoA().get(customerNumber));
		case "PROFORMA_DOCUMENT":
			if (getExecutionContext().getProformaDocument().get(customerNumber) == null) {
				// This is the first time we call this API; let's get value from scenario
				getExecutionContext().getProformaDocument().put(customerNumber, ScenarioComponent.getInstance().get( //
						getScenarioId(), //
						"getProformaDocument", //
						args));
			}
			return new ToolCallResult(call, getExecutionContext().getProformaDocument().get(customerNumber));
		default:
			return new ToolCallResult(call, "ERROR: Invalid document type: " + documentType);
		}
	}

	public FileDownloadTool() {

		super("fileDownload", //
				"This tool provides access to files stored on backend system such as Proforma Document, Power of Attorney document (PoA), and Probate Certificate (SKS).",
				Parameters.class);
	}
}