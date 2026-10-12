# Validación del servicio de inteligencia

Generado el 12/10/2026 con `uv run python -m inteligencia.validacion --verdad datos/verdad_oculta.json`.

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
| Spearman entre la puntuación y la calidad oculta | 0.924 | ≥ 0.8 |

Con los pesos por defecto. Cumple: sí.
