# ADR-003: LLM local con Ollama detrás de una API compatible con OpenAI

- **Estado:** Propuesta (se implementa en N2)
- **Fecha:** 2026-09-28

## Contexto

El brief proponía Azure OpenAI, pero el presupuesto de infraestructura es cero (decisión D6 del
PRD).

## Decisión

El servicio `ia` será el único que hable con el LLM, a través de una API compatible con OpenAI
servida por Ollama en local. Cambiar a Azure OpenAI u otro proveedor será cambiar la URL y el modelo
por configuración.

## Consecuencias

- Sin costo y sin datos fuera del equipo.
- Hay un límite de concurrencia (la GPU atiende 1–2 peticiones), por eso `ia` es un solo servicio
  con su cola.
- No existe todavía: con la replanificación (ADR-010), N2 queda para después de la adjudicación.
