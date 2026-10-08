# Revisión en navegador de "Claridad y acceso"

- Fecha: 2026-10-08
- Commit revisado: `e0ea3e8` (rama `feat/claridad-y-acceso`)
- Usuario de prueba: `admin1` (rol admin; ve también Importación y Configuración)
- Alcance: inicio de sesión de Keycloak con el tema nuevo (pantalla dividida) y todas las pantallas
  de la SPA con la guía, el menú que se explica solo y los términos con ayuda.

## Entorno y método

- **Gateway** (<http://localhost:8080>, reconstruido con `docker compose -f infra/docker-compose.yml
  up -d --build --wait gateway`): inicio de sesión de Keycloak, comportamiento bajo la CSP y
  verificación de que no se pide OTP.
- **Servidor de Vite** (<http://localhost:5173>, sin CSP): axe sobre la SPA. La CSP del gateway
  (`connect-src 'self'`) impide cargar axe, así que se revisó el mismo código en Vite.
- axe-core 4.10.2, reglas WCAG 2.0, 2.1 y 2.2 niveles A y AA, **con** la regla de contraste (en
  jsdom no se calcula; en un navegador real sí).
- Anchos: 375, 768, 1024 y 1440 px, en tema claro y en tema oscuro (`resize_window` con
  `colorScheme`).
- Scroll horizontal: `document.documentElement.scrollWidth <= window.innerWidth`.
- Método para el cambio de tema: dos corridas dieron `color-contrast` con los colores del tema
  contrario justo después de cambiar de tema (transición en curso); al repetir con 2 s de espera
  dieron 0. No es un defecto.

## Inicio de sesión de Keycloak (gateway)

Violaciones de axe con contraste, en claro / oscuro:

| Ancho (px) | axe claro / oscuro | Scroll horizontal | Contenido |
|---|---|---|---|
| 1440 | 0 / 0 | No | Marca, lema y los 4 puntos con su descripción |
| 1024 | 0 / 0 | No | Marca, lema y los 4 puntos con su descripción |
| 768 | 0 / 0 | No | Marca, lema y los 4 puntos (solo el título) |
| 375 | 0 / 0 | No | Marca y lema (los puntos se ocultan) |

- Foco visible al tabular: contorno sólido de 2 px `#0369A1` en usuario y contraseña.
- CSP del gateway: sin violaciones propias de la aplicación en la consola (solo el intento de
  cargar axe, que la CSP bloquea).

### Verificación sin OTP

`admin1` inicia sesión y entra directo al Tablero: no se pide OTP.

## Aplicación (Vite)

Violaciones de axe con contraste, en claro / oscuro. "1" es siempre la misma violación, `region`
(hallazgo H2); en ninguna celda hubo otra regla ni `color-contrast`.

| Página | 1440 px | 1024 px | 768 px | 375 px | Scroll horizontal |
|---|---|---|---|---|---|
| Tablero (con la guía) | 1 / 1 | 1 / 1 | 1 / 1 | 0 / 0 | No |
| Proveedores | 1 / 1 | 1 / 1 | 1 / 1 | 0 / 0 | No |
| Detalle: Resumen, Contratos y Desempeño | 1 / 1 (las 3 pestañas) | 1 / 1 | 1 / 1 | 0 / 0 (las 3 pestañas en oscuro) | No |
| Precios con un servicio (SAAS-CRM-ENT) | 1 / 1 | 1 / 1 | 1 / 1 | 0 / 0 | No |
| Ranking | 1 / 1 | 1 / 1 | 1 / 1 | 0 / 0 | No |
| Alertas | 1 / 1 | 1 / 1 | 1 / 1 | 0 / 0 | No |
| Importación (como `admin1`) | 1 / 1 | 1 / 1 | 1 / 1 | 0 / 0 | No |
| Configuración | 1 / 1 | 1 / 1 | 1 / 1 | 0 / 0 | No |

- A 375 px el menú lateral es un panel deslizable cerrado, por eso `region` no aparece.
- En Precios, "Siguiente paso" lleva a `/proveedores?categoria=licencia_saas`.

## Interacción (1440 px, tema claro)

| Comprobación | Resultado |
|---|---|
| Término "Ahorro potencial" en el Tablero, con teclado | Enter abre el diálogo con el nombre "Ahorro potencial" y su definición; Escape lo cierra y el foco vuelve al botón; Espacio también lo abre |
| Menú colapsado (Ctrl+B): ayuda emergente de "Ranking" | El título queda arriba (y = 136) y la descripción abajo (y = 152), con la misma x |
| "Ocultar guía" | La guía desaparece y el foco pasa a `#contenido` |
| Volver a mostrar la guía | En Ranking, menú de usuario, "Mostrar guía de uso": vuelve a la ruta `/` con la guía visible ("3 de 3 listos") |

## Hallazgos y su corrección

| # | Hallazgo | Causa | Corrección | Commit |
|---|---|---|---|---|
| H1 | En el inicio de sesión, el título "Inicie sesión en su cuenta" se parte en 2 líneas (73 px de alto) en los 4 anchos. Es un pendiente de la Tarea 2. | El encabezado del formulario de Keycloak es una rejilla 70/30 que reserva la columna estrecha para el selector de idioma, que este tema no muestra. | `.plataforma-login .pf-v5-c-login__main-header { grid-template-columns: minmax(0, 1fr); }` en `plataforma.css`: el título usa todo el ancho. No es comprobable en jsdom, así que no lleva prueba. | `04b5805` |
| H2 | axe `region` a 768 px o más, en ambos temas: la marca "PluriOne / Negociación con proveedores" del encabezado del menú lateral queda fuera de toda región. Es anterior a este plan (viene del Plan A). | `<nav aria-label="Principal">` envolvía solo los grupos de `SidebarContent`; `SidebarHeader` quedaba suelto en el contenedor del menú. | En `BarraLateral.tsx`, el `<nav aria-label="Principal">` envuelve `SidebarHeader` y `SidebarContent`, con `className="flex min-h-0 flex-1 flex-col"` para conservar la columna flex del menú (encabezado fijo, contenido con scroll). No se tocó `web/src/components/ui/`. Prueba en `Layout.test.tsx`: el enlace "PluriOne" está dentro de la navegación "Principal" (falló antes de la corrección). | `ebe5d60` |
| H3 | En la variante de re-autenticación del inicio de sesión (hay sesión SSO y Keycloak muestra el usuario intentado, por ejemplo con `prompt=login`): (1) axe `label`, porque el campo del usuario no tiene etiqueta; (2) scroll horizontal de página en todos los anchos (a 375 px la página medía 565 px). Se encontró después de la primera pasada y se corrige en esta misma tarea. | Ambos vienen del marcado copiado de `keycloak.v2` en `template.ftl`: (1) `<input id="kc-attempted-username" … readonly>` no tiene `aria-label`; (2) el `<span class="kc-tooltip-text">` dentro de `#reset-login` está `visibility: hidden` pero se sigue maquetando (`left: 160 %`, `white-space: nowrap`, unos 209 px de ancho) y ensancha la página. | (1) `aria-label="${msg("usernameOrEmail")}"` en ese campo. (2) `.plataforma-login .kc-tooltip-text { display: none; }` en `plataforma.css`; el botón conserva su `aria-label` y se le agrega `title="${msg('restartLoginTooltip')}"` para que quien usa ratón siga viendo la ayuda al pasar encima. El resto de la plantilla queda igual. No es comprobable en jsdom, así que no lleva prueba. | `690d5d9` |

Pruebas tras las correcciones: 22 archivos, 265 pruebas, todas pasan; `npm run lint` y
`npm run build` sin errores (el aviso de Vite por el tamaño del chunk principal ya existía).

## Verificación tras las correcciones

Repetida en el navegador por el controlador sobre los commits de las correcciones.

- **H1 (`04b5805`):** corregido. El título normal del inicio de sesión ocupa una línea (36 px de
  alto, 352 px de ancho) a 1024 y 1440 px. A 768 y 375 px se parte en dos líneas solo porque el
  ancho de texto de la tarjeta es de 294 y 279 px (menos de 352 px): ajuste natural de línea,
  aceptado. axe: 0 violaciones a 1440 claro, 1024 claro, 768 claro y 375 claro.
- **H2 (`ebe5d60`):** corregido. axe: 0 violaciones a 1440 claro, 1024 oscuro y 768 claro, con el
  menú colapsado (Ctrl+B) y en el panel móvil de 375 px (allí el enlace de la marca también queda
  dentro de la navegación "Principal"). Con una ventana de 500 px de alto, el contenido del menú
  sigue desplazándose (`overflow: auto`, 555 > 436 px).
- **H3 (`690d5d9`):** pendiente de verificación en navegador por el controlador.

## No revisado

- **Lector de pantalla real (NVDA o VoiceOver).** Fuera del alcance de esta revisión; se cubre con
  axe y con pruebas de nombre accesible.
- **axe sobre la SPA servida por el gateway.** La CSP (`connect-src 'self'`) impide cargar axe. Se
  revisó en Vite (mismo código) y en el gateway solo se confirmó que no hay violaciones de CSP
  propias de la aplicación.
