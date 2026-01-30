from typing import Literal

import pydantic

from . import imports, schema_type, utils

NullableConstraintDict = dict[str, str | int | float | None]


class ConstraintDict(dict[str, str | int | float]):
    def generate(self, imports: imports.Imports) -> str:
        if len(self) == 1 and schema_type.DEFAULT in self:
            return str(self[schema_type.DEFAULT])

        if len(self):
            imports.add("pydantic")

            args = ", ".join(f"{key}={val}" for key, val in self.items())

            return f"{schema_type.FIELD}({args})"

        return ""


class BaseConstraint(pydantic.BaseModel):
    custom_message: str | None = pydantic.Field(alias="customMessage", default=None)
    """Message to be displayed if constraint is violated."""

    def generate(self) -> NullableConstraintDict:
        return {}


class LengthConstraint(BaseConstraint):
    type: Literal["LENGTH"]
    """The type of the validation constraint."""

    max_length: int | None = pydantic.Field(alias="maxLength", default=None)
    """Maximum string length."""

    min_length: int | None = pydantic.Field(alias="minLength", default=None)
    """Minimum string length."""

    def generate(self) -> NullableConstraintDict:
        return {"max_length": self.max_length, "min_length": self.min_length}


class RangeConstraint(BaseConstraint):
    type: Literal["RANGE"]
    """The type of the validation constraint."""

    maximum: int | float | None = None
    """Maximum allowed value."""

    minimum: int | float | None = None
    """Minimum allowed value."""

    def generate(self) -> NullableConstraintDict:
        return {"le": self.maximum, "ge": self.minimum}


class PatternConstraint(BaseConstraint):
    type: Literal["PATTERN"]
    """The type of the validation constraint."""

    pattern: str
    """Regular expression for valid values."""

    def generate(self) -> NullableConstraintDict:
        return {"pattern": f"r{utils.quote_wrap(self.pattern)}"}


class CustomValidatorReferenceConstraint(BaseConstraint):
    type: Literal["CUSTOM_VALIDATOR_REF"]
    """The type of the validation constraint."""

    custom_validator_id: str = pydantic.Field(alias="customValidatorId")


class OtherConstraint(BaseConstraint):
    type: Literal["NOT_BLANK", "NOT_EMPTY", "TRIMMED", "NO_WHITESPACE", "REGEX"]


Constraint = (
    LengthConstraint | RangeConstraint | OtherConstraint | PatternConstraint | CustomValidatorReferenceConstraint
)


class Constraints(pydantic.RootModel[list[Constraint]]):
    def generate(self) -> ConstraintDict:
        constraints: ConstraintDict = ConstraintDict()

        for constraint in self.root:
            constraints.update(utils.remove_none_values(constraint.generate()))

        return constraints
