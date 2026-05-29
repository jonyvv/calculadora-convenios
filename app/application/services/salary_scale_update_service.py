import re
import unicodedata

from app.domain.entities.agreement import Agreement, Category
from app.infrastructure.parsers.parser_factory import ParserFactory


class SalaryScaleUpdateService:
    def __init__(self, parser_factory: ParserFactory | None = None):
        self.parser_factory = parser_factory or ParserFactory()

    def update(self, agreement: Agreement, filename: str, content: bytes) -> tuple[Agreement, dict]:
        text = self.parser_factory.parse(filename, content)
        entries = self._extract_entries(text)
        if not entries:
            raise ValueError("No se detectaron filas de escala salarial con puesto e importe basico.")

        updated = 0
        added = 0
        categories = list(agreement.categories)
        for entry in entries:
            category = self._find_category(categories, entry)
            if category:
                category.basic_salary = entry["basic_salary"]
                updated += 1
            else:
                categories.append(Category(
                    category_id=entry["category_id"] or self._category_id(entry["name"]),
                    name=entry["name"],
                    basic_salary=entry["basic_salary"],
                    zone=entry.get("zone") or None,
                    location=entry.get("zone") or None,
                ))
                added += 1

        source = agreement.metadata.source_document or ""
        if filename not in source:
            agreement.metadata.source_document = f"{source}, {filename}" if source else filename
        agreement.categories = categories
        return agreement, {
            "updated": updated,
            "added": added,
            "detected_rows": len(entries),
            "filename": filename,
        }

    def _extract_entries(self, text: str) -> list[dict]:
        entries = []
        current_headers: list[str] = []
        for raw_line in text.splitlines():
            parts = self._split_row(raw_line)
            if len(parts) < 2:
                continue
            normalized = [self._token(part) for part in parts]
            if self._looks_like_header(normalized):
                current_headers = normalized
                continue
            entry = self._entry_from_row(parts, current_headers)
            if entry:
                entries.append(entry)
        return entries

    def _entry_from_row(self, parts: list[str], headers: list[str]) -> dict | None:
        if headers and len(headers) == len(parts):
            data = {headers[index]: parts[index].strip() for index in range(len(parts))}
            name = self._first(data, "PUESTO", "ROL", "CATEGORIA", "CATEGORY", "NOMBRE")
            category_id = self._first(data, "CATEGORY_ID", "CODIGO", "CODE", "ID")
            amount = self._money(self._first(data, "BASICO", "BASIC", "SALARIO", "SUELDO", "REMUNERACION"))
            zone = self._first(data, "ZONA", "UBICACION", "LOCATION")
        else:
            amount_index = next((index for index in range(len(parts) - 1, -1, -1) if self._money(parts[index]) is not None), None)
            if amount_index is None:
                return None
            amount = self._money(parts[amount_index])
            values = [part.strip() for index, part in enumerate(parts) if index != amount_index and part.strip()]
            category_id = values[0] if values and self._looks_like_code(values[0]) else ""
            name = values[1] if category_id and len(values) > 1 else values[0] if values else ""
            zone = ""

        if not name or amount is None or amount <= 0:
            return None
        return {
            "category_id": category_id.strip(),
            "name": name.strip(),
            "basic_salary": amount,
            "zone": zone.strip(),
        }

    def _split_row(self, line: str) -> list[str]:
        clean = line.strip().strip("|")
        if not clean or clean.startswith("#"):
            return []
        if "|" in clean:
            return [part.strip() for part in clean.split("|")]
        if "\t" in clean:
            return [part.strip() for part in clean.split("\t")]
        if ";" in clean:
            return [part.strip() for part in clean.split(";")]
        return re.split(r"\s{2,}", clean)

    def _looks_like_header(self, normalized: list[str]) -> bool:
        row = set(normalized)
        has_category = bool(row.intersection({"CATEGORY_ID", "CATEGORIA", "CATEGORY", "PUESTO", "ROL", "NOMBRE"}))
        has_amount = bool(row.intersection({"BASICO", "BASIC", "SALARIO", "SUELDO", "REMUNERACION"}))
        return has_category and has_amount

    def _find_category(self, categories: list[Category], entry: dict) -> Category | None:
        entry_id = self._token(entry["category_id"])
        entry_name = self._token(entry["name"])
        for category in categories:
            if entry_id and self._token(category.category_id) == entry_id:
                return category
        for category in categories:
            if self._token(category.name) == entry_name:
                return category
        return None

    def _first(self, data: dict, *keys: str) -> str:
        for key in keys:
            for data_key, value in data.items():
                if key in data_key and value:
                    return value
        return ""

    def _money(self, value: str) -> float | None:
        raw = str(value or "").strip()
        match = re.search(r"-?\$?\s*[\d.,]+", raw)
        if not match:
            return None
        number = match.group(0).replace("$", "").replace(" ", "")
        if "," in number and "." in number:
            number = number.replace(".", "").replace(",", ".")
        elif "," in number:
            number = number.replace(",", ".")
        try:
            return float(number)
        except ValueError:
            return None

    def _looks_like_code(self, value: str) -> bool:
        token = self._token(value)
        return bool(token) and (token.isupper() or any(char.isdigit() for char in token) or "_" in token)

    def _category_id(self, name: str) -> str:
        return self._token(name)[:60] or "CATEGORIA"

    def _token(self, value: str) -> str:
        normalized = unicodedata.normalize("NFD", str(value or ""))
        ascii_value = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return re.sub(r"[^A-Z0-9]+", "_", ascii_value.upper()).strip("_")
