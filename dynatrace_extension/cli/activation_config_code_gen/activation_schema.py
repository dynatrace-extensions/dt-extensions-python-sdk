"""Contains the ActivationSchema model"""

from typing import Annotated, Literal

import pydantic

from . import complex_type, documented, enum
from . import imports as _imports
from . import property as prop

DISCLAIMER = '''\
"""
Contains the ActivationConfig models

This file has been auto-generated, do not modify directly
"""'''


class ActivationSchema(documented.Documented):
    enums: enum.Enums = pydantic.Field(default_factory=lambda: enum.Enums({}))
    """Custom enums that can be referenced by properties."""

    properties: prop.Properties
    """The properties this config is constructed of."""

    dynatrace: Literal["1"] = pydantic.Field(pattern=r"^\d+(\.\d+)*$")
    """The Dynatrace API level."""

    allowed_scopes: list[Annotated[str, pydantic.Field(min_length=1)]] = pydantic.Field(
        alias="allowedScopes", min_length=1, default_factory=lambda: ["tenant"]
    )
    """The scope classes for which a setting value can be persisted."""

    schema_id: str = pydantic.Field(alias="schemaId")
    """The unique identifier for this schema."""

    owner_development: str = pydantic.Field(alias="ownerDevelopment", min_length=1)
    """The person responsible for the schema structure."""

    maturity: Literal["IN_DEVELOPMENT", "PREVIEW", "EARLY_ADOPTER", "GENERAL_AVAILABILITY"] = "GENERAL_AVAILABILITY"
    """Maturity of the settings topic"""

    types: complex_type.ComplexTypes = pydantic.Field(default_factory=lambda: complex_type.ComplexTypes({}))
    """Custom types that can be referenced by properties."""

    def generate(self) -> str:
        imports = _imports.Imports()
        enums = self.enums.generate(imports)
        types = self.types.generate(imports)
        activation_config = complex_type.ComplexType(
            description=self.description,
            displayName=self.display_name,
            documentation=self.documentation,
            properties=self.properties,
        ).generate("activation_config", imports)
        imports_gen = imports.generate()
        body = "\n\n\n".join(item for item in (DISCLAIMER, imports_gen, enums, types, activation_config) if item)

        return f"{body}\n"
