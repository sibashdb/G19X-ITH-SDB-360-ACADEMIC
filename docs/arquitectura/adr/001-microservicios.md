# ADR-001: Microservicios en lugar de monolito modular

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

El residente quería practicar una arquitectura de producción, y el dominio se parte bien en
proveedores, inteligencia, negociación y administración. Un monolito modular habría sido más
barato de construir.

## Decisión

Cada capacidad es un servicio FastAPI con su propia base de datos, desplegado con Docker
Compose. Los servicios se comunican por eventos (ADR-005) y, solo cuando necesitan la respuesta
en el momento, por HTTP.

## Consecuencias

- Más infraestructura, pruebas de contrato y consistencia eventual.
- Mitigaciones:
  - `libs/comun` concentra la infraestructura repetida (JWT, errores, outbox, consumidor y topología);
  - hubo un esqueleto funcional temprano;
  - hay una sola instancia de PostgreSQL (ADR-006).
- El costo se notó en el calendario: la retroalimentación del asesor del 15/10/2026 pidió recortar
  el alcance para que la negociación entrara en el MVP (ADR-010).
