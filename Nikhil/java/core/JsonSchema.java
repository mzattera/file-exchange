package core;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kjetland.jackson.jsonSchema.JsonSchemaGenerator;

/**
 * The class provide methods to :
 * 
 * 1. Obtain a JSON schema from a class.
 * 
 * 2. Serialise an instance of a class into JSON.
 * 
 * 3. De-serialise the JSON representation of a class.
 *
 * The class fully supports Jackson annotations when creating a schema fro a
 * class.
 * 
 * @see <a href=
 *      "https://json-schema.org/understanding-json-schema">Understanding JSON
 *      Schema</a>
 * 
 * @author Massimiliano "Maxi" Zattera
 */
public class JsonSchema {

	/** Used for creating JSON schema out of classes */
	private final static JsonSchemaGenerator SCHEMA_GENERATOR = new JsonSchemaGenerator(new ObjectMapper());

	/**
	 * Mapper provided for JSON serialisation via Jackson, if needed. Use this to
	 * deserialized objects that have been created through some schema.
	 */
	private static final ObjectMapper JSON_MAPPER;
	static {
		JSON_MAPPER = new ObjectMapper();
		JSON_MAPPER.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
		JSON_MAPPER.setSerializationInclusion(JsonInclude.Include.NON_NULL);
	}

	// The below method uses JsonSchemaGenerator and Jacksoon annotations to create
	// a JSON schema fro the class. Use pydantic and its annotations to achieve same
	// result.
	
	/**
	 * @return JSON schema for the class c.
	 * @throws JsonProcessingException
	 */
	public static <T> String getJsonSchema(Class<T> c) {
		try {
			return JSON_MAPPER.writeValueAsString(SCHEMA_GENERATOR.generateJsonSchema(c));
		} catch (JsonProcessingException e) {
			return null; // Should never happen
		}
	}

	// Below Java methods can easily be translated in Python by using pydantic:
	//
	// from typing import Type, TypeVar
	// from pydantic import BaseModel
	//
	// T = TypeVar("T", bound=BaseModel)
	//
	//
	// # ---------- generic helpers ----------
	// def serialize(obj: BaseModel) -> str:
	// """Return *obj* as a JSON string, omitting fields whose value is None."""
	// return obj.json(exclude_none=True)
	//
	//
	// def deserialize(json_str: str, cls: Type[T]) -> T:
	// """Parse *json_str* into an instance of *cls*, ignoring unknown keys."""
	// return cls.parse_raw(json_str)
	// # -------------------------------------

	/**
	 * @return The Object o serialised as a JSON string.
	 */
	public static <T> String serialize(Object o) throws JsonProcessingException {
		return JSON_MAPPER.writeValueAsString(o);
	}

	/**
	 * @param json An object of type T serialised using JSON.
	 * @return An instance of T, corresponding to the object that is provided as
	 *         JSON object.
	 * @throws JsonProcessingException
	 * @throws JsonMappingException
	 */
	public static <T> T deserialize(String json, Class<T> c) throws JsonProcessingException {
		return JSON_MAPPER.readValue(json, c);
	}

	/**
	 * @param json An object of type T serialised using JSON.
	 * @return An instance of T, corresponding to the object that is provided as
	 *         JSON object.
	 */
	public static <T> T deserialize(String json, TypeReference<T> c) throws JsonProcessingException {
		return JSON_MAPPER.readValue(json, c);
	}

	public static void main(String[] args) {
		System.out.println(JsonSchema.getJsonSchema(FunctionCallExample.GetCurrentWeatherTool.Parameters.class));
	}
}