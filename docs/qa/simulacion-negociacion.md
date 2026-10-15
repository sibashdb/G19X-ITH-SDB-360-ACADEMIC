# Simulación de negociación con bots (N1)

- **Escenarios:** 20 compras y 10 renovaciones; 74 sesiones.
- **Datos:** `generador.modelo.generar(42)`, los mismos que escribe `python -m generador` en `datos/`.
- **Cómo se corrió:** `SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest services/negociacion/tests/test_simulacion.py`.
- **Acuerdo posible:** la reserva del bot cabe en los límites del comprador. Sin ese traslape no hay acuerdo y lo correcto es cerrar sin acuerdo.

| Métrica | Meta (PRD §1.6) | Resultado |
|---|---|---|
| Acuerdos fuera de los límites del comprador | 0 | 0 |
| Tasa de acuerdo | ≥ 70 % | 81.1 % |
| Ahorro frente a la primera oferta (promedio de los acuerdos) | ≥ 8 % | 16.5 % |
| Sesiones con acuerdo posible | — | 60 de 74 |

## Por estilo de proveedor

| Estilo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |
|---|---|---|---|---|---|
| duro | 16 | 16 | 16 | 100.0 % | 18.6 % |
| erratico | 23 | 16 | 16 | 69.6 % | 15.4 % |
| flexible | 14 | 11 | 11 | 78.6 % | 8.9 % |
| manipulador | 21 | 17 | 17 | 81.0 % | 20.6 % |

## Por tipo de negociación

| Tipo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |
|---|---|---|---|---|---|
| compra | 64 | 55 | 55 | 85.9 % | 16.6 % |
| renovacion | 10 | 5 | 5 | 50.0 % | 16.0 % |

> La sección `## Lectura` que sigue se escribe a mano: al volver a generar este archivo se borra.

## Lectura

De las 74 sesiones simuladas, 81.1 % cerraron en acuerdo tentativo con un ahorro promedio de 16.5 % frente a la primera oferta, y ningún acuerdo cruzó un límite del comprador (0). En el total se cumplen las dos metas del PRD §1.6 (tasa de acuerdo ≥ 70 % y ahorro ≥ 8 %); por estilo, el errático queda bajo la meta de tasa, con 69.6 %, y el flexible queda apenas sobre la meta de ahorro, con 8.9 %. En cada estilo y en cada tipo de negociación los acuerdos igualan a las sesiones con acuerdo posible (60 de 74 en total), así que la falta de acuerdo la explican los escenarios en que la reserva del bot no cabe en los límites del comprador y no el agente. Por eso la renovación llega a 50.0 %: solo 5 de sus 10 sesiones tenían acuerdo posible.
