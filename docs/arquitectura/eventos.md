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

## Tipos de evento

`actor` es siempre `{id, nombre}` de la persona que hizo el cambio (`id` es nulo para el sistema).

| Evento | Publica | Lo reciben | Payload | Para qué |
|---|---|---|---|---|
| `proveedor.actualizado` | proveedores (importación, reproceso) | inteligencia, negociacion | `id`, `rfc`, `nombre`, `tamano`, `categorias`, `contacto_nombre`, `contacto_email`, `activo` | Copias locales del proveedor |
| `servicio.actualizado` | proveedores (importación, catálogo, reproceso) | inteligencia, negociacion, administracion | `id`, `codigo`, `nombre`, `categoria`, `unidad`, `moneda`, `activo`. Si vino del catálogo, además `cambio` (`creado`, `actualizado`, `activado` o `desactivado`), `campos` y `actor` | Copias del catálogo y Actividad de quien lo cambió |
| `contrato.registrado` | proveedores (importación) | inteligencia | `id`, `proveedor_id`, `folio`, `rfc_proveedor`, `tipo`, `fecha_inicio`, `fecha_fin`, `moneda`, `plazo_pago_dias`, `sla_disponibilidad`, `tope_aumento_pct`, `cuota_implementacion` y `lineas` (`codigo_servicio`, `nombre_servicio`, `categoria`, `unidad`, `cantidad`, `precio_unitario`) | Historial de precios y condiciones |
| `desempeno.registrado` | proveedores (importación) | inteligencia | `proveedor_id`, `periodo`, `sla_cumplimiento_pct`, `tiempo_resolucion_h`, `incidentes_criticos`, `entregas_a_tiempo_pct`, `satisfaccion` | Puntuación del proveedor |
| `tipo_cambio.registrado` | proveedores (importación, reproceso) | inteligencia | `periodo`, `usd_mxn` | Llevar los montos en USD a MXN |
| `importacion.completada` | proveedores | administracion | `entidad`, `filas`, `registros`, `omitidos`, `actor` | Actividad de las importaciones |
| `importacion.rechazada` | proveedores | administracion | `entidad`, `errores`, `actor` | Actividad de los intentos fallidos |
| `configuracion.actualizada` | inteligencia | administracion | `cambios` (por campo, `anterior` y `nuevo`), `actor` | Actividad de los cambios de pesos, umbral e inflación |
| `modelo.entrenado` | inteligencia | administracion | `version`, `mape`, `mape_linea_base`, `cobertura`, `promovido`, `origen`, `actor` | Actividad de cada entrenamiento del modelo de precios |
| `negociacion.publicada` | negociacion | administracion | `folio`, `titulo`, `tipo`, `proveedores` (cuántos), `actor` | Actividad |
| `negociacion.cancelada` | negociacion | administracion | `folio`, `titulo`, `motivo`, `actor` | Actividad |
| `negociacion.invitacion_enviada` | negociacion | administracion | `folio`, `titulo`, `proveedor`, `destinatario`, `estado`, `error`, `reenvio`, `actor` | Actividad y página Correos |

**Planeado, incremento 4′:** `negociacion.adjudicada`, para que `proveedores` registre el contrato
nuevo e `inteligencia` lo sume al historial. Así, cada negociación cerrada mejora el precio de
referencia de la siguiente.

## Llamadas HTTP síncronas

Solo donde la respuesta hace falta en el momento. Ninguna forma un ciclo.

| Origen → destino | Para qué | Si el destino no responde |
|---|---|---|
| negociacion → inteligencia | `GET /precios/servicios/{codigo}/referencia`: banda P25 · P50 · P75 para proponer el ideal y el límite | Responde 503 y el comprador reintenta. Si no hay contratos comparables (no es una falla), la línea queda sin referencia y el comprador fija sus valores |
| negociacion → proveedores | `GET /proveedores/{id}/contratos`: términos vigentes de un contrato que se renueva | Responde 503: la renovación no se crea y el comprador reintenta |
| administracion → Keycloak | API de administración: usuarios, roles e inicios de sesión | Responde 503 («Sin conexión con Keycloak») y la página lo muestra |
| administracion → servicios, RabbitMQ y Mailpit | Salud de cada pieza para el Estado del sistema | La pieza aparece como «Sin respuesta» |
