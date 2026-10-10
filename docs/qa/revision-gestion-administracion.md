# Revisión en navegador de "Operación del sistema"

- Fecha: 2026-10-09
- Commit revisado: `5e46212` (rama `feat/operacion-sistema`); correcciones en `e31cd9a` y `8be4d3e`
- Usuarios de prueba: `admin1` (rol admin) y `comprador1` (rol comprador, para el Centro de ayuda)
- Alcance: las pantallas nuevas del plan 2 (Panel, Actividad, Catálogo, Estado del sistema y Centro de
  ayuda), el foco en Importación y el recorrido completo de eventos de `proveedores` a la bitácora de
  `administracion`.

## Entorno y método

- **Stack completo** con `docker compose -f infra/docker-compose.yml up -d --build --wait` y la prueba
  de humo (`uv run python infra/smoke_test.py`): `OK: SPA, Keycloak, proveedores, administración y
  operación responden (60 proveedores).`
- **Gateway** (<http://localhost:8080>, con CSP): los flujos de la tabla siguiente. En las pantallas
  nuevas no hubo violaciones de CSP propias de la aplicación y todas las llamadas a `/api` respondieron
  200.
- **Servidor de Vite** (<http://localhost:5173>, sin CSP, con `StrictMode`): axe sobre la SPA. La CSP del
  gateway (`connect-src 'self'`) impide cargar axe, así que se revisó el mismo código en Vite.
- axe-core 4.10.2, reglas WCAG 2.0, 2.1 y 2.2 niveles A y AA, **con** la regla de contraste.
- Anchos: 375, 768, 1024 y 1440 px, en tema claro y en tema oscuro (`resize_window` con
  `colorScheme`; el tema de la aplicación está en "Sistema").
- Scroll horizontal: `document.documentElement.scrollWidth <= window.innerWidth`.
- La descarga del CSV se capturó dentro de la página (sin guardar el archivo): se interceptó
  `URL.createObjectURL` y el clic del enlace de descarga, y se leyeron los bytes del `Blob`.

## Flujos (gateway, 1440 px, tema claro)

| # | Flujo | Resultado |
|---|---|---|
| 1 | Menú | "Sistema" muestra Panel, Usuarios, Actividad, Catálogo, Estado del sistema, Correos, Importación y Configuración; "Soporte" muestra Centro de ayuda. Panel está activo solo en `/sistema`; en `/sistema/usuarios` solo Usuarios. |
| 2 | Catálogo: alta | `qa-rev-01` (en minúsculas) se guarda como `QA-REV-01`; aviso "Se dio de alta el servicio QA-REV-01."; el panel se cierra y el foco vuelve a "Nuevo servicio". Las etiquetas Categoría, Unidad y Moneda están asociadas a sus selectores (`aria-labelledby`). |
| 2 | Catálogo: edición | Cambio de nombre guardado; aviso "Se guardaron los cambios de QA-REV-01."; el foco vuelve a "Editar QA-REV-01". En edición, el código es de solo lectura. |
| 2 | Catálogo: servicio con contratos | En `SOP-MESA-TK`, Categoría y Moneda están deshabilitadas y su descripción accesible es "La categoría y la moneda no se pueden cambiar: el servicio ya tiene contratos y sus precios dependen de ellas."; Unidad sigue editable. Escape cierra el panel y el foco vuelve a "Editar SOP-MESA-TK". |
| 2 | Catálogo: desactivar y activar (con teclado) | El diálogo "¿Desactivar QA-REV-01?" abre con el foco en Cancelar; Tab y Enter confirman. El foco pasa a "Activar QA-REV-01"; Enter lo activa y el foco pasa a "Desactivar QA-REV-01". |
| 3 | Actividad: catálogo | Con "Catálogo", las cuatro acciones del paso 2 aparecen al instante ("Dio de alta el servicio QA-REV-01", "Editó…", "Desactivó…", "Activó…"), junto con las de `HUMO-SERV` de la prueba de humo. |
| 3 | Actividad: importación rechazada | Un CSV de servicios con 2 errores (código con espacios, categoría inventada) se rechaza en Importación con su tabla de errores, y la bitácora muestra "Intentó importar servicios del catálogo; el archivo tenía 2 errores" con resultado "Falló". |
| 3 | Actividad: filtros | Persona, tipo, desde y hasta quedan en la URL. El corte de fechas usa la hora de la Ciudad de México: el intento de las 12:03 a.m. del 10 de octubre no aparece con `hasta=2026-10-09` y sí con `hasta=2026-10-10`. |
| 3 | Actividad: exportar CSV | Nombre `actividad.csv`, tipo `text/csv`, empieza con el BOM `EF BB BF`, columnas `Fecha,Persona,Acción,Resultado,IP`, acentos correctos en UTF-8 y solo las filas de los filtros aplicados. El foco se queda en "Exportar CSV". |
| 4 | Estado del sistema | Los cinco servicios "Sano" con su tiempo (10–17 ms). Con Mailpit detenido, "Volver a comprobar" muestra "4 de 5 servicios sanos" y solo "Buzón de correo (Mailpit)" como "Caído" ("No respondió en 2 s."); los demás siguen "Sano". Mailpit se volvió a levantar. |
| 5 | Panel | Las cuatro tarjetas tienen datos (6 usuarios activos, 0 intentos fallidos, 0 servicios con problemas, 14 correos) y enlazan a Usuarios, Actividad de sesiones, Estado del sistema y Correos. La actividad reciente y las últimas importaciones coinciden con Actividad. |
| 6 | Centro de ayuda (`admin1`) | La búsqueda "contraseña temporal" encuentra 3 artículos (dos de administración) y aparecen las 6 preguntas frecuentes. El botón "?" de la barra superior lleva a `/ayuda`. |
| 6 | Centro de ayuda (`comprador1`) | La misma búsqueda encuentra solo "Entrar y moverse por la plataforma"; no aparecen el tema Administración ni sus 2 preguntas. `/ayuda/gestionar-usuarios` muestra "Acceso restringido". |
| 7 | Importación | Al pasar de paso, el foco va al título del paso nuevo ("2. Elija el archivo: …", "3. Resultado"). Al cargar la página en Vite (con `StrictMode`) el foco se queda en `<body>` (corrección `a2abd8a`, de la revisión de la Tarea 11). |

## Aplicación (Vite): axe

Violaciones de axe con contraste, en claro / oscuro. En las 48 combinaciones no hubo violaciones ni scroll
horizontal.

| Página | 1440 px | 1024 px | 768 px | 375 px | Scroll horizontal |
|---|---|---|---|---|---|
| Panel (`/sistema`) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | No |
| Actividad | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | No |
| Catálogo, con el panel de alta abierto | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | No |
| Estado del sistema | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | No |
| Centro de ayuda | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | No |
| Artículo "Dar de alta y administrar usuarios" | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | No |

## Hallazgos y su corrección

| # | Hallazgo | Causa | Corrección | Commit |
|---|---|---|---|---|
| H1 | Al pulsar "Limpiar filtros" en Actividad, el foco cae a `<body>` y quien usa teclado o lector de pantalla pierde su lugar (WCAG 2.4.3). El mismo patrón estaba en Usuarios, Proveedores, Catálogo ("Limpiar filtros") y Centro de ayuda ("Limpiar búsqueda"). | El botón solo se muestra mientras hay filtros: al limpiarlos se desmonta con el foco dentro. Las páginas no comparten componente. | Cada manejador mueve el foco, con una `ref`, a un control que sigue en pantalla: Actividad al selector "Persona"; Usuarios y Proveedores al campo de búsqueda (en Proveedores, los dos botones usan el mismo manejador); Catálogo al chip "Todas"; Ayuda al campo "Buscar en la ayuda". Cada página tiene una prueba que falló antes de la corrección (`toHaveFocus()` en el control esperado y la URL sin filtros). | `e31cd9a` |
| H2 | El enlace "Centro de ayuda" de la guía de uso va dentro de una frase y se distinguía casi solo por el color: contraste de 1.3:1 con el texto que lo rodea (`#0369A1` contra `#475569`) y peso 500 contra 400. axe lo aprueba (`link-in-text-block`) por la diferencia de peso, pero la señal es débil. Es el único enlace de la aplicación dentro de una frase. | Clases `font-medium text-accent hover:underline`: subrayado solo al pasar el ratón. | `underline underline-offset-2` siempre, conservando `font-medium text-accent`. Prueba en `GuiaUso.test.tsx`: el enlace tiene la clase `underline` (falló antes de la corrección). | `8be4d3e` |

## Verificación tras las correcciones

Repetida en el navegador por el controlador, en Vite, sobre `8be4d3e`.

- **H1:** corregido. Tras limpiar, la URL queda sin parámetros y el foco está en: Actividad, el selector
  "Persona"; Catálogo (`?categoria=nube&estado=inactivos`, sin resultados), el chip "Todas" con
  `aria-pressed="true"`; Usuarios (`?q=ana`), el campo "Buscar por nombre, usuario o correo"; Proveedores
  (`?q=zzz`, botón del estado vacío), el campo "Buscar por nombre o RFC"; Ayuda (`?q=usuarios`), el campo
  "Buscar en la ayuda", vacío.
- **H2:** corregido. El enlace tiene `text-decoration-line: underline`; axe en el Tablero con la guía:
  0 violaciones.

## No revisado

- **Lector de pantalla real (NVDA o VoiceOver).** Fuera del alcance de esta revisión; se cubre con axe y
  con pruebas de nombre y descripción accesibles.
- **axe sobre la SPA servida por el gateway.** La CSP impide cargar axe; se revisó el mismo código en
  Vite.
- **Abrir `actividad.csv` en Excel.** El archivo se verificó por sus bytes (BOM UTF-8, separador coma,
  acentos); no se abrió en Excel.
- **Pérdida de foco fuera del alcance de este plan.** `Paginacion.tsx` usa `disabled` en Anterior y
  Siguiente, en Proveedores el botón "Ir a la primera página" se desmonta al usarse y en Alertas
  "Quitar filtros" (estado vacío) se desmonta igual que los botones de H1. Proveedores muestra
  dos botones "Limpiar filtros" cuando no hay resultados (fila de filtros y estado vacío). Son anteriores
  a este plan; quedan anotados para otra tarea.
