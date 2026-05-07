from app.application.builders.agreement_builder import AgreementBuilder
from app.application.services.convention_test_generator import ConventionTestGenerator
from app.infrastructure.ai.codex_mapper import CodexMapper


def raw_payload():
    return {
        "document_metadata": {
            "agreement_id": "CCT_130_75",
            "name": "Comercio",
            "version": "2026_04",
            "valid_from": "2026-04-01",
        },
        "raw_categories": [{"category_id": "A", "name": "Administrativo A", "basic_salary": 500000}],
        "raw_salary_rules": [
            {"kind": "REMUNERATIVE", "code": "PRESENTISMO", "name": "Presentismo", "rate": 8.33, "base_reference": "BASIC"},
            {"kind": "DEDUCTION", "code": "JUBILACION", "name": "Jubilacion", "rate": 11},
            {"kind": "OVERTIME", "code": "OT_50", "multiplier": 1.5},
        ],
        "raw_event_rules": [{"event_type": "ABSENCE", "subtype": "UNJUSTIFIED", "effects": ["LOSE_ATTENDANCE"]}],
        "raw_compliance_rules": [{"rule": "attendance_bonus_removed_if_unjustified_absence"}],
        "ambiguities": [],
    }


def test_codex_mapper_maps_intermediate_json_to_agreement():
    agreement, warnings = CodexMapper(AgreementBuilder()).map_to_agreement(raw_payload(), "cct.txt")

    assert warnings == []
    assert agreement.metadata.agreement_id == "CCT_130_75"
    assert agreement.metadata.status == "ACTIVE"
    assert agreement.categories[0].basic_salary == 500000
    assert agreement.salary_model.overtime_rules[0].code == "OT_50"


def test_missing_critical_information_marks_agreement_as_draft():
    raw = raw_payload()
    raw["raw_categories"] = []
    agreement, warnings = AgreementBuilder().build(raw, "cct.txt")

    assert agreement.metadata.status == "DRAFT"
    assert "Faltan categorias del convenio" in warnings


def test_convention_test_generator_creates_pytest_file(tmp_path):
    agreement, _warnings = AgreementBuilder().build(raw_payload(), "cct.txt")
    path = ConventionTestGenerator(str(tmp_path)).generate(agreement)

    assert path.exists()
    assert "test_convention_json_is_valid" in path.read_text(encoding="utf-8")
