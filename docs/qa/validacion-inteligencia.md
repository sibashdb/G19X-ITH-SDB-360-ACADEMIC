# Validación del servicio de inteligencia

Generado el 16/10/2026 con `uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json`.

Datos del generador: semilla 42, 60 proveedores, 3,553 líneas de contrato y desempeño hasta 09/2026. La verdad oculta (calidad de cada proveedor) solo se usa aquí, para medir; la plataforma nunca la ve.

## Precio justo

Validación temporal: se entrena con los contratos hasta 6 meses antes del último y se mide con los posteriores.

| Método | MAPE del P50 | Cobertura [P25, P75] |
|---|---|---|
| Línea base | 9.3 % | 43.5 % |
| Modelo (gradient boosting por cuantiles) | 8.3 % | 46.4 % |

Meta: MAPE del P50 ≤ 15.0 % y cobertura entre 40.0 % y 60.0 %. En uso: el modelo, porque mejora la línea base. Cumple: sí.

## Puntuación de proveedores

| Medida | Valor | Meta |
|---|---|---|
| Spearman entre la puntuación y la calidad oculta | 0.923 | ≥ 0.8 |

Con los pesos por defecto. Cumple: sí.

## Adjudicación

200 eventos simulados (semilla 4242): cada uno es una categoría con 2 a 5 proveedores activos, a 12 meses, con el P50 del servicio por el nivel de precio latente de cada proveedor y un SLA nulo o de 99.0 a 99.9 %. El recomendado usa la puntuación observada; el mejor verdadero repite el cálculo con la calidad oculta por 100 como desempeño, con el mismo costo, riesgo y SLA.

| Medida | Valor | Meta |
|---|---|---|
| Acierto top-1 (el recomendado es el mejor verdadero) | 85.0 % | ≥ 85.0 % |
| Acierto top-2 (el mejor verdadero está entre los dos primeros) | 99.5 % | |
| Margen promedio de los fallos | 7.6 puntos | |

Con los pesos por defecto. Cumple: sí.
