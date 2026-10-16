# Revisión en navegador de la negociación y del portal del proveedor (N1b)

- **Fecha:** 2026-10-15.
- **Commit revisado:** `6341f73`, de la rama `feat/negociacion-interfaz`. Las correcciones están en `60c9c6d`, `cd7dd17`, `1996210`, `f5f3c95` y `48a0b1c`.
- **Usuarios de prueba:** `comprador1` (rol comprador), `aprobador1` (rol aprobador) y `admin1` (rol admin). Sus contraseñas están en el realm de desarrollo y no se repiten aquí. La persona que hizo la revisión inició cada sesión en el panel del navegador; las contraseñas no pasaron por el agente.
- **Alcance:**
  - la interfaz de la negociación: lista, nueva compra, renovación, editor del borrador, publicación, supervisión de sesiones, respuesta manual, reenvío y cancelación;
  - el portal del proveedor;
  - «Renovar» desde el Tablero;
  - la huella en la bitácora, en Actividad y en Correos.

## Entorno y método

- **Verificación previa** (desde `web/`): `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check` limpios.
  - En `6341f73` pasaron 600 pruebas en 53 archivos. Con las correcciones son 603 en 53 archivos.
  - El chunk principal mide 419.72 kB (126.93 kB con gzip).
- **Stack y prueba de humo:** stack completo reconstruido con `docker compose -f infra/docker-compose.yml up -d --build --wait`. La prueba de humo `uv run python infra/smoke_test.py` respondió `OK: SPA, Keycloak, proveedores, administración, operación, inteligencia y negociación responden (60 proveedores).`
  - La base `negociacion_db` tenía sus copias de proveedores (60) y servicios (42), y tres negociaciones canceladas de pruebas de humo anteriores.
- **Gateway** (<http://localhost:8080>, con CSP), con la imagen de `6341f73`:
  - los flujos de la tabla siguiente, comprobados con el texto de la página, el árbol de accesibilidad, las peticiones de red y la consola;
  - el portal se abrió en otra pestaña, sin sesión de Keycloak, con los enlaces del diálogo de publicación y de Mailpit (<http://localhost:8025>).
- **Servidor de Vite** (<http://localhost:5173>, sin CSP), con el código de la rama ya corregido:
  - axe-core cargado desde `/node_modules/axe-core/axe.min.js`;
  - reglas WCAG 2.0, 2.1 y 2.2, niveles A y AA, **con** la regla de contraste;
  - cada vista se cargó en un `iframe` del mismo origen con el ancho de la prueba (375, 768, 1024 y 1440 px), en tema claro y en tema oscuro (`prefers-color-scheme` emulado; el tema de la aplicación está en «Sistema»);
  - aquí se volvieron a comprobar las cinco correcciones, porque la imagen del gateway no las incluye.
- **Desplazamiento horizontal:** se considera correcto si `document.documentElement.scrollWidth <= window.innerWidth`.
- **Datos que deja la revisión:**
  - NEG-2026-0004 (compra, cancelada, con dos acuerdos tentativos);
  - NEG-2026-0005 (renovación de C-000302, en evaluación);
  - NEG-2026-0006 «QA editor con palanca» (abierta, con una sesión escalada).

## Flujos (gateway, tema claro)

| # | Flujo | Resultado |
|---|---|---|
| 1 | Negociaciones | **comprador1** ve las tres negociaciones de la prueba de humo y «Nueva negociación». Con el filtro «Borrador», la lista vacía dice «Ninguna negociación con estos filtros» y ofrece «Quitar filtros». La lista vacía sin filtros no se pudo ver porque ya había datos (la cubre su prueba en jsdom). **aprobador1** no ve: «Nueva negociación»; «Renovar» en el Tablero; «Reenviar» ni «Cancelar negociación» en una negociación abierta; «Tomar el control» ni el formulario de respuesta en una sesión escalada. |
| 2 | Crear una compra | NEG-2026-0004 «QA compra de licencias y nube»: 500 de «Mantenimiento de equipos de cómputo» y 200 de «Soporte de segundo nivel - ticket». Se invitó a tres proveedores, buscados por «Azteca» y mostrados en «3 de 10 proveedores elegidos». Al crear, se abre el editor. |
| 3 | Editor del borrador | Cada línea muestra su banda P25 · P50 · P75 y propone como ideal el P25 y como límite el P50, en centavos. Al activar «Plazo de pago» con peso 20, el total cambia en vivo a «Total: 120 de 100 · Los pesos deben sumar 100»; con 80/20 vuelve a «Total: 100 de 100». Con un límite de $600.00 en la segunda línea (P75 $556.58) aparece el aviso «pagaría más que en tres de cada cuatro contratos», que no impide publicar. Con cambios sin guardar, «Publicar» queda con `aria-disabled` y lo explica «Guarde los cambios antes de publicar». «Guardar cambios» confirma «Se guardaron los cambios.» |
| 4 | Publicar | El diálogo «Enlaces de invitación» muestra una vez cada enlace, con «Copiar» y el correo al que se envió. Al cerrarlo con «Listo», el foco pasa al contenido (el botón «Publicar» ya no existe) y el diálogo no vuelve. En Mailpit llegó un correo «Invitación a negociar: QA compra de licencias y nube (NEG-2026-0004)» por proveedor, con el mismo enlace `/portal#t=…` del diálogo. |
| 5 | Portal: negociar hasta un acuerdo | Red Azteca abrió su enlace. El `#t=…` desaparece de la barra y recargar sigue funcionando. Ofreció $400.00, $650.00 y 15 días, por encima de los límites. El agente contraofertó $298.89, $481.94 y 59 días (95 % para el comprador). «Aceptar esta propuesta» llena el formulario y deja el foco en «Enviar oferta». Al enviar, el portal muestra «Acuerdo tentativo», quita el formulario y anuncia «La negociación terminó con un acuerdo tentativo.» En la web, la sesión dice «Acuerdo tentativo · Ronda 2 de 6», y «¿Por qué respondió esto?» explica las dos respuestas con su utilidad y su objetivo. |
| 6 | Portal: precio raro | Nube Azteca ofreció $20.00, menos de la décima parte del P50. El agente pidió aclararlo y «Le quedan 6 rondas» no cambió. Volver a enviar sin marcar la casilla tampoco consumió la ronda. Con «Confirmo estos valores» marcada, la ronda avanzó («Le quedan 5 rondas») y el agente contraofertó, con «Hemos recibido propuestas más competitivas». Aquí apareció el defecto 1. |
| 7 | Escalar y atender a mano | Datos Azteca pulsó «Hablar con una persona»; en la tabla quedó «Escalada · Persona». Después ofreció $330.00, $580.00 y 30 días. Se le respondió con un mensaje y una contraoferta dentro de los límites ($310.00, $560.00 y 45 días; 43 %), que el portal mostró en 3 s o menos. «Devolver al agente» deja el foco en el mismo botón, ya con el texto «Tomar el control». Después se volvió a tomar el control y se usó «Aceptar la última oferta». Como la oferta ($330.00) salía del límite, se pidió confirmar con «Esto sale de sus límites»; con «Enviar de todos modos», la sesión quedó en «Acuerdo tentativo» con «Acuerdo fuera de sus límites: lo verá el aprobador». Aquí aparecieron los defectos 3 y 5. |
| 8 | Renovar desde el Tablero | «Renovar el contrato C-000302» (Infra Azteca, dos líneas en USD) abre «Renovar un contrato». Trae el título «Renovación C-000302», las líneas con su precio vigente y al proveedor como único invitado. El editor muestra «Precio vigente: USD 13.2261». Al activar «Plazo de pago» propone 15 días, el valor vigente, como límite. Se publicó como NEG-2026-0005. |
| 9 | Reenviar y cancelar | «Reenviar» pide confirmar y muestra el enlace nuevo de Nube Azteca una vez. El enlace anterior muestra «El enlace no es válido o ya venció», y el nuevo funciona al pegarlo en la misma pestaña. «Cancelar negociación», con motivo, deja NEG-2026-0004 en «Cancelada» y la sesión abierta en «Sin acuerdo»; después, el enlace nuevo tampoco sirve. Aquí apareció el defecto 4. |
| 10 | Bitácora, Actividad y Correos | **Bitácora:** la consulta de `negociacion_db` agrupa `evento.creado`, `evento.editado`, `evento.publicado`, `invitacion.enviada`, `invitacion.reenviada`, `oferta.recibida` (proveedor), `motor.decision` (agente), `sesion.escalada` (proveedor), `control.tomado`, `control.devuelto`, `respuesta.manual` y `evento.cancelado`. **Actividad (admin1):** el filtro «Negociación» lista «Publicó la negociación … con 3 proveedores», cada «Envió a … la invitación a negociar», «Reenvió a …» y «Canceló la negociación …: Revisión QA: se cierra la prueba.» **Correos:** lista cada «Invitación a negociar» con su destinatario, quién la pidió y «Enviado». |
| 11 | Consola y red | No hay errores de CSP ni de JavaScript. Las llamadas a `/api/negociacion` responden 200, salvo dos casos esperados: un 422, el aviso «fuera de límites» de la aceptación del flujo 7, y los 401 del portal con enlaces viejos o cancelados. La consola solo registra la línea del navegador «Failed to load resource» de esos 401 y 422; ningún mensaje ni URL registrada contiene el token. |

**Además, sobre el portal:**
- `/portal#t=…` no inicia el flujo de Keycloak: después de `/portal` no hay ninguna petición a `/auth`.
- Con un enlace rechazado hay una sola consulta y no se reintenta.
- El servicio responde el mismo 401 («El enlace no es válido o ya venció.») con un enlace corto, con uno de 43 caracteres y sin encabezado.
- Las consultas del portal solo llevan `Authorization: Invitacion …`, y responden 200 sin sesión de Keycloak.
- Las ofertas llevan `Idempotency-Key`: `crypto.randomUUID` funciona porque `localhost` es un contexto seguro.

## axe y desplazamiento horizontal por ancho

Se revisaron 12 vistas a 375, 768, 1024 y 1440 px, en claro y en oscuro (96 pasadas):
- Negociaciones;
- Nueva negociación como compra y como renovación;
- el editor del borrador con «Tope de aumento anual» activo;
- una negociación abierta con su sesión;
- una negociación cancelada con tres sesiones;
- una sesión con acuerdo y sus explicaciones;
- una sesión con el formulario de respuesta manual y la contraoferta abierta;
- el portal activo sin ofertas, con la propuesta del agente, en acuerdo tentativo y con un enlace inválido.

| Resultado | Vistas |
|---|---|
| 0 violaciones, 0 nodos de contraste sin resolver, sin desplazamiento horizontal | Las 12 vistas, en los 4 anchos y los 2 temas |
| Sin violación de axe, pero sin ningún encabezado (defecto 5) | Portal con un enlace inválido, antes de `48a0b1c`. Después: h1 «Portal de proveedores» y 0 violaciones en los 4 anchos y los 2 temas |

## Defectos encontrados y su corrección

| # | Defecto | Causa | Corrección | Commit |
|---|---|---|---|---|
| 1 | Cuando el agente pedía aclarar un precio raro, el portal vaciaba el formulario. Para marcar «Confirmo estos valores», el proveedor tenía que volver a escribir toda la oferta | Al responder bien la API, el formulario se limpiaba siempre, aunque la respuesta pidiera confirmar | Si la vista nueva trae `pide_confirmacion`, se conservan los valores y la nota, y el aviso dice «Revise su oferta: si es correcta, marque «Confirmo estos valores» y envíela de nuevo.» | `60c9c6d` |
| 2 | «…es la referencia del mercado del 15 oct 2026, 8:53 p.m..» llevaba punto doble | `formatoFechaHora` ya termina en «p.m.» y la frase agregaba otro punto (el mismo error que el defecto 4 de la revisión de inteligencia) | La fecha va entre paréntesis: «(consultada el 15 oct 2026, 9:43 p.m.).» | `cd7dd17` |
| 3 | Al escalar antes de ofertar, la conversación decía «Ronda 0» en la petición del proveedor y en el aviso | La etiqueta de ronda se mostraba siempre | La etiqueta solo aparece desde la ronda 1 | `1996210` |
| 4 | Al cerrar el diálogo del enlace reenviado, el foco caía en el contenido en vez de volver a «Reenviar» | El diálogo guardaba el elemento enfocado al abrirse. La respuesta llega mientras la confirmación aún se cierra con su animación, así que guardaba el botón de la confirmación, que luego desaparece | La tabla le pasa al diálogo el botón «Reenviar» de la fila. En el navegador, el foco vuelve a «Reenviar la invitación a Soluciones del Norte S.A. de C.V.» | `f5f3c95` |
| 5 | El portal con un enlace inválido no tenía ningún encabezado | El estado vacío usa un párrafo como título, y sin sesión no se muestra el título de la negociación | h1 solo para lectores de pantalla: «Portal de proveedores» | `48a0b1c` |

- **Pruebas en jsdom:** los cinco defectos tienen prueba, y cada una falló antes de su corrección.
  - La del defecto 4 mueve el foco mientras llega la respuesta, porque jsdom no anima el cierre de la confirmación.
  - La del defecto 2 exige el texto «(consultada el …).».
- **Comprobación en el navegador:** las cinco correcciones se comprobaron otra vez en el servidor de Vite con NEG-2026-0006:
  - un precio de $1.00 conserva la oferta y muestra el aviso;
  - una sesión escalada antes de ofertar ya no dice «Ronda 0»;
  - el foco vuelve a «Reenviar»;
  - el editor dice «(consultada el … p.m.).»;
  - el portal inválido tiene su h1.

## Pendientes

- **Ayuda con textos inexactos.** Lo señaló la revisión de la Tarea 10 y queda para la revisión final de la rama:
  - «Cede de forma pareja» describe solo al estilo flexible, pero la interfaz también lo muestra en «Balanceado»;
  - la ayuda y el diálogo de enlaces nombran «Reenviar invitación», pero el botón dice «Reenviar».
- **Dos consultas rechazadas por un enlace.** Al pegar un enlace viejo en la misma pestaña, el portal hizo dos consultas que respondieron 401, en lugar de una. No hay ningún efecto visible.
- **La sesión expiró en Vite durante axe.** En el servidor de Vite, la sesión de la SPA expiró dos veces mientras corría axe. Varias copias de la aplicación en `iframe` de una misma pestaña comparten `sessionStorage` y el token de renovación, así que es un efecto del método de revisión y no se vio en el uso normal. Se volvió a entrar con la sesión única de Keycloak.
