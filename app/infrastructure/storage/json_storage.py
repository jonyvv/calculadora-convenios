import json
from pathlib import Path
from typing import Any


class JsonStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, path: str, data: dict[str, Any]) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def read(self, path: str) -> dict[str, Any]:
        return json.loads((self.root / path).read_text(encoding="utf-8"))

    def exists(self, path: str) -> bool:
        return (self.root / path).exists()

    def glob(self, pattern: str) -> list[Path]:
        return list(self.root.glob(pattern))
