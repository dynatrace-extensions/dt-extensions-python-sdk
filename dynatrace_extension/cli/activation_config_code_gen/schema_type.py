from typing import Literal

import pydantic

from . import imports

DEFAULT = "default"
DEFAULT_FACTORY = "default_factory"
BASE_MODEL = "pydantic.BaseModel"
FIELD = "pydantic.Field"
SECRET_STR = "pydantic.SecretStr"
ANY_FACTORY = "lambda:"
DATE_FACTORY = f"{ANY_FACTORY} datetime.date.fromisoformat"
TIME_FACTORY = f"{ANY_FACTORY} datetime.time.fromisoformat"
DATE_TIME_FACTORY = f"{ANY_FACTORY} datetime.datetime.fromisoformat"
SECRET_FACTORY = f"{ANY_FACTORY} {SECRET_STR}"


Type = Literal[
    "boolean",
    "integer",
    "float",
    "local_date",
    "local_time",
    "local_date_time",
    "zoned_date_time",
    "time_zone",
    "text",
    "secret",
    "setting",
    "list",
    "set",
]


class SchemaType(pydantic.RootModel[Type]):
    def generate_default_value(self, value: str) -> dict[str, str]:
        if value == "None":
            return {DEFAULT: value}

        match self.root:
            case "local_date":
                return {DEFAULT_FACTORY: f"{DATE_FACTORY}({value})"}
            case "local_time":
                return {DEFAULT_FACTORY: f"{TIME_FACTORY}({value})"}
            case "local_date_time" | "zoned_date_time":
                return {DEFAULT_FACTORY: f"{DATE_TIME_FACTORY}({value})"}
            case "secret":
                return {DEFAULT_FACTORY: f"{SECRET_FACTORY}({value})"}
            case "list":
                return {DEFAULT_FACTORY: f"{ANY_FACTORY} {value}"}
            case "set":
                return {DEFAULT_FACTORY: f"{ANY_FACTORY} set({value})"}
            case _:
                return {DEFAULT: value}

    def generate(self, imports: imports.Imports) -> str:
        match self.root:
            case "local_date" | "local_time" | "local_date_time" | "zoned_date_time":
                imports.add("datetime")
            case "setting":
                imports.add("typing", "Any")
            case "secret":
                imports.add("pydantic")
            case _:
                pass

        match self.root:
            case "boolean":
                return "bool"
            case "integer":
                return "int"
            case "float":
                return "float"
            case "local_date":
                return "datetime.date"
            case "local_time":
                return "datetime.time"
            case "local_date_time" | "zoned_date_time":
                return "datetime.datetime"
            case "time_zone" | "text":
                return "str"
            case "secret":
                return SECRET_STR
            case "setting":
                return "Any"
            case other:
                raise ValueError(other)


class PropertyType(SchemaType):
    def generate(self, imports: imports.Imports) -> str:
        match self.root:
            case "list":
                return "list"
            case "set":
                return "set"
            case _:
                return super().generate(imports)
