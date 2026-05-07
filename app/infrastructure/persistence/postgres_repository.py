import psycopg
from psycopg.rows import dict_row

from app.domain.entities.agreement import Agreement
from app.domain.entities.employee import Employee
from app.domain.entities.monthly_event import MonthlyEvent
from app.domain.repositories.agreement_repository import AgreementRepository
from app.domain.repositories.employee_repository import EmployeeRepository
from app.domain.repositories.event_repository import EventRepository
from app.shared.exceptions import NotFoundError


class PostgresRepository(AgreementRepository, EmployeeRepository, EventRepository):
    """JSONB adapter for production persistence. Run migrations before enabling."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def _conn(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def save_version(self, agreement: Agreement) -> Agreement:
        with self._conn() as conn:
            conn.execute(
                "insert into agreements (agreement_id, version, payload) values (%s, %s, %s) "
                "on conflict (agreement_id, version) do update set payload = excluded.payload",
                (agreement.metadata.agreement_id, agreement.metadata.version, agreement.model_dump_json()),
            )
        return agreement

    def list(self) -> list[Agreement]:
        with self._conn() as conn:
            rows = conn.execute("select payload from agreements order by agreement_id, version").fetchall()
        return [Agreement.model_validate_json(row["payload"]) for row in rows]

    def get(self, agreement_id: str, version: str | None = None) -> Agreement:
        if version is None:
            return self.get_active(agreement_id)
        with self._conn() as conn:
            row = conn.execute("select payload from agreements where agreement_id=%s and version=%s", (agreement_id, version)).fetchone()
        if row is None:
            raise NotFoundError("Agreement version not found")
        return Agreement.model_validate_json(row["payload"])

    def activate(self, agreement_id: str, version: str) -> Agreement:
        agreement = self.get(agreement_id, version)
        with self._conn() as conn:
            conn.execute(
                "insert into active_agreements (agreement_id, version) values (%s, %s) "
                "on conflict (agreement_id) do update set version = excluded.version",
                (agreement_id, version),
            )
        return agreement

    def get_active(self, agreement_id: str) -> Agreement:
        with self._conn() as conn:
            row = conn.execute("select version from active_agreements where agreement_id=%s", (agreement_id,)).fetchone()
        if row is None:
            raise NotFoundError("Active agreement not found")
        return self.get(agreement_id, row["version"])

    def save(self, entity):
        if isinstance(entity, Employee):
            with self._conn() as conn:
                conn.execute(
                    "insert into employees (employee_id, payload) values (%s, %s) "
                    "on conflict (employee_id) do update set payload = excluded.payload",
                    (entity.employee_id, entity.model_dump_json()),
                )
            return entity
        if isinstance(entity, MonthlyEvent):
            with self._conn() as conn:
                conn.execute(
                    "insert into monthly_events (employee_id, period, payload) values (%s, %s, %s) "
                    "on conflict (employee_id, period) do update set payload = excluded.payload",
                    (entity.employee_id, entity.period, entity.model_dump_json()),
                )
            return entity
        raise TypeError("Unsupported entity")

    def get_employee(self, employee_id: str) -> Employee:
        with self._conn() as conn:
            row = conn.execute("select payload from employees where employee_id=%s", (employee_id,)).fetchone()
        if row is None:
            raise NotFoundError("Employee not found")
        return Employee.model_validate_json(row["payload"])

    def get_events(self, employee_id: str, period: str) -> MonthlyEvent:
        with self._conn() as conn:
            row = conn.execute("select payload from monthly_events where employee_id=%s and period=%s", (employee_id, period)).fetchone()
        if row is None:
            raise NotFoundError("Monthly events not found")
        return MonthlyEvent.model_validate_json(row["payload"])
