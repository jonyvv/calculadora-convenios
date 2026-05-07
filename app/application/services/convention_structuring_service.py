from agents.agreement_structuring_agent import AgreementStructuringAgent
from app.domain.entities.agreement import Agreement
from app.domain.repositories.agreement_repository import AgreementRepository
from app.application.services.document_extraction_orchestrator import DocumentExtractionOrchestrator


class ConventionStructuringService:
    def __init__(
        self,
        extraction_orchestrator: DocumentExtractionOrchestrator,
        codex_agent: AgreementStructuringAgent,
        agreements: AgreementRepository,
    ):
        self.extraction_orchestrator = extraction_orchestrator
        self.codex_agent = codex_agent
        self.agreements = agreements

    def upload_convention(self, documents: list[tuple[str, bytes]]) -> tuple[Agreement, dict, list[str], str, list[dict]]:
        extracted_documents = []
        for document in documents:
            extracted = self.extraction_orchestrator.extract_text(document)
            extracted_documents.append({
                "filename": document[0],
                "source": extracted["source"],
                "text": extracted["text"],
            })
        source_document = ", ".join(filename for filename, _ in documents)
        full_text = "\n\n".join(f"## SOURCE_DOCUMENT: {item['filename']}\n{item['text']}" for item in extracted_documents)
        codex_input = {
            "document_metadata": {"source_document": source_document},
            "full_text": full_text,
        }
        result = self.codex_agent.process(codex_input)
        if result["status"] == "ERROR":
            raise RuntimeError("; ".join(result["warnings"]))
        agreement = self.agreements.get(result["agreement_id"], result["version"])
        return agreement, codex_input, result["warnings"], result.get("generated_test", ""), extracted_documents
