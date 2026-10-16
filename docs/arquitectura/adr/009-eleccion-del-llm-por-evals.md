# ADR-009: Elección del modelo LLM local según los evals

- **Estado:** Propuesta (se decide en N2)
- **Fecha:** 2026-09-28

## Contexto

Varios modelos de 3–4B parámetros caben en la GPU de desarrollo (por ejemplo, Qwen3 4B o
Gemma 3 4B). Cuál conviene depende de qué tan bien interpreten las ofertas.

## Decisión

Se elegirá con un conjunto etiquetado de mensajes de proveedor (PRD §4.8). La meta es ≥ 90 % de
campos interpretados correctamente, cero filtraciones del límite ante la suite de ataques y una
respuesta en menos de 20 s en el percentil 95.

## Consecuencias

- Pendiente: depende de N2, que quedó después de la adjudicación (ADR-010).
