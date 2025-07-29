package com.infosys.small.core;

import com.fasterxml.jackson.core.JsonProcessingException;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import lombok.ToString;
import lombok.experimental.SuperBuilder;

/**
 * This class encapsulates the response from a LLM (as a {@link ChatMessage}).
 * 
 * In addition, this also contains a reason why the response terminated.
 * 
 * @author Massimiliano "Maxi" Zattera.
 */
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@RequiredArgsConstructor
@SuperBuilder
@Getter
@Setter
@ToString
public class ChatCompletion {

	/**
	 * This enumeration describes possible ways in which a language model completed
	 * its output.
	 * 
	 * @author Massimiliano "Maxi" Zattera.
	 */
	public enum FinishReason {

		/**
		 * Text generation is not yet completed, model might be returning a partial
		 * result (e.g. to allow streaming).
		 */
		IN_PROGRESS,

		/**
		 * Text generation has successfully terminated and the text is complete.
		 */
		COMPLETED,

		/**
		 * Text generation is finished, but the text was truncated, probably for
		 * limitations in model output length.
		 */
		TRUNCATED,

		/**
		 * Text content was in part or completely omitted due to content filters (e.g.
		 * profanity filter)
		 */
		INAPPROPRIATE,

		/** All finish reasons that do not fit in any other value */
		OTHER;
	}

	@NonNull
	private FinishReason finishReason;

	@NonNull
	private ChatMessage message;

	/**
	 * 
	 * @return A string representation of the returned message..
	 */
	public String getText() {
		return message.getTextContent();
	}

	/**
	 * 
	 * @return The content of this message as an instance of given class. This
	 *         assumes {@link #getText()} will return a properly formatted JSON
	 *         representation of the object.
	 * 
	 * @throws JsonProcessingException If an error occurs while parsing the message
	 *                                 content.
	 */
	public <T> T getObject(Class<T> c) throws JsonProcessingException {
		return JsonSchema.deserialize(getText(), c);
	}
}
