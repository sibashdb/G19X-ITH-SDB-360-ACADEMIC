# SDD ledger — plan: docs/superpowers/plans/2026-09-29-incremento-1-esqueleto-y-proveedores.md

Spec: docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md
Worktree: .claude/worktrees/feat+incremento-1 · branch worktree-feat+incremento-1 · branch base 5ac7db5

## Pre-flight scan

### Task pairs sharing files or interfaces

| Tasks | Producer → consumer | Finding |
|---|---|---|
| 1 ↔ 7, 11 | T1 creates root pyproject (dev group, sources, coverage.source, mypy.packages); T7/T11 append proveedores/generador | Consistent |
| 2 ↔ 3 | `correlation_id`, `middleware_correlacion` → Problem Details body | Consistent |
| 3 ↔ 4 | `registrar_manejadores`, TITULOS 401 "No autenticado" / 403 "Sin permiso" → T4 test asserts "Sin permiso" | Consistent |
| 4 ↔ 7, 10 | `ClavesPrueba(EMISOR, AUDIENCIA, validador(), token())`, `ROLES_INTERNOS`, `requiere_rol` | Consistent |
| 5 ↔ 10 | `ConfiguracionBase.root_path`, `crear_router_salud` dict of async checks | Consistent |
| 6 ↔ 7, 9 | `ColumnasOutbox` mixin + `Outbox` model + `ix_outbox_pendientes` in migration; `registrar_evento(sesion, modelo, tipo, payload)` | Consistent |
| 7 ↔ 9, 10, 11 | models, `obtener_sesion`, fixtures `url_bd`/`fabrica`/`claves`; TRUNCATE list covers all 7 tables | Consistent |
| 8 ↔ 9 | `leer_csv`, `duplicados`, `agrupar_contratos`, `ErrorFila`, `FilaContrato.cabecera()` | Consistent |
| 9 ↔ 10 | `importar`, `Entidad`, `ResumenImportacion(entidad, filas, registros, omitidos, eventos)`, `ErrorImportacion` 422 | Consistent |
| 9 ↔ 11 | `ORDEN_CARGA` file names = `{entidad}.csv` = generator outputs | Consistent |
| 10 ↔ 13 | `root_path=/api/proveedores`; smoke test hits `/api/proveedores/proveedores`, `/openapi.json` | Consistent |
| 11 ↔ 12 | `../datos:/datos:ro` mount; `python -m proveedores.importacion.cli /datos` | Consistent |
| 12 ↔ 13 | T13 appends `gateway` service; smoke test reads dev passwords from realm JSON; client `pruebas-humo` | Consistent |
| 13 ↔ 14 | `@/auth`, `@/api`, `@/tipos` (T14 adds NOMBRES_TAMANO), Layout nav + rutas modified | Consistent |
| 15 ↔ all | CI runs the same commands tasks verified; gitleaks allowlists realm JSON and .env.example | Consistent |

### Per-task self-consistency

| Task | Finding |
|---|---|
| 1 | pytest `testpaths` lists `services`, `tools` before they exist → see Ruling R1 |
| 2 | 5 tests ↔ code consistent |
| 3 | 5 tests ↔ code consistent |
| 4 | 10 tests (3 parametrized) ↔ code consistent |
| 5 | 4 tests ↔ code consistent |
| 6 | 5 tests ↔ code consistent; needs Docker |
| 7 | migration hand-written to match models; drift test guards it |
| 8 | 13 tests ↔ code consistent |
| 9 | 9 tests ↔ code consistent; long lines fixed by `ruff format` before `ruff check` |
| 10 | 13 tests ↔ code consistent; conftest imports appended then moved to top |
| 11 | 5 + 1 tests ↔ code consistent |
| 12 | no automated tests; manual compose verification steps |
| 13 | shadcn CLI may prompt interactively → see Ruling R2; 3 vitest tests |
| 14 | 2 vitest tests (+3 from T13 = 5) |
| 15 | CI mirrors verified commands |

Plan-mandated items the rubric may flag: CSV fixture strings duplicated between `test_aplicar.py` and `test_api.py` → Ruling R3.

## Rulings

- Ruling R1: keep `testpaths = ["libs", "services", "tools"]` from Task 1; if pytest errors on missing dirs, T1 uses `["libs"]` and T7/T11 extend it — pytest ignores missing testpaths in practice — cost if wrong: one-line config edit.
- Ruling R2: T13 scaffold — if `npx shadcn@latest init -t vite …` prompts or hangs without a TTY, fall back to the documented manual path (npm create vite react-ts → tailwindcss + @tailwindcss/vite → `@` alias in tsconfig + vite.config → `npx shadcn@latest init -y`) — both paths produce the same files the plan relies on — cost if wrong: minor config differences caught by lint/build.
- Ruling R3: duplicated CSV fixture strings across test modules are test data, not logic; kept (importlib import mode prevents importing sibling test modules) — cost if wrong: small refactor to conftest fixtures later.
- Ruling R4: branch is the harness-managed `worktree-feat+incremento-1`, not `feat/incremento-1` — renaming is a PR-time cosmetic — cost if wrong: none functional.
- Ruling R5: every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (harness attribution rule) although plan commit commands omit it — cost if wrong: none.
- Ruling R6: uv (WinGet Links) and docker (Docker Desktop resources/bin) are not on this session's PATH; implementers prefix PATH in each shell command — cost if wrong: commands fail fast and visibly.

- Ruling R7: uv on this Windows host cannot create the managed-Python minor-version link ("Missing expected target directory for Python minor version link"); every uv command sets `UV_PYTHON=C:/Users/sebas/AppData/Roaming/uv/python/cpython-3.13.15-windows-x86_64-none/python.exe` (env only, never committed; CI/Docker on Linux unaffected) — cost if wrong: local-only env quirk, trivially reverted.
- Ruling R8: T1 added `libs/comun/src/comun/py.typed` (PEP 561, required by mypy strict on installed packages) and `[tool.ruff.format] exclude = ["*.md"]` (ruff formats Markdown code blocks) — accepted; T7 and T11 must also add `py.typed` to `proveedores` and `generador` — cost if wrong: none.

## Progress

Task 1: complete (commits 5ac7db5..59cb62a, review clean)
Task 1: minor (deferred): coverage fail_under only enforced when pytest runs with --cov (plan runs --cov in T6/T10/T11 and CI) — confirm in final review
Task 1: minor (deferred): testcontainers `postgres` extra pulls no driver; asyncpg comes from proveedores deps (T7)
Task 1: minor (deferred): testpaths lists dirs that do not exist until T7/T11 (pytest tolerates it)
Task 2: Ruling R5b: reviewer flagged d9c6237 trailer "Claude Haiku 4.5" vs R5 "Claude Opus 5.5" — amended R5: each commit's Co-Authored-By trailer names the model that actually wrote it (Haiku-authored commits say Haiku); accurate attribution beats uniformity; no history rewrite — cost if wrong: cosmetic trailer text.
Task 2: Ruling R9: StarletteDeprecationWarning "Using httpx with starlette.testclient is deprecated" appears in every TestClient run; Task 3 adds a message-targeted `filterwarnings` ignore in root pyproject so test output stays pristine (TestClient is a test-only dependency; revisit when Starlette drops httpx) — cost if wrong: one config line.
Task 2: complete (commits 59cb62a..d9c6237, 1 ruling, review otherwise clean)
Task 2: minor (deferred): test_configurar_logs restores handlers but not root logger level
Task 2: minor (deferred): `excepcion` branch of FormatoJSON and regex boundaries (64/65 chars, empty) untested
Task 2: minor (deferred): unhandled-exception 500 responses carry no X-Request-ID header (middleware never reaches header set)
Task 2: minor (deferred): uvicorn.error/uvicorn.access loggers keep non-JSON format — consider `--log-config`/`log_config=None` when the Dockerfile CMD is written (T12)
Task 3: review Approved with 1 Important (plan-mandated): English text leaks into error responses (HTTPStatus fallback titles, Starlette default details, Pydantic validation messages).
Task 3: Ruling R10: fix now — Spanish TITULOS incl. 409/410/500/502/504, fallback f"Error {code}" (also removes HTTPStatus ValueError crash on non-standard codes), Spanish default details for 404/405, and X-Request-ID header on 500s; defer Pydantic validation-message translation (developer-facing query/path errors; DRY option: move T8's MENSAJES map into comun and reuse) — spec "mensajes en español" binds user-facing text — cost if wrong: developers see English 422 details until final review.
Task 3: minor (deferred): filterwarnings entry could also name its category (DeprecationWarning)
Task 3: minor (deferred): commit ffef9a2 body bullets in English (subject Spanish)
Task 3: minor (deferred): Pydantic 422 validation "mensaje" text still English (see R10)
Task 3: fix round 1/5 (3 addressed, 0 open — Spanish titles/fallback, Spanish default details, X-Request-ID on 500; commits ffef9a2..5566601)
Task 3: complete (commits d9c6237..5566601, review clean after 1 fix round)
Task 4: review Needs fixes — 1 Important (plan-mandated): PyJWKClient(cache_keys=True) trusts rotated/revoked keys until restart.
Task 4: Ruling R11: fix now (spec security constraint outranks the plan text) — drop cache_keys=True; same round also guards `realm_access: null` (crafted-token 500) and adds regression tests for alg=none, missing exp, null realm_access — cost if wrong: one extra JWKS fetch per 300 s.
Task 4: minor (deferred): no clock-skew leeway in jwt.decode (suggest leeway=10)
Task 4: minor (deferred): JWKS outage → 503 without a log line; PyJWKClient default 30 s timeout inside threadpool (suggest timeout=5); non-JSON JWKS body → 500
Task 4: minor (deferred): pyjwt floor >=2.10 vs unknown-kid refresh cooldown verified only in 2.15.1 — consider raising floor
Task 4: fix round 1/5 (3 addressed, 0 open — drop cache_keys, null realm_access guard, JWT security regression tests; commits e08b1a0..841496a)
Task 4: minor (deferred): test_auth.py uses `__import__("json")` instead of top-level import
Task 4: complete (commits 5566601..841496a, review clean after 1 fix round)
Task 5: complete (commits 841496a..c4c281c, review clean)
Task 5: minor (deferred): salud.py logs probe exceptions with exc_info=True (possible DSN-with-credentials in driver errors; noisy every healthcheck) — consider logging type name only
Task 5: minor (deferred): database_url/rabbitmq_url plain str — repr/model_dump would print credentials; consider SecretStr
Task 5: minor (deferred): health probes run sequentially (2 s each) — asyncio.gather would bound latency
Task 5: minor (deferred): no tests for probe timeout branch or missing required settings; config test not isolated from ambient OIDC_* env vars
Task 6: implementer deviations accepted: asyncpg added to root dev group early (tests need it); testcontainers.community.* import paths.
Task 6: review Needs fixes — Important: (a) plan-mandated mandatory=False marks unroutable events published (lost from broker); (b) failure-path/exactly-once not tested.
Task 6: Ruling R12: keep mandatory=False in increment 1 — mandatory=True + on_return_raises would roll back whole batches whenever any event type has no bound queue (poison pill) and block all publishing until increment 2; the outbox table remains the durable event log — INCREMENT 2 PLAN MUST: declare durable consumer queues/bindings before relays publish, and add republish (reset publicado_en) or an alternate-exchange for unroutable events — cost if wrong: events emitted before consumers exist need replay (already planned).
Task 6: Ruling R13: fix round also takes two cheap robustness items — targeted filterwarnings for testcontainers "@wait_container_is_ready" deprecation, and publish timeout=10 — pristine test output and no indefinitely held row locks — cost if wrong: none.
Task 6: minor (deferred): ejecutar swallows "conectar() not called" RuntimeError forever; cerrar() leaves _exchange set; double conectar leaks a connection
Task 6: minor (deferred): no retention/purge of published outbox rows (partial index ix_outbox_pendientes comes in T7 migration)
Task 6: minor (deferred): ordering best-effort (ocurrido_en at flush; multiple relays) — document; envelope values (event_id==row id, UTC iso, version) not asserted
Task 6: minor (deferred): pydantic_core imported directly but not declared in libs/comun deps; testcontainers floor >=4.9 vs community.* paths
Task 6: fix round 1/5 IN PROGRESS — changes applied UNCOMMITTED in worktree (outbox.py timeout, 2 failure-path tests + exactly-once assertion, testcontainers warning filter; `pytest libs/comun` 37 passed, ruff/mypy clean). Implementer's `uv run pytest --cov` and a temporary mutation check were DENIED by the auto-mode classifier ("Security Test Removal"); commit not made. Controller did NOT run the denied commands (no permission laundering) — waiting for user decision.
Task 6: USER AUTHORIZED (2026-09-29) running `uv run pytest --cov` and committing; controller ran it (37 passed, 97.74 %, no warnings) and committed cece3e2 (trailers Sonnet 5.5 + Opus 5.5).
Task 6: fix round 1/5 (4 addressed, 0 open — failure-path + ejecutar-survival tests, exactly-once assertion, testcontainers warning filter, publish timeout=10; commits f4335f3..cece3e2)
Task 6: minor (deferred): publish timeout is per message — worst case ~lote x 10 s lock hold on a stalled broker
Task 6: complete (commits c4c281c..cece3e2, review clean after 1 fix round)
Task 7: complete (commits cece3e2..3540a5a, review clean; reviewer independently diffed model DDL vs migration SQL — no drift)
Task 7: minor (deferred, FIX BEFORE FIRST DEPLOY): UniqueConstraint(proveedor_id, periodo) auto-named uq_registro_desempeno_proveedor_id (reads as proveedor_id-only) — give explicit name while migration 0001 is unreleased
Task 7: minor (deferred): no range CHECKs (percentages 0-100, satisfaccion 1-5, plazo_pago_dias>=0, cuota>=0, usd_mxn>0, incidentes>=0; categorias array unconstrained) — import validates, DB doesn't
Task 7: minor (deferred): test_migracion_se_revierte_y_se_reaplica asserts nothing; drift test lacks compare_server_default=True; no test of CHECK/CASCADE/partial index
Task 7: minor (deferred): conftest sets process-wide os.environ["DATABASE_URL"]; TRUNCATE list hard-coded (derive from Base.metadata.sorted_tables)
Task 7: minor (deferred): ruff isort treats comun/proveedores as third-party → mixed grouping; consider [tool.ruff.lint.isort] known-first-party
Task 7: minor (deferred): no index on linea_contrato.servicio_id
Task 8: review Approved-conditional with 2 Important (plan-mandated): csv.Error escapes leer_csv (500 on unterminated quote/huge field); literal_error & some Pydantic types still English.
Task 8: Ruling R15: fix now — catch csv.Error → ErrorFila(0,"archivo",…); Spanish option lists, finite_number, date_from_datetime_inexact; plus cheap integrity items: duplicate header names rejected (silent data loss), whitespace-only optional cells = empty, RFC digits [0-9] — spec "never a 500 on a bad file" + Spanish messages — cost if wrong: small parser changes, covered by tests.
Task 8: minor (deferred): Excel exports with trailing empty columns/rows produce noisy errors (skip fully empty records, ignore empty trailing header names)
Task 8: minor (deferred): `activo` rejects Spanish Excel VERDADERO/FALSO; list-index field names like "categorias.1" leak into messages
Task 8: minor (deferred): row number = DictReader record ordinal (differs from physical line with embedded newlines); separator detected from first line only
Task 8: minor (deferred): tests don't pin quoted fields, CRLF, header whitespace, blank rows, FilaTipoCambio, activo=false
Task 8: fix round 1/5 APPLIED (commit 2a6e09a on top of 26eb3e3; implementer reports 20/20 parse tests, 59 total, no warnings) — SCOPED RE-REVIEW PENDING: next step = review package 26eb3e3..2a6e09a + re-review of the 5 R15 findings, then Task 9.
Task 8: minor (deferred): csv.DictReader non-strict — stray quote in a small file shows as per-row errors; empty header name shows "no reconocidas: " with blank
SESSION PAUSED (usage limit) after Task 8 fix round 1. Resume: re-review Task 8 fix (FIX_BASE 26eb3e3, HEAD 2a6e09a), then Tasks 9–15, then final whole-branch review.
SESSION RESUMED 2026-09-30.
Task 8: fix round 1/5 (5 addressed, 0 open — csv.Error caught, Spanish literal/finite/date messages, duplicate headers, whitespace-only cells, ASCII RFC digits; commits 26eb3e3..2a6e09a)
Task 8: minor (deferred): whitespace-only required text now "Campo obligatorio" instead of "No puede estar vacío" (accepted behaviour change)
Task 8: complete (commits 3540a5a..2a6e09a, review clean after 1 fix round)
Task 9: implementer deviations accepted: dict(result.all()) instead of deprecated Result.tuples(); insert/returning split for mypy.
Task 9: complete (commits 2a6e09a..9617f0e, review clean; reviewer verified at scale: 2,000 contracts/4,000 lines in 1.5 s, idempotent re-import 0.13 s)
Task 9: minor (deferred): tests don't assert persisted linea_contrato rows, full proveedor payload, event id == DB id, duplicados() wiring per entity, desempeno unknown-RFC, mixed re-import (all verified manually by reviewer)
Task 9: minor (deferred): existing contracts silently counted in `omitidos` even if CSV data differs (by design; UI shows omitidos)
Task 9: minor (deferred): identical re-imports re-emit proveedor.actualizado/desempeno.registrado and bump actualizado_en (IS DISTINCT FROM guard later)
Task 9: minor (deferred): desempeno.registrado payload omits rfc_proveedor (plan code); re-importing a service with a different moneda unguarded vs existing lines; _desempeno queries ids before parse-error check
Task 10: implemented fbbc492 (14 API tests incl. R16 409; 82 total; coverage 96.14 %) — task review pending (base 9617f0e).
Task 10: minor (deferred): coverage undercounts async SQLAlchemy code (greenlets); add `[tool.coverage.run] concurrency = ["greenlet", "thread"]` (implementer measured 97 % with it)
Task 10: minor (deferred): app lifespan (relay start/stop) not exercised by tests (by plan)
Task 10: review Approved with 2 Important: (1) plan-mandated multipart body fully spooled before auth / 10 MB checked after receipt; (2) request-validation 422s English (cross-task, comun/errores.py).
Task 10: Ruling R17: keep upload handling — Nginx gateway enforces client_max_body_size 10m (Task 13) and the service is internal-only in compose; final review to confirm the gateway config lands — cost if wrong: internal-network disk-spooling DoS vector.
Task 10: Ruling R18: fix now — move Pydantic Spanish translation (MENSAJES/_mensaje/_unir/_opciones) from parseo.py into comun/mensajes.py (traducir_error), used by comun/errores.py and parseo.py (DRY), add uuid/int/bool types; plus desplazamiento le=1_000_000 (was 500 on huge values) and warning log in the R16 409 branch — supersedes R10's deferral — cost if wrong: small refactor covered by existing parse tests.
Task 10: fix round 1/5 (3 addressed, 0 open — comun/mensajes.py shared Spanish translation (+enum), desplazamiento le=1_000_000, 409 warning log; commits fbbc492..f711bfa; 89 tests, 96.59 %)
Task 10: minor (deferred): 409 warning log exc_info includes SQLAlchemy [SQL]/[parameters] (imported row values in server logs) — set create_async_engine(hide_parameters=True) or log type name only
Task 10: minor (deferred): body-validation types outside MENSAJES (e.g. json_invalid) still English — no JSON-body routes yet
Task 10: complete (commits 9617f0e..f711bfa, review clean after 1 fix round)
Task 11: implemented 865d442 (95 tests, 94.65 %; generator: 60 suppliers, 1,912 contracts, 4,272 lines, 3,570 perf rows; imports with 0 errors). Implementer added `# noqa: S311` on random.Random(seed) (accepted: non-crypto RNG).
Task 11: review Approved with 2 Important (plan-mandated): KPIs nearly noise-free (Spearman 0.98–0.995) and no short-history suppliers; bulk-load CLI message claims "no se importó ninguna fila" after earlier files committed.
Task 11: Ruling R19: fix now (before any derived datasets exist) — per-supplier observation bias + per-KPI persistent offsets + ~15 % recent suppliers (1–12 months), KPI/price Spearman tests calibrated; CLI names failing file and already-imported entities; plus "Kubernetes" → generic name (constraint: sin marcas reales), verdad_oculta.json LF newlines, --anios/--proveedores ≥ 1 — spec 4.2 "señales imperfectas", 4.4 contraction — cost if wrong: dataset regenerates in seconds.
Task 11: minor (deferred): renewal label random (not tied to prior contracts / tope_aumento); tamano no price effect; inactive suppliers keep monthly performance rows; ~4,300 lines vs spec "~6,000"
Task 11: minor (deferred): reloading the folder re-emits proveedor/desempeno events (T12 runs the loader once, manually)
Task 11: fix round 1/5 (5 addressed, 0 open — imperfect KPI signals (seed 11 rho 0.79–0.87, composite 0.89–0.93), recent suppliers, ErrorCarga naming file + imported entities, no brand names, LF json, positive CLI ints; commits 865d442..809e14b; 110 tests, 96.60 %; data now 60 suppliers / 1,601 contracts / 3,553 lines / 2,980 perf rows)
Task 11: minor (deferred): CLI first line "…no se importó ninguna fila. Ya se importaron: …" slightly contradictory wording; volume seed-sensitive (one seed in 1–200 gives 1,471 folios); --anios no upper bound (absurd values traceback); supplier suffix "Azteca" resembles real brands
Task 11: complete (commits f711bfa..809e14b, review clean after 1 fix round)
Task 12: Ruling R20: add `.superpowers` to .dockerignore (controller scratch must not be copied into images by `COPY . /app`) — cost if wrong: none.
Task 12: complete (commits 809e14b..e1a7989, review clean; verified live: 4 services healthy, 1,601 contracts loaded, outbox 4,641/0 pending, DB isolation, issuer/PKCE/audience/OTP required actions in realm; stack left RUNNING)
Task 12: Ruling R21: fold three one-line infra hardenings into Task 13 (same files): `hostname: rabbitmq` (mnesia dir follows container id → state orphaned on recreate; matters for durable queues in increment 2), `pg_isready -U postgres -h 127.0.0.1` (init-phase socket-only false ready), .dockerignore `**/.env`, `**/.env.local`, `.coverage`, `htmlcov` — cost if wrong: none.
Task 12: minor (deferred): OTP enforced per seeded user (requiredActions), not per role — production realm must use conditional OTP by role (document in manual técnico); failureFactor default 30 lax
Task 12: minor (deferred): `COPY . /app` puts infra/ (dev realm creds), docs/, tests/ into the image and busts cache; floating `uv:latest`/`python:3.13-slim` tags
Task 12: minor (deferred): ops notes for manual — realm import IGNORE_EXISTING (edit needs down -v), .env passwords only apply at first init, init.sh interpolates passwords unquoted, no restart policies
Task 12: note: Git Bash needs MSYS_NO_PATHCONV=1 for `docker compose exec … /datos` paths
Task 13: implemented f915c89 (shadcn CLI with extra `-p nova -y`; import.meta.dirname in vite.config; removed CLI-created nested web/.git) — deviations accepted. Smoke test OK (60 suppliers); manual login comprador1 OK. R21 applied (rabbit@rabbitmq, pg_isready TCP, .dockerignore).
Task 13: review Approved with 2 Important (plan-mandated): (1) Layout dead-ends on auth.error (silent-renew failure after idle/sleep) with raw English text and no re-login; (2) gateway-generated 413/429/502-504 are English HTML → pedir falls back to English statusText; unmatched /api/* returns index.html (SyntaxError in pedir).
Task 13: Ruling R22: address both in Task 14 (it already modifies Layout.tsx and the web layer; avoids a separate fix cycle): Spanish error + "Volver a iniciar sesión" button (removeUser + signinRedirect) with a test; nginx error_page 413/429/502/503/504 → Spanish application/problem+json and `location /api/` → JSON 404; pedir Spanish fallback for non-JSON/null bodies with tests — Task 14's review must verify them — cost if wrong: if Task 14 slips, the gaps surface in final review.
Task 13: complete (commits e1a7989..f915c89, review Approved; Important items carried by R22 into Task 14)
Task 14: implemented 958a61c (pages byte-identical to plan + R22 items 1–3; Vitest 15/15; gateway 413/404/429/502 Spanish JSON verified; smoke OK). Implementer stopped/started proveedores to test 502 — controller re-checked salud/vivo 200 via gateway.
Task 14: review Approved with 1 Important (plan-mandated): ProveedorDetalle contratos/desempeno sub-tables have no loading/error/empty state.
Task 14: Ruling R23: fix now — loading/error(role=alert)/empty rows + Vitest test; plus `location = /api` JSON 404, formal "Su sesión…", invalidate ["proveedor"] on import — cost if wrong: none.
Task 14: minor (deferred): server-level error_page also applies to /auth/ (Keycloak 5xx shows JSON on browser navigation); gateway JSON errors lack X-Request-ID and Retry-After; pedir casts Problem Details fields unvalidated; network "Failed to fetch" English; 422 on non-UUID id shows generic message; id not encodeURIComponent; tables: no initial loading indicator/aria-live, blank continuation cells, periodo shows day, quantity 3 fraction digits; test gaps (non-admin Importacion, nav hiding, multipart field name, Proveedores/ProveedorDetalle pages, status 500 path)
Task 14: fix round 1/5 (4 addressed, 0 open — sub-table loading/error/empty states + tests, `location = /api` JSON 404, formal register, invalidate ["proveedor"]; commits 958a61c..74dd49a; Vitest 20/20)
Task 14: complete (commits f915c89..74dd49a, review clean after 1 fix round; R22 items verified)
Task 15: implemented d34fd19 (workflow/dependabot/PR template/gitleaks/README verbatim + Windows notes; local Step 4 green: 110 py tests 96.6 %, 20 web tests, stack+smoke OK; gitleaks and GitHub runner never executed — no remote).
Task 15: review Approved with 1 Important (plan-mandated): secretos job lacks pull-requests:read (fails on private-repo PRs) and GITLEAKS_LICENSE for org repos.
Task 15: Ruling R24: fix now with cheap same-file hardening — job permissions + license env; anchored gitleaks allowlist regexes; dependabot conventional-commit prefixes, docker-compose ecosystem /infra, ignore python minor/major; CI timeouts + concurrency; README `npm test -- --run`, `npm ci` note, `UV_PYTHON=3.13` — cost if wrong: config lines only.
Task 15: minor (deferred): spec 6.1/6.2 per-PR pip-audit/npm audit/path filters/contract diff (oasdiff)/Trivy not in increment-1 CI (Trivy/ZAP/E2E deferred by plan; audits & path filters & contracts not listed in deferral table — carry to increment 2 plan)
Task 15: fix round 1/5 (5 addressed, 0 open — secretos permissions + license env, anchored allowlist, dependabot prefixes/compose/python ignore, CI timeouts + concurrency, README; commits d34fd19..8dfc3d3)
Task 15: complete (commits 74dd49a..8dfc3d3, review clean after 1 fix round)
ALL 15 TASKS COMPLETE. Next: final whole-branch review 5ac7db5..8dfc3d3 (most capable model), then finishing-a-development-branch.
FINAL REVIEW (opus, 2026-10-01): Ready to merge "With fixes"; 0 Critical; Important: (1) running service logs are uvicorn plain text, not JSON with correlation_id (Global Constraint); (2) OTP per seeded user, not per role; (3) plan/spec gap: tipo_cambio & servicio catalog emit no events (inteligencia/negociacion lack a sanctioned data path). 110 py tests 96.6 %, 20 web tests, smoke OK.
Ruling R25: ONE final fix wave — JSON logs for uvicorn loggers (+ test) and an audit log line per successful import (entity, counts, usuario.id); importer hardening (incidentes_criticos upper bound, NUL bytes → file-level error); migration 0002 renaming uq_registro_desempeno_proveedor_id → uq_registro_desempeno_proveedor_id_periodo (+ naming convention column_0_N_name); pagination tiebreakers (Proveedor.id; Contrato folio); contratos_vigentes date in America/Mexico_City (+ tzdata dep); encodeURIComponent(id) in ProveedorDetalle; PyJWKClient timeout=5 + jwt leeway=10; create_async_engine(hide_parameters=True); remove scaffold leftovers (theme-provider.tsx, web/README.md); README "Limitaciones conocidas" (OTP per role, R12 unroutable events + replay obligation, dev-only realm incl. pruebas-humo) — final reviewer's merge blocker + cheap hardening — cost if wrong: small, all covered by tests.
Ruling R26: OTP-by-role (conditional browser flow) deferred — implementing requires realm re-import via `down -v`, which also wipes proveedores_db (shared pgdata); MUST be done before any non-local deployment and before increment 4 (approvals); documented in README limitations — cost if wrong: admins/aprobadores created later or who remove their authenticator log in with password only (local dev only today).
Ruling R27: events for tipo_cambio and servicio catalog (or sanctioned HTTP reads) + backfill go to the top of the increment-2 plan together with R12 obligations (durable queues before publishing, replay tool), T9 "omitidos with different data" warning, T11 volume vs spec 4.2, T15 per-PR audits/contract diff/path filters, T12 COPY . /app + pinned tags before publishing images — cost if wrong: increment-2 planning item.
Final-review minors left deferred (as triaged): generator volume, multipart English 400 + instance path, Excel dd/mm and empty-row round-trips, spec 2.3 layout deviation (record in ADR/increment 0), test hygiene items, range CHECKs, isort, servicio_id index, CLI wording, UI/gateway polish (deep links, rate-limit key, upstream re-resolution, gzip, "Failed to fetch").
Closed by final review: T1 fail_under (CI runs --cov), T1 testpaths (dirs exist), T2 500-without-X-Request-ID (R10), T3 English Pydantic messages (R18).
FINAL FIX WAVE: commits 8dfc3d3..b045d1d (7 commits) — scoped re-review: all 10 R25 items ADDRESSED, no new Critical/Important. Verified: 120 py tests 96.48 %, 21 web tests, stack rebuilt healthy, alembic 0002, smoke OK, proveedores logs JSON with correlation_id, constraint renamed.
Final minor (deferred): engine test reads private pool._pre_ping; cli.py engine flags untested.
Ruling R28: parked — `GET /proveedores?q=` containing a NUL byte may reach PostgreSQL via ILIKE and return 500 (same class as R25 item 2, outside the fix diff; read-only route, no data impact); fix in increment 2 by rejecting "\x00" in query params — cost if wrong: a crafted query gets a generic 500 Problem Details.
Ruling R29: preserve this ledger as docs/qa/bitacora-revision-incremento-1.md before deleting the scratch workspace — it is evidence for the "Reporte QA" deliverable (spec 6.5 #6) — cost if wrong: one doc file to delete.
INCREMENT 1 COMPLETE — branch worktree-feat+incremento-1 at b045d1d (+ ledger commit). Next: finishing-a-development-branch.
Task 13: minor (deferred): deep links lost after login (redirect_uri "/" + no state restore); X-Forwarded-For spoofable ($proxy_add_x_forwarded_for at edge); gateway log_format lacks request id; rate limit keyed on Docker bridge IP; nginx resolves upstreams once (restart gateway after recreating services); smoke test doesn't check X-Request-ID echo / other headers / 413 / 429; no gzip/cache headers; pedir/ErrorApi untested (Task 14 adds tests); scaffold leftovers (theme-provider.tsx, README, svgs, .prettierrc width 80)
Task 10: minor (deferred): IntegrityError catch not narrowed to SQLSTATE 23505; non-deterministic orderings (no id/folio tiebreakers, Contrato.lineas unordered); date.today() process TZ; engine never disposed / lifespan yield not in try-finally; /docs & /openapi.json unauthenticated (FastAPI default); test gaps (desempeno 404, bounds, 10 MB boundary, backslash in q)
Task 9: Ruling R16: concurrent import of the same new folio raises IntegrityError at commit → HTTP 500; Task 10 maps sqlalchemy IntegrityError in the import route to ErrorDominio(409, "Conflicto", Spanish retry message) with a test — spec "never a 500 on a bad file/import" — cost if wrong: one except clause.
