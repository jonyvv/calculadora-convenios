import re
from datetime import datetime, timezone

from app.domain.entities.agreement import AgreementMetadata


class MetadataBuilder:
    def build(self, raw: dict, source_document: str, status: str) -> AgreementMetadata:
        document_metadata = raw.get("document_metadata") or {}
        agreement_id = self._agreement_id(document_metadata, source_document)
        return AgreementMetadata(
            agreement_id=agreement_id,
            name=document_metadata.get("name") or document_metadata.get("title") or agreement_id,
            version=document_metadata.get("version") or self._version(document_metadata),
            valid_from=document_metadata.get("valid_from") or "2026-01-01",
            valid_to=document_metadata.get("valid_to"),
            source_document=source_document,
            created_at=datetime.now(timezone.utc).isoformat(),
            status=status,
        )

    def _agreement_id(self, metadata: dict, source_document: str) -> str:
        explicit = metadata.get("agreement_id") or metadata.get("code")
        source = f"{explicit or ''} {source_document}".upper()
        match = re.search(r"CCT[\s_-]*(\d+)[/\-_](\d+)", source)
        if match:
            return f"CCT_{match.group(1)}_{match.group(2)}"
        if explicit:
            return re.sub(r"[^A-Z0-9]+", "_", str(explicit).upper()).strip("_")
        return "CCT_IMPORTADO"

    def _version(self, metadata: dict) -> str:
        valid_from = str(metadata.get("valid_from") or "2026-01-01")
        match = re.match(r"(\d{4})-(\d{2})", valid_from)
        return f"{match.group(1)}_{match.group(2)}" if match else "2026_01"
