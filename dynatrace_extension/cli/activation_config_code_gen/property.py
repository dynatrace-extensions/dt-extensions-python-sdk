from typing import Any

import pydantic

from . import constraint, documented, imports, item, ref, schema_type, utils

DefaultValue = str | int | float | bool | None | list[Any]


def generate_default_value(value: DefaultValue) -> str:
    if isinstance(value, str):
        return utils.quote_wrap(value)

    if isinstance(value, list):
        return f"[{', '.join(generate_default_value(item) for item in value)}]"

    return str(value)


class Property(documented.Documented):
    type: schema_type.PropertyType | ref.RefPointer
    """Datatype of the property."""

    items: item.Item | None = None
    """Specification for individual items of a list/set type."""

    constraints: constraint.Constraints = pydantic.Field(default_factory=lambda: constraint.Constraints([]))
    """Validation constraints the property value must fulfill to be persistable."""

    nullable: bool = False
    """Defines if value can be null/omitted."""

    default: DefaultValue = None
    """Value to be used for factory default results."""

    def _generate_type(self, imports: imports.Imports) -> str:
        prop_type = self.type.generate(imports)

        match prop_type:
            case "list" | "set":
                if self.items:
                    inner_type = self.items.generate(imports)
                else:
                    imports.add("typing", "Any")

                    inner_type = "Any"

                prop_type = f"{prop_type}[{inner_type}]"
            case _:
                pass

        if self.nullable:
            prop_type = f"{prop_type} | None"

        if isinstance(self.type, ref.RefPointer):
            return utils.quote_wrap(prop_type)

        return prop_type

    def _generate_default(self, alias: str, imports: imports.Imports) -> str:
        constraints = self.constraints.generate()

        if alias:
            constraints.update(alias=utils.quote_wrap(alias))

        if self.nullable or self.default is not None:
            constraints.update(self.type.generate_default_value(generate_default_value(self.default)))

        return constraints.generate(imports)

    def generate(self, alias: str, imports: imports.Imports) -> str:
        name = utils.get_property_name(alias)
        alias = alias if name != alias else ""

        default = self._generate_default(alias, imports)
        default = f" = {default}" if default else ""

        definition = f"{name}: {self._generate_type(imports)}{default}"

        return "\n".join(item for item in (definition, self.generate_docs()) if item)


class Properties(pydantic.RootModel[dict[str, Property]]):
    def generate(self, imports: imports.Imports) -> str:
        return "\n\n".join(prop.generate(name, imports) for name, prop in self.root.items())
