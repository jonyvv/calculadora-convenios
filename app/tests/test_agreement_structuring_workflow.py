import json

from app.application.services.convention_test_generator import ConventionTestGenerator
from app.application.workflows.agreement_structuring_workflow import AgreementProcessingLogger, AgreementStructuringWorkflow
from agents.codex_structuring_agent import CodexStructuringAgent
from agents.codex_structuring_agent.logger import CodexAgentLogger
from app.infrastructure.persistence.json_agreement_repository import JsonAgreementRepository
from app.infrastructure.storage.json_storage import JsonStorage


def raw_payload(version: str = "2026_04") -> dict:
    return {
        "document_metadata": {
            "agreement_id": "CCT_130_75",
            "name": "Comercio",
            "version": version,
            "valid_from": "2026-04-01",
            "source_document": "raw_gemini_output.json",
        },
        "raw_categories": [{"category_id": "A", "name": "Administrativo A", "basic_salary": 500000}],
        "raw_salary_rules": [
            {"kind": "REMUNERATIVE", "code": "PRESENTISMO", "name": "Presentismo", "rate": 8.33},
            {"kind": "DEDUCTION", "code": "JUBILACION", "name": "Jubilacion", "rate": 11},
            {"kind": "OVERTIME", "code": "OT_50", "multiplier": 1.5},
        ],
        "raw_event_rules": [{"event_type": "ABSENCE", "subtype": "UNJUSTIFIED", "effects": ["LOSE_ATTENDANCE"]}],
        "raw_compliance_rules": [{"rule": "attendance_bonus_removed_if_unjustified_absence"}],
        "ambiguities": [],
    }


def workflow(tmp_path):
    repository = JsonAgreementRepository(JsonStorage(str(tmp_path / "storage")))
    codex_agent = CodexStructuringAgent(
        repository,
        test_generator=ConventionTestGenerator(str(tmp_path / "tests" / "conventions")),
        logger=CodexAgentLogger(str(tmp_path / "logs" / "agents" / "codex")),
    )
    return AgreementStructuringWorkflow(
        repository=repository,
        codex_agent=codex_agent,
        logger=AgreementProcessingLogger(str(tmp_path / "logs" / "convention_processing")),
    )


def write_raw(tmp_path, payload):
    path = tmp_path / "raw_gemini_output.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_workflow_maps_raw_json_and_returns_success(tmp_path):
    result = workflow(tmp_path).run(write_raw(tmp_path, raw_payload()))

    assert result["status"] == "SUCCESS"
    assert result["agreement_id"] == "CCT_130_75"
    assert result["version"] == "2026_04"
    assert result["warnings"] == []
    assert (tmp_path / "storage" / "convenios" / "CCT_130_75" / "2026_04.json").exists()
    assert result["generated_test"].endswith("test_cct_130_75_2026_04.py")
    assert result["log_path"].endswith(".json")


def test_workflow_marks_draft_when_critical_raw_fields_are_missing(tmp_path):
    payload = raw_payload()
    payload.pop("raw_categories")
    result = workflow(tmp_path).run(write_raw(tmp_path, payload))

    assert result["status"] == "DRAFT"
    assert "Falta key intermedia raw_categories" in result["warnings"]


def test_workflow_supersedes_previous_active_version(tmp_path):
    instance = workflow(tmp_path)
    first = raw_payload("2026_04")
    second = raw_payload("2026_07")
    instance.run(write_raw(tmp_path, first))
    instance.run(write_raw(tmp_path, second))

    old_path = tmp_path / "storage" / "convenios" / "CCT_130_75" / "2026_04.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    assert old["metadata"]["status"] == "SUPERSEDED"
