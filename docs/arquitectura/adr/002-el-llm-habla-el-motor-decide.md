# ADR-002: «El LLM habla, el motor decide»

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

Los modelos que caben en la GPU de desarrollo (4 GB de VRAM, 3–4B parámetros) sirven para
interpretar y redactar texto, pero no son fiables para decidir montos. Además, el proveedor puede
intentar manipular al agente (*prompt injection*).

## Decisión

Toda decisión con dinero la toma código determinista y probado: ofertas, contraofertas,
concesiones, aceptación y adjudicación. El LLM solo convierte el mensaje del proveedor en una
oferta estructurada y redacta mensajes y explicaciones.

## Consecuencias

- El sistema es medible: el simulador de bots comprueba que no haya acuerdos fuera de límites
  (0 en 74 sesiones).
- Desde N1 se cumple de la forma más estricta: todavía no hay LLM, y el agente usa plantillas.
- Cuando llegue N2, el LLM nunca podrá cambiar un monto ni ver el límite.
