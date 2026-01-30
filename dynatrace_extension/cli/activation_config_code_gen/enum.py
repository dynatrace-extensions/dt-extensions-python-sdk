from typing import Literal

import pydantic

from . import documented, imports, utils


class EnumValue(documented.Documented):
    value: str
    """Persisted value for the enum item"""

    def generate(self) -> str:
        return utils.quote_wrap(self.value)


class EnumType(documented.Documented):
    type: Literal["enum"] = "enum"
    """The type of the referable object."""

    items: list[EnumValue]
    """Mapping from enum values to displayName."""

    def _generate_type(self, imports: imports.Imports) -> str:
        items = ", ".join(item.generate() for item in self.items)

        if items:
            imports.add("typing", "Literal")

            return f"Literal[{items}]"

        return "str"

    def generate(self, name: str, imports: imports.Imports) -> str:
        name = utils.get_class_name(f"{name}_enum")
        definition = f"{name} = {self._generate_type(imports)}"
        docs = self.generate_docs()

        return "\n".join(item for item in (definition, docs) if item)


class Enums(pydantic.RootModel[dict[str, EnumType]]):
    def generate(self, imports: imports.Imports) -> str:
        return "\n\n".join(
            enum.generate(name, imports) for name, enum in self.root.items()
        )
