import json

from agents.codex_structuring_agent import CodexStructuringAgent
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


def agent(tmp_path):
    return CodexStructuringAgent(JsonAgreementRepository(JsonStorage(str(tmp_path / "storage"))))


def test_codex_structuring_agent_processes_raw_gemini_json(tmp_path):
    result = agent(tmp_path).process(raw_payload())

    assert result["status"] == "SUCCESS"
    assert result["agreement_id"] == "CCT_130_75"
    assert result["version"] == "2026_04"
    assert (tmp_path / "storage" / "convenios" / "CCT_130_75" / "2026_04.json").exists()
    assert result["log_path"].endswith(".json")
    assert result["generated_test"].endswith("test_cct_130_75_2026_04.py")


def test_codex_structuring_agent_marks_draft_for_missing_required_keys(tmp_path):
    payload = raw_payload()
    payload.pop("raw_salary_rules")
    result = agent(tmp_path).process(payload)

    assert result["status"] == "DRAFT"
    assert "Falta key intermedia raw_salary_rules" in result["warnings"]


def test_codex_structuring_agent_supersedes_active_version(tmp_path):
    instance = agent(tmp_path)
    instance.process(raw_payload("2026_04"))
    instance.process(raw_payload("2026_07"))

    old_path = tmp_path / "storage" / "convenios" / "CCT_130_75" / "2026_04.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    assert old["metadata"]["status"] == "SUPERSEDED"
