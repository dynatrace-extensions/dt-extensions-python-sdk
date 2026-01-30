class Imports:
    def __init__(self) -> None:
        self.imports: dict[str, set[str]] = {}

    def add(self, module: str, item: str | None = None) -> None:
        self.imports.setdefault(module, set())

        if item is not None:
            self.imports[module].add(item)

    def generate(self) -> str:
        return "\n".join(
            (
                f"import {module}"
                if not items
                else f"from {module} import {', '.join(items)}"
            )
            for module, items in self.imports.items()
        )
