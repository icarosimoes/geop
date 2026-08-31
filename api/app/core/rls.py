from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, company_id: int) -> None:
    """Seta o GUC `app.current_company_id` que as policies `tenant_isolation` (RLS)
    usam pra filtrar linhas por empresa.

    Precisa ser chamado ANTES de qualquer query numa tabela com RLS, a partir de um
    `company_id` já validado — normalmente um claim de JWT cuja assinatura já foi
    verificada (`decode_*_token`), então o valor é confiável mesmo sem checar ainda
    se o usuário/registro existe. Setar o GUC não concede privilégio nenhum, só
    restringe quais linhas ficam visíveis: se o `company_id` acabar não batendo com
    nada, a query seguinte simplesmente não encontra o registro (mesmo resultado de
    hoje, sem RLS).

    Sem isso, a primeira query numa tabela com `FORCE ROW LEVEL SECURITY` falha com
    "unrecognized configuration parameter" (fail-closed) — não é um 403 silencioso,
    quebra a rota inteira. Achado em docs/auditoria-2026-07-03.md#c1: a role da API
    era superusuário e ignorava RLS incondicionalmente, então essa ordem invertida
    nunca dava erro; só apareceu ao restringir a role (migration `20260831_0070`).

    `is_local=false` (terceiro argumento do `set_config`): escopo de **sessão**,
    não de transação. Um `SET LOCAL`/`is_local=true` some no primeiro `commit()`
    — qualquer query em tabela RLS feita numa transação seguinte da mesma
    request (comum: `record_event` + commit, depois mais uma query) voltaria a
    falhar. O `RESET app.current_company_id` no `finally` de `require_session`/
    `require_employee_session` (`app/core/dependencies.py`) existe exatamente
    pra limpar esse estado de sessão antes da conexão voltar pro pool — o par
    certo do `is_local=false` daqui. Achado ao ligar a timeline de chamados de
    suporte (`add_comment` faz `commit()` no meio da função) — ver
    docs/registro-trabalho.md.

    No-op fora do Postgres (SQLite nos testes locais sem `TEST_DATABASE_URL`) — RLS
    não existe lá, então não há o que setar.
    """
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT set_config('app.current_company_id', :cid, false)"),
            {"cid": str(company_id)},
        )
