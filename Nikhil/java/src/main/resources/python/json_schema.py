from __future__ import annotations

import json
from typing import Type, TypeVar
from pydantic import BaseModel, TypeAdapter

T = TypeVar("T", bound=BaseModel)

class JsonSchema:
    """
    Python version of the Java JsonSchema utility class.
    Provides methods for:
    1. Getting a JSON schema from a Pydantic model.
    2. Serializing a Pydantic model instance to JSON.
    3. Deserializing a JSON string to a Pydantic model instance.
    """

    @staticmethod
    def get_json_schema(cls: type[BaseModel]) -> str:
        """
        Returns the JSON schema (draft-07) for the given Pydantic model class.

        Args:
            cls: The Pydantic model class.

        Returns:
            A string containing the JSON schema for the class.
        """
        return json.dumps(cls.model_json_schema(), separators=(",", ":"))

    @staticmethod
    def serialize(obj: BaseModel) -> str:
        """
        Serializes a Pydantic model instance to a JSON string, omitting fields whose value is None.

        Args:
            obj: The Pydantic model instance.

        Returns:
            The JSON string representation of the model.
        """
        return obj.model_dump_json(exclude_none=True)

    @staticmethod
    def deserialize(json_str: str, cls: Type[T]) -> T:
        """
        Deserializes a JSON string into an instance of the specified Pydantic model class,
        ignoring unknown fields.

        Args:
            json_str: The JSON string to deserialize.
            cls: The Pydantic model class.

        Returns:
            An instance of the specified model class.
        """
        adapter = TypeAdapter(cls)
        return adapter.validate_json(json_str, strict=False)
