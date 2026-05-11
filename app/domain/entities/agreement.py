from typing import Any

from pydantic import BaseModel, Field


class AgreementMetadata(BaseModel):
    agreement_id: str
    name: str
    version: str
    valid_from: str
    valid_to: str | None = None
    source_document: str
    created_at: str
    status: str = "DRAFT"
    union: str | None = None
    activity: str | None = None
    jurisdiction: str | None = None
    parity_terms: list[dict[str, Any]] = Field(default_factory=list)


class Category(BaseModel):
    category_id: str
    name: str
    basic_salary: float


class SalaryItem(BaseModel):
    code: str
    name: str
    type: str
    calculation_type: str = "FIXED"
    base_reference: str = ""
    amount: float | None = None
    rate: float | None = None
    formula: str | None = None
    applies_to_categories: list[str] = Field(default_factory=list)
    applies_to_tags: list[str] = Field(default_factory=list)
    input_mode: str = "AUTO"
    unit: str | None = None


class Deduction(BaseModel):
    code: str
    name: str = ""
    rate: float
    base: str = "REMUNERATIVE_TOTAL"


class OvertimeRule(BaseModel):
    code: str
    multiplier: float


class EventRule(BaseModel):
    event_type: str
    subtype: str | None = None
    effects: list[str] = Field(default_factory=list)


class AuditRule(BaseModel):
    rule: str


class SalaryModel(BaseModel):
    remunerative_items: list[SalaryItem] = Field(default_factory=list)
    non_remunerative_items: list[SalaryItem] = Field(default_factory=list)
    deductions: list[Deduction] = Field(default_factory=list)
    employer_contributions: list[dict[str, Any]] = Field(default_factory=list)
    fiscal_shields: list[dict[str, Any]] = Field(default_factory=list)
    overtime_rules: list[OvertimeRule] = Field(default_factory=list)


class Agreement(BaseModel):
    metadata: AgreementMetadata
    categories: list[Category] = Field(default_factory=list)
    salary_model: SalaryModel = Field(default_factory=SalaryModel)
    event_rules: list[EventRule] = Field(default_factory=list)
    audit_rules: list[AuditRule] = Field(default_factory=list)
