import pydantic

from . import constraint, documented, imports, ref, schema_type, utils


class Item(documented.Documented):
    type: schema_type.SchemaType | ref.RefPointer
    """Datatype of the property."""

    constraints: constraint.Constraints = pydantic.Field(default_factory=lambda: constraint.Constraints([]))
    """Validation constraints the list/set item value must fulfill to be persistable."""

    def _generate_type(self, imports: imports.Imports) -> str:
        item_type = self.type.generate(imports)

        if isinstance(self.type, ref.RefPointer):
            return utils.quote_wrap(item_type)

        return item_type

    def generate(self, imports: imports.Imports) -> str:
        item_type = self._generate_type(imports)
        constraints = self.constraints.generate()

        if constraints:
            imports.add("typing", "Annotated")

            return f"Annotated[{item_type}, {constraints.generate(imports)}]"

        return item_type
