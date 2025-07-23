package core;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.core.JsonMissing;
import com.openai.models.FunctionDefinition;
import com.openai.models.FunctionParameters;
import com.openai.models.ResponseFormatJsonSchema;
import com.openai.models.ResponseFormatJsonSchema.JsonSchema.Schema;
import com.openai.models.chat.completions.ChatCompletionAssistantMessageParam;
import com.openai.models.chat.completions.ChatCompletionAssistantMessageParam.Builder;
import com.openai.models.chat.completions.ChatCompletionCreateParams;
import com.openai.models.chat.completions.ChatCompletionCreateParams.ResponseFormat;
import com.openai.models.chat.completions.ChatCompletionDeveloperMessageParam;
import com.openai.models.chat.completions.ChatCompletionMessage;
import com.openai.models.chat.completions.ChatCompletionMessageParam;
import com.openai.models.chat.completions.ChatCompletionMessageToolCall;
import com.openai.models.chat.completions.ChatCompletionMessageToolCall.Function;
import com.openai.models.chat.completions.ChatCompletionTool;
import com.openai.models.chat.completions.ChatCompletionToolMessageParam;
import com.openai.models.chat.completions.ChatCompletionUserMessageParam;

import lombok.Getter;
import lombok.NonNull;
import lombok.Setter;

/**
 * This class implements an Agent that uses OpenAI models via the Chat
 * Completions API. This class is implemented using the OpenAI Java SDK.
 * 
 * @author Massimiliano "Maxi" Zattera
 */
public class Agent {

	private final static Logger LOG = LoggerFactory.getLogger(Agent.class);

	public static final String DEFAULT_MODEL = "gpt-4.1";

	protected Agent() {
		this("OpenAIChatCompletionService", "Test agent", new ArrayList<>());
	}

	protected Agent(@NonNull String id, @NonNull String description, @NonNull List<? extends Tool> tools) {
		this.client = OpenAIOkHttpClient.fromEnv();
		this.id = id;
		this.description = description;
		for (Tool t : tools) {
			t.init(this);
			toolMap.put(t.getId(), t);
		}
		this.model = DEFAULT_MODEL;
		this.temperature = 0.0d;
	}

	/**
	 * This class uses an OpenAIClient to call the OpenAI API. In python you do not
	 * need a client; you can omit this field and use openai intead.
	 * 
	 * E.g. instead of:
	 * 
	 * client.chat().completions().create(req);
	 * 
	 * In Python use:
	 * 
	 * import openai
	 * 
	 * openai.ChatCompletion.create(**req)
	 */
	protected final OpenAIClient client;

	/**
	 * Unique agent ID.
	 */
	@Getter
	private final String id;

	/**
	 * A verbose description of the agent, describing its capabilities.
	 */
	@Getter
	@Setter
	private String description;

	/**
	 * The name of the LLM model used by this agent (e.g. "gpt-4").
	 */
	@Getter
	@Setter
	private String model;

	/**
	 * Personality (system prompt) for the agent.
	 */
	@Getter
	@Setter
	private String personality;

	/**
	 * Messages exchanged so far in current conversation with the agent.
	 */
	@Getter
	private final List<ChatMessage> history = new ArrayList<>();

	/**
	 * The temperature of the sampling operation for the underlying LLM.
	 */
	@Getter
	@Setter
	private Double temperature = 0d;

	/**
	 * Starts a new chat, clearing current conversation.
	 */
	public void clearConversation() {
		history.clear();
	}

	/**
	 * Maximum number of messages to keep in chat history.
	 */
	@Getter
	@Setter
	private int maxHistoryLength = Integer.MAX_VALUE;

	/**
	 * Maximum number of history messages to send to LLM during a conversation.
	 * 
	 * Notice this does NOT limit length of conversation history (see
	 * {@link #getMaxHistoryLength}).
	 */
	@Getter
	@Setter
	private int maxConversationSteps = Integer.MAX_VALUE;

	/**
	 * Output format for the model, as JSON schema.
	 */
	@Getter
	private String responseFormat;

	/**
	 * This method allows to specify an output format for the model. This is used to
	 * create structured outputs with model supporting it so that, for example, the
	 * model returns its responses in a pre-defined JSON format.
	 * 
	 * @param schema A class which schema will be used to define the output format.
	 */
	public void setResponseFormat(Class<?> schema) {
		responseFormat = JsonSchema.getJsonSchema(schema);
	}

	/**
	 * Available and already initialized tools that agent can use. Maps each tool ID
	 * into corresponding tool instance.
	 */
	protected Map<String, Tool> toolMap = new HashMap<>();

	/**
	 * Continues current chat, with the provided message.
	 * 
	 * The exchange is added to the conversation history.
	 */
	public ChatCompletion chat(String msg) {
		return chat(new ChatMessage(ChatMessage.Author.USER, msg));

	}

	/**
	 * Continues current chat, with the provided message.
	 * 
	 * The exchange is added to the conversation history.
	 */
	public ChatCompletion chat(ChatMessage msg) {
		return chat(List.of(msg));
	}

	/**
	 * Continues current chat, with the provided messages.
	 * 
	 * The exchange is added to the conversation history.
	 */
	public ChatCompletion chat(List<ChatMessage> msg) {

		// Add messages to conversation and trims it; this also adds personality
		List<ChatMessage> conversation = new ArrayList<>(getHistory());
		conversation.addAll(msg);
		trimConversation(conversation);

		// Create response
		ChatCompletion result = chatCompletion(conversation);

		// Add messages and response to history
		getHistory().addAll(msg);
		getHistory().add(result.getMessage());

		// Make sure history is of desired length
		if (getHistory().size() > getMaxHistoryLength()) {
			getHistory().subList(0, getHistory().size() - getMaxHistoryLength()).clear();
		}

		return result;
	}

	/**
	 * Completes text outside a conversation (executes given prompt ignoring and
	 * without affecting conversation history).
	 * 
	 * Notice this does not consider or affects chat history but bot personality is
	 * used, if provided.
	 */
	public ChatCompletion complete(String prompt) {
		return complete(new ChatMessage(ChatMessage.Author.USER, prompt));
	}

	/**
	 * Completes text outside a conversation (executes given prompt ignoring and
	 * without affecting conversation history).
	 * 
	 * Notice this does not consider or affects chat history but bot personality is
	 * used, if provided.
	 */
	public ChatCompletion complete(ChatMessage prompt) {

		List<ChatMessage> conversation = List.of(prompt);
		trimConversation(conversation);

		return chatCompletion(conversation);
	}

	/**
	 * Trims given list of messages (typically a conversation history), so it fits
	 * the limits set in this instance (that is, maximum conversation steps).
	 * 
	 * Notice the personality (system prompt) is always and automatically added on
	 * top of the trimmed list (if set).
	 * 
	 * @throws IllegalArgumentException if no message can be added because of
	 *                                  context size limitations.
	 */
	private void trimConversation(List<ChatMessage> messages) {

		// Remove tool call results left on top without corresponding calls, or this
		// will cause HTTP 400 error for tools
		int firstNonToolIndex = 0;
		for (ChatMessage m : messages) {
			if (m.hasToolCallResults()) {
				firstNonToolIndex++;
			} else {
				break;
			}
		}
		if (firstNonToolIndex > 0) {
			messages.subList(0, firstNonToolIndex).clear();
		}

		// Trims down the list of messages accordingly to given limits.
		if (messages.size() > getMaxConversationSteps())
			messages.subList(0, messages.size() - getMaxConversationSteps()).clear();

		if (messages.size() == 0)
			throw new IllegalArgumentException("No messages left in conversation");

		if (getPersonality() != null)
			// must add a system message on top with personality
			messages.add(0, new ChatMessage(ChatMessage.Author.DEVELOPER, getPersonality()));
	}

	/**
	 * This method sends given list of messages to the LLM and creates corresponding
	 * chat response, which is returned.
	 */
	@SuppressWarnings("unchecked")
	private ChatCompletion chatCompletion(List<ChatMessage> messages) {

		// The method starts by building required ChatCompletionCreateParams instance to
		// call the OpenAI chat API.
		// When translating this into Python you should be a request req that is then
		// sent to openai.ChatCompletion.create(**req)

		// Translate messages into format suitable to be used with OpenAI API
		// Here each ChatMessage is translated into the corresponding
		// ChatCompletionMessageParam.
		List<ChatCompletionMessageParam> openAiMessages = new ArrayList<>();
		for (ChatMessage m : messages)
			openAiMessages.addAll(fromChatMessage(m));

		// ThHere we use a Builder to build ChatCompletionCreateParams step by step
		// Notice that here we set the model, the messages and the temperature
		// With OpenAI Java SDK, messages must be a list of ChatCompletionMessageParam
		// but in Python you might build them differently as part of req; check what
		// fromChatMessage() does
		ChatCompletionCreateParams.Builder b = ChatCompletionCreateParams.builder() //
				.model(getModel()) //
				.messages(openAiMessages) //
				.temperature(getTemperature());

		// Only if response format was set, provide it; check what
		// createResponseFormat() does
		if (getResponseFormat() == null)
			b.responseFormat(JsonMissing.of());
		else
			b.responseFormat(createResponseFormat());

		// If there is any tool, provide them in req; check what createToolDefinitions()
		// does
		if (toolMap.size() == 0)
			b.tools(JsonMissing.of());
		else
			b.tools(createToolDefinitions());
		ChatCompletionCreateParams req = b.build();

		LOG.info(req.toString());

		// Calls OpenAI Chat Completion API and returns result
		com.openai.models.chat.completions.ChatCompletion resp = client.chat().completions().create(req);
		com.openai.models.chat.completions.ChatCompletion.Choice choice = resp.choices().get(0);
		return new ChatCompletion(fromOpenAiApi(choice.finishReason()), fromOpenAiMessage(choice.message()));
	}

	/**
	 * Translates Java OpenAI SDK finish reason into one we can use.
	 */
	private static ChatCompletion.FinishReason fromOpenAiApi(
			com.openai.models.chat.completions.ChatCompletion.Choice.FinishReason finishReason) {
		switch (finishReason.value()) {
		case STOP:
		case TOOL_CALLS:
		case FUNCTION_CALL:
			return ChatCompletion.FinishReason.COMPLETED;
		case LENGTH:
			return ChatCompletion.FinishReason.TRUNCATED;
		case CONTENT_FILTER:
			return ChatCompletion.FinishReason.INAPPROPRIATE;
		default:
			throw new IllegalArgumentException("Unrecognized finish reason: " + finishReason);
		}
	}

	/**
	 * Turns an ChatCompletionMessageParam returned by API into a ChatMessage. This
	 * is required because we want to return ChatMessage objects and store them as
	 * such in the history.
	 */
	private ChatMessage fromOpenAiMessage(ChatCompletionMessage msg) {

		if (msg.toolCalls().isPresent()) {

			// The model returned a set of tool calls, transparently translate that into a
			// message with a multiple parts each being a ToolCall
			List<ToolCall> calls = new ArrayList<>();
			for (ChatCompletionMessageToolCall call : msg.toolCalls().get()) {
				ToolCall toolCall;
				try {
					toolCall = ToolCall.builder() //
							.id(call.id()) //
							.tool(toolMap.get(call.function().name())) //
							.arguments(call.function().arguments()) //
							.build();
				} catch (JsonProcessingException e) {
					throw new IllegalArgumentException(e);
				}
				calls.add(toolCall);
			}

			// Nothing else to return in this case
			return new ChatMessage(ChatMessage.Author.BOT, calls);
		}

		List<MessagePart> parts = new ArrayList<>();
		if (msg.content().isPresent()) {
			// Normal (text) message was returned, just add it as TextPart
			parts.add(new TextPart(msg.content().get()));
		}
		if (msg.refusal().isPresent()) {
			// OpenAI returned a refusal; translate it into a text message and attach it as
			// TextPart
			parts.add(new TextPart("**The model generated a refusal**\n\n" + msg.refusal().get()));
		}

		// Return a message with all the parts we found
		return new ChatMessage(ChatMessage.Author.BOT, parts);
	}

	/**
	 * This converts a generic ChatMessaege provided by user into an
	 * ChatCompletionMessageParam that is used for the OpenAi API. This is needed
	 * because we want to deal with ChatMessage when talking to the agent.
	 */
	private List<ChatCompletionMessageParam> fromChatMessage(ChatMessage msg) {

		if (msg.hasToolCalls()) {

			// The message contains tool calls; we translate them into a
			// ChatCompletionAssistantMessageParam which will contain all these calls
			Builder b = ChatCompletionAssistantMessageParam.builder();
			for (ToolCall c : msg.getToolCalls()) {
				try {
					b.addToolCall(ChatCompletionMessageToolCall.builder() //
							.id(c.getId()).function(Function.builder() //
									.name(c.getTool().getId()) //
									.arguments(JsonSchema.serialize(c.getArguments())) //
									.build()) //
							.build());
				} catch (JsonProcessingException e) {
					// Rethrows as runtime exception; in Python you do not need to know since you do
					// not need to declare exceptions in methods
					throw new RuntimeException(e);
				}
			}

			// There is nothing else to return since in this case the message will only have
			// calls.
			return List.of(ChatCompletionMessageParam.ofAssistant(b.build())); //
		}

		if (msg.hasToolCallResults()) {

			// The message contains some call results that we translate into corresponding
			// ChatCompletionMessageParam
			List<ChatCompletionMessageParam> result = new ArrayList<>();
			List<ToolCallResult> results = msg.getToolCallResults();
			for (ToolCallResult r : results) {
				result.add(ChatCompletionMessageParam.ofTool( //
						ChatCompletionToolMessageParam.builder() //
								.content(r.getResult().toString()) //
								.toolCallId(r.getToolCallId()).build() //
				));
			}

			// There is nothing else to return since in this case the message will only have
			// call results.
			return result;
		}

		// In all other cases, we expect a simple text message
		if (msg.isText()) {
			if (msg.getParts().size() != 1)
				throw new IllegalArgumentException(
						"Message can be only be simple text, a tool call, or tool call results");

			// Return corresponding ChatCompletionMessageParam
			switch (msg.getAuthor()) {
			case USER:
				return List.of(ChatCompletionMessageParam.ofUser( //
						ChatCompletionUserMessageParam.builder().content(msg.getTextContent()).build() //
				));
			case DEVELOPER:
				return List.of(ChatCompletionMessageParam.ofDeveloper( //
						ChatCompletionDeveloperMessageParam.builder().content(msg.getTextContent()).build() //
				));
			case BOT:
				return List.of(ChatCompletionMessageParam.ofAssistant( //
						ChatCompletionAssistantMessageParam.builder().content(msg.getTextContent()).build() //
				));
			default:
				throw new IllegalArgumentException("Message author not supported: " + msg.getAuthor());
			}
		}

		throw new IllegalArgumentException("Message can be only be simple text, a tool call, or tool call results");
	}

	/**
	 * @return A ResponseFormat that can be used to create a
	 *         ChatCompletionCreateParams to call OpenAI Chat Completion API.
	 */
	private ChatCompletionCreateParams.ResponseFormat createResponseFormat() {

		try {
			return ResponseFormat.ofJsonSchema( //
					ResponseFormatJsonSchema.builder() //
							.jsonSchema( //
									ResponseFormatJsonSchema.JsonSchema.builder() //
											.name("Anonymous") //
											.description("No Description") //
											.schema(JsonSchema.deserialize(getResponseFormat(), Schema.class)) //
											.build() //
							).build());
		} catch (JsonProcessingException e) {
			// Rethrows as runtime exception; in Python you do not need to know since you do
			// not need to declare exceptions in methods
			throw new RuntimeException(e);
		}
	}

	/**
	 * @return A List<ChatCompletionTool> that can be used to create a
	 *         ChatCompletionCreateParams to call OpenAI Chat Completion API. The
	 *         list will contain definitions for all the tools this agent can use.
	 */
	private List<ChatCompletionTool> createToolDefinitions() {

		List<Tool> tools = new ArrayList<>(toolMap.values());
		List<ChatCompletionTool> tls = new ArrayList<>(tools.size());
		for (Tool t : tools) {
			ChatCompletionTool f;
			try {
				f = ChatCompletionTool.builder() //
						.function( //
								FunctionDefinition.builder() //
										.name(t.getId()) //
										.description(t.getDescription()) //
										.strict(false) //
										.parameters(
												JsonSchema.deserialize(t.getJsonParameters(), FunctionParameters.class))
										.build() //
						).build();
			} catch (JsonProcessingException e) {
				// Rethrows as runtime exception; in Python you do not need to know since you do
				// not need to declare exceptions in methods
				throw new RuntimeException(e);
			}
			tls.add(f);
		}

		return tls;
	}

	/**
	 * Closes the agent freeing up resources.
	 */
	public void close() {
		for (Tool t : toolMap.values()) {
			try {
				t.close();
			} catch (Exception e) {
			}
		}

		try {
			client.close();
		} catch (Exception e) {
		}
	}

	public static class Format {
		@JsonProperty(required = true)
		@JsonPropertyDescription("Your output message")
		public String out;
	}

	public static void main(String[] args) {
		Agent bot = null;
		try {
			bot = new Agent();
			bot.setPersonality(
					"Always output messages as described by this schema: " + JsonSchema.getJsonSchema(Format.class));
			bot.setResponseFormat(Format.class);

			System.out.println(bot.chat("Ciao!").getText());
		} catch (Exception e) {
			e.printStackTrace(System.err);
		} finally {
			if (bot != null)
				try {
					bot.close();
				} catch (Exception e) {
				}
		}
	}
}