from typing import Any

from pydantic import BaseModel, Field


class AgreementMetadata(BaseModel):
    agreement_id: str
    name: str
    version: str
    valid_from: str
    valid_to: str | None = None
    source_document: str
    created_at: str
    status: str = "DRAFT"
    union: str | None = None
    activity: str | None = None
    jurisdiction: str | None = None
    parity_terms: list[dict[str, Any]] = Field(default_factory=list)


class Category(BaseModel):
    category_id: str
    name: str
    basic_salary: float
    valor_hora: float | None = None
    valor_jornal: float | None = None
    zone: str | None = None
    location: str | None = None


class SalaryItem(BaseModel):
    code: str
    name: str
    type: str
    calculation_type: str = "FIXED"
    base_reference: str = ""
    amount: float | None = None
    rate: float | None = None
    formula: str | None = None
    applies_to_categories: list[str] = Field(default_factory=list)
    applies_to_tags: list[str] = Field(default_factory=list)
    input_mode: str = "AUTO"
    unit: str | None = None


class ConceptoConvenio(BaseModel):
    nombre: str
    tipo: str
    formula: str | None = None
    base_calculo: str | None = None
    porcentaje: float | None = None
    importe_fijo: float | None = None
    condiciones: list[str] = Field(default_factory=list)
    excepciones: list[str] = Field(default_factory=list)
    fuente_articulo: str | None = None
    requiere_validacion: bool = False
    observaciones: str | None = None


class Deduction(BaseModel):
    code: str
    name: str = ""
    rate: float
    base: str = "REMUNERATIVE_TOTAL"
    application_type: str = "MANDATORY"
    applies_when: str | None = None
    requires_employee_flag: str | None = None
    source_article: str | None = None


class OvertimeRule(BaseModel):
    code: str
    multiplier: float


class EventRule(BaseModel):
    event_type: str
    subtype: str | None = None
    effects: list[str] = Field(default_factory=list)


class AuditRule(BaseModel):
    rule: str


class SalaryModel(BaseModel):
    remunerative_items: list[SalaryItem] = Field(default_factory=list)
    non_remunerative_items: list[SalaryItem] = Field(default_factory=list)
    deductions: list[Deduction] = Field(default_factory=list)
    employer_contributions: list[dict[str, Any]] = Field(default_factory=list)
    fiscal_shields: list[dict[str, Any]] = Field(default_factory=list)
    overtime_rules: list[OvertimeRule] = Field(default_factory=list)


class ModuloIdentificacionAlcance(BaseModel):
    partes_signatarias: list[str] = Field(default_factory=list)
    vigencia: dict[str, Any] = Field(default_factory=dict)
    ambito_aplicacion: dict[str, Any] = Field(default_factory=dict)
    categorias_profesionales: list[dict[str, Any]] = Field(default_factory=list)


class ModuloRemuneraciones(BaseModel):
    salario_basico: list[ConceptoConvenio] = Field(default_factory=list)
    adicionales_fijos: list[ConceptoConvenio] = Field(default_factory=list)
    adicionales_variables: list[ConceptoConvenio] = Field(default_factory=list)
    antiguedad: list[ConceptoConvenio] = Field(default_factory=list)
    presentismo_asistencia: list[ConceptoConvenio] = Field(default_factory=list)
    titulos_tecnicos_profesionales: list[ConceptoConvenio] = Field(default_factory=list)
    remuneraciones_por_rendimiento: list[ConceptoConvenio] = Field(default_factory=list)
    beneficios_no_remunerativos: list[ConceptoConvenio] = Field(default_factory=list)
    viaticos: list[ConceptoConvenio] = Field(default_factory=list)
    asignaciones_familiares: list[ConceptoConvenio] = Field(default_factory=list)
    descuentos: list[ConceptoConvenio] = Field(default_factory=list)


class ModuloJornadaTiempos(BaseModel):
    jornada_estandar: dict[str, Any] = Field(default_factory=dict)
    horas_suplementarias: list[dict[str, Any]] = Field(default_factory=list)
    jornada_nocturna: dict[str, Any] = Field(default_factory=dict)
    jornada_insalubre: dict[str, Any] = Field(default_factory=dict)
    descansos: dict[str, Any] = Field(default_factory=dict)


class ModuloLicenciasDescansos(BaseModel):
    vacaciones_ordinarias: list[dict[str, Any]] = Field(default_factory=list)
    licencias_especiales: list[dict[str, Any]] = Field(default_factory=list)
    enfermedades_infortunios: dict[str, Any] = Field(default_factory=dict)


class ModuloExtincionProteccion(BaseModel):
    preaviso: list[dict[str, Any]] = Field(default_factory=list)
    indemnizaciones: list[dict[str, Any]] = Field(default_factory=list)
    sac: dict[str, Any] = Field(default_factory=dict)
    liquidacion_final: dict[str, Any] = Field(default_factory=dict)
    agravantes: list[dict[str, Any]] = Field(default_factory=list)


class ValidacionLegal(BaseModel):
    estado: str
    mensaje: str
    valor_ingresado: Any = None
    valor_minimo_legal: Any = None
    fuente_normativa: str
    accion_sugerida: str


class ModeloLiquidacion(BaseModel):
    tipo: str = "sueldo_base"
    unidad_principal: str = "mensual"
    periodicidad: str = "mensual"
    base_calculo: str = "salario_basico_categoria"
    formula_base: str = "salario_basico_categoria"
    requiere_horas_trabajadas: bool = False
    requiere_dias_trabajados: bool = False
    requiere_categoria: bool = True
    requiere_jornada: bool = False


class Agreement(BaseModel):
    metadata: AgreementMetadata
    categories: list[Category] = Field(default_factory=list)
    salary_model: SalaryModel = Field(default_factory=SalaryModel)
    event_rules: list[EventRule] = Field(default_factory=list)
    audit_rules: list[AuditRule] = Field(default_factory=list)
    identificacion_alcance: ModuloIdentificacionAlcance = Field(default_factory=ModuloIdentificacionAlcance)
    remuneraciones: ModuloRemuneraciones = Field(default_factory=ModuloRemuneraciones)
    jornada_tiempos: ModuloJornadaTiempos = Field(default_factory=ModuloJornadaTiempos)
    licencias_descansos: ModuloLicenciasDescansos = Field(default_factory=ModuloLicenciasDescansos)
    extincion_proteccion: ModuloExtincionProteccion = Field(default_factory=ModuloExtincionProteccion)
    validaciones_legales: list[ValidacionLegal] = Field(default_factory=list)
    fuentes_normativas: list[dict[str, Any]] = Field(default_factory=list)
    advertencias_auditor: list[dict[str, Any]] = Field(default_factory=list)
    modelo_liquidacion: ModeloLiquidacion = Field(default_factory=ModeloLiquidacion)
