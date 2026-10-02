# Revisión visual y de accesibilidad del Plan A (sistema de diseño y experiencia)

- Fecha: 2026-10-01
- Commit revisado: `3067de4` (rama `feat/experiencia-inteligencia`)
- Usuario de prueba: `comprador1` (rol Compras)
- Herramientas: panel de navegador de Claude; build de producción servida por el gateway
  (<http://localhost:8080>, con CSP) y servidor de Vite (<http://localhost:5173>) para inyectar
  axe-core desde `/node_modules/axe-core/axe.min.js`.
- axe: reglas WCAG 2.0, 2.1 y 2.2 niveles A y AA, **con** la regla de contraste (en jsdom no se
  calcula; en un navegador real sí).
- Scroll horizontal: `document.documentElement.scrollWidth <= window.innerWidth`.

## Verificaciones previas

| Verificación | Resultado |
|---|---|
| `npm run lint` | Sin errores |
| `npm run build` | Correcto; aviso de Vite por el chunk principal (> 500 kB, Recharts), ya registrado como menor |
| `npx vitest run` | 16 archivos, 192 pruebas, todas pasan |
| `docker compose -f infra/docker-compose.yml up -d --build --wait gateway` | Todos los contenedores sanos |
| `uv run python infra/smoke_test.py` | `OK: SPA, Keycloak y proveedores responden (60 proveedores).` |

## Build de producción (gateway, con CSP)

| Verificación | Resultado |
|---|---|
| Inicio de sesión de Keycloak, tema claro | Fondo marino, "PluriOne" sobre "Plataforma de Negociación" sin mayúsculas forzadas, botón "Iniciar sesión" en acento `#0369A1` con texto blanco |
| Inicio de sesión de Keycloak, tema oscuro | Igual, botón `#38BDF8` con texto oscuro |
| Errores de consola en Tablero, Proveedores y detalle, tras recargar con el tema oscuro guardado | Ninguno (ni de CSP ni de JavaScript) |
| Script previo al render `/tema.js` | Se carga y deja `html.dark` y `color-scheme: dark` cuando `plataforma-tema=oscuro` está guardado (sin destello del tema equivocado) |
| Fuentes | Fira Sans 400/500/600 cargadas desde el propio origen |
| Gráfica de desempeño | Línea visible, leyenda "Cumplimiento de SLA" y tooltip "sep 2025 Cumplimiento de SLA 98.62 %" (con unidad) |

## axe y scroll horizontal por ancho de pantalla (antes de las correcciones, commit `3067de4`)

Rutas revisadas en cada ancho, cada una en tema claro y en tema oscuro: Tablero, Proveedores,
Detalle (pestañas Resumen, Contratos y Desempeño), Ranking, Alertas, Precios (sobreprecios),
Precios con un servicio elegido, Importación y Configuración como comprador (muestran "Acceso
restringido") y una ruta inexistente.

| Ancho (px) | Resultado antes de las correcciones |
|---|---|
| 375 | Sin scroll horizontal en ninguna ruta. axe: `scrollable-region-focusable` en Detalle contratos y Detalle desempeño (claro y oscuro); el resto, sin violaciones. |
| 572 | Igual que 375. Un `color-contrast` en Proveedores oscuro **no se reprodujo**: axe midió durante la transición de color de 150 ms tras cambiar la clase `.dark`; repetido con 200 ms de espera, 0 violaciones. |
| 768 (759 efectivos) | **Scroll horizontal de página** en Proveedores, Detalle contratos y Detalle desempeño. axe: `scrollable-region-focusable` en contratos y desempeño. |
| 1024 | **Scroll horizontal de página** en Detalle contratos y Detalle desempeño (`scrollWidth` 1090 > 1024). |
| 1440 | Sin violaciones ni scroll horizontal en ninguna ruta. |

Menú lateral a 375 px: el botón "Mostrar u ocultar el menú" abre el panel deslizable; al elegir
"Ranking" navega y el panel se cierra; axe sin violaciones.

## Defectos encontrados y su corrección

Los defectos 1 a 3 se corrigieron cada uno con su prueba en jsdom (escrita antes y que falló) y en
su propio commit `fix(web)`. El defecto 4 es solo de documentación (README) y salió, sin prueba,
en el commit de este documento.

| # | Defecto | Causa | Corrección | Commit |
|---|---|---|---|---|
| 1 | Scroll horizontal de página a 768 y 1024 px (el diseño pide que solo las tablas desplacen dentro de su contenedor) | El `main` de `SidebarInset` es un elemento flex con `min-width: auto` y no se encoge: a 1024 px medía 834 px y, con los 256 px del menú, la página llegaba a 1090 px. | `min-w-0` en el `SidebarInset` de `Layout.tsx`. Prueba en `Layout.test.tsx`: el único `main` tiene la clase `min-w-0` (jsdom no mide el diseño). | `9d787d4` |
| 2 | axe `scrollable-region-focusable` (WCAG 2.1.1 Teclado) en Contratos y Desempeño del detalle | El contenedor con scroll de la tabla no tiene elementos enfocables dentro y con teclado no se puede desplazar. | El contenedor `[data-slot=table-container]` de `table.tsx` recibe `tabIndex={0}` y un anillo de foco visible con tokens (`focus-visible:ring-2 focus-visible:ring-ring`). Pruebas en `ProveedorDetalle.test.tsx`: el contenedor de las tablas de Contratos y de Desempeño tiene `tabindex="0"`. | `4ca9ef9` |
| 3 | El enlace profundo se perdía al pasar por el inicio de sesión: abrir `/precios` sin sesión llevaba a Keycloak y al volver caía en `/` (Tablero). Es anterior al Plan A; se corrige aquí por decisión del controlador. | `Layout.tsx` llamaba `signinRedirect()` sin estado y `onSigninCallback` reemplazaba la URL por la de retorno. | `signinRedirect({ state: ruta + parámetros })` en la redirección automática y en "Volver a iniciar sesión"; `onSigninCallback` restaura ese estado con `history.replaceState` y avisa al enrutador con `popstate` solo si es una ruta relativa segura (empieza con una sola `/`, sin `//` ni `/\`); en otro caso conserva el comportamiento anterior. Pruebas en `auth.test.ts` (restaura y dispara `popstate`; el enrutador real llega a la ruta; sin estado, estado que no es texto, URL absoluta, `//` y `/\` conservan solo la ruta actual) y en `Layout.test.tsx` (la redirección automática y el botón pasan la ruta y sus parámetros). | `c5d1e5e` |
| 4 | El comando `kcadm` del README fallaba en PowerShell 5.1 (comillas dobles internas) y en Git Bash (conversión de rutas) | PowerShell pierde las comillas dobles internas al llamar a un programa externo; Git Bash convierte `/opt/…` y `/tmp/…` en rutas de Windows. | README: variante de PowerShell sin comillas internas, variante de Git Bash con `MSYS_NO_PATHCONV=1` y la alternativa por la consola de administración (*Realm settings → Themes → Login theme*). Sin valores de contraseña. | `a32d7b1` |

Pruebas tras las correcciones: 16 archivos, 201 pruebas, todas pasan; `npm run lint` y
`npm run build` sin errores (192 antes de las correcciones).

## Nueva medición en navegador tras las correcciones (commit `a32d7b1`)

Servidor de Vite (<http://localhost:5173>), con `comprador1`, las mismas 12 rutas, en tema claro y
en tema oscuro, y axe con la regla de contraste. Tras cambiar el tema se esperaron 400 ms antes de
medir, para no capturar la transición de color de 150 ms (la causa del falso positivo de
`color-contrast` que se vio antes). Cada celda indica las violaciones de axe en
claro / oscuro; en ninguna ruta, ancho ni tema hubo scroll horizontal de página.

| Página | 375 px | 768 px | 1024 px | 1440 px |
|---|---|---|---|---|
| Tablero | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Proveedores | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Detalle, pestaña Resumen | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Detalle, pestaña Contratos | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Detalle, pestaña Desempeño | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Ranking | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Alertas | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Precios (sobreprecios) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Precios con un servicio elegido | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Importación (como comprador: "Acceso restringido") | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Configuración (como comprador: "Acceso restringido") | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Ruta inexistente | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

Esto confirma las correcciones 1 y 2: desaparecen el scroll horizontal de página a 768 y 1024 px
y `scrollable-region-focusable` en Contratos y Desempeño.

### Enlace profundo con inicio de sesión real (corrección 3)

Se borró la sesión de la SPA (las claves `oidc.*` de `sessionStorage`) y se abrió
`/proveedores/<id>?pestana=desempeno`. La carga inicial fue la devolución del inicio de sesión
(`/?state=…&session_state=…&iss=…&code=…`) y la SPA terminó en
`/proveedores/<id>?pestana=desempeno` con la pestaña "Desempeño" activa. Verificado.

## Qué no se pudo revisar y por qué

- **Importación y Configuración con rol admin.** Requieren `admin1`, que exige OTP en su primer
  inicio de sesión; con `comprador1` solo se vio "Acceso restringido". Quedan cubiertas por sus
  pruebas de jsdom (incluido axe en ambos temas).
- **Variante de PowerShell del README.** El implementador no pudo ejecutarla (su entorno es Git
  Bash); el residente ejecutó con éxito el comando equivalente sin comillas dobles internas.
- **Fuera del alcance de la medición.** Las pantallas de Keycloak solo se revisaron a la vista (sin
  axe registrado) y no hubo recorrido manual con teclado ni con lector de pantalla.
