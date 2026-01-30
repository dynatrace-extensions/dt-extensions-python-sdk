from typing import Literal

import pydantic

from . import documented, imports, schema_type, utils
from . import property as prop


class ComplexType(documented.Documented):
    type: Literal["object"] = "object"
    """The type of the referable object."""

    properties: prop.Properties
    """The properties this type is constructed of."""

    def generate(self, name: str, imports: imports.Imports) -> str:
        name = utils.get_class_name(f"{name}_model")
        docs = self.generate_docs()
        properties = self.properties.generate(imports)
        body = "\n\n".join(item for item in (docs, properties) if item) or "pass"

        imports.add("pydantic")

        return f"class {name}({schema_type.BASE_MODEL}):\n{utils.indent(body)}"


class ComplexTypes(pydantic.RootModel[dict[str, ComplexType]]):
    def generate(self, imports: imports.Imports) -> str:
        return "\n\n\n".join(complex_type.generate(name, imports) for name, complex_type in self.root.items())
