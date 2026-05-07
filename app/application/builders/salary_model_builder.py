from app.domain.entities.agreement import Deduction, OvertimeRule, SalaryItem, SalaryModel


class SalaryModelBuilder:
    def build(self, raw: dict) -> SalaryModel:
        raw_rules = raw.get("raw_salary_rules") or []
        remunerative_items: list[SalaryItem] = []
        non_remunerative_items: list[SalaryItem] = []
        deductions: list[Deduction] = []
        overtime_rules: list[OvertimeRule] = []
        fiscal_shields: list[dict] = []

        for rule in raw_rules:
            kind = str(rule.get("kind") or rule.get("type") or "").upper()
            code = self._code(rule)
            if "DEDUCTION" in kind or "RETENTION" in kind or "DEDUCCION" in kind:
                deductions.append(Deduction(
                    code=code,
                    name=rule.get("name") or code,
                    rate=float(rule.get("rate") or rule.get("percentage") or 0),
                    base=rule.get("base") or "REMUNERATIVE_TOTAL",
                ))
            elif "OVERTIME" in kind or "HORA_EXTRA" in kind:
                overtime_rules.append(OvertimeRule(code=code, multiplier=float(rule.get("multiplier") or 1)))
            elif "NON_REMUNERATIVE" in kind or "NO_REMUNERATIVO" in kind:
                non_remunerative_items.append(self._salary_item(rule, code, "NON_REMUNERATIVE"))
            elif "FISCAL" in kind:
                fiscal_shields.append(rule)
            else:
                remunerative_items.append(self._salary_item(rule, code, "REMUNERATIVE"))

        if not deductions:
            deductions = [
                Deduction(code="JUBILACION", name="Jubilacion", rate=11, base="REMUNERATIVE_TOTAL"),
                Deduction(code="OBRA_SOCIAL", name="Obra social", rate=3, base="REMUNERATIVE_TOTAL"),
                Deduction(code="LEY_19032", name="Ley 19.032", rate=3, base="REMUNERATIVE_TOTAL"),
            ]
        if not overtime_rules:
            overtime_rules = [OvertimeRule(code="OT_50", multiplier=1.5), OvertimeRule(code="OT_100", multiplier=2)]

        return SalaryModel(
            remunerative_items=remunerative_items,
            non_remunerative_items=non_remunerative_items,
            deductions=deductions,
            fiscal_shields=fiscal_shields,
            overtime_rules=overtime_rules,
        )

    def _salary_item(self, rule: dict, code: str, item_type: str) -> SalaryItem:
        return SalaryItem(
            code=code,
            name=rule.get("name") or code,
            type=item_type,
            calculation_type=rule.get("calculation_type") or ("PERCENTAGE" if rule.get("rate") else "FIXED"),
            base_reference=rule.get("base_reference") or rule.get("base") or "BASIC",
            amount=rule.get("amount"),
            rate=rule.get("rate") or rule.get("percentage"),
            formula=rule.get("formula"),
        )

    def _code(self, rule: dict) -> str:
        raw = str(rule.get("code") or rule.get("name") or "RULE").upper()
        return "_".join(part for part in raw.replace("%", "").split() if part)
