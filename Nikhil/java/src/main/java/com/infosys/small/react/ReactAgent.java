package com.infosys.small.react;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.fasterxml.jackson.annotation.JsonView;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.infosys.small.core.Agent;
import com.infosys.small.core.Tool;
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDescription;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.NonNull;
import lombok.Setter;

/**
 * This implements a generic ReAct agent.
 */
public class ReactAgent extends Agent {

	public static final String DEFAULT_MODEL = "gpt-4.1";
//	public static final String DEFAULT_MODEL = "gpt-4o";
//	public static final String DEFAULT_MODEL = "o3";

	/**
	 * Base class for {@link Tool} parameters for those tools that are available to
	 * a ReAct agent. They must all accept at least a thought parameter.
	 */
	@NoArgsConstructor
	public static class Parameters {

		@JsonProperty(required = true)
		@JsonPropertyDescription("Your reasoning about why this tool has been called.")
		public @NonNull String thought;
	}

	@NoArgsConstructor
	@JsonSchemaDescription("This represent the final execution step performed by a ReAct agent.")
	public static class Step {

		// ** Strictly ignore this when translating into Python
		public static class Views {
			public interface Compact {
			}

			public interface Complete extends Compact {
			}
		}

		public enum Status {
			IN_PROGRESS, COMPLETED, ERROR
		};

		@JsonPropertyDescription("If you finish the execution or you experience an unrecoverable error, set this to either COMPLETED or ERROR respectively.")
		@JsonView(Views.Compact.class)
		public Status status;

		// Do not remove it's OK it stays here
		@JsonPropertyDescription("The tool or agent that executed this step. This is provided automatically, so you do not need to output it.")
		@JsonView(Views.Compact.class)
		public @NonNull String actor;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Your reasoning about why and how accomplish this step.")
		@JsonView(Views.Compact.class)
		public @NonNull String thought;

		@JsonProperty(required = true)
		@JsonPropertyDescription("Any additional data, like step outcomes, error messages, etc..")
		@JsonView(Views.Compact.class)
		public @NonNull String observation;

		// Private constructor to force use of the builder
		private Step(Builder builder) {
			this.status = builder.status;
			this.actor = Objects.requireNonNull(builder.actor, "id must not be null");
			this.thought = Objects.requireNonNull(builder.thought, "thought must not be null");
			this.observation = Objects.requireNonNull(builder.observation, "observation must not be null");
		}

		/**
		 * Builder for Step.
		 */
		public static class Builder {
			private Status status;
			private String actor;
			private String thought;
			private String observation;

			public Builder status(Status status) {
				this.status = status;
				return this;
			}

			public Builder actor(@NonNull String actor) {
				this.actor = actor;
				return this;
			}

			public Builder thought(@NonNull String thought) {
				this.thought = thought;
				return this;
			}

			public Builder observation(@NonNull String observation) {
				this.observation = observation;
				return this;
			}

			public Step build() {
				return new Step(this);
			}
		}
	}

	@NoArgsConstructor
	@JsonSchemaDescription("This extends execution step to cover function calls")
	public static class ToolCallStep extends Step {

		@JsonProperty(required = true)
		@JsonPropertyDescription("The action that was taken at this step. It is typically a tool invocation.")
		@JsonView(Views.Compact.class)
		public @NonNull String action;

		@JsonProperty(required = true, value = "action_input")
		@JsonPropertyDescription("Input for the action.")
		@JsonView(Views.Compact.class)
		public @NonNull String actionInput;

		@JsonProperty(required = true, value = "action_steps")
		@JsonPropertyDescription("In case the action for this step was delegated to another agent, this is the list of steps that agent performed to complete the action.")
		@JsonView(Views.Complete.class)
		public @NonNull List<Step> actionSteps;

		private ToolCallStep(Builder builder) {
			super(builder);
			this.action = Objects.requireNonNull(builder.action, "action must not be null");
			this.actionInput = Objects.requireNonNull(builder.actionInput, "actionInput must not be null");
			this.actionSteps = new ArrayList<>(builder.actionSteps);
		}

		/**
		 * Builder for ToolCallStep.
		 */
		public static class Builder extends Step.Builder {
			private String action;
			private String actionInput;
			public List<Step> actionSteps = new ArrayList<>();

			@Override
			public Builder status(Status status) {
				return (Builder) super.status(status);
			}

			@Override
			public Builder actor(@NonNull String actor) {
				return (Builder) super.actor(actor);
			}

			@Override
			public Builder thought(@NonNull String thought) {
				return (Builder) super.thought(thought);
			}

			@Override
			public Builder observation(@NonNull String observation) {
				return (Builder) super.observation(observation);
			}

			public Builder action(@NonNull String action) {
				this.action = action;
				return this;
			}

			public Builder actionInput(@NonNull String actionInput) {
				this.actionInput = actionInput;
				return this;
			}

			public Builder actionSteps(@NonNull List<? extends Step> steps) {
				this.actionSteps = new ArrayList<>(steps);
				return this;
			}

			public Builder addAllSteps(@NonNull List<? extends Step> steps) {
				this.actionSteps.addAll(steps);
				return this;
			}

			public Builder addStep(@NonNull Step step) {
				this.actionSteps.add(step);
				return this;
			}

			@Override
			public ToolCallStep build() {
				return new ToolCallStep(this);
			}
		}
	}

	/**
	 * Any additional context you want to provide to the agent.
	 */
	@Getter
	@Setter
	private @NonNull String context = "";

	/**
	 * Any additional examples you want to provide to the agent.
	 */
	@Getter
	@Setter
	private @NonNull String examples = "";

	/**
	 * The list of steps executed so far while executing current command.
	 */
	@Getter
	private final @NonNull List<Step> steps = new ArrayList<>();

	/**
	 * @return Last step so far (or null).
	 */
	public Step getLastStep() {
		return (steps.size() == 0) ? null : steps.get(steps.size() - 1);
	}

	/**
	 * Adds one step to the list of execution steps.
	 */
	void addStep(Step step) {
		steps.add(step);

		// TODO Write step into the database, if a link to the database is provided
	}

	@Getter(AccessLevel.PROTECTED)
	private final @NonNull ExecutorModule executor;

	@Getter(AccessLevel.PROTECTED)
	private final @NonNull CriticModule reviewer;

	// TODO Make it a wrapper of another agent instead? A lot of code forwarding...

	public ReactAgent(@NonNull String id, @NonNull String description, @NonNull List<? extends Tool> tools,
			boolean checkLastStep) {

		// Only executor is using tools
		super(id, description, new ArrayList<>());
		setModel(DEFAULT_MODEL);
		setTemperature(0d);

		this.executor = new ExecutorModule(this, tools, checkLastStep, DEFAULT_MODEL);
		this.reviewer = new CriticModule(this, tools, DEFAULT_MODEL);
	}

	public Step execute(@NonNull String command) throws JsonProcessingException {
		return executor.execute(command);
	}
}
