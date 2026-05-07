from io import BytesIO

from pypdf import PdfReader

from app.infrastructure.parsers.base import DocumentParser


class PdfParser(DocumentParser):
    def parse(self, content: bytes) -> str:
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
