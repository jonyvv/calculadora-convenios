import json

from agents.agreement_structuring_agent import AgreementStructuringAgent
from agents.agreement_structuring_agent.logger import AgreementStructuringLogger
from app.application.services.convention_test_generator import ConventionTestGenerator
from app.infrastructure.persistence.json_agreement_repository import JsonAgreementRepository
from app.infrastructure.storage.json_storage import JsonStorage


def payload(version_text: str = "vigencia desde 01/04/2026 hasta 31/03/2027") -> dict:
    return {
        "document_metadata": {
            "source_document": "gemini_text.json",
        },
        "full_text": f"""
        Convenio colectivo CCT 130/75 Comercio.
        Sindicato: Federacion Argentina de Empleados de Comercio.
        Actividad: Comercio.
        Ambito nacional.
        {version_text}
        Paritaria abril 2026 con revision.

        Categoria Administrativo A basico $500.000,00
        Categoria Vendedor B basico $550.000,00

        Se abonara presentismo 8,33% y antiguedad 1% por anio.
        Adicional por zona 5%. Productividad segun acuerdo.
        Sumas no remunerativas por acuerdo y bono extraordinario.
        Deducciones: jubilacion 11%, obra social 3%, sindicato 2%.
        Contribuciones patronales y ART.
        Horas extra al 50% y horas extra al 100% en feriado.
        Falta injustificada pierde presentismo. Falta justificada no descuenta.
        Licencias, vacaciones, suspensiones y feriados trabajados.
        """,
    }


def agent(tmp_path):
    repository = JsonAgreementRepository(JsonStorage(str(tmp_path / "storage")))
    return AgreementStructuringAgent(
        repository,
        test_generator=ConventionTestGenerator(str(tmp_path / "tests" / "conventions")),
        logger=AgreementStructuringLogger(str(tmp_path / "logs" / "agents" / "codex")),
    )


def test_agreement_structuring_agent_builds_agreement_from_full_text(tmp_path):
    result = agent(tmp_path).process(payload())

    assert result["status"] == "SUCCESS"
    assert result["agreement_id"] == "CCT_130_75"
    assert result["version"] == "2026_04"
    agreement_path = tmp_path / "storage" / "convenios" / "CCT_130_75" / "2026_04.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))
    assert agreement["metadata"]["activity"] == "Comercio."
    assert len(agreement["categories"]) == 2
    assert agreement["salary_model"]["employer_contributions"]
    assert any(rule["rule"] == "attendance_bonus_removed_if_unjustified_absence" for rule in agreement["audit_rules"])


def test_agreement_structuring_agent_marks_draft_without_full_text(tmp_path):
    result = agent(tmp_path).process({"document_metadata": {}})

    assert result["status"] == "DRAFT"
    assert "Falta full_text extraido por Gemini" in result["warnings"]


def test_agreement_structuring_agent_supersedes_previous_version(tmp_path):
    instance = agent(tmp_path)
    instance.process(payload("vigencia desde 01/04/2026"))
    instance.process(payload("vigencia desde 01/07/2026"))

    old_path = tmp_path / "storage" / "convenios" / "CCT_130_75" / "2026_04.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    assert old["metadata"]["status"] == "SUPERSEDED"


def test_agreement_structuring_agent_reads_gemini_salary_tables(tmp_path):
    result = agent(tmp_path).process({
        "document_metadata": {"source_document": "escala.pdf"},
        "full_text": """
        ## METADATA
        convenio: CCT 40/89 Camioneros
        vigencia_desde: 01/04/2026

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | CHOFER_1 | Chofer primera categoria | Abril 2026 | $ 850.000,00 | $ 994.000,00 | escala salarial |
        | AUXILIAR | Auxiliar especializado | Abril 2026 | $ 710.500,50 | $ 820.000,00 | escala salarial |

        ## HABERES_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | PRESENTISMO | Presentismo | PERCENTAGE | NO_INDICADO | 8,33% | BASIC | TODAS | Abril 2026 | remunerativo |
        | PLUS_CONVENIO | Plus convenio | FIXED | $ 25.000,00 | NO_INDICADO | BASIC | TODAS | Abril 2026 | remunerativo |

        ## HABERES_NO_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | SUMA_NR | Suma no remunerativa acuerdo | FIXED | $ 40.000,00 | NO_INDICADO | BASIC | TODAS | Abril 2026 | no remunerativo |

        ## RETENCIONES_DEDUCCIONES
        | code | concepto | porcentaje | importe | base | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | JUBILACION | Jubilacion | 11% | NO_INDICADO | REMUNERATIVE_TOTAL | ley |
        | OBRA_SOCIAL | Obra social | 3% | NO_INDICADO | REMUNERATIVE_TOTAL | ley |
        | SINDICATO | Sindicato | 2% | NO_INDICADO | REMUNERATIVE_TOTAL | convenio |
        """,
    })

    agreement_path = tmp_path / "storage" / "convenios" / result["agreement_id"] / f"{result['version']}.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))

    assert result["status"] == "SUCCESS"
    assert agreement["categories"][0]["category_id"] == "CHOFER_1"
    assert agreement["categories"][0]["basic_salary"] == 850000
    assert agreement["categories"][1]["basic_salary"] == 710500.5
    presentismo = next(item for item in agreement["salary_model"]["remunerative_items"] if item["code"] == "PRESENTISMO")
    assert presentismo["rate"] == 8.33
    plus = next(item for item in agreement["salary_model"]["remunerative_items"] if item["code"] == "PLUS_CONVENIO")
    assert plus["amount"] == 25000
    non_remunerative = agreement["salary_model"]["non_remunerative_items"][0]
    assert non_remunerative["code"] == "SUMA_NR"
    assert non_remunerative["amount"] == 40000
    assert {deduction["code"]: deduction["rate"] for deduction in agreement["salary_model"]["deductions"]} == {
        "JUBILACION": 11,
        "OBRA_SOCIAL": 3,
        "SINDICATO": 2,
    }
