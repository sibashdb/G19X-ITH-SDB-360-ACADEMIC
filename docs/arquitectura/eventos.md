# Eventos entre servicios

Los servicios no comparten bases de datos: cuando algo cambia, el dueño del dato publica un evento
y quien lo necesita guarda su copia. La fuente de verdad de los tipos, las colas y sus enlaces es
`libs/comun/src/comun/topologia.py`; una prueba verifica que `infra/rabbitmq/definitions.json`
diga lo mismo y que todo evento que se publica llegue a alguna cola. La versión formal está en
[`asyncapi.yaml`](asyncapi.yaml) (AsyncAPI 3.0).

## Cómo viajan

- **Exchange `eventos`**, de tipo *topic*. La clave de enrutamiento es el tipo del evento (por
  ejemplo, `contrato.registrado`).
- **Outbox transaccional.** El evento se guarda en la tabla `outbox` en la misma transacción que
  el cambio. Un proceso del servicio (`RelayOutbox`) lo publica después, así que no hay cambio sin
  evento ni evento sin cambio.
- **Al menos una vez.** Un evento puede llegar dos veces. Por eso los consumidores son
  idempotentes: registran el `event_id` en `evento_procesado` (o en `actividad.clave_origen`) y
  saltan lo que ya procesaron.
- **Colas *quorum* con cola de fallidos.** Tras 5 entregas fallidas, el mensaje pasa a
  `<cola>.dlq` y el Estado del sistema lo avisa.
- **Qué hace el consumidor ante un error** (`libs/comun/src/comun/consumidor.py`):
  - un mensaje mal formado (`ValueError`: JSON inválido, payload que no cumple su forma) no se
    reintenta, porque no se arregla solo: va directo a la cola de fallidos;
  - cualquier otra excepción (una falla de la base de datos o de red, o un `KeyError` porque el
    dato que el evento referencia todavía no llega, como un proveedor que se importará después)
    espera 5 s y devuelve el mensaje a la cola. El consumidor nunca suelta su conexión por un
    mensaje, y tras 5 entregas fallidas RabbitMQ lo manda a la cola de fallidos.

**Sobre (igual en todos los eventos):**

| Campo | Contenido |
|---|---|
| `event_id` | UUID del evento; es la llave de idempotencia |
| `type` | Tipo del evento, igual a la clave de enrutamiento |
| `version` | Versión del payload (hoy, 1 en todos) |
| `occurred_at` | Fecha y hora ISO 8601 con zona |
| `correlation_id` | El `X-Request-ID` de la petición que lo originó |
| `payload` | Los datos del evento (tabla siguiente) |

## Colas

| Cola | Servicio | Claves que recibe |
|---|---|---|
| `inteligencia.eventos` | inteligencia | `proveedor.*`, `servicio.*`, `contrato.*`, `desempeno.*`, `tipo_cambio.*` |
| `administracion.actividad` | administracion | `importacion.*`, `servicio.*`, `configuracion.*`, `modelo.*`, `negociacion.*` |
| `negociacion.eventos` | negociacion | `proveedor.*`, `servicio.*` |
| `proveedores.eventos` | proveedores | `negociacion.adjudicada` |

## Tipos de evento

`actor` es siempre `{id, nombre}` de la persona que hizo el cambio (`id` es nulo para el sistema).

| Evento | Publica | Lo reciben | Payload | Para qué |
|---|---|---|---|---|
| `proveedor.actualizado` | proveedores (importación, reproceso) | inteligencia, negociacion | `id`, `rfc`, `nombre`, `tamano`, `categorias`, `contacto_nombre`, `contacto_email`, `activo` | Copias locales del proveedor |
| `servicio.actualizado` | proveedores (importación, catálogo, reproceso) | inteligencia, negociacion, administracion | `id`, `codigo`, `nombre`, `categoria`, `unidad`, `moneda`, `activo`. Si vino del catálogo, además `cambio` (`creado`, `actualizado`, `activado` o `desactivado`), `campos` y `actor` | Copias del catálogo y Actividad de quien lo cambió |
| `contrato.registrado` | proveedores (importación y adjudicación) | inteligencia | `id`, `proveedor_id`, `folio`, `rfc_proveedor`, `tipo`, `fecha_inicio`, `fecha_fin`, `moneda`, `plazo_pago_dias`, `sla_disponibilidad`, `tope_aumento_pct`, `cuota_implementacion` y `lineas` (`codigo_servicio`, `nombre_servicio`, `categoria`, `unidad`, `cantidad`, `precio_unitario`) | Historial de precios y condiciones. Un contrato que nace de una adjudicación lleva el mismo payload que uno importado |
| `desempeno.registrado` | proveedores (importación) | inteligencia | `proveedor_id`, `periodo`, `sla_cumplimiento_pct`, `tiempo_resolucion_h`, `incidentes_criticos`, `entregas_a_tiempo_pct`, `satisfaccion` | Puntuación del proveedor |
| `tipo_cambio.registrado` | proveedores (importación, reproceso) | inteligencia | `periodo`, `usd_mxn` | Llevar los montos en USD a MXN |
| `importacion.completada` | proveedores | administracion | `entidad`, `filas`, `registros`, `omitidos`, `actor` | Actividad de las importaciones |
| `importacion.rechazada` | proveedores | administracion | `entidad`, `errores`, `actor` | Actividad de los intentos fallidos |
| `configuracion.actualizada` | inteligencia | administracion | `cambios` (por campo, `anterior` y `nuevo`), `actor` | Actividad de los cambios de pesos, umbrales (de riesgo y de aprobación) e inflación |
| `modelo.entrenado` | inteligencia | administracion | `version`, `mape`, `mape_linea_base`, `cobertura`, `promovido`, `origen`, `actor` | Actividad de cada entrenamiento del modelo de precios |
| `negociacion.publicada` | negociacion | administracion | `folio`, `titulo`, `tipo`, `proveedores` (cuántos), `actor` | Actividad |
| `negociacion.cancelada` | negociacion | administracion | `folio`, `titulo`, `motivo`, `actor` | Actividad |
| `negociacion.invitacion_enviada` | negociacion | administracion | `folio`, `titulo`, `proveedor`, `destinatario`, `estado`, `error`, `reenvio`, `actor` | Actividad y página Correos |
| `negociacion.adjudicada` | negociacion (al aprobarse, o al adjudicar el comprador directamente) | proveedores, administracion | `folio`, `titulo`, `tipo`, `proveedor_id`, `proveedor` (nombre), `costo_total_mxn`, `contrato`, `aprobacion` (`directa` o `aprobada`), `actor`. `contrato` trae `folio` (`C-` y el folio de la negociación), `tipo`, `moneda`, `fecha_inicio`, `fecha_fin`, `plazo_pago_dias`, `sla_disponibilidad`, `tope_aumento_pct`, `cuota_implementacion` y `lineas` (`codigo_servicio`, `cantidad`, `precio_unitario`) | Contrato nuevo en `proveedores` y Actividad |
| `negociacion.desierta` | negociacion (cierre sin acuerdos, o el comprador la declara desierta) | administracion | `folio`, `titulo`, `motivo` (`sin_acuerdos` cuando la declara el sistema), `actor` | Actividad |
| `negociacion.resultado_enviado` | negociacion | administracion | Igual que `negociacion.invitacion_enviada`, más `resultado` (`adjudicada`, `no_elegida` o `desierta`) | Actividad y página Correos |

**El ciclo se cierra por eventos.** `proveedores` consume `negociacion.adjudicada` en la cola
`proveedores.eventos`: crea el contrato y sus líneas en una transacción que también guarda el
`event_id` en `evento_procesado`, y publica el `contrato.registrado` de siempre. `inteligencia`
lo recibe como cualquier contrato y lo suma al historial, así que cada negociación cerrada mejora
el precio de referencia de la siguiente. Si el folio ya tiene contrato, el evento no hace nada.
Un proveedor o servicio que `proveedores` aún no conoce se reintenta y, tras 5 entregas, va a
`proveedores.eventos.dlq`; un payload mal formado va directo. La adjudicación sigue válida en
`negociacion` en los dos casos.

## Llamadas HTTP síncronas

Solo donde la respuesta hace falta en el momento. Ninguna forma un ciclo.

| Origen → destino | Para qué | Si el destino no responde |
|---|---|---|
| negociacion → inteligencia | `GET /precios/servicios/{codigo}/referencia`: banda P25 · P50 · P75 para proponer el ideal y el límite | Responde 503 y el comprador reintenta. Si no hay contratos comparables (no es una falla), la línea queda sin referencia y el comprador fija sus valores |
| negociacion → inteligencia | `POST /adjudicacion/recomendacion`: ordena los acuerdos tentativos por costo total, desempeño, riesgo y SLA, con su explicación | Responde 503 y no guarda nada. Un evento en USD sin tipo de cambio registrado se responde en `inteligencia` con 409 `tipo_cambio_no_disponible`, y `negociacion` también lo responde como 503 |
| negociacion → proveedores | `GET /proveedores/{id}/contratos`: términos vigentes de un contrato que se renueva | Responde 503: la renovación no se crea y el comprador reintenta |
| negociacion → ia | `POST /interpretar`: el mensaje libre del proveedor, con las líneas y las palancas pero sin ideales, límites, pesos ni referencias. `POST /redactar`: la respuesta del agente a partir de la decisión del motor. Cada turno tiene hasta 18 s para las dos | El agente sigue sin el LLM: contesta con su plantilla, y a un mensaje libre le pide usar el formulario. Una caída de `ia` no cuenta como interpretación fallida |
| ia → Ollama | API compatible con OpenAI (`/v1/chat/completions`), con la respuesta en JSON Schema y temperatura 0 | `ia` responde 503 `llm_no_disponible`, o 502 `respuesta_invalida` si la respuesta no cumple el esquema |
| administracion → Keycloak | API de administración: usuarios, roles e inicios de sesión | Responde 503 («Sin conexión con Keycloak») y la página lo muestra |
| administracion → servicios, RabbitMQ y Mailpit | Salud de cada pieza para el Estado del sistema | La pieza aparece como «Sin respuesta» |
