package core;

import lombok.NonNull;

/**
 * This is a tool that an {@link Agent} can invoke to perform a task.
 * Tool life cycle involves tool been initialized once before it is called and closed when it is no longer needed.
 * 
 * @author Massimiliano "Maxi" Zattera.
 *
 */
public interface Tool {

	/**
	 * Unique identifier for the tool; this is used as tool ID in API calls normally.
	 * 
	 * @return
	 */
	String getId();

	/**
	 * 
	 * @return A verbose description of what the tool does does, so that the agent
	 *         knows when to call it.
	 */
	String getDescription();

	/**
	 * 
	 * @return JSON Schema describing the parameters for the tool.
	 */
	String getJsonParameters();

	/**
	 * 
	 * @return True if the tool was already initialized.
	 */
	boolean isInitialized();

	/**
	 * 
	 * @return True if the tool was already closed.
	 */
	boolean isClosed();

	/**
	 * This must be called by the agent once and only once before any invocation to
	 * this tool.
	 * 
	 * @param agent The agent that is using this tool.
	 */
	void init(@NonNull Agent agent);

	/**
	 * Invokes (executes) the tool. This can be called several times.
	 * 
	 * @param call The call to the tool, created by the calling agent.
	 * 
	 * @return The result of calling the tool.
	 * 
	 * @param RuntimeException if the tool was not yet initialized.
	 */
	ToolCallResult invoke(@NonNull ToolCall call) throws Exception;
	
	/**
	 * Closes the tool when it is no longer needed.
	 */
    void close() throws Exception;
}