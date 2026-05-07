import re
from datetime import datetime, timezone

from agents.codex_structuring_agent.builders import FormulaBuilder
from app.domain.entities.agreement import (
    AgreementMetadata,
    AuditRule,
    Category,
    Deduction,
    EventRule,
    OvertimeRule,
    SalaryItem,
    SalaryModel,
)


class TextTools:
    @staticmethod
    def money(value: str) -> float:
        cleaned = str(value or "").replace("$", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(re.sub(r"[^0-9.]", "", cleaned) or 0)

    @staticmethod
    def percent(value: str) -> float | None:
        value = str(value or "")
        if not value.strip() or "NO_INDICADO" in value.upper():
            return None
        match = re.search(r"(\d+(?:[,.]\d+)?)", value)
        return float(match.group(1).replace(",", ".")) if match else None

    @staticmethod
    def code(value: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")

    @staticmethod
    def tables_after_heading(text: str, heading: str) -> list[dict[str, str]]:
        lines = text.splitlines()
        heading_index = next((index for index, line in enumerate(lines) if heading.lower() in line.lower()), None)
        if heading_index is None:
            return []

        table_lines = []
        for line in lines[heading_index + 1:]:
            stripped = line.strip()
            if table_lines and (not stripped or stripped.startswith("##")):
                break
            if "|" in stripped:
                table_lines.append(stripped)

        if len(table_lines) < 2:
            return []

        headers = [TextTools.code(header).lower() for header in TextTools._split_table_line(table_lines[0])]
        rows = []
        for line in table_lines[1:]:
            values = TextTools._split_table_line(line)
            if not values or all(re.fullmatch(r"-+", value.strip()) for value in values):
                continue
            rows.append({headers[index]: values[index].strip() if index < len(values) else "" for index in range(len(headers))})
        return rows

    @staticmethod
    def _split_table_line(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]


class MetadataBuilder:
    def build(self, payload: dict, status: str) -> AgreementMetadata:
        metadata = payload.get("document_metadata") or {}
        text = payload.get("full_text") or ""
        agreement_id = self._agreement_id(metadata, text)
        valid_from = metadata.get("valid_from") or self._valid_from(text)
        return AgreementMetadata(
            agreement_id=agreement_id,
            name=metadata.get("name") or self._name(text, agreement_id),
            version=metadata.get("version") or valid_from[:7].replace("-", "_"),
            valid_from=valid_from,
            valid_to=metadata.get("valid_to") or self._valid_to(text),
            source_document=metadata.get("source_document") or "gemini_full_text",
            created_at=datetime.now(timezone.utc).isoformat(),
            status=status,
            union=metadata.get("union") or self._after_label(text, "sindicato"),
            activity=metadata.get("activity") or self._after_label(text, "actividad"),
            jurisdiction=metadata.get("jurisdiction") or self._jurisdiction(text),
            parity_terms=self._parity_terms(text),
        )

    def _agreement_id(self, metadata: dict, text: str) -> str:
        explicit = metadata.get("agreement_id") or metadata.get("code")
        source = f"{explicit or ''} {text}".upper()
        match = re.search(r"CCT\s*(\d+)\s*/\s*(\d+)", source)
        if match:
            return f"CCT_{match.group(1)}_{match.group(2)}"
        return TextTools.code(str(explicit or "CCT_40_89"))

    def _name(self, text: str, agreement_id: str) -> str:
        match = re.search(r"(?:convenio|cct)[^\n]{0,80}", text, flags=re.IGNORECASE)
        return match.group(0).strip().title() if match else agreement_id

    def _valid_from(self, text: str) -> str:
        match = re.search(r"(?:vigencia|desde)[^\d]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text, flags=re.IGNORECASE)
        if match:
            day, month, year = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        return "2026-01-01"

    def _valid_to(self, text: str) -> str | None:
        match = re.search(r"(?:hasta)[^\d]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text, flags=re.IGNORECASE)
        if not match:
            return None
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    def _after_label(self, text: str, label: str) -> str | None:
        match = re.search(rf"{label}\s*:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _jurisdiction(self, text: str) -> str | None:
        if re.search(r"\bnacional\b", text, flags=re.IGNORECASE):
            return "Nacional"
        return self._after_label(text, "jurisdiccion") or self._after_label(text, "jurisdicción")

    def _parity_terms(self, text: str) -> list[dict]:
        terms = []
        for match in re.finditer(r"paritaria[^\n\r]{0,140}", text, flags=re.IGNORECASE):
            terms.append({"description": match.group(0).strip()})
        return terms


class CategoryBuilder:
    def build(self, payload: dict) -> list[Category]:
        text = payload.get("full_text") or ""
        categories = self._from_extracted_tables(text)
        patterns = [
            r"categoria\s+([A-Z0-9][A-Z0-9\s.-]{0,50})\s+(?:basico|básico)?\s*\$?\s*([0-9][0-9.,]+)",
            r"categoría\s+([A-Z0-9][A-Z0-9\s.-]{0,50})\s+(?:basico|básico)?\s*\$?\s*([0-9][0-9.,]+)",
            r"([A-Z][A-Za-zÁÉÍÓÚáéíóúñÑ\s]{2,40})\s+\$?\s*([0-9]{2,3}(?:[.,][0-9]{3})+(?:,[0-9]{2})?)",
        ]
        seen = {category.category_id for category in categories}
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                name = match.group(1).strip(" .:-")
                amount = TextTools.money(match.group(2))
                if amount <= 0:
                    continue
                name = self._normalize_category_name(name)
                category_id = TextTools.code(name)[:30] or "A"
                if category_id in seen:
                    continue
                seen.add(category_id)
                categories.append(Category(category_id=category_id, name=name.title(), basic_salary=amount))
        return categories

    def _from_extracted_tables(self, text: str) -> list[Category]:
        categories = []
        seen = set()
        for row in TextTools.tables_after_heading(text, "ESCALA_SALARIAL_CATEGORIAS"):
            name = (
                row.get("puesto_rol_categoria")
                or row.get("categoria")
                or row.get("puesto")
                or row.get("rol")
                or row.get("name")
                or ""
            ).strip()
            amount = TextTools.money(
                row.get("basico")
                or row.get("sueldo_basico")
                or row.get("basic_salary")
                or row.get("total_remunerativo")
                or ""
            )
            if not name or amount <= 0 or "NO_INDICADO" in name.upper():
                continue
            category_id = TextTools.code(row.get("category_id") or name)[:30] or "A"
            if category_id in seen:
                continue
            seen.add(category_id)
            categories.append(Category(category_id=category_id, name=name.title(), basic_salary=amount))
        return categories

    def _normalize_category_name(self, name: str) -> str:
        normalized = re.sub(r"\b(categoria|categoría|basico|básico)\b", "", name, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", normalized).strip(" .:-")


class SalaryModelBuilder:
    def build(self, payload: dict) -> SalaryModel:
        text = payload.get("full_text") or ""
        return SalaryModel(
            remunerative_items=self._remunerative_items(text),
            non_remunerative_items=self._non_remunerative_items(text),
            deductions=self._deductions(text),
            employer_contributions=self._employer_contributions(text),
            fiscal_shields=self._fiscal_shields(text),
            overtime_rules=self._overtime_rules(text),
        )

    def _remunerative_items(self, text: str) -> list[SalaryItem]:
        items = self._items_from_table(text, "HABERES_REMUNERATIVOS", "REMUNERATIVE")
        keyword_map = {
            "antig": ("SENIORITY", "Antiguedad"),
            "presentismo": ("PRESENTISMO", "Presentismo"),
            "zona": ("ZONA", "Zona"),
            "productividad": ("PRODUCTIVIDAD", "Productividad"),
            "titulo": ("TITULO", "Titulo"),
            "título": ("TITULO", "Titulo"),
            "adicional": ("ADICIONAL", "Adicional"),
        }
        lower = text.lower()
        for keyword, (code, name) in keyword_map.items():
            if any(item.code == code for item in items):
                continue
            if keyword in lower:
                rate = self._near_percentage(text, keyword)
                items.append(SalaryItem(
                    code=code,
                    name=name,
                    type="REMUNERATIVE",
                    calculation_type="PERCENTAGE" if rate is not None else "FIXED",
                    base_reference="BASIC",
                    rate=rate,
                    amount=None if rate is not None else 0,
                ))
        return self._dedupe_items(items)

    def _non_remunerative_items(self, text: str) -> list[SalaryItem]:
        items = self._items_from_table(text, "HABERES_NO_REMUNERATIVOS", "NON_REMUNERATIVE")
        lower = text.lower()
        if "no remunerativ" in lower or "acuerdo" in lower:
            items.append(SalaryItem(code="AGREEMENT_SUM", name="Acuerdo no remunerativo", type="NON_REMUNERATIVE", amount=0))
        if "bono" in lower:
            items.append(SalaryItem(code="BONUS_NR", name="Bono", type="NON_REMUNERATIVE", amount=0))
        return self._dedupe_items(items)

    def _items_from_table(self, text: str, heading: str, item_type: str) -> list[SalaryItem]:
        items = []
        for row in TextTools.tables_after_heading(text, heading):
            concept = row.get("concepto") or row.get("name") or ""
            code = TextTools.code(row.get("code") or concept)
            if not code or code in {"BASIC", "BASICO", "SUELDO_BASICO"}:
                continue
            amount = TextTools.money(row.get("importe") or row.get("amount") or "")
            rate = TextTools.percent(row.get("porcentaje") or row.get("rate") or "")
            calculation_type = (row.get("calculation_type") or "").upper()
            if calculation_type not in {"FIXED", "PERCENTAGE", "FORMULA"}:
                calculation_type = "PERCENTAGE" if rate is not None else "FIXED"
            if amount <= 0 and rate is None:
                continue
            items.append(SalaryItem(
                code=code,
                name=concept or code,
                type=item_type,
                calculation_type=calculation_type,
                base_reference=row.get("base") or row.get("base_reference") or "BASIC",
                amount=amount if calculation_type == "FIXED" else None,
                rate=rate if calculation_type == "PERCENTAGE" else None,
                formula=row.get("formula") if calculation_type == "FORMULA" else None,
            ))
        return items

    def _deductions(self, text: str) -> list[Deduction]:
        lower = text.lower()
        deductions = self._deductions_from_table(text)
        if "jubil" in lower:
            if not any(deduction.code == "JUBILACION" for deduction in deductions):
                deductions.append(Deduction(code="JUBILACION", name="Jubilacion", rate=self._near_percentage(text, "jubil") or 11))
        if "obra social" in lower:
            if not any(deduction.code == "OBRA_SOCIAL" for deduction in deductions):
                deductions.append(Deduction(code="OBRA_SOCIAL", name="Obra social", rate=self._near_percentage(text, "obra social") or 3))
        if "sindicato" in lower or "cuota sindical" in lower:
            if not any(deduction.code == "SINDICATO" for deduction in deductions):
                deductions.append(Deduction(code="SINDICATO", name="Sindicato", rate=self._near_percentage(text, "sindicato") or 2))
        return self._dedupe_deductions(deductions) or [
            Deduction(code="JUBILACION", name="Jubilacion", rate=11),
            Deduction(code="OBRA_SOCIAL", name="Obra social", rate=3),
        ]

    def _deductions_from_table(self, text: str) -> list[Deduction]:
        deductions = []
        for row in TextTools.tables_after_heading(text, "RETENCIONES_DEDUCCIONES"):
            concept = row.get("concepto") or row.get("name") or ""
            code = TextTools.code(row.get("code") or concept)
            rate = TextTools.percent(row.get("porcentaje") or row.get("rate") or "")
            if not code or rate is None or rate <= 0:
                continue
            deductions.append(Deduction(
                code=code,
                name=concept or code,
                rate=rate,
                base=row.get("base") or "REMUNERATIVE_TOTAL",
            ))
        return deductions

    def _dedupe_deductions(self, deductions: list[Deduction]) -> list[Deduction]:
        result = {}
        for deduction in deductions:
            result[deduction.code] = deduction
        return list(result.values())

    def _employer_contributions(self, text: str) -> list[dict]:
        lower = text.lower()
        contributions = []
        if "contribuciones" in lower or "cargas sociales" in lower:
            contributions.append({"code": "SOCIAL_SECURITY", "name": "Contribuciones patronales", "base": "REMUNERATIVE_TOTAL"})
        if "art" in lower:
            contributions.append({"code": "ART", "name": "ART", "base": "REMUNERATIVE_TOTAL"})
        return contributions

    def _overtime_rules(self, text: str) -> list[OvertimeRule]:
        lower = text.lower()
        rules = []
        if "50%" in text or "cincuenta" in lower or "hora extra" in lower:
            rules.append(OvertimeRule(code="OT_50", multiplier=1.5))
        if "100%" in text or "cien" in lower or "feriado" in lower:
            rules.append(OvertimeRule(code="OT_100", multiplier=2))
        return rules or [OvertimeRule(code="OT_50", multiplier=1.5), OvertimeRule(code="OT_100", multiplier=2)]

    def _fiscal_shields(self, text: str) -> list[dict]:
        return [{"code": "NON_REMUNERATIVE_LIMIT", "description": "Conceptos no remunerativos detectados"}] if "no remunerativ" in text.lower() else []

    def _near_percentage(self, text: str, keyword: str) -> float | None:
        match = re.search(rf"{keyword}[^\n\r%]{{0,80}}?(\d+(?:[,.]\d+)?)\s*%", text, flags=re.IGNORECASE)
        return float(match.group(1).replace(",", ".")) if match else None

    def _dedupe_items(self, items: list[SalaryItem]) -> list[SalaryItem]:
        result = {}
        for item in items:
            result[item.code] = item
        return list(result.values())


class EventRuleBuilder:
    def build(self, payload: dict) -> list[EventRule]:
        text = (payload.get("full_text") or "").lower()
        rules = []
        if "falta injustificada" in text or "inasistencia injustificada" in text:
            rules.append(EventRule(event_type="ABSENCE", subtype="UNJUSTIFIED", effects=["DISCOUNT_DAY", "LOSE_ATTENDANCE"]))
        if "falta justificada" in text or "inasistencia justificada" in text:
            rules.append(EventRule(event_type="ABSENCE", subtype="JUSTIFIED", effects=[]))
        if "suspension" in text or "suspensión" in text:
            rules.append(EventRule(event_type="SUSPENSION", subtype=None, effects=["DISCOUNT_DAY"]))
        if "licencia" in text:
            rules.append(EventRule(event_type="LEAVE", subtype=None, effects=[]))
        if "vacaciones" in text:
            rules.append(EventRule(event_type="LEAVE", subtype="VACATION", effects=[]))
        if "feriado" in text:
            rules.append(EventRule(event_type="HOLIDAY_WORKED", subtype="WORKED", effects=["PAY_OVERTIME_100"]))
        if "hora extra" in text or "horas extra" in text:
            rules.append(EventRule(event_type="OVERTIME", subtype=None, effects=["PAY_OVERTIME"]))
        return rules


class ComplianceBuilder:
    def build(self, agreement_rules: list[EventRule], salary_model: SalaryModel) -> list[AuditRule]:
        rules = []
        codes = {item.code for item in salary_model.remunerative_items}
        has_unjustified_absence = any(rule.event_type == "ABSENCE" and rule.subtype == "UNJUSTIFIED" for rule in agreement_rules)
        if has_unjustified_absence and "PRESENTISMO" in codes:
            rules.append(AuditRule(rule="attendance_bonus_removed_if_unjustified_absence"))
        if salary_model.overtime_rules:
            rules.append(AuditRule(rule="overtime_must_match_declared_multiplier"))
        if salary_model.deductions:
            rules.append(AuditRule(rule="deductions_apply_only_to_remunerative_total"))
        return rules


__all__ = [
    "MetadataBuilder",
    "CategoryBuilder",
    "SalaryModelBuilder",
    "EventRuleBuilder",
    "ComplianceBuilder",
    "FormulaBuilder",
]
