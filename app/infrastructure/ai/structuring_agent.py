import re

from app.infrastructure.ai.gemini_client import GeminiClient


class SemanticExtractionAgent:
    def __init__(self, client: GeminiClient):
        self.client = client

    def extract(self, filename: str, text: str) -> dict:
        chunk_size = self.client.settings.gemini_structuring_chunk_chars
        if len(text) > chunk_size:
            return self._extract_large_document(filename, text, chunk_size)
        return self._extract_chunk(filename, text, 1, 1)

    def _extract_large_document(self, filename: str, text: str, chunk_size: int) -> dict:
        chunks = [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)]
        partials = [self._extract_chunk(filename, chunk, position, len(chunks)) for position, chunk in enumerate(chunks, start=1)]
        prompt = f"""
Sos Gemini actuando SOLO como Semantic Extraction Agent.
Consolida estos JSON intermedios parciales en un unico JSON intermedio.
No generes Agreement final. No normalices al dominio definitivo. No guardes nada.
Formato exacto:
{{
  "document_metadata": {{}},
  "raw_categories": [],
  "raw_salary_rules": [],
  "raw_event_rules": [],
  "raw_compliance_rules": [],
  "ambiguities": []
}}
No uses markdown.

Documento fuente: {filename}
Parciales:
{partials}
"""
        return self.client.generate_json(prompt)

    def _extract_chunk(self, filename: str, text: str, position: int, total: int) -> dict:
        prompt = f"""
Sos Gemini actuando SOLO como Semantic Extraction Agent.
Lee este fragmento {position}/{total} del documento laboral {filename}.
Interpreta articulos, categorias, reglas salariales, novedades, cumplimiento y ambiguedades.
Devuelve SOLO JSON intermedio con este formato exacto:
{{
  "document_metadata": {{
    "agreement_id": "",
    "name": "",
    "version": "",
    "valid_from": "",
    "valid_to": "",
    "source_document": "{filename}"
  }},
  "raw_categories": [],
  "raw_salary_rules": [],
  "raw_event_rules": [],
  "raw_compliance_rules": [],
  "ambiguities": []
}}
Gemini NO debe generar Agreement final, NO debe escribir archivos y NO debe inventar reglas.
No copies parrafos largos. Usa reglas compactas y trazables. No uses markdown.

Fragmento:
{text}
"""
        return self.client.generate_json(prompt)


class MockSemanticExtractionAgent(SemanticExtractionAgent):
    def __init__(self):
        pass

    def extract(self, filename: str, text: str) -> dict:
        agreement_id = self._infer_agreement_id(filename, text)
        return {
            "document_metadata": {
                "agreement_id": agreement_id,
                "name": self._infer_name(filename, agreement_id),
                "version": "2026_01",
                "valid_from": "2026-01-01",
                "valid_to": None,
                "source_document": filename,
            },
            "raw_categories": [{"category_id": "A", "name": "Categoria A", "basic_salary": 100000}],
            "raw_salary_rules": [
                {"kind": "REMUNERATIVE", "code": "SENIORITY", "name": "Antiguedad", "calculation_type": "PERCENTAGE", "base_reference": "BASIC", "rate": 1},
                {"kind": "REMUNERATIVE", "code": "PRESENTISMO", "name": "Presentismo", "calculation_type": "PERCENTAGE", "base_reference": "BASIC", "rate": 10},
                {"kind": "DEDUCTION", "code": "JUBILACION", "name": "Jubilacion", "rate": 11, "base": "REMUNERATIVE_TOTAL"},
                {"kind": "OVERTIME", "code": "OT_50", "multiplier": 1.5},
                {"kind": "OVERTIME", "code": "OT_100", "multiplier": 2},
            ],
            "raw_event_rules": [{"event_type": "ABSENCE", "subtype": "UNJUSTIFIED", "effects": ["DISCOUNT_DAY", "LOSE_ATTENDANCE"]}],
            "raw_compliance_rules": [{"rule": "attendance_bonus_removed_if_unjustified_absence"}],
            "ambiguities": ["Mock de Gemini activo: JSON intermedio generado para desarrollo."] if text.strip() else ["Documento sin texto extraible"],
        }

    def _infer_agreement_id(self, filename: str, text: str) -> str:
        source = f"{filename} {text[:1000]}".upper()
        match = re.search(r"CCT[\s_-]*(\d+)[/\-_](\d+)", source)
        if match:
            return f"CCT_{match.group(1)}_{match.group(2)}"
        return "CCT_40_89"

    def _infer_name(self, filename: str, agreement_id: str) -> str:
        clean = filename.split(",", 1)[0].rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
        return clean.title() if clean else agreement_id


StructuringAgent = SemanticExtractionAgent
MockStructuringAgent = MockSemanticExtractionAgent


class FallbackSemanticExtractionAgent(SemanticExtractionAgent):
    def __init__(self, primary: SemanticExtractionAgent, fallback: MockSemanticExtractionAgent):
        self.primary = primary
        self.fallback = fallback

    def extract(self, filename: str, text: str) -> dict:
        try:
            return self.primary.extract(filename, text)
        except RuntimeError as exc:
            raw = self.fallback.extract(filename, text)
            raw.setdefault("ambiguities", [])
            raw["ambiguities"].insert(0, f"Gemini no respondio correctamente; se uso fallback local de desarrollo. Error: {exc}")
            return raw
