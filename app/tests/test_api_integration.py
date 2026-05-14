from fastapi.testclient import TestClient

from app.main import create_app


def test_import_employee_events_payroll_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    upload = client.post("/agreements/upload", files={"file": ("cct.txt", b"CCT 40/89 Categoria A basico $100.000,00 presentismo 10% jubilacion 11% horas extra 50%", "text/plain")})
    assert upload.status_code == 200
    assert upload.json()["agreement"]["metadata"]["agreement_id"] == "CCT_40_89"

    employee = client.post("/employees", json={
        "employee_id": "E1",
        "agreement_id": "CCT_40_89",
        "category_id": "A",
        "seniority_years": 2,
    })
    assert employee.status_code == 200

    events = client.post("/events", json={
        "employee_id": "E1",
        "period": "2026-04",
        "events": [{"type": "OVERTIME", "subtype": "OT_50", "hours": 8}],
    })
    assert events.status_code == 200

    payroll = client.post("/payroll/calculate", json={"employee_id": "E1", "period": "2026-04"})
    assert payroll.status_code == 200
    assert payroll.json()["net_salary"] > 0

    audit = client.post("/payroll/audit", json={"employee_id": "E1", "period": "2026-04"})
    assert audit.status_code == 200
    assert audit.json()["status"] == "APPROVED"


def test_upload_multiple_agreement_files_creates_active_agreement(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.post("/agreements/upload-files", files=[
        ("files", ("CCT_130_75.txt", b"Convenio colectivo CCT 130/75 comercio", "text/plain")),
        ("files", ("paritaria_2026.txt", b"Escala salarial y adicionales", "text/plain")),
    ])

    assert response.status_code == 200
    agreement = response.json()["agreement"]
    assert agreement["metadata"]["agreement_id"] == "CCT_130_75"
    assert "CCT_130_75.txt, paritaria_2026.txt" == agreement["metadata"]["source_document"]
    assert response.json()["extractions"][0]["filename"] == "CCT_130_75.txt, paritaria_2026.txt"

    active = client.get("/agreements/CCT_130_75")
    assert active.status_code == 200
    assert active.json()["metadata"]["version"] == "2026_01"


def test_employee_seniority_is_calculated_from_hire_date(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.post("/employees", json={
        "employee_id": "E2",
        "agreement_id": "CCT_40_89",
        "category_id": "A",
        "hire_date": "2020-01-01",
    })

    assert response.status_code == 200
    assert response.json()["seniority_years"] >= 6


def test_employee_can_be_listed_and_reassigned_to_another_agreement(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    client.post("/agreements/upload-files", files=[
        ("files", ("CCT_130_75.txt", b"Convenio colectivo CCT 130/75 comercio", "text/plain")),
    ])
    created = client.post("/employees", json={
        "employee_id": "E3",
        "agreement_id": "CCT_130_75",
        "category_id": "A",
        "hire_date": "2020-01-01",
    })
    assert created.status_code == 200

    listed = client.get("/employees")
    assert listed.status_code == 200
    assert any(employee["employee_id"] == "E3" for employee in listed.json())

    updated = client.put("/employees/E3", json={
        "employee_id": "E3",
        "agreement_id": "CCT_40_89",
        "category_id": "A",
        "hire_date": "2021-01-01",
    })
    assert updated.status_code == 200
    assert updated.json()["agreement_id"] == "CCT_40_89"


def test_agreement_can_be_updated_and_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    upload = client.post("/agreements/upload-files", files=[
        ("files", ("CCT_130_75.txt", b"Convenio colectivo CCT 130/75 comercio", "text/plain")),
    ])
    agreement = upload.json()["agreement"]
    agreement["salary_model"]["deductions"][0]["rate"] = 10

    updated = client.put(f"/agreements/{agreement['metadata']['agreement_id']}", json=agreement)
    assert updated.status_code == 200
    assert updated.json()["salary_model"]["deductions"][0]["rate"] == 10

    deleted = client.delete(f"/agreements/{agreement['metadata']['agreement_id']}?version={agreement['metadata']['version']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_full_smart_calculator_case_from_multi_file_cct(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    client = TestClient(create_app())

    convenio = b"""
    Convenio colectivo CCT 999/26 Transporte de prueba.
    Sindicato: Sindicato Test de Transporte.
    Actividad: Transporte de prueba.
    Ambito nacional.
    Vigencia desde 01/06/2026 hasta 30/06/2026.
    Horas extra al 50% en dias comunes y horas extra al 100% en domingos y feriados.
    Falta injustificada pierde presentismo.
    """
    escala = b"""
    ## ESCALA_SALARIAL_CATEGORIAS
    | category_id | puesto_rol_categoria | periodo | basico | total_remunerativo | observaciones |
    | A | Chofer de primera categoria | Junio 2026 | $ 300.000,00 | $ 342.000,00 | escala salarial |

    ## HABERES_REMUNERATIVOS
    | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
    | ANTIG | Antiguedad | PERCENTAGE | NO_INDICADO | 1% | BASIC | TODOS | Junio 2026 | 1% por anio |
    | PRESENTISMO | Presentismo | PERCENTAGE | NO_INDICADO | 10% | BASIC | TODOS | Junio 2026 | pierde por falta injustificada |

    ## HABERES_NO_REMUNERATIVOS
    | code | concepto | calculation_type | importe | porcentaje | base | aplica_a_categoria | periodo | observaciones |
    | VIAT_DIA | Viatico diario | FIXED | $ 10.000,00 | NO_INDICADO | BASIC | A | Junio 2026 | CARGA_MANUAL dias trabajados |

    ## RETENCIONES_DEDUCCIONES
    | code | concepto | porcentaje | importe | base | observaciones |
    | JUBILACION | Jubilacion | 11% | NO_INDICADO | REMUNERATIVE_TOTAL | legal |
    | LEY_19032 | Ley 19.032 | 3% | NO_INDICADO | REMUNERATIVE_TOTAL | legal |
    | OBRA_SOCIAL | Obra Social | 3% | NO_INDICADO | REMUNERATIVE_TOTAL | legal |
    """

    upload = client.post("/agreements/upload-files", files=[
        ("files", ("CCT_999_26_reglas.txt", convenio, "text/plain")),
        ("files", ("CCT_999_26_escala.txt", escala, "text/plain")),
    ])

    assert upload.status_code == 200
    agreement = upload.json()["agreement"]
    assert agreement["metadata"]["agreement_id"] == "CCT_999_26"
    assert agreement["metadata"]["source_document"] == "CCT_999_26_reglas.txt, CCT_999_26_escala.txt"
    assert agreement["identificacion_alcance"]["categorias_profesionales"][0]["nombre"] == "Chofer De Primera Categoria"
    assert agreement["remuneraciones"]["salario_basico"]
    assert agreement["remuneraciones"]["antiguedad"]
    assert agreement["remuneraciones"]["presentismo_asistencia"]
    assert agreement["remuneraciones"]["viaticos"]
    assert {item["code"] for item in agreement["salary_model"]["deductions"]} >= {"JUBILACION", "LEY_19032", "OBRA_SOCIAL", "SINDICATO"}

    employee = client.post("/employees", json={
        "employee_id": "E_SMART",
        "agreement_id": "CCT_999_26",
        "category_id": "A",
        "seniority_years": 4,
        "workday": "Completa",
    })
    assert employee.status_code == 200

    events = client.post("/events", json={
        "employee_id": "E_SMART",
        "period": "2026-06",
        "events": [
            {"type": "OVERTIME", "subtype": "OT_50", "hours": 10},
            {"type": "SALARY_ITEM", "subtype": "VIAT_DIA", "quantity": 3},
            {"type": "LIQUIDATION", "subtype": "SAC"},
        ],
    })
    assert events.status_code == 200

    payroll = client.post("/payroll/calculate", json={"employee_id": "E_SMART", "period": "2026-06"})
    assert payroll.status_code == 200
    result = payroll.json()
    details = {detail["code"]: detail for detail in result["details"]}

    assert details["BASIC"]["amount"] == 300000
    assert details["ANTIG"]["amount"] == 12000
    assert details["PRESENTISMO"]["amount"] == 30000
    assert details["OT_50"]["amount"] == 22500
    assert details["VIAT_DIA"]["amount"] == 30000
    assert details["SAC"]["amount"] == 182250
    assert result["gross_salary"] == 576750
    assert details["SINDICATO"]["amount"] == -10935
    assert result["deductions"] == 103882.5
    assert result["net_salary"] == 472867.5

    audit = client.post("/payroll/audit", json={"employee_id": "E_SMART", "period": "2026-06"})
    assert audit.status_code == 200
    assert audit.json()["status"] == "APPROVED"
