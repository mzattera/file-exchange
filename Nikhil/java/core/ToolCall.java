package core;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import lombok.ToString;

/**
 * {@link Agent}s can invoke tools. This interface represents a single tool
 * invocation, as part of a message.
 * 
 * @author Massimiliano "Maxi" Zattera
 *
 */
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@RequiredArgsConstructor
@Getter
@Setter
@ToString
public class ToolCall implements MessagePart {

	/**
	 * Builder
	 * 
	 * @author Luna
	 */
	public static final class Builder {
		private String id;
		private Tool tool;
		private Map<String, Object> arguments = new HashMap<>();

		public Builder id(@NonNull String id) {
			this.id = id;
			return this;
		}

		public Builder tool(@NonNull Tool tool) {
			this.tool = tool;
			return this;
		}

		/** Accepts any map whose values extend Object. */
		public Builder arguments(@NonNull Map<String, ? extends Object> args) {
			this.arguments = new HashMap<>(args);
			return this;
		}

		/**
		 * Parse a JSON string into the arguments map.
		 * 
		 * @throws JsonProcessingException
		 */
		public Builder arguments(@NonNull String json) throws JsonProcessingException {

			this.arguments = JsonSchema.deserialize(json, new TypeReference<Map<String, Object>>() {
			});
			return this;
		}

		public ToolCall build() {
			ToolCall tc = new ToolCall();
			tc.setId(Objects.requireNonNull(id, "id must not be null"));
			tc.setTool(Objects.requireNonNull(tool, "tool must not be null"));
			tc.setArguments(arguments);
			return tc;
		}
	}

	public static Builder builder() {
		return new Builder();
	}
	
	/**
	 * Unique ID for this tool call.
	 */
	@NonNull
	private String id;

	/**
	 * The tool being called. Notice it is not always guaranteed this to be set
	 * correctly, as some services might not be able to retrieve the proper Tool
	 * instance; this depends on the service generating the call. If this field is
	 * null, developers need to map this call to the proper tool externally from the
	 * service.
	 */
	private Tool tool;

	/**
	 * Arguments to use in the call, as name/value pairs.
	 */
	@NonNull
	private Map<String, Object> arguments = new HashMap<>();

	@Override
	public String getContent() {
		return toString();
	}

	/**
	 * Executes this call. Notice this will work only if {{@link #getTool()} returns
	 * a valid tool.
	 * 
	 * @return Result of invoking the tool.
	 * @throws Exception If an error occurs while executing the call.
	 */
	public ToolCallResult execute() throws Exception {
		return getTool().invoke(this);
	}
}
