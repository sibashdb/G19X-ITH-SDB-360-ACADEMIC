# Tablero: estado de las negociaciones y ahorro logrado

| Campo | Valor |
|---|---|
| Fecha | 2026-10-22 |
| Capacidad | 10 del PRD (§1.3), Tablero |
| Origen | Revisión del asesor del 22/10/2026, punto 3 ([`docs/MVP.md`](../../MVP.md)) |
| Estado | Diseño aprobado por el residente en conversación (22/10/2026) |

## 1. Intención

El Tablero ya muestra el gasto, los vencimientos, los proveedores en riesgo y el ahorro
potencial. Le faltan dos cosas de la capacidad 10: **en qué estado están las negociaciones** y
**cuánto se ahorró al negociar**. Con eso el MVP queda completo en su flujo: quien entra ve qué
negociaciones esperan algo y qué rindieron las que ya se adjudicaron.

**Metas:**
- Cuántas negociaciones hay en cada estado, con acceso directo a la lista filtrada.
- El ahorro logrado en las negociaciones adjudicadas, en MXN y en porcentaje.

**Fuera de alcance:**
- El ahorro frente al precio anterior y frente al P50, la tasa de acuerdo y las rondas promedio
  (PRD §4.7). El residente decidió medir solo frente a la primera oferta.
- Filtros por periodo, gráficas nuevas y exportación a CSV.
- Cualquier cambio a la recomendación, la propuesta o la aprobación.

**Sería un fracaso aunque funcione** que el ahorro use una regla de costo total distinta de la
que el comprador ve al adjudicar, o que una falla de `negociacion` deje sin Tablero a quien entra.

## 2. Decisiones

| # | Decisión | De quién |
|---|---|---|
| D1 | El ahorro se mide **solo frente a la primera oferta** del proveedor adjudicado | Residente |
| D2 | El ahorro se mide **en costo total del contrato**, con la misma regla que la adjudicación (precio × cantidad, por el plazo en las unidades mensuales, más la cuota de implementación), **al plazo acordado**: la primera oferta conserva sus precios y su cuota. Enmendada el 23/10/2026 tras la revisión final: con el plazo propio de la primera oferta, un plazo negociado invertía o inflaba el ahorro acumulado | Claude |
| D3 | La regla de costo total y las unidades mensuales pasan de `inteligencia` a `libs/comun`, y la usan los dos servicios | Claude |
| D4 | Los datos los calcula `negociacion` en `GET /tablero`; el Tablero de la SPA lo consulta aparte del de `inteligencia` | Claude |
| D5 | El monto en MXN usa el tipo de cambio implícito de la adjudicación (`costo_total_mxn / costo_total`), sin llamar a otro servicio | Claude |
| D6 | Se cuentan todas las negociaciones adjudicadas, sin filtro de fechas | Claude |

## 3. Cómo se calcula

**Por estado.** Un conteo de eventos por cada uno de los 7 estados de `ESTADOS_EVENTO`
(`borrador`, `abierto`, `en_evaluacion`, `pendiente_aprobacion`, `adjudicado`, `desierto` y
`cancelado`). Un estado sin eventos vale 0.

**Ahorro logrado.** Para cada evento en estado `adjudicado`, se toma su adjudicación vigente:
la única con estado `aprobada` o `directa`, porque las `rechazadas` son historial.
- **Primera oferta:** la oferta del proveedor (`autor = "proveedor"`) con la menor `secuencia` en
  la sesión adjudicada, aunque haya quedado fuera de los límites (`valida = False`): es lo primero
  que pidió el proveedor. Toda oferta guardada trae todas las líneas y palancas del evento. Su
  costo total se calcula con D2, armada igual que el candidato que
  `negociacion` envía a la recomendación (`adjudicacion.candidatos`). La cuota sale de sus
  palancas, o vale 0 si no la trae. El plazo es el acordado, el de la última oferta del
  proveedor, para que la diferencia sean precios y cuota y no meses de más o de menos.
- **Costo adjudicado:** `Adjudicacion.costo_total`, ya guardado.
- **En MXN:** las dos cifras se multiplican por `costo_total_mxn / costo_total` de esa
  adjudicación. En un evento en MXN, la tasa es 1.
- **Totales:**
  - número de adjudicadas;
  - suma de la primera oferta en MXN;
  - suma del costo adjudicado en MXN;
  - ahorro en MXN, que es la diferencia;
  - porcentaje: ahorro entre la suma de la primera oferta, por 100, con un decimal.

  Sin adjudicadas, los montos valen 0 y el porcentaje es `null`.
- El ahorro puede salir negativo si la primera oferta costaba menos que lo adjudicado (por
  ejemplo, si el proveedor subió la cuota de implementación). Se muestra tal cual, sin
  ocultarlo.
- Los montos se redondean a centavos.

## 4. Lo que se construye

**`libs/comun`.** Un módulo con `UNIDADES_MENSUALES` y la función de costo total, que recibe
las líneas (unidad, cantidad y precio), el plazo en meses y la cuota. `inteligencia` deja de
definirlas y las importa: su comportamiento y sus pruebas no cambian.

**`negociacion`, `GET /tablero`.**
- Lo pueden leer los tres roles internos (`Lector`).
- Devuelve:
  ```json
  {
    "por_estado": {"borrador": 0, "abierto": 2, "en_evaluacion": 1, "pendiente_aprobacion": 1,
                   "adjudicado": 3, "desierto": 1, "cancelado": 0},
    "ahorro": {"adjudicadas": 3, "primera_oferta_mxn": "1250000.00",
               "adjudicado_mxn": "1100000.00", "ahorro_mxn": "150000.00", "ahorro_pct": 12.0}
  }
  ```
- La regla de §3 es una función pura del dominio. El endpoint solo junta los datos de la base.
- Se exporta el contrato a `docs/arquitectura/openapi/negociacion.json`.

**SPA, Tablero.** Una fila nueva, «Negociaciones», debajo de los indicadores actuales, con dos
tarjetas:
- **Ahorro logrado:**
  - el monto, con el mismo formato corto que el ahorro potencial;
  - debajo, «X % frente a la primera oferta, en N negociaciones adjudicadas»;
  - un enlace a Negociaciones filtrada por adjudicadas;
  - el término tiene su definición en el glosario.
  - Sin adjudicadas, la tarjeta dice que todavía no hay negociaciones adjudicadas.
- **Estado de las negociaciones:** cada estado con su número, con las etiquetas de
  `NOMBRES_ESTADO_EVENTO`. Cada uno abre Negociaciones filtrada por ese estado (`?estado=…`).

La fila tiene su propia carga y su propio error. Si `negociacion` no responde, el resto del
Tablero se ve igual y solo esta fila muestra el error con la opción de reintentar.

## 5. Pruebas

- **Dominio:**
  - la regla del ahorro con un evento en MXN y otro en USD;
  - una primera oferta sin plazo ni cuota;
  - ahorro negativo;
  - sin adjudicadas (porcentaje `null`).
- **`comun`:** la función de costo total con unidades mensuales y no mensuales. Las pruebas
  actuales de la recomendación en `inteligencia` siguen pasando sin cambios.
- **API de `negociacion`** (PostgreSQL real):
  - los conteos por estado;
  - que una adjudicación rechazada no cuenta;
  - el ahorro de una negociación adjudicada de punta a punta;
  - la ruta entra a `ESPERADAS` de `test_api_permisos.py`: sin token responde 401 y con un rol
    externo, 403.
- **SPA:**
  - la fila con datos, sin adjudicadas y con error de `negociacion`, con el resto del Tablero
    visible;
  - los enlaces a la lista filtrada;
  - axe sin violaciones.
- **Revisión en el navegador** del Tablero en claro y oscuro, a 375 y 1440 px.

## 6. Documentación al terminar

- **README:** la capacidad 10 pasa a «Hecho»; el ahorro logrado se describe en «Qué está hecho».
- **`docs/MVP.md`:** la fila 10 pasa a «Hecho».
- **`docs/arquitectura/c4.md`:** `negociacion` también sirve los indicadores de las
  negociaciones del Tablero.
- **Ayuda:** la guía del Tablero menciona la fila nueva.
