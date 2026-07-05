"""Testes da importação em lote de contracheque (PC8): manifesto CSV + ZIP de PDFs,
casando cada PDF a um funcionário por CPF (com fallback por matrícula) — não depende
de nenhum ERP/sistema de folha fixo, já que CPF é universal em qualquer holerite."""

import io
import zipfile
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import Employee, EmployeePayslip
from tests.conftest import TENANT_A, auth_header, make_token

IMPORT_URL = "/api/v1/timeclock/employees/payslips/import"
PDF_BYTES = b"%PDF-1.4 fake content"


@pytest.fixture()
def mock_storage():
    with patch("app.domain.attachments.service.upload_file", return_value="fake/key.pdf"):
        yield


async def _create_employee(
    session, *, cpf: str | None = None, registration_number: str | None = None, name: str = "Func"
) -> Employee:
    employee = Employee(
        company_id=TENANT_A,
        name=name,
        cpf=cpf,
        registration_number=registration_number,
        status="active",
    )
    session.add(employee)
    await session.commit()
    await session.refresh(employee)
    return employee


def _zip_with(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _manifest(rows: list[str]) -> bytes:
    header = "cpf,matricula,competencia,arquivo"
    return "\n".join([header, *rows]).encode("utf-8")


def _upload(client, manifest: bytes, archive: bytes, headers: dict[str, str]):
    return client.post(
        IMPORT_URL,
        files={
            "manifest": ("manifesto.csv", manifest, "text/csv"),
            "archive": ("contracheques.zip", archive, "application/zip"),
        },
        headers=headers,
    )


@pytest.mark.asyncio
async def test_import_creates_payslip_by_cpf(client, session, mock_storage):
    employee = await _create_employee(session, cpf="11122233344", name="Maria")
    manifest = _manifest([f"{employee.cpf},,2026-06,maria.pdf"])
    archive = _zip_with({"maria.pdf": PDF_BYTES})

    resp = await _upload(client, manifest, archive, auth_header(TENANT_A))
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "total": 1,
        "created": 1,
        "updated": 0,
        "failed": 0,
        "results": [
            {
                "row": 1,
                "status": "created",
                "employee_name": "Maria",
                "reference_month": "2026-06",
                "error": None,
            }
        ],
    }

    payslip = await session.scalar(
        select(EmployeePayslip).where(EmployeePayslip.employee_id == employee.id)
    )
    assert payslip is not None
    assert str(payslip.reference_month) == "2026-06-01"


@pytest.mark.asyncio
async def test_import_fallback_matricula_when_cpf_blank(client, session, mock_storage):
    employee = await _create_employee(session, registration_number="MAT-42", name="João")
    manifest = _manifest([f",{employee.registration_number},2026-06,joao.pdf"])
    archive = _zip_with({"joao.pdf": PDF_BYTES})

    resp = await _upload(client, manifest, archive, auth_header(TENANT_A))
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert data["results"][0]["employee_name"] == "João"


@pytest.mark.asyncio
async def test_import_employee_not_found(client, session, mock_storage):
    manifest = _manifest(["00000000000,,2026-06,ninguem.pdf"])
    archive = _zip_with({"ninguem.pdf": PDF_BYTES})

    resp = await _upload(client, manifest, archive, auth_header(TENANT_A))
    assert resp.status_code == 200
    data = resp.json()
    assert data["failed"] == 1
    assert data["results"][0]["status"] == "failed"
    assert data["results"][0]["error"] == "funcionario_nao_encontrado"


@pytest.mark.asyncio
async def test_import_file_missing_in_zip(client, session, mock_storage):
    employee = await _create_employee(session, cpf="22233344455", name="Ana")
    manifest = _manifest([f"{employee.cpf},,2026-06,nao-existe.pdf"])
    archive = _zip_with({"outro-arquivo.pdf": PDF_BYTES})

    resp = await _upload(client, manifest, archive, auth_header(TENANT_A))
    assert resp.status_code == 200
    data = resp.json()
    assert data["failed"] == 1
    assert data["results"][0]["error"] == "arquivo_nao_encontrado_no_zip"


@pytest.mark.asyncio
async def test_import_reimport_same_competencia_updates_attachment(client, session, mock_storage):
    employee = await _create_employee(session, cpf="33344455566", name="Carla")
    manifest = _manifest([f"{employee.cpf},,2026-06,carla.pdf"])

    first = await _upload(
        client, manifest, _zip_with({"carla.pdf": PDF_BYTES}), auth_header(TENANT_A)
    )
    assert first.json()["created"] == 1

    second = await _upload(
        client,
        manifest,
        _zip_with({"carla.pdf": PDF_BYTES + b" v2"}),
        auth_header(TENANT_A),
    )
    data = second.json()
    assert data["created"] == 0
    assert data["updated"] == 1
    assert data["results"][0]["status"] == "updated"

    rows = (
        await session.execute(
            select(EmployeePayslip).where(EmployeePayslip.employee_id == employee.id)
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_import_rejects_zip_path_traversal(client, session, mock_storage):
    employee = await _create_employee(session, cpf="44455566677", name="Bia")
    manifest = _manifest([f"{employee.cpf},,2026-06,../evil.pdf"])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.pdf", PDF_BYTES)

    resp = await _upload(client, manifest, buf.getvalue(), auth_header(TENANT_A))
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_archive_entry"


@pytest.mark.asyncio
async def test_import_requires_permission(client, session, mock_storage):
    headers = {"Authorization": f"Bearer {make_token(TENANT_A, permissions=[])}"}
    manifest = _manifest(["11122233344,,2026-06,maria.pdf"])
    archive = _zip_with({"maria.pdf": PDF_BYTES})

    resp = await _upload(client, manifest, archive, headers)
    assert resp.status_code == 403
