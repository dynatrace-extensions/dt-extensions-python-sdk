import pydantic

from . import imports, schema_type, utils


class RefPointer(pydantic.BaseModel):
    ref: str = pydantic.Field(alias="$ref")

    def _is_enum(self) -> bool:
        return self.ref.startswith("#/enums/")

    def generate_default_value(self, value: str) -> dict[str, str]:
        return {schema_type.DEFAULT: value}

    def generate(self, imports: imports.Imports) -> str:  # noqa
        name = self.ref.split("/")[-1]

        if self._is_enum():
            return utils.get_class_name(f"{name}_enum")

        return utils.get_class_name(f"{name}_model")
