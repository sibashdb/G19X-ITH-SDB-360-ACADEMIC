# Sub-proyecto 1 · Plan A — Sistema de diseño y experiencia: Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la SPA se vea y navegue como el producto final: sistema de diseño claro/oscuro con selector de tema, armazón con menú lateral por rol y barra superior, Proveedores e Importación rediseñados, las páginas nuevas (Tablero, Precios, Ranking, Alertas, Configuración) con sus estados vacíos, y el inicio de sesión de Keycloak con la misma identidad.

**Architecture:** Solo frontend y Keycloak; la API no cambia. Los tokens viven como variables CSS en `web/src/index.css` (hex, claro y oscuro) y los componentes solo usan clases de Tailwind ligadas a esos tokens; un lint prohíbe colores literales y una prueba calcula el contraste WCAG de cada par. El estado de filtros, pestañas y selección vive en la URL (`useSearchParams`) para que atrás/adelante y los enlaces funcionen. Las páginas que dependen del servicio `inteligencia` (Plan B) muestran su estructura final con estados vacíos y un aviso único (`AvisoInteligencia`) que el Plan B retira.

**Tech Stack:** React 19 + TypeScript 6 + Vite 8, Tailwind v4, shadcn 4.21 (estilo `radix-nova`), Recharts 3 (vía `shadcn add chart`), TanStack Query 5, react-router 8, react-oidc-context, `@fontsource/fira-sans` y `@fontsource-variable/fira-code`, Vitest 5 + Testing Library + axe-core · Keycloak 26.5 (tema de login que extiende `keycloak.v2`).

**Spec:** `docs/superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md` (secciones 1, 3, 7 —parte de frontend— y 8, "Plan A").

## Global Constraints

- **Tokens (únicos colores permitidos), claro / oscuro:** `background` #F8FAFC / #0B1220 · `card` #FFFFFF / #111A2E · `foreground` #020617 / #E2E8F0 · `muted` #E8ECF1 / #1A2438 · `muted-foreground` #475569 / #94A3B8 · `border` #E2E8F0 / #24324A · `primary` #0F172A / #E2E8F0 · `accent` #0369A1 / #38BDF8 · `success` #15803D / #4ADE80 · `warning` #B45309 / #FBBF24 · `destructive` #DC2626 / #F87171 · `sidebar` #0F172A / #0B1220 · `chart-1..5` #0369A1 #0F766E #B45309 #64748B #6D28D9 / #38BDF8 #2DD4BF #FBBF24 #94A3B8 #A78BFA.
- "El color **nunca es la única señal**. Los estados llevan icono y texto ("Sobreprecio", "Justo"), y las series de gráficas llevan etiqueta directa o leyenda."
- Contraste ≥ **4.5:1** en pares texto/fondo de los tokens y ≥ **3:1** en elementos gráficos, en ambos temas (prueba automática).
- **Lint** que prohíbe colores literales (`#hex`, `rgb(`) en `web/src/paginas` y `web/src/componentes`.
- Tipografía **Fira Sans** (texto y títulos) y **Fira Code** (RFC, folios, códigos), auto-hospedadas con `@fontsource`; **se elimina Geist**; la CSP del gateway solo permite fuentes de `'self'`.
- Cifras con `font-variant-numeric: tabular-nums`. Escala 12 / 14 / 16 (base) / 18 / 20 / 24 / 30 px. Espaciado 4 / 8 / 12 / 16 / 24 / 32 px. Radio 8 px en controles y 12 px en tarjetas. Sombra solo en elementos flotantes.
- Iconos `lucide-react`, siempre con texto o `aria-label` (decorativos con `aria-hidden`). Nunca emojis.
- Transiciones de 150–200 ms; se respeta `prefers-reduced-motion`; sin animaciones de entrada decorativas (no se agrega GSAP).
- Tema `claro | oscuro | sistema`, guardado en `localStorage`, aplicado con la clase `.dark` en `<html>`; un script previo al render evita el destello. La CSP del gateway (`default-src 'self'`) **no permite scripts en línea**: el script es un archivo de `web/public/`.
- Estados estándar: esqueletos (`Skeleton`) mientras carga; estado vacío con título, una línea de explicación y una acción; error en `Alert` con el mensaje en español y un botón **"Reintentar"**.
- Usable a 375, 768, 1024 y 1440 px; **sin scroll horizontal de página** (las tablas desplazan dentro de su contenedor).
- Interfaz y mensajes en **español (México)**, incluidos los textos para lectores de pantalla de los componentes generados por shadcn.
- Los montos llegan como texto decimal y **no se operan en el navegador** (solo se formatean).
- Importación y Configuración son **solo para admin** en la interfaz (la API vuelve a validar el rol).
- **La API no cambia** en este plan (solo `web/`, `infra/keycloak/`, `infra/docker-compose.yml`, `infra/smoke_test.py`, documentación).
- Dependencias nuevas permitidas: `@fontsource/fira-sans`, `@fontsource-variable/fira-code`, `axe-core` (dev) y lo que instale `npx shadcn@4.21.0 add` (Radix, `recharts`). Ninguna otra.
- Pruebas: Vitest + Testing Library por página (carga, vacío, error y datos, según aplique) y revisión axe por página en ambos temas.
- Commits con Conventional Commits en español; el trailer `Co-Authored-By` nombra al modelo que realmente escribió el código (regla R5b de la bitácora). Nunca `git push` ni remotos. Nunca se versionan `infra/.env`, `datos/`, `web/node_modules`, `web/dist`, `.superpowers/` ni el PDF.

## Review Focus

1. **Parámetros de URL editados a mano o viejos** (`?pagina=abc`, `?pagina=999999999`, `?categoria=foo`, `?pestana=x`, `?servicio=NOEXISTE`, `?tipo=x`) → la página usa el valor por defecto, nunca envía a la API un valor fuera de rango y no se rompe. Pruebas en las Tareas 5, 6, 8 y 9.
2. **Preferencia de tema corrupta o almacenamiento bloqueado** (`localStorage` con `"azul"`, navegador que lanza excepción al leerlo) → se usa "sistema" y la aplicación arranca; el script previo al render y el proveedor de tema deciden lo mismo. Pruebas en la Tarea 2.
3. **Archivo de importación problemático** (`.CSV` en mayúsculas, `.xlsx`, más de 10 MB, vacío, dos archivos soltados a la vez) → `.CSV` se acepta; lo demás se rechaza en el navegador con un mensaje en español y sin subir nada. Pruebas en la Tarea 7.
4. **Instalación nueva sin datos** (sin proveedores ni catálogo antes de la primera importación) → estados vacíos que explican qué falta y, al administrador, le enlazan a Importación; nunca una tabla vacía sin explicación. Pruebas en las Tareas 5 y 9.
5. **Sin conexión con el servidor** (gateway caído: `fetch` rechaza con "Failed to fetch", en inglés) → mensaje en español "No se pudo conectar con el servidor…" con "Reintentar". Pruebas en la Tarea 3.

## Diferido conscientemente (fuera de este plan)

| Qué | Cuándo | Por qué |
|---|---|---|
| Puntuación, gasto anual, alertas y "precio vs. mercado" en la lista y el detalle de proveedores; gráfica *bullet* contra la categoría | Plan B | Son datos del servicio `inteligencia`. |
| Orden por columna y filtro "en riesgo" en la lista de proveedores | Plan B | La API de proveedores ordena por nombre y no conoce el riesgo; ordenar por puntuación o gasto requiere `inteligencia`. Este plan no toca la API. |
| Conteo de la campana de alertas | Plan B | Sale de `GET /api/inteligencia/alertas`. |
| Componentes `sonner` y `progress` | Plan B | Ninguna acción de este plan los usa (guardar configuración, reentrenar, barra de puntuación). |
| axe automatizado en navegador real (Playwright) | Sub-proyecto 4 | Aquí: axe en jsdom por página + revisión con axe en el navegador al final (Tarea 11). |

## Entorno (Windows, Git Bash)

Ejecute todo desde la raíz del repositorio. Antes de cualquier comando de Docker o uv:

```bash
export PATH="/c/Users/sebas/AppData/Local/Microsoft/WinGet/Links:/c/Program Files/Docker/Docker/resources/bin:$PATH"
export UV_PYTHON="C:/Users/sebas/AppData/Roaming/uv/python/cpython-3.13.15-windows-x86_64-none/python.exe"
export MSYS_NO_PATHCONV=1
```

Los comandos del frontend van en un subshell para no cambiar el directorio de la sesión: `(cd web && npx vitest run src/tema.test.tsx)`. El stack de Docker Compose corre como proyecto `plataforma` desde `infra/`; gateway en <http://localhost:8080>.

## Estructura de archivos

```
web/
  index.html                       script de tema previo al render, favicon, título
  public/tema.js                   aplica el tema guardado antes del primer render (nuevo)
  public/favicon.svg               icono del producto (nuevo; se borra public/vite.svg)
  eslint.config.js                 regla contra colores literales
  tsconfig.app.json · tsconfig.node.json   pruebas *.node.test.ts con tipos de Node
  src/index.css                    tokens claro/oscuro, fuentes, base, movimiento reducido
  src/tokens.node.test.ts          contraste WCAG de los tokens (nuevo)
  src/tema.tsx · tema.test.tsx     ProveedorTema, useTema, aplicarTema (nuevo)
  src/main.tsx                     envuelve la app con ProveedorTema
  src/setupPruebas.ts              polyfills de jsdom (matchMedia, ResizeObserver, punteros)
  src/api.ts · api.test.ts         error de red en español
  src/parametros.ts · parametros.test.ts   enteroPositivo, unoDe, useParametros (nuevo)
  src/tipos.ts                     CATEGORIAS, KPIS_DESEMPENO, formatoPeriodo, alertas, Servicio, normalizarTexto
  src/rutas.tsx                    rutas nuevas
  src/pruebas/sesion.ts            sesión OIDC simulada para pruebas (nuevo)
  src/pruebas/utilidades.tsx       render de páginas, API simulada, axe (nuevo)
  src/componentes/
    Estados.tsx                    EstadoCarga, EstadoVacio, EstadoError, ContenidoConsulta (nuevo)
    EncabezadoPagina.tsx · Seccion.tsx · RequiereRol.tsx · Base.test.tsx (nuevos)
    navegacion.ts · navegacion.test.ts   menú por rol, ruta activa, migas (nuevo)
    BarraLateral.tsx · BarraSuperior.tsx (nuevos) · Layout.tsx · Layout.test.tsx
    EtiquetaEstado.tsx · TablaContratos.tsx · DesempenoProveedor.tsx (nuevos)
    AvisoInteligencia.tsx · TarjetaKpi.tsx (nuevos)
  src/components/ui/               shadcn: skeleton, sidebar(+sheet, tooltip, separator, input), dropdown-menu,
                                   breadcrumb, tabs, select, chart; badge y alert ajustados
  src/hooks/use-mobile.ts          lo crea shadcn con sidebar
  src/paginas/
    Tablero · Ranking · Alertas · Configuracion · Precios (+ pruebas) (nuevos)
    Proveedores · ProveedorDetalle · Importacion · NoEncontrado (rediseño, + pruebas)
    Inicio.tsx                     se elimina (lo reemplaza Tablero)
infra/
  keycloak/themes/plataforma/login/theme.properties · resources/css/plataforma.css · resources/fonts/*
  keycloak/realm-plataforma.json   loginTheme
  docker-compose.yml               montaje del tema
  smoke_test.py                    verifica el tema de inicio de sesión
docs/qa/revision-visual-plan-a.md  resultados de la revisión en navegador (Tarea 11)
README.md                          tema de inicio de sesión e interfaz
```

---

### Task 1: Tokens del sistema de diseño, tipografía y lint de colores

**Files:**
- Modify: `web/src/index.css` (reemplazo completo)
- Modify: `web/package.json`, `web/package-lock.json` (Fira Sans y Fira Code; quitar Geist)
- Modify: `web/eslint.config.js`
- Modify: `web/tsconfig.app.json`, `web/tsconfig.node.json`
- Test: `web/src/tokens.node.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces: variables CSS `--background … --sidebar-ring`, `--success`, `--warning`, `--destructive-foreground`, `--chart-1..5` en `:root` y `.dark`; clases de Tailwind `text-success`, `border-warning/40`, `bg-sidebar-primary`, `text-destructive-foreground`, etc.; `font-mono` = Fira Code; radio `rounded-lg` = 8 px y `rounded-xl` = 12 px. Las pruebas `*.node.test.ts` se compilan con `tsconfig.node.json` (tipos de Node) y se excluyen de `tsconfig.app.json`.

- [ ] **Step 1: Configurar TypeScript para pruebas que leen archivos**

Vitest devuelve una cadena vacía al importar `.css` (incluso con `?raw`), así que la prueba de contraste lee `index.css` con `node:fs`. Esas pruebas se nombran `*.node.test.ts` y se compilan con los tipos de Node.

En `web/tsconfig.app.json`, después de `"include": ["src"]`, agregue:

```json
  "include": ["src"],
  "exclude": ["src/**/*.node.test.ts"]
```

En `web/tsconfig.node.json` cambie `include`:

```json
  "include": ["vite.config.ts", "src/**/*.node.test.ts"]
```

- [ ] **Step 2: Escribir la prueba de contraste (falla)**

Cree `web/src/tokens.node.test.ts`:

```ts
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const css = readFileSync(resolve(import.meta.dirname, "index.css"), "utf8")

/** Variables declaradas en el bloque `selector { … }` de index.css. */
function variables(selector: string): Record<string, string> {
  const inicio = css.indexOf(`${selector} {`)
  if (inicio < 0) throw new Error(`index.css no tiene el bloque ${selector}`)
  const bloque = css.slice(inicio, css.indexOf("}", inicio))
  return Object.fromEntries(
    [...bloque.matchAll(/--([\w-]+):\s*([^;]+);/g)].map(([, nombre, valor]) => [
      nombre,
      valor.trim(),
    ])
  )
}

const CLARO = variables(":root")
const TEMAS = { claro: CLARO, oscuro: { ...CLARO, ...variables(".dark") } }

/** Resuelve `var(--x)` y exige un color #RRGGBB. */
function color(tema: Record<string, string>, token: string): string {
  let valor = tema[token]
  for (let saltos = 0; valor?.startsWith("var(--") && saltos < 5; saltos++) {
    valor = tema[valor.slice(6, -1)]
  }
  if (!/^#[0-9a-f]{6}$/i.test(valor ?? "")) {
    throw new Error(`El token --${token} debe ser un color #RRGGBB (es ${valor})`)
  }
  return valor
}

function luminancia(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contraste(a: string, b: string): number {
  const [claro, oscuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
  return (claro + 0.05) / (oscuro + 0.05)
}

const TEXTO = 4.5
const GRAFICO = 3

function par(frente: string, fondo: string, minimo: number): [string, string, number] {
  return [frente, fondo, minimo]
}

/** Pares que la interfaz usa: [primer plano, fondo, contraste mínimo]. */
const PARES = [
  ...["background", "card", "muted"].flatMap((fondo) => [
    par("foreground", fondo, TEXTO),
    par("muted-foreground", fondo, TEXTO),
    par("accent", fondo, TEXTO),
  ]),
  ...["success", "warning", "destructive"].flatMap((estado) => [
    par(estado, "background", TEXTO),
    par(estado, "card", TEXTO),
  ]),
  par("card-foreground", "card", TEXTO),
  par("popover-foreground", "popover", TEXTO),
  par("primary-foreground", "primary", TEXTO),
  par("secondary-foreground", "secondary", TEXTO),
  par("accent-foreground", "accent", TEXTO),
  par("destructive-foreground", "destructive", TEXTO),
  par("sidebar-foreground", "sidebar", TEXTO),
  par("sidebar-accent-foreground", "sidebar-accent", TEXTO),
  par("sidebar-primary-foreground", "sidebar-primary", TEXTO),
  ...[1, 2, 3, 4, 5].map((n) => par(`chart-${n}`, "card", GRAFICO)),
  par("ring", "background", GRAFICO),
  par("sidebar-ring", "sidebar", GRAFICO),
]

describe("contraste de los tokens", () => {
  it("calcula el contraste WCAG", () => {
    expect(contraste("#000000", "#FFFFFF")).toBeCloseTo(21, 1)
    expect(contraste("#777777", "#FFFFFF")).toBeCloseTo(4.48, 2)
  })

  for (const [nombre, tema] of Object.entries(TEMAS)) {
    it.each(PARES)(`tema ${nombre}: --%s sobre --%s cumple %d:1`, (frente, fondo, minimo) => {
      expect(contraste(color(tema, frente), color(tema, fondo))).toBeGreaterThanOrEqual(minimo)
    })
  }
})
```

- [ ] **Step 3: Verificar que falla**

Run: `(cd web && npx vitest run src/tokens.node.test.ts)`
Expected: FAIL — los tokens actuales son `oklch(...)` y `color()` lanza "El token --foreground debe ser un color #RRGGBB"; además faltan `--success`, `--warning` y `--destructive-foreground`. La prueba "calcula el contraste WCAG" pasa.

- [ ] **Step 4: Instalar las fuentes y quitar Geist**

Run: `(cd web && npm install @fontsource/fira-sans @fontsource-variable/fira-code && npm uninstall @fontsource-variable/geist)`
Expected: `package.json` lista `@fontsource/fira-sans` y `@fontsource-variable/fira-code`; ya no lista `@fontsource-variable/geist`.

- [ ] **Step 5: Reemplazar `web/src/index.css`**

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";
@import "@fontsource/fira-sans/400.css";
@import "@fontsource/fira-sans/500.css";
@import "@fontsource/fira-sans/600.css";
@import "@fontsource/fira-sans/700.css";
@import "@fontsource-variable/fira-code";

@custom-variant dark (&:is(.dark *));

@theme inline {
    --font-sans: "Fira Sans", ui-sans-serif, system-ui, sans-serif;
    --font-heading: var(--font-sans);
    --font-mono: "Fira Code Variable", ui-monospace, monospace;
    --color-sidebar-ring: var(--sidebar-ring);
    --color-sidebar-border: var(--sidebar-border);
    --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
    --color-sidebar-accent: var(--sidebar-accent);
    --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
    --color-sidebar-primary: var(--sidebar-primary);
    --color-sidebar-foreground: var(--sidebar-foreground);
    --color-sidebar: var(--sidebar);
    --color-chart-5: var(--chart-5);
    --color-chart-4: var(--chart-4);
    --color-chart-3: var(--chart-3);
    --color-chart-2: var(--chart-2);
    --color-chart-1: var(--chart-1);
    --color-ring: var(--ring);
    --color-input: var(--input);
    --color-border: var(--border);
    --color-success: var(--success);
    --color-warning: var(--warning);
    --color-destructive-foreground: var(--destructive-foreground);
    --color-destructive: var(--destructive);
    --color-accent-foreground: var(--accent-foreground);
    --color-accent: var(--accent);
    --color-muted-foreground: var(--muted-foreground);
    --color-muted: var(--muted);
    --color-secondary-foreground: var(--secondary-foreground);
    --color-secondary: var(--secondary);
    --color-primary-foreground: var(--primary-foreground);
    --color-primary: var(--primary);
    --color-popover-foreground: var(--popover-foreground);
    --color-popover: var(--popover);
    --color-card-foreground: var(--card-foreground);
    --color-card: var(--card);
    --color-foreground: var(--foreground);
    --color-background: var(--background);
    --radius-sm: calc(var(--radius) * 0.6);
    --radius-md: calc(var(--radius) * 0.8);
    --radius-lg: var(--radius);
    --radius-xl: 0.75rem;
    --radius-2xl: calc(var(--radius) * 1.8);
    --radius-3xl: calc(var(--radius) * 2.2);
    --radius-4xl: calc(var(--radius) * 2.6);
}

/* Tokens de la dirección visual A (corporativa clara). Solo hex: tokens.node.test.ts calcula su contraste. */
:root {
    --radius: 0.5rem;
    --background: #F8FAFC;
    --foreground: #020617;
    --card: #FFFFFF;
    --card-foreground: #020617;
    --popover: #FFFFFF;
    --popover-foreground: #020617;
    --primary: #0F172A;
    --primary-foreground: #FFFFFF;
    --secondary: #E8ECF1;
    --secondary-foreground: #020617;
    --muted: #E8ECF1;
    --muted-foreground: #475569;
    --accent: #0369A1;
    --accent-foreground: #FFFFFF;
    --success: #15803D;
    --warning: #B45309;
    --destructive: #DC2626;
    --destructive-foreground: #FFFFFF;
    --border: #E2E8F0;
    --input: #CBD5E1;
    --ring: #0369A1;
    --chart-1: #0369A1;
    --chart-2: #0F766E;
    --chart-3: #B45309;
    --chart-4: #64748B;
    --chart-5: #6D28D9;
    --sidebar: #0F172A;
    --sidebar-foreground: #E2E8F0;
    --sidebar-primary: #0369A1;
    --sidebar-primary-foreground: #FFFFFF;
    --sidebar-accent: #1E293B;
    --sidebar-accent-foreground: #FFFFFF;
    --sidebar-border: #1E293B;
    --sidebar-ring: #38BDF8;
}

.dark {
    --background: #0B1220;
    --foreground: #E2E8F0;
    --card: #111A2E;
    --card-foreground: #E2E8F0;
    --popover: #111A2E;
    --popover-foreground: #E2E8F0;
    --primary: #E2E8F0;
    --primary-foreground: #0B1220;
    --secondary: #1A2438;
    --secondary-foreground: #E2E8F0;
    --muted: #1A2438;
    --muted-foreground: #94A3B8;
    --accent: #38BDF8;
    --accent-foreground: #0B1220;
    --success: #4ADE80;
    --warning: #FBBF24;
    --destructive: #F87171;
    --destructive-foreground: #0B1220;
    --border: #24324A;
    --input: #334155;
    --ring: #38BDF8;
    --chart-1: #38BDF8;
    --chart-2: #2DD4BF;
    --chart-3: #FBBF24;
    --chart-4: #94A3B8;
    --chart-5: #A78BFA;
    --sidebar: #0B1220;
    --sidebar-foreground: #E2E8F0;
    --sidebar-primary: #38BDF8;
    --sidebar-primary-foreground: #0B1220;
    --sidebar-accent: #1A2438;
    --sidebar-accent-foreground: #E2E8F0;
    --sidebar-border: #24324A;
    --sidebar-ring: #38BDF8;
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  html {
    @apply font-sans;
    color-scheme: light;
  }
  html.dark {
    color-scheme: dark;
  }
  body {
    @apply bg-background text-foreground;
    /* Cifras de igual ancho: los montos se alinean en columnas. */
    font-variant-numeric: tabular-nums;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

- [ ] **Step 6: Verificar que la prueba pasa**

Run: `(cd web && npx vitest run src/tokens.node.test.ts)`
Expected: PASS — 1 prueba de cálculo + 2 × 31 pares.

- [ ] **Step 7: Comprobar que el lint todavía no detecta colores literales (RED)**

Cree temporalmente `web/src/componentes/SondaColor.tsx`:

```tsx
export const sonda = (
  <span className="text-[#ff0000]" style={{ color: "rgb(0 0 0)" }}>
    x
  </span>
)
```

Run: `(cd web && npx eslint src/componentes/SondaColor.tsx)`
Expected: sin errores (la regla aún no existe).

- [ ] **Step 8: Agregar la regla al final del arreglo de `web/eslint.config.js`**

```js
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

// Colores literales: hex de 3 a 8 dígitos o funciones de color.
const COLOR_LITERAL = '/#[0-9a-fA-F]{3,8}\\b|\\b(rgba?|hsla?|oklch)\\(/'
const MENSAJE_COLOR =
  'Use los tokens del sistema de diseño (p. ej. text-destructive o var(--chart-1)), no colores literales.'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // Las pantallas solo usan los tokens de web/src/index.css.
    files: ['src/paginas/**/*.{ts,tsx}', 'src/componentes/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        { selector: `Literal[value=${COLOR_LITERAL}]`, message: MENSAJE_COLOR },
        { selector: `TemplateElement[value.raw=${COLOR_LITERAL}]`, message: MENSAJE_COLOR },
      ],
    },
  },
])
```

- [ ] **Step 9: Verificar que el lint detecta la sonda (GREEN) y borrarla**

Run: `(cd web && npx eslint src/componentes/SondaColor.tsx)`
Expected: 2 errores `no-restricted-syntax` ("Use los tokens del sistema de diseño…").

Run: `rm web/src/componentes/SondaColor.tsx && (cd web && npm run lint && npm run build && npm test -- --run)`
Expected: lint sin errores, build correcto (sin errores de tipos), todas las pruebas pasan.

- [ ] **Step 10: Commit**

```bash
git add web/src/index.css web/src/tokens.node.test.ts web/eslint.config.js web/tsconfig.app.json web/tsconfig.node.json web/package.json web/package-lock.json
git commit -m "feat(web): tokens claro/oscuro, tipografía Fira, prueba de contraste y lint de colores"
```

---

### Task 2: Tema claro, oscuro y sistema

**Files:**
- Create: `web/src/tema.tsx`, `web/public/tema.js`, `web/public/favicon.svg`
- Modify: `web/index.html`, `web/src/main.tsx`, `web/src/setupPruebas.ts`
- Delete: `web/public/vite.svg`, `web/src/assets/react.svg` (restos de la plantilla, sin referencias)
- Test: `web/src/tema.test.tsx`

**Interfaces:**
- Consumes: clase `.dark` y variables de la Tarea 1.
- Produces:
  - `type Tema = "claro" | "oscuro" | "sistema"`
  - `CLAVE_TEMA = "plataforma-tema"` (clave de `localStorage`)
  - `NOMBRES_TEMA: Record<Tema, string>` → `{ claro: "Claro", oscuro: "Oscuro", sistema: "Sistema" }`
  - `aplicarTema(tema: Tema): void` — pone o quita `.dark` y `color-scheme` en `<html>`
  - `<ProveedorTema>{children}</ProveedorTema>` y `useTema(): { tema: Tema; cambiarTema(tema: Tema): void }` (lanza fuera del proveedor)
  - `web/public/tema.js` hace lo mismo que `aplicarTema(temaGuardado())` antes del render.
  - `setupPruebas.ts` deja `window.matchMedia` (devuelve `matches: false`), `ResizeObserver`, `scrollIntoView`, `hasPointerCapture` y `releasePointerCapture` para jsdom.

- [ ] **Step 1: Polyfills de jsdom**

Reemplace `web/src/setupPruebas.ts`:

```ts
import "@testing-library/jest-dom/vitest"

// jsdom no implementa estas APIs del navegador. matchMedia: tema "sistema" y menú lateral
// (useIsMobile); ResizeObserver: gráficas y Radix; punteros y scroll: Select de Radix.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: (consulta: string) => ({
    matches: false,
    media: consulta,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
})

class ResizeObserverDePrueba {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverDePrueba as unknown as typeof ResizeObserver

Element.prototype.scrollIntoView = () => {}
Element.prototype.hasPointerCapture = () => false
Element.prototype.releasePointerCapture = () => {}
```

- [ ] **Step 2: Escribir las pruebas del tema (fallan)**

Cree `web/src/tema.test.tsx`:

```tsx
import { act, cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import guionPrevio from "../public/tema.js?raw"
import { CLAVE_TEMA, ProveedorTema, useTema, type Tema } from "@/tema"

function Interruptor() {
  const { tema, cambiarTema } = useTema()
  return (
    <>
      <span data-testid="tema">{tema}</span>
      {(["claro", "oscuro", "sistema"] as Tema[]).map((opcion) => (
        <button key={opcion} type="button" onClick={() => cambiarTema(opcion)}>
          {opcion}
        </button>
      ))}
    </>
  )
}

/** Simula la preferencia del sistema operativo y permite cambiarla en caliente. */
function simularSistema(oscuroInicial: boolean) {
  let oscuro = oscuroInicial
  const oyentes = new Set<() => void>()
  vi.stubGlobal("matchMedia", (consulta: string) => ({
    get matches() {
      return consulta.includes("dark") && oscuro
    },
    media: consulta,
    addEventListener: (_: string, oyente: () => void) => oyentes.add(oyente),
    removeEventListener: (_: string, oyente: () => void) => oyentes.delete(oyente),
  }))
  return {
    cambiar(valor: boolean) {
      oscuro = valor
      oyentes.forEach((oyente) => oyente())
    },
  }
}

function renderizar() {
  return render(
    <ProveedorTema>
      <Interruptor />
    </ProveedorTema>
  )
}

const html = document.documentElement

afterEach(() => {
  cleanup()
  localStorage.clear()
  html.classList.remove("dark")
  html.style.colorScheme = ""
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("ProveedorTema", () => {
  it("usa 'sistema' por defecto y sigue al sistema operativo en caliente", () => {
    const sistema = simularSistema(true)
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("sistema")
    expect(html).toHaveClass("dark")

    act(() => sistema.cambiar(false))
    expect(html).not.toHaveClass("dark")
  })

  it("guarda la elección y aplica la clase y el color-scheme", async () => {
    simularSistema(false)
    renderizar()

    await userEvent.click(screen.getByRole("button", { name: "oscuro" }))
    expect(localStorage.getItem(CLAVE_TEMA)).toBe("oscuro")
    expect(html).toHaveClass("dark")
    expect(html.style.colorScheme).toBe("dark")

    await userEvent.click(screen.getByRole("button", { name: "claro" }))
    expect(html).not.toHaveClass("dark")
    expect(html.style.colorScheme).toBe("light")
  })

  it("recupera el tema guardado aunque el sistema prefiera otro", () => {
    simularSistema(false)
    localStorage.setItem(CLAVE_TEMA, "oscuro")
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("oscuro")
    expect(html).toHaveClass("dark")
  })

  it("trata un valor guardado desconocido como 'sistema'", () => {
    simularSistema(true)
    localStorage.setItem(CLAVE_TEMA, "azul")
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("sistema")
    expect(html).toHaveClass("dark")
  })

  it("funciona aunque el navegador bloquee localStorage", async () => {
    simularSistema(false)
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("sistema")
    await userEvent.click(screen.getByRole("button", { name: "oscuro" }))
    expect(html).toHaveClass("dark")
  })

  it("useTema fuera del proveedor avisa en español", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    expect(() => render(<Interruptor />)).toThrow("useTema debe usarse dentro de ProveedorTema")
  })
})

describe("script previo al render (public/tema.js)", () => {
  const ejecutar = () => new Function(guionPrevio)()

  it.each([
    ["oscuro", false, true],
    ["claro", true, false],
    ["sistema", true, true],
    ["azul", true, true],
    [null, false, false],
  ])("con %s guardado y sistema oscuro=%s aplica dark=%s", (guardado, sistemaOscuro, esperado) => {
    simularSistema(sistemaOscuro)
    if (guardado) localStorage.setItem(CLAVE_TEMA, guardado)

    ejecutar()

    expect(html.classList.contains("dark")).toBe(esperado)
    expect(html.style.colorScheme).toBe(esperado ? "dark" : "light")
  })

  it("no falla si localStorage está bloqueado", () => {
    simularSistema(true)
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })

    expect(ejecutar).not.toThrow()
    expect(html).toHaveClass("dark")
  })
})
```

- [ ] **Step 3: Verificar que fallan**

Run: `(cd web && npx vitest run src/tema.test.tsx)`
Expected: FAIL — no se resuelven `@/tema` ni `../public/tema.js?raw`.

- [ ] **Step 4: Implementar `web/src/tema.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

export type Tema = "claro" | "oscuro" | "sistema"

/** Clave de localStorage; public/tema.js usa la misma. */
export const CLAVE_TEMA = "plataforma-tema"

export const NOMBRES_TEMA: Record<Tema, string> = {
  claro: "Claro",
  oscuro: "Oscuro",
  sistema: "Sistema",
}

const CONSULTA_OSCURO = "(prefers-color-scheme: dark)"

/** Tema guardado; un valor desconocido o un almacenamiento bloqueado cuentan como "sistema". */
function temaGuardado(): Tema {
  try {
    const valor = localStorage.getItem(CLAVE_TEMA)
    return valor === "claro" || valor === "oscuro" ? valor : "sistema"
  } catch {
    return "sistema"
  }
}

export function aplicarTema(tema: Tema): void {
  const oscuro =
    tema === "oscuro" || (tema === "sistema" && window.matchMedia(CONSULTA_OSCURO).matches)
  document.documentElement.classList.toggle("dark", oscuro)
  document.documentElement.style.colorScheme = oscuro ? "dark" : "light"
}

type EstadoTema = { tema: Tema; cambiarTema: (tema: Tema) => void }

const ContextoTema = createContext<EstadoTema | null>(null)

export function ProveedorTema({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(temaGuardado)

  useEffect(() => {
    aplicarTema(tema)
    if (tema !== "sistema") return
    // En "sistema" se sigue al sistema operativo también mientras la app está abierta.
    const consulta = window.matchMedia(CONSULTA_OSCURO)
    const alCambiar = () => aplicarTema("sistema")
    consulta.addEventListener("change", alCambiar)
    return () => consulta.removeEventListener("change", alCambiar)
  }, [tema])

  function cambiarTema(nuevo: Tema) {
    try {
      localStorage.setItem(CLAVE_TEMA, nuevo)
    } catch {
      // Sin almacenamiento (modo privado estricto): el tema dura lo que la pestaña.
    }
    setTema(nuevo)
  }

  return <ContextoTema value={{ tema, cambiarTema }}>{children}</ContextoTema>
}

export function useTema(): EstadoTema {
  const contexto = useContext(ContextoTema)
  if (!contexto) throw new Error("useTema debe usarse dentro de ProveedorTema")
  return contexto
}
```

- [ ] **Step 5: Crear `web/public/tema.js`**

```js
// Aplica el tema guardado antes del primer render para evitar el destello de tema equivocado.
// Es un archivo externo porque la CSP del gateway no permite scripts en línea.
// Debe decidir lo mismo que aplicarTema() en src/tema.tsx (lo verifica src/tema.test.tsx).
;(function () {
  var tema = "sistema"
  try {
    tema = localStorage.getItem("plataforma-tema") || "sistema"
  } catch (e) {
    // Almacenamiento bloqueado: se usa la preferencia del sistema.
  }
  var oscuro =
    tema === "oscuro" ||
    (tema !== "claro" && window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", oscuro)
  document.documentElement.style.colorScheme = oscuro ? "dark" : "light"
})()
```

- [ ] **Step 6: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/tema.test.tsx)`
Expected: PASS (6 + 6 pruebas).

- [ ] **Step 7: Conectar el tema a la aplicación**

`web/index.html` completo:

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PluriOne · Negociación con proveedores</title>
    <!-- Antes del primer render (evita el destello del tema equivocado); externo por la CSP. -->
    <script src="/tema.js"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`web/public/favicon.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#0F172A"/><path d="M16 6l9 5v10l-9 5-9-5V11z" fill="none" stroke="#38BDF8" stroke-width="2.5" stroke-linejoin="round"/></svg>
```

En `web/src/main.tsx` envuelva todo con `ProveedorTema`:

```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "react-oidc-context"
import { RouterProvider } from "react-router/dom"
import { configuracionOidc } from "@/auth"
import { router } from "@/rutas"
import { ProveedorTema } from "@/tema"
import "./index.css"

const clienteConsultas = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ProveedorTema>
      <AuthProvider {...configuracionOidc}>
        <QueryClientProvider client={clienteConsultas}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AuthProvider>
    </ProveedorTema>
  </StrictMode>
)
```

Borre los restos de la plantilla (confirme antes que nada los referencia):

Run: `grep -rn "vite.svg\|react.svg" web/src web/index.html` → Expected: sin resultados.
Run: `git rm web/public/vite.svg web/src/assets/react.svg`

- [ ] **Step 8: Verificación completa**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)`
Expected: todo en verde; `web/dist/tema.js` y `web/dist/favicon.svg` existen; el build no advierte sobre `/tema.js`.

- [ ] **Step 9: Commit**

```bash
git add web/src/tema.tsx web/src/tema.test.tsx web/public/tema.js web/public/favicon.svg web/index.html web/src/main.tsx web/src/setupPruebas.ts
git commit -m "feat(web): tema claro, oscuro o del sistema con script previo al render"
```

---

### Task 3: Componentes base, utilidades de prueba y error de red en español

**Files:**
- Create: `web/src/componentes/Estados.tsx`, `EncabezadoPagina.tsx`, `Seccion.tsx`, `RequiereRol.tsx`
- Create: `web/src/pruebas/sesion.ts`, `web/src/pruebas/utilidades.tsx`
- Create (shadcn): `web/src/components/ui/skeleton.tsx`
- Modify: `web/src/components/ui/badge.tsx` (variantes `success`, `warning`; `destructive` de contorno), `web/src/components/ui/alert.tsx` (descripción destructiva sin transparencia)
- Modify: `web/src/api.ts`, `web/src/api.test.ts`
- Modify: `web/package.json`, `web/package-lock.json` (`axe-core` dev)
- Test: `web/src/componentes/Base.test.tsx`

**Interfaces:**
- Consumes: `ErrorApi`, `pedir` (`@/api`); `useRoles`, `NOMBRES_ROL`, `Rol` (`@/auth`); `ProveedorTema` (Tarea 2).
- Produces:
  - `EstadoCarga({ filas?: number = 5, etiqueta?: string = "Cargando…" })` — `role="status"` con texto oculto.
  - `EstadoVacio({ icono?: LucideIcon = Inbox, titulo: string, descripcion: string, accion?: ReactNode })`
  - `EstadoError({ error: Error, alReintentar?: () => void })` — `Alert` destructivo; título de `ErrorApi.titulo` o "No se pudo cargar la información"; botón "Reintentar".
  - `ContenidoConsulta<T>({ consulta: UseQueryResult<T>, children: (datos: T) => ReactNode })` — carga → `EstadoCarga`, error → `EstadoError` con `refetch`.
  - `EncabezadoPagina({ titulo: string, descripcion?: string, acciones?: ReactNode })` — `<h1>`.
  - `Seccion({ titulo: string, descripcion?: string, acciones?: ReactNode, children: ReactNode, className?: string })` — `Card` con `<h2>`.
  - `RequiereRol({ rol: Rol, children: ReactNode })` — si falta el rol: "Acceso restringido" con enlace "Ir al tablero".
  - `Badge` acepta `variant="success" | "warning"`.
  - `pedir` lanza `ErrorApi(0, "Sin conexión", "No se pudo conectar con el servidor; revise su conexión e intente de nuevo.")` cuando `fetch` rechaza.
  - Pruebas: `sesionDePrueba` (`{ roles: string[]; signoutRedirect: Mock }`), `tokenConRoles(roles)`, `oidcSimulado()` (módulo sustituto de `react-oidc-context`, sesión iniciada como "Ana López"); `respuestaJson(cuerpo, estado = 200)`, `simularApi(rutas | (url) => Response)`, `urlDeLlamada(simulado, indice = -1): URL`, `renderizarPagina(elemento, { ruta = "/", patron = "*" }) → { cliente, ...RenderResult }`, `ubicacionActual(): string`, `esperarSinViolaciones(contenedor)`.

- [ ] **Step 1: Instalar `axe-core` y el componente `skeleton`**

Run: `(cd web && npm install -D axe-core && npx shadcn@4.21.0 add skeleton --yes)`
Expected: `web/src/components/ui/skeleton.tsx` creado; `axe-core` en `devDependencies`. Run: `git status --short` — si el CLI modificó algún archivo que ya existía (p. ej. `index.css` o otro de `components/ui/`), restáurelo con `git checkout -- <archivo>`: los tokens ya están definidos.

- [ ] **Step 2: Crear la sesión simulada `web/src/pruebas/sesion.ts`**

```ts
import { vi } from "vitest"

/** Estado de la sesión simulada; cada prueba puede cambiar los roles. */
export const sesionDePrueba = {
  roles: ["admin"] as string[],
  signoutRedirect: vi.fn(async () => {}),
}

/** JWT sin firma con los roles de realm indicados (la interfaz solo lee la carga). */
export function tokenConRoles(roles: string[]): string {
  const carga = btoa(JSON.stringify({ realm_access: { roles } }))
  return `cabecera.${carga}.firma`
}

/**
 * Sustituto de react-oidc-context con la sesión iniciada como "Ana López".
 * Uso: vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())
 */
export function oidcSimulado() {
  return {
    hasAuthParams: () => false,
    useAuth: () => ({
      isAuthenticated: true,
      isLoading: false,
      activeNavigator: undefined,
      error: undefined,
      user: {
        access_token: tokenConRoles(sesionDePrueba.roles),
        profile: { given_name: "Ana", family_name: "López", preferred_username: "ana.lopez" },
      },
      signoutRedirect: sesionDePrueba.signoutRedirect,
      signinRedirect: vi.fn(async () => {}),
      removeUser: vi.fn(async () => {}),
    }),
  }
}
```

- [ ] **Step 3: Crear `web/src/pruebas/utilidades.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import axe from "axe-core"
import type { ReactNode } from "react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router"
import { expect, vi } from "vitest"
import { ProveedorTema } from "@/tema"

export function respuestaJson(cuerpo: unknown, estado = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "Content-Type": "application/json" },
  })
}

type Respuesta = Response | Promise<Response>

/**
 * Sustituye fetch. Con un objeto, responde cada URL exacta (404 si no está); con una función,
 * decide por URL. Cada llamada crea una respuesta nueva (el cuerpo solo se lee una vez).
 */
export function simularApi(respuestas: Record<string, () => Respuesta> | ((url: string) => Respuesta)) {
  const simulado = vi.fn((url: string) => {
    if (typeof respuestas === "function") return Promise.resolve(respuestas(url))
    const respuesta = respuestas[url]
    return Promise.resolve(respuesta ? respuesta() : new Response("", { status: 404 }))
  })
  vi.stubGlobal("fetch", simulado)
  return simulado
}

/** URL de una llamada a fetch simulada (por defecto, la última), para revisar sus parámetros. */
export function urlDeLlamada(simulado: { mock: { calls: unknown[][] } }, indice = -1): URL {
  return new URL(String(simulado.mock.calls.at(indice)?.[0]), "http://localhost")
}

function Ubicacion() {
  const { pathname, search } = useLocation()
  return (
    <span hidden data-testid="ubicacion">
      {pathname + search}
    </span>
  )
}

/** Ruta y parámetros actuales de la página renderizada con renderizarPagina. */
export function ubicacionActual(): string {
  return screen.getByTestId("ubicacion").textContent ?? ""
}

/** Renderiza una página con tema, consultas (sin reintentos) y enrutador en memoria. */
export function renderizarPagina(elemento: ReactNode, { ruta = "/", patron = "*" } = {}) {
  const cliente = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const resultado = render(
    <ProveedorTema>
      <QueryClientProvider client={cliente}>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route
              path={patron}
              element={
                <>
                  {elemento}
                  <Ubicacion />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ProveedorTema>
  )
  return { cliente, ...resultado }
}

/**
 * axe (reglas WCAG 2.x A y AA) con la clase .dark quitada y puesta. jsdom no calcula estilos,
 * así que la regla de contraste se desactiva: el contraste lo cubre tokens.node.test.ts y la
 * revisión en navegador de la Tarea 11.
 */
export async function esperarSinViolaciones(contenedor: Element): Promise<void> {
  for (const oscuro of [false, true]) {
    document.documentElement.classList.toggle("dark", oscuro)
    const { violations } = await axe.run(contenedor, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      rules: { "color-contrast": { enabled: false } },
    })
    expect(violations.map((v) => `${v.id}: ${v.help}`)).toEqual([])
  }
  document.documentElement.classList.remove("dark")
}
```

- [ ] **Step 4: Escribir las pruebas de los componentes base (fallan)**

Cree `web/src/componentes/Base.test.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Bell } from "lucide-react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ErrorApi } from "@/api"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta, EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("estados estándar", () => {
  it("EstadoCarga anuncia la carga sin texto visible", () => {
    renderizarPagina(<EstadoCarga filas={3} />)
    expect(screen.getByRole("status")).toHaveTextContent("Cargando…")
  })

  it("EstadoVacio muestra título, explicación y acción", () => {
    renderizarPagina(
      <EstadoVacio
        icono={Bell}
        titulo="Sin alertas"
        descripcion="No hay nada pendiente."
        accion={<Button>Actualizar</Button>}
      />
    )
    expect(screen.getByText("Sin alertas")).toBeInTheDocument()
    expect(screen.getByText("No hay nada pendiente.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Actualizar" })).toBeInTheDocument()
  })

  it("EstadoError usa el título de Problem Details y permite reintentar", async () => {
    const alReintentar = vi.fn()
    renderizarPagina(
      <EstadoError
        error={new ErrorApi(503, "Servicio no disponible", "Intente más tarde.")}
        alReintentar={alReintentar}
      />
    )
    expect(screen.getByRole("alert")).toHaveTextContent("Servicio no disponible")
    expect(screen.getByRole("alert")).toHaveTextContent("Intente más tarde.")
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(alReintentar).toHaveBeenCalledOnce()
  })

  it("EstadoError sin ErrorApi usa un título genérico y sin reintento no muestra el botón", () => {
    renderizarPagina(<EstadoError error={new Error("Algo falló")} />)
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar la información")
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument()
  })

  it("ContenidoConsulta pasa de error a datos al reintentar", async () => {
    let intentos = 0
    function Consulta() {
      const consulta = useQuery({
        queryKey: ["prueba"],
        queryFn: async () => {
          intentos += 1
          if (intentos === 1) throw new ErrorApi(502, "Servicio no disponible", "Caído.")
          return "datos listos"
        },
      })
      return <ContenidoConsulta consulta={consulta}>{(datos) => <p>{datos}</p>}</ContenidoConsulta>
    }
    renderizarPagina(<Consulta />)

    expect(await screen.findByRole("alert")).toHaveTextContent("Caído.")
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByText("datos listos")).toBeInTheDocument()
  })
})

describe("estructura de página", () => {
  it("EncabezadoPagina y Seccion dan títulos h1 y h2", () => {
    renderizarPagina(
      <>
        <EncabezadoPagina titulo="Precios" descripcion="Precio de referencia." />
        <Seccion titulo="Historial">contenido</Seccion>
      </>
    )
    expect(screen.getByRole("heading", { level: 1, name: "Precios" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { level: 2, name: "Historial" })).toBeInTheDocument()
  })

  it("RequiereRol muestra el contenido al rol indicado", () => {
    renderizarPagina(<RequiereRol rol="admin">Panel de admin</RequiereRol>)
    expect(screen.getByText("Panel de admin")).toBeInTheDocument()
  })

  it("RequiereRol bloquea a quien no tiene el rol", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<RequiereRol rol="admin">Panel de admin</RequiereRol>)
    expect(screen.queryByText("Panel de admin")).not.toBeInTheDocument()
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ir al tablero" })).toHaveAttribute("href", "/")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(
      <>
        <EncabezadoPagina titulo="Prueba" />
        <Seccion titulo="Sección">
          <EstadoVacio titulo="Vacío" descripcion="Nada aquí." />
        </Seccion>
        <EstadoCarga />
        <EstadoError error={new Error("x")} alReintentar={() => {}} />
      </>
    )
    await esperarSinViolaciones(container)
  })
})
```

Agregue al final de `web/src/api.test.ts` (dentro de `describe("pedir", …)`):

```ts
  it("traduce un fallo de red (fetch rechazado) a un mensaje en español", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")))

    const error = await errorDe(pedir("/x", "tk"))

    expect(error.estado).toBe(0)
    expect(error.titulo).toBe("Sin conexión")
    expect(error.message).toBe(
      "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."
    )
  })
```

- [ ] **Step 5: Verificar que fallan**

Run: `(cd web && npx vitest run src/componentes/Base.test.tsx src/api.test.ts)`
Expected: FAIL — no existen los módulos de `componentes/` y `pedir` deja escapar el `TypeError`.

- [ ] **Step 6: Implementar el error de red en `web/src/api.ts`**

Reemplace la línea `const respuesta = await fetch(...)` dentro de `pedir` por:

```ts
  let respuesta: Response
  try {
    respuesta = await fetch(`/api${ruta}`, { ...init, headers: cabeceras })
  } catch {
    // fetch rechaza, con un mensaje en inglés, cuando no hay red o el gateway no responde.
    throw new ErrorApi(
      0,
      "Sin conexión",
      "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."
    )
  }
```

- [ ] **Step 7: Implementar los componentes**

`web/src/componentes/Estados.tsx`:

```tsx
import type { UseQueryResult } from "@tanstack/react-query"
import { CircleAlert, Inbox, RefreshCw, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"
import { ErrorApi } from "@/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function EstadoCarga({ filas = 5, etiqueta = "Cargando…" }: { filas?: number; etiqueta?: string }) {
  return (
    <div role="status" className="space-y-2">
      <span className="sr-only">{etiqueta}</span>
      {Array.from({ length: filas }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  )
}

export function EstadoVacio({
  icono: Icono = Inbox,
  titulo,
  descripcion,
  accion,
}: {
  icono?: LucideIcon
  titulo: string
  descripcion: string
  accion?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center">
      <Icono aria-hidden className="size-8 text-muted-foreground" />
      <p className="font-medium">{titulo}</p>
      <p className="max-w-prose text-sm text-muted-foreground">{descripcion}</p>
      {accion && <div className="mt-2">{accion}</div>}
    </div>
  )
}

export function EstadoError({ error, alReintentar }: { error: Error; alReintentar?: () => void }) {
  const titulo = error instanceof ErrorApi ? error.titulo : "No se pudo cargar la información"
  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden />
      <AlertTitle>{titulo}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {alReintentar && (
          <Button variant="outline" size="sm" className="mt-2" onClick={alReintentar}>
            <RefreshCw aria-hidden />
            Reintentar
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

/** Muestra carga, error con "Reintentar" o el contenido de una consulta. */
export function ContenidoConsulta<T>({
  consulta,
  children,
}: {
  consulta: UseQueryResult<T>
  children: (datos: T) => ReactNode
}) {
  if (consulta.isPending) return <EstadoCarga />
  if (consulta.isError) {
    return <EstadoError error={consulta.error} alReintentar={() => void consulta.refetch()} />
  }
  return children(consulta.data)
}
```

`web/src/componentes/EncabezadoPagina.tsx`:

```tsx
import type { ReactNode } from "react"

export function EncabezadoPagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: string
  descripcion?: string
  acciones?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        {descripcion && <p className="text-sm text-muted-foreground">{descripcion}</p>}
      </div>
      {acciones && <div className="flex flex-wrap gap-2">{acciones}</div>}
    </div>
  )
}
```

`web/src/componentes/Seccion.tsx`:

```tsx
import type { ReactNode } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export function Seccion({
  titulo,
  descripcion,
  acciones,
  children,
  className,
}: {
  titulo: string
  descripcion?: string
  acciones?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">{titulo}</h2>
          {descripcion && <p className="text-sm text-muted-foreground">{descripcion}</p>}
        </div>
        {acciones}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
```

`web/src/componentes/RequiereRol.tsx`:

```tsx
import { Lock } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"
import { NOMBRES_ROL, useRoles, type Rol } from "@/auth"
import { EstadoVacio } from "@/componentes/Estados"
import { Button } from "@/components/ui/button"

/** Oculta una sección a quien no tiene el rol. Solo es interfaz: la API vuelve a validar. */
export function RequiereRol({ rol, children }: { rol: Rol; children: ReactNode }) {
  const roles = useRoles()
  if (roles.includes(rol)) return children
  return (
    <EstadoVacio
      icono={Lock}
      titulo="Acceso restringido"
      descripcion={`Esta sección es solo para el rol de ${NOMBRES_ROL[rol]}.`}
      accion={
        <Button asChild variant="outline">
          <Link to="/">Ir al tablero</Link>
        </Button>
      }
    />
  )
}
```

- [ ] **Step 8: Ajustar `badge.tsx` y `alert.tsx` al contraste**

Con estos tokens, el texto destructivo sobre su propio tinte al 10 % queda en ~4.1:1. Los estados usan contorno y texto del color (texto sobre `card`, ≥ 4.5:1 por la prueba de la Tarea 1).

En `web/src/components/ui/badge.tsx`, dentro de `variants.variant`, reemplace `destructive` y agregue `success` y `warning`:

```ts
        destructive:
          "border-destructive/40 text-destructive focus-visible:ring-destructive/20 [a]:hover:bg-destructive/10",
        success: "border-success/40 text-success [a]:hover:bg-success/10",
        warning: "border-warning/40 text-warning [a]:hover:bg-warning/10",
```

En `web/src/components/ui/alert.tsx`, en la variante `destructive`, cambie `*:data-[slot=alert-description]:text-destructive/90` por `*:data-[slot=alert-description]:text-destructive`.

- [ ] **Step 9: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/componentes/Base.test.tsx src/api.test.ts)`
Expected: PASS, salida limpia (sin advertencias).

- [ ] **Step 10: Verificación completa y commit**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)` → todo en verde.

```bash
git add web/src/componentes/Estados.tsx web/src/componentes/EncabezadoPagina.tsx web/src/componentes/Seccion.tsx web/src/componentes/RequiereRol.tsx web/src/componentes/Base.test.tsx web/src/pruebas web/src/components/ui/skeleton.tsx web/src/components/ui/badge.tsx web/src/components/ui/alert.tsx web/src/api.ts web/src/api.test.ts web/package.json web/package-lock.json
git commit -m "feat(web): estados de carga, vacío y error, utilidades de prueba con axe y error de red en español"
```

---

### Task 4: Armazón — menú lateral por rol, barra superior y migas

**Files:**
- Create (shadcn): `web/src/components/ui/sidebar.tsx`, `dropdown-menu.tsx`, `breadcrumb.tsx` y sus dependencias (`sheet.tsx`, `tooltip.tsx`, `separator.tsx`; `input.tsx` y `button.tsx` ya existen), `web/src/hooks/use-mobile.ts`
- Create: `web/src/componentes/navegacion.ts`, `navegacion.test.ts`, `BarraLateral.tsx`, `BarraSuperior.tsx`
- Modify: `web/src/componentes/Layout.tsx`, `web/src/componentes/Layout.test.tsx`

**Interfaces:**
- Consumes: `useRoles`, `NOMBRES_ROL` (`@/auth`); `useTema`, `NOMBRES_TEMA`, `Tema` (Tarea 2); `tokenConRoles`, `esperarSinViolaciones` (Tarea 3).
- Produces:
  - `type ElementoNavegacion = { titulo: string; ruta: string; icono: LucideIcon; soloAdmin?: boolean }`, `type SeccionNavegacion = { titulo: string; elementos: ElementoNavegacion[] }`, `type Miga = { titulo: string; ruta?: string }`
  - `NAVEGACION: SeccionNavegacion[]` — Resumen: Tablero `/` · Proveedores: Proveedores `/proveedores`, Ranking `/ranking` · Inteligencia: Precios `/precios`, Alertas `/alertas` · Datos: Importación `/importacion` y Configuración `/configuracion` (ambos `soloAdmin`).
  - `navegacionPara(roles: Rol[]): SeccionNavegacion[]`, `estaActiva(ruta: string, pathname: string): boolean`, `migasDe(pathname: string): Miga[]`
  - `Layout` (misma firma): `SidebarProvider` + `BarraLateral` + `SidebarInset` (el único `<main>`) con `BarraSuperior` y `<div id="contenido">` con el `Outlet`; enlace "Saltar al contenido"; `document.title = "<última miga> · PluriOne"`.
  - Nombres accesibles que usan las pruebas: navegación "Principal", migas "Ruta de navegación", botones "Mostrar u ocultar el menú", "Alertas", "Tema: <Claro|Oscuro|Sistema>", "Cuenta de <nombre>"; elemento de menú "Cerrar sesión".

- [ ] **Step 1: Instalar los componentes de shadcn**

Run: `(cd web && npx shadcn@4.21.0 add sidebar dropdown-menu breadcrumb --yes)`

Run: `git status --short` y `git diff --stat`. Restaure con `git checkout -- <archivo>` cualquier archivo **que ya existía** y el CLI modificó (en especial `web/src/index.css`, `button.tsx`, `input.tsx`, `badge.tsx`, `alert.tsx`): los tokens y los ajustes de las Tareas 1 y 3 se conservan.

Run: `grep -n "data-active\|<main" web/src/components/ui/sidebar.tsx`
Expected: `SidebarMenuButton` marca la opción activa con `data-active` y `SidebarInset` renderiza `<main>`. Si alguno difiere, ajuste el código de los Steps 6 y 7 (la clase `data-[active=true]:` y el único `<main>`) y anótelo en el reporte.

- [ ] **Step 2: Traducir los textos para lectores de pantalla de los componentes generados**

Run: `grep -rnE "Toggle Sidebar|>Sidebar<|Displays the mobile sidebar|>Close<|\"Close\"|>More<|\"breadcrumb\"" web/src/components/ui`

Reemplace cada aparición:

| Inglés | Español |
|---|---|
| `Toggle Sidebar` (texto `sr-only`, `aria-label` y `title`) | `Mostrar u ocultar el menú` |
| `Sidebar` (título del `Sheet` móvil) | `Menú` |
| `Displays the mobile sidebar.` | `Menú principal de la plataforma.` |
| `Close` (botón de cierre del `Sheet`) | `Cerrar` |
| `More` (puntos suspensivos de las migas) | `Más` |
| `aria-label="breadcrumb"` | `aria-label="Ruta de navegación"` |

Run de nuevo el `grep` → Expected: sin resultados.

- [ ] **Step 3: Escribir las pruebas de navegación (fallan)**

`web/src/componentes/navegacion.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { estaActiva, migasDe, navegacionPara } from "@/componentes/navegacion"

const titulos = (roles: Parameters<typeof navegacionPara>[0]) =>
  navegacionPara(roles).flatMap((s) => s.elementos.map((e) => e.titulo))

describe("navegacionPara", () => {
  it("oculta Importación y Configuración a quien no es admin", () => {
    expect(titulos(["comprador"])).toEqual(["Tablero", "Proveedores", "Ranking", "Precios", "Alertas"])
    expect(titulos([])).toEqual(["Tablero", "Proveedores", "Ranking", "Precios", "Alertas"])
  })

  it("muestra todo al admin, agrupado por sección", () => {
    const secciones = navegacionPara(["admin"])
    expect(secciones.map((s) => s.titulo)).toEqual(["Resumen", "Proveedores", "Inteligencia", "Datos"])
    expect(titulos(["admin"])).toContain("Configuración")
  })

  it("descarta las secciones que quedan vacías", () => {
    expect(navegacionPara(["aprobador"]).map((s) => s.titulo)).not.toContain("Datos")
  })
})

describe("estaActiva", () => {
  it.each([
    ["/", "/", true],
    ["/", "/proveedores", false],
    ["/proveedores", "/proveedores", true],
    ["/proveedores", "/proveedores/abc", true],
    ["/proveedores", "/proveedoresx", false],
  ])("ruta %s en %s → %s", (ruta, pathname, esperado) => {
    expect(estaActiva(ruta, pathname)).toBe(esperado)
  })
})

describe("migasDe", () => {
  it.each([
    ["/", [{ titulo: "Resumen" }, { titulo: "Tablero" }]],
    ["/proveedores", [{ titulo: "Proveedores" }]],
    ["/proveedores/", [{ titulo: "Proveedores" }]],
    ["/proveedores/abc", [{ titulo: "Proveedores", ruta: "/proveedores" }, { titulo: "Detalle" }]],
    ["/ranking", [{ titulo: "Proveedores" }, { titulo: "Ranking" }]],
    ["/precios", [{ titulo: "Inteligencia" }, { titulo: "Precios" }]],
    ["/no-existe", [{ titulo: "Página no encontrada" }]],
  ])("%s", (pathname, esperado) => {
    expect(migasDe(pathname)).toEqual(esperado)
  })
})
```

Reemplace `web/src/componentes/Layout.test.tsx`:

```tsx
import { cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Layout } from "@/componentes/Layout"
import { tokenConRoles } from "@/pruebas/sesion"
import { esperarSinViolaciones } from "@/pruebas/utilidades"
import { CLAVE_TEMA, ProveedorTema } from "@/tema"

const removeUser = vi.fn().mockResolvedValue(undefined)
const signinRedirect = vi.fn().mockResolvedValue(undefined)
const signoutRedirect = vi.fn().mockResolvedValue(undefined)
const estado = vi.hoisted(() => ({ autenticacion: {} as object }))

vi.mock("react-oidc-context", () => ({
  hasAuthParams: () => false,
  useAuth: () => estado.autenticacion,
}))

function sesionCon(roles: string[]) {
  return {
    isAuthenticated: true,
    isLoading: false,
    activeNavigator: undefined,
    error: undefined,
    user: {
      access_token: tokenConRoles(roles),
      profile: { given_name: "Ana", family_name: "López", preferred_username: "ana.lopez" },
    },
    removeUser,
    signinRedirect,
    signoutRedirect,
  }
}

function renderizar(ruta = "/") {
  return render(
    <ProveedorTema>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="*" element={<h1>Contenido de prueba</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ProveedorTema>
  )
}

beforeEach(() => {
  estado.autenticacion = sesionCon(["comprador"])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  localStorage.clear()
  document.documentElement.classList.remove("dark")
})

describe("Layout con la sesión en error", () => {
  it("muestra un mensaje en español y permite volver a iniciar sesión", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    estado.autenticacion = {
      error: new Error("invalid_grant: Token is not active"),
      isAuthenticated: false,
      isLoading: false,
      activeNavigator: undefined,
      user: null,
      removeUser,
      signinRedirect,
    }
    renderizar()

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Su sesión expiró o no se pudo iniciar sesión."
    )
    expect(screen.queryByText(/invalid_grant/)).not.toBeInTheDocument()
    expect(signinRedirect).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: "Volver a iniciar sesión" }))

    expect(removeUser).toHaveBeenCalledOnce()
    expect(signinRedirect).toHaveBeenCalledOnce()
    expect(removeUser.mock.invocationCallOrder[0]).toBeLessThan(
      signinRedirect.mock.invocationCallOrder[0]
    )
  })
})

describe("Layout con sesión iniciada", () => {
  it("muestra a un comprador solo las secciones que le corresponden", () => {
    renderizar()
    const menu = screen.getByRole("navigation", { name: "Principal" })
    for (const nombre of ["Tablero", "Proveedores", "Ranking", "Precios", "Alertas"]) {
      expect(within(menu).getByRole("link", { name: nombre })).toBeInTheDocument()
    }
    expect(within(menu).queryByRole("link", { name: "Importación" })).not.toBeInTheDocument()
    expect(within(menu).queryByRole("link", { name: "Configuración" })).not.toBeInTheDocument()
  })

  it("muestra al admin Importación y Configuración", () => {
    estado.autenticacion = sesionCon(["admin"])
    renderizar()
    const menu = screen.getByRole("navigation", { name: "Principal" })
    expect(within(menu).getByRole("link", { name: "Importación" })).toHaveAttribute("href", "/importacion")
    expect(within(menu).getByRole("link", { name: "Configuración" })).toHaveAttribute(
      "href",
      "/configuracion"
    )
  })

  it("marca la página actual, muestra las migas y titula el documento", () => {
    renderizar("/proveedores/abc")
    const menu = screen.getByRole("navigation", { name: "Principal" })
    expect(within(menu).getByRole("link", { name: "Proveedores" })).toHaveAttribute("aria-current", "page")
    expect(within(menu).getByRole("link", { name: "Tablero" })).not.toHaveAttribute("aria-current")

    const migas = screen.getByRole("navigation", { name: "Ruta de navegación" })
    expect(within(migas).getByRole("link", { name: "Proveedores" })).toHaveAttribute("href", "/proveedores")
    expect(within(migas).getByText("Detalle")).toHaveAttribute("aria-current", "page")
    expect(document.title).toBe("Detalle · PluriOne")
  })

  it("tiene un solo main, enlace para saltar al contenido y controles en español", () => {
    renderizar()
    expect(screen.getAllByRole("main")).toHaveLength(1)
    expect(screen.getByRole("link", { name: "Saltar al contenido" })).toHaveAttribute("href", "#contenido")
    expect(document.getElementById("contenido")).toContainElement(
      screen.getByRole("heading", { name: "Contenido de prueba" })
    )
    expect(screen.getByRole("button", { name: "Mostrar u ocultar el menú" })).toBeInTheDocument()
  })

  it("cambia el tema desde la barra superior", async () => {
    renderizar()
    await userEvent.click(screen.getByRole("button", { name: "Tema: Sistema" }))
    await userEvent.click(await screen.findByRole("menuitemradio", { name: "Oscuro" }))

    expect(document.documentElement).toHaveClass("dark")
    expect(localStorage.getItem(CLAVE_TEMA)).toBe("oscuro")
    expect(screen.getByRole("button", { name: "Tema: Oscuro" })).toBeInTheDocument()
  })

  it("muestra el usuario con sus roles y cierra sesión", async () => {
    estado.autenticacion = sesionCon(["comprador", "aprobador"])
    renderizar()
    await userEvent.click(screen.getByRole("button", { name: "Cuenta de Ana López" }))

    expect(await screen.findByText("Compras · Aprobación")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("menuitem", { name: "Cerrar sesión" }))
    expect(signoutRedirect).toHaveBeenCalledOnce()
  })

  it("el menú de alertas enlaza a la página de alertas", async () => {
    renderizar()
    await userEvent.click(screen.getByRole("button", { name: "Alertas" }))

    expect(await screen.findByText("No hay alertas activas")).toBeInTheDocument()
    expect(screen.getByRole("menuitem", { name: "Ver todas las alertas" })).toHaveAttribute(
      "href",
      "/alertas"
    )
  })

  it("no tiene violaciones de accesibilidad", async () => {
    estado.autenticacion = sesionCon(["admin"])
    const { container } = renderizar("/proveedores")
    await esperarSinViolaciones(container)
  })
})
```

- [ ] **Step 4: Verificar que fallan**

Run: `(cd web && npx vitest run src/componentes/navegacion.test.ts src/componentes/Layout.test.tsx)`
Expected: FAIL — no existe `@/componentes/navegacion` y el `Layout` actual no tiene menú lateral ni barra superior (la prueba de sesión en error sigue pasando).

- [ ] **Step 5: Implementar `web/src/componentes/navegacion.ts`**

```ts
import {
  Bell,
  Building2,
  FileUp,
  LayoutDashboard,
  Settings,
  Tags,
  Trophy,
  type LucideIcon,
} from "lucide-react"
import type { Rol } from "@/auth"

export type ElementoNavegacion = {
  titulo: string
  ruta: string
  icono: LucideIcon
  soloAdmin?: boolean
}
export type SeccionNavegacion = { titulo: string; elementos: ElementoNavegacion[] }
export type Miga = { titulo: string; ruta?: string }

export const NAVEGACION: SeccionNavegacion[] = [
  { titulo: "Resumen", elementos: [{ titulo: "Tablero", ruta: "/", icono: LayoutDashboard }] },
  {
    titulo: "Proveedores",
    elementos: [
      { titulo: "Proveedores", ruta: "/proveedores", icono: Building2 },
      { titulo: "Ranking", ruta: "/ranking", icono: Trophy },
    ],
  },
  {
    titulo: "Inteligencia",
    elementos: [
      { titulo: "Precios", ruta: "/precios", icono: Tags },
      { titulo: "Alertas", ruta: "/alertas", icono: Bell },
    ],
  },
  {
    titulo: "Datos",
    elementos: [
      { titulo: "Importación", ruta: "/importacion", icono: FileUp, soloAdmin: true },
      { titulo: "Configuración", ruta: "/configuracion", icono: Settings, soloAdmin: true },
    ],
  },
]

/** Menú visible para los roles dados; la API vuelve a validar cada permiso. */
export function navegacionPara(roles: Rol[]): SeccionNavegacion[] {
  const esAdmin = roles.includes("admin")
  return NAVEGACION.map((seccion) => ({
    ...seccion,
    elementos: seccion.elementos.filter((e) => esAdmin || !e.soloAdmin),
  })).filter((seccion) => seccion.elementos.length > 0)
}

export function estaActiva(ruta: string, pathname: string): boolean {
  if (ruta === "/") return pathname === "/"
  return pathname === ruta || pathname.startsWith(`${ruta}/`)
}

/** Migas de pan: sección › página › detalle (la sección se omite si se llama igual que la página). */
export function migasDe(pathname: string): Miga[] {
  const [, primero = "", ...resto] = pathname.split("/")
  const base = `/${primero}`
  for (const seccion of NAVEGACION) {
    const elemento = seccion.elementos.find((e) => e.ruta === base)
    if (!elemento) continue
    const migas: Miga[] = seccion.titulo === elemento.titulo ? [] : [{ titulo: seccion.titulo }]
    if (resto.some(Boolean)) {
      return [...migas, { titulo: elemento.titulo, ruta: elemento.ruta }, { titulo: "Detalle" }]
    }
    return [...migas, { titulo: elemento.titulo }]
  }
  return [{ titulo: "Página no encontrada" }]
}
```

- [ ] **Step 6: Implementar `web/src/componentes/BarraLateral.tsx`**

```tsx
import { Hexagon } from "lucide-react"
import { Link, useLocation } from "react-router"
import { useRoles } from "@/auth"
import { estaActiva, navegacionPara } from "@/componentes/navegacion"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export function BarraLateral() {
  const { pathname } = useLocation()
  const roles = useRoles()
  const { isMobile, setOpenMobile } = useSidebar()
  // En móvil el menú es un panel deslizable: se cierra al elegir una opción.
  const alNavegar = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/" onClick={alNavegar}>
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <Hexagon aria-hidden className="size-4" />
                </span>
                <span className="grid leading-tight">
                  <span className="font-semibold">PluriOne</span>
                  <span className="text-xs text-sidebar-foreground/70">
                    Negociación con proveedores
                  </span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <nav aria-label="Principal">
          {navegacionPara(roles).map((seccion) => (
            <SidebarGroup key={seccion.titulo}>
              <SidebarGroupLabel>{seccion.titulo}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {seccion.elementos.map(({ titulo, ruta, icono: Icono }) => {
                    const activa = estaActiva(ruta, pathname)
                    return (
                      <SidebarMenuItem key={ruta}>
                        <SidebarMenuButton
                          asChild
                          isActive={activa}
                          tooltip={titulo}
                          className="data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground"
                        >
                          <Link
                            to={ruta}
                            aria-current={activa ? "page" : undefined}
                            onClick={alNavegar}
                          >
                            <Icono aria-hidden />
                            <span>{titulo}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </nav>
      </SidebarContent>
    </Sidebar>
  )
}
```

- [ ] **Step 7: Implementar `web/src/componentes/BarraSuperior.tsx` y el nuevo `Layout.tsx`**

`web/src/componentes/BarraSuperior.tsx`:

```tsx
import { Bell, BellOff, LogOut, Monitor, Moon, Sun, type LucideIcon } from "lucide-react"
import { Fragment } from "react"
import { useAuth } from "react-oidc-context"
import { Link, useLocation } from "react-router"
import { NOMBRES_ROL, useRoles } from "@/auth"
import { migasDe } from "@/componentes/navegacion"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { NOMBRES_TEMA, useTema, type Tema } from "@/tema"

const ICONOS_TEMA: Record<Tema, LucideIcon> = { claro: Sun, oscuro: Moon, sistema: Monitor }

function Migas() {
  const migas = migasDe(useLocation().pathname)
  return (
    <Breadcrumb>
      <BreadcrumbList>
        {migas.map((miga, i) => {
          const ultima = i === migas.length - 1
          return (
            <Fragment key={`${i}-${miga.titulo}`}>
              {i > 0 && <BreadcrumbSeparator className="hidden md:block" />}
              <BreadcrumbItem className={ultima ? undefined : "hidden md:inline-flex"}>
                {ultima ? (
                  <BreadcrumbPage>{miga.titulo}</BreadcrumbPage>
                ) : miga.ruta ? (
                  <BreadcrumbLink asChild>
                    <Link to={miga.ruta}>{miga.titulo}</Link>
                  </BreadcrumbLink>
                ) : (
                  <span>{miga.titulo}</span>
                )}
              </BreadcrumbItem>
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}

/** Campana: el conteo y las 5 alertas más severas llegan en el Plan B. */
function MenuAlertas() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-lg" aria-label="Alertas">
          <Bell aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel>Alertas</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <p className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
          <BellOff aria-hidden className="size-4" />
          No hay alertas activas
        </p>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/alertas">Ver todas las alertas</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function SelectorTema() {
  const { tema, cambiarTema } = useTema()
  const Icono = ICONOS_TEMA[tema]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-lg" aria-label={`Tema: ${NOMBRES_TEMA[tema]}`}>
          <Icono aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Tema</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={tema} onValueChange={(valor) => cambiarTema(valor as Tema)}>
          {(Object.keys(NOMBRES_TEMA) as Tema[]).map((opcion) => {
            const IconoOpcion = ICONOS_TEMA[opcion]
            return (
              <DropdownMenuRadioItem key={opcion} value={opcion}>
                <IconoOpcion aria-hidden />
                {NOMBRES_TEMA[opcion]}
              </DropdownMenuRadioItem>
            )
          })}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function MenuUsuario() {
  const auth = useAuth()
  const roles = useRoles()
  const perfil = auth.user?.profile
  const nombre =
    [perfil?.given_name, perfil?.family_name].filter(Boolean).join(" ") ||
    perfil?.preferred_username ||
    "Usuario"
  const iniciales = nombre
    .split(" ")
    .map((parte) => parte[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-2" aria-label={`Cuenta de ${nombre}`}>
          <span
            aria-hidden
            className="flex size-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
          >
            {iniciales}
          </span>
          <span className="hidden text-sm font-medium md:inline">{nombre}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="space-y-0.5">
          <span className="block font-medium">{nombre}</span>
          <span className="block text-xs font-normal text-muted-foreground">
            {roles.map((rol) => NOMBRES_ROL[rol]).join(" · ") || "Sin rol asignado"}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void auth.signoutRedirect()}>
          <LogOut aria-hidden />
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function BarraSuperior() {
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
      <Migas />
      <div className="ml-auto flex items-center gap-1">
        <MenuAlertas />
        <SelectorTema />
        <MenuUsuario />
      </div>
    </header>
  )
}
```

Reemplace `web/src/componentes/Layout.tsx`:

```tsx
import { useEffect } from "react"
import { hasAuthParams, useAuth } from "react-oidc-context"
import { Outlet, useLocation } from "react-router"
import { BarraLateral } from "@/componentes/BarraLateral"
import { BarraSuperior } from "@/componentes/BarraSuperior"
import { migasDe } from "@/componentes/navegacion"
import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"

export function Layout() {
  const auth = useAuth()
  const { pathname } = useLocation()

  useEffect(() => {
    const puedeRedirigir =
      !hasAuthParams() && !auth.isAuthenticated && !auth.activeNavigator && !auth.isLoading
    if (puedeRedirigir && !auth.error) void auth.signinRedirect()
  }, [auth])

  // El mensaje original de la librería suele venir en inglés: solo se registra, no se muestra.
  useEffect(() => {
    if (auth.error) console.error("Error de sesión:", auth.error)
  }, [auth.error])

  // Cada página tiene su propio título (lo anuncian los lectores de pantalla al navegar).
  useEffect(() => {
    const migas = migasDe(pathname)
    document.title = `${migas[migas.length - 1].titulo} · PluriOne`
  }, [pathname])

  async function volverAIniciarSesion() {
    await auth
      .removeUser()
      .catch((error: unknown) => console.error("No se pudo limpiar la sesión:", error))
    await auth.signinRedirect()
  }

  if (auth.error) {
    return (
      <div role="alert" className="space-y-3 p-6">
        <p>Su sesión expiró o no se pudo iniciar sesión.</p>
        <Button onClick={() => void volverAIniciarSesion()}>Volver a iniciar sesión</Button>
      </div>
    )
  }
  if (!auth.isAuthenticated) {
    return <p className="p-6 text-muted-foreground">Redirigiendo al inicio de sesión…</p>
  }

  return (
    <TooltipProvider>
      <SidebarProvider>
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
        >
          Saltar al contenido
        </a>
        <BarraLateral />
        <SidebarInset>
          <BarraSuperior />
          <div
            id="contenido"
            tabIndex={-1}
            className="mx-auto w-full max-w-7xl flex-1 p-4 outline-none md:p-6 lg:p-8"
          >
            <Outlet />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
```

- [ ] **Step 8: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/componentes/navegacion.test.ts src/componentes/Layout.test.tsx)`
Expected: PASS, salida limpia. Si axe reporta algo de los componentes generados, corríjalo en el componente (no desactive reglas) y anótelo en el reporte.

- [ ] **Step 9: Verificación completa y commit**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)` → todo en verde.

```bash
git add web/src/components/ui web/src/hooks web/src/componentes/navegacion.ts web/src/componentes/navegacion.test.ts web/src/componentes/BarraLateral.tsx web/src/componentes/BarraSuperior.tsx web/src/componentes/Layout.tsx web/src/componentes/Layout.test.tsx web/package.json web/package-lock.json
git commit -m "feat(web): armazón con menú lateral por rol, barra superior, migas y selector de tema"
```

---

### Task 5: Lista de proveedores rediseñada con estado en la URL

**Files:**
- Create: `web/src/parametros.ts`, `web/src/parametros.test.ts`, `web/src/componentes/EtiquetaEstado.tsx`
- Modify: `web/src/paginas/Proveedores.tsx` (reemplazo completo), `web/src/tipos.ts` (agregar `CATEGORIAS`)
- Test: `web/src/paginas/Proveedores.test.tsx`

**Interfaces:**
- Consumes: `EncabezadoPagina`, `EstadoCarga`, `EstadoVacio`, `EstadoError` (Tarea 3); `renderizarPagina`, `simularApi`, `urlDeLlamada`, `ubicacionActual`, `esperarSinViolaciones`, `sesionDePrueba` (Tarea 3).
- Produces:
  - `enteroPositivo(valor: string | null, porDefecto: number, maximo = Number.MAX_SAFE_INTEGER): number`
  - `unoDe<T extends string>(valor: string | null, permitidos: readonly T[]): T | null`
  - `useParametros(): [URLSearchParams, (cambios: Record<string, string | null>) => void]` — `null` borra la clave; agrega una entrada al historial.
  - `CATEGORIAS: Categoria[]` en `@/tipos`.
  - `EtiquetaEstado({ activo: boolean })` — insignia "Activo" (icono + texto, `success`) o "Inactivo" (contorno).
  - Parámetros de URL de `/proveedores`: `q`, `categoria`, `estado` (`activos | inactivos`), `pagina` (1-based). Claves de consulta: `["proveedores", { q, categoria, estado, pagina }]` (Importación invalida el prefijo `["proveedores"]`).

- [ ] **Step 1: Escribir las pruebas de `parametros.ts` (fallan)**

`web/src/parametros.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { enteroPositivo, unoDe } from "@/parametros"

describe("enteroPositivo", () => {
  it.each([
    ["3", 3],
    [null, 1],
    ["", 1],
    ["abc", 1],
    ["0", 1],
    ["-2", 1],
    ["2.5", 1],
  ])("%s → %d", (valor, esperado) => {
    expect(enteroPositivo(valor, 1)).toBe(esperado)
  })

  it("limita al máximo", () => {
    expect(enteroPositivo("999999999", 1, 40_000)).toBe(40_000)
  })
})

describe("unoDe", () => {
  it("acepta solo valores permitidos", () => {
    expect(unoDe("nube", ["nube", "soporte"])).toBe("nube")
    expect(unoDe("hackeo", ["nube", "soporte"])).toBeNull()
    expect(unoDe(null, ["nube"])).toBeNull()
  })
})
```

Run: `(cd web && npx vitest run src/parametros.test.ts)` → Expected: FAIL (no existe `@/parametros`).

- [ ] **Step 2: Implementar `web/src/parametros.ts`**

```ts
import { useSearchParams } from "react-router"

/** Entero ≥ 1 leído de la URL; cualquier otro valor cuenta como el valor por defecto. */
export function enteroPositivo(
  valor: string | null,
  porDefecto: number,
  maximo = Number.MAX_SAFE_INTEGER
): number {
  const numero = Number(valor)
  if (!valor || !Number.isInteger(numero) || numero < 1) return porDefecto
  return Math.min(numero, maximo)
}

/** El valor solo si está en la lista permitida (la URL se puede editar a mano). */
export function unoDe<T extends string>(valor: string | null, permitidos: readonly T[]): T | null {
  return permitidos.includes(valor as T) ? (valor as T) : null
}

/** Parámetros de búsqueda de la URL y una función para cambiarlos (`null` borra la clave). */
export function useParametros(): [URLSearchParams, (cambios: Record<string, string | null>) => void] {
  const [parametros, setParametros] = useSearchParams()
  function actualizar(cambios: Record<string, string | null>) {
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      for (const [clave, valor] of Object.entries(cambios)) {
        if (valor) siguientes.set(clave, valor)
        else siguientes.delete(clave)
      }
      return siguientes
    })
  }
  return [parametros, actualizar]
}
```

Run: `(cd web && npx vitest run src/parametros.test.ts)` → Expected: PASS.

- [ ] **Step 3: Escribir las pruebas de la página (fallan)**

`web/src/paginas/Proveedores.test.tsx`:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Proveedores } from "@/paginas/Proveedores"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

const PAGINA = {
  total: 2,
  elementos: [
    { id: "p1", rfc: "AAA010101AAA", nombre: "Nube Andina", tamano: "mediana", categorias: ["nube"], activo: true },
    {
      id: "p2",
      rfc: "BBB020202BBB",
      nombre: "Consultores Bajío",
      tamano: "pequena",
      categorias: ["consultoria", "soporte"],
      activo: false,
    },
  ],
}
const VACIA = { total: 0, elementos: [] }

function apiDeProveedores(pagina: object = PAGINA) {
  return simularApi((url) =>
    url.startsWith("/api/proveedores/proveedores?")
      ? respuestaJson(pagina)
      : new Response("", { status: 404 })
  )
}

const renderizar = (ruta = "/proveedores") => renderizarPagina(<Proveedores />, { ruta })

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Proveedores", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})))
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista los proveedores con RFC, categorías y estado", async () => {
    apiDeProveedores()
    renderizar()

    const tabla = await screen.findByRole("table")
    expect(within(tabla).getByRole("link", { name: "Nube Andina" })).toHaveAttribute("href", "/proveedores/p1")
    expect(within(tabla).getByText("AAA010101AAA")).toBeInTheDocument()
    expect(within(tabla).getByText("Consultoría")).toBeInTheDocument()
    expect(within(tabla).getByText("Activo")).toBeInTheDocument()
    expect(within(tabla).getByText("Inactivo")).toBeInTheDocument()
    expect(screen.getByText("Mostrando 1–2 de 2 proveedores")).toBeInTheDocument()
  })

  it("filtra por categoría y estado, y cada filtro vuelve a la primera página", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=3")
    await screen.findByRole("table")
    expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("50")

    await userEvent.click(screen.getByRole("button", { name: "Nube" }))
    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("categoria")).toBe("nube"))
    expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("0")
    expect(ubicacionActual()).toBe("/proveedores?categoria=nube")
    expect(screen.getByRole("button", { name: "Nube" })).toHaveAttribute("aria-pressed", "true")

    await userEvent.click(screen.getByRole("button", { name: "Inactivos" }))
    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("activo")).toBe("false"))
    expect(ubicacionActual()).toBe("/proveedores?categoria=nube&estado=inactivos")
  })

  it("busca por nombre o RFC", async () => {
    const simulado = apiDeProveedores()
    renderizar()
    await screen.findByRole("table")

    await userEvent.type(screen.getByLabelText("Buscar por nombre o RFC"), "  andina ")
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }))

    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("q")).toBe("andina"))
    expect(ubicacionActual()).toBe("/proveedores?q=andina")
  })

  it("pagina con Siguiente", async () => {
    const simulado = apiDeProveedores({ ...PAGINA, total: 60 })
    renderizar()
    expect(await screen.findByText("Mostrando 1–25 de 60 proveedores")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled()

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))

    await waitFor(() => expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("25"))
    expect(ubicacionActual()).toBe("/proveedores?pagina=2")
    expect(await screen.findByText("Mostrando 26–50 de 60 proveedores")).toBeInTheDocument()
  })

  it("ignora parámetros inválidos de la URL", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=abc&categoria=hackeo&estado=quiza")
    await screen.findByRole("table")

    const url = urlDeLlamada(simulado)
    expect(url.searchParams.get("desplazamiento")).toBe("0")
    expect(url.searchParams.has("categoria")).toBe(false)
    expect(url.searchParams.has("activo")).toBe(false)
  })

  it("limita la página al máximo que acepta la API", async () => {
    const simulado = apiDeProveedores()
    renderizar("/proveedores?pagina=999999999")
    await waitFor(() =>
      expect(urlDeLlamada(simulado).searchParams.get("desplazamiento")).toBe("999975")
    )
  })

  it("sin proveedores invita al administrador a importar", async () => {
    sesionDePrueba.roles = ["admin"]
    apiDeProveedores(VACIA)
    renderizar()

    expect(await screen.findByText("Aún no hay proveedores")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ir a Importación" })).toHaveAttribute("href", "/importacion")
  })

  it("sin proveedores, un comprador recibe la indicación sin enlace de importación", async () => {
    apiDeProveedores(VACIA)
    renderizar()

    expect(await screen.findByText("Pida a un administrador que importe el catálogo del ERP.")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "Ir a Importación" })).not.toBeInTheDocument()
  })

  it("sin resultados con filtros ofrece limpiarlos", async () => {
    apiDeProveedores(VACIA)
    renderizar("/proveedores?q=zzz&categoria=nube")

    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
    const botones = screen.getAllByRole("button", { name: "Limpiar filtros" })
    await userEvent.click(botones[botones.length - 1])
    expect(ubicacionActual()).toBe("/proveedores")
  })

  it("muestra el error en español y permite reintentar", async () => {
    let fallar = true
    simularApi(() => (fallar ? new Response("Bad Gateway", { status: 502 }) : respuestaJson(PAGINA)))
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible; intente más tarde."
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByRole("link", { name: "Nube Andina" })).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    apiDeProveedores()
    const { container } = renderizar()
    await screen.findByRole("table")
    await esperarSinViolaciones(container)
  })
})
```

Run: `(cd web && npx vitest run src/paginas/Proveedores.test.tsx)` → Expected: FAIL (la página actual no usa la URL ni los estados nuevos).

- [ ] **Step 4: Agregar `CATEGORIAS` a `web/src/tipos.ts` y crear `EtiquetaEstado`**

Debajo de `NOMBRES_CATEGORIA` en `web/src/tipos.ts`:

```ts
export const CATEGORIAS = Object.keys(NOMBRES_CATEGORIA) as Categoria[]
```

`web/src/componentes/EtiquetaEstado.tsx`:

```tsx
import { CircleCheck, CircleOff } from "lucide-react"
import { Badge } from "@/components/ui/badge"

export function EtiquetaEstado({ activo }: { activo: boolean }) {
  return activo ? (
    <Badge variant="success">
      <CircleCheck aria-hidden />
      Activo
    </Badge>
  ) : (
    <Badge variant="outline">
      <CircleOff aria-hidden />
      Inactivo
    </Badge>
  )
}
```

- [ ] **Step 5: Reemplazar `web/src/paginas/Proveedores.tsx`**

```tsx
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, Search, X } from "lucide-react"
import type { FormEvent, ReactNode } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, NOMBRES_TAMANO, type PaginaProveedores } from "@/tipos"

const POR_PAGINA = 25
const PAGINA_MAXIMA = 40_000 // la API acepta desplazamientos de hasta 1,000,000
const ESTADOS = ["activos", "inactivos"] as const

function Filtro({ activo, onClick, children }: { activo: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <Button
      type="button"
      size="sm"
      variant={activo ? "default" : "outline"}
      aria-pressed={activo}
      className="rounded-full"
      onClick={onClick}
    >
      {children}
    </Button>
  )
}

export function Proveedores() {
  const token = useToken()
  const roles = useRoles()
  const [parametros, actualizar] = useParametros()
  const q = (parametros.get("q") ?? "").trim().slice(0, 100)
  const categoria = unoDe(parametros.get("categoria"), CATEGORIAS)
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const pagina = enteroPositivo(parametros.get("pagina"), 1, PAGINA_MAXIMA)
  const hayFiltros = Boolean(q || categoria || estado)

  const consulta = useQuery({
    queryKey: ["proveedores", { q, categoria, estado, pagina }],
    queryFn: () => {
      const busqueda = new URLSearchParams({
        limite: String(POR_PAGINA),
        desplazamiento: String((pagina - 1) * POR_PAGINA),
      })
      if (q) busqueda.set("q", q)
      if (categoria) busqueda.set("categoria", categoria)
      if (estado) busqueda.set("activo", String(estado === "activos"))
      return pedir<PaginaProveedores>(`/proveedores/proveedores?${busqueda}`, token)
    },
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = String(new FormData(evento.currentTarget).get("q") ?? "").trim()
    actualizar({ q: texto || null, pagina: null })
  }
  const limpiar = () => actualizar({ q: null, categoria: null, estado: null, pagina: null })
  const botonLimpiar = (
    <Button type="button" variant="ghost" onClick={limpiar}>
      <X aria-hidden />
      Limpiar filtros
    </Button>
  )

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError) {
      return <EstadoError error={consulta.error} alReintentar={() => void consulta.refetch()} />
    }
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      if (hayFiltros) {
        return (
          <EstadoVacio
            titulo="Sin resultados"
            descripcion="Ningún proveedor coincide con la búsqueda o los filtros."
            accion={botonLimpiar}
          />
        )
      }
      if (pagina > 1) {
        return (
          <EstadoVacio
            titulo="Esta página no tiene resultados"
            descripcion={`Hay ${total.toLocaleString("es-MX")} proveedores en total.`}
            accion={
              <Button variant="outline" onClick={() => actualizar({ pagina: null })}>
                Ir a la primera página
              </Button>
            }
          />
        )
      }
      const esAdmin = roles.includes("admin")
      return (
        <EstadoVacio
          titulo="Aún no hay proveedores"
          descripcion={
            esAdmin
              ? "Importe el catálogo de proveedores del ERP para comenzar."
              : "Pida a un administrador que importe el catálogo del ERP."
          }
          accion={
            esAdmin && (
              <Button asChild>
                <Link to="/importacion">Ir a Importación</Link>
              </Button>
            )
          }
        />
      )
    }

    const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))
    const desde = (pagina - 1) * POR_PAGINA + 1
    const hasta = Math.min(pagina * POR_PAGINA, total)
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Proveedor</TableHead>
              <TableHead>Categorías</TableHead>
              <TableHead>Tamaño</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <Link
                    to={`/proveedores/${encodeURIComponent(p.id)}`}
                    className="font-medium text-accent hover:underline"
                  >
                    {p.nombre}
                  </Link>
                  <div className="font-mono text-xs text-muted-foreground">{p.rfc}</div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {p.categorias.map((c) => (
                      <Badge key={c} variant="secondary">
                        {NOMBRES_CATEGORIA[c] ?? c}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>{NOMBRES_TAMANO[p.tamano] ?? p.tamano}</TableCell>
                <TableCell>
                  <EtiquetaEstado activo={p.activo} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
          <span aria-live="polite">
            Mostrando {desde.toLocaleString("es-MX")}–{hasta.toLocaleString("es-MX")} de{" "}
            {total.toLocaleString("es-MX")} proveedores
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagina <= 1}
              onClick={() => actualizar({ pagina: String(pagina - 1) })}
            >
              <ArrowLeft aria-hidden />
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pagina >= paginas}
              onClick={() => actualizar({ pagina: String(pagina + 1) })}
            >
              Siguiente
              <ArrowRight aria-hidden />
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Proveedores"
        descripcion="Proveedores de servicios de TI con sus categorías y su estado."
      />
      <Card>
        <CardContent className="space-y-4">
          <form role="search" onSubmit={buscar} className="flex flex-wrap items-center gap-2">
            <label htmlFor="busqueda" className="sr-only">
              Buscar por nombre o RFC
            </label>
            <div className="relative w-full max-w-sm">
              <Search
                aria-hidden
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                id="busqueda"
                name="q"
                key={q}
                defaultValue={q}
                placeholder="Nombre o RFC"
                maxLength={100}
                className="pl-8"
              />
            </div>
            <Button type="submit">Buscar</Button>
            {hayFiltros && botonLimpiar}
          </form>
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Filtrar por categoría" className="flex flex-wrap gap-2">
              <Filtro activo={!categoria} onClick={() => actualizar({ categoria: null, pagina: null })}>
                Todas
              </Filtro>
              {CATEGORIAS.map((c) => (
                <Filtro
                  key={c}
                  activo={categoria === c}
                  onClick={() => actualizar({ categoria: c, pagina: null })}
                >
                  {NOMBRES_CATEGORIA[c]}
                </Filtro>
              ))}
            </div>
            <div role="group" aria-label="Filtrar por estado" className="flex flex-wrap gap-2 md:ml-auto">
              <Filtro activo={!estado} onClick={() => actualizar({ estado: null, pagina: null })}>
                Todos
              </Filtro>
              <Filtro
                activo={estado === "activos"}
                onClick={() => actualizar({ estado: "activos", pagina: null })}
              >
                Activos
              </Filtro>
              <Filtro
                activo={estado === "inactivos"}
                onClick={() => actualizar({ estado: "inactivos", pagina: null })}
              >
                Inactivos
              </Filtro>
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </section>
  )
}
```

- [ ] **Step 6: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/paginas/Proveedores.test.tsx src/parametros.test.ts)`
Expected: PASS, salida limpia.

- [ ] **Step 7: Verificación completa y commit**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)` → todo en verde.

```bash
git add web/src/parametros.ts web/src/parametros.test.ts web/src/componentes/EtiquetaEstado.tsx web/src/paginas/Proveedores.tsx web/src/paginas/Proveedores.test.tsx web/src/tipos.ts
git commit -m "feat(web): lista de proveedores con filtros en chips, estado en la URL y estados estándar"
```

---

### Task 6: Detalle del proveedor con pestañas y gráfica de desempeño

**Files:**
- Create (shadcn): `web/src/components/ui/tabs.tsx`, `select.tsx`, `chart.tsx` (instala `recharts`)
- Create: `web/src/componentes/TablaContratos.tsx`, `web/src/componentes/DesempenoProveedor.tsx`
- Modify: `web/src/paginas/ProveedorDetalle.tsx` (reemplazo completo), `web/src/tipos.ts`
- Test: `web/src/paginas/ProveedorDetalle.test.tsx` (reemplazo completo)

**Interfaces:**
- Consumes: `ContenidoConsulta`, `EstadoCarga`, `EstadoError`, `EstadoVacio`, `Seccion` (Tarea 3); `useParametros`, `unoDe`, `EtiquetaEstado` (Tarea 5).
- Produces:
  - En `@/tipos`: `type ClaveKpi = "sla_cumplimiento_pct" | "tiempo_resolucion_h" | "incidentes_criticos" | "entregas_a_tiempo_pct" | "satisfaccion"`; `KPIS_DESEMPENO: { clave: ClaveKpi; nombre: string; unidad: string }[]`; `formatoKpi(valor: string | number, unidad: string): string`; `formatoPeriodo(iso: string): string` ("2026-08-01" → mes abreviado y año en es-MX).
  - `TablaContratos({ contratos: Contrato[] })`, `DesempenoProveedor({ registros: Desempeno[] })` (registros en orden descendente, como los devuelve la API).
  - Parámetro de URL `pestana` (`resumen` por defecto, `contratos`, `desempeno`). La API de desempeño se pide con `?meses=24`.

- [ ] **Step 1: Instalar `tabs`, `select` y `chart`**

Run: `(cd web && npx shadcn@4.21.0 add tabs select chart --yes)`

Run: `git status --short`; restaure con `git checkout -- <archivo>` cualquier archivo **existente** que el CLI haya modificado (en especial `web/src/index.css`). Run: `grep '"recharts"' web/package.json` → Expected: versión `^3`. Run: `grep -rnE ">Close<|\"Close\"|>More<" web/src/components/ui` → Expected: sin resultados (si aparecen, tradúzcalos como en la Tarea 4).

- [ ] **Step 2: Agregar los indicadores y formatos a `web/src/tipos.ts`**

Al final del archivo:

```ts
export type ClaveKpi =
  | "sla_cumplimiento_pct"
  | "tiempo_resolucion_h"
  | "incidentes_criticos"
  | "entregas_a_tiempo_pct"
  | "satisfaccion"

export const KPIS_DESEMPENO: { clave: ClaveKpi; nombre: string; unidad: string }[] = [
  { clave: "sla_cumplimiento_pct", nombre: "Cumplimiento de SLA", unidad: "%" },
  { clave: "tiempo_resolucion_h", nombre: "Tiempo de resolución", unidad: "h" },
  { clave: "incidentes_criticos", nombre: "Incidentes críticos", unidad: "" },
  { clave: "entregas_a_tiempo_pct", nombre: "Entregas a tiempo", unidad: "%" },
  { clave: "satisfaccion", nombre: "Satisfacción", unidad: "de 5" },
]

export function formatoKpi(valor: string | number, unidad: string): string {
  return unidad ? `${valor} ${unidad}` : String(valor)
}

/** "2026-08-01" → mes abreviado y año en español de México (p. ej. "ago 2026"). */
export function formatoPeriodo(iso: string): string {
  const [anio, mes] = iso.split("-").map(Number)
  return new Date(anio, mes - 1, 1).toLocaleDateString("es-MX", { month: "short", year: "numeric" })
}
```

- [ ] **Step 3: Escribir las pruebas (fallan)**

Reemplace `web/src/paginas/ProveedorDetalle.test.tsx`:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"
import { formatoPeriodo } from "@/tipos"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

const RUTA = "/api/proveedores/proveedores/p1"

const PROVEEDOR = {
  id: "p1",
  rfc: "AAA010101AAA",
  nombre: "Proveedor Uno",
  tamano: "mediana",
  categorias: ["nube"],
  activo: true,
  contacto_nombre: "Ana Pérez",
  contacto_email: "ana@ejemplo.test",
  contratos_vigentes: 1,
}

const CONTRATO = {
  id: "c1",
  folio: "CT-0001",
  tipo: "nuevo",
  fecha_inicio: "2026-01-01",
  fecha_fin: "2026-12-31",
  moneda: "MXN",
  plazo_pago_dias: 30,
  sla_disponibilidad: null,
  tope_aumento_pct: null,
  cuota_implementacion: "0",
  lineas: [
    {
      codigo_servicio: "NUBE-01",
      nombre_servicio: "Nube pública",
      unidad: "mes",
      cantidad: "12",
      precio_unitario: "1500.0000",
    },
  ],
}

const DESEMPENO = [
  {
    periodo: "2026-08-01",
    sla_cumplimiento_pct: "99.10",
    tiempo_resolucion_h: "4.50",
    incidentes_criticos: 1,
    entregas_a_tiempo_pct: "95.00",
    satisfaccion: "4.40",
  },
  {
    periodo: "2026-07-01",
    sla_cumplimiento_pct: "98.70",
    tiempo_resolucion_h: "5.20",
    incidentes_criticos: 2,
    entregas_a_tiempo_pct: "92.00",
    satisfaccion: "4.10",
  },
]

function api(cambios: Record<string, () => Response | Promise<Response>> = {}) {
  return simularApi({
    [RUTA]: () => respuestaJson(PROVEEDOR),
    [`${RUTA}/contratos`]: () => respuestaJson([CONTRATO]),
    [`${RUTA}/desempeno?meses=24`]: () => respuestaJson(DESEMPENO),
    ...cambios,
  })
}

const renderizar = (ruta = "/proveedores/p1") =>
  renderizarPagina(<ProveedorDetalle />, { ruta, patron: "/proveedores/:id" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("ProveedorDetalle", () => {
  it("muestra la ficha del proveedor", async () => {
    api()
    renderizar()

    expect(await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })).toBeInTheDocument()
    expect(screen.getByText("AAA010101AAA")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "ana@ejemplo.test" })).toHaveAttribute(
      "href",
      "mailto:ana@ejemplo.test"
    )
    expect(screen.getByText("Activo")).toBeInTheDocument()
  })

  it("el resumen muestra el desempeño del último mes", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("heading", { name: `Desempeño de ${formatoPeriodo("2026-08-01")}` })
    ).toBeInTheDocument()
    expect(screen.getByText("99.10 %")).toBeInTheDocument()
    expect(screen.getByText("4.40 de 5")).toBeInTheDocument()
  })

  it("muestra Cargando mientras llega el desempeño", async () => {
    let liberar = () => {}
    const espera = new Promise<void>((resolver) => {
      liberar = resolver
    })
    api({ [`${RUTA}/desempeno?meses=24`]: () => espera.then(() => respuestaJson(DESEMPENO)) })
    renderizar()

    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
    expect(screen.getByRole("status")).toHaveTextContent("Cargando…")
    liberar()
    expect(await screen.findByText("99.10 %")).toBeInTheDocument()
  })

  it("la pestaña Contratos se refleja en la URL y lista las líneas", async () => {
    api()
    renderizar()
    await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })

    await userEvent.click(screen.getByRole("tab", { name: "Contratos" }))

    expect(await screen.findByText("CT-0001")).toBeInTheDocument()
    expect(screen.getByText("Nube pública")).toBeInTheDocument()
    expect(ubicacionActual()).toBe("/proveedores/p1?pestana=contratos")
  })

  it("avisa con una alerta cuando falla la consulta de contratos", async () => {
    api({ [`${RUTA}/contratos`]: () => new Response("Bad Gateway", { status: 502 }) })
    renderizar("/proveedores/p1?pestana=contratos")

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible; intente más tarde."
    )
    expect(screen.queryByText("Sin contratos registrados")).not.toBeInTheDocument()
  })

  it("muestra que no hay contratos cuando la lista llega vacía", async () => {
    api({ [`${RUTA}/contratos`]: () => respuestaJson([]) })
    renderizar("/proveedores/p1?pestana=contratos")

    expect(await screen.findByText("Sin contratos registrados")).toBeInTheDocument()
  })

  it("muestra que no hay datos cuando el desempeño llega vacío", async () => {
    api({ [`${RUTA}/desempeno?meses=24`]: () => respuestaJson([]) })
    renderizar()

    expect(await screen.findByText("Sin datos de desempeño")).toBeInTheDocument()
  })

  it("la pestaña Desempeño muestra la gráfica y la tabla del indicador elegido", async () => {
    api()
    renderizar("/proveedores/p1?pestana=desempeno")

    expect(
      await screen.findByRole("figure", { name: "Cumplimiento de SLA de los últimos 2 meses" })
    ).toBeInTheDocument()
    const tabla = screen.getByRole("table")
    expect(within(tabla).getAllByRole("row")).toHaveLength(3)

    await userEvent.click(screen.getByRole("combobox", { name: "Indicador" }))
    await userEvent.click(await screen.findByRole("option", { name: "Satisfacción" }))

    expect(screen.getByRole("figure", { name: "Satisfacción de los últimos 2 meses" })).toBeInTheDocument()
  })

  it("una pestaña desconocida en la URL muestra el resumen", async () => {
    api()
    renderizar("/proveedores/p1?pestana=inventada")

    expect(await screen.findByRole("tab", { name: "Resumen" })).toHaveAttribute("aria-selected", "true")
  })

  it("codifica el id al construir la ruta de la API", async () => {
    simularApi({
      "/api/proveedores/proveedores/a%20b%3Fx": () => respuestaJson(PROVEEDOR),
      "/api/proveedores/proveedores/a%20b%3Fx/contratos": () => respuestaJson([]),
      "/api/proveedores/proveedores/a%20b%3Fx/desempeno?meses=24": () => respuestaJson([]),
    })
    renderizar("/proveedores/a%20b%3Fx")

    expect(await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })).toBeInTheDocument()
  })

  it("un proveedor inexistente ofrece volver a la lista", async () => {
    simularApi({})
    renderizar()

    expect(await screen.findByText("El proveedor no existe")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Volver a proveedores" })).toHaveAttribute("href", "/proveedores")
  })

  it("un error al cargar la ficha permite reintentar", async () => {
    let fallar = true
    api({ [RUTA]: () => (fallar ? new Response("", { status: 503 }) : respuestaJson(PROVEEDOR)) })
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent("Servicio no disponible")
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })).toBeInTheDocument()
  })

  it.each(["resumen", "contratos", "desempeno"])(
    "la pestaña %s no tiene violaciones de accesibilidad",
    async (pestana) => {
      api()
      const { container } = renderizar(`/proveedores/p1?pestana=${pestana}`)
      await screen.findByRole("heading", { level: 1, name: "Proveedor Uno" })
      await screen.findByRole("tabpanel")
      await esperarSinViolaciones(container)
    }
  )
})
```

Run: `(cd web && npx vitest run src/paginas/ProveedorDetalle.test.tsx)` → Expected: FAIL (sin pestañas ni gráfica; desempeño con `meses=12`).

- [ ] **Step 4: Implementar `web/src/componentes/TablaContratos.tsx`**

```tsx
import { FileText } from "lucide-react"
import { EstadoVacio } from "@/componentes/Estados"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatoFecha, formatoMoneda, type Contrato } from "@/tipos"

export function TablaContratos({ contratos }: { contratos: Contrato[] }) {
  if (contratos.length === 0) {
    return (
      <EstadoVacio
        icono={FileText}
        titulo="Sin contratos registrados"
        descripcion="Este proveedor aún no tiene contratos importados."
      />
    )
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Folio</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead>Vigencia</TableHead>
          <TableHead>Servicio</TableHead>
          <TableHead className="text-right">Cantidad</TableHead>
          <TableHead className="text-right">Precio unitario</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {contratos.flatMap((c) =>
          c.lineas.map((linea, i) => (
            <TableRow key={`${c.id}-${linea.codigo_servicio}`}>
              <TableCell className="font-mono">{i === 0 ? c.folio : ""}</TableCell>
              <TableCell>{i === 0 ? (c.tipo === "nuevo" ? "Nuevo" : "Renovación") : ""}</TableCell>
              <TableCell>
                {i === 0 ? `${formatoFecha(c.fecha_inicio)} – ${formatoFecha(c.fecha_fin)}` : ""}
              </TableCell>
              <TableCell>{linea.nombre_servicio}</TableCell>
              <TableCell className="text-right">
                {Number(linea.cantidad).toLocaleString("es-MX")} {linea.unidad}
              </TableCell>
              <TableCell className="text-right">
                {formatoMoneda(linea.precio_unitario, c.moneda)}
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 5: Implementar `web/src/componentes/DesempenoProveedor.tsx`**

```tsx
import { ChartLine } from "lucide-react"
import { useId, useState } from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"
import { EstadoVacio } from "@/componentes/Estados"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { KPIS_DESEMPENO, formatoKpi, formatoPeriodo, type ClaveKpi, type Desempeno } from "@/tipos"

/** Gráfica de un indicador por mes y tabla con todos (alternativa accesible a la gráfica). */
export function DesempenoProveedor({ registros }: { registros: Desempeno[] }) {
  const [clave, setClave] = useState<ClaveKpi>("sla_cumplimiento_pct")
  const idEtiqueta = useId()

  if (registros.length === 0) {
    return (
      <EstadoVacio
        icono={ChartLine}
        titulo="Sin datos de desempeño"
        descripcion="Aún no se ha importado el desempeño mensual de este proveedor."
      />
    )
  }

  const kpi = KPIS_DESEMPENO.find((k) => k.clave === clave) ?? KPIS_DESEMPENO[0]
  // La API entrega del mes más reciente al más antiguo; la gráfica va en orden cronológico.
  const serie = [...registros].reverse().map((r) => ({ periodo: r.periodo, valor: Number(r[clave]) }))
  const configuracion = { valor: { label: kpi.nombre, color: "var(--chart-1)" } } satisfies ChartConfig

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span id={idEtiqueta} className="text-sm font-medium">
          Indicador
        </span>
        <Select value={clave} onValueChange={(valor) => setClave(valor as ClaveKpi)}>
          <SelectTrigger aria-labelledby={idEtiqueta} className="w-60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {KPIS_DESEMPENO.map((k) => (
              <SelectItem key={k.clave} value={k.clave}>
                {k.nombre}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <figure aria-label={`${kpi.nombre} de los últimos ${serie.length} meses`}>
        <ChartContainer config={configuracion} className="aspect-auto h-64 w-full">
          <LineChart accessibilityLayer data={serie} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="periodo"
              tickFormatter={formatoPeriodo}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis tickLine={false} axisLine={false} width={44} domain={["auto", "auto"]} />
            <ChartTooltip
              content={<ChartTooltipContent labelFormatter={(valor) => formatoPeriodo(String(valor))} />}
            />
            <Line dataKey="valor" type="monotone" stroke="var(--color-valor)" strokeWidth={2} dot={false} />
          </LineChart>
        </ChartContainer>
      </figure>
      <Table>
        <TableCaption>Valores mensuales de los indicadores</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Periodo</TableHead>
            {KPIS_DESEMPENO.map((k) => (
              <TableHead key={k.clave} className="text-right">
                {k.nombre}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {registros.map((r) => (
            <TableRow key={r.periodo}>
              <TableCell>{formatoPeriodo(r.periodo)}</TableCell>
              {KPIS_DESEMPENO.map((k) => (
                <TableCell key={k.clave} className="text-right">
                  {formatoKpi(r[k.clave], k.unidad)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 6: Reemplazar `web/src/paginas/ProveedorDetalle.tsx`**

```tsx
import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { ArrowLeft, ChartLine, FileQuestion } from "lucide-react"
import { Link, useParams } from "react-router"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { DesempenoProveedor } from "@/componentes/DesempenoProveedor"
import { ContenidoConsulta, EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { EtiquetaEstado } from "@/componentes/EtiquetaEstado"
import { Seccion } from "@/componentes/Seccion"
import { TablaContratos } from "@/componentes/TablaContratos"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { unoDe, useParametros } from "@/parametros"
import {
  KPIS_DESEMPENO,
  NOMBRES_CATEGORIA,
  NOMBRES_TAMANO,
  formatoKpi,
  formatoPeriodo,
  type Contrato,
  type Desempeno,
  type ProveedorDetalle as Detalle,
} from "@/tipos"

const PESTANAS = ["resumen", "contratos", "desempeno"] as const

function Encabezado({ proveedor: p }: { proveedor: Detalle }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-start justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">{p.nombre}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono">{p.rfc}</span>
            <span aria-hidden>·</span>
            <span>{NOMBRES_TAMANO[p.tamano] ?? p.tamano}</span>
            <EtiquetaEstado activo={p.activo} />
          </div>
          <div className="flex flex-wrap gap-1">
            {p.categorias.map((c) => (
              <Badge key={c} variant="secondary">
                {NOMBRES_CATEGORIA[c] ?? c}
              </Badge>
            ))}
          </div>
        </div>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Contacto</dt>
            <dd>{p.contacto_nombre}</dd>
            <dd>
              <a href={`mailto:${p.contacto_email}`} className="text-accent hover:underline">
                {p.contacto_email}
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Contratos vigentes</dt>
            <dd className="text-2xl font-semibold">{p.contratos_vigentes}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}

function Resumen({ consulta }: { consulta: UseQueryResult<Desempeno[]> }) {
  return (
    <ContenidoConsulta consulta={consulta}>
      {(registros) => {
        const ultimo = registros[0]
        if (!ultimo) {
          return (
            <EstadoVacio
              icono={ChartLine}
              titulo="Sin datos de desempeño"
              descripcion="Aún no se ha importado el desempeño mensual de este proveedor."
            />
          )
        }
        return (
          <Seccion titulo={`Desempeño de ${formatoPeriodo(ultimo.periodo)}`} descripcion="Último mes registrado.">
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {KPIS_DESEMPENO.map((kpi) => (
                <div key={kpi.clave} className="rounded-lg border p-3">
                  <dt className="text-sm text-muted-foreground">{kpi.nombre}</dt>
                  <dd className="text-xl font-semibold">{formatoKpi(ultimo[kpi.clave], kpi.unidad)}</dd>
                </div>
              ))}
            </dl>
          </Seccion>
        )
      }}
    </ContenidoConsulta>
  )
}

export function ProveedorDetalle() {
  const { id = "" } = useParams()
  const token = useToken()
  const [parametros, actualizar] = useParametros()
  const pestana = unoDe(parametros.get("pestana"), PESTANAS) ?? "resumen"
  const ruta = `/proveedores/proveedores/${encodeURIComponent(id)}`

  const detalle = useQuery({
    queryKey: ["proveedor", id],
    queryFn: () => pedir<Detalle>(ruta, token),
    enabled: Boolean(token),
  })
  const contratos = useQuery({
    queryKey: ["proveedor", id, "contratos"],
    queryFn: () => pedir<Contrato[]>(`${ruta}/contratos`, token),
    enabled: detalle.isSuccess,
  })
  const desempeno = useQuery({
    queryKey: ["proveedor", id, "desempeno"],
    queryFn: () => pedir<Desempeno[]>(`${ruta}/desempeno?meses=24`, token),
    enabled: detalle.isSuccess,
  })

  if (detalle.isPending) return <EstadoCarga filas={3} />
  if (detalle.isError) {
    if (detalle.error instanceof ErrorApi && detalle.error.estado === 404) {
      return (
        <EstadoVacio
          icono={FileQuestion}
          titulo="El proveedor no existe"
          descripcion="Puede que el enlace sea incorrecto o que el proveedor ya no esté en el catálogo."
          accion={
            <Button asChild variant="outline">
              <Link to="/proveedores">Volver a proveedores</Link>
            </Button>
          }
        />
      )
    }
    return <EstadoError error={detalle.error} alReintentar={() => void detalle.refetch()} />
  }

  return (
    <section className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/proveedores">
          <ArrowLeft aria-hidden />
          Proveedores
        </Link>
      </Button>
      <Encabezado proveedor={detalle.data} />
      <Tabs
        value={pestana}
        onValueChange={(valor) => actualizar({ pestana: valor === "resumen" ? null : valor })}
      >
        <TabsList>
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="contratos">Contratos</TabsTrigger>
          <TabsTrigger value="desempeno">Desempeño</TabsTrigger>
        </TabsList>
        <TabsContent value="resumen" className="mt-4">
          <Resumen consulta={desempeno} />
        </TabsContent>
        <TabsContent value="contratos" className="mt-4">
          <Seccion titulo="Contratos">
            <ContenidoConsulta consulta={contratos}>
              {(datos) => <TablaContratos contratos={datos} />}
            </ContenidoConsulta>
          </Seccion>
        </TabsContent>
        <TabsContent value="desempeno" className="mt-4">
          <Seccion titulo="Desempeño de los últimos 24 meses">
            <ContenidoConsulta consulta={desempeno}>
              {(registros) => <DesempenoProveedor registros={registros} />}
            </ContenidoConsulta>
          </Seccion>
        </TabsContent>
      </Tabs>
    </section>
  )
}
```

- [ ] **Step 7: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/paginas/ProveedorDetalle.test.tsx)`
Expected: PASS. La salida debe quedar limpia: si Recharts advierte en jsdom que el ancho o alto del contenedor es 0, silencie **solo ese mensaje** en este archivo de prueba con `vi.spyOn(console, "warn")` filtrando el texto (deje pasar cualquier otra advertencia) y anótelo en el reporte. Si axe marca `aria-valid-attr-value` en las pestañas inactivas (Radix apunta `aria-controls` a paneles que no monta), agregue `forceMount` y `hidden={pestana !== "<valor>"}` a cada `TabsContent`.

- [ ] **Step 8: Verificación completa y commit**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)` → todo en verde.

```bash
git add web/src/components/ui web/src/componentes/TablaContratos.tsx web/src/componentes/DesempenoProveedor.tsx web/src/paginas/ProveedorDetalle.tsx web/src/paginas/ProveedorDetalle.test.tsx web/src/tipos.ts web/package.json web/package-lock.json
git commit -m "feat(web): detalle del proveedor con pestañas, resumen del último mes y gráfica de desempeño"
```

---

### Task 7: Importación en tres pasos

**Files:**
- Modify: `web/src/paginas/Importacion.tsx` (reemplazo completo)
- Test: `web/src/paginas/Importacion.test.tsx` (reemplazo completo)

**Interfaces:**
- Consumes: `RequiereRol`, `EncabezadoPagina`, `Seccion` (Tarea 3); `pedir`, `ErrorApi`; utilidades de prueba (Tarea 3).
- Produces: `Importacion` (misma ruta `/importacion`); `validarArchivo(archivo: File): string | null` (exportada para pruebas). Mantiene `POST /api/proveedores/importaciones/{entidad}` y la invalidación de `["proveedores"]` y `["proveedor"]`.

- [ ] **Step 1: Escribir las pruebas (fallan)**

Reemplace `web/src/paginas/Importacion.test.tsx`:

```tsx
import { cleanup, fireEvent, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Importacion } from "@/paginas/Importacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina, respuestaJson, simularApi } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

const zonaDeArchivo = () => screen.getByLabelText(/Arrastre el archivo CSV/)

function soltar(...archivos: File[]) {
  fireEvent.drop(zonaDeArchivo().closest("label")!, { dataTransfer: { files: archivos } })
}

async function irAlPasoDeArchivo(tipo = /Catálogo de servicios/) {
  await userEvent.click(screen.getByRole("radio", { name: tipo }))
  await userEvent.click(screen.getByRole("button", { name: "Continuar" }))
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Importacion", () => {
  it("guía la importación en tres pasos y muestra el resumen", async () => {
    simularApi({
      "/api/proveedores/importaciones/servicios": () =>
        respuestaJson({ entidad: "servicios", filas: 40, registros: 40, omitidos: 0, eventos: 0 }),
    })
    renderizarPagina(<Importacion />)

    expect(screen.getByRole("radio", { name: /Catálogo de servicios/ })).toBeChecked()
    expect(screen.getByText("Tipo de archivo").closest("li")).toHaveAttribute("aria-current", "step")
    await irAlPasoDeArchivo()
    await userEvent.upload(zonaDeArchivo(), new File(["x"], "servicios.csv", { type: "text/csv" }))
    expect(screen.getByText(/servicios\.csv/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(await screen.findByText("Importación completada")).toBeInTheDocument()
    expect(screen.getByText("Resultado").closest("li")).toHaveAttribute("aria-current", "step")
    expect(screen.getByText("Registros").nextElementSibling).toHaveTextContent("40")
    expect(screen.getByRole("button", { name: /Importar Proveedores/ })).toBeInTheDocument()
  })

  it("muestra los errores por fila que devuelve la API y permite elegir otro archivo", async () => {
    const simulado = simularApi({
      "/api/proveedores/importaciones/proveedores": () =>
        respuestaJson(
          {
            title: "Archivo con errores",
            detail: "Se encontraron 1 error(es); no se importó ninguna fila.",
            errores: [{ fila: 2, campo: "contacto_email", mensaje: "Formato inválido" }],
          },
          422
        ),
    })
    renderizarPagina(<Importacion />)

    await irAlPasoDeArchivo(/Proveedores/)
    await userEvent.upload(zonaDeArchivo(), new File(["rfc\n"], "proveedores.csv", { type: "text/csv" }))
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))

    expect(await screen.findByText("Formato inválido")).toBeInTheDocument()
    expect(screen.getByText("contacto_email")).toBeInTheDocument()
    const [url, init] = simulado.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe("/api/proveedores/importaciones/proveedores")
    expect(init.method).toBe("POST")

    await userEvent.click(screen.getByRole("button", { name: "Elegir otro archivo" }))
    expect(zonaDeArchivo()).toBeInTheDocument()
  })

  it("invalida la lista y los detalles de proveedores tras importar", async () => {
    simularApi({
      "/api/proveedores/importaciones/servicios": () =>
        respuestaJson({ entidad: "servicios", filas: 1, registros: 1, omitidos: 0, eventos: 1 }),
    })
    const { cliente } = renderizarPagina(<Importacion />)
    const invalidar = vi.spyOn(cliente, "invalidateQueries")

    await irAlPasoDeArchivo()
    await userEvent.upload(zonaDeArchivo(), new File(["x"], "servicios.csv", { type: "text/csv" }))
    await userEvent.click(screen.getByRole("button", { name: "Importar" }))
    await screen.findByText("Importación completada")

    expect(invalidar).toHaveBeenCalledWith({ queryKey: ["proveedores"] })
    expect(invalidar).toHaveBeenCalledWith({ queryKey: ["proveedor"] })
  })

  it("rechaza en el navegador un archivo que no es CSV", async () => {
    const simulado = simularApi({})
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    soltar(new File(["x"], "datos.xlsx"))

    expect(await screen.findByRole("alert")).toHaveTextContent("El archivo debe tener extensión .csv.")
    expect(screen.getByRole("button", { name: "Importar" })).toBeDisabled()
    expect(simulado).not.toHaveBeenCalled()
  })

  it("acepta la extensión .CSV en mayúsculas", async () => {
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    soltar(new File(["x"], "DATOS.CSV"))

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Importar" })).toBeEnabled()
  })

  it("rechaza archivos de más de 10 MB y vacíos", async () => {
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    const grande = new File(["x"], "grande.csv")
    Object.defineProperty(grande, "size", { value: 10 * 1024 * 1024 + 1 })
    soltar(grande)
    expect(await screen.findByRole("alert")).toHaveTextContent("El archivo excede el límite de 10 MB.")

    soltar(new File([], "vacio.csv"))
    expect(screen.getByRole("alert")).toHaveTextContent("El archivo está vacío.")
  })

  it("pide soltar un solo archivo", async () => {
    renderizarPagina(<Importacion />)
    await irAlPasoDeArchivo()

    soltar(new File(["x"], "a.csv"), new File(["y"], "b.csv"))

    expect(await screen.findByRole("alert")).toHaveTextContent("Suelte un solo archivo a la vez.")
    expect(screen.getByRole("button", { name: "Importar" })).toBeDisabled()
  })

  it("solo los administradores pueden importar", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Importacion />)

    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(screen.queryByRole("radio")).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad en los pasos", async () => {
    const { container } = renderizarPagina(<Importacion />)
    await esperarSinViolaciones(container)
    await irAlPasoDeArchivo()
    await esperarSinViolaciones(container)
  })
})
```

Run: `(cd web && npx vitest run src/paginas/Importacion.test.tsx)` → Expected: FAIL.

- [ ] **Step 2: Reemplazar `web/src/paginas/Importacion.tsx`**

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, Check, CircleCheck, FileSpreadsheet, Upload } from "lucide-react"
import { useState, type DragEvent } from "react"
import { ErrorApi, pedir } from "@/api"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import type { ResumenImportacion } from "@/tipos"

const ENTIDADES = [
  { valor: "servicios", nombre: "Catálogo de servicios", descripcion: "Servicios de TI con su categoría, unidad y moneda." },
  { valor: "proveedores", nombre: "Proveedores", descripcion: "RFC, nombre, tamaño, categorías y contacto." },
  { valor: "tipo_cambio", nombre: "Tipo de cambio", descripcion: "Tipo de cambio mensual de USD a MXN." },
  { valor: "contratos", nombre: "Contratos", descripcion: "Contratos y sus líneas; requiere proveedores y servicios." },
  { valor: "desempeno", nombre: "Desempeño", descripcion: "Indicadores mensuales por proveedor; requiere proveedores." },
] as const

type Entidad = (typeof ENTIDADES)[number]["valor"]

const PASOS = ["Tipo de archivo", "Archivo", "Resultado"]
const MAX_BYTES = 10 * 1024 * 1024

/** Revisa en el navegador lo que el servidor rechazaría de todos modos, para avisar antes de subir. */
export function validarArchivo(archivo: File): string | null {
  if (!archivo.name.toLowerCase().endsWith(".csv")) return "El archivo debe tener extensión .csv."
  if (archivo.size > MAX_BYTES) return "El archivo excede el límite de 10 MB."
  if (archivo.size === 0) return "El archivo está vacío."
  return null
}

function tamanoLegible(bytes: number): string {
  const formato = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 1 })
  return bytes < 1024 * 1024
    ? `${formato.format(bytes / 1024)} KB`
    : `${formato.format(bytes / (1024 * 1024))} MB`
}

function Pasos({ actual }: { actual: number }) {
  return (
    <ol aria-label="Pasos de la importación" className="flex flex-wrap gap-4">
      {PASOS.map((nombre, i) => {
        const numero = i + 1
        const hecho = numero < actual
        const enCurso = numero === actual
        return (
          <li
            key={nombre}
            aria-current={enCurso ? "step" : undefined}
            className="flex items-center gap-2 text-sm"
          >
            <span
              aria-hidden
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-semibold",
                enCurso && "border-accent bg-accent text-accent-foreground",
                hecho && "border-success text-success"
              )}
            >
              {hecho ? <Check className="size-3.5" /> : numero}
            </span>
            <span className={enCurso || hecho ? "font-medium" : "text-muted-foreground"}>{nombre}</span>
            {hecho && <span className="sr-only">(completado)</span>}
          </li>
        )
      })}
    </ol>
  )
}

function DetalleError({ error }: { error: Error }) {
  const deApi = error instanceof ErrorApi ? error : null
  return (
    <Alert variant="destructive">
      <AlertTitle>{deApi?.titulo ?? "No se pudo importar"}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {deApi && deApi.errores.length > 0 && (
          <Table className="mt-2">
            <TableHeader>
              <TableRow>
                <TableHead>Fila</TableHead>
                <TableHead>Campo</TableHead>
                <TableHead>Problema</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deApi.errores.map((e) => (
                <TableRow key={`${e.fila}-${e.campo}-${e.mensaje}`}>
                  <TableCell>{e.fila}</TableCell>
                  <TableCell className="font-mono">{e.campo}</TableCell>
                  <TableCell>{e.mensaje}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </AlertDescription>
    </Alert>
  )
}

export function Importacion() {
  return (
    <RequiereRol rol="admin">
      <FlujoImportacion />
    </RequiereRol>
  )
}

function FlujoImportacion() {
  const token = useToken()
  const clienteConsultas = useQueryClient()
  const [paso, setPaso] = useState(1)
  const [entidad, setEntidad] = useState<Entidad>("servicios")
  const [archivo, setArchivo] = useState<File | null>(null)
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null)
  const [arrastrando, setArrastrando] = useState(false)

  const importacion = useMutation({
    mutationFn: (datos: { entidad: Entidad; archivo: File }) => {
      const formulario = new FormData()
      formulario.append("archivo", datos.archivo)
      return pedir<ResumenImportacion>(`/proveedores/importaciones/${datos.entidad}`, token, {
        method: "POST",
        body: formulario,
      })
    },
    // "proveedor" es el prefijo de las consultas del detalle (ficha, contratos y desempeño).
    onSuccess: () =>
      Promise.all([
        clienteConsultas.invalidateQueries({ queryKey: ["proveedores"] }),
        clienteConsultas.invalidateQueries({ queryKey: ["proveedor"] }),
      ]),
  })

  const indice = ENTIDADES.findIndex((e) => e.valor === entidad)
  const actual = ENTIDADES[indice]
  const siguiente = ENTIDADES[indice + 1]

  function elegir(nuevo: File | null) {
    setArchivo(nuevo)
    setErrorArchivo(nuevo ? validarArchivo(nuevo) : null)
  }

  function soltar(evento: DragEvent<HTMLLabelElement>) {
    evento.preventDefault()
    setArrastrando(false)
    const archivos = evento.dataTransfer.files
    if (archivos.length > 1) {
      setArchivo(null)
      setErrorArchivo("Suelte un solo archivo a la vez.")
      return
    }
    elegir(archivos[0] ?? null)
  }

  function importar() {
    if (archivo && !errorArchivo) {
      importacion.mutate({ entidad, archivo }, { onSettled: () => setPaso(3) })
    }
  }

  function empezar(nueva: Entidad, nuevoPaso: number) {
    importacion.reset()
    elegir(null)
    setEntidad(nueva)
    setPaso(nuevoPaso)
  }

  return (
    <section className="max-w-3xl space-y-6">
      <EncabezadoPagina
        titulo="Importar datos del ERP"
        descripcion="Cargue los archivos CSV exportados del ERP. Si un archivo tiene errores, no se importa ninguna fila."
      />
      <Pasos actual={paso} />

      {paso === 1 && (
        <Seccion titulo="1. Elija el tipo de archivo">
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm text-muted-foreground">
              Siga el orden recomendado: contratos y desempeño hacen referencia a proveedores y servicios ya
              importados.
            </legend>
            {ENTIDADES.map((e, i) => (
              <label
                key={e.valor}
                className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50 has-checked:border-accent"
              >
                <input
                  type="radio"
                  name="entidad"
                  value={e.valor}
                  checked={entidad === e.valor}
                  onChange={() => setEntidad(e.valor)}
                  className="mt-1 accent-accent"
                />
                <span>
                  <span className="font-medium">
                    {i + 1}. {e.nombre}
                  </span>
                  <span className="block text-sm text-muted-foreground">{e.descripcion}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <Button className="mt-4" onClick={() => setPaso(2)}>
            Continuar
            <ArrowRight aria-hidden />
          </Button>
        </Seccion>
      )}

      {paso === 2 && (
        <Seccion titulo={`2. Elija el archivo: ${actual.nombre}`}>
          <div className="space-y-4">
            <label
              onDragOver={(evento) => {
                evento.preventDefault()
                setArrastrando(true)
              }}
              onDragLeave={() => setArrastrando(false)}
              onDrop={soltar}
              className={cn(
                "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors focus-within:ring-2 focus-within:ring-ring",
                arrastrando && "border-accent bg-muted"
              )}
            >
              <Upload aria-hidden className="size-8 text-muted-foreground" />
              <span className="font-medium">Arrastre el archivo CSV aquí o haga clic para elegirlo</span>
              <span className="text-sm text-muted-foreground">
                CSV en UTF-8, separado por coma o punto y coma, de hasta 10 MB.
              </span>
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                onChange={(evento) => elegir(evento.target.files?.[0] ?? null)}
              />
            </label>
            {archivo && !errorArchivo && (
              <p className="flex items-center gap-2 text-sm">
                <FileSpreadsheet aria-hidden className="size-4 text-muted-foreground" />
                {archivo.name} · {tamanoLegible(archivo.size)}
              </p>
            )}
            {errorArchivo && (
              <p role="alert" className="text-sm text-destructive">
                {errorArchivo}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => setPaso(1)}>
                <ArrowLeft aria-hidden />
                Atrás
              </Button>
              <Button onClick={importar} disabled={!archivo || Boolean(errorArchivo) || importacion.isPending}>
                {importacion.isPending ? "Importando…" : "Importar"}
              </Button>
            </div>
          </div>
        </Seccion>
      )}

      {paso === 3 && (
        <Seccion titulo="3. Resultado">
          {importacion.isSuccess && (
            <div className="space-y-4">
              <Alert role="status">
                <CircleCheck aria-hidden className="text-success" />
                <AlertTitle>Importación completada</AlertTitle>
                <AlertDescription>
                  Se importó {archivo?.name} ({actual.nombre}).
                </AlertDescription>
              </Alert>
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {(
                  [
                    ["Filas leídas", importacion.data.filas],
                    ["Registros", importacion.data.registros],
                    ["Omitidos", importacion.data.omitidos],
                    ["Eventos", importacion.data.eventos],
                  ] as const
                ).map(([nombre, valor]) => (
                  <div key={nombre} className="rounded-lg border p-3">
                    <dt className="text-sm text-muted-foreground">{nombre}</dt>
                    <dd className="text-2xl font-semibold">{valor.toLocaleString("es-MX")}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex flex-wrap gap-2">
                {siguiente && (
                  <Button onClick={() => empezar(siguiente.valor, 2)}>
                    Importar {siguiente.nombre}
                    <ArrowRight aria-hidden />
                  </Button>
                )}
                <Button variant="outline" onClick={() => empezar(entidad, 1)}>
                  Importar otro archivo
                </Button>
              </div>
            </div>
          )}
          {importacion.isError && (
            <div className="space-y-4">
              <DetalleError error={importacion.error} />
              <Button variant="outline" onClick={() => empezar(entidad, 2)}>
                Elegir otro archivo
              </Button>
            </div>
          )}
        </Seccion>
      )}
    </section>
  )
}
```

- [ ] **Step 3: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/paginas/Importacion.test.tsx)`
Expected: PASS, salida limpia.

- [ ] **Step 4: Verificación completa y commit**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)` → todo en verde.

```bash
git add web/src/paginas/Importacion.tsx web/src/paginas/Importacion.test.tsx
git commit -m "feat(web): importación en tres pasos con arrastrar y soltar y validación previa del archivo"
```

---

### Task 8: Tablero, Ranking, Alertas y Configuración con sus estados vacíos

**Files:**
- Create: `web/src/componentes/AvisoInteligencia.tsx`, `web/src/componentes/TarjetaKpi.tsx`
- Create: `web/src/paginas/Tablero.tsx`, `Ranking.tsx`, `Alertas.tsx`, `Configuracion.tsx` y sus `*.test.tsx`
- Modify: `web/src/paginas/NoEncontrado.tsx`, `web/src/rutas.tsx`, `web/src/tipos.ts`
- Delete: `web/src/paginas/Inicio.tsx`

**Interfaces:**
- Consumes: `EncabezadoPagina`, `Seccion`, `EstadoVacio`, `RequiereRol` (Tarea 3); `useParametros`, `unoDe` (Tarea 5); `CATEGORIAS` (Tarea 5); `Tabs`, `Select` (Tarea 6).
- Produces:
  - `AvisoInteligencia()` — aviso único (`role="note"`) que el Plan B elimina al conectar datos.
  - `TarjetaKpi({ titulo: string, valor: string | null, detalle?: string, icono: LucideIcon, enlace: string, textoEnlace: string })` — con `valor={null}` muestra "—" y el texto oculto "Sin datos". El Plan B le pasa cifras.
  - En `@/tipos`: `type TipoAlerta = "vencimiento" | "sobreprecio" | "riesgo"`, `type Severidad = "alta" | "media" | "informativa"`, `NOMBRES_TIPO_ALERTA`, `NOMBRES_SEVERIDAD`.
  - Rutas: `/` Tablero, `/ranking` (`?categoria=`), `/alertas` (`?tipo=&severidad=`), `/configuracion` (solo admin). Los enlaces del Tablero llevan a `/alertas?tipo=vencimiento`, `/alertas?tipo=riesgo` y `/precios?vista=sobreprecios` (la Tarea 9 crea `/precios`).

- [ ] **Step 1: Agregar los tipos de alerta a `web/src/tipos.ts`**

```ts
export type TipoAlerta = "vencimiento" | "sobreprecio" | "riesgo"
export type Severidad = "alta" | "media" | "informativa"

export const NOMBRES_TIPO_ALERTA: Record<TipoAlerta, string> = {
  vencimiento: "Contrato por vencer",
  sobreprecio: "Sobreprecio",
  riesgo: "Proveedor en riesgo",
}

export const NOMBRES_SEVERIDAD: Record<Severidad, string> = {
  alta: "Alta",
  media: "Media",
  informativa: "Informativa",
}
```

- [ ] **Step 2: Escribir las pruebas (fallan)**

`web/src/paginas/Tablero.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Tablero } from "@/paginas/Tablero"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("Tablero", () => {
  it("saluda y muestra los cuatro indicadores sin datos con su enlace", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Tablero />)

    expect(screen.getByRole("heading", { level: 1, name: "Tablero" })).toBeInTheDocument()
    expect(screen.getByText(/Hola, Ana\./)).toBeInTheDocument()
    expect(screen.getAllByText("Sin datos")).toHaveLength(4)
    expect(screen.getByRole("link", { name: "Ver vencimientos" })).toHaveAttribute("href", "/alertas?tipo=vencimiento")
    expect(screen.getByRole("link", { name: "Ver riesgos" })).toHaveAttribute("href", "/alertas?tipo=riesgo")
    expect(screen.getByRole("link", { name: "Ver sobreprecios" })).toHaveAttribute("href", "/precios?vista=sobreprecios")
    expect(screen.getByRole("note")).toHaveTextContent("Inteligencia en preparación")
  })

  it("solo el administrador ve el estado de los datos", () => {
    renderizarPagina(<Tablero />)
    expect(screen.getByRole("heading", { name: "Estado de los datos" })).toBeInTheDocument()

    cleanup()
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Tablero />)
    expect(screen.queryByRole("heading", { name: "Estado de los datos" })).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Tablero />)
    await esperarSinViolaciones(container)
  })
})
```

`web/src/paginas/Ranking.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Ranking } from "@/paginas/Ranking"
import { esperarSinViolaciones, renderizarPagina, ubicacionActual } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

afterEach(cleanup)

describe("Ranking", () => {
  it("abre la categoría indicada en la URL", () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=nube" })
    expect(screen.getByRole("tab", { name: "Nube" })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByRole("heading", { name: "Ranking · Nube" })).toBeInTheDocument()
    expect(screen.getByText("Sin puntuaciones todavía")).toBeInTheDocument()
  })

  it("cambiar de pestaña actualiza la URL", async () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await userEvent.click(screen.getByRole("tab", { name: "Soporte" }))
    expect(ubicacionActual()).toBe("/ranking?categoria=soporte")
    await userEvent.click(screen.getByRole("tab", { name: "Todas" }))
    expect(ubicacionActual()).toBe("/ranking")
  })

  it("una categoría inválida muestra todas", () => {
    renderizarPagina(<Ranking />, { ruta: "/ranking?categoria=inventada" })
    expect(screen.getByRole("tab", { name: "Todas" })).toHaveAttribute("aria-selected", "true")
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Ranking />, { ruta: "/ranking" })
    await esperarSinViolaciones(container)
  })
})
```

`web/src/paginas/Alertas.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Alertas } from "@/paginas/Alertas"
import { esperarSinViolaciones, renderizarPagina, ubicacionActual } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

afterEach(cleanup)

describe("Alertas", () => {
  it("lee los filtros de la URL y ofrece quitarlos", async () => {
    renderizarPagina(<Alertas />, { ruta: "/alertas?tipo=vencimiento&severidad=alta" })

    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent("Contrato por vencer")
    expect(screen.getByRole("combobox", { name: "Severidad" })).toHaveTextContent("Alta")
    expect(screen.getByText("No hay alertas activas")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "Quitar filtros" }))
    expect(ubicacionActual()).toBe("/alertas")
  })

  it("cambiar el tipo actualiza la URL", async () => {
    renderizarPagina(<Alertas />, { ruta: "/alertas" })
    await userEvent.click(screen.getByRole("combobox", { name: "Tipo" }))
    await userEvent.click(await screen.findByRole("option", { name: "Sobreprecio" }))
    expect(ubicacionActual()).toBe("/alertas?tipo=sobreprecio")
  })

  it("ignora valores inválidos de la URL", () => {
    renderizarPagina(<Alertas />, { ruta: "/alertas?tipo=inventado&severidad=x" })
    expect(screen.getByRole("combobox", { name: "Tipo" })).toHaveTextContent("Todos los tipos")
    expect(screen.queryByRole("button", { name: "Quitar filtros" })).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Alertas />, { ruta: "/alertas" })
    await esperarSinViolaciones(container)
  })
})
```

`web/src/paginas/Configuracion.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Configuracion } from "@/paginas/Configuracion"
import { sesionDePrueba } from "@/pruebas/sesion"
import { esperarSinViolaciones, renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("Configuracion", () => {
  it("muestra al administrador las secciones de puntuación y modelo", () => {
    renderizarPagina(<Configuracion />)
    expect(screen.getByRole("heading", { name: "Pesos de la puntuación" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Modelo de precios" })).toBeInTheDocument()
  })

  it("bloquea a quien no es administrador", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<Configuracion />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Pesos de la puntuación" })).not.toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    const { container } = renderizarPagina(<Configuracion />)
    await esperarSinViolaciones(container)
  })
})
```

Run: `(cd web && npx vitest run src/paginas/Tablero.test.tsx src/paginas/Ranking.test.tsx src/paginas/Alertas.test.tsx src/paginas/Configuracion.test.tsx)` → Expected: FAIL (no existen las páginas).

- [ ] **Step 3: Implementar los componentes compartidos**

`web/src/componentes/AvisoInteligencia.tsx`:

```tsx
import { Info } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

/** Aviso temporal: el Plan B lo elimina al conectar el servicio de inteligencia. */
export function AvisoInteligencia() {
  return (
    <Alert role="note">
      <Info aria-hidden />
      <AlertTitle>Inteligencia en preparación</AlertTitle>
      <AlertDescription>
        Los indicadores, precios de referencia, puntuaciones y alertas se activarán con el servicio de
        inteligencia. Mientras tanto puede consultar proveedores, contratos y desempeño.
      </AlertDescription>
    </Alert>
  )
}
```

`web/src/componentes/TarjetaKpi.tsx`:

```tsx
import { ArrowRight, type LucideIcon } from "lucide-react"
import { Link } from "react-router"
import { Card, CardContent } from "@/components/ui/card"

export function TarjetaKpi({
  titulo,
  valor,
  detalle,
  icono: Icono,
  enlace,
  textoEnlace,
}: {
  titulo: string
  valor: string | null
  detalle?: string
  icono: LucideIcon
  enlace: string
  textoEnlace: string
}) {
  return (
    <Card size="sm">
      <CardContent className="space-y-2">
        <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
          <span>{titulo}</span>
          <Icono aria-hidden className="size-4" />
        </div>
        <p className="text-2xl font-semibold">
          {valor ?? (
            <>
              <span aria-hidden>—</span>
              <span className="sr-only">Sin datos</span>
            </>
          )}
        </p>
        {detalle && <p className="text-xs text-muted-foreground">{detalle}</p>}
        <Link
          to={enlace}
          className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
        >
          {textoEnlace}
          <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 4: Implementar las páginas**

`web/src/paginas/Tablero.tsx`:

```tsx
import {
  CalendarClock,
  ChartBar,
  ChartLine,
  Database,
  ListOrdered,
  PiggyBank,
  TriangleAlert,
  Wallet,
} from "lucide-react"
import { useAuth } from "react-oidc-context"
import { useRoles } from "@/auth"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { TarjetaKpi } from "@/componentes/TarjetaKpi"

const KPIS = [
  { titulo: "Gasto anual contratado", icono: Wallet, enlace: "/proveedores", textoEnlace: "Ver proveedores" },
  { titulo: "Por vencer (90 días)", icono: CalendarClock, enlace: "/alertas?tipo=vencimiento", textoEnlace: "Ver vencimientos" },
  { titulo: "Proveedores en riesgo", icono: TriangleAlert, enlace: "/alertas?tipo=riesgo", textoEnlace: "Ver riesgos" },
  { titulo: "Ahorro potencial", icono: PiggyBank, enlace: "/precios?vista=sobreprecios", textoEnlace: "Ver sobreprecios" },
]

export function Tablero() {
  const auth = useAuth()
  const roles = useRoles()
  const nombre = auth.user?.profile.given_name ?? auth.user?.profile.preferred_username
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Tablero"
        descripcion={`${nombre ? `Hola, ${nombre}. ` : ""}Resumen de las compras de servicios de TI.`}
      />
      <AvisoInteligencia />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {KPIS.map((kpi) => (
          <TarjetaKpi key={kpi.titulo} {...kpi} valor={null} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Seccion titulo="Gasto por categoría">
          <EstadoVacio icono={ChartBar} titulo="Sin datos todavía" descripcion="Aquí verá el gasto anual contratado por categoría de servicio." />
        </Seccion>
        <Seccion titulo="Gasto comprometido por mes">
          <EstadoVacio icono={ChartLine} titulo="Sin datos todavía" descripcion="Aquí verá el gasto comprometido de los últimos 24 meses." />
        </Seccion>
        <Seccion titulo="Próximos vencimientos">
          <EstadoVacio icono={CalendarClock} titulo="Sin datos todavía" descripcion="Aquí verá los contratos que vencen en los próximos 90 días." />
        </Seccion>
        <Seccion titulo="Alertas principales">
          <EstadoVacio icono={TriangleAlert} titulo="Sin datos todavía" descripcion="Aquí verá las alertas más severas: vencimientos, sobreprecios y riesgos." />
        </Seccion>
      </div>
      <Seccion titulo="Mejores y peores proveedores">
        <EstadoVacio icono={ListOrdered} titulo="Sin datos todavía" descripcion="Aquí verá los 5 proveedores con mejor y peor puntuación." />
      </Seccion>
      {roles.includes("admin") && (
        <Seccion titulo="Estado de los datos">
          <EstadoVacio icono={Database} titulo="Sin datos todavía" descripcion="Aquí verá la fecha de la última importación, los registros por entidad y el modelo de precios activo." />
        </Seccion>
      )}
    </section>
  )
}
```

`web/src/paginas/Ranking.tsx`:

```tsx
import { Trophy } from "lucide-react"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { unoDe, useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA } from "@/tipos"

const TODAS = "todas"
const OPCIONES: [string, string][] = [[TODAS, "Todas"], ...CATEGORIAS.map((c): [string, string] => [c, NOMBRES_CATEGORIA[c]])]

export function Ranking() {
  const [parametros, actualizar] = useParametros()
  const activa = unoDe(parametros.get("categoria"), CATEGORIAS) ?? TODAS
  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Ranking de proveedores"
        descripcion="Proveedores ordenados por su puntuación ajustada dentro de cada categoría."
      />
      <AvisoInteligencia />
      <Tabs value={activa} onValueChange={(valor) => actualizar({ categoria: valor === TODAS ? null : valor })}>
        <TabsList className="h-auto flex-wrap">
          {OPCIONES.map(([valor, nombre]) => (
            <TabsTrigger key={valor} value={valor}>
              {nombre}
            </TabsTrigger>
          ))}
        </TabsList>
        {OPCIONES.map(([valor, nombre]) => (
          <TabsContent key={valor} value={valor} className="mt-4">
            <Seccion titulo={`Ranking · ${valor === TODAS ? "Todas las categorías" : nombre}`}>
              <EstadoVacio
                icono={Trophy}
                titulo="Sin puntuaciones todavía"
                descripcion="El ranking ordenará a los proveedores por SLA, resolución, incidentes, entregas a tiempo y satisfacción; los que tengan menos de 6 meses de historial se marcarán como “Historial corto”."
              />
            </Seccion>
          </TabsContent>
        ))}
      </Tabs>
    </section>
  )
}
```

`web/src/paginas/Alertas.tsx`:

```tsx
import { BellOff } from "lucide-react"
import { useId } from "react"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { unoDe, useParametros } from "@/parametros"
import { NOMBRES_SEVERIDAD, NOMBRES_TIPO_ALERTA, type Severidad, type TipoAlerta } from "@/tipos"

// Radix Select no admite el valor vacío: "todas" representa "sin filtro".
const TODAS = "todas"
const TIPOS = Object.keys(NOMBRES_TIPO_ALERTA) as TipoAlerta[]
const SEVERIDADES = Object.keys(NOMBRES_SEVERIDAD) as Severidad[]

function Filtro({
  etiqueta,
  valor,
  opciones,
  alCambiar,
}: {
  etiqueta: string
  valor: string
  opciones: [string, string][]
  alCambiar: (valor: string) => void
}) {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <span id={id} className="text-sm font-medium">
        {etiqueta}
      </span>
      <Select value={valor} onValueChange={alCambiar}>
        <SelectTrigger aria-labelledby={id} className="w-56">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {opciones.map(([v, nombre]) => (
            <SelectItem key={v} value={v}>
              {nombre}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export function Alertas() {
  const [parametros, actualizar] = useParametros()
  const tipo = unoDe(parametros.get("tipo"), TIPOS)
  const severidad = unoDe(parametros.get("severidad"), SEVERIDADES)
  const hayFiltros = Boolean(tipo || severidad)
  return (
    <section className="space-y-6">
      <EncabezadoPagina titulo="Alertas" descripcion="Contratos por vencer, sobreprecios y proveedores en riesgo." />
      <AvisoInteligencia />
      <div className="flex flex-wrap gap-4">
        <Filtro
          etiqueta="Tipo"
          valor={tipo ?? TODAS}
          opciones={[[TODAS, "Todos los tipos"], ...TIPOS.map((t): [string, string] => [t, NOMBRES_TIPO_ALERTA[t]])]}
          alCambiar={(v) => actualizar({ tipo: v === TODAS ? null : v })}
        />
        <Filtro
          etiqueta="Severidad"
          valor={severidad ?? TODAS}
          opciones={[[TODAS, "Todas las severidades"], ...SEVERIDADES.map((s): [string, string] => [s, NOMBRES_SEVERIDAD[s]])]}
          alCambiar={(v) => actualizar({ severidad: v === TODAS ? null : v })}
        />
      </div>
      <Seccion titulo="Alertas activas">
        <EstadoVacio
          icono={BellOff}
          titulo="No hay alertas activas"
          descripcion="Aquí aparecerán los contratos por vencer en 90, 60 y 30 días, los precios sobre P75 y los proveedores con puntuación baja o en caída."
          accion={
            hayFiltros && (
              <Button variant="outline" onClick={() => actualizar({ tipo: null, severidad: null })}>
                Quitar filtros
              </Button>
            )
          }
        />
      </Seccion>
    </section>
  )
}
```

`web/src/paginas/Configuracion.tsx`:

```tsx
import { Database, SlidersHorizontal } from "lucide-react"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"

export function Configuracion() {
  return (
    <RequiereRol rol="admin">
      <section className="space-y-6">
        <EncabezadoPagina
          titulo="Configuración"
          descripcion="Parámetros de la puntuación de proveedores y del modelo de precios."
        />
        <AvisoInteligencia />
        <div className="grid gap-4 lg:grid-cols-2">
          <Seccion titulo="Pesos de la puntuación">
            <EstadoVacio
              icono={SlidersHorizontal}
              titulo="Sin configuración todavía"
              descripcion="Podrá ajustar los pesos de SLA, resolución, incidentes, entregas y satisfacción (deben sumar 100), el umbral de riesgo y la inflación anual."
            />
          </Seccion>
          <Seccion titulo="Modelo de precios">
            <EstadoVacio
              icono={Database}
              titulo="Sin modelos entrenados"
              descripcion="Aquí verá la versión activa del modelo, su error (MAPE) y podrá reentrenarlo."
            />
          </Seccion>
        </div>
      </section>
    </RequiereRol>
  )
}
```

Reemplace `web/src/paginas/NoEncontrado.tsx`:

```tsx
import { FileQuestion } from "lucide-react"
import { Link } from "react-router"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoVacio } from "@/componentes/Estados"
import { Button } from "@/components/ui/button"

export function NoEncontrado() {
  return (
    <section className="space-y-6">
      <EncabezadoPagina titulo="Página no encontrada" />
      <EstadoVacio
        icono={FileQuestion}
        titulo="No encontramos esta página"
        descripcion="Revise la dirección o vuelva al tablero."
        accion={
          <Button asChild>
            <Link to="/">Ir al tablero</Link>
          </Button>
        }
      />
    </section>
  )
}
```

Reemplace `web/src/rutas.tsx` y borre `Inicio.tsx` (`git rm web/src/paginas/Inicio.tsx`):

```tsx
import { createBrowserRouter } from "react-router"
import { Layout } from "@/componentes/Layout"
import { Alertas } from "@/paginas/Alertas"
import { Configuracion } from "@/paginas/Configuracion"
import { Importacion } from "@/paginas/Importacion"
import { NoEncontrado } from "@/paginas/NoEncontrado"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"
import { Proveedores } from "@/paginas/Proveedores"
import { Ranking } from "@/paginas/Ranking"
import { Tablero } from "@/paginas/Tablero"

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Tablero },
      { path: "proveedores", Component: Proveedores },
      { path: "proveedores/:id", Component: ProveedorDetalle },
      { path: "ranking", Component: Ranking },
      { path: "alertas", Component: Alertas },
      { path: "importacion", Component: Importacion },
      { path: "configuracion", Component: Configuracion },
      { path: "*", Component: NoEncontrado },
    ],
  },
])
```

- [ ] **Step 5: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/paginas/Tablero.test.tsx src/paginas/Ranking.test.tsx src/paginas/Alertas.test.tsx src/paginas/Configuracion.test.tsx)`
Expected: PASS. Si axe marca `aria-valid-attr-value` en las pestañas de Ranking, aplique la misma corrección que en la Tarea 6 (`forceMount` + `hidden`).

- [ ] **Step 6: Verificación completa y commit**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)` → todo en verde.

```bash
git add web/src/componentes/AvisoInteligencia.tsx web/src/componentes/TarjetaKpi.tsx web/src/paginas web/src/rutas.tsx web/src/tipos.ts
git commit -m "feat(web): tablero, ranking, alertas y configuración con su estructura final y estados vacíos"
```

---

### Task 9: Precios — catálogo de servicios con búsqueda

**Files:**
- Create: `web/src/paginas/Precios.tsx`, `web/src/paginas/Precios.test.tsx`
- Modify: `web/src/tipos.ts` (`Servicio`, `normalizarTexto`), `web/src/rutas.tsx` (ruta `precios`)

**Interfaces:**
- Consumes: `ContenidoConsulta`, `EstadoVacio`, `EncabezadoPagina`, `Seccion` (Tarea 3); `useParametros` (Tarea 5); `AvisoInteligencia` (Tarea 8); `GET /api/proveedores/servicios` (ya existe; responde `Servicio[]` ordenados por categoría y código).
- Produces:
  - `type Servicio = { id: string; codigo: string; nombre: string; categoria: Categoria; unidad: string; moneda: "MXN" | "USD" }`
  - `normalizarTexto(texto: string): string` — minúsculas sin acentos (para buscar "consultoria" y hallar "Consultoría").
  - Parámetros de URL de `/precios`: `servicio` (código del catálogo) y `vista=sobreprecios`. Clave de consulta `["servicios"]`.

- [ ] **Step 1: Escribir las pruebas (fallan)**

`web/src/paginas/Precios.test.tsx`:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Precios } from "@/paginas/Precios"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"
import { normalizarTexto } from "@/tipos"

vi.mock("react-oidc-context", async () => (await import("@/pruebas/sesion")).oidcSimulado())

const SERVICIOS = [
  { id: "s1", codigo: "CONS-01", nombre: "Consultoría SAP", categoria: "consultoria", unidad: "hora", moneda: "MXN" },
  { id: "s2", codigo: "NUBE-01", nombre: "Cómputo en la nube", categoria: "nube", unidad: "mes", moneda: "USD" },
  { id: "s3", codigo: "NUBE-02", nombre: "Almacenamiento de objetos", categoria: "nube", unidad: "TB", moneda: "USD" },
]

const conCatalogo = (servicios: object[] = SERVICIOS) =>
  simularApi({ "/api/proveedores/servicios": () => respuestaJson(servicios) })

const renderizar = (ruta = "/precios") => renderizarPagina(<Precios />, { ruta })
const lista = () => screen.getByRole("list", { name: "Servicios del catálogo" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  sesionDePrueba.roles = ["admin"]
})

describe("normalizarTexto", () => {
  it("quita acentos y mayúsculas", () => {
    expect(normalizarTexto("Consultoría ÓPTIMA")).toBe("consultoria optima")
  })
})

describe("Precios", () => {
  it("muestra un esqueleto mientras carga el catálogo", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})))
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("agrupa los servicios por categoría", async () => {
    conCatalogo()
    renderizar()

    expect(await screen.findByRole("button", { name: /Consultoría SAP/ })).toBeInTheDocument()
    expect(within(lista()).getByText("Consultoría")).toBeInTheDocument()
    expect(within(lista()).getByText("Nube")).toBeInTheDocument()
    expect(screen.getByText("Elija un servicio")).toBeInTheDocument()
  })

  it("busca por nombre o código sin importar acentos ni mayúsculas", async () => {
    conCatalogo()
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })
    const buscador = screen.getByRole("searchbox", { name: "Buscar servicio por nombre o código" })

    await userEvent.type(buscador, "CONSULTORIA")
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "nube-02")
    expect(within(lista()).getByRole("button", { name: /Almacenamiento de objetos/ })).toBeInTheDocument()
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "zzz")
    expect(screen.getByText("Ningún servicio coincide con «zzz».")).toBeInTheDocument()
  })

  it("elegir un servicio lo refleja en la URL y muestra su detalle", async () => {
    conCatalogo()
    renderizar()

    await userEvent.click(await screen.findByRole("button", { name: /Cómputo en la nube/ }))

    expect(ubicacionActual()).toBe("/precios?servicio=NUBE-01")
    expect(screen.getByRole("button", { name: /Cómputo en la nube/ })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("heading", { level: 2, name: "Cómputo en la nube" })).toBeInTheDocument()
    expect(screen.getByText("NUBE-01 · Nube · por mes · USD")).toBeInTheDocument()
  })

  it("un servicio desconocido en la URL pide elegir uno", async () => {
    conCatalogo()
    renderizar("/precios?servicio=NO-EXISTE")
    expect(await screen.findByText("Elija un servicio")).toBeInTheDocument()
  })

  it("cambia a la vista de todos los sobreprecios", async () => {
    conCatalogo()
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })

    await userEvent.click(screen.getByRole("button", { name: "Todos los sobreprecios" }))

    expect(ubicacionActual()).toBe("/precios?vista=sobreprecios")
    expect(screen.getByRole("heading", { level: 2, name: "Todos los sobreprecios" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Todos los sobreprecios" })).toHaveAttribute("aria-pressed", "true")
  })

  it("con el catálogo vacío invita al administrador a importar", async () => {
    conCatalogo([])
    renderizar()
    expect(await screen.findByText("El catálogo está vacío")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ir a Importación" })).toHaveAttribute("href", "/importacion")
  })

  it("muestra el error en español y permite reintentar", async () => {
    let fallar = true
    simularApi(() => (fallar ? new Response("", { status: 502 }) : respuestaJson(SERVICIOS)))
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent("El servicio no está disponible")
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByRole("button", { name: /Consultoría SAP/ })).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    conCatalogo()
    const { container } = renderizar("/precios?servicio=NUBE-01")
    await screen.findByRole("heading", { level: 2, name: "Cómputo en la nube" })
    await esperarSinViolaciones(container)
  })
})
```

Run: `(cd web && npx vitest run src/paginas/Precios.test.tsx)` → Expected: FAIL.

- [ ] **Step 2: Agregar `Servicio` y `normalizarTexto` a `web/src/tipos.ts`**

```ts
export type Servicio = {
  id: string
  codigo: string
  nombre: string
  categoria: Categoria
  unidad: string
  moneda: "MXN" | "USD"
}

/** Minúsculas y sin acentos, para buscar "consultoria" y encontrar "Consultoría". */
export function normalizarTexto(texto: string): string {
  return texto.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase()
}
```

- [ ] **Step 3: Implementar `web/src/paginas/Precios.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query"
import { ChartLine, Tags, TrendingUp } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { AvisoInteligencia } from "@/componentes/AvisoInteligencia"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useParametros } from "@/parametros"
import { CATEGORIAS, NOMBRES_CATEGORIA, normalizarTexto, type Servicio } from "@/tipos"

function ListaServicios({
  servicios,
  seleccionado,
  alElegir,
}: {
  servicios: Servicio[]
  seleccionado: string | null
  alElegir: (codigo: string) => void
}) {
  const [busqueda, setBusqueda] = useState("")
  const termino = normalizarTexto(busqueda.trim())
  const visibles = servicios.filter(
    (s) => !termino || normalizarTexto(`${s.nombre} ${s.codigo}`).includes(termino)
  )
  const grupos = CATEGORIAS.map((categoria) => ({
    categoria,
    servicios: visibles.filter((s) => s.categoria === categoria),
  })).filter((grupo) => grupo.servicios.length > 0)

  return (
    <div className="space-y-3">
      <label htmlFor="buscar-servicio" className="sr-only">
        Buscar servicio por nombre o código
      </label>
      <Input
        id="buscar-servicio"
        type="search"
        placeholder="Nombre o código"
        value={busqueda}
        onChange={(evento) => setBusqueda(evento.target.value)}
      />
      {grupos.length === 0 ? (
        <p className="px-2 py-4 text-sm text-muted-foreground">Ningún servicio coincide con «{busqueda.trim()}».</p>
      ) : (
        <ul aria-label="Servicios del catálogo" className="max-h-[28rem] space-y-3 overflow-y-auto">
          {grupos.map((grupo) => (
            <li key={grupo.categoria}>
              <p className="px-2 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {NOMBRES_CATEGORIA[grupo.categoria]}
              </p>
              <ul className="space-y-1">
                {grupo.servicios.map((s) => (
                  <li key={s.codigo}>
                    <button
                      type="button"
                      aria-pressed={s.codigo === seleccionado}
                      onClick={() => alElegir(s.codigo)}
                      className="group w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted aria-pressed:bg-accent aria-pressed:text-accent-foreground"
                    >
                      <span className="block">{s.nombre}</span>
                      <span className="font-mono text-xs text-muted-foreground group-aria-pressed:text-accent-foreground">
                        {s.codigo}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function DetalleServicio({ servicio }: { servicio: Servicio }) {
  return (
    <div className="space-y-4">
      <Seccion
        titulo={servicio.nombre}
        descripcion={`${servicio.codigo} · ${NOMBRES_CATEGORIA[servicio.categoria] ?? servicio.categoria} · por ${servicio.unidad} · ${servicio.moneda}`}
      >
        <EstadoVacio
          icono={Tags}
          titulo="Sin precio de referencia todavía"
          descripcion="Aquí verá P25, P50 y P75 para la cantidad y el plazo que indique, con el método usado, su confianza y el número de observaciones."
        />
      </Seccion>
      <Seccion titulo="Historial de precios">
        <EstadoVacio
          icono={ChartLine}
          titulo="Sin historial todavía"
          descripcion="Aquí verá los precios de los contratos en el tiempo sobre la banda P25–P75."
        />
      </Seccion>
      <Seccion titulo="Contratos sobre P75">
        <EstadoVacio
          icono={TrendingUp}
          titulo="Sin sobreprecios detectados todavía"
          descripcion="Aquí verá los contratos vigentes de este servicio por encima de P75 y su ahorro potencial anual."
        />
      </Seccion>
    </div>
  )
}

export function Precios() {
  const token = useToken()
  const roles = useRoles()
  const [parametros, actualizar] = useParametros()
  const vista = parametros.get("vista") === "sobreprecios" ? "sobreprecios" : "servicio"
  const codigo = parametros.get("servicio")

  const servicios = useQuery({
    queryKey: ["servicios"],
    queryFn: () => pedir<Servicio[]>("/proveedores/servicios", token),
    enabled: Boolean(token),
  })

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Precios"
        descripcion="Precio de referencia por servicio (P25, P50 y P75) y contratos por encima del mercado."
        acciones={
          <div role="group" aria-label="Vista" className="flex gap-2">
            <Button
              variant={vista === "servicio" ? "default" : "outline"}
              aria-pressed={vista === "servicio"}
              onClick={() => actualizar({ vista: null })}
            >
              Por servicio
            </Button>
            <Button
              variant={vista === "sobreprecios" ? "default" : "outline"}
              aria-pressed={vista === "sobreprecios"}
              onClick={() => actualizar({ vista: "sobreprecios" })}
            >
              Todos los sobreprecios
            </Button>
          </div>
        }
      />
      <AvisoInteligencia />
      {vista === "sobreprecios" ? (
        <Seccion titulo="Todos los sobreprecios">
          <EstadoVacio
            icono={TrendingUp}
            titulo="Sin sobreprecios detectados todavía"
            descripcion="Aquí verá los contratos vigentes por encima de P75, ordenados por ahorro potencial."
          />
        </Seccion>
      ) : (
        <ContenidoConsulta consulta={servicios}>
          {(catalogo) => {
            if (catalogo.length === 0) {
              const esAdmin = roles.includes("admin")
              return (
                <EstadoVacio
                  icono={Tags}
                  titulo="El catálogo está vacío"
                  descripcion={
                    esAdmin
                      ? "Importe el catálogo de servicios del ERP para consultar precios."
                      : "Pida a un administrador que importe el catálogo del ERP."
                  }
                  accion={
                    esAdmin && (
                      <Button asChild>
                        <Link to="/importacion">Ir a Importación</Link>
                      </Button>
                    )
                  }
                />
              )
            }
            const seleccionado = catalogo.find((s) => s.codigo === codigo) ?? null
            return (
              <div className="grid items-start gap-4 lg:grid-cols-[20rem_1fr]">
                <Seccion titulo="Servicios">
                  <ListaServicios
                    servicios={catalogo}
                    seleccionado={seleccionado?.codigo ?? null}
                    alElegir={(nuevo) => actualizar({ servicio: nuevo })}
                  />
                </Seccion>
                {seleccionado ? (
                  <DetalleServicio servicio={seleccionado} />
                ) : (
                  <Seccion titulo="Servicio">
                    <EstadoVacio
                      icono={Tags}
                      titulo="Elija un servicio"
                      descripcion="Seleccione un servicio del catálogo para ver su precio de referencia y su historial."
                    />
                  </Seccion>
                )}
              </div>
            )
          }}
        </ContenidoConsulta>
      )}
    </section>
  )
}
```

En `web/src/rutas.tsx` importe `Precios` y agregue `{ path: "precios", Component: Precios },` después de la ruta `ranking`.

- [ ] **Step 4: Verificar que las pruebas pasan**

Run: `(cd web && npx vitest run src/paginas/Precios.test.tsx)`
Expected: PASS, salida limpia.

- [ ] **Step 5: Verificación completa y commit**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)` → todo en verde.

```bash
git add web/src/paginas/Precios.tsx web/src/paginas/Precios.test.tsx web/src/tipos.ts web/src/rutas.tsx
git commit -m "feat(web): página de precios con catálogo agrupado y búsqueda sin acentos"
```

---

### Task 10: Tema de inicio de sesión de Keycloak

**Files:**
- Create: `infra/keycloak/themes/plataforma/login/theme.properties`
- Create: `infra/keycloak/themes/plataforma/login/resources/css/plataforma.css`
- Create: `infra/keycloak/themes/plataforma/login/resources/fonts/fira-sans-latin-400-normal.woff2`, `fira-sans-latin-600-normal.woff2`, `OFL.txt` (copiados de `@fontsource/fira-sans`)
- Modify: `infra/keycloak/realm-plataforma.json` (`"loginTheme": "plataforma"`), `infra/docker-compose.yml` (montaje), `infra/smoke_test.py`, `README.md`

**Interfaces:**
- Consumes: `@fontsource/fira-sans` instalado en la Tarea 1 (archivos en `web/node_modules/@fontsource/fira-sans/files/`).
- Produces: tema `plataforma` (padre `keycloak.v2`, solo CSS) montado en `/opt/keycloak/themes/plataforma`; la página de inicio de sesión enlaza `…/login/plataforma/css/plataforma.css`.

Datos verificados del tema `keycloak.v2` de Keycloak 26.5.7: `parent=base`, `import=common/keycloak`, `styles=css/styles.css`, `stylesCommon` con PatternFly 5, `darkMode=true` con la clase `pf-v5-theme-dark`; el título superior es `#kc-header-wrapper` con el `displayName` del realm; el botón principal usa `--pf-v5-c-button--m-primary--BackgroundColor`.

- [ ] **Step 1: Agregar la verificación a la prueba de humo (falla)**

En `infra/smoke_test.py`, dentro del `with httpx.Client(...)`, después de la verificación de la CSP de la SPA:

```python
        acceso = cliente.get(
            "/auth/realms/plataforma/protocol/openid-connect/auth",
            params={
                "client_id": "web",
                "response_type": "code",
                "scope": "openid",
                "redirect_uri": f"{BASE}/",
                "code_challenge": "A" * 43,
                "code_challenge_method": "S256",
            },
        )
        verificar(
            acceso.status_code == 200 and "login/plataforma/css/plataforma.css" in acceso.text,
            "Keycloak no aplica el tema de inicio de sesión 'plataforma'",
        )
```

Run: `uv run python infra/smoke_test.py`
Expected: `FALLA: Keycloak no aplica el tema de inicio de sesión 'plataforma'`.

- [ ] **Step 2: Crear el tema**

`infra/keycloak/themes/plataforma/login/theme.properties`:

```properties
# Extiende el inicio de sesión v2 de Keycloak solo con CSS (sin plantillas propias que mantener).
parent=keycloak.v2
import=common/keycloak
styles=css/styles.css css/plataforma.css
```

Copie las fuentes y su licencia (la OFL exige distribuirla junto con las fuentes):

Run: `mkdir -p infra/keycloak/themes/plataforma/login/resources/fonts infra/keycloak/themes/plataforma/login/resources/css`
Run: `cp web/node_modules/@fontsource/fira-sans/files/fira-sans-latin-400-normal.woff2 web/node_modules/@fontsource/fira-sans/files/fira-sans-latin-600-normal.woff2 infra/keycloak/themes/plataforma/login/resources/fonts/`
Run: `cp web/node_modules/@fontsource/fira-sans/LICENSE infra/keycloak/themes/plataforma/login/resources/fonts/OFL.txt`

`infra/keycloak/themes/plataforma/login/resources/css/plataforma.css`:

```css
/* Tema "plataforma": misma identidad que la SPA (dirección A, corporativa clara). Solo CSS. */

@font-face {
  font-family: "Fira Sans";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("../fonts/fira-sans-latin-400-normal.woff2") format("woff2");
}

@font-face {
  font-family: "Fira Sans";
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url("../fonts/fira-sans-latin-600-normal.woff2") format("woff2");
}

/* Mismos valores que los tokens de web/src/index.css. */
:root {
  --plataforma-fondo: #0F172A;
  --plataforma-acento: #0369A1;
  --plataforma-acento-hover: #075985;
  --plataforma-sobre-acento: #FFFFFF;
}

.pf-v5-theme-dark {
  --plataforma-fondo: #0B1220;
  --plataforma-acento: #38BDF8;
  --plataforma-acento-hover: #7DD3FC;
  --plataforma-sobre-acento: #0B1220;
}

:root,
.pf-v5-theme-dark {
  --pf-v5-global--FontFamily--text: "Fira Sans", system-ui, sans-serif;
  --pf-v5-global--FontFamily--heading: "Fira Sans", system-ui, sans-serif;
  --pf-v5-global--primary-color--100: var(--plataforma-acento);
  --pf-v5-global--primary-color--200: var(--plataforma-acento-hover);
  --pf-v5-global--link--Color: var(--plataforma-acento);
  --pf-v5-global--link--Color--hover: var(--plataforma-acento-hover);
  --keycloak-card-top-color: var(--plataforma-acento);
}

/* Fondo marino en ambos temas, como el menú lateral de la SPA. */
.login-pf body {
  background: var(--plataforma-fondo);
}

/* Nombre del producto sobre el nombre del realm, sin mayúsculas forzadas. */
#kc-header-wrapper {
  font-family: "Fira Sans", system-ui, sans-serif;
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: normal;
  text-transform: none;
  color: #E2E8F0 !important;
}

#kc-header-wrapper::before {
  content: "PluriOne";
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.875rem;
  font-weight: 400;
  color: #94A3B8;
}

.pf-v5-c-login__main {
  border-radius: 12px;
}

/* Botón principal: el texto sobre el acento cumple 4.5:1 en ambos temas. */
.pf-v5-c-button.pf-m-primary {
  --pf-v5-c-button--m-primary--BackgroundColor: var(--plataforma-acento);
  --pf-v5-c-button--m-primary--hover--BackgroundColor: var(--plataforma-acento-hover);
  --pf-v5-c-button--m-primary--focus--BackgroundColor: var(--plataforma-acento-hover);
  --pf-v5-c-button--m-primary--active--BackgroundColor: var(--plataforma-acento-hover);
  --pf-v5-c-button--m-primary--Color: var(--plataforma-sobre-acento);
  --pf-v5-c-button--m-primary--hover--Color: var(--plataforma-sobre-acento);
  --pf-v5-c-button--m-primary--focus--Color: var(--plataforma-sobre-acento);
  --pf-v5-c-button--m-primary--active--Color: var(--plataforma-sobre-acento);
}

/* Foco siempre visible. */
:focus-visible {
  outline: 2px solid var(--plataforma-acento);
  outline-offset: 2px;
}
```

- [ ] **Step 3: Montar el tema y asignarlo en el realm**

En `infra/docker-compose.yml`, en `keycloak.volumes`, agregue debajo del montaje de importación:

```yaml
      - ./keycloak/themes/plataforma:/opt/keycloak/themes/plataforma:ro
```

(La importación lee solo los `.json` de `/opt/keycloak/data/import`; la carpeta `themes/` que queda dentro de ese montaje se ignora.)

En `infra/keycloak/realm-plataforma.json`, agregue después de `"defaultLocale": "es",`:

```json
  "loginTheme": "plataforma",
```

- [ ] **Step 4: Recrear Keycloak y aplicar el tema al realm ya importado**

Keycloak solo importa el realm la primera vez, así que en un volumen existente el tema se asigna con `kcadm.sh` (no borra datos):

Run: `docker compose -f infra/docker-compose.yml up -d --wait keycloak`
Run: `docker compose -f infra/docker-compose.yml logs --no-color --tail 50 keycloak` → Expected: sin errores de importación ni de temas.
Run:

```bash
docker compose -f infra/docker-compose.yml exec keycloak bash -c '/opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config --server http://localhost:8080/auth --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" && /opt/keycloak/bin/kcadm.sh update realms/plataforma --config /tmp/kcadm.config -s loginTheme=plataforma'
```

Expected: sin salida de error.

- [ ] **Step 5: Verificar con la prueba de humo y en el navegador**

Run: `uv run python infra/smoke_test.py`
Expected: `OK: SPA, Keycloak y proveedores responden (… proveedores).`

En el navegador (http://localhost:8080 → redirige al inicio de sesión) confirme, en tema claro y oscuro del sistema: fondo marino, "PluriOne" sobre "Plataforma de Negociación" sin mayúsculas forzadas, botón "Iniciar sesión" en el acento con texto legible, foco visible al tabular. Si no tiene navegador, anótelo en el reporte para la Tarea 11.

- [ ] **Step 6: Documentar en `README.md`**

Agregue al final de la sección "Arranque rápido" (antes de "### Notas para Windows"):

````markdown
### Tema de inicio de sesión en un realm ya importado

Keycloak importa el realm solo la primera vez. Si su volumen de PostgreSQL ya tenía el realm
`plataforma`, aplique el tema de inicio de sesión una sola vez (no borra datos):

```bash
docker compose -f infra/docker-compose.yml up -d --wait keycloak
docker compose -f infra/docker-compose.yml exec keycloak bash -c '/opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config --server http://localhost:8080/auth --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" && /opt/keycloak/bin/kcadm.sh update realms/plataforma --config /tmp/kcadm.config -s loginTheme=plataforma'
```
````

- [ ] **Step 7: Commit**

```bash
git add infra/keycloak/themes infra/keycloak/realm-plataforma.json infra/docker-compose.yml infra/smoke_test.py README.md
git commit -m "feat(infra): tema de inicio de sesión 'plataforma' en Keycloak con la identidad de la SPA"
```

---

### Task 11: Revisión en navegador, accesibilidad real y documentación

Esta tarea la ejecuta el controlador (necesita el panel de navegador). Lo que encuentre se corrige con prueba primero cuando sea comprobable en jsdom.

**Files:**
- Create: `docs/qa/revision-visual-plan-a.md`
- Modify: `README.md` (sección "Interfaz"), `.gitignore` (`.claude/`)
- Modify: los archivos que requieran correcciones (cada corrección con su prueba cuando aplique)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: evidencia de la revisión (páginas × anchos × temas, resultados de axe en navegador real, ausencia de scroll horizontal, consola sin errores de CSP).

- [ ] **Step 1: Suite completa**

Run: `(cd web && npm run lint && npm run build && npm test -- --run)`
Expected: todo en verde, salida limpia. Anote el número de pruebas.

- [ ] **Step 2: Reconstruir el gateway y correr la prueba de humo**

Run: `docker compose -f infra/docker-compose.yml up -d --build --wait gateway`
Run: `uv run python infra/smoke_test.py` → Expected: `OK: …`

- [ ] **Step 3: Revisar la build de producción (gateway, con CSP)**

En el panel de navegador abra <http://localhost:8080>, inicie sesión con `comprador1` (contraseña en `infra/keycloak/realm-plataforma.json`; no la repita en el chat). En Tablero, Proveedores, detalle (las tres pestañas), Precios (con un servicio elegido), Ranking, Alertas y una ruta inexistente:
- `read_console_messages` con `onlyErrors: true` → Expected: sin errores de CSP (`tema.js`, fuentes, `<style>` de la gráfica) ni de JavaScript.
- Cambie el tema con el selector (Claro, Oscuro, Sistema) y recargue: no debe verse destello del tema equivocado.

- [ ] **Step 4: axe en navegador real y scroll horizontal**

Cree `.claude/launch.json` (el servidor de Vite reenvía `/api` al gateway y Keycloak acepta `http://localhost:5173` como redirección):

```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "web", "runtimeExecutable": "npm", "runtimeArgs": ["--prefix", "web", "run", "dev"], "port": 5173 }
  ]
}
```

Ábralo con `preview_start` (`name: "web"`) e inicie sesión con `comprador1`. En cada página del Step 3, en tema claro y oscuro, ejecute con `javascript_tool`:

```js
await new Promise((ok, mal) => {
  if (window.axe) return ok()
  const s = document.createElement("script")
  s.src = "/node_modules/axe-core/axe.min.js"
  s.onload = ok
  s.onerror = mal
  document.head.append(s)
})
const r = await axe.run(document, {
  runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
})
r.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.help}`)
```

Expected: `[]` en todas (aquí sí corre la regla de contraste). Con `resize_window` a 375, 768, 1024 y 1440 px, ejecute `document.documentElement.scrollWidth <= window.innerWidth` → Expected: `true` en todas; en 375 px el menú lateral es un panel deslizable que se cierra al elegir una opción. Vuelva a `preset: "desktop"` al terminar.

Importación y Configuración requieren `admin1` con OTP: si no puede iniciar sesión como admin, pida al residente que lo haga o registre que esas dos páginas quedan cubiertas por sus pruebas de jsdom.

- [ ] **Step 5: Corregir lo encontrado**

Para cada violación o defecto: si es comprobable en jsdom, primero la prueba que falla en el archivo de la página, luego la corrección; si es solo visual (contraste de un tinte, desbordamiento), corrija y vuelva a medir en el navegador. Un commit por corrección: `fix(web): …`.

- [ ] **Step 6: Documentar**

`docs/qa/revision-visual-plan-a.md`: fecha, commit revisado, tabla página × ancho × tema con el resultado de axe y del scroll horizontal, errores de consola encontrados y su corrección, y lo que no se pudo revisar (con motivo).

En `README.md`, después de "## Desarrollo", agregue:

```markdown
## Interfaz

- Sistema de diseño: tokens claro/oscuro en `web/src/index.css` (los componentes solo usan tokens;
  `npm run lint` rechaza colores literales y `src/tokens.node.test.ts` verifica el contraste WCAG).
- Tema claro, oscuro o del sistema desde la barra superior; la preferencia se guarda en el navegador.
- Fuentes Fira Sans y Fira Code servidas por la propia aplicación (sin CDN).
- Revisión de accesibilidad y diseño adaptable: `docs/qa/revision-visual-plan-a.md`.
```

En `.gitignore` agregue la línea `.claude/` (configuración local del editor y worktrees).

- [ ] **Step 7: Commit**

```bash
git add docs/qa/revision-visual-plan-a.md README.md .gitignore
git commit -m "docs(qa): revisión en navegador del Plan A (axe, temas y anchos de pantalla)"
```
