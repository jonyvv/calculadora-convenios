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


def test_agreement_structuring_agent_merges_salary_scale_from_second_document(tmp_path):
    result = agent(tmp_path).process({
        "document_metadata": {"source_document": "reglas.pdf, escala.pdf"},
        "full_text": """
        ## SOURCE_DOCUMENT: reglas.pdf
        Convenio CCT 40/89. Ley 19032. Articulo 12. Licencias y ausencias.

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | NO_INDICADO | NO_INDICADO | NO_INDICADO | NO_INDICADO | NO_INDICADO | el convenio normativo no trae escala |

        ## EVENT_RULES
        Falta injustificada pierde presentismo.

        ## SOURCE_DOCUMENT: escala.pdf
        Informe tecnico CCT 40/89 vigencia desde 01/04/2026.

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | 1 | Chofer de primera categoria | Abril 2026 | $ 984.338,23 | $ 1.050.000,00 | escala salarial |
        | 2 | Administrativo de segunda categoria | Abril 2026 | $ 942.242,71 | $ 990.000,00 | escala salarial |

        ## HABERES_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | PRESENTISMO | Presentismo | FIXED | $ 60.000,00 | NO_INDICADO | BASIC | TODAS | Abril 2026 | remunerativo |
        """,
    })

    agreement_path = tmp_path / "storage" / "convenios" / result["agreement_id"] / f"{result['version']}.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))

    assert [category["category_id"] for category in agreement["categories"]] == ["1", "2"]
    assert agreement["categories"][0]["name"] == "Chofer De Primera Categoria"
    assert agreement["categories"][0]["basic_salary"] == 984338.23
    assert all(category["name"] != "Ley" for category in agreement["categories"])


def test_agreement_structuring_agent_does_not_duplicate_table_concepts_with_heuristics(tmp_path):
    result = agent(tmp_path).process({
        "document_metadata": {"source_document": "camioneros.pdf"},
        "full_text": """
        Convenio colectivo CCT 40/89. Antiguedad, presentismo y adicionales de convenio.
        Deducciones: jubilacion, obra social y sindicato.

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | 1 | Chofer de primera categoria | Abril 2026 | $ 984.338,23 | $ 1.050.000,00 | escala salarial |

        ## HABERES_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | HR01 | Antiguedad | PERCENTAGE | NO_INDICADO | 1% | BASIC | TODAS | Abril 2026 | remunerativo |
        | HR02 | Premio por Presentismo | FIXED | $ 60.000,00 | NO_INDICADO | BASIC | TODAS | Abril 2026 | remunerativo |
        | NO_INDICADO | Pluralidad Tareas Grupo III | PERCENTAGE | NO_INDICADO | 18% | BASIC | TODAS | Abril 2026 | remunerativo |

        ## HABERES_NO_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | HNR01 | Comida | FIXED | $ 15.061,95 | NO_INDICADO | NO_INDICADO | TODAS | Abril 2026 | no remunerativo |

        ## RETENCIONES_DEDUCCIONES
        | code | concepto | porcentaje | importe | base | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | D01 | Aportes de Ley | 17% | NO_INDICADO | Total Remunerativo | seguridad social |
        | D02 | Contribucion Solidaria | 3% | NO_INDICADO | Total Remunerativo | convenio |
        """,
    })

    agreement_path = tmp_path / "storage" / "convenios" / result["agreement_id"] / f"{result['version']}.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))
    remunerative_codes = [item["code"] for item in agreement["salary_model"]["remunerative_items"]]
    deduction_codes = [item["code"] for item in agreement["salary_model"]["deductions"]]

    assert "SENIORITY" not in remunerative_codes
    assert "PRESENTISMO" not in remunerative_codes
    assert "ADICIONAL" not in remunerative_codes
    assert "PLURALIDAD_TAREAS_GRUPO_III" in remunerative_codes
    assert "JUBILACION" not in deduction_codes
    assert "OBRA_SOCIAL" not in deduction_codes
    assert deduction_codes == ["D01", "D02"]


def test_agreement_structuring_agent_moves_percentage_wage_additional_to_remunerative(tmp_path):
    result = agent(tmp_path).process({
        "document_metadata": {"source_document": "camioneros.pdf"},
        "full_text": """
        Convenio CCT 40/89 vigencia desde 01/04/2026.

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | 1 | Chofer de primera categoria | Abril 2026 | $ 984.338,23 | $ 1.050.000,00 | escala salarial |

        ## HABERES_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | HR04 | Rama Recoleccion de Residuos | PERCENTAGE | NO_INDICADO | 15% | BASIC | TODAS | Abril 2026 | remunerativo |

        ## HABERES_NO_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | NO_INDICADO | Diferencial Rama Recoleccion | PERCENTAGE | NO_INDICADO | 15% | BASIC | TODAS | Abril 2026 | no remunerativo |
        | HNR01 | Comida | FIXED | $ 15.061,95 | NO_INDICADO | NO_INDICADO | TODAS | Abril 2026 | no remunerativo |
        """,
    })

    agreement_path = tmp_path / "storage" / "convenios" / result["agreement_id"] / f"{result['version']}.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))

    remunerative_codes = {item["code"] for item in agreement["salary_model"]["remunerative_items"]}
    non_remunerative_codes = {item["code"] for item in agreement["salary_model"]["non_remunerative_items"]}

    assert "DIFERENCIAL_RAMA_RECOLECCION" in remunerative_codes
    assert "DIFERENCIAL_RAMA_RECOLECCION" not in non_remunerative_codes
    assert "HNR01" in non_remunerative_codes


def test_agreement_structuring_agent_keeps_multiple_deductions_with_repeated_or_missing_codes(tmp_path):
    result = agent(tmp_path).process({
        "document_metadata": {"source_document": "descuentos.pdf"},
        "full_text": """
        Convenio CCT 40/89 vigencia desde 01/04/2026.

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | 1 | Chofer de primera categoria | Abril 2026 | $ 984.338,23 | $ 1.050.000,00 | escala salarial |

        ## HABERES_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | BASIC | Sueldo basico | FIXED | NO_INDICADO | NO_INDICADO | BASIC | TODAS | Abril 2026 | remunerativo |

        ## RETENCIONES_DEDUCCIONES
        | code | descripcion | alicuota | base_calculo | observaciones |
        | --- | --- | --- | --- | --- |
        | D | Jubilacion | 11% | Total Remunerativo | ley |
        | D | Obra social | 3% | Total Remunerativo | ley |
        | NO_INDICADO | Ley 19032 | 3% | Total Remunerativo | ley |
        | RETENCION | Sindicato | 2% | Total Remunerativo | convenio |
        """,
    })

    agreement_path = tmp_path / "storage" / "convenios" / result["agreement_id"] / f"{result['version']}.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))
    deductions = agreement["salary_model"]["deductions"]

    assert {deduction["name"]: deduction["rate"] for deduction in deductions} == {
        "Jubilacion": 11,
        "Obra social": 3,
        "Ley 19032": 3,
        "Sindicato": 2,
    }
    assert len(deductions) == 4


def test_agreement_structuring_agent_marks_variable_viaticos_as_manual(tmp_path):
    result = agent(tmp_path).process({
        "document_metadata": {"source_document": "viaticos.pdf"},
        "full_text": """
        Convenio CCT 40/89 vigencia desde 01/05/2026.

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | 1 | Chofer de primera categoria | Mayo 2026 | $ 984.338,23 | $ 1.050.000,00 | escala salarial |

        ## HABERES_NO_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | VIATICO_KM | Viatico por kilometro | FIXED | $ 50,00 | NO_INDICADO | KM | TODAS | Mayo 2026 | cargar kilometros recorridos |
        | HNR01 | Viatico fijo mensual | FIXED | $ 10.000,00 | NO_INDICADO | NO_INDICADO | TODAS | Mayo 2026 | importe fijo mensual |
        """,
    })

    agreement_path = tmp_path / "storage" / "convenios" / result["agreement_id"] / f"{result['version']}.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))
    items = {item["code"]: item for item in agreement["salary_model"]["non_remunerative_items"]}

    assert items["VIATICO_KM"]["input_mode"] == "MANUAL"
    assert items["VIATICO_KM"]["unit"] == "KM"


def test_agreement_structuring_agent_normalizes_manual_km_items_without_formula(tmp_path):
    result = agent(tmp_path).process({
        "document_metadata": {"source_document": "viaticos_km.pdf"},
        "full_text": """
        Convenio CCT 40/89 vigencia desde 01/05/2026.

        ## ESCALA_SALARIAL_CATEGORIAS
        | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
        | --- | --- | --- | --- | --- | --- |
        | 1 | Chofer de primera categoria | Mayo 2026 | $ 984.338,23 | $ 1.050.000,00 | escala salarial |

        ## HABERES_NO_REMUNERATIVOS
        | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
        | --- | --- | --- | --- | --- | --- | --- | --- | --- |
        | RETRIB_KM | Retribucion por kilometro | FORMULA | $ 120,00 | NO_INDICADO | KM | TODAS | Mayo 2026 | CARGA_MANUAL kilometros recorridos |
        | VIAT_KM | Viatico por kilometro | FORMULA | $ 80,00 | NO_INDICADO | KM | TODAS | Mayo 2026 | CARGA_MANUAL kilometros recorridos |
        """,
    })

    agreement_path = tmp_path / "storage" / "convenios" / result["agreement_id"] / f"{result['version']}.json"
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))
    items = {item["code"]: item for item in agreement["salary_model"]["non_remunerative_items"]}

    assert "Formula faltante para RETRIB_KM" not in result["warnings"]
    assert "Formula faltante para VIAT_KM" not in result["warnings"]
    assert items["RETRIB_KM"]["calculation_type"] == "FIXED"
    assert items["RETRIB_KM"]["amount"] == 120
    assert items["RETRIB_KM"]["input_mode"] == "MANUAL"
    assert items["RETRIB_KM"]["unit"] == "KM"
    assert items["VIAT_KM"]["calculation_type"] == "FIXED"
    assert items["VIAT_KM"]["amount"] == 80
    assert items["VIAT_KM"]["input_mode"] == "MANUAL"
    assert items["VIAT_KM"]["unit"] == "KM"
