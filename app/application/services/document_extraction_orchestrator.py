from app.application.services.extraction_logger import ExtractionLogger
from app.infrastructure.ai.gemini_document_extractor import GeminiDocumentTextExtractor


class DocumentExtractionOrchestrator:
    def __init__(
        self,
        gemini_extractor: GeminiDocumentTextExtractor,
        logger: ExtractionLogger | None = None,
    ):
        self.gemini_extractor = gemini_extractor
        self.logger = logger or ExtractionLogger()

    def extract_text(self, file: tuple[str, bytes]) -> dict:
        filename, content = file
        self.logger.info(f"Gemini extraction started: {filename}")
        try:
            text = self.gemini_extractor.extract_text(filename, content)
            self.logger.info(f"Gemini extraction success: {filename}")
            return {"source": "gemini", "text": self._normalize(text)}
        except Exception as exc:
            self.logger.error(f"Gemini extraction failed: {filename}: {exc}")
            raise

    def extract_documents(self, documents: list[tuple[str, bytes]]) -> dict:
        if len(documents) == 1:
            return self.extract_text(documents[0])
        filenames = ", ".join(filename for filename, _ in documents)
        self.logger.info(f"Gemini multi-document extraction started: {filenames}")
        try:
            text = self.gemini_extractor.extract_documents(documents)
            self.logger.info(f"Gemini multi-document extraction success: {filenames}")
            return {"source": "gemini", "text": self._normalize(text)}
        except Exception as exc:
            self.logger.error(f"Gemini multi-document extraction failed: {filenames}: {exc}")
            raise

    def _normalize(self, text: str) -> str:
        lines = [" ".join(line.split()) for line in (text or "").replace("\x00", " ").splitlines()]
        return "\n".join(line for line in lines if line).strip()
