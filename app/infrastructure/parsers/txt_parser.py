from app.infrastructure.parsers.base import DocumentParser


class TxtParser(DocumentParser):
    def parse(self, content: bytes) -> str:
        return content.decode("utf-8", errors="ignore")
