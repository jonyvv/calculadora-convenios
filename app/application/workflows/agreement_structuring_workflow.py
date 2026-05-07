import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.codex_structuring_agent import CodexStructuringAgent
from app.infrastructure.persistence.json_agreement_repository import JsonAgreementRepository
from app.infrastructure.storage.json_storage import JsonStorage
from app.shared.config import Settings


class AgreementProcessingLogger:
    def __init__(self, root: str = "logs/convention_processing"):
        self.root = Path(root)

    def write(self, payload: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        agreement_id = payload.get("agreement_id") or "unknown"
        version = payload.get("version") or "unknown"
        path = self.root / f"{timestamp}_{agreement_id}_{version}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


class AgreementStructuringWorkflow:
    name = "agreement_structuring_workflow"

    def __init__(
        self,
        repository: JsonAgreementRepository,
        codex_agent: CodexStructuringAgent | None = None,
        logger: AgreementProcessingLogger | None = None,
    ):
        self.repository = repository
        self.codex_agent = codex_agent or CodexStructuringAgent(repository)
        self.logger = logger or AgreementProcessingLogger()

    def run(self, raw_json_path: str | Path) -> dict[str, Any]:
        raw_path = Path(raw_json_path)
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            agent_result = self.codex_agent.process(raw)
            output = {
                "status": agent_result["status"],
                "agreement_id": agent_result["agreement_id"],
                "version": agent_result["version"],
                "warnings": agent_result["warnings"],
            }
            log_path = self.logger.write({
                **output,
                "workflow": self.name,
                "input_file": str(raw_path),
                "agent_log": agent_result.get("log_path"),
                "generated_test": agent_result.get("generated_test"),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })
            return {**output, "log_path": str(log_path), "generated_test": agent_result.get("generated_test")}
        except Exception as exc:
            output = {
                "status": "ERROR",
                "agreement_id": "",
                "version": "",
                "warnings": [str(exc)],
            }
            log_path = self.logger.write({
                **output,
                "workflow": self.name,
                "input_file": str(raw_path),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })
            return {**output, "log_path": str(log_path)}


def create_default_workflow() -> AgreementStructuringWorkflow:
    settings = Settings()
    storage = JsonStorage(settings.storage_root)
    repository = JsonAgreementRepository(storage)
    return AgreementStructuringWorkflow(repository)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog=AgreementStructuringWorkflow.name)
    parser.add_argument("raw_json_path", help="Path to raw_gemini_output.json")
    args = parser.parse_args()
    result = create_default_workflow().run(args.raw_json_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
