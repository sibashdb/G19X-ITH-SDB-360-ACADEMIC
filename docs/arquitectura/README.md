# Documento de arquitectura

Entregable 3 del cronograma (PRD §6.5). Describe la plataforma tal como está construida al
20/10/2026, después de N1 y de la adjudicación con sus servicios y su interfaz. Lo planeado
aparece marcado como tal. Los requerimientos y el diseño original están en el
[PRD](../superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md).

| Documento | Contenido |
|---|---|
| [`c4.md`](c4.md) | Diagramas C4 de contexto, contenedores y componentes (`negociacion` e `inteligencia`) |
| [`modelo-de-datos.md`](modelo-de-datos.md) | Un diagrama entidad-relación por servicio, generado de los modelos |
| [`eventos.md`](eventos.md) | Eventos entre servicios, colas, garantías de entrega y llamadas HTTP síncronas |
| [`asyncapi.yaml`](asyncapi.yaml) | Contrato de los eventos en AsyncAPI 3.0 |
| [`openapi/`](openapi/) | Contrato OpenAPI de cada servicio (`proveedores`, `administracion`, `inteligencia` y `negociacion`) |
| [`adr/`](adr/) | Registros de decisiones de arquitectura |

## Decisiones de arquitectura

| ADR | Decisión | Estado |
|---|---|---|
| [001](adr/001-microservicios.md) | Microservicios en lugar de monolito modular | Aceptada |
| [002](adr/002-el-llm-habla-el-motor-decide.md) | «El LLM habla, el motor decide» | Aceptada |
| [003](adr/003-llm-local-con-ollama.md) | LLM local con Ollama detrás de una API compatible con OpenAI | Propuesta (N2) |
| [004](adr/004-keycloak-oidc.md) | Keycloak (OIDC), migrable a Entra ID | Aceptada |
| [005](adr/005-eventos-rabbitmq-outbox.md) | RabbitMQ con outbox transaccional y consumidores idempotentes | Aceptada (aio-pika en lugar de FastStream) |
| [006](adr/006-postgresql-una-base-por-servicio.md) | Una instancia de PostgreSQL con una base y un usuario por servicio | Aceptada |
| [007](adr/007-concesiones-dependientes-del-tiempo.md) | Concesiones dependientes del tiempo con utilidad multiatributo | Aceptada |
| [008](adr/008-benchmark-por-cuantiles.md) | Precio justo con regresión por cuantiles y regla de promoción | Aceptada |
| [009](adr/009-eleccion-del-llm-por-evals.md) | Elección del LLM local según los evals | Propuesta (N2) |
| [010](adr/010-negociacion-determinista-antes-del-llm.md) | Negociación determinista antes del LLM, y adjudicación antes que la IA | Aceptada |
| [011](adr/011-quien-aprueba-una-adjudicacion.md) | Quién aprueba una adjudicación: el aprobador sobre el umbral o fuera de límites, si no el comprador; nunca quien propone | Aceptada |

## Mantenerlo al día

- **Contratos OpenAPI:** con el stack levantado, `uv run python infra/exportar_contratos.py` los
  vuelve a escribir. Las rutas son relativas a cada servicio; detrás del gateway llevan el prefijo
  `/api/<servicio>`.
- **Eventos:** un tipo nuevo se declara primero en `libs/comun/src/comun/topologia.py` y después
  en `eventos.md` y `asyncapi.yaml`.
- **Modelo de datos:** cada migración de Alembic que cambie tablas debe reflejarse en
  `modelo-de-datos.md`.
- **Decisiones nuevas:** van como ADR con el número siguiente. Una decisión que cambia otra la
  marca como «Reemplazada por ADR-NNN».
