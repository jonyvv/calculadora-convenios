from datetime import datetime, timezone
from pathlib import Path


class ExtractionLogger:
    def __init__(self, root: str = "logs/extraction"):
        self.root = Path(root)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def warning(self, message: str) -> None:
        self._write("WARNING", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)

    def _write(self, level: str, message: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        timestamp = datetime.now(timezone.utc).isoformat()
        with (self.root / f"{date}.log").open("a", encoding="utf-8") as log:
            log.write(f"[{level}] {timestamp} {message}\n")
