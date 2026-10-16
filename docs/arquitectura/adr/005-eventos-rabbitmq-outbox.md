# ADR-005: Eventos con RabbitMQ, outbox transaccional y consumidores idempotentes

- **Estado:** Aceptada (con un cambio de librería)
- **Fecha:** 2026-09-28

## Contexto

Los servicios no comparten bases de datos (ADR-006). Necesitan propagar cambios sin perder
eventos aunque RabbitMQ esté caído un momento.

## Decisión

- Exchange *topic* `eventos`, con colas *quorum* y cola de fallidos tras 5 entregas.
- Patrón *outbox*: el evento se guarda en la misma transacción que el cambio y un proceso lo publica.
- Los consumidores registran el `event_id` para ignorar duplicados.
- La topología vive en `libs/comun/src/comun/topologia.py`, y una prueba la compara con
  `infra/rabbitmq/definitions.json`.

## Consecuencias

- Entrega al menos una vez y consistencia eventual: las copias locales se ponen al día en
  segundos.
- **Cambio frente al PRD:** el PRD decía FastStream. Al construir el servicio de inteligencia se
  decidió no agregarlo, porque `libs/comun` ya tenía un consumidor y un relay propios sobre
  aio-pika (spec 2026-10-10, D5). Por eso la AsyncAPI se escribe a mano
  ([`../asyncapi.yaml`](../asyncapi.yaml)) y no se genera.
