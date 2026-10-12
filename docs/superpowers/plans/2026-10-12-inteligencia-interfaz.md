# Inteligencia en la interfaz (Plan B2) — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Las páginas de la plataforma muestran los datos reales del servicio `inteligencia` (Tablero, Proveedores, Precios, Ranking, Alertas con la campana, Configuración y la tarjeta "Datos y modelo" del Panel) y se cierran los pendientes de interfaz del Plan A y del plan 2.

**Architecture:** La web consulta `/api/inteligencia/…` con un solo gancho, `useInteligencia`, en `web/src/inteligencia.ts`, junto con los tipos de las respuestas y los formatos compartidos. Cuatro componentes pequeños (`BarraPuntuacion`, `Tendencia`, `PosicionMercado`, `ElementoAlerta`) se reutilizan en las páginas. El servicio recibe cuatro ajustes que la interfaz necesita: el orden de las alertas por ahorro, el filtro de alertas por proveedor, el error del último entrenamiento y la versión del modelo que de verdad está en uso.

**Tech Stack:** React 19 + TypeScript 6, Vite 8, Tailwind v4 con los tokens de `web/src/index.css`, shadcn/radix, TanStack Query 5, react-router 8, Recharts 3, lucide-react; Vitest + Testing Library + axe-core. En el servicio: Python 3.13, FastAPI, pytest con Testcontainers.

**Spec:** `docs/superpowers/specs/2026-10-10-servicio-inteligencia-design.md` (§2 B2, §7, §10 "Interfaz (B2)", §11 y §12). Las páginas se describen en `docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md` §3.1–§3.3; la de 2026-10-10 manda donde difieren.

## Global Constraints

**Rama y entorno**
- Rama `feat/inteligencia-interfaz`, creada desde `main` en `71bdd1b` (B1 ya integrada).
- Los comandos de la web se corren desde `web/`; los de Python, desde la raíz del repositorio con `uv run`.
- Las pruebas de integración del servicio usan Docker (Testcontainers); sin Docker, corra solo las unitarias que indique el paso y dígalo en su reporte.

**Contrato con el servicio**
- Los tipos de `web/src/inteligencia.ts` copian los esquemas de `services/inteligencia/src/inteligencia/api/esquemas.py`; un campo nuevo en uno va en el otro.
- La web pide `pedir("/inteligencia/…")`: `pedir` antepone `/api`.
- Toda consulta GET al servicio usa `useInteligencia(ruta)`, con la clave `["inteligencia", ruta]`; al guardar la configuración se invalidan todas con `{ queryKey: ["inteligencia"] }`.
- Los montos llegan como texto decimal y no se operan en el navegador. La única excepción es calcular el ancho de una barra, y lleva un comentario que lo dice.
- La puntuación y la tendencia llegan con un decimal. El MAPE y la cobertura llegan como fracción (`"0.083000"`) y se muestran como porcentaje con un decimal (`"8.3 %"`).

**Textos y formato**
- Español de México, de "usted". El primer término técnico de cada página va con `Termino` (glosario de `web/src/glosario.ts`).
- El color nunca es la única señal: severidad, posición frente al mercado, tendencia y total de los pesos llevan icono y texto.
- Formatos (todos en `web/src/inteligencia.ts` o `web/src/tipos.ts`):
  - precios y montos de tabla: `formatoMoneda(valor, moneda)`, que ya existe;
  - cifras grandes del Tablero: `montoCorto("48200000.00")` → `"$48.2 M MXN"`;
  - puntuación: `formatoPuntuacion(72.4)` → `"72.4"`;
  - porcentaje: `formatoPorcentaje(8.3)` → `"8.3 %"`;
  - fechas: `formatoFecha` y `formatoFechaHora`, que ya existen.
- Rango de una puntuación (color de su barra):
  - `bajo` si es menor que el umbral de riesgo (40 por omisión; se lee de `GET /configuracion`);
  - `alto` desde 70, o desde el umbral si este es mayor;
  - `medio` entre los dos.

**Accesibilidad**
- 0 violaciones de axe en cada página, en claro y oscuro (`esperarSinViolaciones`), y en el navegador con la regla de contraste, a 375, 768, 1024 y 1440 px (Task 12).
- Cada gráfica va en un `figure` con `aria-label`. Sus datos están también en una tabla, dentro de `<details>` ("Ver los datos") cuando la tabla no es el contenido principal.
- Un botón que no aplica en ese momento pero puede tener el foco usa `aria-disabled` y una guarda en su manejador, no `disabled`.
- Foco: `outline-hidden`, nunca `outline-none`. Cuando un botón desaparece al usarse, el foco pasa a un control que siga en pantalla.

**Dependencias**
- No se agregan dependencias. `sonner` y `progress` no se instalan: los avisos de guardado y de entrenamiento van en línea, con `role="status"`.

**Seguridad de credenciales**
- Nunca escriba contraseñas ni secretos en comandos, archivos versionados o reportes; `infra/.env` no se versiona.
- Las contraseñas de desarrollo están en `infra/keycloak/realm-plataforma.json`; no las repita.
- No haga `git push` ni toque los remotos.

**Calidad**
- Si la tarea toca `web/`, deben quedar limpios: `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check "src/**/*.{ts,tsx}"`.
- Si toca Python, deben quedar limpios: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` y `uv run pytest services/inteligencia`.
- No se editan planes ni bitácoras anteriores (`docs/superpowers/plans/*` de otras ramas, `docs/qa/bitacora-*`).

**Commits**
- Conventional Commits en español.
- Mensaje: asunto, una línea en blanco y `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (dos `-m`).
- Verifique con `git log -1 --format=%B`.
- No haga commit de `infra/.env`, `datos/`, `web/node_modules`, `web/dist`, `.superpowers/` ni PDFs.

## Review Focus

1. **El servicio de inteligencia no responde.** La página que depende de él muestra el error en español con "Reintentar".
   - La ficha del proveedor sigue mostrando lo que viene de `proveedores` aunque la puntuación, el mercado o las alertas fallen.
   - La campana dice en su menú que no pudo cargar las alertas.
   - Pruebas: Task 6 (`la ficha se muestra aunque la inteligencia no responda`) y Task 4 (`la campana avisa en su menú si no pudo cargar las alertas`).
2. **Copia local vacía o a medio llenar** (entorno recién creado o reproceso en curso). Un proveedor que existe en `proveedores` pero que la inteligencia aún no conoce (404) se ve con "Sin puntuación todavía". Un Tablero en ceros explica en cada sección qué falta.
   - Pruebas: Task 3 (`sin datos, cada sección explica qué falta`) y Task 6 (`un proveedor que la inteligencia aún no conoce se ve sin puntuación`).
3. **Cientos de alertas de sobreprecio** (275 en el entorno de desarrollo).
   - La campana muestra a lo más "99+".
   - Alertas pagina de 25 en 25 y, dentro de una severidad, pone primero el sobreprecio con más ahorro en MXN.
   - Una página fuera de rango ofrece volver a la primera.
   - Pruebas: Task 1 (`test_en_la_misma_severidad_los_sobreprecios_van_de_mayor_a_menor_ahorro_en_mxn`), Task 4 (`la campana limita el número a 99+`, `pagina de 25 en 25` y `una página fuera de rango ofrece volver a la primera`) y Task 7 (`la vista de todos los sobreprecios los pagina y enlaza a cada servicio`).
4. **Valores inválidos en formularios y en la URL.**
   - Configuración: pesos que no suman 100, negativos o decimales.
   - Precios: cantidad 0, negativa o enorme.
   - URL: `orden=hackeo`, `pagina=abc`, `proveedor=no-uuid`.
   - Ninguno llega al servicio: se rechazan junto al campo o se cambian por el valor por omisión. El error que sí responda el servicio se muestra junto a su campo.
   - Pruebas: Task 9 (`no guarda si los pesos no suman 100 y dice cuánto suman` y `muestra junto al campo el error del servicio`), Task 7 (`una cantidad inválida en la URL usa la sugerida` y `una cantidad de cero en el formulario no se envía`), Task 5 (`ignora parámetros inválidos de la URL`) y Task 4 (`un proveedor inválido en la URL se ignora, igual que los demás valores inválidos`).
5. **Reentrenamiento que falla, que ya corre o cuyo modelo no carga.**
   - Un 409 explica que ya hay uno en curso y la página sigue el entrenamiento hasta que termina.
   - Un entrenamiento fallido muestra el motivo (`ultimo_error`).
   - Un modelo promovido que no se pudo cargar avisa que se usa la línea base.
   - Pruebas: Task 1 (`test_un_modelo_que_no_carga_esta_activo_pero_no_en_uso`) y Task 9 (`un entrenamiento que falla muestra el motivo` y `avisa si el modelo promovido no está en uso`).

## Tareas

Se ejecutan en orden; cada una deja el repositorio verde.

| # | Tarea | Archivos principales |
|---|---|---|
| 1 | Servicio: orden por ahorro, filtro por proveedor, último error y modelo en uso | `dominio/monedas.py`, `dominio/alertas.py`, `api/tablero.py`, `entrenamiento.py`, `api/ajustes.py` |
| 2 | Cimientos de la web: tipos, consulta, formatos y componentes | `web/src/inteligencia.ts`, `componentes/{BarraPuntuacion,Tendencia,PosicionMercado,ElementoAlerta}.tsx`, `glosario.ts` |
| 3 | Tablero con datos reales | `web/src/paginas/Tablero.tsx` |
| 4 | Alertas, campana y paginación accesible | `paginas/Alertas.tsx`, `componentes/BarraSuperior.tsx`, `componentes/Paginacion.tsx` |
| 5 | Lista de proveedores desde la inteligencia | `paginas/Proveedores.tsx` |
| 6 | Ficha del proveedor: puntuación, mercado y alertas | `paginas/ProveedorDetalle.tsx`, `componentes/TablaContratos.tsx` |
| 7 | Precios: referencia, historial y sobreprecios | `paginas/Precios.tsx`, `componentes/{ReferenciaPrecio,HistorialPrecios,TablaSobreprecios}.tsx` |
| 8 | Ranking | `paginas/Ranking.tsx` |
| 9 | Configuración, "Datos y modelo" y Centro de ayuda | `paginas/Configuracion.tsx`, `componentes/{FormularioPuntuacion,PanelModeloPrecios}.tsx`, `paginas/Panel.tsx`, `ayuda.ts` |
| 10 | Rutas diferidas y foco visible en alto contraste | `rutas.tsx`, `components/ui/*.tsx`, `componentes/Layout.tsx` |
| 11 | Guía por usuario, términos en la guía y README | `guia.ts`, `componentes/GuiaUso.tsx`, `README.md` |
| 12 | Revisión en navegador y documentación | `docs/qa/revision-inteligencia-interfaz.md`, `README.md` |

**Fuera de alcance** (se registran aquí para que nadie los dé por hechos):
- Pendientes de B1 que son del servicio y no cambian la interfaz:
  - un contrato cuenta en su propia referencia de mercado;
  - el contexto se recalcula en cada consulta mientras dura una importación.
  - Quedan para un plan del servicio.
- El ranking por categoría mezcla grupos de comparación cuando una categoría llega a 20 proveedores. La Task 8 lo explica en pantalla; el cálculo no cambia.
- "Gasto por servicio" en el Resumen de la ficha: estaba en la especificación de origen, pero la de 2026-10-10 (§7.1) ya no lo pide.
- El estado "atendida" de las alertas (spec §2).
- `sonner` y `progress`: ver Dependencias.
- Los valores viejos de `--input` en el plan del Plan A: no se editan planes anteriores.

---

### Task 1: Servicio: orden por ahorro, filtro por proveedor, último error y modelo en uso

Cuatro ajustes de `inteligencia` que la interfaz necesita. Todos vienen de decisiones del residente o de la revisión final de B1:

- **Orden de las alertas.** Dentro de una severidad y una fecha, primero los riesgos y luego los sobreprecios, de mayor a menor ahorro en MXN. Así la campana y la primera página de Alertas muestran lo que más conviene atender.
- **Filtro por proveedor.** `GET /alertas?proveedor=<uuid>` sirve a la ficha del proveedor y al enlace "alertas" de la lista.
- **Error del último entrenamiento.** Hoy, un reentrenamiento manual que falla responde 202 y la pantalla no muestra nada. `/modelos` gana `ultimo_error`.
- **Modelo en uso.** `/modelos.activo` y `/datos.modelo` dicen el modelo promovido aunque cargarlo haya fallado y se esté usando la línea base. `/modelos` y `/datos` ganan `en_uso`: la versión que de verdad responde, o `null` si se usa la línea base.

`tipo_cambio_en` y `a_mxn` pasan de `dominio/tablero.py` a un módulo propio. `alertas.py` los necesita para ordenar, y `tablero.py` ya importa `alertas.py`: dejarlos en `tablero.py` haría una importación circular.

**Files:**
- Create: `services/inteligencia/src/inteligencia/dominio/monedas.py`
- Modify: `services/inteligencia/src/inteligencia/dominio/tablero.py`
- Modify: `services/inteligencia/src/inteligencia/dominio/alertas.py`
- Modify: `services/inteligencia/src/inteligencia/contexto.py`
- Modify: `services/inteligencia/src/inteligencia/api/tablero.py`
- Modify: `services/inteligencia/src/inteligencia/api/precios.py:17`
- Modify: `services/inteligencia/src/inteligencia/api/proveedores.py:18`
- Modify: `services/inteligencia/src/inteligencia/entrenamiento.py`
- Modify: `services/inteligencia/src/inteligencia/api/esquemas.py`
- Modify: `services/inteligencia/src/inteligencia/api/ajustes.py`
- Modify: `docs/superpowers/specs/2026-10-10-servicio-inteligencia-design.md` (§4.3 y su cabecera)
- Test: `services/inteligencia/tests/test_alertas.py`, `test_tablero.py`, `test_api_tablero.py`, `test_entrenamiento.py`, `test_api_ajustes.py`

**Interfaces:**
- Consumes: lo que B1 dejó en `main` (`Alerta`, `ordenar`, `Contexto.modelo`, `Entrenador`, `RegistroModelos`, `DatosSalida`).
- Produces:
  - `inteligencia.dominio.monedas`: `CENTAVOS`, `tipo_cambio_en(tipos, fecha) -> Decimal | None` y `a_mxn(monto, moneda, usd_mxn) -> Decimal`, sin cambios de comportamiento.
  - `ordenar(alertas: Iterable[Alerta], usd_mxn: Decimal | None = None) -> list[Alerta]`.
  - `GET /alertas` acepta `proveedor: UUID`.
  - `Entrenador.ultimo_error: str | None` y la constante `entrenamiento.ERROR_INTERNO`.
  - JSON de `GET /modelos`: `{entrenando, activo, en_uso, ultimo_error, elementos}`.
  - JSON de `GET /datos`: `{registros, ultimo_evento, modelo, en_uso, entrenando}`.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `services/inteligencia/tests/test_alertas.py`, agregue `from dataclasses import replace` a las importaciones y esta prueba al final:

```python
def test_en_la_misma_severidad_los_sobreprecios_van_de_mayor_a_menor_ahorro_en_mxn() -> None:
    contrato = _contrato(date(2026, 12, 31))
    base = sobreprecio(contrato, LINEA, Banda(18.0, 20.0, 22.0), HOY)
    caida = riesgo("p-3", "Redes del Sur", 55.0, 70.0, 40, HOY)
    assert base is not None and caida is not None and caida.severidad == "media"
    pesos = replace(base, id="sobreprecio:a", ahorro_potencial=Decimal("1000.00"), moneda="MXN")
    dolares = replace(base, id="sobreprecio:b", ahorro_potencial=Decimal("100.00"), moneda="USD")
    # 100 USD a 20 MXN por dólar son 2,000 MXN: más que los 1,000 MXN del otro contrato.
    assert [a.id for a in ordenar([pesos, dolares, caida], Decimal("20"))] == [
        caida.id,
        "sobreprecio:b",
        "sobreprecio:a",
    ]
    # Sin tipo de cambio, el ahorro en USD no se puede convertir y cuenta como 0.
    assert [a.id for a in ordenar([dolares, pesos])] == ["sobreprecio:a", "sobreprecio:b"]
```

En `services/inteligencia/tests/test_tablero.py`, cambie la importación de la línea 7 por estas dos:

```python
from inteligencia.dominio.monedas import a_mxn, tipo_cambio_en
from inteligencia.dominio.tablero import calcular
```

En `services/inteligencia/tests/test_api_tablero.py`, agregue `{"proveedor": "no-es-un-uuid"}` a la lista de `@pytest.mark.parametrize` de `test_alertas_valida_los_filtros`, y esta prueba después de `test_alertas_filtra_pagina_y_ordena`:

```python
async def test_alertas_filtra_por_proveedor(
    cliente: httpx.AsyncClient, comprador: Cabeceras, cargar: Cargar
) -> None:
    await cargar(generar(42, n_proveedores=10))
    todas = (await cliente.get("/alertas", params={"limite": 200}, headers=comprador)).json()
    proveedor = todas["elementos"][0]["proveedor_id"]
    suyas = (
        await cliente.get(
            "/alertas", params={"proveedor": proveedor, "limite": 200}, headers=comprador
        )
    ).json()
    esperadas = [a for a in todas["elementos"] if a["proveedor_id"] == proveedor]
    assert suyas == {"total": len(esperadas), "elementos": esperadas}
```

En `services/inteligencia/tests/test_entrenamiento.py`:

1. Agregue `assert entrenador.ultimo_error is None` después de `assert not entrenador.entrenando` en `test_entrenar_registra_el_modelo_y_publica_el_evento`.
2. Reemplace el cuerpo de `test_un_entrenamiento_fallido_libera_el_candado` desde `entrenador = Entrenador(fabrica, tmp_path)` por:

```python
    entrenador = Entrenador(fabrica, tmp_path)
    assert entrenador.iniciar("manual", ADMIN)
    await entrenador.esperar()
    assert not entrenador.entrenando
    assert entrenador.ultimo_error == entrenamiento.ERROR_INTERNO
    assert await _registros(fabrica) == []
    assert entrenador.iniciar("manual", ADMIN)  # se puede volver a intentar
    assert entrenador.ultimo_error is None  # un intento nuevo borra el error anterior
    await entrenador.esperar()
```

3. En `test_sin_datos_no_registra_nada`, agregue al final:

```python
    assert entrenador.ultimo_error == (
        "No hay datos suficientes para entrenar. Solo hay 0 líneas de contrato."
    )
```

En `services/inteligencia/tests/test_api_ajustes.py`:

1. Agregue a las importaciones:

```python
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from inteligencia.modelos import ModeloBenchmark, Outbox
```

   Quite la importación anterior de `Outbox` sola.
2. Reemplace la aserción de `test_registro_de_modelos_vacio` por:

```python
    assert respuesta.json() == {
        "entrenando": False,
        "activo": None,
        "en_uso": None,
        "ultimo_error": None,
        "elementos": [],
    }
```

3. En `test_entrenar_registra_el_modelo`, agregue al final:

```python
    assert registro["en_uso"] == registro["activo"]
    assert registro["ultimo_error"] is None
```

4. En `test_datos_de_la_copia_local`, cambie la última aserción por:

```python
    assert (cuerpo["modelo"], cuerpo["en_uso"], cuerpo["entrenando"]) == (None, None, False)
```

5. Agregue al final:

```python
async def test_un_modelo_que_no_carga_esta_activo_pero_no_en_uso(
    cliente: httpx.AsyncClient,
    admin: Cabeceras,
    comprador: Cabeceras,
    fabrica: Fabrica,
    tmp_path: Path,
) -> None:
    """Si el archivo del modelo promovido se perdió, se usa la línea base y la API lo dice."""
    async with fabrica() as sesion, sesion.begin():
        sesion.add(
            ModeloBenchmark(
                version=1,
                entrenado_en=datetime.now(UTC),
                origen="manual",
                actor_nombre="admin1",
                observaciones=100,
                datos_hasta=date(2026, 9, 30),
                mape=Decimal("0.100000"),
                mape_linea_base=Decimal("0.120000"),
                cobertura=Decimal("0.500000"),
                pinball=Decimal("0.010000"),
                promovido=True,
                artefacto=str(tmp_path / "no-existe.joblib"),
            )
        )
    registro = (await cliente.get("/modelos", headers=comprador)).json()
    assert (registro["activo"], registro["en_uso"]) == (1, None)
    datos = (await cliente.get("/datos", headers=admin)).json()
    assert (datos["modelo"]["version"], datos["en_uso"]) == (1, None)
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run: `uv run pytest services/inteligencia/tests/test_alertas.py services/inteligencia/tests/test_tablero.py -v`
Expected: FAIL. `test_tablero.py` no encuentra `inteligencia.dominio.monedas`, y `ordenar` no acepta el tipo de cambio (`TypeError`).

Run: `uv run pytest services/inteligencia/tests/test_api_tablero.py services/inteligencia/tests/test_entrenamiento.py services/inteligencia/tests/test_api_ajustes.py -v`
Expected: FAIL. `proveedor` no se valida (200 en lugar de 422), `ultimo_error` no existe (`AttributeError`) y `/modelos` y `/datos` no traen `en_uso`.

- [ ] **Step 3: Mover la conversión de monedas a su propio módulo**

Cree `services/inteligencia/src/inteligencia/dominio/monedas.py`:

```python
"""Conversión de montos a MXN con el tipo de cambio vigente."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

CENTAVOS = Decimal("0.01")


def tipo_cambio_en(tipos: Mapping[date, Decimal], fecha: date) -> Decimal | None:
    """El tipo de cambio vigente en `fecha` (o el más viejo si `fecha` es anterior a todos)."""
    if not tipos:
        return None
    anteriores = [periodo for periodo in tipos if periodo <= fecha]
    return tipos[max(anteriores)] if anteriores else tipos[min(tipos)]


def a_mxn(monto: Decimal, moneda: str, usd_mxn: Decimal | None) -> Decimal:
    if moneda == "MXN":
        return monto
    # ponytail: sin tipo de cambio registrado, los montos en USD no se pueden convertir y no
    # cuentan; con el ERP de verdad siempre hay al menos un periodo.
    return monto * usd_mxn if usd_mxn is not None else Decimal(0)
```

En `services/inteligencia/src/inteligencia/dominio/tablero.py`:

1. Borre `CENTAVOS = Decimal("0.01")` y las funciones `tipo_cambio_en` y `a_mxn` completas.
2. Agregue `from inteligencia.dominio.monedas import CENTAVOS, a_mxn, tipo_cambio_en` junto a las otras importaciones de `inteligencia.dominio`.
3. Cambie la línea de `alertas_principales` por:

```python
        alertas_principales=ordenar(alertas, ultimo)[:CUANTAS_ALERTAS],
```

En `services/inteligencia/src/inteligencia/api/precios.py` y `api/proveedores.py`, cambie:

```python
from inteligencia.dominio.tablero import CENTAVOS, a_mxn, tipo_cambio_en
```

por:

```python
from inteligencia.dominio.monedas import CENTAVOS, a_mxn, tipo_cambio_en
```

- [ ] **Step 4: Ordenar por ahorro en MXN dentro de cada severidad**

En `services/inteligencia/src/inteligencia/dominio/alertas.py`:

1. Agregue `from inteligencia.dominio.monedas import a_mxn` a las importaciones de `inteligencia.dominio`.
2. Debajo de `ORDEN_SEVERIDAD`, agregue:

```python
# En la misma severidad y fecha: primero el proveedor en riesgo, luego el vencimiento y al final
# los sobreprecios, de mayor a menor ahorro (decisión del residente para la campana y Alertas).
ORDEN_TIPO: dict[str, int] = {"riesgo": 0, "vencimiento": 1, "sobreprecio": 2}
```

3. Reemplace `ordenar` por:

```python
def ordenar(alertas: Iterable[Alerta], usd_mxn: Decimal | None = None) -> list[Alerta]:
    """Por severidad y fecha; los sobreprecios, de mayor a menor ahorro en MXN."""

    def clave(alerta: Alerta) -> tuple[int, date, int, Decimal, str]:
        ahorro = a_mxn(alerta.ahorro_potencial or Decimal(0), alerta.moneda or "MXN", usd_mxn)
        return (
            ORDEN_SEVERIDAD[alerta.severidad],
            alerta.fecha,
            ORDEN_TIPO[alerta.tipo],
            -ahorro,
            alerta.id,
        )

    return sorted(alertas, key=clave)
```

En `services/inteligencia/src/inteligencia/contexto.py`:

1. Agregue `from inteligencia.dominio.monedas import tipo_cambio_en`.
2. Cambie `alertas = ordenar(avisos)` por:

```python
    alertas = ordenar(avisos, tipo_cambio_en(datos.tipos_cambio, hoy))
```

- [ ] **Step 5: Filtrar las alertas por proveedor**

En `services/inteligencia/src/inteligencia/api/tablero.py`, agregue `from uuid import UUID` y cambie la ruta `/alertas` por:

```python
@router.get("/alertas")
async def alertas(
    contexto: Ctx,
    tipo: Literal["vencimiento", "sobreprecio", "riesgo"] | None = None,
    severidad: Literal["alta", "media", "informativa"] | None = None,
    proveedor: UUID | None = None,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> esquemas.PaginaAlertas:
    filtradas = [
        a
        for a in contexto.alertas
        if (tipo is None or a.tipo == tipo)
        and (severidad is None or a.severidad == severidad)
        and (proveedor is None or a.proveedor_id == str(proveedor))
    ]
    visibles = filtradas[(pagina - 1) * limite : pagina * limite]
    return esquemas.PaginaAlertas(
        total=len(filtradas),
        elementos=[esquemas.AlertaSalida.model_validate(a) for a in visibles],
    )
```

- [ ] **Step 6: Guardar el error del último entrenamiento**

En `services/inteligencia/src/inteligencia/entrenamiento.py`:

1. Debajo de `INTERVALO_REVISION_S = 60`, agregue:

```python
ERROR_INTERNO = "El entrenamiento falló por un error interno; revise los registros del servicio."
```

2. En `__init__`, después de `self._tarea: asyncio.Task[None] | None = None`, agregue:

```python
        self._ultimo_error: str | None = None
```

3. Después de la propiedad `entrenando`, agregue:

```python
    @property
    def ultimo_error(self) -> str | None:
        """Por qué falló el último entrenamiento; None si terminó bien o si no ha corrido ninguno."""
        return self._ultimo_error
```

4. En `iniciar`, antes de `self._en_curso = True`, agregue `self._ultimo_error = None`.
5. Cambie los dos `except` de `_entrenar` por:

```python
        except DatosInsuficientes as exc:
            log.warning("No se entrenó el modelo de precios: %s", exc)
            self._ultimo_error = f"No hay datos suficientes para entrenar. {exc}"
        except Exception:
            log.exception("Falló el entrenamiento del modelo de precios")
            self._ultimo_error = ERROR_INTERNO
```

6. En `ejecutar_periodicamente`, cambie el comentario `ponytail` por:

```python
        # ponytail: si el entrenamiento falla siempre (p. ej. pocos datos), se reintenta cada
        # `intervalo`; el motivo queda en `ultimo_error` y Configuración lo muestra.
```

- [ ] **Step 7: Informar el modelo en uso y el último error**

En `services/inteligencia/src/inteligencia/api/esquemas.py`, cambie `RegistroModelos` y `DatosSalida` por:

```python
class RegistroModelos(BaseModel):
    entrenando: bool
    activo: int | None  # el último promovido; None: ninguno mejoró la línea base
    en_uso: int | None  # el que responde las consultas; None: se usa la línea base
    ultimo_error: str | None  # por qué falló el último entrenamiento
    elementos: list[ModeloSalida]
```

```python
class DatosSalida(BaseModel):
    registros: dict[str, int]
    ultimo_evento: datetime | None
    modelo: ModeloSalida | None  # el activo (último promovido)
    en_uso: int | None  # el que responde las consultas; None: se usa la línea base
    entrenando: bool
```

En `services/inteligencia/src/inteligencia/api/ajustes.py`:

1. Cambie `from inteligencia.api.dependencias import Admin, Interno, Sesion` por:

```python
from inteligencia.api.dependencias import Admin, Ctx, Interno, Sesion
from inteligencia.contexto import Contexto
```

2. Agregue, debajo de `_para_evento`:

```python
def _en_uso(contexto: Contexto) -> int | None:
    """La versión que de verdad responde: la promovida puede no cargar (archivo perdido o de otra
    versión de scikit-learn) y entonces se usa la línea base."""
    return None if contexto.modelo is None else contexto.modelo.version
```

3. Cambie la ruta `/modelos` por:

```python
@router.get("/modelos")
async def modelos(
    request: Request, _: Interno, sesion: Sesion, contexto: Ctx
) -> esquemas.RegistroModelos:
    registros = await sesion.scalars(
        select(ModeloBenchmark).order_by(ModeloBenchmark.version.desc()).limit(MAX_MODELOS)
    )
    activo = await consultas.modelo_activo(sesion)
    entrenador: Entrenador = request.app.state.entrenador
    return esquemas.RegistroModelos(
        entrenando=entrenador.entrenando,
        activo=None if activo is None else activo.version,
        en_uso=_en_uso(contexto),
        ultimo_error=entrenador.ultimo_error,
        elementos=[esquemas.ModeloSalida.model_validate(r) for r in registros],
    )
```

4. Cambie la firma de `/datos` para que el rol se revise antes de calcular el contexto, y agregue `en_uso`:

```python
@router.get("/datos")
async def datos(
    request: Request, _: Admin, sesion: Sesion, contexto: Ctx
) -> esquemas.DatosSalida:
```

   Y en su `return`, agregue `en_uso=_en_uso(contexto),` después de `modelo=…`.

- [ ] **Step 8: Correr las pruebas y ver que pasan**

Run: `uv run pytest services/inteligencia -v`
Expected: PASS (todas, incluidas las de integración; necesitan Docker).

Run: `uv run ruff format . && uv run ruff check . && uv run mypy`
Expected: sin errores.

- [ ] **Step 9: Precisar la especificación**

En `docs/superpowers/specs/2026-10-10-servicio-inteligencia-design.md`:

1. En la tabla de la cabecera, cambie la fila `Estado` por:

```markdown
| Estado | Aprobada por el residente (2026-10-10); §4.2, §4.3 y §6 precisados con el plan B1; §4.3, con el plan B2 |
```

2. En la tabla de §4.3, cambie estas tres filas:

```markdown
| `GET /alertas?tipo=&severidad=&proveedor=&pagina=&limite=` | interno | Alertas activas por severidad y fecha; en la misma severidad, los sobreprecios de mayor a menor ahorro en MXN (la campana usa `limite=5`) |
```

```markdown
| `GET /modelos` · `POST /modelos/entrenar` | interno · admin | Registro de modelos, versión activa (promovida), versión en uso (`null` si se usa la línea base) y error del último entrenamiento · entrenamiento (202) |
```

```markdown
| `GET /datos` | admin | Registros por entidad en la copia local, último evento recibido, modelo activo con su MAPE y versión en uso |
```

- [ ] **Step 10: Commit**

```bash
git add services/inteligencia docs/superpowers/specs/2026-10-10-servicio-inteligencia-design.md
git commit -m "feat(inteligencia): alertas por ahorro y por proveedor, último error del entrenamiento y modelo en uso" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Cimientos de la web: tipos, consulta, formatos y componentes

Todo lo que las páginas comparten va en un solo módulo, `web/src/inteligencia.ts`: los tipos de las respuestas, el gancho de consulta, el umbral de riesgo, los formatos y la ruta de cada alerta. Los indicadores que se repiten en varias páginas van en cuatro componentes pequeños. El glosario corrige "ahorro potencial", que no es anual sino por lo que resta del contrato, y suma los términos que traen Configuración y Ranking.

**Files:**
- Create: `web/src/inteligencia.ts`
- Create: `web/src/inteligencia.test.ts`
- Create: `web/src/componentes/BarraPuntuacion.tsx`
- Create: `web/src/componentes/Tendencia.tsx`
- Create: `web/src/componentes/PosicionMercado.tsx`
- Create: `web/src/componentes/ElementoAlerta.tsx`
- Create: `web/src/componentes/IndicadoresInteligencia.test.tsx`
- Modify: `web/src/glosario.ts`
- Modify: `web/src/api.ts` (`enviarJson` acepta `"PUT"`)

**Interfaces:**
- Consumes: `pedir`, `enviarJson` (`@/api`), `useToken` (`@/auth`), `formatoMoneda`, `formatoFecha`, `NOMBRES_SEVERIDAD`, `NOMBRES_TIPO_ALERTA`, `Categoria`, `Severidad`, `TipoAlerta` (`@/tipos`), `Badge`, `Popover*` (`@/components/ui`), `cn` (`@/lib/utils`).
- Produces (en `@/inteligencia`):
  - Tipos: `Confianza`, `Metodo`, `ClaveComponente`, `Alerta`, `PaginaAlertas`, `Destacado`, `Vencimiento`, `TableroDatos`, `ServicioPrecios`, `Referencia`, `HistorialPrecios`, `Sobreprecio`, `ProveedorConPuntuacion`, `PaginaProveedoresConPuntuacion`, `ComponentePuntuacion`, `Puntuacion`, `MercadoLinea`, `FilaRanking`, `ConfiguracionInteligencia`, `ModeloPrecios`, `RegistroModelos`, `DatosInteligencia`, `RangoPuntuacion`.
  - `useInteligencia<T>(ruta: string, opciones?): UseQueryResult<T, Error>`, con la clave `["inteligencia", ruta]`.
  - `useUmbralRiesgo(): number` y `UMBRAL_POR_OMISION = 40`.
  - `rangoPuntuacion(valor: number, umbral: number): RangoPuntuacion` y `PUNTUACION_ALTA = 70`.
  - Formatos: `formatoPuntuacion(valor: number): string`, `formatoPorcentaje(valor: number): string`, `fraccionComoPorcentaje(valor: string): string`, `formatoDecimal(valor: number, decimales?: number): string`, `montoCorto(valor: string): string`, `porUnidad(unidad: string): string`.
  - `COMPONENTES: { clave: ClaveComponente; nombre: string; corto: string; unidad: string }[]`.
  - `rutaDeAlerta(alerta: Alerta): string`.
- Produces (componentes):
  - `BarraPuntuacion({ puntuacion: number | null; confianza: Confianza | null; umbral: number })`.
  - `Tendencia({ valor: number | null })`.
  - `PosicionMercado({ linea: MercadoLinea })`.
  - `ElementoAlerta({ alerta: Alerta })`.
- Produces (glosario): claves nuevas `mape`, `percentil` y `lineaBase`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Cree `web/src/inteligencia.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import {
  formatoPorcentaje,
  formatoPuntuacion,
  fraccionComoPorcentaje,
  montoCorto,
  porUnidad,
  rangoPuntuacion,
  rutaDeAlerta,
  type Alerta,
} from "@/inteligencia"

const ALERTA: Alerta = {
  id: "vencimiento:c1",
  tipo: "vencimiento",
  severidad: "alta",
  titulo: "Vence en 12 días: CT-0001",
  explicacion: "El contrato con Nube Andina (Nube pública) termina el 24/10/2026.",
  entidad_tipo: "contrato",
  entidad_id: "c1",
  entidad_nombre: "CT-0001",
  proveedor_id: "p 1",
  proveedor_nombre: "Nube Andina",
  fecha: "2026-10-24",
  ahorro_potencial: null,
  moneda: null,
}

describe("formatos de la inteligencia", () => {
  it("abrevia las cifras grandes del Tablero", () => {
    expect(montoCorto("48200000.00")).toBe("$48.2 M MXN")
    expect(montoCorto("1174700000.00")).toBe("$1,174.7 M MXN")
    expect(montoCorto("12500.00")).toBe("$12.5 mil MXN")
    expect(montoCorto("950.5")).toBe("$950.50 MXN")
  })

  it("da un decimal a las puntuaciones y a los porcentajes", () => {
    expect(formatoPuntuacion(72.44)).toBe("72.4")
    expect(formatoPuntuacion(6)).toBe("6.0")
    expect(formatoPorcentaje(8.3)).toBe("8.3 %")
    expect(formatoPorcentaje(-3.1)).toBe("-3.1 %")
    expect(fraccionComoPorcentaje("0.083000")).toBe("8.3 %")
  })

  it("dice la unidad del precio en palabras", () => {
    expect(porUnidad("usuario_mes")).toBe("por usuario al mes")
    expect(porUnidad("vcpu_mes")).toBe("por vCPU al mes")
    expect(porUnidad("otra")).toBe("por otra")
  })

  it("ubica la puntuación en su rango según el umbral de riesgo", () => {
    expect(rangoPuntuacion(39.9, 40)).toBe("bajo")
    expect(rangoPuntuacion(40, 40)).toBe("medio")
    expect(rangoPuntuacion(69.9, 40)).toBe("medio")
    expect(rangoPuntuacion(70, 40)).toBe("alto")
    // Con un umbral por encima de 70 no hay rango medio: o está en riesgo o está bien.
    expect(rangoPuntuacion(72, 75)).toBe("bajo")
    expect(rangoPuntuacion(75, 75)).toBe("alto")
  })

  it("lleva cada alerta a su proveedor, en la pestaña de contratos si es de un contrato", () => {
    expect(rutaDeAlerta(ALERTA)).toBe("/proveedores/p%201?pestana=contratos")
    expect(
      rutaDeAlerta({ ...ALERTA, entidad_tipo: "proveedor", entidad_id: "p 1" })
    ).toBe("/proveedores/p%201")
  })
})
```

Cree `web/src/componentes/IndicadoresInteligencia.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import { PosicionMercado } from "@/componentes/PosicionMercado"
import { Tendencia } from "@/componentes/Tendencia"
import type { Alerta, MercadoLinea } from "@/inteligencia"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

afterEach(cleanup)

const LINEA: MercadoLinea = {
  contrato_id: "c1",
  folio: "CT-0001",
  codigo_servicio: "NUBE-01",
  servicio: "Nube pública",
  moneda: "MXN",
  precio: "1500.0000",
  posicion: "sobre_p75",
  p25: "1000.0000",
  p50: "1200.0000",
  p75: "1400.0000",
  metodo: "modelo",
  confianza: "baja",
  ahorro_potencial: "3600.00",
}

const ALERTA: Alerta = {
  id: "riesgo:p2",
  tipo: "riesgo",
  severidad: "alta",
  titulo: "Puntuación baja: Datos del Norte",
  explicacion: "Su puntuación es 31.0 de 100, por debajo del umbral de 40.",
  entidad_tipo: "proveedor",
  entidad_id: "p2",
  entidad_nombre: "Datos del Norte",
  proveedor_id: "p2",
  proveedor_nombre: "Datos del Norte",
  fecha: "2026-10-12",
  ahorro_potencial: null,
  moneda: null,
}

describe("BarraPuntuacion", () => {
  it("muestra la cifra, pinta la barra según su rango y marca el historial corto", () => {
    const { container } = renderizarPagina(
      <BarraPuntuacion puntuacion={72.4} confianza="baja" umbral={40} />
    )
    expect(screen.getByText("72.4")).toBeInTheDocument()
    expect(screen.getByText("Historial corto")).toBeInTheDocument()
    const barra = container.querySelector("[data-rango]")
    expect(barra).toHaveAttribute("data-rango", "alto")
    expect(barra).toHaveStyle({ width: "72.4%" })
  })

  it("debajo del umbral la barra es de riesgo", () => {
    const { container } = renderizarPagina(
      <BarraPuntuacion puntuacion={31} confianza="normal" umbral={40} />
    )
    expect(container.querySelector("[data-rango]")).toHaveAttribute(
      "data-rango",
      "bajo"
    )
    expect(screen.queryByText("Historial corto")).not.toBeInTheDocument()
  })

  it("sin puntuación lo dice con texto", () => {
    renderizarPagina(
      <BarraPuntuacion puntuacion={null} confianza={null} umbral={40} />
    )
    expect(screen.getByText("Sin datos")).toBeInTheDocument()
  })
})

describe("Tendencia", () => {
  it.each([
    [3.2, "+3.2 puntos en 3 meses"],
    [-4.1, "-4.1 puntos en 3 meses"],
    [0, "0.0 puntos en 3 meses"],
  ])("con %s dice el cambio con su signo", (valor, texto) => {
    const { container } = renderizarPagina(<Tendencia valor={valor} />)
    expect(container).toHaveTextContent(texto)
  })

  it("sin historia suficiente lo dice al lector de pantalla", () => {
    renderizarPagina(<Tendencia valor={null} />)
    expect(screen.getByText("Sin tendencia")).toHaveClass("sr-only")
  })
})

describe("PosicionMercado", () => {
  it("dice la posición con texto y abre el detalle del mercado", async () => {
    renderizarPagina(<PosicionMercado linea={LINEA} />)

    await userEvent.click(screen.getByRole("button", { name: "Sobre P75" }))

    const detalle = await screen.findByRole("dialog", {
      name: "Nube pública frente al mercado",
    })
    expect(detalle).toHaveTextContent("$1,500.00")
    expect(detalle).toHaveTextContent("$1,400.00")
    expect(detalle).toHaveTextContent("Ahorro potencial")
    expect(detalle).toHaveTextContent("$3,600.00")
    expect(detalle).toHaveTextContent("baja confianza")
  })

  it("sin referencia lo dice con texto", () => {
    renderizarPagina(
      <PosicionMercado
        linea={{ ...LINEA, posicion: null, p25: null, p50: null, p75: null }}
      />
    )
    expect(screen.getByText("Sin referencia")).toBeInTheDocument()
  })
})

describe("ElementoAlerta", () => {
  it("muestra la severidad con texto, enlaza a su proveedor y no tiene violaciones", async () => {
    const { container } = renderizarPagina(<ElementoAlerta alerta={ALERTA} />)

    // "Severidad" es solo para lectores de pantalla; a la vista queda "Alta".
    expect(container.querySelector("[data-slot=badge]")).toHaveTextContent(
      "Severidad Alta"
    )
    expect(
      screen.getByRole("link", { name: "Puntuación baja: Datos del Norte" })
    ).toHaveAttribute("href", "/proveedores/p2")
    expect(screen.getByText(ALERTA.explicacion)).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })
})
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/inteligencia.test.ts src/componentes/IndicadoresInteligencia.test.tsx`
Expected: FAIL, porque los módulos `@/inteligencia` y `@/componentes/BarraPuntuacion` no existen.

- [ ] **Step 3: Escribir `web/src/inteligencia.ts`**

```ts
import {
  useQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import type { Categoria, Severidad, TipoAlerta } from "@/tipos"

// Tipos de services/inteligencia/src/inteligencia/api/esquemas.py: un campo nuevo va en los dos.
// Los montos y precios llegan como texto decimal; puntuaciones y percentiles, como número.

export type Confianza = "normal" | "baja"
export type Metodo = "linea_base" | "modelo"
export type ClaveComponente =
  | "sla"
  | "resolucion"
  | "incidentes"
  | "entregas"
  | "satisfaccion"

export type Alerta = {
  id: string
  tipo: TipoAlerta
  severidad: Severidad
  titulo: string
  explicacion: string
  entidad_tipo: "contrato" | "proveedor"
  entidad_id: string
  entidad_nombre: string
  proveedor_id: string
  proveedor_nombre: string
  fecha: string
  ahorro_potencial: string | null
  moneda: string | null
}
export type PaginaAlertas = { total: number; elementos: Alerta[] }

export type Destacado = {
  proveedor_id: string
  nombre: string
  puntuacion: number
}
export type Vencimiento = {
  contrato_id: string
  folio: string
  proveedor_id: string
  proveedor: string
  servicios: string[]
  fecha_fin: string
  dias: number
  monto_mensual: string
}
export type TableroDatos = {
  fecha: string
  moneda: "MXN"
  gasto_anual: string
  variacion_pct: number | null
  por_vencer: number
  en_riesgo: number
  total_proveedores: number
  ahorro_potencial: string
  gasto_por_categoria: { categoria: Categoria; monto: string }[]
  gasto_por_mes: { mes: string; monto: string }[]
  proximos_vencimientos: Vencimiento[]
  alertas_principales: Alerta[]
  mejores: Destacado[]
  peores: Destacado[]
  distribucion: { rango: string; proveedores: number }[]
}

export type ServicioPrecios = {
  codigo: string
  nombre: string
  categoria: Categoria
  unidad: string
  moneda: string
  observaciones: number
}
export type Referencia = {
  codigo: string
  moneda: string
  unidad: string
  cantidad: string
  plazo: number
  fecha: string
  p25: string
  p50: string
  p75: string
  metodo: Metodo
  version: number | null
  confianza: Confianza
  observaciones: number
}
export type HistorialPrecios = {
  codigo: string
  moneda: string
  cantidad: string
  puntos: {
    fecha: string
    precio: string
    cantidad: string
    folio: string
    proveedor: string
  }[]
  bandas: { mes: string; p25: string; p50: string; p75: string }[]
}
export type Sobreprecio = {
  contrato_id: string
  folio: string
  proveedor_id: string
  proveedor: string
  codigo_servicio: string
  servicio: string
  moneda: string
  precio: string
  p25: string
  p50: string
  p75: string
  fecha_fin: string
  ahorro_potencial: string
  ahorro_potencial_mxn: string
}

export type ProveedorConPuntuacion = {
  id: string
  rfc: string
  nombre: string
  tamano: string
  categorias: Categoria[]
  activo: boolean
  puntuacion: number | null
  confianza: Confianza | null
  tendencia: number | null
  gasto_anual: string
  contratos_vigentes: number
  alertas: number
  en_riesgo: boolean
}
export type PaginaProveedoresConPuntuacion = {
  total: number
  elementos: ProveedorConPuntuacion[]
}
export type ComponentePuntuacion = {
  kpi: ClaveComponente
  valor: number
  mediana_categoria: number
  percentil: number
}
export type Puntuacion = {
  proveedor_id: string
  categoria: Categoria | null
  puntuacion: number | null
  sin_ajuste: number | null
  meses: number
  historial_corto: boolean
  tendencia: number | null
  componentes: ComponentePuntuacion[]
  historial: { mes: string; puntuacion: number }[]
}
export type MercadoLinea = {
  contrato_id: string
  folio: string
  codigo_servicio: string
  servicio: string
  moneda: string
  precio: string
  posicion: "bajo_p25" | "justo" | "sobre_p75" | null
  p25: string | null
  p50: string | null
  p75: string | null
  metodo: Metodo | null
  confianza: Confianza | null
  ahorro_potencial: string
}
export type FilaRanking = {
  posicion: number
  proveedor_id: string
  nombre: string
  categoria: Categoria
  puntuacion: number
  componentes: Record<ClaveComponente, number>
  meses: number
  historial_corto: boolean
  tendencia: number | null
}

export type ConfiguracionInteligencia = {
  peso_sla: number
  peso_resolucion: number
  peso_incidentes: number
  peso_entregas: number
  peso_satisfaccion: number
  umbral_riesgo: number
  inflacion_anual: string
  actualizado_en: string | null
  actualizado_por: string | null
}
export type ModeloPrecios = {
  version: number
  entrenado_en: string
  origen: "manual" | "automatico"
  actor_nombre: string
  observaciones: number
  datos_hasta: string
  mape: string
  mape_linea_base: string
  cobertura: string
  pinball: string
  promovido: boolean
}
export type RegistroModelos = {
  entrenando: boolean
  activo: number | null
  en_uso: number | null
  ultimo_error: string | null
  elementos: ModeloPrecios[]
}
export type DatosInteligencia = {
  registros: Record<string, number>
  ultimo_evento: string | null
  modelo: ModeloPrecios | null
  en_uso: number | null
  entrenando: boolean
}

type OpcionesConsulta<T> = Omit<
  UseQueryOptions<T, Error, T>,
  "queryKey" | "queryFn" | "enabled"
> & { enabled?: boolean }

/** GET a /api/inteligencia{ruta}. La clave común ["inteligencia", …] permite invalidarlas juntas. */
export function useInteligencia<T>(
  ruta: string,
  opciones: OpcionesConsulta<T> = {}
): UseQueryResult<T, Error> {
  const token = useToken()
  const queryKey: QueryKey = ["inteligencia", ruta]
  return useQuery({
    ...opciones,
    queryKey,
    queryFn: () => pedir<T>(`/inteligencia${ruta}`, token),
    enabled: Boolean(token) && (opciones.enabled ?? true),
  })
}

export const UMBRAL_POR_OMISION = 40
export const PUNTUACION_ALTA = 70

/** Umbral de "en riesgo" configurado; mientras carga, o si la consulta falla, el valor por omisión. */
export function useUmbralRiesgo(): number {
  const configuracion = useInteligencia<ConfiguracionInteligencia>(
    "/configuracion"
  )
  return configuracion.data?.umbral_riesgo ?? UMBRAL_POR_OMISION
}

export type RangoPuntuacion = "bajo" | "medio" | "alto"

/** Bajo: en riesgo (menos que el umbral). Alto: desde 70, o desde el umbral si es mayor. */
export function rangoPuntuacion(
  valor: number,
  umbral: number
): RangoPuntuacion {
  if (valor < umbral) return "bajo"
  return valor >= Math.max(PUNTUACION_ALTA, umbral) ? "alto" : "medio"
}

const UN_DECIMAL = new Intl.NumberFormat("es-MX", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const DOS_DECIMALES = new Intl.NumberFormat("es-MX", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatoPuntuacion(valor: number): string {
  return UN_DECIMAL.format(valor)
}

export function formatoPorcentaje(valor: number): string {
  return `${UN_DECIMAL.format(valor)} %`
}

/** MAPE y cobertura llegan como fracción ("0.083000"): se muestran como "8.3 %". */
export function fraccionComoPorcentaje(valor: string): string {
  return formatoPorcentaje(Number(valor) * 100)
}

export function formatoDecimal(valor: number, decimales = 2): string {
  return valor.toLocaleString("es-MX", { maximumFractionDigits: decimales })
}

/** Cifras grandes en MXN para las tarjetas: "48200000.00" → "$48.2 M MXN". */
export function montoCorto(valor: string): string {
  const numero = Number(valor)
  if (Math.abs(numero) >= 1e6)
    return `$${UN_DECIMAL.format(numero / 1e6)} M MXN`
  if (Math.abs(numero) >= 1e3)
    return `$${UN_DECIMAL.format(numero / 1e3)} mil MXN`
  return `$${DOS_DECIMALES.format(numero)} MXN`
}

const UNIDADES_EN_TEXTO: Record<string, string> = {
  usuario_mes: "usuario al mes",
  vcpu_mes: "vCPU al mes",
  gb_mes: "GB al mes",
  mes: "mes",
  hora: "hora",
  ticket: "ticket",
}

/** "usuario_mes" → "por usuario al mes", para acompañar un precio unitario. */
export function porUnidad(unidad: string): string {
  return `por ${UNIDADES_EN_TEXTO[unidad] ?? unidad}`
}

/** Los cinco indicadores de la puntuación, en el orden de la API. */
export const COMPONENTES: {
  clave: ClaveComponente
  nombre: string
  corto: string
  unidad: string
}[] = [
  { clave: "sla", nombre: "Cumplimiento de SLA", corto: "SLA", unidad: "%" },
  {
    clave: "resolucion",
    nombre: "Tiempo de resolución",
    corto: "Resolución",
    unidad: "h",
  },
  {
    clave: "incidentes",
    nombre: "Incidentes críticos",
    corto: "Incidentes",
    unidad: "al mes",
  },
  {
    clave: "entregas",
    nombre: "Entregas a tiempo",
    corto: "Entregas",
    unidad: "%",
  },
  {
    clave: "satisfaccion",
    nombre: "Satisfacción",
    corto: "Satisfacción",
    unidad: "de 5",
  },
]

/** Página donde se atiende una alerta: la del proveedor, en Contratos si es de un contrato. */
export function rutaDeAlerta(alerta: Alerta): string {
  const proveedor = `/proveedores/${encodeURIComponent(alerta.proveedor_id)}`
  return alerta.entidad_tipo === "contrato"
    ? `${proveedor}?pestana=contratos`
    : proveedor
}
```

- [ ] **Step 4: Escribir los cuatro componentes**

`web/src/componentes/BarraPuntuacion.tsx`:

```tsx
import { Badge } from "@/components/ui/badge"
import {
  formatoPuntuacion,
  rangoPuntuacion,
  type Confianza,
  type RangoPuntuacion,
} from "@/inteligencia"
import { cn } from "@/lib/utils"

const COLOR: Record<RangoPuntuacion, string> = {
  bajo: "bg-destructive",
  medio: "bg-warning",
  alto: "bg-success",
}

/** Puntuación con una barra de color por rango; la cifra es la señal, la barra la acompaña. */
export function BarraPuntuacion({
  puntuacion,
  confianza,
  umbral,
}: {
  puntuacion: number | null
  confianza: Confianza | null
  umbral: number
}) {
  if (puntuacion === null) {
    return <span className="text-sm text-muted-foreground">Sin datos</span>
  }
  const rango = rangoPuntuacion(puntuacion, umbral)
  return (
    <div className="flex min-w-28 flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium tabular-nums">
          {formatoPuntuacion(puntuacion)}
        </span>
        {confianza === "baja" && <Badge variant="warning">Historial corto</Badge>}
      </div>
      <div aria-hidden className="h-1.5 w-full rounded-full bg-muted">
        <div
          data-rango={rango}
          className={cn("h-full rounded-full", COLOR[rango])}
          style={{ width: `${puntuacion}%` }}
        />
      </div>
    </div>
  )
}
```

`web/src/componentes/Tendencia.tsx`:

```tsx
import { Minus, TrendingDown, TrendingUp } from "lucide-react"
import { formatoPuntuacion } from "@/inteligencia"
import { cn } from "@/lib/utils"

/** Cambio de la puntuación contra hace 3 meses, con icono, signo y texto para lectores. */
export function Tendencia({ valor }: { valor: number | null }) {
  if (valor === null) {
    return (
      <span className="text-muted-foreground">
        <span aria-hidden>—</span>
        <span className="sr-only">Sin tendencia</span>
      </span>
    )
  }
  const [Icono, color, signo] =
    valor > 0
      ? ([TrendingUp, "text-success", "+"] as const)
      : valor < 0
        ? ([TrendingDown, "text-destructive", ""] as const)
        : ([Minus, "text-muted-foreground", ""] as const)
  return (
    <span className={cn("inline-flex items-center gap-1 tabular-nums", color)}>
      <Icono aria-hidden className="size-4" />
      {signo}
      {formatoPuntuacion(valor)}
      <span className="sr-only"> puntos en 3 meses</span>
    </span>
  )
}
```

`web/src/componentes/PosicionMercado.tsx`:

```tsx
import { ArrowDown, Check, TriangleAlert, type LucideIcon } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import type { MercadoLinea } from "@/inteligencia"
import { cn } from "@/lib/utils"
import { formatoMoneda } from "@/tipos"

const POSICIONES: Record<
  NonNullable<MercadoLinea["posicion"]>,
  { texto: string; icono: LucideIcon; color: string }
> = {
  bajo_p25: { texto: "Bajo P25", icono: ArrowDown, color: "text-success" },
  justo: { texto: "Justo", icono: Check, color: "text-accent" },
  sobre_p75: {
    texto: "Sobre P75",
    icono: TriangleAlert,
    color: "text-destructive",
  },
}

/** Precio de una línea frente al mercado: icono y texto; el detalle se abre con clic o teclado. */
export function PosicionMercado({ linea }: { linea: MercadoLinea }) {
  if (
    linea.posicion === null ||
    linea.p25 === null ||
    linea.p50 === null ||
    linea.p75 === null
  ) {
    return <span className="text-muted-foreground">Sin referencia</span>
  }
  const { texto, icono: Icono, color } = POSICIONES[linea.posicion]
  const filas: [string, string][] = [
    ["Precio pagado", linea.precio],
    ["P25 (bajo)", linea.p25],
    ["P50 (típico)", linea.p50],
    ["P75 (alto)", linea.p75],
  ]
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-1 rounded-sm font-medium underline decoration-dotted underline-offset-4 outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
            color
          )}
        >
          <Icono aria-hidden className="size-4" />
          {texto}
        </button>
      </PopoverTrigger>
      <PopoverContent
        aria-label={`${linea.servicio} frente al mercado`}
        className="w-72 space-y-2 text-sm"
      >
        <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
          {filas.map(([nombre, valor]) => (
            <div key={nombre} className="contents">
              <dt className="text-muted-foreground">{nombre}</dt>
              <dd className="text-right tabular-nums">
                {formatoMoneda(valor, linea.moneda)}
              </dd>
            </div>
          ))}
          {Number(linea.ahorro_potencial) > 0 && (
            <div className="contents">
              <dt className="font-medium">Ahorro potencial</dt>
              <dd className="text-right font-medium tabular-nums">
                {formatoMoneda(linea.ahorro_potencial, linea.moneda)}
              </dd>
            </div>
          )}
        </dl>
        <p className="text-xs text-muted-foreground">
          {linea.metodo === "modelo"
            ? "Calculado con el modelo de precios"
            : "Calculado con la línea base"}
          {linea.confianza === "baja"
            ? "; baja confianza: hay pocos contratos comparables."
            : "."}
        </p>
      </PopoverContent>
    </Popover>
  )
}
```

`web/src/componentes/ElementoAlerta.tsx`:

```tsx
import {
  CalendarClock,
  Tags,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react"
import { Link } from "react-router"
import { Badge } from "@/components/ui/badge"
import { rutaDeAlerta, type Alerta } from "@/inteligencia"
import {
  NOMBRES_SEVERIDAD,
  NOMBRES_TIPO_ALERTA,
  formatoFecha,
  type Severidad,
  type TipoAlerta,
} from "@/tipos"

const ICONOS: Record<TipoAlerta, LucideIcon> = {
  vencimiento: CalendarClock,
  sobreprecio: Tags,
  riesgo: TriangleAlert,
}
const VARIANTES: Record<Severidad, "destructive" | "warning" | "secondary"> = {
  alta: "destructive",
  media: "warning",
  informativa: "secondary",
}

/** Una alerta: tipo con icono, severidad con texto, título enlazado, explicación y fecha. */
export function ElementoAlerta({ alerta }: { alerta: Alerta }) {
  const Icono = ICONOS[alerta.tipo]
  const fecha =
    alerta.tipo === "vencimiento"
      ? `Vence el ${formatoFecha(alerta.fecha)}`
      : `Calculada el ${formatoFecha(alerta.fecha)}`
  return (
    <article className="flex gap-3 py-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted">
        <Icono aria-hidden className="size-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={VARIANTES[alerta.severidad]}>
            <span className="sr-only">Severidad </span>
            {NOMBRES_SEVERIDAD[alerta.severidad]}
          </Badge>
          <span>
            {NOMBRES_TIPO_ALERTA[alerta.tipo]} · {alerta.proveedor_nombre} ·{" "}
            {fecha}
          </span>
        </div>
        <Link
          to={rutaDeAlerta(alerta)}
          className="block font-medium break-words text-accent hover:underline"
        >
          {alerta.titulo}
        </Link>
        <p className="text-sm break-words text-muted-foreground">
          {alerta.explicacion}
        </p>
      </div>
    </article>
  )
}
```

- [ ] **Step 5: Glosario y `enviarJson`**

En `web/src/glosario.ts`, cambie `ahorroPotencial` y `puntuacion`, y agregue las tres claves nuevas al final del objeto:

```ts
  ahorroPotencial: {
    termino: "Ahorro potencial",
    definicion:
      "Lo que ahorraría en lo que resta del contrato si pagara el precio típico del mercado (P50).",
  },
```

```ts
  puntuacion: {
    termino: "Puntuación",
    definicion:
      "Calificación de 0 a 100 del desempeño del proveedor en los últimos 12 meses, comparada con los proveedores de su categoría principal (o con todos, si su categoría tiene pocos).",
  },
```

```ts
  mape: {
    termino: "MAPE",
    definicion:
      "Error promedio del modelo al estimar el precio típico, como porcentaje del precio real: 10 % significa que se equivoca, en promedio, por una décima parte.",
  },
  percentil: {
    termino: "Percentil",
    definicion:
      "Posición de 0 a 100 frente a los proveedores con los que se compara: 80 significa que rinde mejor que el 80 % de ellos.",
  },
  lineaBase: {
    termino: "Línea base",
    definicion:
      "Precio de referencia calculado directamente con los contratos de los últimos 24 meses, sin el modelo de precios.",
  },
```

En `web/src/api.ts`, cambie la firma de `enviarJson`:

```ts
export function enviarJson(
  metodo: "POST" | "PATCH" | "PUT",
  datos?: unknown
): RequestInit {
```

- [ ] **Step 6: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/inteligencia.test.ts src/componentes/IndicadoresInteligencia.test.tsx src/componentes/Termino.test.tsx src/paginas/Ayuda.test.tsx`
Expected: PASS. `Termino.test.tsx` y `Ayuda.test.tsx` recorren el glosario y deben seguir en verde con las claves nuevas.

Run: `npm run lint && npm run build && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: sin errores.

- [ ] **Step 7: Commit**

```bash
git add web/src/inteligencia.ts web/src/inteligencia.test.ts web/src/componentes/BarraPuntuacion.tsx web/src/componentes/Tendencia.tsx web/src/componentes/PosicionMercado.tsx web/src/componentes/ElementoAlerta.tsx web/src/componentes/IndicadoresInteligencia.test.tsx web/src/glosario.ts web/src/api.ts
git commit -m "feat(web): tipos, consulta y formatos de la inteligencia, con sus indicadores compartidos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Tablero con datos reales

El Tablero deja los estados vacíos y muestra `GET /inteligencia/tablero`:

- los cuatro indicadores;
- el gasto por categoría, en barras horizontales con su cifra;
- el gasto comprometido de 24 meses, en una línea con su tabla de datos;
- los próximos vencimientos;
- las alertas principales;
- los mejores y peores proveedores, con la distribución de puntuaciones.

Se quitan `AvisoInteligencia` y la sección "Estado de los datos", que pasa al Panel en la Task 9 (spec D2). Cada sección vacía explica qué falta.

**Files:**
- Modify (reescritura): `web/src/paginas/Tablero.tsx`
- Modify (reescritura): `web/src/paginas/Tablero.test.tsx`

**Interfaces:**
- Consumes (Task 2): `useInteligencia`, `useUmbralRiesgo`, `montoCorto`, `formatoPorcentaje`, `formatoDecimal` y `TableroDatos` de `@/inteligencia`; `BarraPuntuacion` y `ElementoAlerta`.
- Consumes (existentes): `TarjetaKpi`, `Seccion`, `ContenidoConsulta`, `EstadoVacio`, `GuiaUso`, `Termino`, `ChartContainer`, `Table*`, `formatoFecha`, `formatoMoneda`, `formatoPeriodo` y `NOMBRES_CATEGORIA`.
- Produces: enlaces que las Tasks 4 y 5 deben entender: `/proveedores?orden=gasto_anual&direccion=desc`, `/proveedores?en_riesgo=true`, `/alertas?tipo=vencimiento` y `/precios?vista=sobreprecios`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Reemplace `web/src/paginas/Tablero.test.tsx` completo:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Tablero } from "@/paginas/Tablero"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ALERTA = {
  id: "riesgo:p2",
  tipo: "riesgo",
  severidad: "alta",
  titulo: "Puntuación baja: Datos del Norte",
  explicacion: "Su puntuación es 31.0 de 100, por debajo del umbral de 40.",
  entidad_tipo: "proveedor",
  entidad_id: "p2",
  entidad_nombre: "Datos del Norte",
  proveedor_id: "p2",
  proveedor_nombre: "Datos del Norte",
  fecha: "2026-10-12",
  ahorro_potencial: null,
  moneda: null,
}

const TABLERO = {
  fecha: "2026-10-12",
  moneda: "MXN",
  gasto_anual: "48200000.00",
  variacion_pct: 3.1,
  por_vencer: 12,
  en_riesgo: 4,
  total_proveedores: 60,
  ahorro_potencial: "1900000.00",
  gasto_por_categoria: [
    { categoria: "nube", monto: "30000000.00" },
    { categoria: "soporte", monto: "18200000.00" },
  ],
  gasto_por_mes: [
    { mes: "2026-09-01", monto: "3900000.00" },
    { mes: "2026-10-01", monto: "4016666.67" },
  ],
  proximos_vencimientos: [
    {
      contrato_id: "c1",
      folio: "CT-0001",
      proveedor_id: "p1",
      proveedor: "Nube Andina",
      servicios: ["Nube pública"],
      fecha_fin: "2026-10-30",
      dias: 18,
      monto_mensual: "125000.00",
    },
  ],
  alertas_principales: [ALERTA],
  mejores: [{ proveedor_id: "p1", nombre: "Nube Andina", puntuacion: 91.2 }],
  peores: [{ proveedor_id: "p2", nombre: "Datos del Norte", puntuacion: 31 }],
  distribucion: [
    { rango: "0-19", proveedores: 0 },
    { rango: "20-39", proveedores: 4 },
    { rango: "40-59", proveedores: 20 },
    { rango: "60-79", proveedores: 30 },
    { rango: "80-100", proveedores: 6 },
  ],
}

const VACIO = {
  ...TABLERO,
  gasto_anual: "0.00",
  variacion_pct: null,
  por_vencer: 0,
  en_riesgo: 0,
  total_proveedores: 0,
  ahorro_potencial: "0.00",
  gasto_por_categoria: [],
  gasto_por_mes: [{ mes: "2026-10-01", monto: "0.00" }],
  proximos_vencimientos: [],
  alertas_principales: [],
  mejores: [],
  peores: [],
  distribucion: TABLERO.distribucion.map((r) => ({ ...r, proveedores: 0 })),
}

function api(tablero: () => Response = () => respuestaJson(TABLERO)) {
  return simularApi((url) => {
    if (url === "/api/inteligencia/tablero") return tablero()
    if (url.startsWith("/api/proveedores/proveedores?"))
      return respuestaJson({ total: 60, elementos: [] })
    return new Response("", { status: 404 })
  })
}

const tarjeta = (elemento: HTMLElement) =>
  elemento.closest<HTMLElement>("[data-slot=card]")!
const seccion = (titulo: string) =>
  tarjeta(screen.getByRole("heading", { name: titulo }))

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("Tablero", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizarPagina(<Tablero />)
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("muestra la guía de uso arriba del tablero", async () => {
    api()
    renderizarPagina(<Tablero />)
    expect(
      await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    ).toBeInTheDocument()
  })

  it("saluda y muestra los cuatro indicadores con su cifra y su enlace", async () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Tablero />)

    const gasto = tarjeta(await screen.findByText("$48.2 M MXN"))
    expect(screen.getByText(/Hola, Ana\./)).toBeInTheDocument()
    expect(gasto).toHaveTextContent("+3.1 % contra hace 12 meses")
    expect(
      within(gasto).getByRole("link", { name: "Ver proveedores" })
    ).toHaveAttribute("href", "/proveedores?orden=gasto_anual&direccion=desc")
    expect(tarjeta(screen.getByText("Por vencer (90 días)"))).toHaveTextContent(
      "12"
    )
    expect(
      tarjeta(screen.getByText("Proveedores en riesgo"))
    ).toHaveTextContent("4 de 60")
    expect(
      tarjeta(screen.getByRole("button", { name: "Ahorro potencial" }))
    ).toHaveTextContent("$1.9 M MXN")
    expect(
      screen.getByRole("link", { name: "Ver vencimientos" })
    ).toHaveAttribute("href", "/alertas?tipo=vencimiento")
    expect(
      screen.getByRole("link", { name: "Ver proveedores en riesgo" })
    ).toHaveAttribute("href", "/proveedores?en_riesgo=true")
    expect(
      screen.getByRole("link", { name: "Ver sobreprecios" })
    ).toHaveAttribute("href", "/precios?vista=sobreprecios")
    // El aviso temporal y el estado de los datos ya no están en el Tablero.
    expect(screen.queryByRole("note")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Estado de los datos" })
    ).not.toBeInTheDocument()
  })

  it("muestra el gasto, los vencimientos, las alertas y los mejores y peores proveedores", async () => {
    api()
    renderizarPagina(<Tablero />)
    await screen.findByText("$48.2 M MXN")

    const categorias = seccion("Gasto por categoría")
    expect(within(categorias).getByText("Nube")).toBeInTheDocument()
    expect(within(categorias).getByText("$30.0 M MXN")).toBeInTheDocument()

    expect(
      screen.getByRole("figure", { name: /Gasto comprometido por mes/ })
    ).toBeInTheDocument()
    expect(screen.getByText("Ver los datos")).toBeInTheDocument()
    expect(screen.getByText("$4,016,666.67")).toBeInTheDocument()

    const vencimientos = seccion("Próximos vencimientos")
    expect(within(vencimientos).getByText("CT-0001")).toBeInTheDocument()
    expect(within(vencimientos).getByText("en 18 días")).toBeInTheDocument()
    expect(within(vencimientos).getByText("$125,000.00")).toBeInTheDocument()
    expect(
      within(vencimientos).getByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1?pestana=contratos")

    expect(
      screen.getByRole("link", { name: "Puntuación baja: Datos del Norte" })
    ).toHaveAttribute("href", "/proveedores/p2")

    const destacados = seccion("Mejores y peores proveedores")
    expect(
      within(destacados).getByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1")
    expect(within(destacados).getByText("91.2")).toBeInTheDocument()
    expect(within(destacados).getByText("31.0")).toBeInTheDocument()
    expect(within(destacados).getByText("20 proveedores")).toBeInTheDocument()
    expect(
      within(destacados).getByRole("button", { name: "puntuación" })
    ).toBeInTheDocument()
  })

  it("sin datos, cada sección explica qué falta", async () => {
    api(() => respuestaJson(VACIO))
    renderizarPagina(<Tablero />)

    expect(
      await screen.findByText("Sin contratos vigentes")
    ).toBeInTheDocument()
    expect(screen.getByText("Sin gasto comprometido")).toBeInTheDocument()
    expect(screen.getByText("Nada vence pronto")).toBeInTheDocument()
    expect(screen.getByText("No hay alertas activas")).toBeInTheDocument()
    expect(screen.getByText("Aún no hay puntuaciones")).toBeInTheDocument()
    expect(
      tarjeta(screen.getByText("Proveedores en riesgo"))
    ).toHaveTextContent("0 de 0")
  })

  it("si la inteligencia no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    api(() =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(TABLERO)
    )
    renderizarPagina(<Tablero />)

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByText("$48.2 M MXN")).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizarPagina(<Tablero />)
    await screen.findByText("$48.2 M MXN")
    await screen.findByRole("heading", { name: "Cómo usar PluriOne" })
    await esperarSinViolaciones(container)
  })
})
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/paginas/Tablero.test.tsx`
Expected: FAIL. La página aún muestra el aviso y "Sin datos" y no pide `/api/inteligencia/tablero`.

- [ ] **Step 3: Reescribir `web/src/paginas/Tablero.tsx`**

```tsx
import {
  BellOff,
  CalendarClock,
  ChartBar,
  ChartLine,
  ListOrdered,
  PiggyBank,
  TriangleAlert,
  Wallet,
} from "lucide-react"
import { useAuth } from "react-oidc-context"
import { Link } from "react-router"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { GuiaUso } from "@/componentes/GuiaUso"
import { Seccion } from "@/componentes/Seccion"
import { TarjetaKpi } from "@/componentes/TarjetaKpi"
import { Termino } from "@/componentes/Termino"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  formatoDecimal,
  formatoPorcentaje,
  montoCorto,
  useInteligencia,
  useUmbralRiesgo,
  type Destacado,
  type TableroDatos,
} from "@/inteligencia"
import {
  NOMBRES_CATEGORIA,
  formatoFecha,
  formatoMoneda,
  formatoPeriodo,
} from "@/tipos"

const CONFIG_MES = {
  monto: { label: "Gasto comprometido", color: "var(--chart-1)" },
} satisfies ChartConfig

function enlace(texto: string, ruta: string) {
  return (
    <Link to={ruta} className="text-sm font-medium text-accent hover:underline">
      {texto}
    </Link>
  )
}

function cuando(dias: number): string {
  if (dias === 0) return "hoy"
  return dias === 1 ? "mañana" : `en ${dias} días`
}

export function Tablero() {
  const auth = useAuth()
  const nombre =
    auth.user?.profile.given_name ?? auth.user?.profile.preferred_username
  const tablero = useInteligencia<TableroDatos>("/tablero")
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Tablero"
        descripcion={`${nombre ? `Hola, ${nombre}. ` : ""}Esto es lo que gasta en servicios de TI y lo que conviene atender.`}
      />
      <GuiaUso />
      <ContenidoConsulta consulta={tablero}>
        {(datos) => <Contenido datos={datos} />}
      </ContenidoConsulta>
    </section>
  )
}

function Contenido({ datos }: { datos: TableroDatos }) {
  const umbral = useUmbralRiesgo()
  const variacion = datos.variacion_pct
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <TarjetaKpi
          titulo="Gasto anual contratado"
          valor={montoCorto(datos.gasto_anual)}
          detalle="Contratos vigentes, al tipo de cambio más reciente."
          variacion={
            variacion === null
              ? undefined
              : {
                  texto: `${variacion > 0 ? "+" : ""}${formatoPorcentaje(variacion)} contra hace 12 meses`,
                  direccion: variacion < 0 ? "baja" : "sube",
                }
          }
          icono={Wallet}
          enlace="/proveedores?orden=gasto_anual&direccion=desc"
          textoEnlace="Ver proveedores"
        />
        <TarjetaKpi
          titulo="Por vencer (90 días)"
          valor={datos.por_vencer.toLocaleString("es-MX")}
          detalle="Contratos vigentes que terminan en los próximos 90 días."
          icono={CalendarClock}
          enlace="/alertas?tipo=vencimiento"
          textoEnlace="Ver vencimientos"
          tono={datos.por_vencer > 0 ? "advertencia" : "exito"}
        />
        <TarjetaKpi
          titulo="Proveedores en riesgo"
          valor={`${datos.en_riesgo.toLocaleString("es-MX")} de ${datos.total_proveedores.toLocaleString("es-MX")}`}
          detalle={`Puntuación menor que ${umbral} o en caída de más de 10 puntos.`}
          icono={TriangleAlert}
          enlace="/proveedores?en_riesgo=true"
          textoEnlace="Ver proveedores en riesgo"
          tono={datos.en_riesgo > 0 ? "riesgo" : "exito"}
        />
        <TarjetaKpi
          titulo={<Termino clave="ahorroPotencial">Ahorro potencial</Termino>}
          valor={montoCorto(datos.ahorro_potencial)}
          detalle="Si pagara el precio típico en los contratos con sobreprecio."
          icono={PiggyBank}
          enlace="/precios?vista=sobreprecios"
          textoEnlace="Ver sobreprecios"
          tono="exito"
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Seccion
          titulo="Gasto por categoría"
          descripcion="Gasto anual de los contratos vigentes, en MXN."
        >
          <GastoPorCategoria filas={datos.gasto_por_categoria} />
        </Seccion>
        <Seccion
          titulo="Gasto comprometido por mes"
          descripcion="Valor mensual de los contratos vigentes en cada mes, en MXN."
        >
          <GastoPorMes meses={datos.gasto_por_mes} />
        </Seccion>
        <Seccion
          titulo="Próximos vencimientos"
          acciones={enlace(
            "Ver alertas de vencimiento",
            "/alertas?tipo=vencimiento"
          )}
        >
          <Vencimientos filas={datos.proximos_vencimientos} />
        </Seccion>
        <Seccion
          titulo="Alertas principales"
          acciones={enlace("Ver todas las alertas", "/alertas")}
        >
          {datos.alertas_principales.length === 0 ? (
            <EstadoVacio
              icono={BellOff}
              titulo="No hay alertas activas"
              descripcion={
                <>
                  Aquí verá lo más urgente: vencimientos,{" "}
                  <Termino clave="sobreprecio">sobreprecios</Termino> y
                  proveedores en riesgo.
                </>
              }
            />
          ) : (
            <div className="divide-y">
              {datos.alertas_principales.map((alerta) => (
                <ElementoAlerta key={alerta.id} alerta={alerta} />
              ))}
            </div>
          )}
        </Seccion>
      </div>
      <Seccion
        titulo="Mejores y peores proveedores"
        descripcion={
          <>
            Según su <Termino clave="puntuacion">puntuación</Termino> de 0 a
            100.
          </>
        }
        acciones={enlace("Ver ranking completo", "/ranking")}
      >
        {datos.mejores.length === 0 ? (
          <EstadoVacio
            icono={ListOrdered}
            titulo="Aún no hay puntuaciones"
            descripcion="La puntuación se calcula con el desempeño mensual de cada proveedor; aparecerá cuando se importe."
          />
        ) : (
          <div className="grid gap-6 md:grid-cols-3">
            <ListaDestacados
              titulo="Los 5 mejores"
              filas={datos.mejores}
              umbral={umbral}
            />
            <ListaDestacados
              titulo="Los 5 más bajos"
              filas={datos.peores}
              umbral={umbral}
            />
            <Distribucion filas={datos.distribucion} />
          </div>
        )}
      </Seccion>
    </>
  )
}

function GastoPorCategoria({
  filas,
}: {
  filas: TableroDatos["gasto_por_categoria"]
}) {
  if (filas.length === 0) {
    return (
      <EstadoVacio
        icono={ChartBar}
        titulo="Sin contratos vigentes"
        descripcion="Cuando haya contratos vigentes verá aquí cuánto gasta al año en cada categoría."
      />
    )
  }
  // Solo para el ancho de cada barra; la cifra que se lee es el texto de la API.
  const mayor = Math.max(...filas.map((f) => Number(f.monto)))
  return (
    <ul className="space-y-3">
      {filas.map((f) => (
        <li key={f.categoria} className="space-y-1">
          <div className="flex justify-between gap-2 text-sm">
            <span>{NOMBRES_CATEGORIA[f.categoria] ?? f.categoria}</span>
            <span className="font-medium tabular-nums">
              {montoCorto(f.monto)}
            </span>
          </div>
          <div aria-hidden className="h-2 rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-chart-1"
              style={{
                width: `${mayor > 0 ? (Number(f.monto) / mayor) * 100 : 0}%`,
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

function GastoPorMes({ meses }: { meses: TableroDatos["gasto_por_mes"] }) {
  if (meses.every((m) => Number(m.monto) === 0)) {
    return (
      <EstadoVacio
        icono={ChartLine}
        titulo="Sin gasto comprometido"
        descripcion="Aquí verá el valor mensual de los contratos de los últimos 24 meses."
      />
    )
  }
  const serie = meses.map((m) => ({
    mes: m.mes,
    monto: Number(m.monto),
    texto: m.monto,
  }))
  return (
    <div className="space-y-3">
      <figure
        aria-label={`Gasto comprometido por mes, de ${formatoPeriodo(meses[0].mes)} a ${formatoPeriodo(meses[meses.length - 1].mes)}`}
      >
        <ChartContainer config={CONFIG_MES} className="aspect-auto h-56 w-full">
          <LineChart
            accessibilityLayer
            data={serie}
            margin={{ left: 8, right: 8, top: 8 }}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="mes"
              tickFormatter={formatoPeriodo}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(valor: number) =>
                `${formatoDecimal(valor / 1e6, 1)} M`
              }
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(valor) => formatoPeriodo(String(valor))}
                  formatter={(_valor, _nombre, item) => (
                    <div className="flex flex-1 items-center justify-between gap-2 leading-none">
                      <span className="text-muted-foreground">Gasto</span>
                      <span className="font-mono font-medium text-foreground tabular-nums">
                        {formatoMoneda(String(item.payload?.texto), "MXN")}
                      </span>
                    </div>
                  )}
                />
              }
            />
            <Line
              dataKey="monto"
              type="monotone"
              stroke="var(--color-monto)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ChartContainer>
      </figure>
      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-accent">
          Ver los datos
        </summary>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Mes</TableHead>
              <TableHead className="text-right">Monto (MXN)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {meses.map((m) => (
              <TableRow key={m.mes}>
                <TableCell>{formatoPeriodo(m.mes)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoMoneda(m.monto, "MXN")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </details>
    </div>
  )
}

function Vencimientos({
  filas,
}: {
  filas: TableroDatos["proximos_vencimientos"]
}) {
  if (filas.length === 0) {
    return (
      <EstadoVacio
        icono={CalendarClock}
        titulo="Nada vence pronto"
        descripcion="Ningún contrato vigente termina en los próximos 90 días."
      />
    )
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Contrato</TableHead>
          <TableHead>Proveedor</TableHead>
          <TableHead>Vence</TableHead>
          <TableHead className="text-right">Monto mensual</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {filas.map((v) => (
          <TableRow key={v.contrato_id}>
            <TableCell>
              <div className="font-mono">{v.folio}</div>
              <div className="text-xs text-muted-foreground">
                {v.servicios.join(", ")}
              </div>
            </TableCell>
            <TableCell>
              <Link
                to={`/proveedores/${encodeURIComponent(v.proveedor_id)}?pestana=contratos`}
                className="text-accent hover:underline"
              >
                {v.proveedor}
              </Link>
            </TableCell>
            <TableCell>
              <div>{formatoFecha(v.fecha_fin)}</div>
              <div className="text-xs text-muted-foreground">
                {cuando(v.dias)}
              </div>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatoMoneda(v.monto_mensual, "MXN")}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function ListaDestacados({
  titulo,
  filas,
  umbral,
}: {
  titulo: string
  filas: Destacado[]
  umbral: number
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{titulo}</h3>
      <ol className="space-y-3">
        {filas.map((d) => (
          <li key={d.proveedor_id} className="space-y-1">
            <Link
              to={`/proveedores/${encodeURIComponent(d.proveedor_id)}`}
              className="text-sm text-accent hover:underline"
            >
              {d.nombre}
            </Link>
            <BarraPuntuacion
              puntuacion={d.puntuacion}
              confianza={null}
              umbral={umbral}
            />
          </li>
        ))}
      </ol>
    </div>
  )
}

function Distribucion({ filas }: { filas: TableroDatos["distribucion"] }) {
  const mayor = Math.max(1, ...filas.map((f) => f.proveedores))
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Proveedores por rango de puntuación</h3>
      <ul className="space-y-2">
        {filas.map((f) => (
          <li key={f.rango} className="space-y-1">
            <div className="flex justify-between gap-2 text-sm">
              <span>{f.rango.replace("-", "–")}</span>
              <span className="tabular-nums">
                {f.proveedores.toLocaleString("es-MX")}{" "}
                {f.proveedores === 1 ? "proveedor" : "proveedores"}
              </span>
            </div>
            <div aria-hidden className="h-1.5 rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-chart-1"
                style={{ width: `${(f.proveedores / mayor) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

`AvisoInteligencia` todavía lo usan otras páginas; se borra en la Task 9.

- [ ] **Step 4: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/paginas/Tablero.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/paginas/Tablero.tsx web/src/paginas/Tablero.test.tsx
git commit -m "feat(web): el Tablero muestra el gasto, los vencimientos, las alertas y las puntuaciones reales" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Alertas, campana y paginación accesible

**Página Alertas.** Muestra `GET /inteligencia/alertas`.
- Filtra por tipo, severidad y proveedor, con los filtros en la URL.
- Pagina de 25 en 25 y ofrece volver a la primera página si la de la URL ya no existe.
- Hay un solo "Quitar filtros", junto a los filtros. Al usarlo, el foco pasa al filtro de tipo (pendiente del plan 2).

**Campana de la barra superior.**
- Muestra cuántas alertas hay ("99+" desde 100) y las 5 principales.
- Se renueva cada minuto.
- Si el servicio falla, lo dice en su menú.
- Sus textos de estado usan `DropdownMenuLabel`, no un `<p>` suelto dentro de `role="menu"` (pendiente del Plan A).

**Paginación.** `Paginacion` usa `aria-disabled` en lugar de `disabled`, para que el foco no se pierda en la primera o la última página (pendiente del plan 2).

**Files:**
- Modify (reescritura): `web/src/paginas/Alertas.tsx`
- Modify (reescritura): `web/src/paginas/Alertas.test.tsx`
- Modify: `web/src/componentes/BarraSuperior.tsx` (`MenuAlertas`)
- Modify: `web/src/componentes/Layout.test.tsx` (consultas y campana)
- Modify: `web/src/componentes/Paginacion.tsx`
- Create: `web/src/componentes/Paginacion.test.tsx`
- Modify: `web/src/paginas/Proveedores.test.tsx:159` (la aserción de `Anterior`)

**Interfaces:**
- Consumes (Task 2): `useInteligencia`, `rutaDeAlerta`, `PaginaAlertas` y `ElementoAlerta`.
- Produces:
  - URL de Alertas: `?tipo=&severidad=&proveedor=<uuid>&pagina=`. La Task 5 enlaza `/alertas?proveedor=<id>` y la Task 6, la misma ruta.
  - La campana pide exactamente `/api/inteligencia/alertas?limite=5`.
  - `Paginacion` conserva sus props; solo cambia `disabled` por `aria-disabled` con una guarda.

- [ ] **Step 1: Escribir las pruebas que fallan**

Cree `web/src/componentes/Paginacion.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Paginacion } from "@/componentes/Paginacion"

afterEach(cleanup)

describe("Paginacion", () => {
  it("en la primera página, Anterior sigue enfocable pero no cambia de página", async () => {
    const alCambiar = vi.fn()
    render(
      <Paginacion
        pagina={1}
        total={60}
        porPagina={25}
        nombre="alertas"
        alCambiar={alCambiar}
      />
    )
    const anterior = screen.getByRole("button", { name: "Anterior" })
    expect(anterior).toHaveAttribute("aria-disabled", "true")
    expect(anterior).toBeEnabled()

    anterior.focus()
    await userEvent.keyboard("{Enter}")
    expect(alCambiar).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))
    expect(alCambiar).toHaveBeenCalledWith(2)
  })

  it("en la última página, Siguiente conserva el foco y no avanza", async () => {
    const alCambiar = vi.fn()
    render(
      <Paginacion
        pagina={3}
        total={60}
        porPagina={25}
        nombre="alertas"
        alCambiar={alCambiar}
      />
    )
    const siguiente = screen.getByRole("button", { name: "Siguiente" })
    expect(siguiente).toHaveAttribute("aria-disabled", "true")

    siguiente.focus()
    await userEvent.keyboard("{Enter}")
    expect(alCambiar).not.toHaveBeenCalled()
    expect(siguiente).toHaveFocus()
    expect(screen.getByText("Mostrando 51–60 de 60 alertas")).toBeInTheDocument()
  })
})
```

Reemplace `web/src/paginas/Alertas.test.tsx` completo:

```tsx
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Alertas } from "@/paginas/Alertas"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const PROVEEDOR = "0b6a3f5e-1c2d-4e5f-8a9b-0c1d2e3f4a5b"
const VENCIMIENTO = {
  id: "vencimiento:c1",
  tipo: "vencimiento",
  severidad: "alta",
  titulo: "Vence en 12 días: CT-0001",
  explicacion: "El contrato con Nube Andina (Nube pública) termina el 24/10/2026.",
  entidad_tipo: "contrato",
  entidad_id: "c1",
  entidad_nombre: "CT-0001",
  proveedor_id: PROVEEDOR,
  proveedor_nombre: "Nube Andina",
  fecha: "2026-10-24",
  ahorro_potencial: null,
  moneda: null,
}
const SOBREPRECIO = {
  ...VENCIMIENTO,
  id: "sobreprecio:c1:NUBE-01",
  tipo: "sobreprecio",
  severidad: "media",
  titulo: "Sobreprecio en CT-0001: Nube pública",
  explicacion:
    "Paga 1,500.00 MXN por mes; el mercado paga hasta 1,400.00 (P75). Pagando el precio típico (1,200.00) ahorraría 3,600.00 MXN en lo que resta del contrato.",
  fecha: "2026-10-12",
  ahorro_potencial: "3600.00",
  moneda: "MXN",
}
const PAGINA = { total: 2, elementos: [VENCIMIENTO, SOBREPRECIO] }
const VACIA = { total: 0, elementos: [] }

function api(respuesta: () => Response = () => respuestaJson(PAGINA)) {
  return simularApi((url) =>
    url.startsWith("/api/inteligencia/alertas?")
      ? respuesta()
      : new Response("", { status: 404 })
  )
}

const renderizar = (ruta = "/alertas") =>
  renderizarPagina(<Alertas />, { ruta })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Alertas", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista las alertas con su severidad, su explicación y el enlace a su proveedor", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("link", { name: "Vence en 12 días: CT-0001" })
    ).toHaveAttribute("href", `/proveedores/${PROVEEDOR}?pestana=contratos`)
    expect(screen.getByText(SOBREPRECIO.explicacion)).toBeInTheDocument()
    expect(screen.getByText("Mostrando 1–2 de 2 alertas")).toBeInTheDocument()
  })

  it("lee los filtros de la URL, los envía y los quita con un solo botón que deja el foco en Tipo", async () => {
    const simulado = api(() => respuestaJson(VACIA))
    renderizar(
      `/alertas?tipo=vencimiento&severidad=alta&proveedor=${PROVEEDOR}`
    )

    expect(
      await screen.findByText("Ninguna alerta coincide con los filtros")
    ).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent(
      "Contrato por vencer"
    )
    expect(
      screen.getByRole("combobox", { name: "Severidad" })
    ).toHaveTextContent("Alta")
    const url = urlDeLlamada(simulado)
    expect(url.searchParams.get("tipo")).toBe("vencimiento")
    expect(url.searchParams.get("severidad")).toBe("alta")
    expect(url.searchParams.get("proveedor")).toBe(PROVEEDOR)
    expect(url.searchParams.get("limite")).toBe("25")
    expect(url.searchParams.get("pagina")).toBe("1")

    const quitar = screen.getAllByRole("button", { name: "Quitar filtros" })
    expect(quitar).toHaveLength(1)
    await userEvent.click(quitar[0])

    expect(ubicacionActual()).toBe("/alertas")
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveFocus()
  })

  it("cambiar el tipo actualiza la URL y vuelve a la primera página", async () => {
    api()
    renderizar("/alertas?pagina=2")
    await userEvent.click(screen.getByRole("combobox", { name: "Tipo" }))
    await userEvent.click(
      await screen.findByRole("option", { name: "Sobreprecio" })
    )
    expect(ubicacionActual()).toBe("/alertas?tipo=sobreprecio")
  })

  it("un proveedor inválido en la URL se ignora, igual que los demás valores inválidos", async () => {
    const simulado = api()
    renderizar(
      "/alertas?tipo=inventado&severidad=x&proveedor=no-es-uuid&pagina=abc"
    )
    await screen.findByText("Mostrando 1–2 de 2 alertas")

    const url = urlDeLlamada(simulado)
    expect(url.searchParams.has("tipo")).toBe(false)
    expect(url.searchParams.has("severidad")).toBe(false)
    expect(url.searchParams.has("proveedor")).toBe(false)
    expect(url.searchParams.get("pagina")).toBe("1")
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent(
      "Todos los tipos"
    )
    expect(
      screen.queryByRole("button", { name: "Quitar filtros" })
    ).not.toBeInTheDocument()
  })

  it("pagina de 25 en 25", async () => {
    const simulado = api(() => respuestaJson({ ...PAGINA, total: 60 }))
    renderizar()
    expect(
      await screen.findByText("Mostrando 1–25 de 60 alertas")
    ).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))

    expect(ubicacionActual()).toBe("/alertas?pagina=2")
    expect(urlDeLlamada(simulado).searchParams.get("pagina")).toBe("2")
  })

  it("una página fuera de rango ofrece volver a la primera", async () => {
    api(() => respuestaJson({ total: 30, elementos: [] }))
    renderizar("/alertas?pagina=5")

    expect(
      await screen.findByText("Esta página no tiene resultados")
    ).toBeInTheDocument()
    expect(screen.getByText(/Hay 30 alertas activas/)).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("button", { name: "Ir a la primera página" })
    )
    expect(ubicacionActual()).toBe("/alertas")
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveFocus()
  })

  it("sin alertas explica qué aparecerá aquí", async () => {
    api(() => respuestaJson(VACIA))
    renderizar()
    expect(
      await screen.findByText("No hay alertas activas")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "sobreprecio" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "puntuación" })
    ).toBeInTheDocument()
  })

  it("si el servicio no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    api(() =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(PAGINA)
    )
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByText("Mostrando 1–2 de 2 alertas")
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar()
    await screen.findByText("Mostrando 1–2 de 2 alertas")
    await esperarSinViolaciones(container)
  })

  it("sugiere ver proveedores y revisar precios", async () => {
    api()
    renderizar()
    expect(
      await screen.findByRole("link", { name: /Ver proveedores/ })
    ).toHaveAttribute("href", "/proveedores")
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
  })
})
```

En `web/src/componentes/Layout.test.tsx`:

1. Agregue a las importaciones:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  esperarSinViolaciones,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"
```

   Quite la importación anterior de `esperarSinViolaciones` sola.
2. Debajo de `const signoutRedirect = …`, agregue:

```tsx
const ALERTA_CAMPANA = {
  id: "riesgo:p2",
  tipo: "riesgo",
  severidad: "alta",
  titulo: "Puntuación baja: Datos del Norte",
  explicacion: "Su puntuación es 31.0 de 100, por debajo del umbral de 40.",
  entidad_tipo: "proveedor",
  entidad_id: "p2",
  entidad_nombre: "Datos del Norte",
  proveedor_id: "p2",
  proveedor_nombre: "Datos del Norte",
  fecha: "2026-10-12",
  ahorro_potencial: null,
  moneda: null,
}
let respuestaAlertas: () => Response
```

3. Cambie `renderizar` para que tenga un cliente de consultas:

```tsx
function renderizar(ruta = "/") {
  const cliente = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <ProveedorTema>
      <QueryClientProvider client={cliente}>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="*" element={<h1>Contenido de prueba</h1>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ProveedorTema>
  )
}
```

4. En `beforeEach`, agregue:

```tsx
  respuestaAlertas = () => respuestaJson({ total: 0, elementos: [] })
  simularApi((url) =>
    url === "/api/inteligencia/alertas?limite=5"
      ? respuestaAlertas()
      : new Response("", { status: 404 })
  )
```

5. En `afterEach`, agregue `vi.unstubAllGlobals()`.
6. Reemplace la prueba `"el menú de alertas enlaza a la página de alertas"` por estas cuatro:

```tsx
  it("el menú de alertas enlaza a la página de alertas", async () => {
    renderizar()
    await userEvent.click(screen.getByRole("button", { name: "Alertas" }))

    expect(
      await screen.findByText("No hay alertas activas")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("menuitem", { name: "Ver todas las alertas" })
    ).toHaveAttribute("href", "/alertas")
  })

  it("la campana muestra cuántas alertas hay y abre las principales", async () => {
    respuestaAlertas = () =>
      respuestaJson({ total: 7, elementos: [ALERTA_CAMPANA] })
    renderizar()

    const campana = await screen.findByRole("button", {
      name: "Alertas: 7 activas",
    })
    expect(campana).toHaveTextContent("7")
    await userEvent.click(campana)

    expect(
      await screen.findByRole("menuitem", {
        name: /Puntuación baja: Datos del Norte/,
      })
    ).toHaveAttribute("href", "/proveedores/p2")
  })

  it("la campana limita el número a 99+", async () => {
    respuestaAlertas = () =>
      respuestaJson({ total: 250, elementos: [ALERTA_CAMPANA] })
    renderizar()
    expect(
      await screen.findByRole("button", { name: "Alertas: 250 activas" })
    ).toHaveTextContent("99+")
  })

  it("la campana avisa en su menú si no pudo cargar las alertas", async () => {
    respuestaAlertas = () => new Response("", { status: 502 })
    renderizar()
    await userEvent.click(screen.getByRole("button", { name: "Alertas" }))
    expect(
      await screen.findByText("No se pudieron cargar las alertas.")
    ).toBeInTheDocument()
  })
```

En `web/src/paginas/Proveedores.test.tsx`, línea 159, cambie `.toBeDisabled()` por `.toHaveAttribute("aria-disabled", "true")`.

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/componentes/Paginacion.test.tsx src/paginas/Alertas.test.tsx src/componentes/Layout.test.tsx src/paginas/Proveedores.test.tsx`
Expected: FAIL.
- Los botones de `Paginacion` usan `disabled`.
- Alertas no consulta el servicio.
- La campana no tiene conteo.
- `Proveedores.test.tsx` espera `aria-disabled`.

- [ ] **Step 3: Paginación con `aria-disabled`**

Reemplace `web/src/componentes/Paginacion.tsx` completo:

```tsx
import { ArrowLeft, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"

/**
 * "Mostrando 1–25 de 60 …" con Anterior/Siguiente. En los extremos los botones quedan marcados
 * con aria-disabled y siguen enfocables: con `disabled` el foco se perdería al llegar al final.
 */
export function Paginacion({
  pagina,
  total,
  porPagina,
  nombre,
  alCambiar,
}: {
  pagina: number
  total: number
  porPagina: number
  nombre: string
  alCambiar: (pagina: number) => void
}) {
  const paginas = Math.max(1, Math.ceil(total / porPagina))
  const desde = (pagina - 1) * porPagina + 1
  const hasta = Math.min(pagina * porPagina, total)
  const primera = pagina <= 1
  const ultima = pagina >= paginas
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
      <span aria-live="polite">
        Mostrando {desde.toLocaleString("es-MX")}–
        {hasta.toLocaleString("es-MX")} de {total.toLocaleString("es-MX")}{" "}
        {nombre}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          aria-disabled={primera}
          onClick={() => {
            if (!primera) alCambiar(pagina - 1)
          }}
        >
          <ArrowLeft aria-hidden />
          Anterior
        </Button>
        <Button
          variant="outline"
          size="sm"
          aria-disabled={ultima}
          onClick={() => {
            if (!ultima) alCambiar(pagina + 1)
          }}
        >
          Siguiente
          <ArrowRight aria-hidden />
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Reescribir `web/src/paginas/Alertas.tsx`**

```tsx
import { keepPreviousData } from "@tanstack/react-query"
import { BellOff, Building2, Tags, X } from "lucide-react"
import { useId, useRef, type Ref } from "react"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Paginacion } from "@/componentes/Paginacion"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { Termino } from "@/componentes/Termino"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useInteligencia, type PaginaAlertas } from "@/inteligencia"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import {
  NOMBRES_SEVERIDAD,
  NOMBRES_TIPO_ALERTA,
  type Severidad,
  type TipoAlerta,
} from "@/tipos"

// Radix Select no admite el valor vacío: "todas" representa "sin filtro".
const TODAS = "todas"
const TIPOS = Object.keys(NOMBRES_TIPO_ALERTA) as TipoAlerta[]
const SEVERIDADES = Object.keys(NOMBRES_SEVERIDAD) as Severidad[]
const POR_PAGINA = 25
const PAGINA_MAXIMA = 10_000 // la que acepta la API
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function Filtro({
  etiqueta,
  valor,
  opciones,
  alCambiar,
  refDisparador,
}: {
  etiqueta: string
  valor: string
  opciones: [string, string][]
  alCambiar: (valor: string) => void
  refDisparador?: Ref<HTMLButtonElement>
}) {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <span id={id} className="text-sm font-medium">
        {etiqueta}
      </span>
      <Select value={valor} onValueChange={alCambiar}>
        <SelectTrigger
          ref={refDisparador}
          aria-labelledby={id}
          className="w-56"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {opciones.map(([v, nombre]) => (
            <SelectItem key={v} value={v}>
              {nombre}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export function Alertas() {
  const [parametros, actualizar] = useParametros()
  const tipo = unoDe(parametros.get("tipo"), TIPOS)
  const severidad = unoDe(parametros.get("severidad"), SEVERIDADES)
  const crudo = parametros.get("proveedor")
  const proveedor = crudo && UUID.test(crudo) ? crudo : null
  const pagina = enteroPositivo(parametros.get("pagina"), 1, PAGINA_MAXIMA)
  const hayFiltros = Boolean(tipo || severidad || proveedor)
  const refTipo = useRef<HTMLButtonElement>(null)

  const busqueda = new URLSearchParams({
    pagina: String(pagina),
    limite: String(POR_PAGINA),
  })
  if (tipo) busqueda.set("tipo", tipo)
  if (severidad) busqueda.set("severidad", severidad)
  if (proveedor) busqueda.set("proveedor", proveedor)
  const consulta = useInteligencia<PaginaAlertas>(`/alertas?${busqueda}`, {
    placeholderData: keepPreviousData,
  })
  const nombreProveedor = consulta.data?.elementos[0]?.proveedor_nombre

  // El botón usado desaparece: el foco pasa al filtro de tipo, que sigue en pantalla.
  function quitarFiltros() {
    actualizar({ tipo: null, severidad: null, proveedor: null, pagina: null })
    refTipo.current?.focus()
  }
  function irALaPrimera() {
    actualizar({ pagina: null })
    refTipo.current?.focus()
  }

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      if (pagina > 1 && total > 0) {
        return (
          <EstadoVacio
            titulo="Esta página no tiene resultados"
            descripcion={`Hay ${total.toLocaleString("es-MX")} alertas ${
              hayFiltros ? "que coinciden con los filtros" : "activas"
            }.`}
            accion={
              <Button variant="outline" onClick={irALaPrimera}>
                Ir a la primera página
              </Button>
            }
          />
        )
      }
      if (hayFiltros) {
        return (
          <EstadoVacio
            icono={BellOff}
            titulo="Ninguna alerta coincide con los filtros"
            descripcion="Pruebe con otros filtros o use «Quitar filtros»."
          />
        )
      }
      return (
        <EstadoVacio
          icono={BellOff}
          titulo="No hay alertas activas"
          descripcion={
            <>
              Aquí aparecerán los contratos que vencen en 90, 60 y 30 días, los
              precios con <Termino clave="sobreprecio">sobreprecio</Termino> y
              los proveedores con{" "}
              <Termino clave="puntuacion">puntuación</Termino> baja o en caída.
            </>
          }
        />
      )
    }
    return (
      <div className="space-y-4">
        <div className="divide-y">
          {elementos.map((alerta) => (
            <ElementoAlerta key={alerta.id} alerta={alerta} />
          ))}
        </div>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="alertas"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Alertas"
        descripcion={
          <>
            Lo que conviene atender hoy: contratos por vencer, precios altos y
            proveedores que bajan su{" "}
            <Termino clave="desempeno">desempeño</Termino>.
          </>
        }
      />
      <div className="flex flex-wrap items-center gap-4">
        <Filtro
          etiqueta="Tipo"
          valor={tipo ?? TODAS}
          refDisparador={refTipo}
          opciones={[
            [TODAS, "Todos los tipos"],
            ...TIPOS.map((t): [string, string] => [t, NOMBRES_TIPO_ALERTA[t]]),
          ]}
          alCambiar={(v) =>
            actualizar({ tipo: v === TODAS ? null : v, pagina: null })
          }
        />
        <Filtro
          etiqueta="Severidad"
          valor={severidad ?? TODAS}
          opciones={[
            [TODAS, "Todas las severidades"],
            ...SEVERIDADES.map((s): [string, string] => [
              s,
              NOMBRES_SEVERIDAD[s],
            ]),
          ]}
          alCambiar={(v) =>
            actualizar({ severidad: v === TODAS ? null : v, pagina: null })
          }
        />
        {proveedor && (
          <Badge variant="outline">
            Proveedor: {nombreProveedor ?? "el elegido"}
          </Badge>
        )}
        {hayFiltros && (
          <Button variant="outline" onClick={quitarFiltros}>
            <X aria-hidden />
            Quitar filtros
          </Button>
        )}
      </div>
      <Seccion titulo="Alertas activas">{contenido()}</Seccion>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores",
            descripcion: "Revise quién le vende y sus contratos.",
            ruta: "/proveedores",
            icono: Building2,
          },
          {
            titulo: "Revisar precios",
            descripcion: "Compare lo que paga con el mercado.",
            ruta: "/precios",
            icono: Tags,
          },
        ]}
      />
    </section>
  )
}
```

- [ ] **Step 5: La campana con datos**

En `web/src/componentes/BarraSuperior.tsx`:

1. Agregue a las importaciones:

```tsx
import type { ReactNode } from "react"
import {
  rutaDeAlerta,
  useInteligencia,
  type PaginaAlertas,
} from "@/inteligencia"
import { NOMBRES_SEVERIDAD, NOMBRES_TIPO_ALERTA } from "@/tipos"
```

   (`Fragment` ya se importa de `react`: junte las dos importaciones en una.)
2. Reemplace `MenuAlertas` (y su comentario) por:

```tsx
/** Campana: cuántas alertas hay y las 5 principales; se renueva cada minuto. */
function MenuAlertas() {
  const alertas = useInteligencia<PaginaAlertas>("/alertas?limite=5", {
    refetchInterval: 60_000,
  })
  const total = alertas.data?.total ?? 0
  const estado = (texto: ReactNode) => (
    <DropdownMenuLabel className="flex items-center gap-2 py-3 text-sm font-normal">
      {texto}
    </DropdownMenuLabel>
  )
  let contenido: ReactNode
  if (alertas.isPending) contenido = estado("Cargando…")
  else if (alertas.isError)
    contenido = estado("No se pudieron cargar las alertas.")
  else if (alertas.data.elementos.length === 0)
    contenido = estado(
      <>
        <BellOff aria-hidden className="size-4" />
        No hay alertas activas
      </>
    )
  else
    contenido = alertas.data.elementos.map((alerta) => (
      <DropdownMenuItem key={alerta.id} asChild>
        <Link
          to={rutaDeAlerta(alerta)}
          className="flex flex-col items-start gap-0.5"
        >
          <span className="text-xs text-muted-foreground">
            Severidad {NOMBRES_SEVERIDAD[alerta.severidad].toLowerCase()} ·{" "}
            {NOMBRES_TIPO_ALERTA[alerta.tipo]}
          </span>
          <span className="break-words whitespace-normal">
            {alerta.titulo}
          </span>
        </Link>
      </DropdownMenuItem>
    ))
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-lg"
          className="relative"
          aria-label={
            total > 0
              ? `Alertas: ${total.toLocaleString("es-MX")} activas`
              : "Alertas"
          }
        >
          <Bell aria-hidden />
          {total > 0 && (
            <span
              aria-hidden
              className="absolute top-0.5 right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-xs leading-none font-semibold text-destructive-foreground tabular-nums"
            >
              {total > 99 ? "99+" : total}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>
          Alertas{total > 0 && ` (${total.toLocaleString("es-MX")})`}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {contenido}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/alertas">Ver todas las alertas</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

- [ ] **Step 6: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/componentes/Paginacion.test.tsx src/paginas/Alertas.test.tsx src/componentes/Layout.test.tsx src/paginas/Proveedores.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde. Si otra prueba aún usa `toBeDisabled()` con "Anterior" o "Siguiente", cámbiela a `toHaveAttribute("aria-disabled", "true")`.

- [ ] **Step 7: Commit**

```bash
git add web/src/paginas/Alertas.tsx web/src/paginas/Alertas.test.tsx web/src/componentes/BarraSuperior.tsx web/src/componentes/Layout.test.tsx web/src/componentes/Paginacion.tsx web/src/componentes/Paginacion.test.tsx web/src/paginas/Proveedores.test.tsx
git commit -m "feat(web): Alertas filtrables y paginadas, la campana con conteo y la paginación sin perder el foco" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Lista de proveedores desde la inteligencia

La lista lee `GET /inteligencia/proveedores` (spec D7), que ya tiene la puntuación, el gasto anual, los contratos vigentes y las alertas de cada proveedor.
- **Columnas nuevas:** Puntuación (barra con color por rango e indicador de historial corto), Gasto anual, Contratos vigentes y Alertas. La cifra de alertas enlaza a `/alertas?proveedor=<id>`.
- **Filtro y orden:** filtro "En riesgo" y orden por columna, con `aria-sort` en la columna ordenada.
- **Pendientes del plan 2:** queda un solo "Limpiar filtros". Después de "Ir a la primera página", el foco pasa al buscador.
- **Columna quitada:** Tamaño, que sigue en la ficha.
- **Si `inteligencia` no responde:** se muestra el error con "Reintentar" (spec §7.1).

**Files:**
- Modify (reescritura): `web/src/paginas/Proveedores.tsx`
- Modify (reescritura): `web/src/paginas/Proveedores.test.tsx`

**Interfaces:**
- Consumes (Task 2): `useInteligencia`, `useUmbralRiesgo`, `PaginaProveedoresConPuntuacion` y `BarraPuntuacion`.
- Consumes (Task 4): `Paginacion` con `aria-disabled`; la página de Alertas acepta `?proveedor=<id>`.
- Produces: la URL de la lista acepta `?q=&categoria=&estado=activos|inactivos&en_riesgo=true&orden=nombre|puntuacion|gasto_anual|contratos_vigentes|alertas&direccion=asc|desc&pagina=`. El Tablero (Task 3) ya enlaza `?orden=gasto_anual&direccion=desc` y `?en_riesgo=true`.
- La consulta al servicio usa sus nombres de parámetro: `busqueda`, `categoria`, `estado`, `en_riesgo`, `orden`, `direccion`, `pagina` y `tamano=25`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Reemplace `web/src/paginas/Proveedores.test.tsx` completo:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Proveedores } from "@/paginas/Proveedores"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const PAGINA = {
  total: 2,
  elementos: [
    {
      id: "p1",
      rfc: "AAA010101AAA",
      nombre: "Nube Andina",
      tamano: "mediana",
      categorias: ["nube"],
      activo: true,
      puntuacion: 72.4,
      confianza: "normal",
      tendencia: 3.2,
      gasto_anual: "1500000.00",
      contratos_vigentes: 4,
      alertas: 3,
      en_riesgo: false,
    },
    {
      id: "p2",
      rfc: "BBB020202BBB",
      nombre: "Consultores Bajío",
      tamano: "pequena",
      categorias: ["consultoria", "soporte"],
      activo: false,
      puntuacion: 31,
      confianza: "baja",
      tendencia: null,
      gasto_anual: "0.00",
      contratos_vigentes: 0,
      alertas: 1,
      en_riesgo: true,
    },
  ],
}
const VACIA = { total: 0, elementos: [] }

function apiDeProveedores(pagina: object = PAGINA) {
  return simularApi((url) =>
    url.startsWith("/api/inteligencia/proveedores?")
      ? respuestaJson(pagina)
      : new Response("", { status: 404 })
  )
}

/** La última consulta de la lista (la configuración también llama a fetch). */
function consultaDeLista(simulado: ReturnType<typeof simularApi>): URL {
  const indice = simulado.mock.calls.findLastIndex(([url]) =>
    String(url).startsWith("/api/inteligencia/proveedores?")
  )
  return urlDeLlamada(simulado, indice)
}

const renderizar = (ruta = "/proveedores") =>
  renderizarPagina(<Proveedores />, { ruta })

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Proveedores", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista los proveedores con su puntuación, gasto, contratos y alertas", async () => {
    apiDeProveedores()
    renderizar()

    const tabla = await screen.findByRole("table")
    expect(
      within(tabla).getByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1")
    expect(within(tabla).getByText("AAA010101AAA")).toBeInTheDocument()
    expect(within(tabla).getByText("Consultoría")).toBeInTheDocument()
    expect(within(tabla).getByText("72.4")).toBeInTheDocument()
    expect(within(tabla).getByText("Historial corto")).toBeInTheDocument()
    expect(within(tabla).getByText("$1,500,000.00")).toBeInTheDocument()
    expect(
      within(tabla).getByRole("link", { name: "3 alertas de Nube Andina" })
    ).toHaveAttribute("href", "/alertas?proveedor=p1")
    expect(
      within(tabla).getByRole("link", { name: "1 alerta de Consultores Bajío" })
    ).toBeInTheDocument()
    expect(within(tabla).getByText("En riesgo")).toBeInTheDocument()
    expect(within(tabla).getByText("Inactivo")).toBeInTheDocument()
    expect(
      screen.getByText("Mostrando 1–2 de 2 proveedores")
    ).toBeInTheDocument()
  })

  it("filtra por categoría, estado y riesgo, y cada filtro vuelve a la primera página", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=3")
    await screen.findByRole("table")
    expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("3")

    await userEvent.click(screen.getByRole("button", { name: "Nube" }))
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("categoria")).toBe(
        "nube"
      )
    )
    expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("1")
    expect(ubicacionActual()).toBe("/proveedores?categoria=nube")

    await userEvent.click(screen.getByRole("button", { name: "Inactivos" }))
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("estado")).toBe(
        "inactivos"
      )
    )

    const riesgo = screen.getByRole("button", { name: "En riesgo" })
    await userEvent.click(riesgo)
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("en_riesgo")).toBe(
        "true"
      )
    )
    expect(riesgo).toHaveAttribute("aria-pressed", "true")
    expect(ubicacionActual()).toBe(
      "/proveedores?categoria=nube&estado=inactivos&en_riesgo=true"
    )
  })

  it("ordena por columna: las cifras primero de mayor a menor y luego al revés", async () => {
    const simulado = apiDeProveedores()
    renderizar()
    await screen.findByRole("table")
    expect(consultaDeLista(simulado).searchParams.get("orden")).toBe("nombre")
    expect(consultaDeLista(simulado).searchParams.get("direccion")).toBe("asc")

    await userEvent.click(
      screen.getByRole("button", { name: "Ordenar por Puntuación" })
    )
    expect(ubicacionActual()).toBe("/proveedores?orden=puntuacion")
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("direccion")).toBe(
        "desc"
      )
    )
    expect(
      screen.getByRole("columnheader", { name: /Puntuación/ })
    ).toHaveAttribute("aria-sort", "descending")

    await userEvent.click(
      screen.getByRole("button", { name: "Ordenar por Puntuación" })
    )
    expect(ubicacionActual()).toBe(
      "/proveedores?orden=puntuacion&direccion=asc"
    )
    expect(
      screen.getByRole("columnheader", { name: /Puntuación/ })
    ).toHaveAttribute("aria-sort", "ascending")

    await userEvent.click(
      screen.getByRole("button", { name: "Ordenar por Proveedor" })
    )
    expect(ubicacionActual()).toBe("/proveedores")
  })

  it("busca por nombre o RFC", async () => {
    const simulado = apiDeProveedores()
    renderizar()
    await screen.findByRole("table")

    await userEvent.type(
      screen.getByLabelText("Buscar por nombre o RFC"),
      "  andina "
    )
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }))

    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("busqueda")).toBe(
        "andina"
      )
    )
    expect(ubicacionActual()).toBe("/proveedores?q=andina")
  })

  it("el buscador conserva el foco tras pulsar Enter y se vacía con Limpiar filtros", async () => {
    apiDeProveedores()
    renderizar()
    await screen.findByRole("table")
    const campo = screen.getByLabelText("Buscar por nombre o RFC")

    await userEvent.type(campo, "andina{Enter}")

    await waitFor(() => expect(ubicacionActual()).toBe("/proveedores?q=andina"))
    expect(campo).toHaveFocus()
    expect(campo).toHaveValue("andina")

    await userEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }))

    await waitFor(() => expect(ubicacionActual()).toBe("/proveedores"))
    expect(campo).toHaveValue("")
    expect(campo).toHaveFocus()
  })

  it("pagina con Siguiente", async () => {
    const simulado = apiDeProveedores({ ...PAGINA, total: 60 })
    renderizar()
    expect(
      await screen.findByText("Mostrando 1–25 de 60 proveedores")
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Anterior" })).toHaveAttribute(
      "aria-disabled",
      "true"
    )

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))

    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("2")
    )
    expect(ubicacionActual()).toBe("/proveedores?pagina=2")
  })

  it("ignora parámetros inválidos de la URL", async () => {
    const simulado = apiDeProveedores()
    renderizar(
      "/proveedores?pagina=abc&categoria=hackeo&estado=quiza&en_riesgo=tal&orden=hackeo&direccion=x"
    )
    await screen.findByRole("table")

    const url = consultaDeLista(simulado)
    expect(url.searchParams.get("pagina")).toBe("1")
    expect(url.searchParams.get("orden")).toBe("nombre")
    expect(url.searchParams.get("direccion")).toBe("asc")
    expect(url.searchParams.has("categoria")).toBe(false)
    expect(url.searchParams.has("estado")).toBe(false)
    expect(url.searchParams.has("en_riesgo")).toBe(false)
  })

  it("limita la página al máximo que acepta la API", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=999999999")
    await waitFor(() =>
      expect(consultaDeLista(simulado).searchParams.get("pagina")).toBe("1000")
    )
  })

  it("sin proveedores invita al administrador a importar", async () => {
    sesionDePrueba.roles = ["admin"]
    apiDeProveedores(VACIA)
    renderizar()

    expect(
      await screen.findByText("Aún no hay proveedores")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("sin proveedores, un comprador recibe la indicación sin enlace de importación", async () => {
    apiDeProveedores(VACIA)
    renderizar()

    expect(
      await screen.findByText(
        "Pida a un administrador que importe el catálogo del ERP."
      )
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("link", { name: "Ir a Importación" })
    ).not.toBeInTheDocument()
  })

  it("sin resultados con filtros hay un solo Limpiar filtros, que deja el foco en el buscador", async () => {
    apiDeProveedores(VACIA)
    renderizar("/proveedores?q=zzz&categoria=nube")

    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
    const botones = screen.getAllByRole("button", { name: "Limpiar filtros" })
    expect(botones).toHaveLength(1)
    await userEvent.click(botones[0])
    expect(ubicacionActual()).toBe("/proveedores")
    expect(screen.getByLabelText("Buscar por nombre o RFC")).toHaveFocus()
  })

  it.each([
    [
      "con filtros",
      "/proveedores?categoria=nube&pagina=5",
      "Hay 30 proveedores que coinciden",
      "/proveedores?categoria=nube",
    ],
    [
      "sin filtros",
      "/proveedores?pagina=5",
      "Hay 30 proveedores en total",
      "/proveedores",
    ],
  ])(
    "una página fuera de rango %s ofrece volver a la primera y deja el foco en el buscador",
    async (_caso, ruta, descripcion, destino) => {
      apiDeProveedores({ total: 30, elementos: [] })
      renderizar(ruta)

      expect(
        await screen.findByText("Esta página no tiene resultados")
      ).toBeInTheDocument()
      expect(screen.getByText(new RegExp(descripcion))).toBeInTheDocument()
      expect(screen.queryByText("Sin resultados")).not.toBeInTheDocument()

      await userEvent.click(
        screen.getByRole("button", { name: "Ir a la primera página" })
      )
      expect(ubicacionActual()).toBe(destino)
      expect(screen.getByLabelText("Buscar por nombre o RFC")).toHaveFocus()
    }
  )

  it("si la inteligencia no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    simularApi((url) =>
      url.startsWith("/api/inteligencia/proveedores?")
        ? fallar
          ? new Response("Bad Gateway", { status: 502 })
          : respuestaJson(PAGINA)
        : new Response("", { status: 404 })
    )
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible; intente más tarde."
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByRole("link", { name: "Nube Andina" })
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    apiDeProveedores()
    const { container } = renderizar()
    await screen.findByRole("table")
    await esperarSinViolaciones(container)
  })
})
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/paginas/Proveedores.test.tsx`
Expected: FAIL. La página aún consulta `/api/proveedores/proveedores` y no tiene puntuación, orden ni filtro de riesgo.

- [ ] **Step 3: Reescribir `web/src/paginas/Proveedores.tsx`**

```tsx
import { keepPreviousData } from "@tanstack/react-query"
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Search,
  TriangleAlert,
  X,
} from "lucide-react"
import { useEffect, useRef, type FormEvent, type ReactNode } from "react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Filtro } from "@/componentes/Filtro"
import { Iniciales } from "@/componentes/Iniciales"
import { Paginacion } from "@/componentes/Paginacion"
import { Termino } from "@/componentes/Termino"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  useInteligencia,
  useUmbralRiesgo,
  type PaginaProveedoresConPuntuacion,
} from "@/inteligencia"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, formatoMoneda } from "@/tipos"

const POR_PAGINA = 25
const PAGINA_MAXIMA = 1000 // la que acepta la API
const ESTADOS = ["activos", "inactivos"] as const
const ORDENES = [
  "nombre",
  "puntuacion",
  "gasto_anual",
  "contratos_vigentes",
  "alertas",
] as const
const DIRECCIONES = ["asc", "desc"] as const
type Orden = (typeof ORDENES)[number]
type Direccion = (typeof DIRECCIONES)[number]

/** El nombre va de la A a la Z; las cifras, primero de mayor a menor. */
const DIRECCION_INICIAL: Record<Orden, Direccion> = {
  nombre: "asc",
  puntuacion: "desc",
  gasto_anual: "desc",
  contratos_vigentes: "desc",
  alertas: "desc",
}

function EncabezadoOrdenable({
  columna,
  orden,
  direccion,
  alOrdenar,
  children,
  className,
}: {
  columna: Orden
  orden: Orden
  direccion: Direccion
  alOrdenar: (columna: Orden) => void
  children: ReactNode
  className?: string
}) {
  const activa = orden === columna
  const Icono = !activa
    ? ArrowUpDown
    : direccion === "asc"
      ? ArrowUp
      : ArrowDown
  return (
    <TableHead
      aria-sort={
        activa ? (direccion === "asc" ? "ascending" : "descending") : undefined
      }
      className={className}
    >
      <Button
        variant="ghost"
        size="sm"
        className="-mx-2"
        onClick={() => alOrdenar(columna)}
      >
        <span className="sr-only">Ordenar por </span>
        {children}
        <Icono aria-hidden />
      </Button>
    </TableHead>
  )
}

export function Proveedores() {
  const roles = useRoles()
  const umbral = useUmbralRiesgo()
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const categoria = unoDe(parametros.get("categoria"), CATEGORIAS)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const enRiesgo = parametros.get("en_riesgo") === "true"
  const orden: Orden = unoDe(parametros.get("orden"), ORDENES) ?? "nombre"
  const direccion: Direccion =
    unoDe(parametros.get("direccion"), DIRECCIONES) ?? DIRECCION_INICIAL[orden]
  const pagina = enteroPositivo(parametros.get("pagina"), 1, PAGINA_MAXIMA)
  const hayFiltros = Boolean(q || categoria || estado || enRiesgo)

  // El campo no es controlado ni se remonta (así conserva el foco tras Enter): cuando `q` cambia
  // por Atrás/Adelante o por "Limpiar filtros", se copia al campo si el texto escrito difiere.
  const campoBusqueda = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const campo = campoBusqueda.current
    if (campo && campo.value.trim() !== q) campo.value = q
  }, [q])

  const busqueda = new URLSearchParams({
    orden,
    direccion,
    pagina: String(pagina),
    tamano: String(POR_PAGINA),
  })
  if (q) busqueda.set("busqueda", q)
  if (categoria) busqueda.set("categoria", categoria)
  if (estado) busqueda.set("estado", estado)
  if (enRiesgo) busqueda.set("en_riesgo", "true")
  const consulta = useInteligencia<PaginaProveedoresConPuntuacion>(
    `/proveedores?${busqueda}`,
    { placeholderData: keepPreviousData }
  )

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(
      new FormData(evento.currentTarget).get("q") ?? ""
    ).trim()
    actualizar({ q: texto || null, pagina: null })
  }
  // Los botones que se usan desaparecen: el foco pasa al buscador, que sigue en pantalla.
  function limpiar() {
    actualizar({
      q: null,
      categoria: null,
      estado: null,
      en_riesgo: null,
      pagina: null,
    })
    campoBusqueda.current?.focus()
  }
  function irALaPrimera() {
    actualizar({ pagina: null })
    campoBusqueda.current?.focus()
  }
  // Los valores por omisión no se escriben en la URL.
  function ordenar(columna: Orden) {
    const nueva =
      columna === orden
        ? direccion === "asc"
          ? "desc"
          : "asc"
        : DIRECCION_INICIAL[columna]
    actualizar({
      orden: columna === "nombre" ? null : columna,
      direccion: nueva === DIRECCION_INICIAL[columna] ? null : nueva,
      pagina: null,
    })
  }
  const encabezado = (columna: Orden, texto: string, className?: string) => (
    <EncabezadoOrdenable
      columna={columna}
      orden={orden}
      direccion={direccion}
      alOrdenar={ordenar}
      className={className}
    >
      {texto}
    </EncabezadoOrdenable>
  )

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      // Primero la página fuera de rango: con filtros también puede haber coincidencias en otras páginas.
      if (pagina > 1 && total > 0) {
        return (
          <EstadoVacio
            titulo="Esta página no tiene resultados"
            descripcion={`Hay ${total.toLocaleString("es-MX")} proveedores ${
              hayFiltros
                ? "que coinciden con la búsqueda o los filtros"
                : "en total"
            }.`}
            accion={
              <Button variant="outline" onClick={irALaPrimera}>
                Ir a la primera página
              </Button>
            }
          />
        )
      }
      if (hayFiltros) {
        return (
          <EstadoVacio
            titulo="Sin resultados"
            descripcion="Ningún proveedor coincide con la búsqueda o los filtros. Pruebe con otros o use «Limpiar filtros»."
          />
        )
      }
      const esAdmin = roles.includes("admin")
      return (
        <EstadoVacio
          titulo="Aún no hay proveedores"
          descripcion={
            esAdmin
              ? "Importe el catálogo de proveedores del ERP para comenzar. Si ya lo importó, espere a que la inteligencia termine de recibir los datos."
              : "Pida a un administrador que importe el catálogo del ERP."
          }
          accion={
            esAdmin && (
              <Button asChild>
                <Link to="/importacion">Ir a Importación</Link>
              </Button>
            )
          }
        />
      )
    }

    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              {encabezado("nombre", "Proveedor")}
              <TableHead>Categorías</TableHead>
              {encabezado("puntuacion", "Puntuación")}
              {encabezado("gasto_anual", "Gasto anual", "text-right")}
              {encabezado(
                "contratos_vigentes",
                "Contratos vigentes",
                "text-right"
              )}
              {encabezado("alertas", "Alertas", "text-right")}
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Iniciales nombre={p.nombre} />
                    <div className="space-y-0.5">
                      <Link
                        to={`/proveedores/${encodeURIComponent(p.id)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {p.nombre}
                      </Link>
                      <div className="font-mono text-xs text-muted-foreground">
                        {p.rfc}
                      </div>
                      {p.en_riesgo && (
                        <Badge variant="destructive">
                          <TriangleAlert aria-hidden />
                          En riesgo
                        </Badge>
                      )}
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {p.categorias.map((c) => (
                      <Badge key={c} variant="secondary">
                        {NOMBRES_CATEGORIA[c] ?? c}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <BarraPuntuacion
                    puntuacion={p.puntuacion}
                    confianza={p.confianza}
                    umbral={umbral}
                  />
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoMoneda(p.gasto_anual, "MXN")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {p.contratos_vigentes.toLocaleString("es-MX")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {p.alertas > 0 ? (
                    <Link
                      to={`/alertas?proveedor=${encodeURIComponent(p.id)}`}
                      aria-label={`${p.alertas} ${p.alertas === 1 ? "alerta" : "alertas"} de ${p.nombre}`}
                      className="font-medium text-accent hover:underline"
                    >
                      {p.alertas.toLocaleString("es-MX")}
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">0</span>
                  )}
                </TableCell>
                <TableCell>
                  <EtiquetaEstado activo={p.activo} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="proveedores"
          alCambiar={(p) => actualizar({ pagina: String(p) })}
        />
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Proveedores"
        descripcion={
          <>
            Quién le vende servicios de TI, cuánto le paga al año y cómo rinde
            según su <Termino clave="puntuacion">puntuación</Termino>.
          </>
        }
      />
      <Card>
        <CardContent className="space-y-4">
          <form
            role="search"
            onSubmit={buscar}
            className="flex flex-wrap items-center gap-2"
          >
            <label htmlFor="busqueda" className="sr-only">
              Buscar por nombre o RFC
            </label>
            <div className="relative w-full max-w-sm">
              <Search
                aria-hidden
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                id="busqueda"
                name="q"
                ref={campoBusqueda}
                defaultValue={q}
                placeholder="Nombre o RFC"
                maxLength={100}
                className="pl-8"
              />
            </div>
            <Button type="submit">Buscar</Button>
            {hayFiltros && (
              <Button type="button" variant="ghost" onClick={limpiar}>
                <X aria-hidden />
                Limpiar filtros
              </Button>
            )}
          </form>
          <div className="flex flex-wrap items-center gap-2">
            <div
              role="group"
              aria-label="Filtrar por categoría"
              className="flex flex-wrap gap-2"
            >
              <Filtro
                activo={!categoria}
                onClick={() => actualizar({ categoria: null, pagina: null })}
              >
                Todas
              </Filtro>
              {CATEGORIAS.map((c) => (
                <Filtro
                  key={c}
                  activo={categoria === c}
                  onClick={() => actualizar({ categoria: c, pagina: null })}
                >
                  {NOMBRES_CATEGORIA[c]}
                </Filtro>
              ))}
            </div>
            <div
              role="group"
              aria-label="Filtrar por estado y riesgo"
              className="flex flex-wrap gap-2 md:ml-auto"
            >
              <Filtro
                activo={!estado}
                onClick={() => actualizar({ estado: null, pagina: null })}
              >
                Todos
              </Filtro>
              <Filtro
                activo={estado === "activos"}
                onClick={() => actualizar({ estado: "activos", pagina: null })}
              >
                Activos
              </Filtro>
              <Filtro
                activo={estado === "inactivos"}
                onClick={() =>
                  actualizar({ estado: "inactivos", pagina: null })
                }
              >
                Inactivos
              </Filtro>
              <Filtro
                activo={enRiesgo}
                onClick={() =>
                  actualizar({
                    en_riesgo: enRiesgo ? null : "true",
                    pagina: null,
                  })
                }
              >
                <TriangleAlert aria-hidden />
                En riesgo
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </section>
  )
}
```

- [ ] **Step 4: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/paginas/Proveedores.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/paginas/Proveedores.tsx web/src/paginas/Proveedores.test.tsx
git commit -m "feat(web): la lista de proveedores muestra puntuación, gasto y alertas, con orden por columna y filtro de riesgo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Ficha del proveedor: puntuación, mercado y alertas

La ficha sigue leyendo de `proveedores` el detalle, los contratos y el desempeño (spec D7). Agrega tres consultas a `inteligencia`:

- **Encabezado:** puntuación grande con su tendencia, la línea de los últimos 12 meses y las alertas activas (las 3 primeras y un enlace a todas).
- **Resumen:** cada indicador frente a la mediana de su categoría. La barra es el percentil (0–100, más es mejor) y el texto da el valor y la mediana.
- **Contratos:** una columna "Precio vs. mercado" por línea vigente, con icono y texto, y el detalle de P25/P50/P75 y el ahorro en un popover.

Si la inteligencia falla, la ficha se sigue viendo. Cada pieza que depende de ella dice que no está disponible y ofrece "Reintentar". Un 404 de la puntuación (proveedor que la copia local aún no tiene) se muestra como "Sin puntuación todavía".

Sobre el gráfico *bullet* de la spec: el percentil es lo que se compara de forma justa entre indicadores con unidades distintas (%, horas, incidentes), así que la barra lo muestra y el texto da las dos cifras. No se dibuja la mediana como marca: el grupo de comparación puede ser "todos" (categoría con menos de 20 proveedores), y una marca en 50 sugeriría algo que no siempre es cierto.

**Files:**
- Modify (reescritura): `web/src/paginas/ProveedorDetalle.tsx`
- Modify: `web/src/componentes/TablaContratos.tsx`
- Modify: `web/src/paginas/ProveedorDetalle.test.tsx`

**Interfaces:**
- Consumes (Task 2): `useInteligencia`, `Puntuacion`, `MercadoLinea`, `PaginaAlertas`, `COMPONENTES`, `formatoPuntuacion`, `formatoDecimal`, `Tendencia`, `PosicionMercado` y `ElementoAlerta`.
- Consumes (Task 1): `GET /alertas?proveedor=<id>&limite=3`.
- Produces: `TablaContratos({ contratos: Contrato[]; mercado?: MercadoLinea[] })`. Sin `mercado`, la tabla queda igual que antes.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `web/src/paginas/ProveedorDetalle.test.tsx`:

1. Agregue estas constantes debajo de `DESEMPENO`:

```tsx
const INTELIGENCIA = "/api/inteligencia/proveedores/p1"
const ALERTAS_URL = "/api/inteligencia/alertas?proveedor=p1&limite=3"

const PUNTUACION = {
  proveedor_id: "p1",
  categoria: "nube",
  puntuacion: 72.4,
  sin_ajuste: 74,
  meses: 12,
  historial_corto: false,
  tendencia: 3.2,
  componentes: [
    { kpi: "sla", valor: 99.12, mediana_categoria: 98.7, percentil: 80 },
    { kpi: "resolucion", valor: 4.5, mediana_categoria: 5.1, percentil: 65 },
    { kpi: "incidentes", valor: 1.2, mediana_categoria: 1.5, percentil: 60 },
    { kpi: "entregas", valor: 95, mediana_categoria: 92, percentil: 70 },
    { kpi: "satisfaccion", valor: 4.4, mediana_categoria: 4.1, percentil: 75 },
  ],
  historial: [
    { mes: "2025-11-01", puntuacion: 65 },
    { mes: "2026-10-01", puntuacion: 72.4 },
  ],
}

const MERCADO = [
  {
    contrato_id: "c1",
    folio: "CT-0001",
    codigo_servicio: "NUBE-01",
    servicio: "Nube pública",
    moneda: "MXN",
    precio: "1500.0000",
    posicion: "sobre_p75",
    p25: "1000.0000",
    p50: "1200.0000",
    p75: "1400.0000",
    metodo: "modelo",
    confianza: "normal",
    ahorro_potencial: "3600.00",
  },
]

const ALERTAS = {
  total: 2,
  elementos: [
    {
      id: "sobreprecio:c1:NUBE-01",
      tipo: "sobreprecio",
      severidad: "media",
      titulo: "Sobreprecio en CT-0001: Nube pública",
      explicacion:
        "Paga 1,500.00 MXN por mes; el mercado paga hasta 1,400.00 (P75).",
      entidad_tipo: "contrato",
      entidad_id: "c1",
      entidad_nombre: "CT-0001",
      proveedor_id: "p1",
      proveedor_nombre: "Proveedor Uno",
      fecha: "2026-10-12",
      ahorro_potencial: "3600.00",
      moneda: "MXN",
    },
  ],
}
```

2. Reemplace la función `api` por:

```tsx
function api(cambios: Record<string, () => Response | Promise<Response>> = {}) {
  return simularApi({
    [RUTA]: () => respuestaJson(PROVEEDOR),
    [`${RUTA}/contratos`]: () => respuestaJson([CONTRATO]),
    [`${RUTA}/desempeno?meses=24`]: () => respuestaJson(DESEMPENO),
    [`${INTELIGENCIA}/puntuacion`]: () => respuestaJson(PUNTUACION),
    [`${INTELIGENCIA}/mercado`]: () => respuestaJson(MERCADO),
    [ALERTAS_URL]: () => respuestaJson(ALERTAS),
    ...cambios,
  })
}
```

3. Agregue estas pruebas antes de `"codifica el id al construir la ruta de la API"`:

```tsx
  it("el encabezado muestra la puntuación, su tendencia y las alertas activas", async () => {
    api()
    renderizar()

    expect(await screen.findByText("72.4")).toBeInTheDocument()
    expect(screen.getByText("de 100")).toBeInTheDocument()
    expect(
      screen.getByText("puntos en 3 meses", { exact: false }).parentElement
    ).toHaveTextContent("+3.2 puntos en 3 meses")
    expect(
      screen.getByText("Últimos 2 meses: de 65.0 a 72.4")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: "Alertas activas (2)" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Sobreprecio en CT-0001: Nube pública" })
    ).toHaveAttribute("href", "/proveedores/p1?pestana=contratos")
    expect(
      screen.getByRole("link", { name: "Ver sus 2 alertas" })
    ).toHaveAttribute("href", "/alertas?proveedor=p1")
  })

  it("el resumen compara cada indicador con la mediana de su categoría", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("heading", { name: "Frente a su categoría" })
    ).toBeInTheDocument()
    const sla = screen.getByText("Percentil 80.0").closest("li")!
    expect(sla).toHaveTextContent("Cumplimiento de SLA")
    expect(sla).toHaveTextContent("99.12 %")
    expect(sla).toHaveTextContent("mediana 98.7 %")
    expect(
      screen.getByRole("button", { name: "percentil" })
    ).toBeInTheDocument()
  })

  it("la pestaña Contratos compara cada línea vigente con el mercado", async () => {
    api()
    renderizar("/proveedores/p1?pestana=contratos")

    expect(
      await screen.findByRole("button", { name: "Sobre P75" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("columnheader", { name: "Precio vs. mercado" })
    ).toBeInTheDocument()
  })

  it("la ficha se muestra aunque la inteligencia no responda", async () => {
    const caida = () => new Response("", { status: 502 })
    api({
      [`${INTELIGENCIA}/puntuacion`]: caida,
      [`${INTELIGENCIA}/mercado`]: caida,
      [ALERTAS_URL]: caida,
    })
    renderizar("/proveedores/p1?pestana=contratos")

    expect(
      await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    ).toBeInTheDocument()
    expect(await screen.findByText("No se pudo consultar.")).toBeInTheDocument()
    expect(
      screen.getByText("No se pudieron consultar sus alertas.")
    ).toBeInTheDocument()
    expect(
      screen.getByText("No se pudo comparar con el mercado.")
    ).toBeInTheDocument()
    expect(await screen.findByText("CT-0001")).toBeInTheDocument()
    expect(
      screen.queryByRole("columnheader", { name: "Precio vs. mercado" })
    ).not.toBeInTheDocument()
  })

  it("un proveedor que la inteligencia aún no conoce se ve sin puntuación", async () => {
    api({
      [`${INTELIGENCIA}/puntuacion`]: () => new Response("", { status: 404 }),
    })
    renderizar()

    expect(
      await screen.findByText("Sin puntuación todavía")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Frente a su categoría" })
    ).not.toBeInTheDocument()
  })
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/paginas/ProveedorDetalle.test.tsx`
Expected: FAIL en las cinco pruebas nuevas; las anteriores siguen en verde.

- [ ] **Step 3: Columna "Precio vs. mercado" en `TablaContratos`**

Reemplace `web/src/componentes/TablaContratos.tsx` completo:

```tsx
import { FileText } from "lucide-react"
import { EstadoVacio } from "@/componentes/Estados"
import { PosicionMercado } from "@/componentes/PosicionMercado"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { MercadoLinea } from "@/inteligencia"
import { formatoFecha, formatoMoneda, type Contrato } from "@/tipos"

/** Contratos con sus líneas; con `mercado`, cada línea vigente se compara con el mercado. */
export function TablaContratos({
  contratos,
  mercado,
}: {
  contratos: Contrato[]
  mercado?: MercadoLinea[]
}) {
  if (contratos.length === 0) {
    return (
      <EstadoVacio
        icono={FileText}
        titulo="Sin contratos registrados"
        descripcion="Este proveedor aún no tiene contratos importados."
      />
    )
  }
  const porLinea = new Map(
    mercado?.map((m) => [`${m.contrato_id}:${m.codigo_servicio}`, m])
  )
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Folio</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead>Vigencia</TableHead>
          <TableHead>Servicio</TableHead>
          <TableHead className="text-right">Cantidad</TableHead>
          <TableHead className="text-right">Precio unitario</TableHead>
          {mercado && <TableHead>Precio vs. mercado</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {contratos.flatMap((c) =>
          c.lineas.map((linea, i) => {
            const comparada = porLinea.get(`${c.id}:${linea.codigo_servicio}`)
            return (
              // El índice evita claves repetidas: la API permite el mismo servicio en varias líneas.
              <TableRow key={`${c.id}-${i}`}>
                <TableCell className="font-mono">
                  {i === 0 ? c.folio : ""}
                </TableCell>
                <TableCell>
                  {i === 0
                    ? c.tipo === "nuevo"
                      ? "Nuevo"
                      : "Renovación"
                    : ""}
                </TableCell>
                <TableCell>
                  {i === 0
                    ? `${formatoFecha(c.fecha_inicio)} – ${formatoFecha(c.fecha_fin)}`
                    : ""}
                </TableCell>
                <TableCell>{linea.nombre_servicio}</TableCell>
                <TableCell className="text-right">
                  {Number(linea.cantidad).toLocaleString("es-MX")}{" "}
                  {linea.unidad}
                </TableCell>
                <TableCell className="text-right">
                  {formatoMoneda(linea.precio_unitario, c.moneda)}
                </TableCell>
                {mercado && (
                  <TableCell>
                    {comparada ? (
                      <PosicionMercado linea={comparada} />
                    ) : (
                      <span className="text-muted-foreground">
                        <span aria-hidden>—</span>
                        <span className="sr-only">
                          Sin comparación: el contrato no está vigente
                        </span>
                      </span>
                    )}
                  </TableCell>
                )}
              </TableRow>
            )
          })
        )}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 4: Reescribir `web/src/paginas/ProveedorDetalle.tsx`**

```tsx
import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { ArrowLeft, ChartLine, FileQuestion, Tags, Trophy } from "lucide-react"
import { useId } from "react"
import { Link, useParams } from "react-router"
import { Line, LineChart } from "recharts"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { DesempenoProveedor } from "@/componentes/DesempenoProveedor"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import {
  ContenidoConsulta,
  EstadoCarga,
  EstadoError,
  EstadoVacio,
} from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Iniciales } from "@/componentes/Iniciales"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { TablaContratos } from "@/componentes/TablaContratos"
import { Tendencia } from "@/componentes/Tendencia"
import { Termino } from "@/componentes/Termino"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  COMPONENTES,
  formatoDecimal,
  formatoPuntuacion,
  useInteligencia,
  type MercadoLinea,
  type PaginaAlertas,
  type Puntuacion,
} from "@/inteligencia"
import { unoDe, useParametros } from "@/parametros"
import {
  KPIS_DESEMPENO,
  NOMBRES_CATEGORIA,
  NOMBRES_TAMANO,
  formatoKpi,
  formatoPeriodo,
  type Contrato,
  type Desempeno,
  type ProveedorDetalle as Detalle,
} from "@/tipos"

const PESTANAS = ["resumen", "contratos", "desempeno"] as const
const CONFIG_HISTORIAL = {
  puntuacion: { label: "Puntuación", color: "var(--chart-1)" },
} satisfies ChartConfig

/** Para lo que viene de la inteligencia: la ficha sigue útil aunque eso falle. */
function NoDisponible({
  texto,
  alReintentar,
}: {
  texto: string
  alReintentar: () => void
}) {
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      {texto}
      <Button
        variant="link"
        size="sm"
        className="h-auto p-0"
        onClick={alReintentar}
      >
        Reintentar
      </Button>
    </p>
  )
}

function ResumenPuntuacion({
  consulta,
}: {
  consulta: UseQueryResult<Puntuacion>
}) {
  if (consulta.isPending) return <Skeleton className="h-10 w-32" />
  if (consulta.isError) {
    if (consulta.error instanceof ErrorApi && consulta.error.estado === 404) {
      return (
        <span className="text-muted-foreground">Sin puntuación todavía</span>
      )
    }
    return (
      <NoDisponible
        texto="No se pudo consultar."
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  const p = consulta.data
  if (p.puntuacion === null) {
    return <span className="text-muted-foreground">Sin datos de desempeño</span>
  }
  const historial = p.historial
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums">
          {formatoPuntuacion(p.puntuacion)}
        </span>
        <span className="text-muted-foreground">de 100</span>
        <Tendencia valor={p.tendencia} />
      </div>
      {p.historial_corto && (
        <p className="text-xs text-warning">
          <Termino clave="historialCorto">Historial corto</Termino>
        </p>
      )}
      {historial.length > 1 && (
        <>
          <div aria-hidden className="h-10 w-36">
            <ChartContainer
              config={CONFIG_HISTORIAL}
              className="aspect-auto h-10 w-36"
            >
              <LineChart
                data={historial}
                margin={{ top: 4, right: 0, bottom: 4, left: 0 }}
              >
                <Line
                  dataKey="puntuacion"
                  type="monotone"
                  stroke="var(--color-puntuacion)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ChartContainer>
          </div>
          <p className="text-xs text-muted-foreground">
            Últimos {historial.length} meses: de{" "}
            {formatoPuntuacion(historial[0].puntuacion)} a{" "}
            {formatoPuntuacion(historial[historial.length - 1].puntuacion)}
          </p>
        </>
      )}
    </div>
  )
}

function AlertasDelProveedor({
  consulta,
  proveedorId,
}: {
  consulta: UseQueryResult<PaginaAlertas>
  proveedorId: string
}) {
  const idTitulo = useId()
  if (consulta.isPending) return null
  if (consulta.isError) {
    return (
      <NoDisponible
        texto="No se pudieron consultar sus alertas."
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  const { total, elementos } = consulta.data
  if (total === 0) {
    return (
      <p className="text-sm text-muted-foreground">Sin alertas activas.</p>
    )
  }
  return (
    <section aria-labelledby={idTitulo} className="space-y-1 border-t pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={idTitulo} className="text-base font-semibold">
          Alertas activas ({total.toLocaleString("es-MX")})
        </h2>
        <Link
          to={`/alertas?proveedor=${encodeURIComponent(proveedorId)}`}
          className="text-sm font-medium text-accent hover:underline"
        >
          Ver sus {total.toLocaleString("es-MX")}{" "}
          {total === 1 ? "alerta" : "alertas"}
        </Link>
      </div>
      <div className="divide-y">
        {elementos.map((alerta) => (
          <ElementoAlerta key={alerta.id} alerta={alerta} />
        ))}
      </div>
    </section>
  )
}

function Encabezado({
  proveedor: p,
  puntuacion,
  alertas,
}: {
  proveedor: Detalle
  puntuacion: UseQueryResult<Puntuacion>
  alertas: UseQueryResult<PaginaAlertas>
}) {
  return (
    <Card>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Iniciales nombre={p.nombre} tamano="lg" />
              <h1 className="text-2xl font-semibold tracking-tight">
                {p.nombre}
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span className="font-mono">{p.rfc}</span>
              <span aria-hidden>·</span>
              <span>{NOMBRES_TAMANO[p.tamano] ?? p.tamano}</span>
              <EtiquetaEstado activo={p.activo} />
            </div>
            <div className="flex flex-wrap gap-1">
              {p.categorias.map((c) => (
                <Badge key={c} variant="secondary">
                  {NOMBRES_CATEGORIA[c] ?? c}
                </Badge>
              ))}
            </div>
          </div>
          <dl className="grid gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Contacto</dt>
              <dd>{p.contacto_nombre}</dd>
              <dd>
                <a
                  href={`mailto:${p.contacto_email}`}
                  className="break-all text-accent hover:underline"
                >
                  {p.contacto_email}
                </a>
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Contratos vigentes</dt>
              <dd className="text-2xl font-semibold">{p.contratos_vigentes}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">
                <Termino clave="puntuacion">Puntuación</Termino>
              </dt>
              <dd>
                <ResumenPuntuacion consulta={puntuacion} />
              </dd>
            </div>
          </dl>
        </div>
        <AlertasDelProveedor consulta={alertas} proveedorId={p.id} />
      </CardContent>
    </Card>
  )
}

function FrenteASuCategoria({
  consulta,
}: {
  consulta: UseQueryResult<Puntuacion>
}) {
  // Sin datos o con error, el encabezado ya lo dice: aquí no se repite.
  if (!consulta.isSuccess || consulta.data.componentes.length === 0)
    return null
  const p = consulta.data
  const grupo = p.categoria ? NOMBRES_CATEGORIA[p.categoria] : "su categoría"
  return (
    <Seccion
      titulo="Frente a su categoría"
      descripcion={
        <>
          Promedio de los últimos 12 meses frente a la mediana de {grupo}. La
          barra es su <Termino clave="percentil">percentil</Termino>: más larga
          es mejor.
        </>
      }
    >
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {COMPONENTES.map((c) => {
          const componente = p.componentes.find((x) => x.kpi === c.clave)
          if (!componente) return null
          return (
            <li key={c.clave} className="space-y-1 rounded-lg border p-3">
              <div className="flex justify-between gap-2 text-sm">
                <span className="font-medium">{c.nombre}</span>
                <span className="text-muted-foreground tabular-nums">
                  Percentil {formatoPuntuacion(componente.percentil)}
                </span>
              </div>
              <div aria-hidden className="h-2 rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-chart-1"
                  style={{ width: `${componente.percentil}%` }}
                />
              </div>
              <p className="text-sm tabular-nums">
                {formatoKpi(formatoDecimal(componente.valor), c.unidad)}{" "}
                <span className="text-muted-foreground">
                  · mediana{" "}
                  {formatoKpi(
                    formatoDecimal(componente.mediana_categoria),
                    c.unidad
                  )}
                </span>
              </p>
            </li>
          )
        })}
      </ul>
    </Seccion>
  )
}

function UltimoMes({ consulta }: { consulta: UseQueryResult<Desempeno[]> }) {
  return (
    <ContenidoConsulta consulta={consulta}>
      {(registros) => {
        const ultimo = registros[0]
        if (!ultimo) {
          return (
            <EstadoVacio
              icono={ChartLine}
              titulo="Sin datos de desempeño"
              descripcion="Aún no se ha importado el desempeño mensual de este proveedor."
            />
          )
        }
        return (
          <Seccion
            titulo={`Desempeño de ${formatoPeriodo(ultimo.periodo)}`}
            descripcion={
              <>
                Último mes registrado del{" "}
                <Termino clave="desempeno">desempeño</Termino> del proveedor,
                incluido el cumplimiento del <Termino clave="sla">SLA</Termino>.
              </>
            }
          >
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {KPIS_DESEMPENO.map((kpi) => (
                <div key={kpi.clave} className="rounded-lg border p-3">
                  <dt className="text-sm text-muted-foreground">
                    {kpi.nombre}
                  </dt>
                  <dd className="text-xl font-semibold">
                    {formatoKpi(ultimo[kpi.clave], kpi.unidad)}
                  </dd>
                </div>
              ))}
            </dl>
          </Seccion>
        )
      }}
    </ContenidoConsulta>
  )
}

export function ProveedorDetalle() {
  const { id = "" } = useParams()
  const token = useToken()
  const [parametros, actualizar] = useParametros()
  const pestana = unoDe(parametros.get("pestana"), PESTANAS) ?? "resumen"
  const idCodificado = encodeURIComponent(id)
  const ruta = `/proveedores/proveedores/${idCodificado}`

  const detalle = useQuery({
    queryKey: ["proveedor", id],
    queryFn: () => pedir<Detalle>(ruta, token),
    enabled: Boolean(token),
  })
  const contratos = useQuery({
    queryKey: ["proveedor", id, "contratos"],
    queryFn: () => pedir<Contrato[]>(`${ruta}/contratos`, token),
    enabled: detalle.isSuccess,
  })
  const desempeno = useQuery({
    queryKey: ["proveedor", id, "desempeno"],
    queryFn: () => pedir<Desempeno[]>(`${ruta}/desempeno?meses=24`, token),
    enabled: detalle.isSuccess,
  })
  const puntuacion = useInteligencia<Puntuacion>(
    `/proveedores/${idCodificado}/puntuacion`,
    { enabled: detalle.isSuccess }
  )
  const mercado = useInteligencia<MercadoLinea[]>(
    `/proveedores/${idCodificado}/mercado`,
    { enabled: detalle.isSuccess }
  )
  const alertas = useInteligencia<PaginaAlertas>(
    `/alertas?proveedor=${idCodificado}&limite=3`,
    { enabled: detalle.isSuccess }
  )

  if (detalle.isPending) return <EstadoCarga filas={3} />
  if (detalle.isError) {
    if (detalle.error instanceof ErrorApi && detalle.error.estado === 404) {
      return (
        <EstadoVacio
          icono={FileQuestion}
          titulo="El proveedor no existe"
          descripcion="Puede que el enlace sea incorrecto o que el proveedor ya no esté en el catálogo."
          accion={
            <Button asChild variant="outline">
              <Link to="/proveedores">Volver a proveedores</Link>
            </Button>
          }
        />
      )
    }
    return (
      <EstadoError
        error={detalle.error}
        alReintentar={() => void detalle.refetch()}
      />
    )
  }

  return (
    <section className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/proveedores">
          <ArrowLeft aria-hidden />
          Proveedores
        </Link>
      </Button>
      <Encabezado
        proveedor={detalle.data}
        puntuacion={puntuacion}
        alertas={alertas}
      />
      <Tabs
        value={pestana}
        onValueChange={(valor) =>
          actualizar({ pestana: valor === "resumen" ? null : valor })
        }
      >
        <TabsList>
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="contratos">Contratos</TabsTrigger>
          <TabsTrigger value="desempeno">Desempeño</TabsTrigger>
        </TabsList>
        <TabsContent value="resumen" className="mt-4 space-y-4">
          <FrenteASuCategoria consulta={puntuacion} />
          <UltimoMes consulta={desempeno} />
        </TabsContent>
        <TabsContent value="contratos" className="mt-4">
          <Seccion
            titulo="Contratos"
            descripcion={
              <>
                Cada línea vigente frente al precio del mercado (
                <Termino clave="percentiles">P25 · P50 · P75</Termino>).
              </>
            }
          >
            <div className="space-y-3">
              {mercado.isError && (
                <NoDisponible
                  texto="No se pudo comparar con el mercado."
                  alReintentar={() => void mercado.refetch()}
                />
              )}
              <ContenidoConsulta consulta={contratos}>
                {(datos) => (
                  <TablaContratos contratos={datos} mercado={mercado.data} />
                )}
              </ContenidoConsulta>
            </div>
          </Seccion>
        </TabsContent>
        <TabsContent value="desempeno" className="mt-4">
          <Seccion
            titulo="Desempeño de los últimos 24 meses"
            descripcion={
              <>
                Cómo ha cumplido mes a mes, incluido el{" "}
                <Termino clave="sla">SLA</Termino>.
              </>
            }
          >
            <ContenidoConsulta consulta={desempeno}>
              {(registros) => <DesempenoProveedor registros={registros} />}
            </ContenidoConsulta>
          </Seccion>
        </TabsContent>
      </Tabs>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver precios de sus servicios",
            descripcion:
              "Compare lo que paga con el precio de referencia del mercado.",
            ruta: "/precios",
            icono: Tags,
          },
          {
            titulo: "Compararlo en el ranking",
            descripcion:
              "Vea cómo se ubica frente a otros proveedores de su categoría.",
            ruta: detalle.data.categorias[0]
              ? `/ranking?categoria=${detalle.data.categorias[0]}`
              : "/ranking",
            icono: Trophy,
          },
        ]}
      />
    </section>
  )
}
```

- [ ] **Step 5: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/paginas/ProveedorDetalle.test.tsx`
Expected: PASS, incluidas las tres pruebas de accesibilidad por pestaña.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 6: Commit**

```bash
git add web/src/paginas/ProveedorDetalle.tsx web/src/paginas/ProveedorDetalle.test.tsx web/src/componentes/TablaContratos.tsx
git commit -m "feat(web): la ficha del proveedor muestra su puntuación, sus alertas y cada contrato frente al mercado" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Precios: referencia, historial y sobreprecios

Precios lee el catálogo de `GET /inteligencia/precios/servicios`, que solo trae los servicios activos con su número de contratos recientes. Al elegir un servicio muestra tres secciones:

- **Precio de referencia:** P25, P50 y P75 para una cantidad y un plazo ajustables. La cantidad inicial es la mediana de sus contratos recientes y el plazo, 12 meses. Ambos quedan en la URL (`?servicio=&cantidad=&plazo=`). Dice el método (modelo de precios con su versión, o línea base), la confianza y cuántos contratos comparables hubo.
- **Historial de precios:** el precio de cada contrato (puntos) sobre la banda P25–P75 de la línea base, con la línea P50. Los datos van también en una tabla dentro de `<details>`.
- **Contratos con sobreprecio** del servicio.

La vista "Todos los sobreprecios" lista las líneas de todos los servicios, de mayor a menor ahorro en MXN, y pagina de 25 en 25 en el navegador (la API las devuelve todas).

Pendientes del Plan A a 375 px:
- La rejilla usa `minmax(0,1fr)`.
- El eco de la búsqueda usa `break-words`.
- En una sola columna, elegir un servicio lleva el foco al título de su detalle.

**Files:**
- Modify (reescritura): `web/src/paginas/Precios.tsx`
- Modify (reescritura): `web/src/paginas/Precios.test.tsx`
- Create: `web/src/componentes/ReferenciaPrecio.tsx`
- Create: `web/src/componentes/GraficaHistorial.tsx`
- Create: `web/src/componentes/TablaSobreprecios.tsx`

**Interfaces:**
- Consumes (Task 2): `useInteligencia`, `ServicioPrecios`, `Referencia`, `HistorialPrecios`, `Sobreprecio`, `porUnidad` y `formatoDecimal`.
- Consumes (existentes): `Seccion` con `refTitulo`, `Paginacion`, `ContenidoConsulta`, `EstadoVacio`, `EstadoError`, `EstadoCarga`, `Termino`, `Label`, `Input`, `Table*`, `ChartContainer`, `ChartLegend`, `ChartLegendContent`, `ErrorApi`, `enteroPositivo` y `useParametros`.
- Produces:
  - `ReferenciaPrecio({ servicio: ServicioPrecios; cantidadSugerida: string })`.
  - `GraficaHistorial({ historial: HistorialPrecios })`.
  - `TablaSobreprecios({ filas: Sobreprecio[]; conServicio?: boolean })`.
  - URL de Precios: `?servicio=&cantidad=&plazo=` y `?vista=sobreprecios&pagina=`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Reemplace `web/src/paginas/Precios.test.tsx` completo:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Precios } from "@/paginas/Precios"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"
import { normalizarTexto } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const SERVICIOS = [
  {
    codigo: "CONS-01",
    nombre: "Consultoría SAP",
    categoria: "consultoria",
    unidad: "hora",
    moneda: "MXN",
    observaciones: 37,
  },
  {
    codigo: "NUBE-01",
    nombre: "Cómputo en la nube",
    categoria: "nube",
    unidad: "mes",
    moneda: "USD",
    observaciones: 12,
  },
  {
    codigo: "NUBE-02",
    nombre: "Almacenamiento de objetos",
    categoria: "nube",
    unidad: "gb_mes",
    moneda: "USD",
    observaciones: 0,
  },
]

const REFERENCIA = {
  codigo: "CONS-01",
  moneda: "MXN",
  unidad: "hora",
  cantidad: "40",
  plazo: 12,
  fecha: "2026-10-12",
  p25: "1000.0000",
  p50: "1200.0000",
  p75: "1400.0000",
  metodo: "modelo",
  version: 3,
  confianza: "normal",
  observaciones: 37,
}

const HISTORIAL = {
  codigo: "CONS-01",
  moneda: "MXN",
  cantidad: "40",
  puntos: [
    {
      fecha: "2025-12-01",
      precio: "1100.0000",
      cantidad: "40",
      folio: "CT-0002",
      proveedor: "Consultores Bajío",
    },
    {
      fecha: "2026-03-01",
      precio: "1500.0000",
      cantidad: "40",
      folio: "CT-0001",
      proveedor: "Nube Andina",
    },
  ],
  bandas: [
    { mes: "2026-09-01", p25: "1000.0000", p50: "1200.0000", p75: "1400.0000" },
    { mes: "2026-10-01", p25: "1010.0000", p50: "1210.0000", p75: "1410.0000" },
  ],
}

const SOBREPRECIO = {
  contrato_id: "c1",
  folio: "CT-0001",
  proveedor_id: "p1",
  proveedor: "Nube Andina",
  codigo_servicio: "CONS-01",
  servicio: "Consultoría SAP",
  moneda: "MXN",
  precio: "1500.0000",
  p25: "1000.0000",
  p50: "1200.0000",
  p75: "1400.0000",
  fecha_fin: "2026-12-31",
  ahorro_potencial: "3600.00",
  ahorro_potencial_mxn: "3600.00",
}

function api({
  catalogo = () => respuestaJson(SERVICIOS),
  referencia = () => respuestaJson(REFERENCIA),
  todos = [SOBREPRECIO],
}: {
  catalogo?: () => Response
  referencia?: () => Response
  todos?: object[]
} = {}) {
  return simularApi((url) => {
    const base = "/api/inteligencia/precios"
    if (url === `${base}/servicios`) return catalogo()
    if (url.startsWith(`${base}/servicios/CONS-01/referencia?`))
      return referencia()
    if (url === `${base}/servicios/CONS-01/historial`)
      return respuestaJson(HISTORIAL)
    if (url === `${base}/sobreprecios?codigo=CONS-01`)
      return respuestaJson([SOBREPRECIO])
    if (url === `${base}/sobreprecios`) return respuestaJson(todos)
    return new Response("", { status: 404 })
  })
}

/** Parámetros de cada consulta de referencia, en orden. */
function referenciasPedidas(simulado: ReturnType<typeof simularApi>) {
  return simulado.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/referencia?"))
    .map((url) => new URL(url, "http://localhost").searchParams)
}

const renderizar = (ruta = "/precios") =>
  renderizarPagina(<Precios />, { ruta })
const lista = () => screen.getByRole("list", { name: "Servicios del catálogo" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  sesionDePrueba.roles = ["admin"]
})

describe("normalizarTexto", () => {
  it("quita acentos y mayúsculas", () => {
    expect(normalizarTexto("Consultoría ÓPTIMA")).toBe("consultoria optima")
  })
})

describe("Precios", () => {
  it("muestra un esqueleto mientras carga el catálogo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("agrupa los servicios por categoría", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("button", { name: /Consultoría SAP/ })
    ).toBeInTheDocument()
    expect(within(lista()).getByText("Consultoría")).toBeInTheDocument()
    expect(within(lista()).getByText("Nube")).toBeInTheDocument()
    expect(screen.getByText("Elija un servicio")).toBeInTheDocument()
  })

  // jsdom no pinta el foco: se revisan las clases. La lista tiene overflow-y-auto, que recorta el
  // contorno por defecto, así que el anillo va hacia adentro; outline-hidden (y no outline-none)
  // conserva un contorno transparente que el modo de alto contraste sí muestra.
  it("los botones de la lista muestran un anillo de foco que el scroll no recorta", async () => {
    api()
    renderizar()

    const boton = await screen.findByRole("button", { name: /Consultoría SAP/ })

    expect(boton).toHaveClass(
      "outline-hidden",
      "focus-visible:ring-2",
      "focus-visible:ring-inset"
    )
    expect(boton).not.toHaveClass("outline-none")
  })

  it("busca por nombre o código sin importar acentos ni mayúsculas", async () => {
    api()
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })
    const buscador = screen.getByRole("searchbox", {
      name: "Buscar servicio por nombre o código",
    })

    await userEvent.type(buscador, "CONSULTORIA")
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "nube-02")
    expect(
      within(lista()).getByRole("button", { name: /Almacenamiento de objetos/ })
    ).toBeInTheDocument()
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "zzz")
    expect(
      screen.getByText("Ningún servicio coincide con «zzz».")
    ).toHaveClass("break-words")
  })

  it("elegir un servicio lo refleja en la URL, muestra su detalle y le lleva el foco en una sola columna", async () => {
    api()
    renderizar()

    await userEvent.click(
      await screen.findByRole("button", { name: /Cómputo en la nube/ })
    )

    expect(ubicacionActual()).toBe("/precios?servicio=NUBE-01")
    expect(
      screen.getByRole("button", { name: /Cómputo en la nube/ })
    ).toHaveAttribute("aria-pressed", "true")
    const titulo = screen.getByRole("heading", {
      level: 2,
      name: "Cómputo en la nube",
    })
    // En las pruebas matchMedia nunca coincide: la página se comporta como en una pantalla angosta.
    await waitFor(() => expect(titulo).toHaveFocus())
    expect(
      screen.getByText("NUBE-01 · Nube · por mes · USD")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Ver proveedores de esta categoría/ })
    ).toHaveAttribute("href", "/proveedores?categoria=nube")
  })

  it("muestra el precio de referencia con la cantidad sugerida y lo recalcula con otra cantidad y plazo", async () => {
    const simulado = api()
    renderizar("/precios?servicio=CONS-01")

    // "$1,400.00" también aparece en la tabla de sobreprecios: se busca dentro de los tres valores.
    const valores = (await screen.findByText("Típico (P50)")).closest("dl")!
    expect(valores).toHaveTextContent("$1,000.00")
    expect(valores).toHaveTextContent("$1,200.00")
    expect(valores).toHaveTextContent("$1,400.00")
    expect(
      screen.getByText(/Calculado con el modelo de precios versión 3/)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/37 contratos comparables/)
    ).toBeInTheDocument()
    const [primera] = referenciasPedidas(simulado)
    expect(primera.get("cantidad")).toBe("40")
    expect(primera.get("plazo")).toBe("12")

    const cantidad = screen.getByLabelText("Cantidad")
    const plazo = screen.getByLabelText("Plazo (meses)")
    await userEvent.clear(cantidad)
    await userEvent.type(cantidad, "100")
    await userEvent.clear(plazo)
    await userEvent.type(plazo, "24")
    await userEvent.click(screen.getByRole("button", { name: "Calcular" }))

    expect(ubicacionActual()).toBe(
      "/precios?servicio=CONS-01&cantidad=100&plazo=24"
    )
    await waitFor(() => {
      const ultima = referenciasPedidas(simulado).at(-1)!
      expect(ultima.get("cantidad")).toBe("100")
      expect(ultima.get("plazo")).toBe("24")
    })
  })

  it("una cantidad inválida en la URL usa la sugerida", async () => {
    const simulado = api()
    renderizar("/precios?servicio=CONS-01&cantidad=-5&plazo=999")

    await screen.findByText("$1,200.00")
    const [primera] = referenciasPedidas(simulado)
    expect(primera.get("cantidad")).toBe("40")
    expect(primera.get("plazo")).toBe("120")
  })

  it("una cantidad de cero en el formulario no se envía", async () => {
    api()
    renderizar("/precios?servicio=CONS-01")
    await screen.findByText("$1,200.00")

    const cantidad = screen.getByLabelText("Cantidad")
    await userEvent.clear(cantidad)
    await userEvent.type(cantidad, "0")
    await userEvent.click(screen.getByRole("button", { name: "Calcular" }))

    expect(ubicacionActual()).toBe("/precios?servicio=CONS-01")
  })

  it("sin contratos recientes explica por qué no hay precio de referencia", async () => {
    api({
      referencia: () =>
        respuestaJson(
          {
            title: "No encontrado",
            detail: "No hay contratos de este servicio en los últimos 24 meses.",
            codigo: "sin_observaciones",
          },
          404
        ),
    })
    renderizar("/precios?servicio=CONS-01")

    expect(
      await screen.findByText("Sin contratos recientes")
    ).toBeInTheDocument()
  })

  it("muestra el historial y los contratos con sobreprecio del servicio", async () => {
    api()
    renderizar("/precios?servicio=CONS-01")

    expect(
      await screen.findByRole("figure", { name: /Precios de 2 contratos/ })
    ).toBeInTheDocument()
    expect(
      screen.getByText("Ver los precios de cada contrato")
    ).toBeInTheDocument()
    expect(screen.getByText("CT-0002")).toBeInTheDocument()

    const sobreprecios = screen
      .getByRole("heading", { name: "Contratos con sobreprecio" })
      .closest<HTMLElement>("[data-slot=card]")!
    expect(
      await within(sobreprecios).findByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1?pestana=contratos")
    expect(within(sobreprecios).getByText("$3,600.00")).toBeInTheDocument()
  })

  it("un servicio desconocido en la URL pide elegir uno", async () => {
    api()
    renderizar("/precios?servicio=NO-EXISTE")
    expect(await screen.findByText("Elija un servicio")).toBeInTheDocument()
  })

  it("la vista de todos los sobreprecios los pagina y enlaza a cada servicio", async () => {
    const treinta = Array.from({ length: 30 }, (_, i) => ({
      ...SOBREPRECIO,
      contrato_id: `c${i}`,
      folio: `CT-${String(i).padStart(4, "0")}`,
    }))
    api({ todos: treinta })
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })

    await userEvent.click(
      screen.getByRole("button", { name: "Todos los sobreprecios" })
    )

    expect(ubicacionActual()).toBe("/precios?vista=sobreprecios")
    expect(
      screen.getByRole("button", { name: "Todos los sobreprecios" })
    ).toHaveAttribute("aria-pressed", "true")
    expect(
      await screen.findByText("Mostrando 1–25 de 30 líneas con sobreprecio")
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole("link", { name: "Consultoría SAP" })[0]
    ).toHaveAttribute("href", "/precios?servicio=CONS-01")

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))
    expect(ubicacionActual()).toBe("/precios?vista=sobreprecios&pagina=2")
    expect(screen.getByText("CT-0029")).toBeInTheDocument()
  })

  it("con el catálogo vacío invita al administrador a importar", async () => {
    api({ catalogo: () => respuestaJson([]) })
    renderizar()
    expect(
      await screen.findByText("El catálogo está vacío")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("muestra el error en español y permite reintentar", async () => {
    let fallar = true
    api({
      catalogo: () =>
        fallar ? new Response("", { status: 502 }) : respuestaJson(SERVICIOS),
    })
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByRole("button", { name: /Consultoría SAP/ })
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar("/precios?servicio=CONS-01")
    await screen.findByText("$1,200.00")
    await screen.findByRole("figure", { name: /Precios de 2 contratos/ })
    await esperarSinViolaciones(container)
  })
})
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/paginas/Precios.test.tsx`
Expected: FAIL. La página consulta `/api/proveedores/servicios` y aún muestra estados vacíos.

- [ ] **Step 3: Escribir `TablaSobreprecios`**

`web/src/componentes/TablaSobreprecios.tsx`:

```tsx
import { Link } from "react-router"
import { Termino } from "@/componentes/Termino"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { Sobreprecio } from "@/inteligencia"
import { formatoFecha, formatoMoneda } from "@/tipos"

/** Líneas de contratos vigentes que pagan más que el P75, con su ahorro potencial. */
export function TablaSobreprecios({
  filas,
  conServicio = false,
}: {
  filas: Sobreprecio[]
  conServicio?: boolean
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Contrato</TableHead>
          <TableHead>Proveedor</TableHead>
          {conServicio && <TableHead>Servicio</TableHead>}
          <TableHead className="text-right">Precio pagado</TableHead>
          <TableHead className="text-right">P75 del mercado</TableHead>
          <TableHead className="text-right">
            <Termino clave="ahorroPotencial">Ahorro potencial</Termino>
          </TableHead>
          <TableHead>Vence</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {filas.map((f, i) => (
          // El índice evita claves repetidas: un contrato puede tener el mismo servicio dos veces.
          <TableRow key={`${f.contrato_id}:${f.codigo_servicio}:${i}`}>
            <TableCell className="font-mono">{f.folio}</TableCell>
            <TableCell>
              <Link
                to={`/proveedores/${encodeURIComponent(f.proveedor_id)}?pestana=contratos`}
                className="text-accent hover:underline"
              >
                {f.proveedor}
              </Link>
            </TableCell>
            {conServicio && (
              <TableCell>
                <Link
                  to={`/precios?servicio=${encodeURIComponent(f.codigo_servicio)}`}
                  className="text-accent hover:underline"
                >
                  {f.servicio}
                </Link>
              </TableCell>
            )}
            <TableCell className="text-right tabular-nums">
              {formatoMoneda(f.precio, f.moneda)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatoMoneda(f.p75, f.moneda)}
            </TableCell>
            <TableCell className="text-right font-medium tabular-nums">
              {formatoMoneda(f.ahorro_potencial, f.moneda)}
              {f.moneda !== "MXN" && (
                <div className="text-xs font-normal text-muted-foreground">
                  {formatoMoneda(f.ahorro_potencial_mxn, "MXN")} MXN
                </div>
              )}
            </TableCell>
            <TableCell>{formatoFecha(f.fecha_fin)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 4: Escribir `ReferenciaPrecio`**

`web/src/componentes/ReferenciaPrecio.tsx`:

```tsx
import { Tags } from "lucide-react"
import { useId, type FormEvent } from "react"
import { ErrorApi } from "@/api"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Termino } from "@/componentes/Termino"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  useInteligencia,
  type Referencia,
  type ServicioPrecios,
} from "@/inteligencia"
import { cn } from "@/lib/utils"
import { enteroPositivo, useParametros } from "@/parametros"
import { formatoMoneda } from "@/tipos"

const CANTIDAD_MAXIMA = 10_000_000 // las que acepta la API
const PLAZO_MAXIMO = 120

/** La cantidad de la URL si es un número mayor que 0 y no excede el máximo; si no, null. */
function cantidadValida(valor: string | null): string | null {
  const numero = Number(valor)
  return valor && Number.isFinite(numero) && numero > 0 && numero <= CANTIDAD_MAXIMA
    ? valor
    : null
}

/** P25, P50 y P75 para la cantidad y el plazo de la URL, con el formulario para cambiarlos. */
export function ReferenciaPrecio({
  servicio,
  cantidadSugerida,
}: {
  servicio: ServicioPrecios
  cantidadSugerida: string
}) {
  const [parametros, actualizar] = useParametros()
  const cantidad = cantidadValida(parametros.get("cantidad")) ?? cantidadSugerida
  const plazo = enteroPositivo(parametros.get("plazo"), 12, PLAZO_MAXIMO)
  const idCantidad = useId()
  const idPlazo = useId()
  const referencia = useInteligencia<Referencia>(
    `/precios/servicios/${encodeURIComponent(servicio.codigo)}/referencia?${new URLSearchParams(
      { cantidad, plazo: String(plazo) }
    )}`
  )

  function calcular(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const datos = new FormData(evento.currentTarget)
    // El navegador ya bloquea los valores fuera de rango; esto cubre al que no lo haga.
    const nuevaCantidad = cantidadValida(String(datos.get("cantidad")))
    if (!nuevaCantidad) return
    actualizar({
      cantidad: nuevaCantidad,
      plazo: String(
        enteroPositivo(String(datos.get("plazo")), 12, PLAZO_MAXIMO)
      ),
    })
  }

  function resultado() {
    if (referencia.isPending) return <EstadoCarga filas={2} />
    if (referencia.isError) {
      if (
        referencia.error instanceof ErrorApi &&
        referencia.error.codigo === "sin_observaciones"
      ) {
        return (
          <EstadoVacio
            icono={Tags}
            titulo="Sin contratos recientes"
            descripcion="No hay contratos de este servicio en los últimos 24 meses: no se puede calcular su precio de referencia."
          />
        )
      }
      return (
        <EstadoError
          error={referencia.error}
          alReintentar={() => void referencia.refetch()}
        />
      )
    }
    const r = referencia.data
    const valores: [string, string, string][] = [
      ["P25", "Bajo", r.p25],
      ["P50", "Típico", r.p50],
      ["P75", "Alto", r.p75],
    ]
    return (
      <div className="space-y-3">
        <dl className="grid gap-3 sm:grid-cols-3">
          {valores.map(([clave, nombre, valor]) => (
            <div
              key={clave}
              className={cn(
                "rounded-lg border p-3",
                clave === "P50" && "border-accent"
              )}
            >
              <dt className="text-sm text-muted-foreground">
                {nombre} ({clave})
              </dt>
              <dd className="text-xl font-semibold tabular-nums">
                {formatoMoneda(valor, r.moneda)}
              </dd>
            </div>
          ))}
        </dl>
        <p className="text-sm text-muted-foreground">
          {r.metodo === "modelo" ? (
            `Calculado con el modelo de precios versión ${r.version}`
          ) : (
            <>
              Calculado con la <Termino clave="lineaBase">línea base</Termino>
            </>
          )}{" "}
          · {r.observaciones.toLocaleString("es-MX")} contratos comparables de
          los últimos 24 meses
          {r.confianza === "baja" && (
            <>
              {" "}
              ·{" "}
              <span className="text-warning">
                <Termino clave="bajaConfianza">baja confianza</Termino>
              </span>
            </>
          )}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Sin `key`: remontar el formulario al calcular sacaría el foco del botón. */}
      <form
        onSubmit={calcular}
        className="flex flex-wrap items-end gap-3"
      >
        <div className="space-y-1">
          <Label htmlFor={idCantidad}>Cantidad</Label>
          <Input
            id={idCantidad}
            name="cantidad"
            type="number"
            inputMode="decimal"
            min="0.0001"
            max={CANTIDAD_MAXIMA}
            step="any"
            required
            defaultValue={cantidad}
            className="w-36"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={idPlazo}>Plazo (meses)</Label>
          <Input
            id={idPlazo}
            name="plazo"
            type="number"
            inputMode="numeric"
            min={1}
            max={PLAZO_MAXIMO}
            step={1}
            required
            defaultValue={plazo}
            className="w-28"
          />
        </div>
        <Button type="submit">Calcular</Button>
      </form>
      {resultado()}
    </div>
  )
}
```

- [ ] **Step 5: Escribir `GraficaHistorial`**

`web/src/componentes/GraficaHistorial.tsx`:

```tsx
import { ChartLine } from "lucide-react"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
} from "recharts"
import { EstadoVacio } from "@/componentes/Estados"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoDecimal, type HistorialPrecios } from "@/inteligencia"
import { formatoFecha, formatoMoneda, formatoPeriodo } from "@/tipos"

const CONFIGURACION = {
  rango: { label: "Rango típico (P25–P75)", color: "var(--chart-1)" },
  p50: { label: "Precio típico (P50)", color: "var(--chart-2)" },
  precio: { label: "Precio de cada contrato", color: "var(--chart-3)" },
} satisfies ChartConfig

/** "2026-09-01" → milisegundos a medianoche local, para un eje de tiempo. */
const tiempo = (iso: string) => new Date(`${iso}T00:00:00`).getTime()

/** Milisegundos → "AAAA-MM-01", lo que espera formatoPeriodo. */
function mesDe(milisegundos: number): string {
  const fecha = new Date(milisegundos)
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}-01`
}

/** Precio de cada contrato sobre la banda P25–P75 de la línea base y su P50, mes a mes. */
export function GraficaHistorial({
  historial,
}: {
  historial: HistorialPrecios
}) {
  if (historial.puntos.length === 0 && historial.bandas.length === 0) {
    return (
      <EstadoVacio
        icono={ChartLine}
        titulo="Sin contratos en los últimos 24 meses"
        descripcion="Cuando haya contratos de este servicio verá aquí sus precios y el rango típico del mercado."
      />
    )
  }
  const bandas = historial.bandas.map((b) => ({
    t: tiempo(b.mes),
    rango: [Number(b.p25), Number(b.p75)],
    p50: Number(b.p50),
  }))
  const puntos = historial.puntos.map((p) => ({
    t: tiempo(p.fecha),
    precio: Number(p.precio),
  }))
  return (
    <div className="space-y-3">
      <figure
        aria-label={`Precios de ${historial.puntos.length} contratos sobre el rango típico del mercado, últimos 24 meses`}
      >
        <ChartContainer config={CONFIGURACION} className="aspect-auto h-72 w-full">
          <ComposedChart data={bandas} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(t: number) => formatoPeriodo(mesDe(t))}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={64}
              tickFormatter={(valor: number) => formatoDecimal(valor)}
            />
            <ChartLegend content={<ChartLegendContent />} />
            <Area
              dataKey="rango"
              type="monotone"
              stroke="none"
              fill="var(--color-rango)"
              fillOpacity={0.2}
            />
            <Line
              dataKey="p50"
              type="monotone"
              stroke="var(--color-p50)"
              strokeWidth={2}
              dot={false}
            />
            <Scatter data={puntos} dataKey="precio" fill="var(--color-precio)" />
          </ComposedChart>
        </ChartContainer>
      </figure>
      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-accent">
          Ver los precios de cada contrato
        </summary>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Inicio</TableHead>
              <TableHead>Contrato</TableHead>
              <TableHead>Proveedor</TableHead>
              <TableHead className="text-right">Cantidad</TableHead>
              <TableHead className="text-right">Precio</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {historial.puntos.map((p, i) => (
              <TableRow key={`${p.folio}-${i}`}>
                <TableCell>{formatoFecha(p.fecha)}</TableCell>
                <TableCell className="font-mono">{p.folio}</TableCell>
                <TableCell>{p.proveedor}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {Number(p.cantidad).toLocaleString("es-MX")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoMoneda(p.precio, historial.moneda)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </details>
    </div>
  )
}
```

Recharts no dibuja en jsdom, así que la forma de la gráfica se verifica en el navegador en la Task 12. Si `Scatter` con su propio `data` no aparece sobre la banda, ponga los puntos y las bandas en un solo arreglo ordenado por `t`, con `precio`, `rango` o `p50` vacíos según el caso, y quite el `data` de `Scatter`.

- [ ] **Step 6: Reescribir `web/src/paginas/Precios.tsx`**

```tsx
import { Building2, Tags, TrendingUp } from "lucide-react"
import { useEffect, useRef, useState, type Ref } from "react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import {
  ContenidoConsulta,
  EstadoCarga,
  EstadoVacio,
} from "@/componentes/Estados"
import { GraficaHistorial } from "@/componentes/GraficaHistorial"
import { Paginacion } from "@/componentes/Paginacion"
import { ReferenciaPrecio } from "@/componentes/ReferenciaPrecio"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { TablaSobreprecios } from "@/componentes/TablaSobreprecios"
import { Termino } from "@/componentes/Termino"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  porUnidad,
  useInteligencia,
  type HistorialPrecios,
  type ServicioPrecios,
  type Sobreprecio,
} from "@/inteligencia"
import { enteroPositivo, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, normalizarTexto } from "@/tipos"

const POR_PAGINA = 25
const DOS_COLUMNAS = "(min-width: 1024px)" // el `lg` de Tailwind

function ListaServicios({
  servicios,
  seleccionado,
  alElegir,
}: {
  servicios: ServicioPrecios[]
  seleccionado: string | null
  alElegir: (codigo: string) => void
}) {
  const [busqueda, setBusqueda] = useState("")
  const termino = normalizarTexto(busqueda.trim())
  const visibles = servicios.filter(
    (s) =>
      !termino || normalizarTexto(`${s.nombre} ${s.codigo}`).includes(termino)
  )
  const grupos = CATEGORIAS.map((categoria) => ({
    categoria,
    servicios: visibles.filter((s) => s.categoria === categoria),
  })).filter((grupo) => grupo.servicios.length > 0)

  return (
    <div className="space-y-3">
      <label htmlFor="buscar-servicio" className="sr-only">
        Buscar servicio por nombre o código
      </label>
      <Input
        id="buscar-servicio"
        type="search"
        placeholder="Nombre o código"
        value={busqueda}
        onChange={(evento) => setBusqueda(evento.target.value)}
      />
      {grupos.length === 0 ? (
        <p className="px-2 py-4 text-sm break-words text-muted-foreground">
          Ningún servicio coincide con «{busqueda.trim()}».
        </p>
      ) : (
        <ul
          aria-label="Servicios del catálogo"
          className="max-h-[28rem] space-y-3 overflow-y-auto"
        >
          {grupos.map((grupo) => (
            <li key={grupo.categoria}>
              <p className="px-2 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {NOMBRES_CATEGORIA[grupo.categoria]}
              </p>
              <ul className="space-y-1">
                {grupo.servicios.map((s) => (
                  <li key={s.codigo}>
                    <button
                      type="button"
                      aria-pressed={s.codigo === seleccionado}
                      onClick={() => alElegir(s.codigo)}
                      className="group w-full rounded-md px-2 py-1.5 text-left text-sm outline-hidden transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset aria-pressed:bg-accent aria-pressed:text-accent-foreground aria-pressed:focus-visible:ring-accent-foreground"
                    >
                      <span className="block">{s.nombre}</span>
                      <span className="font-mono text-xs text-muted-foreground group-aria-pressed:text-accent-foreground">
                        {s.codigo}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function DetalleServicio({
  servicio,
  refTitulo,
}: {
  servicio: ServicioPrecios
  refTitulo: Ref<HTMLHeadingElement>
}) {
  const codigo = encodeURIComponent(servicio.codigo)
  const historial = useInteligencia<HistorialPrecios>(
    `/precios/servicios/${codigo}/historial`
  )
  const sobreprecios = useInteligencia<Sobreprecio[]>(
    `/precios/sobreprecios?codigo=${codigo}`
  )
  const categoria = NOMBRES_CATEGORIA[servicio.categoria] ?? servicio.categoria
  return (
    <div className="space-y-4">
      <Seccion
        titulo={servicio.nombre}
        refTitulo={refTitulo}
        descripcion={`${servicio.codigo} · ${categoria} · ${porUnidad(servicio.unidad)} · ${servicio.moneda}`}
      >
        <p className="mb-4 text-sm text-muted-foreground">
          El <Termino clave="precioReferencia">precio de referencia</Termino>{" "}
          para la cantidad y el plazo que indique: precio bajo, típico y alto
          del mercado (<Termino clave="percentiles">P25, P50 y P75</Termino>).
        </p>
        {historial.isPending ? (
          <EstadoCarga filas={2} />
        ) : (
          <ReferenciaPrecio
            servicio={servicio}
            cantidadSugerida={historial.data?.cantidad ?? "1"}
          />
        )}
      </Seccion>
      <Seccion
        titulo="Historial de precios"
        descripcion="Precio de cada contrato de los últimos 24 meses sobre el rango típico del mercado."
      >
        <ContenidoConsulta consulta={historial}>
          {(datos) => <GraficaHistorial historial={datos} />}
        </ContenidoConsulta>
      </Seccion>
      <Seccion
        titulo="Contratos con sobreprecio"
        descripcion={
          <>
            Contratos vigentes de este servicio que pagan más que el P75, con
            su <Termino clave="ahorroPotencial">ahorro potencial</Termino>.
          </>
        }
      >
        <ContenidoConsulta consulta={sobreprecios}>
          {(filas) =>
            filas.length === 0 ? (
              <EstadoVacio
                icono={TrendingUp}
                titulo="Sin sobreprecios"
                descripcion="Ningún contrato vigente de este servicio paga más que el P75."
              />
            ) : (
              <TablaSobreprecios filas={filas} />
            )
          }
        </ContenidoConsulta>
      </Seccion>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores de esta categoría",
            descripcion: `Proveedores de ${categoria} y sus contratos.`,
            ruta: `/proveedores?categoria=${servicio.categoria}`,
            icono: Building2,
          },
        ]}
      />
    </div>
  )
}

function TodosLosSobreprecios() {
  const [parametros, actualizar] = useParametros()
  const pagina = enteroPositivo(parametros.get("pagina"), 1)
  const consulta = useInteligencia<Sobreprecio[]>("/precios/sobreprecios")
  return (
    <Seccion
      titulo="Todos los sobreprecios"
      descripcion={
        <>
          Contratos vigentes que pagan más que el P75 del mercado, de mayor a
          menor <Termino clave="ahorroPotencial">ahorro potencial</Termino>{" "}
          en MXN.
        </>
      }
    >
      <ContenidoConsulta consulta={consulta}>
        {(filas) => {
          if (filas.length === 0) {
            return (
              <EstadoVacio
                icono={TrendingUp}
                titulo="Ningún contrato paga sobreprecio"
                descripcion="Todos los contratos vigentes pagan el precio del mercado o menos."
              />
            )
          }
          const visibles = filas.slice(
            (pagina - 1) * POR_PAGINA,
            pagina * POR_PAGINA
          )
          if (visibles.length === 0) {
            return (
              <EstadoVacio
                titulo="Esta página no tiene resultados"
                descripcion={`Hay ${filas.length.toLocaleString("es-MX")} líneas con sobreprecio.`}
                accion={
                  <Button
                    variant="outline"
                    onClick={() => actualizar({ pagina: null })}
                  >
                    Ir a la primera página
                  </Button>
                }
              />
            )
          }
          return (
            <div className="space-y-4">
              <TablaSobreprecios filas={visibles} conServicio />
              <Paginacion
                pagina={pagina}
                total={filas.length}
                porPagina={POR_PAGINA}
                nombre="líneas con sobreprecio"
                alCambiar={(p) => actualizar({ pagina: String(p) })}
              />
            </div>
          )
        }}
      </ContenidoConsulta>
    </Seccion>
  )
}

export function Precios() {
  const roles = useRoles()
  const [parametros, actualizar] = useParametros()
  const vista =
    parametros.get("vista") === "sobreprecios" ? "sobreprecios" : "servicio"
  const codigo = parametros.get("servicio")
  const servicios = useInteligencia<ServicioPrecios[]>("/precios/servicios")

  // En una sola columna el detalle queda debajo de la lista: al elegir un servicio se lleva el
  // foco a su título para que la persona vea el resultado sin buscarlo.
  const refDetalle = useRef<HTMLHeadingElement>(null)
  const enfocarDetalle = useRef(false)
  useEffect(() => {
    if (!enfocarDetalle.current) return
    enfocarDetalle.current = false
    refDetalle.current?.focus()
  }, [codigo])

  function elegir(nuevo: string) {
    if (nuevo === codigo) return
    enfocarDetalle.current = !window.matchMedia(DOS_COLUMNAS).matches
    actualizar({ servicio: nuevo, cantidad: null, plazo: null })
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Precios"
        descripcion={
          <>
            Compare lo que paga con lo que se paga en el mercado: el{" "}
            <Termino clave="precioReferencia">precio de referencia</Termino> de
            cada servicio y los contratos con{" "}
            <Termino clave="sobreprecio">sobreprecio</Termino>.
          </>
        }
        acciones={
          <div role="group" aria-label="Vista" className="flex gap-2">
            <Button
              variant={vista === "servicio" ? "default" : "outline"}
              aria-pressed={vista === "servicio"}
              onClick={() => actualizar({ vista: null, pagina: null })}
            >
              Por servicio
            </Button>
            <Button
              variant={vista === "sobreprecios" ? "default" : "outline"}
              aria-pressed={vista === "sobreprecios"}
              onClick={() => actualizar({ vista: "sobreprecios", pagina: null })}
            >
              Todos los sobreprecios
            </Button>
          </div>
        }
      />
      {vista === "sobreprecios" ? (
        <TodosLosSobreprecios />
      ) : (
        <ContenidoConsulta consulta={servicios}>
          {(catalogo) => {
            if (catalogo.length === 0) {
              const esAdmin = roles.includes("admin")
              return (
                <EstadoVacio
                  icono={Tags}
                  titulo="El catálogo está vacío"
                  descripcion={
                    esAdmin
                      ? "Importe el catálogo de servicios del ERP para consultar precios."
                      : "Pida a un administrador que importe el catálogo del ERP."
                  }
                  accion={
                    esAdmin && (
                      <Button asChild>
                        <Link to="/importacion">Ir a Importación</Link>
                      </Button>
                    )
                  }
                />
              )
            }
            const seleccionado =
              catalogo.find((s) => s.codigo === codigo) ?? null
            return (
              <div className="grid items-start gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
                <Seccion titulo="Servicios">
                  <ListaServicios
                    servicios={catalogo}
                    seleccionado={seleccionado?.codigo ?? null}
                    alElegir={elegir}
                  />
                </Seccion>
                {seleccionado ? (
                  <DetalleServicio
                    key={seleccionado.codigo}
                    servicio={seleccionado}
                    refTitulo={refDetalle}
                  />
                ) : (
                  <Seccion titulo="Servicio">
                    <EstadoVacio
                      icono={Tags}
                      titulo="Elija un servicio"
                      descripcion="Seleccione un servicio del catálogo para ver su precio de referencia y su historial."
                    />
                  </Seccion>
                )}
              </div>
            )
          }}
        </ContenidoConsulta>
      )}
    </section>
  )
}
```

`AvisoInteligencia` ya no se importa aquí; se borra en la Task 9.

- [ ] **Step 7: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/paginas/Precios.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 8: Commit**

```bash
git add web/src/paginas/Precios.tsx web/src/paginas/Precios.test.tsx web/src/componentes/ReferenciaPrecio.tsx web/src/componentes/GraficaHistorial.tsx web/src/componentes/TablaSobreprecios.tsx
git commit -m "feat(web): Precios muestra el precio de referencia, el historial y los sobreprecios reales" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Ranking

Cada pestaña de categoría muestra `GET /inteligencia/ranking?categoria=`. La tabla lleva por proveedor:
- posición;
- proveedor con su categoría principal;
- puntuación (barra, con la marca de historial corto);
- el percentil de cada uno de los cinco indicadores;
- meses de historial;
- tendencia.

La descripción explica contra quién se compara cada proveedor: su categoría principal, o todos si esa categoría tiene menos de 20 proveedores. Ese es el pendiente de B1 "el ranking mezcla grupos de comparación"; se documenta en la interfaz y no se cambia el cálculo. Se quita `AvisoInteligencia`.

**Files:**
- Modify (reescritura): `web/src/paginas/Ranking.tsx`
- Modify (reescritura): `web/src/paginas/Ranking.test.tsx`

**Interfaces:**
- Consumes (Task 2): `useInteligencia`, `useUmbralRiesgo`, `COMPONENTES`, `formatoPuntuacion`, `FilaRanking`, `BarraPuntuacion` y `Tendencia`.
- Produces: nada nuevo; la URL sigue siendo `/ranking?categoria=`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Reemplace `web/src/paginas/Ranking.test.tsx` completo:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Ranking } from "@/paginas/Ranking"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const FILAS = [
  {
    posicion: 1,
    proveedor_id: "p1",
    nombre: "Nube Andina",
    categoria: "nube",
    puntuacion: 72.4,
    componentes: {
      sla: 80,
      resolucion: 65,
      incidentes: 60,
      entregas: 70,
      satisfaccion: 75,
    },
    meses: 12,
    historial_corto: false,
    tendencia: 3.2,
  },
  {
    posicion: 2,
    proveedor_id: "p2",
    nombre: "Datos del Norte",
    categoria: "nube",
    puntuacion: 31,
    componentes: {
      sla: 20,
      resolucion: 35,
      incidentes: 40,
      entregas: 25,
      satisfaccion: 30,
    },
    meses: 4,
    historial_corto: true,
    tendencia: null,
  },
]

function api(respuesta: () => Response = () => respuestaJson(FILAS)) {
  return simularApi((url) =>
    url.startsWith("/api/inteligencia/ranking")
      ? respuesta()
      : new Response("", { status: 404 })
  )
}

/** La última consulta del ranking (la configuración también llama a fetch). */
function consultaDeRanking(simulado: ReturnType<typeof simularApi>): URL {
  const indice = simulado.mock.calls.findLastIndex(([url]) =>
    String(url).startsWith("/api/inteligencia/ranking")
  )
  return urlDeLlamada(simulado, indice)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Ranking", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("abre la categoría indicada en la URL y muestra su ranking", async () => {
    const simulado = api()
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=nube" })

    expect(screen.getByRole("tab", { name: "Nube" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
    expect(
      screen.getByRole("heading", { name: "Ranking · Nube" })
    ).toBeInTheDocument()
    const tabla = await screen.findByRole("table")
    expect(consultaDeRanking(simulado).searchParams.get("categoria")).toBe(
      "nube"
    )
    const primera = within(tabla).getByRole("link", { name: "Nube Andina" })
    expect(primera).toHaveAttribute("href", "/proveedores/p1")
    const fila = primera.closest("tr")!
    expect(fila).toHaveTextContent("72.4")
    expect(fila).toHaveTextContent("80.0")
    expect(fila).toHaveTextContent("+3.2")
    expect(
      within(tabla).getByText("Historial corto")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("columnheader", { name: "Posición" })
    ).toBeInTheDocument()
  })

  it("cambiar de pestaña actualiza la URL", async () => {
    api()
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await userEvent.click(screen.getByRole("tab", { name: "Soporte" }))
    expect(ubicacionActual()).toBe("/ranking?categoria=soporte")
    await userEvent.click(screen.getByRole("tab", { name: "Todas" }))
    expect(ubicacionActual()).toBe("/ranking")
  })

  it("una categoría inválida muestra todas", async () => {
    const simulado = api()
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=inventada" })
    expect(screen.getByRole("tab", { name: "Todas" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
    await screen.findByRole("table")
    expect(consultaDeRanking(simulado).searchParams.has("categoria")).toBe(
      false
    )
  })

  it("sin puntuaciones lo explica", async () => {
    api(() => respuestaJson([]))
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(
      await screen.findByText("Sin puntuaciones todavía")
    ).toBeInTheDocument()
  })

  it("si el servicio no responde, lo dice y permite reintentar", async () => {
    let fallar = true
    api(() =>
      fallar ? new Response("", { status: 502 }) : respuestaJson(FILAS)
    )
    renderizarPagina(<Ranking />, { ruta: "/ranking" })

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByRole("table")).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await screen.findByRole("table")
    await esperarSinViolaciones(container)
  })

  it("sugiere ver proveedores y revisar precios", () => {
    api()
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    expect(
      screen.getByRole("link", { name: /Ver proveedores/ })
    ).toHaveAttribute("href", "/proveedores")
    expect(
      screen.getByRole("link", { name: /Revisar precios/ })
    ).toHaveAttribute("href", "/precios")
  })
})
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/paginas/Ranking.test.tsx`
Expected: FAIL. La página no consulta el ranking y no muestra la tabla.

- [ ] **Step 3: Reescribir `web/src/paginas/Ranking.tsx`**

```tsx
import { Building2, Tags, Trophy } from "lucide-react"
import { Link } from "react-router"
import { BarraPuntuacion } from "@/componentes/BarraPuntuacion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { SiguientePaso } from "@/componentes/SiguientePaso"
import { Tendencia } from "@/componentes/Tendencia"
import { Termino } from "@/componentes/Termino"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  COMPONENTES,
  formatoPuntuacion,
  useInteligencia,
  useUmbralRiesgo,
  type FilaRanking,
} from "@/inteligencia"
import { unoDe, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, type Categoria } from "@/tipos"

const TODAS = "todas"
const OPCIONES: [string, string][] = [
  [TODAS, "Todas"],
  ...CATEGORIAS.map((c): [string, string] => [c, NOMBRES_CATEGORIA[c]]),
]

function TablaRanking({ categoria }: { categoria: Categoria | null }) {
  const umbral = useUmbralRiesgo()
  const ranking = useInteligencia<FilaRanking[]>(
    categoria ? `/ranking?categoria=${categoria}` : "/ranking"
  )
  return (
    <ContenidoConsulta consulta={ranking}>
      {(filas) =>
        filas.length === 0 ? (
          <EstadoVacio
            icono={Trophy}
            titulo="Sin puntuaciones todavía"
            descripcion={
              <>
                El ranking ordena a los proveedores activos por su{" "}
                <Termino clave="desempeno">desempeño</Termino>; aparecerá
                cuando se importe el desempeño mensual.
              </>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">
                  <span aria-hidden>#</span>
                  <span className="sr-only">Posición</span>
                </TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>Puntuación</TableHead>
                {COMPONENTES.map((c) => (
                  <TableHead key={c.clave} className="text-right">
                    {c.corto}
                  </TableHead>
                ))}
                <TableHead className="text-right">Meses</TableHead>
                <TableHead>Tendencia</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filas.map((f) => (
                <TableRow key={f.proveedor_id}>
                  <TableCell className="text-right tabular-nums">
                    {f.posicion}
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/proveedores/${encodeURIComponent(f.proveedor_id)}`}
                      className="font-medium text-accent hover:underline"
                    >
                      {f.nombre}
                    </Link>
                    <div className="text-xs text-muted-foreground">
                      {NOMBRES_CATEGORIA[f.categoria] ?? f.categoria}
                    </div>
                  </TableCell>
                  <TableCell>
                    <BarraPuntuacion
                      puntuacion={f.puntuacion}
                      confianza={f.historial_corto ? "baja" : "normal"}
                      umbral={umbral}
                    />
                  </TableCell>
                  {COMPONENTES.map((c) => (
                    <TableCell
                      key={c.clave}
                      className="text-right tabular-nums"
                    >
                      {formatoPuntuacion(f.componentes[c.clave])}
                    </TableCell>
                  ))}
                  <TableCell className="text-right tabular-nums">
                    {f.meses}
                  </TableCell>
                  <TableCell>
                    <Tendencia valor={f.tendencia} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )
      }
    </ContenidoConsulta>
  )
}

export function Ranking() {
  const [parametros, actualizar] = useParametros()
  const activa = unoDe(parametros.get("categoria"), CATEGORIAS) ?? TODAS
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Ranking de proveedores"
        descripcion={
          <>
            Los proveedores mejor calificados de cada categoría según su{" "}
            <Termino clave="puntuacion">puntuación</Termino>.
          </>
        }
      />
      <Tabs
        value={activa}
        onValueChange={(valor) =>
          actualizar({ categoria: valor === TODAS ? null : valor })
        }
      >
        <TabsList className="h-auto flex-wrap">
          {OPCIONES.map(([valor, nombre]) => (
            <TabsTrigger key={valor} value={valor}>
              {nombre}
            </TabsTrigger>
          ))}
        </TabsList>
        {OPCIONES.map(([valor, nombre]) => (
          <TabsContent key={valor} value={valor} className="mt-4">
            <Seccion
              titulo={`Ranking · ${valor === TODAS ? "Todas las categorías" : nombre}`}
              descripcion={
                <>
                  Cada indicador muestra su{" "}
                  <Termino clave="percentil">percentil</Termino> (100 es el
                  mejor). Cada proveedor se compara con los de su categoría
                  principal, o con todos si esa categoría tiene menos de 20.
                  Con{" "}
                  <Termino clave="historialCorto">historial corto</Termino>, la
                  puntuación se acerca al promedio hasta tener 6 meses de datos.
                </>
              }
            >
              <TablaRanking
                categoria={valor === TODAS ? null : (valor as Categoria)}
              />
            </Seccion>
          </TabsContent>
        ))}
      </Tabs>
      <SiguientePaso
        enlaces={[
          {
            titulo: "Ver proveedores",
            descripcion: "Revise quién le vende y sus contratos.",
            ruta: "/proveedores",
            icono: Building2,
          },
          {
            titulo: "Revisar precios",
            descripcion: "Compare lo que paga con el mercado.",
            ruta: "/precios",
            icono: Tags,
          },
        ]}
      />
    </section>
  )
}
```

- [ ] **Step 4: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/paginas/Ranking.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/paginas/Ranking.tsx web/src/paginas/Ranking.test.tsx
git commit -m "feat(web): el Ranking muestra la puntuación, los percentiles y la tendencia de cada proveedor" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Configuración, "Datos y modelo" y Centro de ayuda

**Configuración** (solo admin) gana dos secciones:

- **Formulario de la puntuación.**
  - Pesos, con el total visible mientras se escribe y con icono y texto, no solo color.
  - Umbral de riesgo e inflación anual.
  - Si los pesos no suman 100, la página no envía nada y dice cuánto suman.
  - Un error del servicio aparece junto a su campo.
  - Al guardar, se invalidan todas las consultas de la inteligencia y aparece un aviso en línea (`role="status"`).
- **Modelo de precios.**
  - Muestra el modelo en uso y su MAPE.
  - Avisa si el modelo promovido no se pudo cargar (`activo` ≠ `en_uso`).
  - Botón "Reentrenar modelo de precios": sigue el entrenamiento cada 2 s mientras corre y muestra el resultado (versión, MAPE contra la línea base y si se promovió) o el motivo del fallo (`ultimo_error`).
  - Registro de modelos.

**Panel de administración.** Gana la tarjeta "Datos y modelo" (`GET /inteligencia/datos`) con el enlace a Configuración (spec D2).

**Centro de ayuda.**
- Se actualizan "Consultar proveedores" y "Entender el precio justo" con lo que ahora muestran las páginas.
- Se agrega "Configurar la puntuación y el modelo de precios", solo para administración.

**Limpieza.** Se borra `AvisoInteligencia`: después de esta tarea ninguna página lo usa.

Sobre `sonner` y `progress`: el pendiente del Plan A proponía instalarlos para estos avisos. Un mensaje en línea con `role="status"` y un icono que gira (que se detiene con `prefers-reduced-motion`) cubren lo mismo sin dependencias nuevas.

**Files:**
- Modify (reescritura): `web/src/paginas/Configuracion.tsx`
- Modify (reescritura): `web/src/paginas/Configuracion.test.tsx`
- Create: `web/src/componentes/FormularioPuntuacion.tsx`
- Create: `web/src/componentes/PanelModeloPrecios.tsx`
- Modify: `web/src/paginas/Panel.tsx`
- Modify: `web/src/paginas/Panel.test.tsx`
- Modify: `web/src/ayuda.ts`
- Modify: `web/src/ayuda.test.ts`
- Delete: `web/src/componentes/AvisoInteligencia.tsx`

**Interfaces:**
- Consumes (Task 1): `PUT /configuracion` (422 con errores `{campo: "body.<campo>" | "body.pesos", mensaje}`), `POST /modelos/entrenar` (202 o 409 `entrenamiento_en_curso`), `GET /modelos` con `en_uso` y `ultimo_error`, y `GET /datos` con `en_uso`.
- Consumes (Task 2): `useInteligencia`, `fraccionComoPorcentaje`, `ConfiguracionInteligencia`, `RegistroModelos`, `ModeloPrecios`, `DatosInteligencia` y `enviarJson("PUT", …)`.
- Consumes (existentes): `erroresPorCampo`, `formatoFechaHora` (`@/fechas`), `Label`, `Input`, `Alert*`, `Table*`, `Badge` y `RequiereRol`.
- Produces: `FormularioPuntuacion()`, `PanelModeloPrecios()` y el artículo `configurar-puntuacion-y-modelo`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Reemplace `web/src/paginas/Configuracion.test.tsx` completo:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Configuracion } from "@/paginas/Configuracion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const CONFIGURACION = {
  peso_sla: 30,
  peso_resolucion: 20,
  peso_incidentes: 20,
  peso_entregas: 15,
  peso_satisfaccion: 15,
  umbral_riesgo: 40,
  inflacion_anual: "4.50",
  actualizado_en: null,
  actualizado_por: null,
}
const V2 = {
  version: 2,
  entrenado_en: "2026-10-10T18:00:00Z",
  origen: "manual",
  actor_nombre: "admin1",
  observaciones: 1520,
  datos_hasta: "2026-09-30",
  mape: "0.083000",
  mape_linea_base: "0.093000",
  cobertura: "0.520000",
  pinball: "0.010000",
  promovido: true,
}
const V3 = {
  ...V2,
  version: 3,
  origen: "automatico",
  actor_nombre: "Sistema (automático)",
  mape: "0.090000",
  mape_linea_base: "0.100000",
}
const MODELOS = {
  entrenando: false,
  activo: 2,
  en_uso: 2,
  ultimo_error: null,
  elementos: [V2],
}

type Respuesta = () => Response

/**
 * La configuración y los modelos. `guardar` responde el PUT (la URL es la misma que la del GET:
 * el primer pedido es la lectura). `entrenar` responde el POST y deja `despues` como estado de
 * los modelos.
 */
function api({
  guardar = () => respuestaJson(CONFIGURACION),
  modelos = MODELOS,
  entrenar = () => respuestaJson({ entrenando: true }, 202),
  despues = MODELOS,
}: {
  guardar?: Respuesta
  modelos?: object
  entrenar?: Respuesta
  despues?: object
} = {}) {
  let lecturas = 0
  let estado = modelos
  return simularApi((url) => {
    if (url === "/api/inteligencia/configuracion")
      return ++lecturas === 1 ? respuestaJson(CONFIGURACION) : guardar()
    if (url === "/api/inteligencia/modelos") return respuestaJson(estado)
    if (url === "/api/inteligencia/modelos/entrenar") {
      estado = despues
      return entrenar()
    }
    return new Response("", { status: 404 })
  })
}

/** El cuerpo del PUT de la configuración, si se envió. */
function cuerpoGuardado(simulado: ReturnType<typeof simularApi>) {
  const llamada = (simulado.mock.calls as unknown[][]).find(
    ([, init]) => (init as RequestInit | undefined)?.method === "PUT"
  )
  return llamada
    ? JSON.parse(String((llamada[1] as RequestInit).body))
    : undefined
}

const renderizar = () => renderizarPagina(<Configuracion />)

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  sesionDePrueba.roles = ["admin"]
})

describe("Configuracion", () => {
  it("muestra un esqueleto en cada sección mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findAllByRole("status")).toHaveLength(2)
  })

  it("muestra al administrador la puntuación y el modelo con sus términos", async () => {
    api()
    renderizar()
    expect(
      screen.getByRole("heading", { name: "Pesos de la puntuación" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: "Modelo de precios" })
    ).toBeInTheDocument()
    for (const termino of ["precio de referencia", "puntuación", "desempeño"]) {
      expect(screen.getByRole("button", { name: termino })).toBeInTheDocument()
    }
    expect(
      await screen.findByLabelText("Cumplimiento de SLA")
    ).toHaveValue(30)
    expect(screen.getByText("Total: 100 de 100")).toBeInTheDocument()
    expect(
      screen.getByText("Son los valores iniciales: nadie los ha cambiado todavía.")
    ).toBeInTheDocument()
  })

  it("bloquea a quien no es administrador", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizar()
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(
      screen.queryByRole("heading", { name: "Pesos de la puntuación" })
    ).not.toBeInTheDocument()
  })

  it("no guarda si los pesos no suman 100 y dice cuánto suman", async () => {
    const simulado = api()
    renderizar()
    const sla = await screen.findByLabelText("Cumplimiento de SLA")

    await userEvent.clear(sla)
    await userEvent.type(sla, "35")
    expect(screen.getByText("Total: 105 de 100")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }))

    expect(
      screen.getByText("Los pesos deben sumar 100; ahora suman 105.")
    ).toBeInTheDocument()
    expect(cuerpoGuardado(simulado)).toBeUndefined()
  })

  it("guarda la configuración y lo confirma", async () => {
    const simulado = api()
    renderizar()
    const sla = await screen.findByLabelText("Cumplimiento de SLA")
    const satisfaccion = screen.getByLabelText("Satisfacción")

    await userEvent.clear(sla)
    await userEvent.type(sla, "35")
    await userEvent.clear(satisfaccion)
    await userEvent.type(satisfaccion, "10")
    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }))

    expect(
      await screen.findByText(
        "Configuración guardada. Las puntuaciones y las alertas ya usan los valores nuevos."
      )
    ).toBeInTheDocument()
    expect(cuerpoGuardado(simulado)).toEqual({
      peso_sla: 35,
      peso_resolucion: 20,
      peso_incidentes: 20,
      peso_entregas: 15,
      peso_satisfaccion: 10,
      umbral_riesgo: 40,
      inflacion_anual: "4.50",
    })
  })

  it("muestra junto al campo el error del servicio", async () => {
    api({
      guardar: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los campos indicados.",
            errores: [
              {
                campo: "body.inflacion_anual",
                mensaje: "Use a lo más dos decimales.",
              },
            ],
          },
          422
        ),
    })
    renderizar()
    await screen.findByLabelText("Cumplimiento de SLA")

    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }))

    const inflacion = screen.getByLabelText("Inflación anual (%)")
    await waitFor(() =>
      expect(inflacion).toHaveAttribute("aria-invalid", "true")
    )
    expect(inflacion).toHaveAccessibleDescription(
      /Use a lo más dos decimales\./
    )
  })

  it("muestra el modelo en uso y su registro", async () => {
    api()
    renderizar()
    const modelo = screen
      .getByRole("heading", { name: "Modelo de precios" })
      .closest<HTMLElement>("[data-slot=card]")!

    expect(await within(modelo).findByText("Versión 2")).toBeInTheDocument()
    expect(within(modelo).getByText("Manual · admin1")).toBeInTheDocument()
    expect(within(modelo).getAllByText("8.3 %")).not.toHaveLength(0)
    expect(within(modelo).getByText("En uso")).toBeInTheDocument()
  })

  it("avisa si el modelo promovido no está en uso", async () => {
    api({ modelos: { ...MODELOS, en_uso: null } })
    renderizar()
    expect(
      await screen.findByText("El modelo promovido no está en uso")
    ).toBeInTheDocument()
  })

  it("reentrena y muestra el resultado", async () => {
    api({
      despues: { ...MODELOS, activo: 3, en_uso: 3, elementos: [V3, V2] },
    })
    renderizar()
    await screen.findByText("Versión 2")

    await userEvent.click(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    )

    expect(
      await screen.findByText(
        "Versión 3: MAPE 9.0 % (línea base 10.0 %). Se promovió: ahora calcula el precio de referencia."
      )
    ).toBeInTheDocument()
  })

  it("un entrenamiento que falla muestra el motivo", async () => {
    api({
      despues: {
        ...MODELOS,
        ultimo_error:
          "No hay datos suficientes para entrenar. Solo hay 12 líneas de contrato.",
      },
    })
    renderizar()
    await screen.findByText("Versión 2")

    await userEvent.click(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    )

    expect(
      await screen.findByText(
        "No se pudo entrenar: No hay datos suficientes para entrenar. Solo hay 12 líneas de contrato."
      )
    ).toBeInTheDocument()
  })

  it("si ya hay un entrenamiento en curso lo explica", async () => {
    api({
      entrenar: () =>
        respuestaJson(
          {
            title: "Conflicto",
            detail:
              "Ya hay un entrenamiento del modelo de precios en curso; espere a que termine.",
            codigo: "entrenamiento_en_curso",
          },
          409
        ),
    })
    renderizar()
    await screen.findByText("Versión 2")

    await userEvent.click(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    )

    expect(
      await screen.findByText(
        "Ya hay un entrenamiento del modelo de precios en curso; espere a que termine."
      )
    ).toBeInTheDocument()
  })

  it("mientras entrena lo dice y el botón queda marcado como no disponible", async () => {
    api({ modelos: { ...MODELOS, entrenando: true } })
    renderizar()
    expect(
      await screen.findByText(
        "Entrenando el modelo de precios; puede tardar un minuto."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Reentrenar modelo de precios" })
    ).toHaveAttribute("aria-disabled", "true")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar()
    await screen.findByText("Versión 2")
    await screen.findByLabelText("Cumplimiento de SLA")
    await esperarSinViolaciones(container)
  })
})
```

En `web/src/paginas/Panel.test.tsx`:

1. Agregue debajo de `ACTIVIDAD`:

```tsx
const DATOS = {
  registros: {
    proveedores: 60,
    servicios: 24,
    contratos: 1600,
    lineas_contrato: 2400,
    desempeno: 1440,
    tipo_cambio: 36,
  },
  ultimo_evento: "2026-10-12T15:00:00Z",
  modelo: {
    version: 2,
    entrenado_en: "2026-10-10T18:00:00Z",
    origen: "manual",
    actor_nombre: "admin1",
    observaciones: 1520,
    datos_hasta: "2026-09-30",
    mape: "0.083000",
    mape_linea_base: "0.093000",
    cobertura: "0.520000",
    pinball: "0.010000",
    promovido: true,
  },
  en_uso: 2,
  entrenando: false,
}
```

2. En `api`, agregue antes del `return respuestaJson(ACTIVIDAD)` final:

```tsx
    if (url.startsWith("/api/inteligencia/datos")) return respuestaJson(DATOS)
```

3. Agregue esta prueba antes de `"solo administración lo ve"`:

```tsx
  it("la tarjeta Datos y modelo resume la copia local y el modelo en uso", async () => {
    api({ usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })

    const datos = tarjeta("Datos y modelo")
    expect(await within(datos).findByText("1,600")).toBeInTheDocument()
    expect(within(datos).getByText("Líneas de contrato")).toBeInTheDocument()
    expect(datos).toHaveTextContent(
      "Modelo de precios: versión 2, MAPE 8.3 %."
    )
    expect(
      within(datos).getByRole("link", { name: "Ir a Configuración" })
    ).toHaveAttribute("href", "/configuracion")
  })
```

En `web/src/ayuda.test.ts`, agregue al final del `describe`:

```ts
  it("solo administración encuentra cómo configurar la puntuación y el modelo", () => {
    expect(
      buscarArticulos("reentrenar modelo", true).map((a) => a.slug)
    ).toContain("configurar-puntuacion-y-modelo")
    expect(buscarArticulos("reentrenar modelo", false)).toEqual([])
  })
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/paginas/Configuracion.test.tsx src/paginas/Panel.test.tsx src/ayuda.test.ts`
Expected: FAIL. Configuración muestra estados vacíos, el Panel no tiene "Datos y modelo" y el artículo no existe.

- [ ] **Step 3: Escribir `FormularioPuntuacion`**

`web/src/componentes/FormularioPuntuacion.tsx`:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, CircleAlert } from "lucide-react"
import { useId, useState, type ComponentProps, type FormEvent } from "react"
import { enviarJson, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { ContenidoConsulta } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { formatoFechaHora } from "@/fechas"
import {
  useInteligencia,
  type ConfiguracionInteligencia,
} from "@/inteligencia"
import { cn } from "@/lib/utils"

const PESOS = [
  ["peso_sla", "Cumplimiento de SLA"],
  ["peso_resolucion", "Tiempo de resolución"],
  ["peso_incidentes", "Incidentes críticos"],
  ["peso_entregas", "Entregas a tiempo"],
  ["peso_satisfaccion", "Satisfacción"],
] as const
type ClavePeso = (typeof PESOS)[number][0]

/** Un campo numérico con su etiqueta, su ayuda y el error del servicio junto a él. */
function CampoNumero({
  nombre,
  etiqueta,
  ayuda,
  error,
  "aria-describedby": otraDescripcion,
  ...entrada
}: {
  nombre: string
  etiqueta: string
  ayuda?: string
  error?: string
} & Omit<ComponentProps<typeof Input>, "id" | "name">) {
  const id = useId()
  // La descripción que llega (p. ej. el total de los pesos) se suma a la ayuda y al error.
  const descripciones = [
    otraDescripcion,
    ayuda && `${id}-ayuda`,
    error && `${id}-error`,
  ]
    .filter(Boolean)
    .join(" ")
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{etiqueta}</Label>
      <Input
        id={id}
        name={nombre}
        type="number"
        required
        aria-invalid={error ? true : undefined}
        aria-describedby={descripciones || undefined}
        className="w-32"
        {...entrada}
      />
      {ayuda && (
        <p id={`${id}-ayuda`} className="text-xs text-muted-foreground">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

function Formulario({ inicial }: { inicial: ConfiguracionInteligencia }) {
  const token = useToken()
  const cliente = useQueryClient()
  const idTotal = useId()
  const [pesos, setPesos] = useState(
    () =>
      Object.fromEntries(
        PESOS.map(([clave]) => [clave, String(inicial[clave])])
      ) as Record<ClavePeso, string>
  )
  const [intentado, setIntentado] = useState(false)
  // Los pesos son enteros: sumarlos aquí no es operar montos.
  const total = PESOS.reduce(
    (suma, [clave]) => suma + (Number(pesos[clave]) || 0),
    0
  )
  const guardar = useMutation({
    mutationFn: (datos: Record<string, number | string>) =>
      pedir<ConfiguracionInteligencia>(
        "/inteligencia/configuracion",
        token,
        enviarJson("PUT", datos)
      ),
    // La puntuación, el ranking, las alertas y el Tablero dependen de esta configuración.
    onSuccess: () => cliente.invalidateQueries({ queryKey: ["inteligencia"] }),
  })
  const errores = erroresPorCampo(guardar.error)
  const errorTotal =
    errores.pesos ??
    (intentado && total !== 100
      ? `Los pesos deben sumar 100; ahora suman ${total}.`
      : undefined)

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (guardar.isPending) return
    setIntentado(true)
    if (total !== 100) return
    const datos = new FormData(evento.currentTarget)
    guardar.mutate({
      ...Object.fromEntries(PESOS.map(([clave]) => [clave, Number(pesos[clave])])),
      umbral_riesgo: Number(datos.get("umbral_riesgo")),
      inflacion_anual: String(datos.get("inflacion_anual")),
    })
  }

  return (
    <form onSubmit={enviar} className="space-y-5">
      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">Pesos (deben sumar 100)</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {PESOS.map(([clave, etiqueta]) => (
            <CampoNumero
              key={clave}
              nombre={clave}
              etiqueta={etiqueta}
              error={errores[clave]}
              min={0}
              max={100}
              step={1}
              inputMode="numeric"
              value={pesos[clave]}
              aria-describedby={idTotal}
              onChange={(evento) => {
                setPesos({ ...pesos, [clave]: evento.target.value })
                guardar.reset()
              }}
            />
          ))}
        </div>
        <p
          id={idTotal}
          aria-live="polite"
          className={cn(
            "flex items-center gap-1 text-sm font-medium",
            total === 100 ? "text-success" : "text-destructive"
          )}
        >
          {total === 100 ? (
            <Check aria-hidden className="size-4" />
          ) : (
            <CircleAlert aria-hidden className="size-4" />
          )}
          Total: {total} de 100
        </p>
        {errorTotal && (
          <p role="alert" className="text-sm text-destructive">
            {errorTotal}
          </p>
        )}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <CampoNumero
          nombre="umbral_riesgo"
          etiqueta="Umbral de riesgo"
          ayuda="Un proveedor con menos puntos queda en riesgo."
          error={errores.umbral_riesgo}
          min={0}
          max={100}
          step={1}
          inputMode="numeric"
          defaultValue={inicial.umbral_riesgo}
          onChange={() => guardar.reset()}
        />
        <CampoNumero
          nombre="inflacion_anual"
          etiqueta="Inflación anual (%)"
          ayuda="Lleva los precios de la línea base a pesos de hoy."
          error={errores.inflacion_anual}
          min={0}
          max={50}
          step={0.01}
          inputMode="decimal"
          defaultValue={inicial.inflacion_anual}
          onChange={() => guardar.reset()}
        />
      </div>
      {guardar.isError && Object.keys(errores).length === 0 && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertDescription>{guardar.error.message}</AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" aria-disabled={guardar.isPending}>
          {guardar.isPending ? "Guardando…" : "Guardar cambios"}
        </Button>
        <p role="status" className="flex items-center gap-1 text-sm text-success">
          {guardar.isSuccess && (
            <>
              <Check aria-hidden className="size-4" />
              Configuración guardada. Las puntuaciones y las alertas ya usan los
              valores nuevos.
            </>
          )}
        </p>
      </div>
      <p className="text-xs text-muted-foreground">
        {inicial.actualizado_en
          ? `Última modificación: ${formatoFechaHora(inicial.actualizado_en)}, por ${inicial.actualizado_por}.`
          : "Son los valores iniciales: nadie los ha cambiado todavía."}
      </p>
    </form>
  )
}

/** Pesos de la puntuación, umbral de riesgo e inflación de la línea base. */
export function FormularioPuntuacion() {
  const configuracion = useInteligencia<ConfiguracionInteligencia>(
    "/configuracion"
  )
  return (
    <Seccion
      titulo="Pesos de la puntuación"
      descripcion={
        <>
          Cuánto pesa cada aspecto del{" "}
          <Termino clave="desempeno">desempeño</Termino>, desde qué{" "}
          <Termino clave="puntuacion">puntuación</Termino> un proveedor queda
          en riesgo y la inflación que usa la línea base.
        </>
      }
    >
      <ContenidoConsulta consulta={configuracion}>
        {(datos) => <Formulario inicial={datos} />}
      </ContenidoConsulta>
    </Seccion>
  )
}
```

- [ ] **Step 4: Escribir `PanelModeloPrecios`**

`web/src/componentes/PanelModeloPrecios.tsx`:

```tsx
import { useMutation } from "@tanstack/react-query"
import { CircleAlert, Database, LoaderCircle, RefreshCw } from "lucide-react"
import { useState } from "react"
import { enviarJson, pedir } from "@/api"
import { useToken } from "@/auth"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import {
  fraccionComoPorcentaje,
  useInteligencia,
  type ModeloPrecios,
  type RegistroModelos,
} from "@/inteligencia"

function Estado({ modelo, enUso }: { modelo: ModeloPrecios; enUso: number | null }) {
  if (modelo.version === enUso) return <Badge variant="success">En uso</Badge>
  return modelo.promovido ? (
    <Badge variant="outline">Promovido</Badge>
  ) : (
    <Badge variant="secondary">No promovido</Badge>
  )
}

/** Lo que pasó con el entrenamiento que pidió esta persona (o el que está corriendo). */
function Resultado({
  datos,
  antes,
}: {
  datos: RegistroModelos
  antes: number | null
}) {
  if (datos.entrenando) {
    return (
      <>
        <LoaderCircle
          aria-hidden
          className="size-4 animate-spin motion-reduce:animate-none"
        />
        Entrenando el modelo de precios; puede tardar un minuto.
      </>
    )
  }
  if (antes === null) return null
  const nuevo = datos.elementos.find((m) => m.version > antes)
  if (nuevo) {
    return (
      <>
        Versión {nuevo.version}: MAPE {fraccionComoPorcentaje(nuevo.mape)}{" "}
        (línea base {fraccionComoPorcentaje(nuevo.mape_linea_base)}).{" "}
        {nuevo.promovido
          ? "Se promovió: ahora calcula el precio de referencia."
          : "No se promovió: no mejoró la línea base."}
      </>
    )
  }
  return datos.ultimo_error ? (
    <span className="text-destructive">
      No se pudo entrenar: {datos.ultimo_error}
    </span>
  ) : null
}

function Contenido({ datos }: { datos: RegistroModelos }) {
  const token = useToken()
  // La versión más reciente al pedir el entrenamiento; null si esta persona no pidió ninguno.
  const [antes, setAntes] = useState<number | null>(null)
  const modelos = useInteligencia<RegistroModelos>("/modelos")
  const entrenar = useMutation({
    mutationFn: () =>
      pedir<{ entrenando: boolean }>(
        "/inteligencia/modelos/entrenar",
        token,
        enviarJson("POST")
      ),
    // Se espera la nueva lectura: así el resultado no se calcula con el registro anterior.
    onSettled: () => modelos.refetch(),
  })
  const ocupado = entrenar.isPending || datos.entrenando
  const enUso = datos.elementos.find((m) => m.version === datos.en_uso)

  function reentrenar() {
    if (ocupado) return
    setAntes(datos.elementos[0]?.version ?? 0)
    entrenar.mutate()
  }

  return (
    <div className="space-y-4">
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Modelo en uso</dt>
          <dd className="font-medium">
            {datos.en_uso !== null ? (
              `Versión ${datos.en_uso}`
            ) : (
              <Termino clave="lineaBase">Línea base</Termino>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            <Termino clave="mape">MAPE</Termino> del modelo en uso
          </dt>
          <dd className="font-medium">
            {enUso ? fraccionComoPorcentaje(enUso.mape) : "—"}
          </dd>
        </div>
      </dl>
      {datos.activo !== null && datos.en_uso !== datos.activo && (
        <Alert>
          <CircleAlert aria-hidden />
          <AlertTitle>El modelo promovido no está en uso</AlertTitle>
          <AlertDescription>
            La versión {datos.activo} no se pudo cargar (por ejemplo, tras
            actualizar scikit-learn o si se perdió su archivo). Mientras tanto,
            el precio de referencia usa la línea base. Reentrene el modelo para
            corregirlo.
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={reentrenar} aria-disabled={ocupado}>
          <RefreshCw aria-hidden />
          Reentrenar modelo de precios
        </Button>
        <p role="status" className="flex items-center gap-2 text-sm">
          <Resultado datos={datos} antes={antes} />
        </p>
      </div>
      {entrenar.isError && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertDescription>{entrenar.error.message}</AlertDescription>
        </Alert>
      )}
      {antes === null && !datos.entrenando && datos.ultimo_error && (
        <p className="text-sm text-muted-foreground">
          El último entrenamiento no se completó: {datos.ultimo_error}
        </p>
      )}
      {datos.elementos.length === 0 ? (
        <EstadoVacio
          icono={Database}
          titulo="Aún no se ha entrenado el modelo"
          descripcion="Se entrena solo al acumular 50 precios nuevos; también puede reentrenarlo ahora."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Versión</TableHead>
              <TableHead>Entrenado</TableHead>
              <TableHead>Origen</TableHead>
              <TableHead className="text-right">Contratos</TableHead>
              <TableHead className="text-right">MAPE</TableHead>
              <TableHead className="text-right">Línea base</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {datos.elementos.map((m) => (
              <TableRow key={m.version}>
                <TableCell>v{m.version}</TableCell>
                <TableCell>{formatoFechaHora(m.entrenado_en)}</TableCell>
                <TableCell>
                  {m.origen === "manual"
                    ? `Manual · ${m.actor_nombre}`
                    : "Automático"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {m.observaciones.toLocaleString("es-MX")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fraccionComoPorcentaje(m.mape)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fraccionComoPorcentaje(m.mape_linea_base)}
                </TableCell>
                <TableCell>
                  <Estado modelo={m} enUso={datos.en_uso} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

/** Modelo en uso, reentrenamiento a pedido y registro de entrenamientos. */
export function PanelModeloPrecios() {
  // Mientras hay un entrenamiento en curso, se vuelve a consultar cada 2 s hasta que termine.
  const modelos = useInteligencia<RegistroModelos>("/modelos", {
    refetchInterval: (consulta) =>
      consulta.state.data?.entrenando ? 2000 : false,
  })
  return (
    <Seccion
      titulo="Modelo de precios"
      descripcion="Estima el precio de referencia. Se reentrena solo al acumular 50 precios nuevos; aquí puede hacerlo a mano."
    >
      <ContenidoConsulta consulta={modelos}>
        {(datos) => <Contenido datos={datos} />}
      </ContenidoConsulta>
    </Seccion>
  )
}
```

`Contenido` vuelve a llamar `useInteligencia("/modelos")`. Es la misma clave en caché, así que no hace otra petición; solo da acceso a `refetch`. No le pase `refetchInterval`: lo maneja `PanelModeloPrecios`.

- [ ] **Step 5: Reescribir `Configuracion.tsx` y borrar `AvisoInteligencia`**

`web/src/paginas/Configuracion.tsx`:

```tsx
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { FormularioPuntuacion } from "@/componentes/FormularioPuntuacion"
import { PanelModeloPrecios } from "@/componentes/PanelModeloPrecios"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Termino } from "@/componentes/Termino"

export function Configuracion() {
  return (
    <RequiereRol rol="admin">
      <section className="space-y-6">
        <EncabezadoPagina
          titulo="Configuración"
          descripcion={
            <>
              Ajuste cómo se califica a los proveedores y cómo se calcula el{" "}
              <Termino clave="precioReferencia">precio de referencia</Termino>.
            </>
          }
        />
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <FormularioPuntuacion />
          <PanelModeloPrecios />
        </div>
      </section>
    </RequiereRol>
  )
}
```

Borre el aviso y compruebe que nadie lo usa:

```bash
git rm web/src/componentes/AvisoInteligencia.tsx
grep -rn "AvisoInteligencia" web/src
```

Expected: `grep` no imprime nada.

- [ ] **Step 6: Tarjeta "Datos y modelo" en el Panel**

En `web/src/paginas/Panel.tsx`:

1. Agregue a las importaciones:

```tsx
import { formatoFechaHora } from "@/fechas"
import {
  fraccionComoPorcentaje,
  useInteligencia,
  type DatosInteligencia,
} from "@/inteligencia"
```

2. Debajo de la función `enlace`, agregue:

```tsx
const ENTIDADES: [string, string][] = [
  ["proveedores", "Proveedores"],
  ["servicios", "Servicios"],
  ["contratos", "Contratos"],
  ["lineas_contrato", "Líneas de contrato"],
  ["desempeno", "Registros de desempeño"],
  ["tipo_cambio", "Tipos de cambio"],
]

function textoModelo(d: DatosInteligencia): string {
  const entrenando = d.entrenando ? " Hay un entrenamiento en curso." : ""
  if (d.modelo && d.en_uso === d.modelo.version)
    return `Modelo de precios: versión ${d.en_uso}, MAPE ${fraccionComoPorcentaje(d.modelo.mape)}.${entrenando}`
  if (d.modelo)
    return `Modelo de precios: la versión ${d.modelo.version} no se pudo cargar y se usa la línea base; reentrénelo en Configuración.${entrenando}`
  return `Modelo de precios: línea base (ningún modelo la ha mejorado todavía).${entrenando}`
}

/** Lo que llegó a la inteligencia y el modelo con que trabaja (spec D2: no va en el Tablero). */
function DatosYModelo() {
  const datos = useInteligencia<DatosInteligencia>("/datos")
  return (
    <Seccion
      titulo="Datos y modelo"
      descripcion="Lo que recibió la inteligencia desde el ERP y el modelo de precios con que trabaja."
      acciones={enlace("Ir a Configuración", "/configuracion")}
    >
      <ContenidoConsulta consulta={datos}>
        {(d) => (
          <div className="space-y-3 text-sm">
            <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
              {ENTIDADES.map(([clave, nombre]) => (
                <div key={clave} className="contents">
                  <dt className="text-muted-foreground">{nombre}</dt>
                  <dd className="text-right tabular-nums">
                    {(d.registros[clave] ?? 0).toLocaleString("es-MX")}
                  </dd>
                </div>
              ))}
            </dl>
            <p>
              Último dato recibido:{" "}
              {d.ultimo_evento
                ? formatoFechaHora(d.ultimo_evento)
                : "ninguno todavía"}
              .
            </p>
            <p>{textoModelo(d)}</p>
          </div>
        )}
      </ContenidoConsulta>
    </Seccion>
  )
}
```

3. En `ContenidoPanel`, agregue `<DatosYModelo />` al final de la columna derecha, después de la sección "Últimas importaciones":

```tsx
          <DatosYModelo />
        </div>
      </div>
    </section>
```

- [ ] **Step 7: Centro de ayuda**

En `web/src/ayuda.ts`, reemplace el artículo `consultar-proveedores` completo por:

```ts
  {
    slug: "consultar-proveedores",
    tema: "proveedores-precios",
    titulo: "Consultar proveedores y su desempeño",
    resumen:
      "Buscar un proveedor, ordenar por puntuación o gasto y revisar sus contratos y su desempeño.",
    secciones: [
      {
        pasos: [
          "Abra Proveedores en el menú.",
          "Busque por nombre o RFC, o filtre por categoría, estado o «En riesgo».",
          "Ordene por puntuación, gasto anual, contratos vigentes o alertas con el encabezado de cada columna; un segundo clic invierte el orden.",
          "Abra un proveedor para ver su puntuación con su tendencia, sus alertas, sus contratos y su desempeño mensual.",
        ],
      },
      {
        titulo: "La puntuación",
        parrafos: [
          "Es una calificación de 0 a 100 de los últimos 12 meses, en la que pesa más lo reciente. Combina el cumplimiento del SLA, el tiempo de resolución, los incidentes críticos, las entregas a tiempo y la satisfacción. Cada proveedor se compara con los de su categoría principal, o con todos si su categoría tiene menos de 20.",
          "Con menos de 6 meses de datos lleva la marca «Historial corto» y su puntuación se acerca al promedio hasta tener más historia. Un proveedor está en riesgo si su puntuación queda por debajo del umbral (40, salvo que administración lo cambie) o si bajó más de 10 puntos en 3 meses.",
        ],
      },
      {
        titulo: "Contratos frente al mercado",
        parrafos: [
          "En la pestaña Contratos, cada línea vigente dice si su precio está por debajo del P25, en el rango típico o sobre el P75. Haga clic en esa marca para ver el P25, el P50, el P75 y el ahorro potencial.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Proveedores", ruta: "/proveedores" }],
  },
```

Reemplace el artículo `precio-justo` completo por:

```ts
  {
    slug: "precio-justo",
    tema: "proveedores-precios",
    titulo: "Entender el precio justo",
    resumen:
      "Qué significan el precio de referencia, los percentiles, el sobreprecio y el ahorro potencial.",
    secciones: [
      {
        parrafos: [
          "El precio de referencia es lo que se paga normalmente en el mercado por un servicio, en una cantidad y un plazo dados. Se expresa con tres valores: P25 (precio bajo), P50 (típico) y P75 (alto).",
          "Se calcula con el modelo de precios cuando hay uno que mejora la línea base; si no, con la línea base: los contratos del servicio de los últimos 24 meses, llevados a pesos de hoy con la inflación configurada. Precios dice cuál se usó y con cuántos contratos.",
          "Hay sobreprecio cuando usted paga más que el P75. El ahorro potencial es lo que ahorraría en lo que resta del contrato si pagara el P50.",
          "Si hay pocos contratos comparables (menos de 8), el precio se marca con baja confianza: tómelo como una estimación.",
        ],
      },
      {
        titulo: "Cómo consultarlo",
        pasos: [
          "Abra Precios y elija un servicio; puede buscarlo por nombre o código.",
          "Ajuste la cantidad y el plazo y pulse «Calcular».",
          "Revise el historial de precios y los contratos con sobreprecio del servicio, o cambie a «Todos los sobreprecios» para verlos de mayor a menor ahorro.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Precios", ruta: "/precios" }],
  },
```

Agregue este artículo después de `catalogo-de-servicios`:

```ts
  {
    slug: "configurar-puntuacion-y-modelo",
    tema: "administracion",
    titulo: "Configurar la puntuación y el modelo de precios",
    resumen:
      "Pesos de la puntuación, umbral de riesgo, inflación y reentrenamiento del modelo.",
    secciones: [
      {
        titulo: "Puntuación",
        pasos: [
          "Abra Configuración en el área Sistema.",
          "Reparta 100 puntos entre los cinco aspectos del desempeño; el total se muestra mientras escribe.",
          "Fije el umbral de riesgo: un proveedor con menos puntos queda en riesgo y genera una alerta.",
          "Ajuste la inflación anual que usa la línea base y pulse «Guardar cambios».",
        ],
      },
      {
        parrafos: [
          "Las puntuaciones, el ranking y las alertas se recalculan al guardar. Cada cambio queda en la Actividad con quién lo hizo y qué valores cambió.",
        ],
      },
      {
        titulo: "Modelo de precios",
        parrafos: [
          "El modelo se entrena solo cuando llegan 50 precios nuevos, y usted puede reentrenarlo con «Reentrenar modelo de precios». Solo se usa si su error (MAPE) es menor que el de la línea base; si no, el precio de referencia sigue con la línea base.",
          "Si el modelo promovido no se pudo cargar, por ejemplo después de una actualización, la página lo avisa y se usa la línea base hasta que lo reentrene.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Configuración", ruta: "/configuracion" }],
  },
```

El texto nuevo de `consultar-proveedores` no debe contener la palabra "justo": `ayuda.test.ts` exige que buscar "precio justo" encuentre solo `precio-justo`.

- [ ] **Step 8: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/paginas/Configuracion.test.tsx src/paginas/Panel.test.tsx src/ayuda.test.ts src/paginas/Ayuda.test.tsx src/paginas/ArticuloAyuda.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 9: Commit**

```bash
git add web/src/paginas/Configuracion.tsx web/src/paginas/Configuracion.test.tsx web/src/componentes/FormularioPuntuacion.tsx web/src/componentes/PanelModeloPrecios.tsx web/src/paginas/Panel.tsx web/src/paginas/Panel.test.tsx web/src/ayuda.ts web/src/ayuda.test.ts web/src/componentes/AvisoInteligencia.tsx
git commit -m "feat(web): Configuración ajusta la puntuación y reentrena el modelo, el Panel resume los datos y el modelo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Rutas diferidas y foco visible en alto contraste

Dos pendientes del Plan A (spec §7.2):

1. **Rutas diferidas.** El bundle mide unos 1,000 kB porque todas las páginas, Recharts incluido, se cargan al arrancar. Con `lazy` de react-router, cada página es un archivo aparte que se descarga la primera vez que se visita.
2. **Foco visible en alto contraste.** `outline-none` (`outline-style: none`) hace que el modo de alto contraste de Windows no pinte el foco. Se cambia por `outline-hidden`, que deja un contorno transparente que ese modo sí muestra. El cambio va en todos los componentes de `components/ui` que lo usan y en `#contenido`.

**Files:**
- Modify (reescritura): `web/src/rutas.tsx`
- Create: `web/src/rutas.test.ts`
- Modify: `web/src/components/ui/{alert-dialog,button,checkbox,dialog,input,radio-group,select,tabs}.tsx`
- Modify: `web/src/componentes/Layout.tsx:89`
- Create: `web/src/componentes/FocoVisible.test.tsx`
- Modify: `web/src/componentes/Layout.test.tsx`

**Interfaces:**
- Consumes: las páginas tal como quedaron en las Tasks 3 a 9 (cada una exporta su componente con nombre).
- Produces: `paginas: RouteObject[]` y `router` en `@/rutas`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Cree `web/src/rutas.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { paginas } from "@/rutas"

describe("rutas", () => {
  it("cada página se descarga aparte y entrega su componente", async () => {
    expect(paginas.length).toBeGreaterThan(0)
    for (const ruta of paginas) {
      // Ninguna página va dentro del bundle inicial: todas se cargan con `lazy`.
      expect(ruta.Component).toBeUndefined()
      expect(typeof ruta.lazy).toBe("function")
      const cargada = await (
        ruta.lazy as () => Promise<{ Component?: unknown }>
      )()
      expect(cargada.Component).toEqual(expect.any(Function))
    }
  })
})
```

Cree `web/src/componentes/FocoVisible.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Select, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

afterEach(cleanup)

// outline-none es `outline-style: none`: el modo de alto contraste de Windows no pinta el foco.
// outline-hidden deja un contorno transparente que ese modo sí muestra.
describe("foco visible en alto contraste", () => {
  it("los controles usan outline-hidden y no outline-none", () => {
    render(
      <>
        <Button>Guardar</Button>
        <Input aria-label="Nombre" />
        <Checkbox aria-label="Acepto" />
        <Select>
          <SelectTrigger aria-label="Opción">
            <SelectValue />
          </SelectTrigger>
        </Select>
        <Tabs defaultValue="a">
          <TabsList>
            <TabsTrigger value="a">A</TabsTrigger>
          </TabsList>
          <TabsContent value="a">Contenido</TabsContent>
        </Tabs>
      </>
    )
    for (const control of [
      screen.getByRole("button", { name: "Guardar" }),
      screen.getByRole("textbox", { name: "Nombre" }),
      screen.getByRole("checkbox", { name: "Acepto" }),
      screen.getByRole("combobox", { name: "Opción" }),
      screen.getByRole("tabpanel"),
    ]) {
      expect(control).toHaveClass("outline-hidden")
      expect(control).not.toHaveClass("outline-none")
    }
  })
})
```

En `web/src/componentes/Layout.test.tsx`, agregue en `describe("Layout con sesión iniciada")`:

```tsx
  it("el contenido principal muestra el foco en alto contraste", () => {
    renderizar()
    expect(document.getElementById("contenido")).toHaveClass("outline-hidden")
    expect(document.getElementById("contenido")).not.toHaveClass("outline-none")
  })
```

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/rutas.test.ts src/componentes/FocoVisible.test.tsx src/componentes/Layout.test.tsx`
Expected: FAIL. `paginas` no existe y los controles tienen `outline-none`.

- [ ] **Step 3: Rutas diferidas**

Antes del cambio, anote el tamaño del chunk principal: `npm run build` imprime `dist/assets/index-….js` con su tamaño y el aviso de chunks de más de 500 kB.

Reemplace `web/src/rutas.tsx` completo:

```tsx
import { createBrowserRouter, type RouteObject } from "react-router"
import { Layout } from "@/componentes/Layout"

// Cada página es un archivo aparte que se descarga la primera vez que se visita: el arranque no
// carga Recharts ni las pantallas de administración que la persona quizá nunca abra.
export const paginas: RouteObject[] = [
  {
    index: true,
    lazy: async () => ({
      Component: (await import("@/paginas/Tablero")).Tablero,
    }),
  },
  {
    path: "proveedores",
    lazy: async () => ({
      Component: (await import("@/paginas/Proveedores")).Proveedores,
    }),
  },
  {
    path: "proveedores/:id",
    lazy: async () => ({
      Component: (await import("@/paginas/ProveedorDetalle")).ProveedorDetalle,
    }),
  },
  {
    path: "ranking",
    lazy: async () => ({
      Component: (await import("@/paginas/Ranking")).Ranking,
    }),
  },
  {
    path: "precios",
    lazy: async () => ({
      Component: (await import("@/paginas/Precios")).Precios,
    }),
  },
  {
    path: "alertas",
    lazy: async () => ({
      Component: (await import("@/paginas/Alertas")).Alertas,
    }),
  },
  {
    path: "importacion",
    lazy: async () => ({
      Component: (await import("@/paginas/Importacion")).Importacion,
    }),
  },
  {
    path: "configuracion",
    lazy: async () => ({
      Component: (await import("@/paginas/Configuracion")).Configuracion,
    }),
  },
  {
    path: "sistema",
    lazy: async () => ({ Component: (await import("@/paginas/Panel")).Panel }),
  },
  {
    path: "sistema/estado",
    lazy: async () => ({
      Component: (await import("@/paginas/EstadoSistema")).EstadoSistema,
    }),
  },
  {
    path: "sistema/usuarios",
    lazy: async () => ({
      Component: (await import("@/paginas/Usuarios")).Usuarios,
    }),
  },
  {
    path: "sistema/usuarios/:id",
    lazy: async () => ({
      Component: (await import("@/paginas/UsuarioDetalle")).UsuarioDetalle,
    }),
  },
  {
    path: "sistema/correos",
    lazy: async () => ({
      Component: (await import("@/paginas/Correos")).Correos,
    }),
  },
  {
    path: "sistema/actividad",
    lazy: async () => ({
      Component: (await import("@/paginas/Actividad")).Actividad,
    }),
  },
  {
    path: "sistema/catalogo",
    lazy: async () => ({
      Component: (await import("@/paginas/Catalogo")).Catalogo,
    }),
  },
  {
    path: "ayuda",
    lazy: async () => ({ Component: (await import("@/paginas/Ayuda")).Ayuda }),
  },
  {
    path: "ayuda/:articulo",
    lazy: async () => ({
      Component: (await import("@/paginas/ArticuloAyuda")).ArticuloAyuda,
    }),
  },
  {
    path: "*",
    lazy: async () => ({
      Component: (await import("@/paginas/NoEncontrado")).NoEncontrado,
    }),
  },
]

/** Lo que se ve mientras llega la primera página (unos milisegundos en la red local). */
function CargaInicial() {
  return (
    <p role="status" className="p-6 text-muted-foreground">
      Cargando…
    </p>
  )
}

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    HydrateFallback: CargaInicial,
    children: paginas,
  },
])
```

- [ ] **Step 4: `outline-hidden` en lugar de `outline-none`**

Run (desde la raíz del repositorio):

```bash
sed -i 's/\boutline-none\b/outline-hidden/g' web/src/components/ui/alert-dialog.tsx web/src/components/ui/button.tsx web/src/components/ui/checkbox.tsx web/src/components/ui/dialog.tsx web/src/components/ui/input.tsx web/src/components/ui/radio-group.tsx web/src/components/ui/select.tsx web/src/components/ui/tabs.tsx web/src/componentes/Layout.tsx
```

Run: `grep -rn "outline-none" web/src --include=*.tsx`
Expected: solo quedan comentarios y aserciones de pruebas que dicen "outline-none" (por ejemplo en `components/ui/table.tsx`, `Precios.test.tsx` y `ProveedorDetalle.test.tsx`). Ninguna clase en uso.

- [ ] **Step 5: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/rutas.test.ts src/componentes/FocoVisible.test.tsx src/componentes/Layout.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde. `npm run build` ya no imprime el aviso de chunks de más de 500 kB; anote en su reporte el tamaño del chunk principal antes y después.

- [ ] **Step 6: Commit**

```bash
git add web/src/rutas.tsx web/src/rutas.test.ts web/src/components/ui web/src/componentes/Layout.tsx web/src/componentes/Layout.test.tsx web/src/componentes/FocoVisible.test.tsx
git commit -m "perf(web): cada página se descarga al visitarla, y el foco se ve en alto contraste" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Guía por usuario, términos en la guía y README

Tres pendientes del plan "Claridad y acceso":

1. **La guía de uso se recuerda por usuario.** Hoy se guarda en una sola clave del navegador (`plataforma-guia`): en un equipo compartido, lo que oculta una persona lo oculta para todas. La clave pasa a ser `plataforma-guia:<sub>`, donde `sub` es el identificador estable de la persona en el token.
   - La clave anterior se ignora: quien había ocultado la guía la verá una vez más y podrá ocultarla de nuevo.
   - No vale la pena migrarla: no se puede saber de quién era.
2. **Términos con `Termino`.** Los pasos de la guía muestran "desempeño" y "precio de referencia" con su definición.
3. **README sin la contraseña en la línea de comandos.** El comando del tema de inicio de sesión ya no pasa `--password` a `kcadm.sh`: usa `KC_CLI_PASSWORD`, como `infra/keycloak/quitar-otp.sh`. Así la contraseña no queda en la lista de procesos, y el mismo comando sirve en Git Bash y en PowerShell porque ya no lleva comillas dobles.

**Files:**
- Modify (reescritura): `web/src/guia.ts`
- Modify (reescritura): `web/src/guia.test.ts`
- Modify: `web/src/auth.ts` (`useUsuarioId`)
- Modify: `web/src/componentes/Layout.tsx`, `web/src/componentes/GuiaUso.tsx` y `web/src/componentes/MenuUsuario.tsx`
- Modify: `web/src/pruebas/sesion.ts`, `web/src/componentes/Layout.test.tsx` y `web/src/componentes/GuiaUso.test.tsx`
- Modify: `README.md` (sección "Tema de inicio de sesión en un realm ya importado")

**Interfaces:**
- Produces:
  - `claveGuia(usuario: string): string` y `PREFIJO_GUIA = "plataforma-guia"`.
  - `useGuia(usuario: string)`, `marcarVisita(usuario, seccion)`, `ocultarGuia(usuario)` y `mostrarGuia(usuario)`.
  - `useUsuarioId(): string` en `@/auth`.
  - `USUARIO_DE_PRUEBA = "ana-1"` en `@/pruebas/sesion`.
- Se elimina `CLAVE_GUIA`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Reemplace `web/src/guia.test.ts` completo:

```ts
import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import {
  claveGuia,
  marcarVisita,
  mostrarGuia,
  ocultarGuia,
  useGuia,
} from "@/guia"

const ANA = "ana-1"
const LUIS = "luis-2"

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe("guía de uso", () => {
  it("empieza visible y sin visitas", () => {
    const { result } = renderHook(() => useGuia(ANA))
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false },
    })
  })

  it("registra visitas y las conserva en la clave de su usuario", () => {
    const { result } = renderHook(() => useGuia(ANA))
    act(() => marcarVisita(ANA, "proveedores"))
    expect(result.current.visitas.proveedores).toBe(true)
    expect(
      JSON.parse(localStorage.getItem(claveGuia(ANA)) ?? "{}").visitas
        .proveedores
    ).toBe(true)
  })

  it("cada persona tiene su propia guía en el mismo navegador", () => {
    const ana = renderHook(() => useGuia(ANA))
    const luis = renderHook(() => useGuia(LUIS))

    act(() => ocultarGuia(ANA))

    expect(ana.result.current.oculta).toBe(true)
    expect(luis.result.current.oculta).toBe(false)
    expect(localStorage.getItem(claveGuia(LUIS))).toBeNull()
  })

  it("se oculta y se vuelve a mostrar", () => {
    const { result } = renderHook(() => useGuia(ANA))
    act(() => ocultarGuia(ANA))
    expect(result.current.oculta).toBe(true)
    act(() => mostrarGuia(ANA))
    expect(result.current.oculta).toBe(false)
  })

  it("un valor corrupto cuenta como estado inicial", () => {
    localStorage.setItem(claveGuia(ANA), "{")
    const { result } = renderHook(() => useGuia(ANA))
    expect(result.current).toEqual({
      oculta: false,
      visitas: { proveedores: false, precios: false },
    })
  })

  it("funciona aunque el navegador bloquee localStorage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    const { result } = renderHook(() => useGuia(ANA))
    expect(result.current.oculta).toBe(false)
    expect(() => act(() => marcarVisita(ANA, "precios"))).not.toThrow()
  })

  it("se oculta aunque el navegador bloquee localStorage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    const { result } = renderHook(() => useGuia(ANA))
    act(() => ocultarGuia(ANA))
    expect(result.current.oculta).toBe(true)
    // Deja el respaldo en memoria como estaba para las demás pruebas.
    act(() => mostrarGuia(ANA))
    expect(result.current.oculta).toBe(false)
  })
})
```

En `web/src/pruebas/sesion.ts`:

1. Agregue, debajo de las importaciones:

```ts
/** El `sub` (identificador estable) de "Ana López" en el token simulado. */
export const USUARIO_DE_PRUEBA = "ana-1"
```

2. En el `profile` de `oidcSimulado`, agregue `sub: USUARIO_DE_PRUEBA,` como primer campo.

En `web/src/componentes/GuiaUso.test.tsx`:

1. Cambie `import { CLAVE_GUIA } from "@/guia"` por:

```tsx
import { claveGuia } from "@/guia"
import { USUARIO_DE_PRUEBA } from "@/pruebas/sesion"
```

2. Cambie cada `CLAVE_GUIA` por `claveGuia(USUARIO_DE_PRUEBA)`.
3. Agregue esta prueba:

```tsx
  it("los términos de los pasos abren su definición", async () => {
    conProveedores(60)
    renderizarPagina(<GuiaUso />)
    expect(
      await screen.findByRole("button", { name: "desempeño" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "precio de referencia" })
    ).toBeInTheDocument()
  })
```

En `web/src/componentes/Layout.test.tsx`:

1. Cambie `import { CLAVE_GUIA } from "@/guia"` por `import { claveGuia } from "@/guia"` y agregue `USUARIO_DE_PRUEBA` a la importación de `@/pruebas/sesion`.
2. En `sesionCon`, agregue `sub: USUARIO_DE_PRUEBA,` al `profile`.
3. Cambie cada `CLAVE_GUIA` por `claveGuia(USUARIO_DE_PRUEBA)`.

- [ ] **Step 2: Correr las pruebas y ver que fallan**

Run (desde `web/`): `npx vitest run src/guia.test.ts src/componentes/GuiaUso.test.tsx src/componentes/Layout.test.tsx`
Expected: FAIL. `claveGuia` no existe y los pasos no tienen términos.

- [ ] **Step 3: Reescribir `web/src/guia.ts`**

```ts
import { useSyncExternalStore } from "react"

/** Prefijo de las claves de localStorage de la guía de uso. */
export const PREFIJO_GUIA = "plataforma-guia"

/** Clave de la guía de una persona (el `sub` de su token): en un equipo compartido, cada quien la suya. */
export function claveGuia(usuario: string): string {
  return `${PREFIJO_GUIA}:${usuario}`
}

export type EstadoGuia = {
  oculta: boolean
  visitas: { proveedores: boolean; precios: boolean }
}

const INICIAL: EstadoGuia = {
  oculta: false,
  visitas: { proveedores: false, precios: false },
}

function interpretar(crudo: string | null): EstadoGuia {
  try {
    const valor = JSON.parse(crudo ?? "null")
    return {
      oculta: valor?.oculta === true,
      visitas: {
        proveedores: valor?.visitas?.proveedores === true,
        precios: valor?.visitas?.precios === true,
      },
    }
  } catch {
    return INICIAL
  }
}

// useSyncExternalStore exige devolver el mismo objeto mientras el estado no cambie.
const ultimos = new Map<string, { crudo: string | null; estado: EstadoGuia }>()
// Respaldo cuando el almacenamiento falla: la preferencia dura mientras la página siga abierta.
const memoria = new Map<string, string>()

function leer(clave: string): string | null {
  try {
    return localStorage.getItem(clave)
  } catch {
    return memoria.get(clave) ?? null
  }
}

function instantanea(usuario: string): EstadoGuia {
  const clave = claveGuia(usuario)
  const crudo = leer(clave)
  const ultimo = ultimos.get(clave)
  if (ultimo && ultimo.crudo === crudo) return ultimo.estado
  const estado = interpretar(crudo)
  ultimos.set(clave, { crudo, estado })
  return estado
}

const oyentes = new Set<() => void>()

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  window.addEventListener("storage", oyente)
  return () => {
    oyentes.delete(oyente)
    window.removeEventListener("storage", oyente)
  }
}

function guardar(usuario: string, cambiar: (estado: EstadoGuia) => EstadoGuia) {
  const clave = claveGuia(usuario)
  const valor = JSON.stringify(cambiar(instantanea(usuario)))
  try {
    localStorage.setItem(clave, valor)
  } catch {
    memoria.set(clave, valor)
  }
  oyentes.forEach((oyente) => oyente())
}

export function marcarVisita(
  usuario: string,
  seccion: "proveedores" | "precios"
): void {
  if (instantanea(usuario).visitas[seccion]) return
  guardar(usuario, (estado) => ({
    ...estado,
    visitas: { ...estado.visitas, [seccion]: true },
  }))
}

export function ocultarGuia(usuario: string): void {
  guardar(usuario, (estado) => ({ ...estado, oculta: true }))
}

export function mostrarGuia(usuario: string): void {
  guardar(usuario, (estado) => ({ ...estado, oculta: false }))
}

export function useGuia(usuario: string): EstadoGuia {
  return useSyncExternalStore(suscribir, () => instantanea(usuario))
}
```

- [ ] **Step 4: Usar el identificador de la persona**

En `web/src/auth.ts`, agregue al final:

```ts
/** Identificador estable de la persona (el `sub` del token), para guardar sus preferencias. */
export function useUsuarioId(): string {
  return useAuth().user?.profile.sub ?? ""
}
```

En `web/src/componentes/Layout.tsx`, cambie el efecto de la guía por:

```tsx
  // La guía del Tablero marca como vistos Proveedores y Precios cuando se visitan.
  const usuario = auth.user?.profile.sub ?? ""
  useEffect(() => {
    if (!usuario) return
    if (estaActiva("/proveedores", pathname)) marcarVisita(usuario, "proveedores")
    if (estaActiva("/precios", pathname)) marcarVisita(usuario, "precios")
  }, [pathname, usuario])
```

En `web/src/componentes/MenuUsuario.tsx`:

1. Agregue `useUsuarioId` a la importación de `@/auth`.
2. Cambie `const guia = useGuia()` por:

```tsx
  const usuario = useUsuarioId()
  const guia = useGuia(usuario)
```

3. Cambie `mostrarGuia()` por `mostrarGuia(usuario)`.

En `web/src/componentes/GuiaUso.tsx`:

1. Agregue `useUsuarioId` a la importación de `@/auth` y `import { Termino } from "@/componentes/Termino"`.
2. Cambie `const guia = useGuia()` por:

```tsx
  const usuario = useUsuarioId()
  const guia = useGuia(usuario)
```

3. Cambie `ocultarGuia()` por `ocultarGuia(usuario)`.
4. En el tipo `Paso`, cambie `descripcion: string` por `descripcion: ReactNode`.
5. Cambie la `descripcion` del paso "Importar contratos y proveedores" por:

```tsx
      descripcion: (
        <>
          Cargue los datos del ERP: catálogo, proveedores, contratos y{" "}
          <Termino clave="desempeno">desempeño</Termino>.
        </>
      ),
```

6. Cambie la del paso "Ver el precio justo" por:

```tsx
      descripcion: (
        <>
          Compare lo que paga con el{" "}
          <Termino clave="precioReferencia">precio de referencia</Termino> del
          mercado.
        </>
      ),
```

- [ ] **Step 5: README con `KC_CLI_PASSWORD`**

En `README.md`, sección "Tema de inicio de sesión en un realm ya importado", reemplace desde el párrafo que empieza "Después, el comando según su terminal." hasta el final del bloque `powershell` por:

````markdown
Después, este comando. Sirve igual en Git Bash y en PowerShell porque no lleva comillas dobles, y
la contraseña viaja en la variable `KC_CLI_PASSWORD` dentro del contenedor: no aparece en la línea
de comandos ni en la lista de procesos. En **Git Bash**, ejecute antes `export MSYS_NO_PATHCONV=1`;
sin eso, Git Bash convierte `/opt/…` y `/tmp/…` en rutas de Windows y el comando falla.

```bash
docker compose -f infra/docker-compose.yml exec keycloak bash -c 'KC_CLI_PASSWORD=$KC_BOOTSTRAP_ADMIN_PASSWORD /opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config --server http://localhost:8080/auth --realm master --user admin && /opt/keycloak/bin/kcadm.sh update realms/plataforma --config /tmp/kcadm.config -s loginTheme=plataforma'
```
````

Si el stack está levantado, corra el comando una vez en Git Bash y confirme que termina sin error. El tema ya está asignado, así que repetirlo no cambia nada. No escriba la contraseña en ningún lado: el contenedor ya la tiene en `KC_BOOTSTRAP_ADMIN_PASSWORD`.

- [ ] **Step 6: Correr las pruebas y ver que pasan**

Run (desde `web/`): `npx vitest run src/guia.test.ts src/componentes/GuiaUso.test.tsx src/componentes/Layout.test.tsx src/paginas/Tablero.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde. `grep -rn "CLAVE_GUIA" web/src` no imprime nada.

- [ ] **Step 7: Commit**

```bash
git add web/src/guia.ts web/src/guia.test.ts web/src/auth.ts web/src/componentes/Layout.tsx web/src/componentes/GuiaUso.tsx web/src/componentes/MenuUsuario.tsx web/src/pruebas/sesion.ts web/src/componentes/Layout.test.tsx web/src/componentes/GuiaUso.test.tsx README.md
git commit -m "fix(web): la guía de uso se recuerda por persona y explica sus términos; el README no pone la contraseña en la línea de comandos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Revisión en navegador y documentación

La hace el **controlador**, no un subagente: necesita el stack completo, iniciar sesión con los usuarios de desarrollo y el panel de navegador. Es la revisión que pide la spec (§1 y §10): axe con contraste en cada página, a 375, 768, 1024 y 1440 px, en claro y oscuro. También recorre los flujos que jsdom no puede probar:
- las gráficas de Recharts;
- el reentrenamiento real;
- la campana con datos reales;
- el foco al elegir un servicio a 375 px.

**Files:**
- Create: `docs/qa/revision-inteligencia-interfaz.md`
- Modify: `README.md` (sección "Interfaz")
- Las correcciones que salgan van cada una en su propio commit `fix(web)`, con su prueba.

- [ ] **Step 1: Verificación previa**

Run (desde la raíz): `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest services/inteligencia`
Run (desde `web/`): `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde. Anote cuántos archivos y pruebas pasaron, y el tamaño del chunk principal.

- [ ] **Step 2: Levantar el stack y la prueba de humo**

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait
```

```bash
uv run python infra/smoke_test.py
```

Expected: la prueba de humo termina con `OK: …`.

- [ ] **Step 3: Recorrer los flujos en el gateway**

El gateway (<http://localhost:8080>) tiene CSP. Use `comprador1` y `admin1`; las contraseñas están en `infra/keycloak/realm-plataforma.json` y no se escriben en el documento. Revise en tema claro, a 1440 px:

| # | Flujo | Qué comprobar |
|---|---|---|
| 1 | Tablero | Las cuatro cifras coinciden con `GET /api/inteligencia/tablero`. La línea de 24 meses se dibuja con su tooltip en MXN. "Ver los datos" abre la tabla. Los enlaces llevan a Alertas, a Proveedores en riesgo y a Precios. |
| 2 | Campana | Número con "99+" si hay 100 o más. Las 5 primeras van primero las altas, y dentro de "media" el sobreprecio de mayor ahorro. Cada una lleva a su proveedor. |
| 3 | Alertas | Filtros en la URL. Paginación de 25. "Quitar filtros" deja el foco en "Tipo". `?proveedor=` desde la lista de proveedores. |
| 4 | Proveedores | Orden por puntuación (mayor primero) y por gasto. Filtro "En riesgo". El número de alertas lleva a Alertas filtradas. "Ir a la primera página" deja el foco en el buscador. |
| 5 | Ficha | Puntuación con tendencia y línea de 12 meses. "Frente a su categoría". En Contratos, "Sobre P75" abre el detalle con P25/P50/P75 y el ahorro. |
| 6 | Precios | Referencia con la cantidad sugerida; recalcular con otra cantidad y plazo. En la gráfica se ven los puntos sobre la banda P25–P75 y la línea P50. "Todos los sobreprecios" pagina. |
| 7 | Ranking | Una pestaña por categoría, percentiles y marca de historial corto. |
| 8 | Configuración (admin1) | Cambiar un peso muestra el total. Guardar responde y la Actividad registra el cambio. "Reentrenar modelo de precios" muestra "Entrenando…" y luego la versión, el MAPE y si se promovió. Con eso, el modelo del entorno de desarrollo (v1, anterior a `version_sklearn`) queda reemplazado. Devuelva los pesos a sus valores iniciales al terminar. |
| 9 | Panel (admin1) | "Datos y modelo" con los registros, el último dato recibido y el modelo en uso. |
| 10 | Consola y red | Sin errores de CSP ni de JavaScript. Las llamadas a `/api/inteligencia` responden 200. |

- [ ] **Step 4: axe y scroll horizontal por ancho**

El servidor de Vite (<http://localhost:5173>, sin CSP) permite inyectar axe-core desde `/node_modules/axe-core/axe.min.js`, igual que en `docs/qa/revision-visual-plan-a.md`.
- Reglas: WCAG 2.0, 2.1 y 2.2, niveles A y AA, **con** la regla de contraste.
- Anchos: 375, 768, 1024 y 1440 px, en tema claro y en tema oscuro.
- Rutas: Tablero; Proveedores; la ficha en sus tres pestañas; Precios con un servicio elegido; "Todos los sobreprecios"; Ranking; Alertas; la campana abierta; y Configuración y Panel como admin1.
- En cada caso, anote las violaciones de axe y si `document.documentElement.scrollWidth <= window.innerWidth`.
- A 375 px, compruebe además que elegir un servicio en Precios lleva el foco al título de su detalle.

- [ ] **Step 5: Corregir lo que salga**

Por cada defecto:
1. Escriba su prueba en jsdom (si se puede) y véala fallar.
2. Corríjalo.
3. Haga un commit `fix(web): …` con el mensaje de dos `-m`.

Si un defecto no se puede probar en jsdom (contraste o diseño), dígalo en el documento.

- [ ] **Step 6: Escribir `docs/qa/revision-inteligencia-interfaz.md`**

Use la estructura de `docs/qa/revision-gestion-administracion.md`:
- cabecera con fecha, commit revisado, usuarios de prueba (sin contraseñas) y alcance;
- "Entorno y método";
- la tabla de flujos del Step 3 con su resultado;
- la tabla de axe y scroll por ancho;
- la tabla de defectos (defecto, causa, corrección y commit);
- lo que quedó pendiente, si algo quedó.

- [ ] **Step 7: Actualizar el README**

En `README.md`, sección "Interfaz":

1. Cambie la línea de la revisión de accesibilidad por:

```markdown
- Revisión de accesibilidad y diseño adaptable: `docs/qa/revision-visual-plan-a.md` (Plan A) y `docs/qa/revision-inteligencia-interfaz.md` (inteligencia en la interfaz).
```

2. Cambie la línea de la guía por:

```markdown
- Guía "Cómo usar PluriOne" en el Tablero; se oculta y vuelve desde el menú de usuario, y se recuerda por persona (no por navegador). El menú
  muestra icono y nombre; el propósito de cada opción aparece en la ayuda emergente del menú
  contraído y lo lee el lector de pantalla.
```

3. Agregue al final de la sección:

```markdown
- **Inteligencia**: el Tablero, Proveedores (lista y ficha), Precios, Ranking, Alertas, la campana de la barra superior y Configuración muestran los datos del servicio `inteligencia` (`web/src/inteligencia.ts`); el Panel resume sus datos y su modelo en "Datos y modelo".
- Cada página se descarga la primera vez que se visita (rutas diferidas en `web/src/rutas.tsx`).
```

- [ ] **Step 8: Commit**

```bash
git add docs/qa/revision-inteligencia-interfaz.md README.md
git commit -m "docs: revisión en navegador de la inteligencia en la interfaz" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
