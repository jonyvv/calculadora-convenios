from app.application.builders.audit_context_builder import AuditContextBuilder
from app.application.services.audit_service import AuditService
from app.application.services.convention_structuring_service import ConventionStructuringService
from app.application.services.document_extraction_orchestrator import DocumentExtractionOrchestrator
from app.application.services.document_import_service import DocumentImportService
from app.application.use_cases.activar_version_convenio import ActivarVersionConvenio
from app.application.use_cases.actualizar_escala_salarial import ActualizarEscalaSalarial
from app.application.use_cases.actualizar_convenio import ActualizarConvenio
from app.application.use_cases.auditar_liquidacion import AuditarLiquidacion
from app.application.use_cases.calcular_liquidacion import CalcularLiquidacion
from app.application.use_cases.crear_empleado import CrearEmpleado
from app.application.use_cases.eliminar_convenio import EliminarConvenio
from app.application.use_cases.importar_convenio import ImportarConvenio
from app.application.use_cases.listar_convenios import ListarConvenios
from app.application.use_cases.listar_empleados import ListarEmpleados
from app.application.use_cases.obtener_convenio import ObtenerConvenio
from app.application.use_cases.obtener_empleado import ObtenerEmpleado
from app.application.use_cases.registrar_novedades import RegistrarNovedades
from app.domain.rules.payroll_engine import PayrollEngine
from app.infrastructure.ai.audit_agent import AuditAgent, MockAuditAgent
from app.infrastructure.ai.gemini_client import GeminiClient
from agents.agreement_structuring_agent import AgreementStructuringAgent
from app.infrastructure.ai.gemini_document_extractor import GeminiDocumentTextExtractor, MockGeminiDocumentTextExtractor
from app.infrastructure.persistence.json_agreement_repository import JsonAgreementRepository
from app.infrastructure.persistence.json_employee_repository import JsonEmployeeRepository
from app.infrastructure.persistence.json_event_repository import JsonEventRepository
from app.infrastructure.storage.json_storage import JsonStorage
from app.shared.config import Settings


class Container:
    def __init__(self):
        self.settings = Settings()
        self.storage = JsonStorage(self.settings.storage_root)
        self.agreements = JsonAgreementRepository(self.storage)
        self.employees = JsonEmployeeRepository(self.storage)
        self.events = JsonEventRepository(self.storage)
        self.engine = PayrollEngine()
        self.gemini_client = GeminiClient(self.settings)
        use_mock = (
            self.settings.use_mock_gemini
            or self.settings.app_env == "test"
            or (self.settings.app_env == "development" and not self.settings.gemini_api_key)
        )
        self.gemini_document_extractor = MockGeminiDocumentTextExtractor() if use_mock else GeminiDocumentTextExtractor(self.gemini_client)
        self.extraction_orchestrator = DocumentExtractionOrchestrator(
            self.gemini_document_extractor,
        )
        self.audit_agent = MockAuditAgent() if use_mock else AuditAgent(self.gemini_client)
        self.codex_agent = AgreementStructuringAgent(self.agreements)
        self.convention_structuring_service = ConventionStructuringService(
            self.extraction_orchestrator,
            self.codex_agent,
            self.agreements,
        )

    def importar_convenio(self) -> ImportarConvenio:
        return ImportarConvenio(DocumentImportService(self.convention_structuring_service), self.agreements)

    def listar_convenios(self) -> ListarConvenios:
        return ListarConvenios(self.agreements)

    def obtener_convenio(self) -> ObtenerConvenio:
        return ObtenerConvenio(self.agreements)

    def activar_version_convenio(self) -> ActivarVersionConvenio:
        return ActivarVersionConvenio(self.agreements)

    def actualizar_convenio(self) -> ActualizarConvenio:
        return ActualizarConvenio(self.agreements)

    def actualizar_escala_salarial(self) -> ActualizarEscalaSalarial:
        return ActualizarEscalaSalarial(self.agreements)

    def eliminar_convenio(self) -> EliminarConvenio:
        return EliminarConvenio(self.agreements)

    def crear_empleado(self) -> CrearEmpleado:
        return CrearEmpleado(self.employees)

    def listar_empleados(self) -> ListarEmpleados:
        return ListarEmpleados(self.employees)

    def obtener_empleado(self) -> ObtenerEmpleado:
        return ObtenerEmpleado(self.employees)

    def registrar_novedades(self) -> RegistrarNovedades:
        return RegistrarNovedades(self.events)

    def calcular_liquidacion(self) -> CalcularLiquidacion:
        return CalcularLiquidacion(self.agreements, self.employees, self.events, self.engine)

    def auditar_liquidacion(self) -> AuditarLiquidacion:
        return AuditarLiquidacion(
            self.agreements,
            self.employees,
            self.events,
            self.engine,
            AuditContextBuilder(),
            AuditService(self.audit_agent),
        )
