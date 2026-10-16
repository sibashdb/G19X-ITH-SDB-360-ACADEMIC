# ADR-008: Precio justo con regresión por cuantiles y regla de promoción

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

El «precio justo» es la base de las alertas de sobreprecio y de los límites que se sugieren al
negociar. Una estadística simple puede bastar, y un modelo solo vale si la mejora.

## Decisión

Hay dos métodos:
- **Línea base:** percentiles P25, P50 y P75 de los contratos comparables.
- **Modelo:** *gradient boosting* por cuantiles con scikit-learn.

Se entrena periódicamente con validación temporal (los últimos 6 meses) y el modelo se promueve
solo si su MAPE mejora el de la línea base. Las versiones quedan en `modelo_benchmark` y los
artefactos en el volumen `modelos`.

## Consecuencias

- Hoy el modelo está en uso: MAPE de 8.3 % contra 9.3 % de la línea base (meta ≤ 15 %).
- Si un reentrenamiento empeora, se sigue usando lo anterior.
- Azure ML no se justifica con este volumen de datos.
