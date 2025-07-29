package com.infosys.small.core;

import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import lombok.ToString;
import lombok.experimental.SuperBuilder;

/**
 * This holds the results of a {@link ToolCall}. It is used to pass results from
 * tool execution back to the calling agent.
 * 
 * @author Massimiliano "Maxi" Zattera.
 *
 */
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@RequiredArgsConstructor
@SuperBuilder
@Getter
@Setter
@ToString
public class ToolCallResult implements MessagePart {

	/** Unique ID for corresponding tool invocation. */
	@NonNull
	private String toolCallId;

	/** Unique ID of the tool being called. */
	// TODO Needed?
	@NonNull
	private String toolId;

	/** Result of calling the tool. */
	private String result;

	/** True if the result is an error. */
	@Builder.Default
	private boolean isError = false;

	public ToolCallResult(@NonNull ToolCall call, String result) {
		toolCallId = call.getId();
		toolId = call.getTool().getId();
		this.result = result;
	}

	public ToolCallResult(String toolCallId, String toolId, String result) {
		this.toolCallId = toolCallId;
		this.toolId = toolId;
		this.result = result;
	}
	
	public ToolCallResult(ToolCall call, Exception e) {
		this(call, "Error: " + e.getMessage());
		isError = true;
	}

	@Override
	public String getContent() {
		return ("ToolCallResult(" + (isError ? "*ERROR* " : "") + (result == null ? "" : result.toString()) + ")");
	}

}
