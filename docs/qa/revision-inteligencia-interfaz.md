# Revisión en navegador de "Inteligencia en la interfaz" (Plan B2)

- **Fechas:** 2026-10-12 y 2026-10-13. La revisión se interrumpió cuando el equipo se reinició; se retomó con el stack levantado de nuevo.
- **Commit revisado:** `8626e87`, de la rama `feat/inteligencia-interfaz`. Las correcciones están en `3af4671`, `476cd30`, `864ff4f`, `b839ef4` y `99a4921`.
- **Usuarios de prueba:** `comprador1` (rol comprador) y `admin1` (rol admin). Sus contraseñas están en el realm de desarrollo y no se repiten aquí.
- **Alcance:**
  - las páginas que ahora muestran datos del servicio `inteligencia`: Tablero, Proveedores (lista y ficha), Precios, Ranking, Alertas con la campana, Configuración y la tarjeta "Datos y modelo" del Panel;
  - los pendientes de interfaz que cierra este plan: rutas diferidas, foco en alto contraste, guía por persona y el README sin `--password`.

## Entorno y método

- **Verificación previa:**
  - `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check` limpios. Las 451 pruebas (41 archivos) son de la corrida anterior a las correcciones de la revisión final; después de ellas, `npx vitest run` pasa con 472 pruebas en 43 archivos;
  - `uv run ruff check`, `ruff format --check`, `mypy` y `pytest services/inteligencia` (146 pruebas) limpios.
- **Tamaño del bundle:** el chunk principal bajó de 1,173.94 kB a 416.29 kB con las rutas diferidas. Recharts va en su propio chunk (347.52 kB) y Vite ya no avisa de chunks de más de 500 kB.
- **Stack y prueba de humo:** stack completo reconstruido con `docker compose -f infra/docker-compose.yml up -d --build --wait`. La prueba de humo `uv run python infra/smoke_test.py` respondió `OK: SPA, Keycloak, proveedores, administración, operación e inteligencia responden (60 proveedores).`
- **Gateway** (<http://localhost:8080>, con CSP): flujos de la tabla siguiente, comprobados con el texto de la página, consultas a `/api` desde la sesión y capturas.
- **Servidor de Vite** (<http://localhost:5173>, sin CSP):
  - axe-core cargado desde `/node_modules/axe-core/axe.min.js`, porque la CSP del gateway impide cargarlo allí;
  - reglas WCAG 2.0, 2.1 y 2.2, niveles A y AA, **con** la regla de contraste;
  - cada ruta se cargó en un `iframe` del mismo origen con el ancho de la prueba (375, 768, 1024 y 1440 px) y se revisó en tema claro y en tema oscuro (`prefers-color-scheme` emulado; el tema de la aplicación está en "Sistema").
- **Desplazamiento horizontal:** se considera correcto si `document.documentElement.scrollWidth <= window.innerWidth`.

## Flujos (gateway, tema claro)

| # | Flujo | Resultado |
|---|---|---|
| 1 | Tablero | Las cuatro cifras coinciden con `GET /api/inteligencia/tablero`: gasto anual $1,174.7 M MXN (+3.9 % contra hace 12 meses), 93 por vencer, 22 de 58 proveedores en riesgo y $26.0 M MXN de ahorro potencial. Se ven el gasto por categoría, la línea de 24 meses con "Ver los datos", los 10 próximos vencimientos, las 5 alertas principales y los mejores y peores proveedores con la distribución. Los enlaces llevan a Alertas, Proveedores en riesgo y Precios. |
| 2 | Campana | Nombre "Alertas: 390 activas" y número visible "99+". Las 5 primeras son las de severidad alta. Dentro de "media", los sobreprecios van de mayor a menor ahorro en MXN, en el mismo orden que `GET /precios/sobreprecios` (C-000414, C-000575, C-000574…). |
| 3 | Alertas | Con `?tipo=sobreprecio` hay 275, "Mostrando 1–25 de 275 alertas". Cada alerta lleva su severidad con texto, su proveedor y la explicación del ahorro. Hay un solo "Quitar filtros". |
| 4 | Proveedores | Ordenada por puntuación, la primera columna marca `aria-sort="descending"`. El número de alertas enlaza a `/alertas?proveedor=<id>`, con nombres como "21 alertas de Tecno Integrales S.A. de C.V.". El texto de los botones de orden es "Ordenar por Puntuación"; la parte "Ordenar por" es solo para lectores de pantalla. |
| 5 | Ficha del proveedor | Puntuación 93.0 de 100 con +2.8 puntos en 3 meses, "Últimos 12 meses: de 87.3 a 93.0" y "Alertas activas (21)". En Contratos, la columna "Precio vs. mercado" marca 17 líneas "Justo" y 17 "Sobre P75"; las 38 líneas de contratos no vigentes quedan sin comparar. |
| 6 | Precios | Con SAAS-CRM-PRO, el resultado dice para qué se calculó ("Precio por usuario al mes para una cantidad de 117 y un plazo de 12 meses"). La gráfica dibuja los 57 contratos sobre la banda P25–P75 y la línea P50, con su leyenda. Las dos tablas de datos ("Precio de cada contrato" y "Rango típico del mercado por mes") están en "Ver los precios de cada contrato". La tabla de contratos con sobreprecio enlaza a cada proveedor. A 375 px, elegir un servicio lleva el foco al título de su detalle. |
| 7 | Ranking | Pestaña por categoría con posición, puntuación, los cinco percentiles, meses de historial y tendencia. La explicación de contra quién se compara cada proveedor coincide con la regla del servicio. |
| 8 | Configuración (admin1) | Al entrar, la página avisó "El modelo promovido no está en uso": la versión 1 del entorno de desarrollo era anterior a `version_sklearn`. "Reentrenar modelo de precios" mostró "Entrenando el modelo de precios; puede tardar un minuto." y después "Versión 2: MAPE 8.3 % (línea base 9.3 %). Se promovió: ahora calcula el precio de referencia." El aviso desapareció y el modelo en uso pasó a ser la versión 2. Se cambiaron los pesos de SLA a 35 y de satisfacción a 10: el total mostró "Total: 105 de 100" a mitad del cambio y la página confirmó "Configuración guardada…" al llegar a 100. Después se regresó a los valores iniciales. |
| 9 | Actividad (admin1) | Con el filtro "Inteligencia" aparecen "Reentrenó el modelo de precios: versión 2, MAPE 8.3 %, promovido" (admin1) y la versión 1 automática. |
| 10 | Panel (admin1) | "Datos y modelo": 60 proveedores, 42 servicios, 1,601 contratos, 3,553 líneas de contrato, 2,980 registros de desempeño y 61 tipos de cambio; último dato recibido; "Modelo de precios: versión 2, MAPE 8.3 %." |
| 11 | Carga diferida | Al recargar una página se ve "Cargando…" un instante y luego la página. Cada página se descarga como un archivo aparte. |
| 12 | README | El comando del tema de inicio de sesión con `KC_CLI_PASSWORD` corre sin error desde PowerShell ("Logging into http://localhost:8080/auth as user admin of realm master"). En Git Bash es el mismo texto. |

## axe y desplazamiento horizontal por ancho

Se revisaron 12 vistas a 375, 768, 1024 y 1440 px, en claro y en oscuro (96 pasadas): Tablero; Proveedores; la ficha en Resumen, Contratos y Desempeño; Precios con un servicio; "Todos los sobreprecios"; Ranking; Alertas; la campana abierta; Configuración; y Panel.

| Resultado antes de las correcciones (commit `8626e87`) | Vistas |
|---|---|
| 0 violaciones, sin desplazamiento horizontal | Tablero, Proveedores, Todos los sobreprecios, Ranking, Alertas, Configuración y Panel, en los 4 anchos y los 2 temas |
| `aria-hidden-focus` en la línea de 12 meses del encabezado (defecto 5) | Las tres pestañas de la ficha, en los 4 anchos y los 2 temas |
| Desplazamiento horizontal de la página: 801 px a 375 y 1,065 px a 768 (defecto 6) | Precios con un servicio elegido |
| `aria-hidden-focus` en `#root` con el menú de la campana abierto | Campana abierta, en todos los anchos. No es un defecto de este plan: Radix oculta el resto de la página (`aria-hidden`) mientras el menú tiene el foco, y pasa igual con cualquier menú desplegable de la plataforma. |

No hubo ninguna violación de contraste en ningún ancho ni tema.

Después de las correcciones se repitieron las vistas afectadas (Tablero, Resumen de la ficha, Precios con un servicio y Panel, a 375, 768 y 1440 px): 0 violaciones y sin desplazamiento horizontal.

## Defectos encontrados y su corrección

| # | Defecto | Causa | Corrección | Commit |
|---|---|---|---|---|
| 1 | El eje horizontal del historial de precios era ilegible: 57 etiquetas de mes encimadas | Con su propio arreglo de datos en el eje de tiempo, la gráfica ponía una marca por contrato | Marcas mensuales tomadas de las bandas (`ticks`). Ahora hay 8 etiquetas a 1440 px y 3 a 375 px | `3af4671` |
| 2 | La banda P25–P75 se veía como una línea delgada | El eje vertical empezaba en 0 y los precios rondan 75–90 | `domain={["auto", "auto"]}` en el eje vertical, que ahora va de 45 a 105 | `3af4671` |
| 3 | En la tarjeta de "Próximos vencimientos" no se veían el proveedor, la fecha ni el monto: la tabla medía 1,330 px en 568 px | Las celdas de contrato (con todos sus servicios) y de proveedor no partían en líneas | `whitespace-normal` en esas celdas. A 1440 px la tabla cabe (513/513 px); a 1024 desplaza dentro de su tarjeta, sin mover la página | `476cd30` |
| 4 | "Último dato recibido: 12 oct 2026, 9:46 p.m.." llevaba punto doble | `formatoFechaHora` ya termina en "a.m." o "p.m." y se agregaba otro punto | Sin punto después de la fecha. La prueba exige que la tarjeta no contenga ".." | `864ff4f` |
| 5 | axe: un elemento enfocable dentro de un bloque `aria-hidden` en la ficha | Recharts 3 vuelve enfocable la gráfica (`accessibilityLayer`), y la línea de 12 meses es decorativa | `accessibilityLayer={false}` solo en esa línea. Las gráficas del Tablero y de Precios lo conservan | `b839ef4` |
| 6 | Precios con un servicio desplazaba la página en horizontal a 375 y 768 px | Debajo de `lg` la rejilla no tenía columnas definidas y su columna crecía al ancho mínimo del contenido | `grid-cols-1` (`minmax(0, 1fr)`) en la rejilla | `99a4921` |

- **Pruebas en jsdom:** los defectos 3, 4 y 6 tienen prueba, y cada una falló antes de su corrección. Las de 3 y 6 solo vigilan las clases, porque jsdom no calcula el diseño; su efecto se midió en el navegador.
- **Sin prueba en jsdom:** los defectos 1, 2 y 5 no la tienen, porque Recharts no dibuja en jsdom. Se comprobaron en el navegador después del commit.

## Pendientes

- La columna "Precio vs. mercado" de la ficha aparece cuando llega la comparación con el mercado, así que la tabla se reacomoda una vez al cargar.
- El primer acceso a cada página espera la descarga de su archivo sin un indicador, porque `HydrateFallback` solo cubre la carga inicial. Si un archivo no se descarga (por ejemplo, una pestaña vieja después de una actualización), se ve la pantalla de error de react-router, porque aún no hay un `errorElement` propio.
