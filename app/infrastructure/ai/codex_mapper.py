from app.application.builders.agreement_builder import AgreementBuilder
from app.domain.entities.agreement import Agreement


class CodexMapper:
    """Infrastructure adapter for the local Domain Structuring Agent."""

    def __init__(self, builder: AgreementBuilder):
        self.builder = builder

    def map_to_agreement(self, raw: dict, source_document: str) -> tuple[Agreement, list[str]]:
        return self.builder.build(raw, source_document)
