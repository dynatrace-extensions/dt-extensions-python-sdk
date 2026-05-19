from typing import Any

from . import activation_schema


def generate_types(schema: dict[str, Any]) -> str:
    """
    Generates the types for a given activation schema

    :param schema: The raw activation schema
    :type schema: dict[str, Any]
    """
    return activation_schema.ActivationSchema(**schema).generate()
