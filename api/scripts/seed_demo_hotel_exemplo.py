"""
Popula um tenant fictício "Hotel Exemplo" (slug hotel-exemplo) com dados de
demonstração em praticamente todos os módulos do sistema, para uso em
apresentação comercial.

Uso (dev local via Docker Compose):

    docker cp api/scripts/seed_demo_hotel_exemplo.py registro-api-1:/tmp/seed_demo_hotel_exemplo.py
    docker exec -e PYTHONPATH=/app -w /app registro-api-1 \
        python /tmp/seed_demo_hotel_exemplo.py

Uso em produção (só depois de validar em dev e com backup feito):

    CONFIRM_PROD=yes python /tmp/seed_demo_hotel_exemplo.py

Idempotente pelo slug do tenant: se "hotel-exemplo" já existir, aborta sem
duplicar nada.
"""

import asyncio
import os
from datetime import UTC, date, datetime, time, timedelta

import bcrypt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domain.apartment_inspections.service import create_apartment_inspection
from app.domain.audit_reports.service import create_audit_report
from app.domain.bulletin.service import create_post
from app.domain.check_suites.service import create_check_suite
from app.domain.checklists.service import create_template as create_checklist_template
from app.domain.contracts.service import (
    create_contract,
    create_cost_center,
    create_supplier,
    create_supplier_contact,
)
from app.domain.employees.service import create_employee
from app.domain.fiscal_requests.service import create_fiscal_request
from app.domain.handoffs.service import create_handoff
from app.domain.inspection_suites.service import create_inspection_suite
from app.domain.maintenance.service import create_record as create_maintenance_record
from app.domain.meetings.service import create_meeting
from app.domain.notifications.service import create_notification
from app.domain.occurrences.service import create_occurrence
from app.domain.platform.service import create_tenant
from app.domain.preventive_plans.service import create_plan as create_preventive_plan
from app.domain.procedures.service import create_procedure
from app.domain.registries.service import create_registry, update_registry
from app.domain.shift_reports.service import create_shift_report
from app.domain.stock.service import create_item as create_stock_item
from app.domain.stock.service import create_movement as create_stock_movement
from app.domain.timeclock.service import (
    create_device,
    create_enrollment,
    create_holiday,
    create_manual_punch,
    set_schedule_day,
)
from app.domain.work_diaries.service import create_work_diary
from app.domain.work_orders.service import create_order as create_work_order
from app.models import Company, Permission, Plan, PlatformUser, Role, Shift, Subscription, User

COMPANY_NAME = "Hotel Exemplo"
COMPANY_SLUG = "hotel-exemplo"
ADMIN_NAME = "Ana Diretora"
ADMIN_EMAIL = "contato@hotelexemplo.com.br"
ADMIN_PASSWORD = "HotelExemplo@123"


def fake_cpf(seed: int) -> str:
    base = f"{300000000 + seed:09d}"
    d1 = sum(int(c) * w for c, w in zip(base, range(10, 1, -1), strict=True)) % 11
    d1 = 0 if d1 < 2 else 11 - d1
    d2 = sum(int(c) * w for c, w in zip(base + str(d1), range(11, 1, -1), strict=True)) % 11
    d2 = 0 if d2 < 2 else 11 - d2
    return f"{base}{d1}{d2}"


def fake_cnpj(seed: int) -> str:
    return f"{10000000 + seed:08d}0001{seed % 100:02d}"


async def main() -> None:
    settings = get_settings()
    if settings.environment == "production" and os.getenv("CONFIRM_PROD") != "yes":
        raise RuntimeError(
            "Recusado: defina CONFIRM_PROD=yes para rodar este seed fictício em produção "
            "(faça isso só depois de validar em dev e com backup feito)."
        )

    async with SessionLocal() as session:
        existing = await session.scalar(select(Company.id).where(Company.slug == COMPANY_SLUG))
        if existing is not None:
            print(f"tenant '{COMPANY_SLUG}' já existe (id={existing}) — seed não repetido.")
            return

        plan_id = await session.scalar(select(Plan.id).where(Plan.code == "professional"))
        if plan_id is None:
            plan_id = await session.scalar(select(Plan.id).limit(1))
        if plan_id is None:
            raise RuntimeError("nenhum plano cadastrado — rode o seed padrão (app/seed.py) antes.")

        # 1. Tenant + role admin + usuário administrador
        platform_user_id = await session.scalar(select(PlatformUser.id).limit(1))
        if platform_user_id is None:
            raise RuntimeError("nenhum platform user cadastrado — rode o seed padrão antes.")

        company = await create_tenant(
            session,
            name=COMPANY_NAME,
            slug=COMPANY_SLUG,
            email="contato@hotelexemplo.com.br",
            document=fake_cnpj(1),
            timezone="America/Sao_Paulo",
            plan_id=plan_id,
            trial_days=365,
            actor_id=platform_user_id,
        )
        company_id = company.id
        print(f"tenant criado: {COMPANY_NAME} (id={company_id})")

        # marca assinatura como ativa (não trial) para a apresentação
        sub = await session.scalar(
            select(Subscription).where(Subscription.company_id == company_id)
        )
        if sub:
            sub.status = "active"
            sub.current_period_start = datetime.now(UTC).replace(tzinfo=None)
            sub.current_period_end = (datetime.now(UTC) + timedelta(days=365)).replace(tzinfo=None)
        await session.commit()

        # bootstrap: role + usuário admin criados via ORM direto (sem record_event),
        # já que ainda não existe nenhum usuário no tenant para ser o "actor" do evento
        wildcard = await session.scalar(select(Permission).where(Permission.code == "*"))
        role = Role(company_id=company_id, code="admin", name="Administrador")
        role.permissions = [wildcard] if wildcard else []
        session.add(role)
        await session.flush()

        admin = User(
            company_id=company_id,
            role_id=role.id,
            name=ADMIN_NAME,
            email=ADMIN_EMAIL.lower(),
            phone="11988887777",
            password=bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode(),
            active=True,
            email_verified_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        actor_id = admin.id
        actor_name, actor_email = admin.name, admin.email
        print(f"usuário admin criado: {ADMIN_EMAIL} / senha {ADMIN_PASSWORD}")

        # 2. Registries: setores, locais (com geofencing), funções
        setores = {}
        for name in ["Recepção", "Governança", "Manutenção", "Cozinha", "Financeiro"]:
            rec = await create_registry(session, company_id, actor_id, name, "Setor")
            setores[name] = rec.id

        locais = {}
        for name, lat, lng in [
            ("Recepção Térreo", -23.561000, -46.656000),
            ("Piscina", -23.560700, -46.655700),
            ("Cozinha Industrial", -23.561300, -46.656300),
            ("Estacionamento", -23.561800, -46.656800),
        ]:
            rec = await create_registry(session, company_id, actor_id, name, "Local")
            await update_registry(
                session,
                company_id,
                actor_id,
                rec.id,
                "Local",
                name,
                latitude=lat,
                longitude=lng,
                geofence_radius_m=120,
            )
            locais[name] = rec.id

        funcoes = {}
        for name in [
            "Recepcionista",
            "Camareira",
            "Técnico de Manutenção",
            "Cozinheiro",
            "Gerente",
        ]:
            rec = await create_registry(session, company_id, actor_id, name, "Função")
            funcoes[name] = rec.id
        print("registries criados: setores, locais, funções")

        # 3. Funcionários (RH / ponto)
        funcionarios_seed = [
            ("Marina Alves Souza", "Recepção", "Recepcionista"),
            ("Carlos Eduardo Lima", "Recepção", "Recepcionista"),
            ("Patrícia Nogueira Reis", "Governança", "Camareira"),
            ("João Pedro Farias", "Governança", "Camareira"),
            ("Fernanda Costa Ribeiro", "Manutenção", "Técnico de Manutenção"),
            ("Rodrigo Teixeira Alves", "Cozinha", "Cozinheiro"),
            ("Juliana Marques Pinto", "Cozinha", "Cozinheiro"),
            ("Bruno Henrique Castro", "Financeiro", "Gerente"),
        ]
        employees = []
        for i, (name, setor, funcao) in enumerate(funcionarios_seed, start=1):
            emp = await create_employee(
                session,
                company_id,
                actor_id,
                name=name,
                cpf=fake_cpf(i),
                status="active",
                job_title=funcao,
                hire_date="2025-03-01",
                registration_number=f"HE-{i:03d}",
                sector_id=setores[setor],
            )
            employees.append(emp)
        print(f"funcionários criados: {len(employees)}")

        # 4. Ponto: dispositivo, matrícula, escala e batidas dos últimos 14 dias
        shifts = (
            await session.scalars(
                select(Shift).where(Shift.company_id == company_id, Shift.deleted_at.is_(None))
            )
        ).all()
        shift_manha = shifts[0]
        device = await create_device(
            session,
            company_id,
            actor_id,
            name="Relógio Recepção",
            model="control_id",
            serial_number="HE-CTRLID-001",
            location_id=locais["Recepção Térreo"],
        )
        await create_enrollment(
            session, company_id, actor_id, employee_id=employees[0].id, external_id="1"
        )

        today = date.today()
        start = today - timedelta(days=14)
        for emp in employees[:5]:
            d = start
            while d <= today:
                if d.weekday() < 6:
                    await set_schedule_day(
                        session, company_id, actor_id, emp.id, d, shift_manha.id, None
                    )
                    await create_manual_punch(
                        session,
                        company_id,
                        actor_id,
                        employee_id=emp.id,
                        punched_at=datetime.combine(d, time(7, 0)),
                        punch_type="in",
                        notes=None,
                    )
                    await create_manual_punch(
                        session,
                        company_id,
                        actor_id,
                        employee_id=emp.id,
                        punched_at=datetime.combine(d, time(16, 0)),
                        punch_type="out",
                        notes=None,
                    )
                d += timedelta(days=1)

        await create_holiday(
            session,
            company_id,
            actor_id,
            holiday_date=date(today.year, 9, 7),
            name="Independência do Brasil",
        )
        await create_holiday(
            session, company_id, actor_id, holiday_date=date(today.year, 12, 25), name="Natal"
        )
        print("ponto: dispositivo, escala e batidas geradas; feriados cadastrados")

        # 5. Ocorrências
        for title, status in [
            ("Vazamento no banheiro do quarto 204", 1),
            ("Ar-condicionado com ruído no quarto 310", 1),
            ("Reclamação de barulho no 5º andar", 3),
            ("Troca de lâmpada queimada no corredor", 2),
            ("Wi-Fi instável na área da piscina", 1),
        ]:
            await create_occurrence(
                session,
                company_id,
                actor_id,
                actor_name,
                actor_email,
                title=title,
                description=f"Ocorrência de demonstração: {title}.",
                unit=None,
                deadline=today + timedelta(days=3),
                status=status,
                sector_id=setores["Manutenção"],
                location_id=None,
                owner_user_id=actor_id,
                notify_user_ids=None,
            )
        print("ocorrências criadas")

        # 6. Solicitações fiscais
        for req_type, title, status in [
            ("nota_fiscal", "Emissão de nota fiscal - hospedagem 08/07", "Em andamento"),
            ("cancelamento", "Cancelamento de reserva 4021", "Concluído"),
            ("nota_fiscal", "Emissão de nota fiscal - evento corporativo", "Em espera"),
            ("segunda_via", "Segunda via de recibo - quarto 118", "Em andamento"),
        ]:
            await create_fiscal_request(
                session,
                company_id,
                actor_id,
                request_type=req_type,
                title=title,
                apartment="118",
                requester=ADMIN_NAME,
                description=f"Solicitação fictícia: {title}.",
                status=status,
                payload={},
            )
        print("solicitações fiscais criadas")

        # 7. Ordens de serviço
        for title, priority, category in [
            ("Reparo de vazamento - quarto 204", "alta", "Hidráulica"),
            ("Manutenção do ar-condicionado - quarto 310", "media", "Refrigeração"),
            ("Pintura do corredor do 3º andar", "baixa", "Pintura"),
            ("Troca de fechadura eletrônica - quarto 512", "alta", "Elétrica"),
        ]:
            await create_work_order(
                session,
                company_id,
                actor_id,
                actor_name,
                actor_email,
                title=title,
                description=f"OS de demonstração: {title}.",
                priority=priority,
                category=category,
                location_id=None,
                occurrence_id=None,
                maintenance_id=None,
                assigned_user_id=actor_id,
                notify_user_ids=None,
                sla_hours=48,
            )
        print("ordens de serviço criadas")

        # 8. Fornecedores, centros de custo e contratos
        fornecedor1 = await create_supplier(
            session,
            company_id,
            actor_id,
            {
                "name": "Limpeza Total Serviços Ltda",
                "document": fake_cnpj(10),
                "document_type": "cnpj",
                "category": "Limpeza",
                "email": "contato@limpezatotal.com.br",
            },
        )
        await create_supplier_contact(
            session,
            company_id,
            actor_id,
            fornecedor1.id,
            {
                "name": "Roberto Dias",
                "role": "Comercial",
                "email": "roberto@limpezatotal.com.br",
                "is_primary": True,
            },
        )
        fornecedor2 = await create_supplier(
            session,
            company_id,
            actor_id,
            {
                "name": "TechNet Internet e Redes",
                "document": fake_cnpj(11),
                "document_type": "cnpj",
                "category": "Tecnologia",
                "email": "suporte@technet.com.br",
            },
        )

        cc_admin = await create_cost_center(
            session, company_id, actor_id, {"name": "Administração", "code": "ADM-01"}
        )
        cc_manut = await create_cost_center(
            session, company_id, actor_id, {"name": "Manutenção", "code": "MAN-01"}
        )
        await create_cost_center(
            session,
            company_id,
            actor_id,
            {"name": "Manutenção Predial", "code": "MAN-02", "parent_id": cc_manut.id},
        )

        await create_contract(
            session,
            company_id,
            actor_id,
            {
                "title": "Contrato de limpeza terceirizada",
                "contract_type": "servico",
                "supplier_id": fornecedor1.id,
                "responsible_user_id": actor_id,
                "status": "ativo",
                "start_date": today - timedelta(days=180),
                "end_date": today + timedelta(days=185),
                "monthly_value": 8500.00,
                "currency": "BRL",
                "cost_center_id": cc_admin.id,
            },
            [],
        )
        await create_contract(
            session,
            company_id,
            actor_id,
            {
                "title": "Contrato de link de internet dedicado",
                "contract_type": "fornecimento",
                "supplier_id": fornecedor2.id,
                "responsible_user_id": actor_id,
                "status": "rascunho",
                "monthly_value": 1200.00,
                "currency": "BRL",
                "cost_center_id": cc_manut.id,
            },
            [],
        )
        print("fornecedores, centros de custo e contratos criados")

        # 9. Reuniões
        await create_meeting(
            session,
            company_id,
            actor_id,
            actor_name,
            actor_email,
            title="Reunião semanal de operações",
            description="Alinhamento entre setores.",
            scheduled_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=2),
            location="Sala de reuniões",
            status="Agendada",
            owner_user_id=actor_id,
            participants=[{"user_id": actor_id, "role": "organizer"}],
            subjects=[{"title": "Ocupação da semana"}, {"title": "Pendências de manutenção"}],
            notify_user_ids=None,
        )
        print("reuniões criadas")

        # 10. Relatórios de turno e passagens de plantão
        await create_shift_report(
            session,
            company_id,
            actor_id,
            actor_name,
            actor_email,
            title="Relatório de turno - manhã",
            description="Turno tranquilo, sem intercorrências.",
            shift_date=today,
            shift_type="Manhã",
            started_at=datetime.combine(today, time(7, 0)),
            ended_at=datetime.combine(today, time(15, 0)),
            status="Concluído",
            owner_user_id=actor_id,
            notify_user_ids=None,
        )
        for title, priority in [
            ("Hóspede do 204 aguardando retorno da manutenção", "alta"),
            ("Confirmar chegada de grupo às 14h", "normal"),
        ]:
            await create_handoff(
                session,
                company_id,
                actor_id,
                title=title,
                description=f"Passagem de plantão: {title}.",
                priority=priority,
                category="Recepção",
                target_shift="Tarde",
                target_date=today,
            )
        print("relatórios de turno e passagens de plantão criados")

        # 11. Estoque
        item1 = await create_stock_item(
            session,
            company_id,
            actor_id,
            name="Papel higiênico",
            category="Higiene",
            unit="pacote",
            min_quantity=20,
            current_quantity=45,
            location_id=locais["Cozinha Industrial"],
        )
        await create_stock_item(
            session,
            company_id,
            actor_id,
            name="Sabonete líquido",
            category="Higiene",
            unit="litro",
            min_quantity=10,
            current_quantity=8,
            location_id=None,
        )
        await create_stock_movement(
            session,
            company_id,
            actor_id,
            item_id=item1[0].id,
            movement_type="saida",
            quantity=5,
            reason="Reposição dos apartamentos",
            work_order_id=None,
            occurrence_id=None,
        )
        print("estoque criado")

        # 12. Manutenção preventiva
        await create_maintenance_record(
            session,
            company_id,
            actor_id,
            actor_name,
            actor_email,
            title="Verificação do gerador de emergência",
            description="Teste mensal do gerador.",
            category="Elétrica",
            status="Concluído",
            priority="media",
            location_id=None,
            owner_user_id=actor_id,
            notify_user_ids=None,
        )
        await create_preventive_plan(
            session,
            company_id,
            actor_id,
            name="Manutenção de ar-condicionados",
            description="Limpeza e checagem de filtros.",
            recurrence="monthly",
            category="Refrigeração",
            priority="media",
            assigned_user_id=actor_id,
            location_id=None,
            sla_hours=24,
        )
        await create_preventive_plan(
            session,
            company_id,
            actor_id,
            name="Teste de bombas de piscina",
            description="Checagem semanal do sistema de filtragem.",
            recurrence="weekly",
            category="Hidráulica",
            priority="baixa",
            assigned_user_id=actor_id,
            location_id=locais["Piscina"],
            sla_hours=8,
        )
        print("manutenção preventiva criada")

        # 13. Checklists e diários de obra
        await create_checklist_template(
            session,
            company_id,
            actor_id,
            name="Checklist de limpeza de quartos",
            description="Checklist padrão de governança.",
            recurrence="daily",
            category="Governança",
            assigned_user_id=actor_id,
            next_due=today,
            items=[
                {"label": "Trocar roupa de cama", "sort_order": 0},
                {"label": "Repor amenities", "sort_order": 1},
                {"label": "Aspirar carpete", "sort_order": 2},
            ],
        )
        await create_work_diary(
            session,
            company_id,
            actor_id,
            diary_date=today,
            title="Reforma da piscina - dia 1",
            description="Início dos trabalhos de reforma.",
            weather="Ensolarado",
            status="Em andamento",
            owner_user_id=actor_id,
            activities=[{"description": "Remoção do revestimento antigo", "sort_order": 0}],
            teams=[
                {
                    "worker_name": "Equipe Reforma Azul",
                    "role": "Pedreiro",
                    "hours_worked": 8,
                    "sort_order": 0,
                }
            ],
            equipment=[{"equipment_name": "Furadeira industrial", "quantity": 2, "sort_order": 0}],
            observations=[{"content": "Sem intercorrências no primeiro dia.", "sort_order": 0}],
        )
        print("checklists e diário de obra criados")

        # 14. Vistorias e checklists de suíte
        suite = await create_inspection_suite(
            session,
            company_id,
            actor_id,
            name="Checklist padrão de apartamento",
            description="Itens verificados em toda vistoria.",
            type="Apartamento",
            status="Ativo",
            owner_user_id=actor_id,
            items=[
                {"area": "Banheiro", "item_name": "Torneiras e chuveiro", "sort_order": 0},
                {"area": "Quarto", "item_name": "Ar-condicionado", "sort_order": 1},
            ],
        )
        await create_apartment_inspection(
            session,
            company_id,
            actor_id,
            unit="204",
            apartment="204",
            inspection_type="Check-out",
            inspection_suite_id=suite["suite"].id,
            inspector_user_id=actor_id,
            scheduled_at=datetime.now(UTC).replace(tzinfo=None),
            completed_at=None,
            status="Pendente",
            notes=None,
        )
        await create_check_suite(
            session,
            company_id,
            actor_id,
            name="Checklist de abertura de recepção",
            description="Itens diários de abertura.",
            status="Ativo",
            owner_user_id=actor_id,
            items=[
                {"label": "Conferir caixa", "sort_order": 0},
                {"label": "Testar sistema PMS", "sort_order": 1},
            ],
        )
        print("vistorias e checklists de suíte criados")

        # 15. Auditoria operacional
        await create_audit_report(
            session,
            company_id,
            actor_id,
            report_date=today,
            shift_type="Manhã",
            auditor_user_id=actor_id,
            status="Concluído",
            notes="Auditoria de rotina sem apontamentos críticos.",
            items=[
                {
                    "category": "Recepção",
                    "description": "Atendimento telefônico",
                    "status": "ok",
                    "sort_order": 0,
                },
                {
                    "category": "Governança",
                    "description": "Padrão de arrumação dos quartos",
                    "status": "ok",
                    "sort_order": 1,
                },
            ],
        )
        print("relatório de auditoria criado")

        # 16. Procedimentos e mural de avisos
        for name, link in [
            ("Manual de check-in", "https://hotelexemplo.com.br/manuais/checkin.pdf"),
            (
                "Procedimento de emergência de incêndio",
                "https://hotelexemplo.com.br/manuais/incendio.pdf",
            ),
        ]:
            await create_procedure(session, company_id, actor_id, name=name, link=link, file=None)
        await create_post(
            session,
            company_id,
            actor_id,
            actor_name,
            actor_email,
            title="Bem-vindos ao novo sistema Registro!",
            body="A partir de hoje usamos o Registro para gestão operacional.",
            pinned=True,
            expires_at=None,
            notify_user_ids=None,
        )
        print("procedimentos e mural criados")

        # 17. Notificações de exemplo para o usuário admin
        for title, body in [
            ("Nova ordem de serviço atribuída a você", "Reparo de vazamento - quarto 204"),
            (
                "Contrato próximo do vencimento",
                "Contrato de limpeza terceirizada vence em 6 meses.",
            ),
        ]:
            await create_notification(
                session, company_id=company_id, user_id=actor_id, title=title, body=body
            )
        print("notificações criadas")

        print(f"\nOK — tenant '{COMPANY_SLUG}' populado com dados fictícios para apresentação.")
        print(f"Login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"Dispositivo de ponto: {device.name} (token {device.webhook_token})")


if __name__ == "__main__":
    asyncio.run(main())
