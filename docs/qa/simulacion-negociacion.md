# Simulación de negociación con bots (N1)

- **Escenarios:** 20 compras y 9 renovaciones; 73 sesiones.
- **Datos:** `generador.modelo.generar(42)`, los mismos que escribe `python -m generador` en `datos/`.
- **Cómo se corrió:** `SIMULACION_REPORTE=docs/qa/simulacion-negociacion.md uv run pytest services/negociacion/tests/test_simulacion.py`.
- **Acuerdo posible:** la reserva del bot cabe en los límites del comprador. Sin ese traslape no hay acuerdo y lo correcto es cerrar sin acuerdo.
- **Escenarios sin simular:** 1, porque sus valores sugeridos no se pueden publicar tal cual: Renovación simulada C-001101 (El ideal y el límite deben ser distintos.)

| Métrica | Meta (PRD §1.6) | Resultado |
|---|---|---|
| Acuerdos fuera de los límites del comprador | 0 | 0 |
| Tasa de acuerdo | ≥ 70 % | 82.2 % |
| Ahorro frente a la primera oferta (promedio de los acuerdos) | ≥ 8 % | 16.6 % |
| Sesiones con acuerdo posible | — | 60 de 73 |

## Por estilo de proveedor

| Estilo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |
|---|---|---|---|---|---|
| duro | 16 | 16 | 16 | 100.0 % | 19.7 % |
| erratico | 22 | 16 | 16 | 72.7 % | 14.5 % |
| flexible | 14 | 11 | 11 | 78.6 % | 9.0 % |
| manipulador | 21 | 17 | 17 | 81.0 % | 20.6 % |

## Por tipo de negociación

| Tipo | Sesiones | Acuerdo posible | Acuerdos | Tasa | Ahorro |
|---|---|---|---|---|---|
| compra | 64 | 55 | 55 | 85.9 % | 16.6 % |
| renovacion | 9 | 5 | 5 | 55.6 % | 16.0 % |

## Lectura

De las 73 sesiones simuladas (20 compras y 9 renovaciones), 60 cerraron en acuerdo tentativo (82.2 %) con un ahorro promedio de 16.6 % frente a la primera oferta del proveedor, y ningún acuerdo cruzó un límite del comprador (0). Se alcanzan las dos metas del PRD §1.6: la tasa de acuerdo supera el 70 % y el ahorro supera el 8 %; el estilo flexible es el más cercano en ahorro, con 9.0 %. Las 13 sesiones sin acuerdo (73 − 60) son las mismas 13 sin acuerdo posible (60 de 73), pues todas las sesiones en que la reserva del bot cabía en los límites del comprador cerraron en acuerdo; el 82.2 % lo fija entonces el traslape de los escenarios y no el agente. La renovación C-001101 no se simuló porque su servicio (NUBE-RSP-GB, 0.0538 USD por GB al mes) vale pocos centavos y, al redondear a centavos, el ideal y el límite sugeridos quedan ambos en 0.05; conviene decidir cómo se manejan los precios unitarios de pocos centavos, que también aparecen en 4 de las 20 compras simuladas.
