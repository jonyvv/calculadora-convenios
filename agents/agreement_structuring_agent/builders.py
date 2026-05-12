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
        rows = []
        heading_indexes = [index for index, line in enumerate(lines) if heading.lower() in line.lower()]

        for heading_index in heading_indexes:
            table_lines = []
            for line in lines[heading_index + 1:]:
                stripped = line.strip()
                if table_lines and (not stripped or stripped.startswith("##")):
                    break
                if "|" in stripped:
                    table_lines.append(stripped)

            if len(table_lines) < 2:
                continue

            headers = [TextTools.code(header).lower() for header in TextTools._split_table_line(table_lines[0])]
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
        source = " ".join(str(part or "") for part in [
            explicit,
            metadata.get("name"),
            metadata.get("source_document"),
            metadata.get("activity"),
            metadata.get("union"),
            text,
        ]).upper()
        matches = re.findall(r"CCT\s*(\d+)\s*[/_-]\s*(\d{2,4})", source)
        if matches:
            first_number = matches[0][0]
            preferred = next((match for match in matches if match[0] == first_number and len(match[1]) == 4), matches[0])
            return f"CCT_{preferred[0]}_{preferred[1]}"
        if explicit:
            return TextTools.code(str(explicit))
        fallback = (
            metadata.get("name")
            or metadata.get("source_document")
            or self._after_label(text, "actividad")
            or self._after_label(text, "sindicato")
            or self._name(text, "CONVENIO")
        )
        fallback_id = TextTools.code(str(fallback))[:50].strip("_")
        return fallback_id or "CONVENIO_SIN_IDENTIFICAR"

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
        if categories:
            return categories
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                name = match.group(1).strip(" .:-")
                amount = TextTools.money(match.group(2))
                if amount <= 0:
                    continue
                name = self._normalize_category_name(name)
                if self._looks_like_non_category(name):
                    continue
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
            descriptive_name = self._first_value(
                row,
                "puesto_rol_categoria",
                "puesto_rol_categor_a",
                "puesto_rol",
                "puesto",
                "rol",
                "cargo",
                "funcion",
                "funci_n",
                "descripcion",
                "descripci_n",
                "name",
            ).strip()
            category_value = self._first_value(
                row,
                "categoria",
                "categor_a",
                "category",
                "category_id",
                "codigo",
                "c_digo",
                "cod",
            ).strip()
            name = (
                descriptive_name
                if descriptive_name and not self._looks_like_code_only(descriptive_name)
                else category_value
            ).strip()
            amount = TextTools.money(
                self._first_value(
                    row,
                    "basico",
                    "b_sico",
                    "sueldo_basico",
                    "sueldo_b_sico",
                    "salario_basico",
                    "salario_b_sico",
                    "basic_salary",
                    "remuneracion_basica",
                    "remuneraci_n_b_sica",
                    "total_remunerativo",
                )
            )
            if not name or amount <= 0 or "NO_INDICADO" in name.upper() or self._looks_like_non_category(name):
                continue
            category_id = TextTools.code(
                self._first_value(row, "category_id", "codigo", "c_digo", "cod", "categor_a_n", "categoria_n")
                or category_value
                or name
            )[:30] or "A"
            category_id = self._unique_category_id(category_id, seen)
            if category_id in seen:
                continue
            seen.add(category_id)
            categories.append(Category(category_id=category_id, name=self._normalize_display_name(name), basic_salary=amount))
        return categories

    def _first_value(self, row: dict[str, str], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value and str(value).strip():
                return str(value)
        return ""

    def _unique_category_id(self, category_id: str, seen: set[str]) -> str:
        if category_id not in seen:
            return category_id
        index = 2
        while f"{category_id}_{index}" in seen:
            index += 1
        return f"{category_id}_{index}"

    def _normalize_display_name(self, name: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(name or "")).strip(" .:-")
        return cleaned.title()

    def _looks_like_code_only(self, value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z]?\d+[A-Za-z]?|[A-Za-z]{1,3}", str(value or "").strip()))

    def _looks_like_non_category(self, name: str) -> bool:
        value = name.lower()
        blocked = (
            "ley",
            "articulo",
            "artículo",
            "resolucion",
            "resolución",
            "decreto",
            "jubilacion",
            "jubilación",
            "obra social",
            "sindicato",
            "retencion",
            "retención",
            "deduccion",
            "deducción",
        )
        return any(token in value for token in blocked)

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
        items.extend(item for item in self._items_from_table(text, "HABERES_NO_REMUNERATIVOS", "NON_REMUNERATIVE") if item.type == "REMUNERATIVE")
        if items:
            return self._dedupe_items(items)
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
        items = [item for item in self._items_from_table(text, "HABERES_NO_REMUNERATIVOS", "NON_REMUNERATIVE") if item.type == "NON_REMUNERATIVE"]
        if items:
            return self._dedupe_items(items)
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
            raw_code = TextTools.code(row.get("code") or "")
            code = TextTools.code(concept if raw_code in {"", "NO_INDICADO"} else raw_code)
            if not code or code in {"BASIC", "BASICO", "SUELDO_BASICO"}:
                continue
            amount = TextTools.money(row.get("importe") or row.get("amount") or "")
            rate = TextTools.percent(row.get("porcentaje") or row.get("rate") or "")
            calculation_type = (row.get("calculation_type") or "").upper()
            if calculation_type not in {"FIXED", "PERCENTAGE", "FORMULA"}:
                calculation_type = "PERCENTAGE" if rate is not None else "FIXED"
            if amount <= 0 and rate is None:
                continue
            normalized_type = self._normalize_item_type(concept, item_type, rate)
            input_mode = self._input_mode(concept, row)
            unit = self._unit(concept, row)
            formula = self._clean_formula(row.get("formula") or "")
            if input_mode == "MANUAL" and calculation_type == "FORMULA" and not formula:
                if amount > 0:
                    calculation_type = "FIXED"
                elif rate is not None:
                    calculation_type = "PERCENTAGE"
            items.append(SalaryItem(
                code=code,
                name=concept or code,
                type=normalized_type,
                calculation_type=calculation_type,
                base_reference=row.get("base") or row.get("base_reference") or "BASIC",
                amount=amount if calculation_type == "FIXED" else None,
                rate=rate if calculation_type == "PERCENTAGE" else None,
                formula=formula if calculation_type == "FORMULA" else None,
                applies_to_categories=self._applies_to_categories(row.get("aplica_a_categoria") or ""),
                applies_to_tags=self._applies_to_tags(concept, row.get("observaciones") or ""),
                input_mode=input_mode,
                unit=unit,
            ))
        return items

    def _deductions(self, text: str) -> list[Deduction]:
        lower = text.lower()
        deductions = self._deductions_from_table(text)
        if self._has_aggregate_legal_contribution(deductions):
            return self._dedupe_deductions(deductions)
        if "jubil" in lower:
            if not any(deduction.code == "JUBILACION" for deduction in deductions):
                deductions.append(Deduction(code="JUBILACION", name="Jubilacion", rate=self._near_percentage(text, "jubil") or 11))
        if "ley 19032" in lower or "ley 19.032" in lower or "inssjp" in lower or "pami" in lower:
            if not any(deduction.code == "LEY_19032" for deduction in deductions):
                deductions.append(Deduction(code="LEY_19032", name="Ley 19.032", rate=self._near_percentage(text, "19032") or self._near_percentage(text, "19.032") or 3))
        if "obra social" in lower:
            if not any(deduction.code == "OBRA_SOCIAL" for deduction in deductions):
                deductions.append(Deduction(code="OBRA_SOCIAL", name="Obra social", rate=self._near_percentage(text, "obra social") or 3))
        if "sindicato" in lower or "cuota sindical" in lower:
            if not any("SINDIC" in TextTools.code(f"{deduction.code} {deduction.name}") for deduction in deductions):
                deductions.append(Deduction(code="SINDICATO", name="Sindicato", rate=self._near_percentage(text, "sindicato") or 2))
        deductions = self._ensure_argentina_statutory_deductions(deductions, text)
        return self._dedupe_deductions(deductions) or [
            Deduction(code="JUBILACION", name="Jubilacion", rate=11),
            Deduction(code="OBRA_SOCIAL", name="Obra social", rate=3),
        ]

    def _deductions_from_table(self, text: str) -> list[Deduction]:
        deductions = []
        for row in TextTools.tables_after_heading(text, "RETENCIONES_DEDUCCIONES"):
            concept = self._first_value(
                row,
                "concepto",
                "conceptos",
                "name",
                "descripcion",
                "descripci_n",
                "detalle",
                "item",
                "aporte",
                "aportes",
                "retencion",
                "retenci_n",
                "deduccion",
                "deducci_n",
            )
            raw_code = TextTools.code(row.get("code") or "")
            code = self._deduction_code(concept, raw_code)
            rate = TextTools.percent(self._first_value(row, "porcentaje", "alicuota", "alicuota_aporte", "al_cuota", "rate", "tasa", "porcentaje_aporte", "valor"))
            if rate is None:
                rate = TextTools.percent(" ".join(str(value or "") for value in row.values()))
            if not code or rate is None or rate <= 0:
                continue
            deductions.append(Deduction(
                code=code,
                name=concept or code,
                rate=rate,
                base=self._first_value(row, "base", "base_calculo", "base_de_calculo", "base_imponible", "sobre", "aplica_sobre") or "REMUNERATIVE_TOTAL",
            ))
        return deductions

    def _ensure_argentina_statutory_deductions(self, deductions: list[Deduction], text: str) -> list[Deduction]:
        if self._has_aggregate_legal_contribution(deductions):
            return deductions
        lower = text.lower()
        if not any(token in lower for token in ("argentina", "cct", "convenio", "sindicato", "obra social", "jubil")):
            return deductions
        required = [
            Deduction(code="JUBILACION", name="Jubilacion", rate=11, base="REMUNERATIVE_TOTAL"),
            Deduction(code="LEY_19032", name="Ley 19.032", rate=3, base="REMUNERATIVE_TOTAL"),
            Deduction(code="OBRA_SOCIAL", name="Obra social", rate=3, base="REMUNERATIVE_TOTAL"),
        ]
        existing = {self._statutory_key(deduction) for deduction in deductions}
        for deduction in required:
            if self._statutory_key(deduction) not in existing:
                deductions.append(deduction)
        return deductions

    def _has_aggregate_legal_contribution(self, deductions: list[Deduction]) -> bool:
        return any("APORTES_DE_LEY" in TextTools.code(f"{deduction.code} {deduction.name}") for deduction in deductions)

    def _statutory_key(self, deduction: Deduction) -> str:
        value = TextTools.code(f"{deduction.code} {deduction.name}")
        if "JUBIL" in value:
            return "JUBILACION"
        if "19032" in value or "PAMI" in value or "INSSJP" in value:
            return "LEY_19032"
        if "OBRA_SOCIAL" in value:
            return "OBRA_SOCIAL"
        if "CUOTA_SINDICAL" in value:
            return "CUOTA_SINDICAL"
        if "SINDIC" in value:
            return "SINDICATO"
        if "SEGURO" in value and "SEPEL" in value:
            return "SEGURO_SEPELIO"
        return deduction.code

    def _deduction_code(self, concept: str, raw_code: str) -> str:
        semantic = self._semantic_deduction_code(concept)
        if semantic:
            return semantic
        return TextTools.code(concept if self._generic_deduction_code(raw_code) else raw_code)

    def _semantic_deduction_code(self, concept: str) -> str | None:
        value = TextTools.code(concept)
        if "JUBIL" in value:
            return "JUBILACION"
        if "19032" in value or "19_032" in value or "PAMI" in value or "INSSJP" in value:
            return "LEY_19032"
        if "OBRA_SOCIAL" in value:
            return "OBRA_SOCIAL"
        if "SEGURO" in value and "SEPEL" in value:
            return "SEGURO_SEPELIO"
        if "CUOTA_SINDICAL" in value:
            return "CUOTA_SINDICAL"
        if "SINDIC" in value:
            return "SINDICATO"
        return None

    def _dedupe_deductions(self, deductions: list[Deduction]) -> list[Deduction]:
        result = {}
        for deduction in deductions:
            result[self._deduction_key(deduction)] = deduction
        return list(result.values())

    def _deduction_key(self, deduction: Deduction) -> str:
        semantic = self._statutory_key(deduction)
        if semantic in {"JUBILACION", "LEY_19032", "OBRA_SOCIAL", "CUOTA_SINDICAL", "SINDICATO", "SEGURO_SEPELIO"}:
            return semantic
        code = TextTools.code(deduction.code)
        name = TextTools.code(deduction.name)
        base = TextTools.code(deduction.base)
        if code in {"", "NO_INDICADO", "DEDUCCION", "DEDUCCIONES", "RETENCION", "RETENCIONES", "APORTE", "APORTES", "D"}:
            return f"{name}_{deduction.rate}_{base}"
        return f"{code}_{name}_{deduction.rate}_{base}"

    def _generic_deduction_code(self, code: str) -> bool:
        return code in {"", "NO_INDICADO", "DEDUCCION", "DEDUCCIONES", "RETENCION", "RETENCIONES", "APORTE", "APORTES", "D"}

    def _first_value(self, row: dict[str, str], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value:
                return value
        return ""

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
            result[self._semantic_key(item)] = item
        return list(result.values())

    def _normalize_item_type(self, concept: str, item_type: str, rate: float | None) -> str:
        value = TextTools.code(concept)
        if item_type == "NON_REMUNERATIVE" and rate is not None:
            if any(token in value for token in ("RAMA", "DIFERENCIAL", "RECOLECCION", "PLURALIDAD")):
                return "REMUNERATIVE"
        return item_type

    def _semantic_key(self, item: SalaryItem) -> str:
        value = TextTools.code(f"{item.code} {item.name}")
        if "ANTIG" in value or "SENIORITY" in value:
            return "SENIORITY"
        if "PRESENTISMO" in value or "ATTENDANCE" in value or "ASISTENCIA" in value:
            return "PRESENTISMO"
        if "PLURALIDAD" in value:
            if "GRUPO_III" in value or "GRUPO_3" in value:
                return "PLURALIDAD_GRUPO_III"
            if "GRUPO_I" in value or "GRUPO_1" in value:
                return "PLURALIDAD_GRUPO_I"
            return "PLURALIDAD"
        return item.code

    def _applies_to_categories(self, value: str) -> list[str]:
        cleaned = TextTools.code(value)
        if not cleaned or cleaned in {"TODAS", "TODOS", "NO_INDICADO", "ALL"}:
            return []
        return [part for part in cleaned.split("_") if part]

    def _applies_to_tags(self, concept: str, observations: str) -> list[str]:
        value = TextTools.code(f"{concept} {observations}")
        tags = []
        tag_map = {
            "CAUDALES": ("CAUDALES", "BLINDADO"),
            "RECOLECCION": ("RECOLECCION", "RESIDUOS"),
            "LACTEA": ("LACTEA", "LACTEO"),
            "AUXILIO": ("AUXILIO", "REMOLQUE"),
            "PLURALIDAD_GRUPO_III": ("PLURALIDAD", "III"),
            "PLURALIDAD_GRUPO_I": ("PLURALIDAD", "I"),
        }
        for tag, tokens in tag_map.items():
            if all(token in value for token in tokens):
                tags.append(tag)
        return tags

    def _input_mode(self, concept: str, row: dict[str, str]) -> str:
        value = TextTools.code(" ".join(str(part or "") for part in [
            concept,
            row.get("base"),
            row.get("base_reference"),
            row.get("formula"),
            row.get("observaciones"),
            row.get("calculation_type"),
        ]))
        manual_tokens = (
            "KILOMETRO",
            "KILOMETROS",
            "KM",
            "CANTIDAD",
            "UNIDADES",
            "VIAJE",
            "VIAJES",
            "VIATICO",
            "VIATICOS",
            "COMIDA",
            "PERNOCTADA",
            "PERNOCTE",
            "COMISION",
            "COMISIONES",
            "PRODUCTIVIDAD",
        )
        return "MANUAL" if any(token in value for token in manual_tokens) else "AUTO"

    def _clean_formula(self, value: str) -> str | None:
        formula = str(value or "").strip()
        if not formula:
            return None
        if TextTools.code(formula) in {"NO_INDICADO", "NO_APLICA", "N_A", "NA", "NONE", "NULL"}:
            return None
        return formula

    def _unit(self, concept: str, row: dict[str, str]) -> str | None:
        value = TextTools.code(" ".join(str(part or "") for part in [concept, row.get("base"), row.get("formula"), row.get("observaciones")]))
        if "KILOMETRO" in value or "KM" in value:
            return "KM"
        if "DIA" in value or "COMIDA" in value:
            return "DAY"
        if "VIAJE" in value:
            return "TRIP"
        if "PERNOCT" in value:
            return "NIGHT"
        if "COMISION" in value:
            return "AMOUNT"
        return None


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
