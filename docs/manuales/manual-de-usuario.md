# Manual de usuario de PluriOne

Parte del entregable 7. Esta es la primera versión, del 27/10/2026: las secciones del
comprador, del proveedor y del aprobador ya tienen sus pasos; lo marcado como **Pendiente** se
escribe del 21/11 al 28/11, según el [plan del proyecto](../plan-del-proyecto.md). La misma
información, más breve, está dentro de la aplicación, en el Centro de ayuda (botón «?» de la
barra superior).

PluriOne ayuda a una empresa a negociar con sus proveedores de servicios de TI: muestra cuánto se
paga normalmente por cada servicio, deja que un agente negocie por usted dentro de los límites que
usted fija y pide que otra persona apruebe las adjudicaciones grandes.

| Rol | Qué hace |
|---|---|
| Comprador | Consulta proveedores y precios, crea y publica negociaciones, las supervisa y adjudica |
| Aprobador | Aprueba o rechaza las adjudicaciones que superan el umbral o que salen de los límites |
| Proveedor | Negocia en el portal con el enlace de su invitación, sin cuenta |
| Administrador | Usuarios, catálogo, importación de datos, configuración y estado del sistema |

## 1. Cómo entrar

- **Personal de la empresa.** Entre con su usuario o correo y su contraseña. La primera vez, use
  el enlace del correo de invitación para definir su contraseña, o la contraseña temporal que le
  entregó administración: la plataforma le pedirá cambiarla.
- **Si la sesión se cierra sola.** Es por seguridad. Vuelva a iniciar sesión y regresará a la
  página donde estaba.
- **El menú.** A la izquierda, agrupado por áreas: Resumen, Proveedores, Inteligencia,
  Negociación, Sistema (solo administración) y Soporte. El botón de la esquina superior
  izquierda lo contrae a iconos; en pantallas pequeñas, ese mismo botón lo abre.
- **Su cuenta y el tema.** Su nombre y su rol están abajo a la izquierda; desde ahí cierra
  sesión. El tema claro, el oscuro o el del sistema se elige en la barra superior.
- **Proveedores.** No tienen cuenta: entran con el enlace personal de su invitación (sección 3).

## 2. Comprador

### 2.1 Revisar el Tablero

El Tablero es la primera pantalla. Muestra el gasto, los contratos por vencer, los proveedores en
riesgo y el ahorro potencial. La fila «Negociaciones» dice cuántas hay en cada estado y cuántas
sesiones escaladas esperan a una persona; cada número abre la lista filtrada. También muestra el
ahorro logrado: lo adjudicado frente a la primera oferta de cada proveedor ganador.

### 2.2 Consultar proveedores y precios

1. En **Proveedores**, busque por nombre o RFC, o filtre por categoría, estado o «En riesgo».
   Abra un proveedor para ver su puntuación (de 0 a 100), sus alertas, sus contratos y su
   desempeño mensual.
2. En **Precios**, elija un servicio, ajuste la cantidad y el plazo y pulse «Calcular». Verá el
   precio de referencia con tres valores: P25 (bajo), P50 (típico) y P75 (alto).
3. En **Alertas** están los sobreprecios, los contratos por vencer y los proveedores en riesgo.

### 2.3 Crear y publicar una negociación

1. En **Negociaciones**, pulse «Nueva negociación». Para renovar un contrato, use «Renovar» en el
   Tablero, en una alerta de vencimiento o en los contratos de la ficha del proveedor.
2. Escriba el título y la fecha límite, y revise las rondas (6 por defecto), el estilo del agente
   («Balanceado» por defecto) y el plazo del contrato.
3. Elija los servicios con su cantidad y los proveedores que invita (hasta 10). Pulse «Crear
   borrador».
4. En el borrador, revise el **ideal** y el **límite** de cada servicio junto a la banda
   P25 · P50 · P75. El límite es lo más que está dispuesto a pagar; el agente nunca lo revela.
   Si queda arriba del P75, verá un aviso.
5. Si le importan otros términos (plazo, plazo de pago, SLA, tope de aumento o cuota de
   implementación), actívelos y reparta 100 puntos de peso entre ellos y el precio.
6. Pulse «Guardar cambios», después «Publicar», y confirme. Cada proveedor recibe su enlace por
   correo; usted lo ve **una sola vez** para copiarlo. Si un proveedor lo pierde, use «Reenviar»
   en la tabla de sesiones: el enlace anterior deja de servir.

### 2.4 Supervisar e intervenir

- La negociación muestra una sesión por proveedor, con su estado, la ronda y qué tan buena es su
  última oferta para usted. Se actualiza sola cada pocos segundos.
- En cada sesión verá la conversación y las ofertas. En cada respuesta del agente,
  «¿Por qué respondió esto?» explica su decisión.
- Si el proveedor le escribió al agente con sus palabras, debajo de su mensaje verá qué entendió
  la plataforma («Interpretado: oferta · confianza 90 %») y, en cada respuesta, si la redactó el
  modelo de lenguaje o es una respuesta de plantilla.
- Con «Tomar el control» usted responde a mano: un mensaje, una contraoferta, aceptar la última
  oferta o cerrar sin acuerdo. Si lo que acepta o propone sale de sus límites, la plataforma le
  pide confirmarlo y lo marca para el aprobador. «Devolver al agente» le regresa la sesión.
- Si un proveedor pide hablar con una persona, su sesión aparece como «Escalada» hasta que usted
  la atienda y la devuelva.

### 2.5 Adjudicar

1. Cuando vence la fecha límite o terminan todas las sesiones, la negociación pasa a
   «En evaluación». La sección «Evaluación» ordena los acuerdos del mejor al peor, marca el
   «Recomendado» y explica «Por qué se recomienda».
2. Pulse «Adjudicar» en la fila del proveedor que elija. Si no es el recomendado, escriba la
   justificación.
3. La confirmación dice si la adjudicación será directa o irá a un aprobador, y por qué. Pulse
   «Confirmar».
4. Si ningún acuerdo le conviene, pulse «Declarar desierta», escriba el motivo y confirme. No se
   puede deshacer.

Con la negociación «Adjudicada», la sección «Resultado» muestra quién propuso, quién aprobó y el
folio del contrato, que ya aparece en el historial del proveedor.

## 3. Proveedor

### 3.1 Entrar con su enlace

Abra el enlace de su correo de invitación. Es personal: no lo comparta. Deja de servir al llegar
la fecha límite, si compras se lo reenvía o si se cancela la negociación. El portal muestra qué
se negocia, la fecha límite, cuántas rondas le quedan y la conversación con el agente.

### 3.2 Enviar una oferta

1. En «Su oferta», escriba el precio unitario de cada servicio y el valor de cada término que se
   negocia.
2. Si quiere, deje una nota para el equipo de compras. La lee una persona; no cambia su oferta.
3. Pulse «Enviar oferta». El agente le responde al momento: acepta, le hace una contraoferta o
   cierra sin acuerdo. Si un precio parece un error de captura, le pide confirmarlo antes de
   responder, y eso no gasta una ronda.
4. Para aceptar la última propuesta del agente, pulse «Aceptar esta propuesta», que llena el
   formulario, y después «Enviar oferta».

Si la negociación termina con un acuerdo, es tentativo: no es vinculante hasta que la empresa lo
adjudique y lo apruebe.

### 3.3 Escribirle al agente

En «Escríbale al agente» puede escribir con sus palabras una oferta, una pregunta o lo que
necesite, y pulsar «Enviar mensaje».

- Si su mensaje trae una oferta, la plataforma llena el formulario con lo que entendió. Revísela
  y pulse «Enviar oferta» para confirmarla: solo cuenta cuando usted la confirma.
- Si pregunta algo, el agente le contesta sin cambiar su oferta ni gastar una ronda.

### 3.4 Hablar con una persona

Pulse «Hablar con una persona» en cualquier momento. Una persona de compras atenderá su sesión.

### 3.5 El resultado

Cuando la negociación se adjudica o se declara desierta, recibe un correo con el resultado que le
toca, y también lo ve en su portal mientras su enlace siga vigente. Ninguno de los dos dice quién
ganó ni muestra montos.

## 4. Aprobador

### 4.1 Encontrar lo que espera su aprobación

En el Tablero, la fila «Negociaciones» marca «Por aprobar» con el número de propuestas que
esperan. Pulse ese número, o abra Negociaciones: su lista empieza en «Por aprobar» si hay
propuestas esperando.

### 4.2 Aprobar o rechazar

1. Abra la negociación. Verá la evaluación con la propuesta resaltada, su justificación, las
   marcas «Fuera de límites» y el motivo por el que requiere aprobación (por ejemplo, «Supera el
   umbral de aprobación»).
2. Pulse «Aprobar» para adjudicar, o «Rechazar» y escriba el motivo.

Al aprobar, la negociación queda «Adjudicada» y se registra el contrato. Al rechazar, vuelve a
«En evaluación» y compras puede proponer de nuevo o declararla desierta.

### 4.3 Reglas que conviene saber

- Una adjudicación va a un aprobador si su costo total supera el umbral (500,000 MXN, salvo que
  administración lo cambie) o si el acuerdo quedó fuera de los límites.
- Quien propone nunca aprueba su propia propuesta: aunque tenga los dos roles, no ve «Aprobar»
  ni «Rechazar» en ella.
- Si la propuesta cambió mientras la leía, la plataforma se lo dice y le pide revisar la nueva.

## 5. Administrador

**Pendiente.** Cada tema tiene ya su guía en el Centro de ayuda de la aplicación; aquí se
escribirá con pasos y capturas de pantalla.

### 5.1 Usuarios y roles

Pendiente.

### 5.2 Contraseñas y correos del sistema

Pendiente.

### 5.3 Actividad (bitácora) y su exportación

Pendiente.

### 5.4 Catálogo de servicios

Pendiente.

### 5.5 Importación de los datos del ERP

Pendiente.

### 5.6 Configuración: puntuación, adjudicación y modelo de precios

Pendiente.

### 5.7 Estado del sistema y Panel

Pendiente.

## 6. Preguntas frecuentes

Pendiente.

## Pendientes de este manual

- Capturas de pantalla de cada paso.
- La sección del administrador (5) y las preguntas frecuentes (6).
- Una revisión con una persona de compras de PluriOne antes de la capacitación (entregable 9).
