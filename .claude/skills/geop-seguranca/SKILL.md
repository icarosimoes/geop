---
name: geop-seguranca
description: Skill de auditoria de segurança de supply chain (npm/pip) e CVEs em dependências do GEOP (api/, web/, admin/, colaborador/). Use para verificar se o projeto foi afetado por um ataque recente a pacote, auditar dependências comprometidas, corrigir CVEs, e guiar recuperação pós-incidente. TRIGGER quando o usuário menciona "supply chain", "CVE", "pacote comprometido", "auditoria de segurança", "npm audit", "vulnerabilidade", "pacote malicioso".
---

Portado de `~/dev/erpsolid/.claude/skills/jarvis-seguranca/` (mesma família Solid),
adaptado à topologia do GEOP: **um backend** (`api/`) e **três frontends** (`web/`,
`admin/`, `colaborador/`), cada um com seu próprio `package.json`/lockfile.

**Regra fundamental**: SEMPRE pesquise na internet antes de citar caminhos de UI ou
números de CVE — informações de segurança mudam rápido e é fácil alucinar um CVE ID.

---

## Estado atual verificado do GEOP (não presuma, confirme de novo se o CI mudou)

| Item | Status (confirmado em `.github/workflows/ci.yml`, 2026-09-04) |
|---|---|
| `pip-audit` da API | ✅ Já roda no CI (job "API — pip-audit"), `--strict --desc` |
| `npm audit` de `web/`/`admin/`/`colaborador/` | ❌ **Não roda no CI** — só `ruff`/`mypy`/pytest/Alembic no lado API e TypeScript check no lado Web; auditoria de dependência JS hoje é sempre manual, gap real |
| Tags Docker de infra (`docker-stack.yml`) | ⚠️ Flutuantes: `postgres:17-alpine`, `redis:7-alpine`, `minio/mc:latest`. `minio/minio` já é pinado (`RELEASE.2025-09-07T16-13-09Z`) — os outros três não |
| Imagens da aplicação em produção | ✅ Tag imutável `sha-<GITHUB_SHA completo>` (ver `docs/infra/deploy-swarm.md`) |
| Secrets em produção | ✅ Docker Swarm Secrets (`registro_database_url`, `registro_jwt_secret`, etc.) |
| JWT | ✅ `PyJWT` (`api/app/core/security.py`), não `python-jose` |

Se o usuário pedir pra fechar o gap de `npm audit`, é trabalho novo (adicionar job ao CI
para os três frontends) — não existe hoje.

---

## Protocolo de auditoria (executar sempre nesta ordem)

### Etapa 1 — Inventário

```bash
# package.json de cada frontend (ignora node_modules)
find . -name "package.json" -not -path "*/node_modules/*" | sort
# → web/package.json, admin/package.json, colaborador/package.json

# Dependências Python
cat api/pyproject.toml
```

### Etapa 2 — Auditar cada um dos 4 componentes

```bash
cd web && npm audit; cd ..
cd admin && npm audit; cd ..
cd colaborador && npm audit; cd ..

cd api
pip install -e ".[dev]" pip-audit
pip freeze --exclude registro-api > /tmp/requirements.txt
pip-audit --strict --desc -r /tmp/requirements.txt
```

Detalhe de CVE (npm):
```bash
npm audit --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for name, info in d.get('vulnerabilities', {}).items():
    for v in info.get('via', []):
        if isinstance(v, dict):
            print(f'{v.get(\"name\")}: {v.get(\"severity\")} — {v.get(\"title\")} ({v.get(\"url\")})')
"
```

**Interpretação de severidade**: `critical`/`high` → agir imediatamente. `moderate` →
avaliar se afeta build-time (menos urgente) ou runtime (urgente). `low` → corrigir na
próxima oportunidade.

**Dependência transitiva travada por um pacote pai**: se `pip-audit`/`npm audit` aponta uma
correção só disponível numa versão que o pacote direto não permite (ex.: `starlette` vem de
`fastapi`, que trava a faixa de versão permitida), fixar a dependência direta sozinha não
resolve — confira a faixa antes de reportar corrigido:

```bash
curl -s https://pypi.org/pypi/<pacote-pai>/<versão>/json | python3 -c \
  "import json,sys; print([r for r in json.load(sys.stdin)['info']['requires_dist'] if '<dependência>' in r.lower()])"
```

Se a faixa do pai não alcança a versão corrigida, o fix real é subir o pacote pai — auditar
as *release notes* antes, é mudança maior, não bump de patch.

### Etapa 3 — Processos suspeitos

```bash
ps aux | grep -E "node|python" | grep -v grep | grep -v "vscode\|cursor\|claude"
```

Sinal de alerta: processo `node`/`python3` sem terminal aberto associado.

### Etapa 4 — Pesquisa online (sempre antes de agir sobre um achado)

Pra cada pacote popular identificado como suspeito, buscar `[nome] supply chain attack
<ano>` e `[nome] compromised versions npm`. Fontes: socket.dev, snyk.io/advisor,
github.com/advisories — mas `npm audit`/`pip-audit` local é sempre mais confiável que
qualquer busca.

### Etapa 5 — Diagnóstico

- 🟢 audit = 0 HIGH/CRITICAL, sem processos suspeitos → Etapa 7 (prevenção)
- 🟡 sinais ambíguos → listar e pedir confirmação manual ao usuário
- 🔴 comprometimento confirmado → Etapa 6 (ordem crítica, não inverter)

---

## Etapa 6 — Recuperação 🔴 (somente se comprometido)

> Alguns malwares têm "interruptor de destruição" que apaga arquivos se credenciais forem
> revogadas antes do malware ser removido — a ordem abaixo importa.

1. **Desconectar internet** — aguardar confirmação do usuário.
2. **Backup offline**: `cp -r ~/dev/geop /caminho/backup/backup_$(date +%Y%m%d_%H%M)`.
3. **Remover malware**:
   ```bash
   rm -rf web/node_modules web/package-lock.json
   rm -rf admin/node_modules admin/package-lock.json
   rm -rf colaborador/node_modules colaborador/package-lock.json
   # editar package.json de cada um para versão segura
   npm install   # em cada diretório
   ```
4. **Só agora** religar internet e revogar credenciais: GitHub (Settings → Developer
   settings → Personal access tokens), npm (`npm token revoke <id>`), Brevo, GHCR, Asaas
   (se em uso), provedor ICP-Brasil/Clicksign.
5. **Auditoria de commits**: `git log --oneline --all -20` + `git branch -a` — procurar
   commit/branch que não deveria existir.
6. **2FA em tudo**: GitHub, registrador de domínio, provedores de pagamento/e-mail.

---

## Etapa 7 — Prevenção

### Tags Docker com versão de patch (recomendado, ainda não aplicado no GEOP)

Tags flutuantes ficam cacheadas em versões vulneráveis no Swarm — `docker pull` manual já
ocorreu, e `docker service update` sem `--image` explícito não força nova busca.

```yaml
# Atual em docker-stack.yml — flutuante
image: postgres:17-alpine
image: redis:7-alpine
image: minio/mc:latest

# Recomendado — atualização controlada e rastreável
image: postgres:17.6-alpine3.21
image: redis:7.4.2-alpine3.21
```

Ao atualizar: testar localmente → commitar `docker-stack.yml` com a versão nova → seguir o
procedimento de mudança crítica de `docs/seguranca.md` ("Mudança crítica": backup, plano de
rollback, registro em `docs/registro-trabalho.md`).

### Regra de cooldown de 7 dias

Antes de instalar qualquer pacote novo (Python ou Node): verificar em socket.dev se foi
publicado/atualizado de forma suspeita recentemente; se publicado há menos de 7 dias,
aguardar; preferir pacotes com histórico longo.

---

## Checklist rápido

```
[ ] npm audit em web/, admin/ e colaborador/ — 0 HIGH/CRITICAL
[ ] pip-audit em api/ (já roda no CI — conferir o último run em vez de rodar de novo, a
    menos que uma dependência tenha mudado desde então)
[ ] Processos suspeitos — nenhum
[ ] Secrets fora do git (nunca commitar .env.prod com valores reais)
[ ] Se for endereçar o gap de CI: adicionar job `npm audit` a `.github/workflows/ci.yml`
    para os três frontends (web/admin/colaborador), no mesmo padrão do job "API — pip-audit"
[ ] Se for endereçar tags flutuantes: pinar versão de patch de postgres/redis/minio-mc em
    docker-stack.yml, seguindo o processo de "Mudança crítica" de docs/seguranca.md
```
