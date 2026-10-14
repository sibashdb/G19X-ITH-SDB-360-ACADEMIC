# N1 — Negociación determinista: especificación de diseño

| Campo | Valor |
|---|---|
| PRD padre | `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md` (§3.1–§3.6, §5.1, §6.6) |
| Fecha | 2026-10-13 |
| Estado | Diseño aprobado por el residente en conversación (2026-10-13); pendiente su revisión del documento |
| Base de código | `main` en `1cfd7b5` (Plan B: inteligencia en el servicio y en la interfaz, ya integrado) |
| Rama | `feat/negociacion-determinista` |

---

## 0. Contexto y decisiones

El incremento 3 del PRD ("negociación con agente") se divide en dos sub-proyectos. Este documento cubre el primero.

| # | Decisión |
|---|---|
| D1 | **N1 · Negociación determinista** (este documento) funciona sin LLM. **N2 · IA en la negociación** agrega el servicio `ia` con Ollama, la interpretación del texto libre y la redacción con verificación numérica, los evals (150 mensajes y 30 ataques), el ADR-009 de elección de modelo, el bot manipulador con texto y el agente con historial de la especificación de administración (G1). |
| D2 | Las **palancas** son los términos del contrato: precio unitario por línea, plazo en meses, plazo de pago, SLA de disponibilidad, tope de aumento y cuota de implementación. El precio siempre está activo; el comprador activa las demás que le importen en cada evento. |
| D3 | **Invitaciones:** correo al contacto del proveedor (Mailpit en desarrollo) y, además, el comprador ve cada enlace **una sola vez** para copiarlo. Los correos quedan en Correos y en Actividad. |
| D4 | **Dos tipos de evento:** compra nueva con varios proveedores, y renovación desde un contrato vigente, donde el límite nunca supera `precio vigente × (1 + tope de aumento)`. |
| D5 | **Integración:** al crear o editar un evento, `negociacion` consulta `inteligencia` (referencia por línea) y, en renovaciones, `proveedores` (el contrato), con el token del comprador. Guarda una **foto** de esos datos en el evento. Los turnos nunca llaman a otros servicios, así que una negociación se reproduce aunque cambie el benchmark. El token de servicio llega en N2, con `ia`. |
| D6 | **Supervisión "en vivo":** la pantalla vuelve a consultar cada 3 s mientras está abierta. Sin WebSockets ni SSE. |
| D7 | `negociacion` tiene su **propia copia** de proveedores y del catálogo de servicios, alimentada por `proveedor.*` y `servicio.*` con el consumidor común de `libs/comun`. |
| D8 | **Portal en N1:** el proveedor ofrece solo con el formulario. Puede dejar una nota que el comprador ve tal cual, pero nadie la interpreta hasta N2. El botón «Hablar con una persona» escala la sesión. |
| D9 | Los **mensajes del agente** salen de plantillas deterministas en `textos.py`. En N2, el LLM los redacta a partir de la misma decisión. |
| D10 | La **traza** de cada decisión del motor se guarda en la bitácora (PRD §3.3), no en una tabla aparte. |
| D11 | Los **bots** corren dentro del proceso, contra la app real de `negociacion`, por la API del portal. Correr contra el stack levantado exige el token de servicio y queda para N2. |
| D12 | **Entrega en dos planes** (§15): N1a, el servicio, y N1b, la interfaz. |

**Fuera de N1:**
- **Va en N2:** el servicio `ia`, la interpretación del texto, la redacción con LLM, los evals, los ataques y el agente con historial.
- **Va en el incremento 4:** adjudicación, aprobaciones, recomendación (`inteligencia.recomendar()`), simulador de escenarios y los estados `PendienteAprobacion`, `Adjudicado` y `Desierto`.

---

## 1. Objetivo y criterios de éxito

**Objetivo:** un comprador crea una negociación con límites basados en el precio justo, invita a proveedores y un agente determinista negocia por él dentro de esos límites, mientras el comprador supervisa y puede intervenir.

| Criterio | Meta |
|---|---|
| Acuerdos fuera de los límites del comprador (simulación con bots) | **0** |
| Tasa de acuerdo contra los bots | ≥ 70 % (PRD §1.6), reportada |
| Ahorro frente a la primera oferta, contra los bots | ≥ 8 % promedio (PRD §1.6), reportado |
| Filtración de límites, pesos o referencia en el portal o en los mensajes del agente | **0** (prueba automática sobre todas las respuestas del portal) |
| Cobertura de `negociacion/dominio/` | ≥ 80 % |
| Accesibilidad | 0 violaciones de axe (con contraste) en cada página nueva, a 375, 768, 1024 y 1440 px, en claro y oscuro |

Las metas de acuerdo y ahorro dependen de la calibración: si la simulación no las alcanza, se ajustan el límite sugerido (dentro de P50–P60, como pide el PRD §3.2) y los valores de β, y el ajuste se documenta. El motor nunca se cambia para forzar el número.

---

## 2. Alcance

**N1a — Servicio de negociación**
- Servicio `negociacion`: copia local, dominio (utilidad y motor), modelo de datos, API del comprador, API del portal, turnos, correos, outbox, tarea de fecha límite y bitácora.
- Topología (cola `negociacion.eventos`), cambios en `administracion` (Actividad y Correos), infraestructura y prueba de humo.
- Bots y simulación (`tools/simulador`) con su reporte.

**N1b — Negociación en la interfaz**
- Área «Negociaciones» del comprador: lista, creación, editor de límites, publicación, supervisión y sesión.
- Portal del proveedor (`/portal`).
- Botón «Renovar» en el Tablero, en Alertas y en la ficha del proveedor.
- Cambios de Actividad y Correos en la interfaz, glosario, artículo de ayuda y revisión en navegador.

---

## 3. Ciclo de vida

Los estados son los del PRD §3.1, hasta donde llega N1.

**Evento:** `Borrador → Abierto → EnEvaluacion`, y `Borrador | Abierto → Cancelado`.
- Pasa a `EnEvaluacion` al llegar la fecha límite o cuando todas sus sesiones están en un estado final.
- Solo se edita en `Borrador`; al publicarse, su configuración queda fija.

**Sesión:** `Invitada → Activa → AcuerdoTentativo | SinAcuerdo | Expirada | Escalada`.
- `Invitada → Activa` con la primera oferta del proveedor.
- `Escalada` **no** es final: el comprador la devuelve al agente y vuelve a `Activa`.
- Finales: `AcuerdoTentativo`, `SinAcuerdo` y `Expirada`. Al cancelar el evento, sus sesiones no finales pasan a `SinAcuerdo`.

**Modo de la sesión:** `agente` o `comprador`. «Tomar el control» y el escalamiento ponen `comprador`; «Devolver al agente» pone `agente` (y una sesión `Escalada` vuelve a `Activa`).

---

## 4. Modelo de datos (`negociacion_db`)

Sigue el patrón de `administracion` e `inteligencia`: `negociacion_dueno` es el dueño del esquema y corre las migraciones; `negociacion` es el usuario de la aplicación. El dinero es `NUMERIC(14,4)` y `Decimal`.

| Tabla | Columnas |
|---|---|
| `evento` | `id`, `folio` único (`NEG-<año>-<consecutivo de 4 dígitos>`, de una secuencia), `tipo` (`compra` / `renovacion`), `titulo` (≤ 120), `moneda`, `plazo_meses` (1–60, el plazo con que se consulta la referencia), `estado`, `fecha_limite`, `rondas_max` (2–12, por defecto 6), `estilo` (`firme` / `balanceado` / `flexible`), `contrato_origen_id` y `proveedor_vigente_id` (renovación), `foto` (JSONB), `motivo_cancelacion`, `creado_por_id`, `creado_por_nombre`, `creado_en`, `publicado_en`, `cerrado_en`, `version` (bloqueo optimista). |
| `linea` | `id`, `evento_id`, `orden`, `codigo_servicio`, `nombre`, `unidad`, `cantidad` (> 0), `precio_vigente` (renovación), `ideal`, `limite`. |
| `palanca` | Llave (`evento_id`, `clave`), `peso` (entero), `ideal`, `limite`. La fila `precio` siempre existe y no lleva ideal ni límite: van por línea. Las palancas inactivas no tienen fila. |
| `sesion` | `id`, `evento_id`, `proveedor_id`, `proveedor_nombre` y `destinatario` (copiados al publicar), `estado`, `modo`, `ronda` (ofertas del proveedor recibidas), `token_hash` (SHA-256, único, nulo si está revocado), `correo_estado` (`pendiente` / `enviado` / `fallido`), `correo_error`, `correo_en`, `fuera_de_limites` (bandera para el aprobador), `actualizado_en`. |
| `mensaje` | `id`, `sesion_id`, `autor` (`proveedor` / `agente` / `comprador` / `sistema`), `texto`, `ronda`, `oferta_id`, `clave_idempotencia`, `creado_en`. Único (`sesion_id`, `clave_idempotencia`). |
| `oferta` | `id`, `sesion_id`, `autor` (`proveedor` / `agente` / `comprador`), `ronda`, `valores` (JSONB: precio por línea y valor por palanca, como texto decimal), `utilidad`, `valida`, `origen` (`formulario` en N1; `texto` llega en N2), `fuera_de_limites_confirmada`, `creado_en`. |
| `bitacora` | `id`, `fecha`, `actor_tipo` (`comprador` / `proveedor` / `agente` / `sistema`), `actor_id`, `actor_nombre`, `accion`, `evento_id`, `sesion_id`, `detalle` (JSONB). La migración da al usuario `negociacion` solo `INSERT` y `SELECT`. |
| `proveedor` | Copia local: `id`, `nombre`, `contacto_nombre`, `contacto_email`, `activo`, `actualizado_en`. |
| `servicio` | Copia local del catálogo: `codigo`, `nombre`, `categoria`, `unidad`, `moneda`, `activo`. |
| `outbox`, `evento_procesado` | Los de `libs/comun`. |

**La foto** (`evento.foto`) guarda la fecha en que se tomó y, por línea, la referencia de `inteligencia` (`p25`, `p50`, `p75`, `metodo`, `version`, `confianza`, `observaciones`) o `null` si no hay referencia. En renovación también guarda los términos vigentes del contrato (`plazo_pago_dias`, `sla_disponibilidad`, `tope_aumento_pct`, `cuota_implementacion`, fechas y precio por línea).

---

## 5. Configuración del evento

### 5.1 Al crear

- **Compra:**
  - de 1 a 20 líneas, cada una con un servicio activo de la copia del catálogo y una cantidad;
  - de 1 a 10 proveedores activos con correo de contacto;
  - todas las líneas en la misma moneda, que es la del evento.
- **Renovación:**
  - recibe `proveedor_id` y `contrato_id`;
  - el contrato debe estar vigente;
  - las líneas, la moneda y el plazo salen del contrato;
  - el único proveedor es el del contrato.
- **Referencia:** por cada línea se consulta `GET /precios/servicios/{codigo}/referencia?cantidad=&plazo=` con el token del comprador.
  - Un 404 con código `sin_observaciones` significa que esa línea no tiene referencia: se acepta, y el comprador fija ideal y límite a mano.
  - Cualquier otro error, o más de 5 s sin respuesta de `inteligencia` o `proveedores`, da 503 («No se pudo consultar la referencia de precios; intente de nuevo») y no se crea nada.

### 5.2 Valores sugeridos

| Caso | Ideal | Límite |
|---|---|---|
| Línea de compra con referencia | P25 | P50 |
| Línea de renovación con referencia | `min(P25, vigente × 0.95)` | `min(P50, vigente × (1 + tope/100))` |
| Línea de renovación sin referencia | `vigente × 0.95` | `vigente × (1 + tope/100)` |
| Línea de compra sin referencia | sin sugerencia | sin sugerencia |
| Palanca no de precio, al activarla en renovación | sin sugerencia | el valor vigente del contrato |
| Palanca no de precio, al activarla en compra | sin sugerencia | sin sugerencia |

- Las sugerencias se redondean a la precisión de cada valor (§6.4).
- **Pesos por defecto:** precio 100. Al activar palancas, el comprador reparte los pesos.
- **Por defecto:** estilo `balanceado`, 6 rondas.

### 5.3 Validación al publicar

- Cada línea y cada palanca activa tiene ideal y límite, con `ideal ≠ límite`. La dirección se deduce de ellos: si el ideal es menor que el límite, menos es mejor.
- Los pesos de las palancas activas son enteros positivos y suman 100.
- **Rangos:**
  - precio > 0;
  - plazo de 1 a 60 meses;
  - plazo de pago de 0 a 180 días;
  - SLA de 0 a 100;
  - tope de 0 a 100;
  - cuota ≥ 0.
- **Renovación:** es un **error** que el límite de una línea supere `precio vigente × (1 + tope/100)`.
- Es un **aviso**, no un error, que el límite de una línea quede por encima de P75.
- La fecha límite está entre 1 hora y 60 días en el futuro.

---

## 6. Motor de concesiones (`negociacion/dominio/motor.py`)

Es un módulo puro, sin base de datos ni red:

`decidir(config, estado, oferta) → Decision`

- **`Decision`** es una de `Aceptar`, `Contraofertar(valores)`, `PedirAclaracion(lineas)` o `CerrarSinAcuerdo`, con su traza.
- En N1 no existe `Escalar`: el escalamiento llega solo por el botón y lo maneja la API. Los disparadores que salen del texto llegan en N2.
- **`config`** lleva las líneas y las palancas con ideal, límite y peso, `T` y β (firme 0.3, balanceado 0.6, flexible 1.0), y la referencia de cada línea.
- **`estado`** lleva la ronda `t` de esta oferta, la última contraoferta de la sesión (de quien sea) y `hay_mejor_oferta`.

### 6.1 Utilidad

- **Por palanca:** `uᵢ(x) = clamp((Lᵢ − x) / (Lᵢ − Iᵢ), 0, 1)`, con ideal `Iᵢ` y límite `Lᵢ`. Sirve para las dos direcciones; un valor mejor que el ideal vale 1.
- **Precio:** `u_precio = Σ gₗ · uₗ(pₗ)`, con `gₗ = cantidadₗ × Lₗ / Σ (cantidad × L)`.
- **Total:** `U = Σ (wᵢ / 100) · uᵢ`.
- **Validez:** una oferta es **válida** si ningún valor queda más allá de su límite. Una oferta inválida nunca se acepta, sin importar su utilidad.

### 6.2 Objetivo por ronda

- `t` es el número de esta oferta del proveedor (1, 2, …). Si el comprador siguió negociando a mano más allá de `T`, el motor usa `t = T`.
- `U_obj(t) = 1 − (t / T)^(1/β)`.
- Curva propia de cada palanca: `vᵢ(t) = Iᵢ + (1 − U_obj(t)) · (Lᵢ − Iᵢ)`. Solo llega al límite en la ronda `T`.

### 6.3 Decisión, en orden

1. **Cordura:** si algún precio queda fuera de `[0.1 × r, 10 × r]`, donde `r` es el P50 de la foto o, sin referencia, el límite de la línea, y la oferta no trae `confirmar_valores`, la respuesta es **PedirAclaracion** con esas líneas. La ronda no se consume.
2. **Contraoferta:** se calcula `oₜ` (§6.4).
3. **Aceptación:** si la oferta es válida y `U(oferta) ≥ U(oₜ)`, **Aceptar**.
4. **Última ronda:** si `t = T` y la oferta no es válida, **CerrarSinAcuerdo**. Una oferta válida en `t = T` siempre se acepta en el paso 3, porque `U_obj(T) = 0`.
5. **En otro caso,** **Contraofertar(oₜ)**. Si `t + 1 = T`, el mensaje pide la mejor y última oferta.

### 6.4 Contraoferta

1. **Tres puntos del camino:**
   - `s′`: la oferta con cada valor llevado a su límite si lo cruzaba;
   - `s̃`: igual a `s′`, pero en las palancas (y líneas) donde la oferta cruzaba el límite usa la curva propia `vᵢ(t)`. Así el agente **no contesta con el límite** salvo en la ronda `T`;
   - `I`: el ideal.
2. **Objetivo:** `objetivo = min(U_obj(t), U(última contraoferta de la sesión))`. Sin contraoferta previa, es `U_obj(t)`. El mínimo es lo que impide retroceder, aunque la contraoferta anterior la haya hecho el comprador.
3. **Búsqueda:** por bisección sobre el camino `s′ → s̃ → I`, que es lineal por tramos y donde `U` no baja, hasta encontrar el punto con `U = objetivo`. Si `U(s′) ≥ objetivo`, la contraoferta es `s′`.
4. **Redondeo:**
   - precios y cuota a centavos; meses y días a enteros; SLA a 0.01 puntos; tope a 0.1 puntos;
   - primero al valor más cercano;
   - si eso deja la utilidad por encima de la última contraoferta, se redondea hacia la oferta del proveedor;
   - los extremos de cada tramo ya están en su precisión (las ofertas se validan así y `vᵢ(t)` se redondea al más cercano), así que el redondeo nunca cruza un límite.

**Ejemplo del PRD §3.3** (una línea, ideal 30, límite 35, `T = 6`, β = 0.6, ofertas del proveedor por encima del límite): las contraofertas de las rondas 2, 4, 5 y 6 son 30.80, 32.54, 33.69 y 35.00. Es una prueba de tabla.

### 6.5 Presión competitiva y mensajes

- **`hay_mejor_oferta`:** lo calcula la capa de servicio. Es verdadero si otra sesión del mismo evento tiene una oferta válida de su proveedor con mayor utilidad que la oferta actual. Solo cambia la plantilla del mensaje, nunca los números.
- **Plantillas** (`textos.py`, en «usted»):
  - **Contraofertar:** agradece, presenta la propuesta, que el portal muestra como tarjeta, agrega «Hemos recibido propuestas más competitivas» si `hay_mejor_oferta`, y pide la mejor y última oferta si la siguiente es la ronda `T`.
  - **Aceptar:** la oferta queda como acuerdo tentativo, no vinculante hasta la adjudicación aprobada.
  - **PedirAclaracion:** «El precio de <servicio> parece fuera de lo usual. Si es correcto, márquelo como confirmado y envíelo de nuevo.»
  - **CerrarSinAcuerdo:** agradece; esta vez no fue posible llegar a un acuerdo.
  - **Sistema, modo comprador:** «Una persona del equipo de compras revisará su oferta y le responderá.»
  - **Sistema, escalamiento:** «Avisamos al equipo de compras; una persona le responderá aquí.»
- **Contenido prohibido:** ningún mensaje contiene límites, ideales, pesos, utilidades, la referencia ni datos de otros proveedores.

### 6.6 Traza

Cada decisión del motor se guarda en la bitácora (acción `motor.decision`) con:
- `u` por palanca y por línea, `U`, `U_obj`, `t`, `T` y β;
- el tramo y el parámetro de la bisección;
- las palancas que se tomaron de su curva propia y el redondeo aplicado;
- `hay_mejor_oferta`;
- la versión del motor (`VERSION_MOTOR`, una constante que sube con cada cambio de comportamiento).

### 6.7 Propiedades (Hypothesis)

- Nunca acepta una oferta inválida.
- Nunca contraoferta fuera de los límites.
- La utilidad de las contraofertas no sube de una ronda a otra, salvo cuando `U(s′)` ya supera el objetivo: entonces la contraoferta es `s′`.
- La aceptación coincide con la regla del §6.3.
- Todo valor de una contraoferta está en su precisión.
- En la ronda `T`, nunca contraoferta.
- `PedirAclaracion` no consume la ronda.

---

## 7. API del comprador (gateway: `/api/negociacion/`)

**Permisos:**
- el rol `comprador` crea y opera **todos** los eventos (es el equipo de compras, y la bitácora registra quién hizo cada cosa);
- `aprobador` y `admin` solo consultan;
- una prueba recorre todas las rutas con cada rol.

| Ruta | Qué hace |
|---|---|
| `GET /eventos` | Lista con filtros `estado` y `tipo`, y paginación. Por evento: folio, título, tipo, estado, fecha límite, número de sesiones, acuerdos y escaladas. |
| `POST /eventos` | Crea un borrador (§5.1). Responde con el evento, la foto y los valores sugeridos. |
| `GET /eventos/{id}` | Configuración, foto, avisos de validación y resumen de cada sesión. |
| `PATCH /eventos/{id}` | Solo en `Borrador` y con `version`; si otro lo cambió, 409. Si cambian las líneas o el plazo, se vuelve a consultar la referencia de las líneas afectadas. |
| `POST /eventos/{id}/publicar` | Valida (§5.3), crea las sesiones y sus tokens, manda los correos (§9.1) y responde **una sola vez** con el enlace de cada sesión. |
| `POST /eventos/{id}/cancelar` | Con `motivo`, en `Borrador` o `Abierto`. Revoca los tokens. |
| `GET /sesiones/{id}` | Mensajes, ofertas con su utilidad y validez, y la traza de cada decisión. |
| `POST /sesiones/{id}/control` | `{"accion": "tomar" | "devolver"}`. Al devolver, si la última oferta del proveedor no tiene respuesta, el agente la procesa en ese momento. |
| `POST /sesiones/{id}/respuestas` | Respuesta manual: `mensaje` con `contraoferta` opcional, o `aceptar` (la última oferta del proveedor), o `cerrar`. Exige modo `comprador` y `Idempotency-Key`. Una contraoferta o una aceptación fuera de límites exige `confirmar_fuera_de_limites` y pone `fuera_de_limites` en la sesión. |
| `POST /sesiones/{id}/invitacion` | Token nuevo (el anterior deja de servir), correo nuevo y el enlace visible una vez. Solo con el evento abierto y la sesión no final. |

Los errores usan el formato común de `libs/comun` (título, detalle en español y código).

---

## 8. Portal del proveedor (`/api/negociacion/portal/`)

### 8.1 Autenticación con el token

- **Encabezado:** `Authorization: Invitacion <token>`. El token es opaco, de 256 bits, y se genera con `secrets.token_urlsafe(32)`.
- **Búsqueda:** el servidor calcula su SHA-256 y busca la sesión.
- **Un solo rechazo:** si el token no existe, fue revocado o ya pasó la fecha límite del evento, la respuesta es siempre 401 «El enlace no es válido o ya venció». Los casos no se distinguen.
- **Enlace:** `URL_PUBLICA/portal#t=<token>`.
  - El fragmento no viaja al servidor ni en el `Referer`, y el gateway ya manda `Referrer-Policy: no-referrer`.
  - La SPA lo pasa a `sessionStorage` y lo borra de la barra con `history.replaceState`.
- **Logs:** nunca contienen el token ni el encabezado.

### 8.2 Rutas

| Ruta | Qué hace |
|---|---|
| `GET /portal/sesion` | La vista del proveedor (abajo). |
| `POST /portal/ofertas` | `{valores, nota?, confirmar_valores?}`: un precio por línea, un valor por palanca activa y una nota opcional de ≤ 2,000 caracteres. Responde con la vista. |
| `POST /portal/escalar` | Pasa la sesión a `Escalada` con modo `comprador`. Responde con la vista. |

- **La vista contiene:** folio, título, líneas (servicio, cantidad y unidad), los **nombres y unidades** de las palancas activas, fecha límite, rondas restantes (`max(T − ronda, 0)`), estado, si lo atiende una persona, el historial de mensajes y la última contraoferta.
- **La vista nunca contiene:** ideales, límites, pesos, utilidades ni la referencia. Una prueba recorre todas las respuestas del portal en una negociación completa y busca esos valores.
- **Reglas comunes de los POST:**
  - `Idempotency-Key` obligatorio: si se repite una clave, devuelve la vista actual sin volver a procesar;
  - 10 por minuto por sesión, contando sus propios mensajes en la base: 429 con `Retry-After`;
  - validación con los rangos del §5.3 y la precisión del §6.4, con mensajes en español por campo;
  - si la sesión ya terminó (antes de la fecha límite), 409 «La negociación terminó». El GET sigue funcionando.

### 8.3 Un turno (una transacción)

1. `SELECT … FOR UPDATE` sobre la sesión.
2. Revisa la idempotencia.
3. Revisa que el evento esté abierto, la sesión no esté en un estado final y no haya pasado la fecha límite.
4. Aplica el límite de tasa.
5. Guarda el mensaje del proveedor y su oferta. Con la primera oferta, la sesión pasa de `Invitada` a `Activa`.
6. **Si el modo es `comprador`:** aumenta la ronda, contesta con el mensaje del sistema y deja la oferta pendiente.
7. **Si el modo es `agente`:**
   - calcula `hay_mejor_oferta` y llama al motor;
   - guarda la traza en la bitácora, la respuesta del agente (mensaje y, si aplica, oferta) y el nuevo estado;
   - aumenta la ronda, salvo con `PedirAclaracion`.
8. Si la sesión quedó en un estado final y no queda ninguna sesión no final, el evento pasa a `EnEvaluacion` con una sola sentencia: `UPDATE … WHERE estado = 'Abierto' AND NOT EXISTS (…)`.
9. Hace commit y devuelve la vista.

Las acciones manuales del comprador usan el mismo bloqueo sobre la sesión.

### 8.4 Fecha límite

- Una tarea en segundo plano del servicio, iniciada en el `lifespan`, corre cada 60 s.
- Pasa a `Expirada` las sesiones no finales de los eventos abiertos con la fecha límite vencida, y lleva esos eventos a `EnEvaluacion`.
- Es idempotente y deja su registro en la bitácora.

---

## 9. Correos, eventos e integración

### 9.1 Correos de invitación

- **Envío:** `negociacion` los manda por SMTP con `smtplib` y `email.message.EmailMessage` dentro de `asyncio.to_thread`. No agrega dependencias. En desarrollo van a Mailpit (`mailpit:1025`).
- **Texto plano en «usted»:**
  - asunto «Invitación a negociar: <título> (<folio>)»;
  - qué se negocia, la fecha límite, el enlace y el aviso de que el enlace es personal.
- **Orden al publicar:**
  1. Una transacción crea las sesiones y sus tokens y pone el evento en `Abierto`.
  2. Fuera de la transacción, se manda cada correo.
  3. Otra transacción guarda en cada sesión `correo_estado` y `correo_error`, y registra `negociacion.invitacion_enviada` en el outbox.
- **Si un correo falla,** o el proceso se cae entre los pasos 1 y 3, el comprador lo ve en la sesión y usa «Reenviar invitación».

### 9.2 Eventos que publica `negociacion`

| Evento | Payload |
|---|---|
| `negociacion.publicada` | `folio`, `titulo`, `tipo`, `proveedores` (número), `actor` |
| `negociacion.cancelada` | `folio`, `titulo`, `motivo`, `actor` |
| `negociacion.invitacion_enviada` | `folio`, `proveedor` (nombre), `destinatario`, `estado` (`enviado` / `fallido`), `error`, `reenvio`, `actor` |

Los acuerdos y escalamientos no se publican en N1, porque nadie los consume todavía. `negociacion.adjudicada` llega en el incremento 4.

### 9.3 Cambios en `administracion`

- **Topología:** `COLA_ADMINISTRACION` agrega la clave `negociacion.*`, y `TIPOS_EVENTO` los tres tipos nuevos.
- **Actividad:**
  - `traducir` registra los tres eventos con origen `negociacion`;
  - una migración agrega ese origen al CHECK de `actividad`.
- **Correos:**
  - `negociacion.invitacion_enviada` también inserta un `CorreoEnviado` del tipo nuevo `negociacion`;
  - una migración amplía el CHECK de `tipo` y permite `usuario_id` nulo, porque el proveedor no es usuario de Keycloak;
  - es idempotente por `event_id`, igual que la actividad.
- **Panel:** el conteo de correos de 7 días los incluye sin más cambios.
- **Estado del sistema:** `negociacion` es el séptimo servicio que se revisa.

### 9.4 Copias locales

- **Cola:** `COLA_NEGOCIACION = Cola("negociacion.eventos", ("proveedor.*", "servicio.*"))`, en `topologia.py` y en `infra/rabbitmq/definitions.json`. La prueba existente vigila que coincidan.
- **Consumidor:** el común de `libs/comun` aplica `proveedor.actualizado` y `servicio.actualizado` a las copias, con el último estado recibido.
- **Llenado:**
  - en un stack nuevo, la cola existe antes de que alguien publique, así que se llena sola;
  - en uno existente, con `python -m proveedores.reproceso --todo` y después `--instantanea`. Se documenta en el README.

---

## 10. Interfaz (N1b)

### 10.1 Área del comprador

- **Menú:** sección «Negociación» con «Negociaciones» (`/negociaciones`, ícono `Handshake`). La ven `comprador`, `aprobador` y `admin`; solo `comprador` ve los botones que cambian algo.

| Página | Contenido |
|---|---|
| `/negociaciones` | Tabla: folio, título, tipo, estado, acuerdos sobre invitados, fecha límite e insignia «Escalada». Filtros por estado y tipo, paginación y «Nueva negociación». |
| `/negociaciones/nueva` | Título, fecha límite, rondas, estilo y plazo; líneas (servicio del catálogo y cantidad); proveedores invitados. Con `?proveedor=<id>&contrato=<id>`, la renovación con todo lo del contrato. Al guardar, crea el borrador y lleva a su editor. |
| `/negociaciones/:id` en `Borrador` | Editor de límites: por línea, la banda P25/P50/P75 de la foto con `ReferenciaPrecio` junto al ideal y el límite (o «Sin referencia de precio»). Las palancas se activan con interruptor y llevan peso, ideal y límite, con el total de pesos en vivo («Total: 105 de 100»). Errores y avisos junto a su campo. «Publicar» con `ConfirmarAccion`; después, un diálogo con cada enlace, «Copiar» y el aviso de que **solo se muestran ahora**. |
| `/negociaciones/:id` abierto, en evaluación o cancelado | Resumen de la configuración y la tabla de sesiones: proveedor, estado, quién atiende (agente o persona), ronda r de T, «Qué tan buena es para usted» (la utilidad de la última oferta en %), última actividad y correo (enviado o fallido) con «Reenviar invitación». «Cancelar negociación» con motivo. |
| `/negociaciones/:id/sesiones/:sid` | La conversación por ronda con su autor; la tabla de ofertas con los valores, la utilidad y si son válidas; en cada respuesta del agente, «¿Por qué respondió esto?» con la traza en palabras («Su oferta vale 41 % para usted; en esta ronda el agente busca al menos 49 %…»). Botones «Tomar el control» y «Devolver al agente», y el formulario manual: mensaje, contraoferta opcional (si sale de los límites, pide confirmación y avisa que el aprobador lo verá), «Aceptar la última oferta» y «Cerrar sin acuerdo». |

- **Actualización:** las dos vistas de supervisión usan `refetchInterval: 3000`, sin consultar en segundo plano. Una región `aria-live="polite"` anuncia solo «Nuevo mensaje del proveedor».
- **«Renovar»** (solo para `comprador`): en las filas de «Próximos vencimientos» del Tablero, en las alertas de vencimiento y en los contratos vigentes de la ficha del proveedor. Lleva a `/negociaciones/nueva?proveedor=…&contrato=…`.
- **Actividad:** el filtro agrega el origen «Negociación» y los textos de las tres acciones.
- **Correos:** agrega el tipo «Invitación a negociar»; sin `usuario_id`, la fila no enlaza a un usuario.
- **Glosario y ayuda:**
  - términos con `Termino`: palanca, ideal, límite, ronda y acuerdo tentativo;
  - el artículo «Cómo negocia el agente», que explica la utilidad, las concesiones por ronda y la regla de aceptación sin fórmulas.

### 10.2 Portal del proveedor (`/portal`)

- **Ruta:** va fuera de `marco`, como hermana en el router. Así no pasa por el `Layout`, que es el que hace `signinRedirect`.
- **Diseño:** encabezado sencillo, sin el menú interno.
- **Contenido:**
  - el resumen: líneas, palancas con su unidad, fecha límite y rondas restantes;
  - la conversación;
  - la tarjeta de la última propuesta del agente con «Aceptar esta propuesta», que llena el formulario con esos valores y pide confirmar;
  - el formulario de oferta: un campo por línea y por palanca con su unidad y ayuda, la nota con contador de caracteres, la casilla «Confirmo estos valores» cuando el agente pidió aclaración, «Enviar oferta» y «Hablar con una persona».
- **Pantallas propias:**
  - enlace inválido o vencido;
  - acuerdo tentativo, con el aviso de que no es vinculante hasta la adjudicación;
  - sin acuerdo;
  - atendido por una persona, que se actualiza cada 3 s.
- **Llamadas a la API:** `pedir` acepta un encabezado de autorización distinto, para mandar `Invitacion <token>`.
- **Idempotencia:** cada envío genera su `Idempotency-Key` con `crypto.randomUUID()` y la reutiliza si se reintenta.
- **Estándares:** «usted», 375 px sin desplazamiento horizontal y axe limpio en ambos temas.

---

## 11. Infraestructura

- `infra/postgres/negociacion.sh`: crea `negociacion_db`, `negociacion_dueno` y `negociacion`, igual que `inteligencia.sh`. Es idempotente, corre en volúmenes nuevos y se ejecuta a mano en uno existente.
- **Compose:**
  - el servicio `negociacion`, con migraciones al arrancar, healthcheck en `/salud/listo` y las variables `INTELIGENCIA_URL`, `PROVEEDORES_URL`, `SMTP_HOST`, `SMTP_PUERTO`, `SMTP_REMITENTE`, `URL_PUBLICA` y las de Keycloak;
  - sus contraseñas en `infra/.env.example`, nunca en un archivo versionado.
- **Gateway:** `location /api/negociacion/` con el mismo `limit_req` y las mismas cabeceras que las otras rutas de API. `/portal` lo sirve la SPA y la CSP actual alcanza.
- **CI y Dependabot:** los trabajos de Python y del stack incluyen el servicio, y Dependabot incluye su directorio.
- **Prueba de humo:** `GET /api/negociacion/eventos` responde, y un proveedor importado llega a la copia local.

---

## 12. Seguridad

- **Token de invitación:** se guarda solo su hash; su alcance es una sesión; vence en la fecha límite; se revoca al reenviar y al cancelar; nunca se registra en logs.
- **Lo que el proveedor nunca ve:** límites, ideales, pesos, utilidades, referencia ni datos de otros proveedores. Se prueba sobre todas las respuestas del portal y sobre todos los mensajes del agente.
- **Entrada:** validación estricta con Pydantic en cada frontera; nota de ≤ 2,000 caracteres; precisión de cada valor.
- **Abuso:** 10 POST por minuto por sesión en el portal, más el límite del gateway.
- **Bitácora:** de solo inserción por permisos de la base, no por convención.
- **Concurrencia:** `FOR UPDATE` por turno y bloqueo optimista en la configuración del evento.
- **Secretos:** ningún secreto en el repositorio ni en los logs; las credenciales viajan por variables de entorno.

---

## 13. Bots y simulación (`tools/simulador`)

- **Paquete:** `tools/simulador`, miembro del workspace de `uv`, como `tools/generador`.
- **Bots puros:** reciben la vista del portal y su verdad oculta y devuelven su siguiente acción: una oferta o reenviar la propuesta del agente para aceptarla.
- **El orquestador** `correr(…)` recibe clientes `httpx` (comprador y portal). No sabe si la app corre dentro del proceso o en un stack; N2 lo reutiliza contra el stack con el token de servicio.
- **Cada proveedor**, con su registro de `datos/verdad_oculta.json`:
  - precio de lista por línea = P50 × `nivel_precio`;
  - reserva = lista × (1 − `flexibilidad`);
  - primera oferta = lista × (1 + margen), con un margen que depende del estilo;
  - concesiones según el estilo:
    - duro: concede tarde;
    - flexible: concede pronto;
    - errático: pasos al azar con semilla, y a veces retrocede;
    - manipulador: en N1 se comporta como duro; sus ataques de texto llegan en N2;
  - en las palancas que no son precio, la reserva se sortea con la semilla entre el ideal y el límite del comprador;
  - acepta (reenvía la propuesta del agente) cuando no cruza ninguna de sus reservas.
- **Escenarios:** compras de 1 a 3 líneas con 2 a 5 proveedores de la misma categoría, y renovaciones de contratos vigentes, todos con semilla fija.
- **Prueba de simulación** (`services/negociacion/tests/test_simulacion.py`):
  - levanta la app con Testcontainers;
  - da la foto con un `httpx.MockTransport` que responde cuantiles de `datos/contratos.csv`;
  - corre los bots y exige **0 acuerdos fuera de límites**.
- **Reporte:** con `SIMULACION_REPORTE=<ruta>`, la prueba escribe `docs/qa/simulacion-negociacion.md` con los acuerdos fuera de límites, la tasa de acuerdo y el ahorro frente a la primera oferta, en total y por estilo, contra las metas del §1.

---

## 14. Calidad y validación

| Ámbito | Qué se prueba |
|---|---|
| Dominio | TDD, la tabla del PRD y las propiedades del §6.7. |
| API del comprador | Permisos por rol, bloqueo optimista, sugerencias y validación (incluida la regla de renovación), publicación con SMTP falso, reenvío que invalida el token anterior, cancelación y falla de `inteligencia` (503 sin datos a medias). |
| Portal | Token inválido, revocado o vencido (el mismo 401), idempotencia, 429, 409 al terminar, `PedirAclaracion` y su confirmación, y la ausencia de datos privados en todas las respuestas. |
| Concurrencia | Dos ofertas simultáneas en la misma sesión se procesan una tras otra y la ronda no se salta. |
| Control manual | Tomar, responder, aceptar fuera de límites con confirmación (y la bandera), devolver y que el agente no retroceda frente a la contraoferta del comprador. |
| Bitácora | `UPDATE` y `DELETE` con el usuario `negociacion` fallan por permisos. |
| Fecha límite | Las sesiones pasan a `Expirada` y el evento a `EnEvaluacion`; repetir la tarea no cambia nada. |
| Eventos (Testcontainers con PostgreSQL y RabbitMQ reales) | Copias locales, repetidos sin duplicar, `administracion` registra Actividad y Correos, y ningún tipo de evento queda sin binding. |
| Interfaz | Vitest y Testing Library por página (carga, vacío, error y datos), axe en cada página nueva y en ambos temas. |
| Revisión en navegador | `docs/qa/revision-negociacion.md`: los flujos del §15 y axe con contraste a 4 anchos y 2 temas, incluido el portal. |

---

## 15. Entrega

1. **N1a — Servicio de negociación**, en `feat/negociacion-determinista`. Termina con:
   - el servicio funcionando por API;
   - la simulación con su reporte;
   - `administracion` registrando Actividad y Correos;
   - la prueba de humo en verde.
2. **N1b — Negociación en la interfaz**, en una rama nueva desde `main` después de integrar N1a. Termina cuando la revisión en navegador recorre este flujo:
   1. crear una compra y una renovación (esta desde el Tablero);
   2. publicar y ver el correo en Mailpit;
   3. negociar desde el portal hasta un acuerdo tentativo;
   4. escalar otra sesión, tomar el control, responder y devolverla;
   5. cancelar un evento;
   6. ver todo en la bitácora, en Actividad y en Correos.

Cada plan se ejecuta con subagentes, con revisión por tarea, revisión final y fusión a `main`.

---

## 16. Documentación a actualizar

- **PRD:**
  - servicios y su mapa (`negociacion` en marcha);
  - eventos y colas (§2.2);
  - entidades de `negociacion` (§4.1);
  - matriz de permisos (comprador opera; aprobador y admin consultan);
  - nota en §3.3 sobre el camino `s′ → s̃ → I`, la curva propia por palanca y el redondeo, que precisan la contraoferta.
- **README:** el servicio y su puerto, las variables nuevas, el portal, el llenado de las copias con el reproceso y cómo correr la simulación.
- **`docs/qa/`:** `simulacion-negociacion.md` (N1a) y `revision-negociacion.md` (N1b).
