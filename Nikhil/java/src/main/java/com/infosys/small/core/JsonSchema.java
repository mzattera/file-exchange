package com.infosys.small.core;

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
	public static final ObjectMapper JSON_MAPPER;
	static {
		JSON_MAPPER = new ObjectMapper();
		JSON_MAPPER.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
		JSON_MAPPER.setSerializationInclusion(JsonInclude.Include.NON_NULL);
	}

	/**
	 * @return JSON schema for the class c.
	 * @throws JsonProcessingException
	 */
	//	** STRICTLY** Translate this method into Python as:
	//    @staticmethod
	//    def get_json_schema(cls: type[BaseModel]) -> str:
	//        """
	//        Returns the JSON schema (draft-07) for the given Pydantic model class.
	//
	//        Args:
	//            cls: The Pydantic model class.
	//
	//        Returns:
	//            A string containing the JSON schema for the class.
	//        """
	//        return json.dumps(cls.model_json_schema(), separators=(",", ":"))
	public static <T> String getJsonSchema(Class<T> c) {
		try {
			return JSON_MAPPER.writeValueAsString(SCHEMA_GENERATOR.generateJsonSchema(c));
		} catch (JsonProcessingException e) {
			return null; // Should never happen
		}
	}

	/**
	 * @return The Object o serialised as a JSON string.
	 */
	//	** STRICTLY** Translate this method into Python as:
	//    @staticmethod
	//    def serialize(obj: BaseModel) -> str:
	//        """
	//        Serializes a Pydantic model instance to a JSON string, omitting fields whose value is None.
	//
	//        Args:
	//            obj: The Pydantic model instance.
	//
	//        Returns:
	//            The JSON string representation of the model.
	//        """
	//        return obj.model_dump_json(exclude_none=True)
	public static <T> String serialize(Object o) throws JsonProcessingException {
		return JSON_MAPPER.writeValueAsString(o);
	}

//	** STRICTLY** Translate the two deserialize() methods below into Python as a single function:
//	@staticmethod
//	def deserialize(json_str: str, cls: Type[T]) -> T:
//	    """
//	    Deserializes a JSON string into an instance of the specified Pydantic model class,
//	    ignoring unknown fields.
//	
//	    Args:
//	        json_str: The JSON string to deserialize.
//	        cls: The Pydantic model class.
//	
//	    Returns:
//	        An instance of the specified model class.
//	    """
//	    adapter = TypeAdapter(cls)
//	    return adapter.validate_json(json_str, strict=False)			
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
	
	/**
	 * Serializes given object to JSON and returns a pretty formatted string representation.
	 */
	public static String prettyPrint(Object o) {
		
		// When translating this into Python **MUST USE** use json.dumps(o, indent=4, sort_keys=True)
		
		try {
			return JSON_MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(o);
		} catch (JsonProcessingException e) {
			return null;
		}
	}
}