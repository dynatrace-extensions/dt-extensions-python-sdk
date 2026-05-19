import pydantic


def sanitize_paragraph(paragraph: str) -> str:
    return paragraph.replace("\r", "").strip("\n").strip().replace("\\", "\\\\")


class Documented(pydantic.BaseModel):
    display_name: str = pydantic.Field(alias="displayName", default="")
    """The human-friendly name of the property."""

    description: str = ""
    """The human-friendly description of the property."""

    documentation: str = ""
    """Additional documentation of the property."""

    def generate_docs(self) -> str:
        docs = "\n\n".join(
            paragraph
            for paragraph in (
                sanitize_paragraph(self.display_name),
                sanitize_paragraph(self.description),
                sanitize_paragraph(self.documentation),
            )
            if paragraph
        )

        if "\n" in docs:
            return f'"""\n{docs}\n"""'

        if docs:
            return f'"""{docs}"""'

        return ""
