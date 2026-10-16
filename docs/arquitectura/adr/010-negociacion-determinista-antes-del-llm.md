# ADR-010: Negociación determinista antes del LLM, y adjudicación antes que la IA

- **Estado:** Aceptada
- **Fecha:** 2026-10-13 (ampliada el 2026-10-15)

## Contexto

El incremento 3 del PRD juntaba el motor, las sesiones, el portal, el servicio `ia`, los evals y
los bots. El 13/10/2026 se partió en N1 (determinista) y N2 (IA). El 15/10/2026, la
retroalimentación del asesor señaló que la negociación aún no existía y que el plan de 16–18
semanas no cabía en el tiempo restante.

## Decisión

1. **N1 primero.** Construir la negociación completa sin LLM: motor, sesiones, portal con
   formulario estructurado, supervisión, bots y bitácora. Los mensajes del agente son plantillas.
2. **Opción A del residente.** Lo siguiente es la adjudicación con aprobación (capacidades 7 y 9,
   Must), del 21/10 al 11/11. N2 (el LLM), las propuestas y el simulador van después, solo si
   sobra tiempo.

## Consecuencias

- La capacidad 5 se cumple como Must con el agente determinista; el LLM pasa a Should
  (PRD §6.6.1).
- El flujo de punta a punta (evento → negociación → recomendación → aprobación) queda antes que
  la IA.
- Si no alcanza el tiempo, el título del proyecto («negociación con agente IA») quedará con un
  agente determinista. Es un riesgo aceptado.
