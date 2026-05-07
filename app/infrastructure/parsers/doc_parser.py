from io import BytesIO

from docx import Document

from app.infrastructure.parsers.base import DocumentParser


class DocParser(DocumentParser):
    def parse(self, content: bytes) -> str:
        doc = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
