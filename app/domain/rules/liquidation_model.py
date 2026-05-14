from dataclasses import dataclass, field

from app.domain.entities.agreement import Agreement, Category, ModeloLiquidacion
from app.domain.entities.monthly_event import MonthlyEvent


@dataclass
class LiquidationValidation:
    estado: str = "ok"
    modelo_liquidacion: str = "sueldo_base"
    alertas: list[str] = field(default_factory=list)
    datos_faltantes: list[str] = field(default_factory=list)
    mensaje: str = ""


@dataclass
class LiquidationBase:
    bruto_base: float
    valor_hora: float
    valor_jornal: float
    horas_trabajadas: float = 0
    dias_trabajados: float = 0


def resolverModeloLiquidacion(convenio: Agreement) -> ModeloLiquidacion:
    model = convenio.modelo_liquidacion or ModeloLiquidacion()
    data = model.model_dump()
    defaults = ModeloLiquidacion().model_dump()
    defaults.update({key: value for key, value in data.items() if value not in (None, "")})
    normalized = ModeloLiquidacion.model_validate(defaults)
    if normalized.tipo not in {"sueldo_base", "por_hora", "jornal", "mixto"}:
        normalized.tipo = "sueldo_base"
    return normalized


def resolver_modelo_liquidacion(convenio: Agreement) -> ModeloLiquidacion:
    return resolverModeloLiquidacion(convenio)


class LiquidationModelResolver:
    def resolve(self, agreement: Agreement) -> ModeloLiquidacion:
        return resolverModeloLiquidacion(agreement)

    def validate(self, agreement: Agreement, monthly_event: MonthlyEvent) -> LiquidationValidation:
        model = self.resolve(agreement)
        worked_hours = self.worked_hours(monthly_event)
        worked_days = self.worked_days(monthly_event)
        missing = []
        alerts = []

        if model.requiere_horas_trabajadas and worked_hours <= 0:
            missing.append("horas_trabajadas")
        if model.requiere_dias_trabajados and worked_days <= 0:
            missing.append("dias_trabajados")
        if worked_hours > 260:
            alerts.append("El valor informado para horas trabajadas supera el rango esperado.")
        if worked_days > 31:
            alerts.append("El valor informado para dias trabajados supera el rango esperado.")

        if missing:
            return LiquidationValidation(
                estado="faltan_datos",
                modelo_liquidacion=model.tipo,
                datos_faltantes=missing,
                mensaje="Faltan datos obligatorios para el modelo de liquidacion.",
            )
        if alerts:
            return LiquidationValidation(
                estado="requiere_confirmacion",
                modelo_liquidacion=model.tipo,
                alertas=alerts,
                mensaje="Hay valores fuera del rango esperado para el convenio.",
            )
        return LiquidationValidation(estado="ok", modelo_liquidacion=model.tipo)

    def compute_base(self, agreement: Agreement, category: Category, monthly_event: MonthlyEvent) -> LiquidationBase:
        model = self.resolve(agreement)
        monthly_hours = self.monthly_hours(agreement)
        monthly_days = self.monthly_days(agreement)
        valor_hora = float(category.valor_hora or category.basic_salary / monthly_hours)
        valor_jornal = float(category.valor_jornal or category.basic_salary / monthly_days)
        hours = self.worked_hours(monthly_event)
        days = self.worked_days(monthly_event)

        if model.tipo == "por_hora":
            bruto_base = valor_hora * hours
        elif model.tipo == "jornal":
            bruto_base = valor_jornal * days
        else:
            bruto_base = category.basic_salary
        return LiquidationBase(
            bruto_base=round(bruto_base, 2),
            valor_hora=round(valor_hora, 6),
            valor_jornal=round(valor_jornal, 6),
            horas_trabajadas=hours,
            dias_trabajados=days,
        )

    def worked_hours(self, monthly_event: MonthlyEvent) -> float:
        return sum(
            float(event.hours or event.quantity or 0)
            for event in monthly_event.events
            if str(event.type or "").upper() in {"WORKED_HOURS", "HORAS_TRABAJADAS"}
            or str(event.subtype or "").upper() == "HORAS_TRABAJADAS"
        )

    def worked_days(self, monthly_event: MonthlyEvent) -> float:
        return sum(
            float(event.days or event.quantity or 0)
            for event in monthly_event.events
            if str(event.type or "").upper() in {"WORKED_DAYS", "DIAS_TRABAJADOS"}
            or str(event.subtype or "").upper() == "DIAS_TRABAJADOS"
        )

    def monthly_hours(self, agreement: Agreement) -> float:
        jornada = agreement.jornada_tiempos.jornada_estandar or {}
        return float(jornada.get("horas_mensuales") or jornada.get("monthly_hours") or 200)

    def monthly_days(self, agreement: Agreement) -> float:
        jornada = agreement.jornada_tiempos.jornada_estandar or {}
        return float(jornada.get("dias_mensuales") or jornada.get("monthly_days") or 30)
