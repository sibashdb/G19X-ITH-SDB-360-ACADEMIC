# Modelo de datos

Un diagrama entidad-relación por servicio, generado de los modelos de SQLAlchemy al 19/10/2026
(las migraciones de Alembic de cada servicio crean exactamente estas tablas). Ningún servicio lee
la base de otro: los datos compartidos viajan por eventos y cada quien guarda su copia.

Convenciones de los diagramas: `PK` llave primaria, `FK` llave foránea, `UK` valor único; los
montos son `numeric` (nunca punto flotante) y las fechas con hora, `timestamptz`. Todas las
tablas `outbox` tienen la misma forma: guardan el evento en la misma transacción que el cambio, y
un proceso del servicio lo publica en RabbitMQ.

## proveedores (`proveedores_db`)

La fuente de verdad de los datos maestros: proveedores, catálogo de servicios, contratos con sus líneas, desempeño mensual y tipo de cambio. Los datos llegan por la importación de CSV (el adaptador del ERP simulado), por la edición del catálogo o, en el caso de un contrato, por una adjudicación aprobada en `negociacion`; cada cambio se publica como evento con el `outbox`. `evento_procesado` hace idempotente al consumidor de `negociacion.adjudicada`.

```mermaid
erDiagram
  proveedor ||--o{ contrato : "proveedor_id"
  proveedor ||--o{ registro_desempeno : "proveedor_id"
  contrato ||--o{ linea_contrato : "contrato_id"
  servicio_catalogo ||--o{ linea_contrato : "servicio_id"
  outbox {
    uuid id PK
    string tipo
    int version
    jsonb payload
    string correlation_id
    timestamptz ocurrido_en
    timestamptz publicado_en
  }
  proveedor {
    uuid id PK
    string rfc UK
    string nombre
    string tamano
    array categorias
    string contacto_nombre
    string contacto_email
    bool activo
    timestamptz actualizado_en
  }
  servicio_catalogo {
    uuid id PK
    string codigo UK
    string nombre
    string categoria
    string unidad
    string moneda
    bool activo
  }
  tipo_cambio {
    date periodo PK
    numeric usd_mxn
  }
  evento_procesado {
    string event_id PK
    string tipo
    timestamptz procesado_en
  }
  contrato {
    uuid id PK
    string folio UK
    uuid proveedor_id FK
    string tipo
    date fecha_inicio
    date fecha_fin
    string moneda
    int plazo_pago_dias
    numeric sla_disponibilidad
    numeric tope_aumento_pct
    numeric cuota_implementacion
  }
  registro_desempeno {
    uuid id PK
    uuid proveedor_id FK
    date periodo
    numeric sla_cumplimiento_pct
    numeric tiempo_resolucion_h
    int incidentes_criticos
    numeric entregas_a_tiempo_pct
    numeric satisfaccion
  }
  linea_contrato {
    uuid id PK
    uuid contrato_id FK
    uuid servicio_id FK
    numeric cantidad
    numeric precio_unitario
  }
```

Únicas compuestas: `registro_desempeno` (proveedor_id, periodo).

## administracion (`administracion_db`)

La Actividad (`actividad`) es una bitácora de solo inserción: el usuario de la aplicación no puede actualizar ni borrar filas, y `clave_origen` evita duplicar un evento que llega dos veces. `correo_enviado` alimenta la página Correos (su `tipo` es `invitacion`, `restablecimiento`, `negociacion` o `resultado_negociacion`) y `cursor_eventos` recuerda hasta dónde se leyeron los inicios de sesión de Keycloak.

```mermaid
erDiagram
  actividad {
    uuid id PK
    timestamptz fecha
    string actor_id
    string actor_nombre
    string tipo
    string objeto_tipo
    string objeto_id
    string objeto_nombre
    jsonb detalle
    string resultado
    string ip
    string origen
    string clave_origen UK
  }
  correo_enviado {
    uuid id PK
    timestamptz fecha
    string tipo
    string destinatario
    string usuario_id
    string solicitado_por
    string estado
    string error
  }
  cursor_eventos {
    string nombre PK
    timestamptz hasta
  }
```

## inteligencia (`inteligencia_db`)

Una copia local de lo que publica `proveedores` (sin llaves foráneas hacia otros servicios), más la configuración de la puntuación y de la adjudicación (`configuracion`, una sola fila: los pesos de la puntuación, los cuatro pesos de la recomendación de adjudicación y el umbral de aprobación en MXN) y el registro de modelos de precios (`modelo_benchmark`; los artefactos van en el volumen `modelos`). `evento_procesado` hace idempotente al consumidor.

```mermaid
erDiagram
  contrato ||--o{ linea_contrato : "contrato_id"
  configuracion {
    int id PK
    int peso_sla
    int peso_resolucion
    int peso_incidentes
    int peso_entregas
    int peso_satisfaccion
    int umbral_riesgo
    numeric inflacion_anual
    int adjudicacion_costo
    int adjudicacion_desempeno
    int adjudicacion_riesgo
    int adjudicacion_sla
    numeric umbral_aprobacion
    timestamptz actualizado_en
    string actualizado_por
  }
  contrato {
    uuid id PK
    string folio
    uuid proveedor_id
    string tipo
    date fecha_inicio
    date fecha_fin
    string moneda
    timestamptz recibido_en
  }
  desempeno {
    uuid proveedor_id PK
    date periodo PK
    numeric sla_cumplimiento_pct
    numeric tiempo_resolucion_h
    int incidentes_criticos
    numeric entregas_a_tiempo_pct
    numeric satisfaccion
  }
  evento_procesado {
    string event_id PK
    string tipo
    timestamptz procesado_en
  }
  modelo_benchmark {
    int version PK
    timestamptz entrenado_en
    string origen
    string actor_nombre
    int observaciones
    date datos_hasta
    numeric mape
    numeric mape_linea_base
    numeric cobertura
    numeric pinball
    bool promovido
    string artefacto
  }
  outbox {
    uuid id PK
    string tipo
    int version
    jsonb payload
    string correlation_id
    timestamptz ocurrido_en
    timestamptz publicado_en
  }
  proveedor {
    uuid id PK
    string rfc
    string nombre
    string tamano
    array categorias
    bool activo
  }
  servicio {
    uuid id PK
    string codigo UK
    string nombre
    string categoria
    string unidad
    string moneda
    bool activo
  }
  tipo_cambio {
    date periodo PK
    numeric usd_mxn
  }
  linea_contrato {
    uuid contrato_id PK,FK
    string codigo_servicio PK
    string categoria
    string unidad
    numeric cantidad
    numeric precio_unitario
  }
```

## negociacion (`negociacion_db`)

Un `evento` de negociación (compra o renovación) tiene sus líneas, sus palancas y una `sesion` por proveedor invitado. Cada sesión guarda sus ofertas (con su utilidad y si respetan los límites) y su conversación (`mensaje`). `bitacora` es de solo inserción, como los mensajes y las ofertas. Cada propuesta de adjudicación es una fila de `adjudicacion`: las rechazadas quedan como historial, guardan la foto completa de la recomendación de `inteligencia` y no se borran; la aplicación solo actualiza las columnas de la decisión (`estado`, `decidida_por_id`, `decidida_por_nombre`, `decidida_en`, `motivo_rechazo` y `contrato_folio`), con `GRANT UPDATE` por columna, al estilo de la ADR-006. `evento.foto` guarda la fecha de la consulta de precios y, en una renovación, los términos vigentes del contrato de origen; la banda P25 · P50 · P75 de cada línea queda en `linea.referencia`. `proveedor` y `servicio` son copias locales alimentadas por eventos. Del enlace de invitación solo se guarda el hash (`token_hash`).

```mermaid
erDiagram
  evento ||--o{ linea : "evento_id"
  evento ||--o{ palanca : "evento_id"
  evento ||--o{ sesion : "evento_id"
  evento ||--o{ adjudicacion : "evento_id"
  sesion ||--o{ adjudicacion : "sesion_id"
  sesion ||--o{ adjudicacion : "recomendada_sesion_id"
  sesion ||--o{ oferta : "sesion_id"
  sesion ||--o{ mensaje : "sesion_id"
  oferta |o--o{ mensaje : "oferta_id"
  bitacora {
    uuid id PK
    timestamptz fecha
    string actor_tipo
    string actor_id
    string actor_nombre
    string accion
    uuid evento_id
    uuid sesion_id
    jsonb detalle
  }
  evento {
    uuid id PK
    string folio UK
    string tipo
    string titulo
    string moneda
    int plazo_meses
    string estado
    timestamptz fecha_limite
    int rondas_max
    string estilo
    uuid contrato_origen_id
    uuid proveedor_vigente_id
    array invitados
    jsonb foto
    string motivo_cancelacion
    string motivo_desierta
    string creado_por_id
    string creado_por_nombre
    timestamptz creado_en
    timestamptz publicado_en
    timestamptz cerrado_en
    int version
  }
  evento_procesado {
    string event_id PK
    string tipo
    timestamptz procesado_en
  }
  outbox {
    uuid id PK
    string tipo
    int version
    jsonb payload
    string correlation_id
    timestamptz ocurrido_en
    timestamptz publicado_en
  }
  proveedor {
    uuid id PK
    string nombre
    array categorias
    string contacto_nombre
    string contacto_email
    bool activo
    timestamptz actualizado_en
  }
  servicio {
    uuid id PK
    string codigo UK
    string nombre
    string categoria
    string unidad
    string moneda
    bool activo
  }
  linea {
    uuid id PK
    uuid evento_id FK
    int orden
    string codigo_servicio
    string nombre
    string unidad
    numeric cantidad
    numeric precio_vigente
    numeric ideal
    numeric limite
    jsonb referencia
  }
  palanca {
    uuid evento_id PK,FK
    string clave PK
    int peso
    numeric ideal
    numeric limite
  }
  sesion {
    uuid id PK
    uuid evento_id FK
    uuid proveedor_id
    string proveedor_nombre
    string destinatario
    string estado
    string modo
    int ronda
    string token_hash UK
    string correo_estado
    string correo_error
    timestamptz correo_en
    bool fuera_de_limites
    timestamptz resultado_avisado_en
    timestamptz actualizado_en
  }
  adjudicacion {
    uuid id PK
    uuid evento_id FK
    uuid sesion_id FK
    string propuesta_por_id
    string propuesta_por_nombre
    timestamptz propuesta_en
    uuid recomendada_sesion_id FK
    bool se_aparta
    string justificacion
    numeric costo_total
    numeric costo_total_mxn
    bool requiere_aprobacion
    array motivo_aprobacion
    jsonb recomendacion
    string estado
    string decidida_por_id
    string decidida_por_nombre
    timestamptz decidida_en
    string motivo_rechazo
    string contrato_folio
  }
  oferta {
    uuid id PK
    uuid sesion_id FK
    bigint secuencia
    string autor
    int ronda
    jsonb valores
    numeric utilidad
    bool valida
    string origen
    bool fuera_de_limites_confirmada
    timestamptz creado_en
  }
  mensaje {
    uuid id PK
    uuid sesion_id FK
    bigint secuencia
    string autor
    text texto
    int ronda
    uuid oferta_id FK
    string clave_idempotencia
    timestamptz creado_en
  }
```

Únicas compuestas: `linea` (evento_id, orden); `sesion` (evento_id, proveedor_id); `mensaje` (sesion_id, clave_idempotencia).

Valores de `evento.estado`: `borrador`, `abierto`, `en_evaluacion`, `pendiente_aprobacion`, `adjudicado`, `desierto` y `cancelado`. `adjudicacion.estado` es `pendiente`, `aprobada`, `rechazada` o `directa` (la que decide el comprador cuando no requiere aprobación), y `motivo_aprobacion` contiene `umbral`, `fuera_de_limites`, los dos o ninguno. `bitacora.actor_tipo` suma `aprobador`. `evento.motivo_desierta` queda vacío cuando el sistema declara desierta la negociación, y `sesion.resultado_avisado_en` marca a quién ya se le avisó el resultado.
