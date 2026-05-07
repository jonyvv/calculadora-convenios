import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CodexAgentLogger:
    def __init__(self, root: str = "logs/agents/codex"):
        self.root = Path(root)

    def write(self, payload: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        agreement_id = payload.get("agreement_id") or "unknown"
        version = payload.get("version") or "unknown"
        path = self.root / f"{timestamp}_{agreement_id}_{version}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
