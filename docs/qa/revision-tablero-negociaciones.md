# Revisión en navegador del Tablero: negociaciones y ahorro logrado

- **Fecha:** 2026-10-23.
- **Rama y commits:** `feat/tablero-negociaciones`, con el código de `244360d`. Las imágenes del stack se construyeron con ese commit.
- **Usuario de prueba:** `comprador1` (rol comprador).
  - Su contraseña está en el realm de desarrollo y no se repite aquí.
  - La persona que hizo la revisión inició la sesión en el panel del navegador; la contraseña no pasó por el agente.
- **Alcance:** la fila «Negociaciones» del Tablero (capacidad 10, spec `docs/superpowers/specs/2026-10-22-tablero-negociaciones-design.md`):
  - la tarjeta «Ahorro logrado»;
  - la sección «Estado de las negociaciones»;
  - su estado de error.

## Entorno y método

- **Verificación previa:**
  - SPA (desde `web/`): `npm run lint`, `npx tsc -b` y `npm test -- --run` limpios, 831 pruebas en 62 archivos.
  - Python: `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy` limpios.
  - Suite de `negociacion`: 337 pruebas.
- **Stack:** `docker compose -f infra/docker-compose.yml up -d --build --wait` con los datos del entorno de desarrollo. La prueba de humo respondió «OK».
- **Datos:** `GET /api/negociacion/tablero` como `comprador1` dio:
  - **por estado:** 9 adjudicadas, 1 en evaluación, 3 desiertas y 10 canceladas;
  - **ahorro:** 308,851,200.00 MXN (43.3 %).
  - Se verificó a mano contra la base:
    - 7 adjudicaciones de la prueba de humo, cuyo proveedor abre en 6,749.94 y acuerda 3,073.14 por 1,000 unidades a 12 meses;
    - 2 negociaciones de la revisión de la adjudicación, sin concesión.
    - La suma de las primeras ofertas (713,397,860.00) y la de lo adjudicado (404,546,660.00) coinciden con la respuesta.
- **Servidor de Vite** (<http://localhost:5173>), detrás del mismo Keycloak:
  - axe-core 4.13.0 cargado desde `/node_modules/axe-core/axe.min.js` dentro de cada vista;
  - reglas WCAG 2.0, 2.1 y 2.2, niveles A y AA, con la regla de contraste;
  - cada vista se cargó en un `iframe` del mismo origen con el ancho de la prueba, en tema claro y en tema oscuro (`prefers-color-scheme` emulado).
- **Desplazamiento horizontal:** se considera correcto si `document.documentElement.scrollWidth <= window.innerWidth`.

## Resultados

| Comprobación | 375 px | 768 px | 1440 px |
|---|---|---|---|
| axe, tema claro | 0 violaciones | — | 0 violaciones |
| axe, tema oscuro | 0 violaciones | — | 0 violaciones |
| Desplazamiento horizontal | No | — | No |
| Disposición | Tarjetas apiladas; estados en 2 columnas | Tarjetas apiladas; estados en 4 columnas | Tarjetas lado a lado, de la misma altura; estados en 4 columnas |
| Texto desbordado en la fila | Ninguno | Ninguno | Ninguno |
| Alto de cada enlace de estado | 46 px | 46 px | 46 px |

- **Contraste sin determinar:** axe dejó 8 nodos a 375 px y 11 a 1440 px. Todos son etiquetas de los ejes de «Gasto comprometido por mes», una gráfica SVG que ya existía. Ninguno está en la fila nueva.
- **Texto de la tarjeta:** «$308.9 M MXN» y «43.3 % frente a la primera oferta, en 9 negociaciones adjudicadas.», con el enlace «Ver adjudicadas».
- **Enlaces:**
  - Los 7 estados llevan a `/negociaciones?estado=<estado>`, con su número en el nombre del enlace («Adjudicada 9», «Por aprobar 0»…).
  - «Adjudicada» abrió Negociaciones con el chip «Adjudicada» activo y 9 filas, las mismas que cuenta el Tablero.
- **Error de `negociacion`:**
  1. Con el contenedor detenido (`docker compose stop negociacion`) y el Tablero recargado, el resto del Tablero cargó completo.
  2. La sección «Estado de las negociaciones» mostró, tras los reintentos de la consulta (unos 7 s), «Servicio no disponible. El servicio no está disponible; intente más tarde.» con el botón «Reintentar».
  3. Con el servicio de nuevo arriba, «Reintentar» cargó la fila sin recargar la página.

## Defectos

La revisión en el navegador no encontró ninguno. La revisión final de la rama encontró dos, que se corrigieron después de esta revisión:

1. **Un plazo negociado distorsionaba el ahorro.** La primera oferta se costeaba con su propio plazo, así que abrir en 12 meses y acordar 1 contaba como 94 % de ahorro.
   - Ahora se costea al plazo acordado, con sus propios precios y su cuota (spec, D2 enmendada).
   - Prueba: `test_la_primera_oferta_se_costea_con_el_plazo_acordado`.
   - Los datos de esta revisión no negocian el plazo, así que sus cifras no cambian.
2. **La fila dependía de `inteligencia`.** Solo aparecía cuando el Tablero de `inteligencia` había cargado.
   - Ahora la consulta empieza en paralelo y la fila se muestra también si `inteligencia` falla.
   - Prueba: «si la inteligencia no responde, la fila de negociaciones carga por su cuenta».

## Observación

En los datos de desarrollo, el ahorro logrado lo dominan las adjudicaciones que deja cada corrida de la prueba de humo (README, «Arranque rápido»). Solo afecta al entorno local.
