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
import com.infosys.small.pnbc.ExecutionContext.UploadEntry;
import com.infosys.small.react.ReactAgent;

import lombok.NonNull;

/**
 * Wrapper for the CAPT tool (file upload).
 */
public class Capt extends Api {

	public static class Parameters extends ReactAgent.Parameters {

		public enum DocumentType {
			SKS, POWER_OF_ATTORNEY, PROFORMA_DOCUMENT, ID
		}

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique customer number of the estate the document refers to. If the document is an ID, this is the custome number fo rthe ID owner (not the estate).")
		public String customerNumber;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Unique file name for the file to upload.")
		public String fileName;

		@JsonProperty(required = true)
		@JsonPropertyDescription("The type of the document to be uploaded; the tool trusts you to provide the right type and it is **NOT** performing any check on the correctness of provided type.")
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

		String fileName = getString("fileName", args);
		if (fileName == null)
			return new ToolCallResult(call, "ERROR: You must provide name of file to upload.");

		String fileContent = ScenarioComponent.getInstance().get(getScenarioId(), Peace.GetFileContentApi.ID, args);
		if (fileContent.toLowerCase().contains("error"))
			return new ToolCallResult(call, "ERROR: File " + fileName + " seems not to exist.");

		String documentType = getString("documentType", args);
		switch (documentType) {
		case "SKS":
			getExecutionContext().getSKS().put(customerNumber, fileContent);
			break;
		case "POWER_OF_ATTORNEY":
			getExecutionContext().getPoA().put(customerNumber, fileContent);
			break;
		case "PROFORMA_DOCUMENT":
			getExecutionContext().getProformaDocument().put(customerNumber, fileContent);
			break;
		case "ID":
			getExecutionContext().getProformaDocument().put(customerNumber, fileContent);
			break;
		default:
			return new ToolCallResult(call, "ERROR: Invalid document type: " + documentType);
		}
		getExecutionContext().log(new UploadEntry(customerNumber, documentType, fileContent));

		return new ToolCallResult(call, "File was successfully uploaded.");
	}

	public Capt() {

		super("CAPT", //
				"This tool allows uploading files like Proforma Document, Power of Attorney document (PoA), and Probate Certificate (SKS), and persons' IDs, that are then made available to other applications. "
						+ "**STRICTLY** do not use this tool to check the type of a document.",
				Parameters.class);
	}
}