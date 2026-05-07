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
