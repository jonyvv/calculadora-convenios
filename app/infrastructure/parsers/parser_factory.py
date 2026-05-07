from app.infrastructure.parsers.doc_parser import DocParser
from app.infrastructure.parsers.excel_parser import ExcelParser
from app.infrastructure.parsers.pdf_parser import PdfParser
from app.infrastructure.parsers.txt_parser import TxtParser


class ParserFactory:
    def parse(self, filename: str, content: bytes) -> str:
        suffix = filename.lower().rsplit(".", 1)[-1]
        if suffix == "pdf":
            return PdfParser().parse(content)
        if suffix in {"docx", "doc"}:
            return DocParser().parse(content)
        if suffix in {"xlsx", "xls"}:
            return ExcelParser().parse(content)
        return TxtParser().parse(content)
