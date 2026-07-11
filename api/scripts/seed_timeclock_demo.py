"""
Popula o tenant empresa-demo com dados fictícios do sistema de ponto: locais
com geofencing, setores, funcionários com PIN, escala, batidas (com atraso,
falta e esquecimento propositais), banco de horas, ajustes de ponto e
contracheques. Útil para visualizar o módulo de ponto sem precisar montar
dados manualmente tela por tela.

Uso (dev local via Docker Compose): `docker-compose.yml` só monta `api/app`,
`api/tests` e `api/alembic` como volume no container — `scripts/` não é
montado, então tem que copiar antes de rodar:

    docker cp api/scripts/seed_timeclock_demo.py registro-api-1:/tmp/seed_timeclock_demo.py
    docker exec -e PYTHONPATH=/app -w /app registro-api-1 \
        python /tmp/seed_timeclock_demo.py

Recusa rodar com ENVIRONMENT=production (nunca usar contra a VPS) e é
idempotente por matrícula: rodar de novo não duplica os 10 funcionários
fictícios (aborta cedo se já existir DEMO-001).
"""

import asyncio
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.attachments.service import create_attachment
from app.domain.employees.service import create_employee
from app.domain.registries.service import create_registry, update_registry
from app.domain.timeclock.service import (
    create_device,
    create_employee_payslip,
    create_enrollment,
    create_manual_punch,
    create_punch_adjustment_request,
    hash_pin,
    recalculate_hour_bank,
    review_punch_adjustment_request,
    set_hour_bank_initial_balance,
    set_schedule_day,
)
from app.models import Company, Employee, EmployeeCredential, Shift

COMPANY_SLUG = "empresa-demo"
ACTOR_EMAIL = "icaro@registro.local"
DEMO_PIN = "123456"

SETORES = ["Recepção", "Governança", "Manutenção", "Cozinha", "Segurança"]

FUNCIONARIOS = [
    ("Marina Alves Souza", "Recepção", "Recepção Principal"),
    ("Carlos Eduardo Lima", "Recepção", "Recepção Principal"),
    ("Patrícia Nogueira Reis", "Governança", "Recepção Principal"),
    ("João Pedro Farias", "Governança", "Recepção Principal"),
    ("Fernanda Costa Ribeiro", "Manutenção", "Manutenção e Estoque"),
    ("Rodrigo Teixeira Alves", "Manutenção", "Manutenção e Estoque"),
    ("Juliana Marques Pinto", "Cozinha", "Cozinha e Restaurante"),
    ("Bruno Henrique Castro", "Cozinha", "Cozinha e Restaurante"),
    ("Camila Rocha Andrade", "Segurança", "Recepção Principal"),
    ("Thiago Barbosa Nunes", "Segurança", "Recepção Principal"),
]


def fake_cpf(seed: int) -> str:
    base = f"{200000000 + seed:09d}"
    d1 = sum(int(c) * w for c, w in zip(base, range(10, 1, -1), strict=True)) % 11
    d1 = 0 if d1 < 2 else 11 - d1
    d2 = sum(int(c) * w for c, w in zip(base + str(d1), range(11, 1, -1), strict=True)) % 11
    d2 = 0 if d2 < 2 else 11 - d2
    return f"{base}{d1}{d2}"


async def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise RuntimeError(
            "Recusado: este script nunca deve rodar contra produção (dados fictícios)."
        )

    async with SessionLocal() as session:
        company_id = await session.scalar(select(Company.id).where(Company.slug == COMPANY_SLUG))
        if company_id is None:
            raise RuntimeError(f"tenant '{COMPANY_SLUG}' não encontrado")

        already = await session.scalar(
            select(Employee.id).where(
                Employee.company_id == company_id, Employee.registration_number == "DEMO-001"
            )
        )
        if already is not None:
            print("Já existe DEMO-001 neste tenant — seed não repetido (idempotente).")
            return

        from app.models import User

        actor_id = await session.scalar(
            select(User.id).where(User.company_id == company_id, User.email == ACTOR_EMAIL)
        )
        if actor_id is None:
            raise RuntimeError(f"usuário '{ACTOR_EMAIL}' não encontrado no tenant")

        # 1. Locais com geofencing
        locais = {}
        for name, lat, lng in [
            ("Recepção Principal", -23.561000, -46.656000),
            ("Cozinha e Restaurante", -23.560500, -46.655500),
            ("Manutenção e Estoque", -23.561500, -46.656500),
        ]:
            record = await create_registry(session, company_id, actor_id, name, "Local")
            await update_registry(
                session,
                company_id,
                actor_id,
                record.id,
                "Local",
                name,
                latitude=lat,
                longitude=lng,
                geofence_radius_m=150,
            )
            locais[name] = record.id
        print("locais:", locais)

        # 2. Setores
        setores = {}
        for name in SETORES:
            record = await create_registry(session, company_id, actor_id, name, "Setor")
            setores[name] = record.id
        print("setores:", setores)

        # 3. Turnos já existentes (seed automático de tenant) — pega Manhã e Tarde
        shifts = (
            await session.scalars(
                select(Shift).where(Shift.company_id == company_id, Shift.deleted_at.is_(None))
            )
        ).all()
        shift_by_name = {s.name: s for s in shifts}
        turno_manha = shift_by_name.get("Manhã") or shifts[0]
        turno_tarde = shift_by_name.get("Tarde") or shifts[0]
        print("turnos:", [s.name for s in shifts])

        # 4. Funcionários + credencial de PIN
        employees = []
        for i, (name, setor_name, local_name) in enumerate(FUNCIONARIOS, start=1):
            emp = await create_employee(
                session,
                company_id,
                actor_id,
                name=name,
                cpf=fake_cpf(i),
                status="active",
                job_title="Auxiliar" if i % 2 else "Assistente",
                hire_date="2025-01-15",
                registration_number=f"DEMO-{i:03d}",
                sector_id=setores[setor_name],
            )
            emp.location_id = locais[local_name]
            session.add(
                EmployeeCredential(
                    company_id=company_id,
                    employee_id=emp.id,
                    pin_hash=hash_pin(DEMO_PIN),
                    must_change_pin=False,
                    pin_set_at=datetime.now(),
                )
            )
            employees.append(emp)
        await session.commit()
        print(f"funcionários criados: {len(employees)} (PIN {DEMO_PIN} para todos)")

        # 5. Escala: turno manhã para os 5 primeiros, tarde para os outros 5, últimos 28 dias
        today = date.today()
        start = today - timedelta(days=28)
        for idx, emp in enumerate(employees):
            shift = turno_manha if idx < 5 else turno_tarde
            d = start
            while d <= today:
                if d.weekday() < 6:  # folga aos domingos
                    await set_schedule_day(session, company_id, actor_id, emp.id, d, shift.id, None)
                d += timedelta(days=1)
        print("escala gerada para 29 dias")

        # 6. Batidas manuais compatíveis com a escala, com variação realista
        #    (chegada adiantada/atrasada, 1 falta, 1 esquecimento de saída)
        punch_start_hour = {turno_manha.id: 7, turno_tarde.id: 13}
        punch_end_hour = {turno_manha.id: 16, turno_tarde.id: 22}
        for idx, emp in enumerate(employees):
            shift = turno_manha if idx < 5 else turno_tarde
            d = start
            day_counter = 0
            while d <= today:
                if d.weekday() < 6:
                    day_counter += 1
                    if day_counter == 10 and idx == 2:
                        d += timedelta(days=1)
                        continue  # falta proposital (Patrícia)
                    variance_in = [-5, 0, 3, 8, 0, -2, 12][day_counter % 7]
                    variance_out = [0, -3, 0, 5, 0, 0, -10][day_counter % 7]
                    checkin = datetime.combine(d, time(punch_start_hour[shift.id], 0)) + timedelta(
                        minutes=variance_in
                    )
                    await create_manual_punch(
                        session,
                        company_id,
                        actor_id,
                        employee_id=emp.id,
                        punched_at=checkin,
                        punch_type="in",
                        notes=None,
                    )
                    if not (day_counter == 15 and idx == 5):  # esquecimento proposital (Rodrigo)
                        checkout = datetime.combine(
                            d, time(punch_end_hour[shift.id], 0)
                        ) + timedelta(minutes=variance_out)
                        await create_manual_punch(
                            session,
                            company_id,
                            actor_id,
                            employee_id=emp.id,
                            punched_at=checkout,
                            punch_type="out",
                            notes=None,
                        )
                d += timedelta(days=1)
        print("batidas lançadas")

        # 7. Banco de horas: recalcula o período + saldo inicial para 2 funcionários
        for emp in employees:
            await recalculate_hour_bank(session, company_id, actor_id, emp.id, start, today)
        await set_hour_bank_initial_balance(
            session,
            company_id,
            actor_id,
            employees[0].id,
            start - timedelta(days=1),
            180,
            "Saldo migrado do sistema anterior",
        )
        await set_hour_bank_initial_balance(
            session,
            company_id,
            actor_id,
            employees[7].id,
            start - timedelta(days=1),
            -60,
            "Saldo negativo migrado do sistema anterior",
        )
        print("banco de horas recalculado")

        # 8. Ajustes de ponto: 1 pendente, 1 aprovado, 1 rejeitado
        adj_pendente = await create_punch_adjustment_request(
            session,
            company_id,
            employees[5].id,
            punch_id=None,
            requested_punched_at=datetime.combine(today - timedelta(days=1), time(22, 5)),
            requested_punch_type="out",
            reason="Esqueci de bater a saída ontem, saí no horário normal do turno.",
        )
        adj_aprovar = await create_punch_adjustment_request(
            session,
            company_id,
            employees[8].id,
            punch_id=None,
            requested_punched_at=datetime.combine(today - timedelta(days=3), time(7, 0)),
            requested_punch_type="in",
            reason="Cheguei mais cedo mas o app não registrou a entrada.",
        )
        adj_rejeitar = await create_punch_adjustment_request(
            session,
            company_id,
            employees[9].id,
            punch_id=None,
            requested_punched_at=datetime.combine(today - timedelta(days=2), time(13, 30)),
            requested_punch_type="in",
            reason="Erro de geolocalização no celular, cheguei no horário.",
        )
        assert adj_pendente is not None
        await review_punch_adjustment_request(
            session,
            company_id,
            actor_id,
            adj_aprovar.id,
            approve=True,
            review_notes="Aprovado, confirmado com o supervisor.",
        )
        await review_punch_adjustment_request(
            session,
            company_id,
            actor_id,
            adj_rejeitar.id,
            approve=False,
            review_notes="Sem registro de geofencing compatível, rejeitado.",
        )
        print("ajustes de ponto: 1 pendente, 1 aprovado, 1 rejeitado")

        # 9. Contracheques: 2 competências para os 3 primeiros funcionários
        for emp in employees[:3]:
            for month in ["2026-05", "2026-06"]:
                attachment = await create_attachment(
                    session,
                    company_id,
                    actor_id,
                    entity_type="employee_payslip",
                    entity_id=emp.id,
                    filename=f"contracheque-{month}.pdf",
                    content_type="application/pdf",
                    data=f"%PDF-1.4 contracheque ficticio {emp.name} {month}".encode(),
                    skip_audit=True,
                )
                if isinstance(attachment, str):
                    print("erro anexo:", attachment)
                    continue
                await create_employee_payslip(
                    session,
                    company_id,
                    actor_id,
                    employee_id=emp.id,
                    reference_month=date.fromisoformat(f"{month}-01"),
                    attachment_id=attachment.id,
                )
        print("contracheques criados")

        # 10. Dispositivo de ponto + vínculo (1 funcionário)
        device = await create_device(
            session,
            company_id,
            actor_id,
            name="Relógio Recepção (Control iD)",
            model="iDFace",
            serial_number="DEMO-CTRLID-001",
            location_id=locais["Recepção Principal"],
        )
        await create_enrollment(
            session,
            company_id,
            actor_id,
            employee_id=employees[0].id,
            external_id="1001",
        )
        print("dispositivo:", device.name, "webhook_token:", device.webhook_token)

        print("\nOK — seed de ponto concluído para empresa-demo.")
        print(f"Login colaborador: matrícula DEMO-001..DEMO-010, PIN {DEMO_PIN}")


if __name__ == "__main__":
    asyncio.run(main())
