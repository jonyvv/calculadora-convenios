from pathlib import Path
import shutil

from app.domain.entities.agreement import Agreement
from app.domain.repositories.agreement_repository import AgreementRepository
from app.infrastructure.storage.json_storage import JsonStorage
from app.shared.exceptions import NotFoundError


class JsonAgreementRepository(AgreementRepository):
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def save_version(self, agreement: Agreement) -> Agreement:
        meta = agreement.metadata
        marker = f"convenios/{meta.agreement_id}/active.json"
        if self.storage.exists(marker):
            active_version = self.storage.read(marker)["version"]
            active_path = f"convenios/{meta.agreement_id}/{active_version}.json"
            if active_version != meta.version and self.storage.exists(active_path):
                active = Agreement.model_validate(self.storage.read(active_path))
                active.metadata.status = "SUPERSEDED"
                self.storage.write(active_path, active.model_dump())
        self.storage.write(f"convenios/{meta.agreement_id}/{meta.version}.json", agreement.model_dump())
        return agreement

    def list(self) -> list[Agreement]:
        agreements = []
        for path in self.storage.glob("convenios/*/*.json"):
            if path.name == "active.json":
                continue
            agreements.append(Agreement.model_validate(self.storage.read(str(path.relative_to(self.storage.root)))))
        return agreements

    def get(self, agreement_id: str, version: str | None = None) -> Agreement:
        if version is None:
            return self.get_active(agreement_id)
        path = f"convenios/{agreement_id}/{version}.json"
        if not self.storage.exists(path):
            raise NotFoundError("Agreement version not found")
        return Agreement.model_validate(self.storage.read(path))

    def activate(self, agreement_id: str, version: str) -> Agreement:
        agreement = self.get(agreement_id, version)
        agreement.metadata.status = "ACTIVE" if agreement.metadata.status != "DRAFT" else "DRAFT"
        self.storage.write(f"convenios/{agreement_id}/{version}.json", agreement.model_dump())
        self.storage.write(f"convenios/{agreement_id}/active.json", {"version": version})
        return agreement

    def get_active(self, agreement_id: str) -> Agreement:
        marker = f"convenios/{agreement_id}/active.json"
        if not self.storage.exists(marker):
            versions = sorted(Path(p).stem for p in self.storage.glob(f"convenios/{agreement_id}/*.json") if p.name != "active.json")
            if not versions:
                raise NotFoundError("Agreement not found")
            return self.get(agreement_id, versions[-1])
        return self.get(agreement_id, self.storage.read(marker)["version"])

    def delete(self, agreement_id: str, version: str | None = None) -> None:
        base = self.storage.root / "convenios" / agreement_id
        root = self.storage.root.resolve()
        if not base.exists():
            raise NotFoundError("Agreement not found")
        if version is None:
            target = base.resolve()
            if root not in target.parents and target != root:
                raise ValueError("Invalid agreement path")
            shutil.rmtree(target)
            return

        target = (base / f"{version}.json").resolve()
        if root not in target.parents:
            raise ValueError("Invalid agreement version path")
        if not target.exists():
            raise NotFoundError("Agreement version not found")
        target.unlink()

        marker = base / "active.json"
        if marker.exists():
            versions = sorted(path.stem for path in base.glob("*.json") if path.name != "active.json")
            if versions:
                self.storage.write(f"convenios/{agreement_id}/active.json", {"version": versions[-1]})
            else:
                marker.unlink()
