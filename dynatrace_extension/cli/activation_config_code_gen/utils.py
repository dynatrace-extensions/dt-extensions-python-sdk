import re
from typing import TypeVar


def indent(text: str, amount: int = 1) -> str:
    tabs = "\t" * amount

    return "\n".join(f"{tabs if line else ''}{line}" for line in text.split("\n"))


def get_property_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"[A-Z]", lambda match: f"_{match[0].lower()}", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    if re.match(r"^[0-9]", name):
        name = f"n_{name}"

    return name.lower()


def get_class_name(name: str) -> str:
    return "".join(
        f"{part[0].upper()}{part[1:]}"
        for part in get_property_name(name).split("_")
        if part
    )


def quote_wrap(text: str) -> str:
    text = text.replace('"', '\\"')

    return f'"{text}"'


T = TypeVar("T")


def remove_none_values(value: dict[str, T | None]) -> dict[str, T]:
    return {key: val for key, val in value.items() if val is not None}
