# ADR-007: Estrategia de concesiones dependiente del tiempo con utilidad multiatributo

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

El agente debe negociar varios términos a la vez (precio por línea y palancas como el plazo de
pago o el SLA), nunca cruzar un límite y ser explicable y medible.

## Decisión

El motor (`services/negociacion/src/negociacion/dominio/motor.py`) sigue a Faratin:
- **Utilidad:** cada oferta tiene una utilidad de 0 a 1. Vale 1 en el ideal del comprador y 0 en
  el límite, ponderada por el peso de cada término.
- **Objetivo por ronda:** `U(t) = 1 − (t/T)^(1/β)`, con β = 0.3 (firme), 0.6 (balanceado) o 1.0
  (flexible).
- **Aceptación:** acepta si la oferta respeta todos los límites y vale al menos lo que pediría en
  esa ronda.
- **Contraoferta:** si no acepta, contraoferta en la frontera de esa utilidad.

## Consecuencias

- Es determinista: las propiedades se prueban con Hypothesis (nunca fuera de límites,
  concesiones monótonas y aceptación coherente).
- Cada respuesta deja su traza («¿Por qué respondió esto?»).
- Contra los bots dio 81.1 % de acuerdos y 16.5 % de ahorro.
