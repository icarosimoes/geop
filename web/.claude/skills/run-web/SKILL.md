---
name: run-web
description: Run, launch, drive, and screenshot the Registro web frontend (Next.js tenant app) against the Docker dev stack. Use when asked to run web, test a web page/flow end-to-end, take a screenshot of a page, or verify a frontend change actually renders and works in the browser.
---

Paths below are relative to `web/` (this app's root), except the driver
itself which lives at `web/.claude/skills/run-web/driver.mjs`.

The web app (`web/`) is a Next.js 16 App Router frontend for the tenant
side of Registro. It's normally served by the `registro-web-1` Docker
container as part of the full stack (API + Postgres + Redis + MinIO),
not run standalone — Server Actions call the FastAPI backend directly,
so a bare `npm run dev` without the rest of the stack won't have
anything real to talk to.

`chromium-cli` is **not installed** in this environment. This skill
ships a small drop-in replacement: `driver.mjs`, a stdin command
REPL built on Playwright that speaks the same verbs (`nav`,
`wait-for`, `fill`, `click`, `screenshot`, `console-errors`). Use it
exactly like the `chromium-cli` heredoc pattern.

## Prerequisites (one-time, this container)

Playwright's bundled Chromium needs `libasound.so.2`, which isn't
present here and `apt-get install` requires a root password this
environment doesn't have. Downloading and extracting the `.deb`
directly (no root needed) works:

```bash
cd web/.claude/skills/run-web
mkdir -p localdeps && cd localdeps
apt-get download libasound2t64
dpkg-deb -x libasound2t64_*.deb extracted
```

Install Playwright itself (already a devDependency isn't required —
this uses a standalone `node_modules` next to the driver):

```bash
cd web/.claude/skills/run-web
npm install playwright@1.61.1
npx playwright install chromium   # downloads the browser binary only;
                                   # install-deps will fail (needs root) — ignore it
```

Every driver invocation needs the extracted lib on `LD_LIBRARY_PATH`:

```bash
export LD_LIBRARY_PATH="$PWD/web/.claude/skills/run-web/localdeps/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
```

## Bring up the stack

```bash
docker compose up -d
timeout 60 bash -c 'until curl -sf http://localhost:3000 >/dev/null; do sleep 1; done'
```

The API runs migrations and seeds a demo tenant automatically on
startup. Seed login (dev only):

- email: `icaro@registro.local`
- password: `Registro@123`
- company slug: `empresa-demo`, wildcard (`*`) permissions

## Run (agent path — the driver)

```bash
cd web/.claude/skills/run-web
export LD_LIBRARY_PATH="$PWD/localdeps/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
node driver.mjs <<'EOF'
nav /login
fill input[name="email"] icaro@registro.local
fill input[name="password"] Registro@123
click button[type="submit"]
wait-for text=Dashboard
screenshot dashboard
console-errors
EOF
```

Screenshots land in `web/.claude/skills/run-web/screenshots/<name>.png`
(full-page). `console-errors` prints every `console.error`/`pageerror`
seen so far in the session — check it before declaring success; a page
can render its shell while every data fetch 500s.

Full command reference is in the comment header of `driver.mjs`:
`nav`, `wait-for` (`text=...` or CSS selector), `fill`, `select` (native `<select>`, use
Playwright's `selectOption` under the hood — `eval el.value = ...`/`selectedIndex` does **not**
fire React's onChange on a controlled `<select>`, same gotcha as text inputs), `set-files`
(for `<input type="file">`), `click`, `press`, `screenshot`, `eval`,
`console-errors`, `sleep` (last resort).

### Worked example: batch payslip import flow

This is the exact script used to verify the `/ponto/contracheques`
batch-import feature end-to-end against the live stack:

```bash
node driver.mjs <<'EOF'
nav /login
fill input[name="email"] icaro@registro.local
fill input[name="password"] Registro@123
click button[type="submit"]
wait-for text=Dashboard
nav /ponto/contracheques
wait-for text=Suba um
screenshot contracheques-empty
set-files input[type="file"][accept*="csv"] ./manifest.csv
set-files input[type="file"][accept*="zip"] ./payslips.zip
click button:has-text("Importar contracheques")
wait-for table
screenshot contracheques-result
console-errors
EOF
```

`manifest.csv` and a `payslips.zip` need to exist next to where you
run this (paths are relative to cwd, not `BASE_URL`). Minimal example:

```bash
printf 'cpf,matricula,competencia,arquivo\n58215069800,,2026-06,teste.pdf\n' > manifest.csv
python3 -c "
import zipfile
with zipfile.ZipFile('payslips.zip', 'w') as z:
    z.writestr('teste.pdf', b'%PDF-1.4 fake payslip content for testing')
"
```

The CPF must match a real, non-deleted employee in the tenant you
logged into — check/create one first, e.g.:

```bash
docker exec registro-postgres-1 psql -U registro -d registro -c \
  "select id, name, cpf from employees where deleted_at is null order by id desc limit 5;"
```

## Run (human path)

```bash
docker compose up -d
# open http://localhost:3000 in a real browser, log in with the seed credentials above
```

Useless in this headless container — only for reference.

## Gotchas

- **`authedFetch` vs raw `fetch` for file uploads.** Server Actions
  that upload `FormData` (e.g. `importPayslipsAction`,
  `importEmployeesAction`) must use a raw `fetch`, not the project's
  `authedFetch` helper — `authedFetch` forces
  `Content-Type: application/json`, which breaks multipart uploads.
  Not a driver issue, but the first thing to check if a file-upload
  flow silently 400s.
- **`page.fill` / `page.setInputFiles`, not `eval el.value = ...`.**
  React controlled inputs (and file inputs) need Playwright's real
  input pipeline to fire `onChange`; direct DOM mutation is invisible
  to React state.
- **One stray `console-errors` entry is expected and harmless:**
  `Refused to execute script from '.../login' because its MIME type
  ('text/html') is not executable...` shows up once per session on
  the first navigation after login redirect. It's not related to any
  app code touched so far — don't chase it, but do check for *other*
  errors alongside it.
- **`chromium-1228` (full) vs `chromium_headless_shell-1228`** — both
  live under `~/.cache/ms-playwright/` after `playwright install
  chromium`; both need the same `libasound.so.2` fix. Playwright's
  default `chromium.launch()` picks the right one automatically.
- **`npx playwright install-deps` will fail here** (tries `sudo`,
  no password available) — expected, ignore it. The one missing lib
  (`libasound.so.2`) is the only blocker; everything else Playwright
  needs is already present in this container.

## Troubleshooting

- `error while loading shared libraries: libasound.so.2: cannot open
  shared object file` → `LD_LIBRARY_PATH` isn't set, or the deb wasn't
  extracted yet. See Prerequisites.
- `browserType.launch: Target page, context or browser has been
  closed` with an `[err]` line mentioning a missing `.so` → same fix,
  read the actual missing library name from the log (it may not
  always be `libasound.so.2` on a different base image) and
  `apt-get download <package> && dpkg-deb -x`.
- Login redirect never resolves / `wait-for text=Dashboard` times out
  → check `docker logs registro-api-1 --tail 30`; the API runs
  migrations/seed on startup and needs a few seconds after
  `docker compose up -d` before login works.
