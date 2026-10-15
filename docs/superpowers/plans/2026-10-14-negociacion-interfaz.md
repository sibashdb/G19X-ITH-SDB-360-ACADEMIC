# Negociación en la interfaz (N1b) — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El comprador crea, configura, publica y supervisa negociaciones desde la web, y el proveedor negocia en `/portal` con su enlace. También se agregan «Renovar» en el Tablero, las Alertas y la ficha del proveedor, el glosario, la ayuda y la revisión en navegador.

**Architecture:** Solo cambia la web; el servicio `negociacion` (N1a, ya en `main`) no se toca.
- **Módulo común:** `web/src/negociacion.ts` copia los esquemas de la API y concentra el gancho `useNegociacion`, los nombres, los formatos, la explicación de la traza y las claves de idempotencia.
- **Páginas:** cada una es un archivo diferido en `web/src/rutas.tsx`. Los componentes que comparten van en `web/src/componentes/negociacion/`.
- **Portal:** es una ruta hermana de `marco`, así que no pasa por el `Layout` ni por el inicio de sesión. Su token vive en `web/src/portal.ts` y viaja solo como `Authorization: Invitacion <token>`.

**Tech Stack:** React 19 + TypeScript 6, Vite 8, Tailwind v4 con los tokens de `web/src/index.css`, shadcn/radix, TanStack Query 5, react-router 8, lucide-react; Vitest + Testing Library + axe-core.

**Spec:** `docs/superpowers/specs/2026-10-13-negociacion-determinista-design.md`.
- Las secciones que rigen este plan son §2 (N1b), §7 y §8 (las rutas que se consumen), §10 (interfaz), §14 (filas «Interfaz» y «Revisión en navegador») y §15 (el flujo que cierra N1b).
- El PRD padre es `docs/superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md`.

## Global Constraints

**Rama y entorno**
- Rama `feat/negociacion-interfaz`, creada desde `main` en `7faa0fd` (N1a ya integrada).
- Los comandos de la web se corren desde `web/`.
- Este plan **no cambia ningún servicio**. Si una tarea necesita algo que la API no da, se detiene y lo reporta.

**Contrato con el servicio**
- Los tipos de `web/src/negociacion.ts` copian `services/negociacion/src/negociacion/api/esquemas.py`; un campo nuevo en uno va en el otro.
- La web pide `pedir("/negociacion/…")`, porque `pedir` antepone `/api`.
- Toda consulta GET del comprador usa `useNegociacion(ruta)`, con la clave `["negociacion", ruta]`. Después de cualquier cambio se invalidan todas con `{ queryKey: ["negociacion"] }`.
- Montos, precios y valores de las palancas llegan y se envían como texto decimal y no se operan en el navegador.
  - Si un valor está dentro de los límites lo decide el servicio, nunca la web.
  - Solo se suman en la web los pesos, que son enteros.
- Las utilidades llegan de 0 a 1 y se muestran como porcentaje entero (`0.413` → `"41 %"`).

**Portal y seguridad**
- **El token del portal:**
  - llega en el fragmento (`/portal#t=<token>`);
  - se guarda en `sessionStorage` con la clave `portal-negociacion`, o en memoria si el navegador bloquea el almacenamiento;
  - se borra de la barra con `history.replaceState`;
  - solo viaja en `Authorization: Invitacion <token>` a `/api/negociacion/portal/…`;
  - nunca va a la consola, a otra ruta ni a la URL.
- **POST con `Idempotency-Key`:** el portal (ofertas y escalar) y las respuestas manuales del comprador la mandan, generada con `crypto.randomUUID()`.
  - Se reutiliza solo al reintentar el mismo cuerpo.
  - Si el cuerpo cambió o el envío ya se completó, la clave es nueva (`crearClaves()` de la Task 1).
- **Consultas periódicas:**
  - son `refetchInterval: 3000` en la supervisión (detalle de una negociación abierta y sesión) y en el portal cuando atiende una persona;
  - nunca corren en segundo plano;
  - un fallo de una consulta periódica no borra lo que ya se ve (`ContenidoVivo`, Task 1).

**Textos y formato**
- Español de México, de «usted». El primer término técnico de cada página va con `Termino`: palanca, ideal, límite, ronda, acuerdo tentativo, P25 · P50 · P75.
- El color nunca es la única señal: estados, validez, fuera de límites y total de pesos llevan icono y texto.
- Formatos:
  - montos con `formatoMoneda(valor, moneda)`;
  - fechas y horas con `formatoFecha` y `formatoFechaHora`;
  - tiempo relativo con `haceCuanto`;
  - utilidad con `formatoUtilidad`;
  - valor de una palanca con `formatoTermino` (Task 1).

**Accesibilidad**
- 0 violaciones de axe en cada página nueva, en claro y oscuro (`esperarSinViolaciones`).
- En el navegador se revisa con la regla de contraste, a 375, 768, 1024 y 1440 px y sin desplazamiento horizontal (Task 11).
- Un botón que no aplica en ese momento pero puede tener el foco usa `aria-disabled` y una guarda en su manejador, no `disabled`.
- Foco: `outline-hidden`, nunca `outline-none`. Cuando un botón desaparece al usarse, el foco pasa a un control que siga en pantalla.
- Mensajes de «se guardó / se envió»: un `<p role="status">` que existe siempre, vacío mientras no hay aviso.

**Dependencias**
- No se agregan dependencias.
- `web/src/components/ui/textarea.tsx` es el archivo de shadcn: usa `radix-ui` y `cn`, ya instalados.

**Seguridad de credenciales**
- Nunca escriba contraseñas ni secretos en comandos, archivos versionados o reportes; `infra/.env` no se versiona.
- Las contraseñas de desarrollo están en `infra/keycloak/realm-plataforma.json`; no las repita.
- No haga `git push` ni toque los remotos.

**Calidad**
- Cada tarea deja limpios, desde `web/`: `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check "src/**/*.{ts,tsx}"`.
- Las pruebas no dejan warnings: ni `act(...)` ni `act` de React Query.
- No se editan planes ni bitácoras anteriores (`docs/superpowers/plans/*` de otras ramas, `docs/qa/bitacora-*`).

**Commits**
- Conventional Commits en español.
- Mensaje: asunto, una línea en blanco y la línea `Co-Authored-By: Claude <modelo que escribió el commit> 5.5 <noreply@anthropic.com>` (dos `-m`).
- Verifique con `git log -1 --format=%B`.
- No haga commit de `infra/.env`, `datos/`, `web/node_modules`, `web/dist`, `.superpowers/` ni PDFs.

## Review Focus

1. **El token del portal se filtra o se pierde.**
   - Después de abrir el enlace, el token no queda en la barra ni en el historial.
   - Recargar la pestaña sigue funcionando.
   - Un enlace nuevo en la misma pestaña reemplaza al anterior.
   - Sin token, o con uno inválido o vencido, se ve la misma pantalla «El enlace no es válido o ya venció», sin pistas de cuál caso es.
   - Pruebas: Task 8 (`toma el token del fragmento, lo guarda y lo quita de la barra`, `sin token no consulta y explica que el enlace no sirve` y `un 401 muestra la misma pantalla`).
2. **Doble clic, o un reintento tras un corte de red, crea dos ofertas o dos respuestas.**
   - El botón queda en `aria-disabled` mientras se envía.
   - El reintento del mismo cuerpo lleva la misma `Idempotency-Key`; una oferta distinta o posterior lleva otra.
   - Pruebas: Task 1 (`crearClaves`), Task 8 (`reintentar el mismo envío reutiliza la clave y una oferta nueva usa otra`) y Task 7 (`responde a mano con una contraoferta y manda Idempotency-Key`).
3. **Dos compradores editan el mismo borrador.**
   - El 409 `version_desactualizada` se explica con «Recargar», que descarta los cambios locales y muestra los del otro.
   - Publicar con cambios sin guardar no publica una versión vieja: «Publicar» espera a que se guarde.
   - Pruebas: Task 4 (`un 409 de versión ofrece recargar y descarta lo local` y `no deja publicar con cambios sin guardar ni con errores`).
4. **La consulta cada 3 s anuncia de más o borra la pantalla.**
   - Solo se anuncia un mensaje nuevo del proveedor, nunca los que ya estaban al abrir.
   - Si una consulta periódica falla, la conversación sigue a la vista con un aviso.
   - Pruebas: Task 1 (`ContenidoVivo conserva los datos si una actualización falla`) y Task 6 (`solo anuncia los mensajes del proveedor que llegan después de abrir`).
5. **Parámetros inválidos en la URL.** Ninguno llega al servicio como valor raro.
   - En la lista, `?estado=hackeo` y `?pagina=abc` se ignoran.
   - En «Nueva negociación», `?proveedor=abc` abre una compra normal.
   - Un contrato que no está entre los del proveedor explica que no se puede renovar.
   - Pruebas: Task 2 (`ignora filtros inválidos de la URL`) y Task 3 (`parámetros de renovación inválidos abren una compra` y `un contrato que no es del proveedor no se puede renovar`).

## Tareas

Se ejecutan en orden; cada una deja el repositorio verde.

| # | Tarea | Archivos principales |
|---|---|---|
| 1 | Cimientos: tipos, consulta, formatos, claves, glosario y menú | `negociacion.ts`, `fechas.ts`, `glosario.ts`, `componentes/navegacion.ts`, `componentes/negociacion/ContenidoVivo.tsx`, `components/ui/textarea.tsx` |
| 2 | Lista de negociaciones | `paginas/Negociaciones.tsx`, `componentes/negociacion/Etiquetas.tsx`, `rutas.tsx` |
| 3 | Nueva negociación: compra y renovación | `paginas/NegociacionNueva.tsx`, `componentes/negociacion/SelectorProveedores.tsx` |
| 4 | Detalle: editor del borrador, publicación con enlaces y cancelación | `paginas/Negociacion.tsx`, `componentes/negociacion/{EditorBorrador,ResumenConfiguracion,BandaReferencia,DialogoEnlaces,DialogoCancelar}.tsx` |
| 5 | Detalle abierto: sesiones, reenvío y cancelación | `componentes/negociacion/TablaSesiones.tsx`, `paginas/Negociacion.tsx` |
| 6 | Supervisión de una sesión | `paginas/SesionNegociacion.tsx`, `componentes/negociacion/{Conversacion,TablaOfertas}.tsx` |
| 7 | Respuesta manual del comprador | `componentes/negociacion/{RespuestaManual,CamposValores}.tsx` |
| 8 | Portal del proveedor | `portal.ts`, `paginas/Portal.tsx`, `rutas.tsx`, `componentes/BarraSuperior.tsx` |
| 9 | «Renovar» en el Tablero, las Alertas y la ficha del proveedor | `paginas/Tablero.tsx`, `componentes/ElementoAlerta.tsx`, `componentes/TablaContratos.tsx`, `paginas/ProveedorDetalle.tsx` |
| 10 | Ayuda, guía de uso y README | `ayuda.ts`, `guia.ts`, `componentes/GuiaUso.tsx`, `componentes/Layout.tsx`, `README.md` |
| 11 | Revisión en navegador y documentación | `docs/qa/revision-negociacion.md`, `README.md` |

**Fuera de alcance** (se registran aquí para que nadie los dé por hechos):
- **Cambiar líneas o proveedores de un borrador ya creado.** La API lo permite, pero la spec (§10.1) pide un editor de límites. Para cambiarlos se cancela el borrador y se crea otro; el editor lo dice en pantalla.
- **Adjudicación, aprobación y recomendación:** incremento 4. La IA, la interpretación de la nota y el agente con historial: N2.
- **`ReferenciaPrecio` en el editor.** Ese componente consulta la referencia **actual** con su propio formulario. El editor debe mostrar la **foto** guardada en el evento (spec D5), así que usa `BandaReferencia`, que solo presenta P25/P50/P75 con el mismo formato.
- **Interruptor (`switch`) para activar una palanca.** Se usa la `Checkbox` que ya existe, con la etiqueta «Negociar <palanca>». Tiene el mismo comportamiento accesible y no agrega un componente.
- **`pedir` con otro encabezado de autorización.** No cambia: ya respeta un `Authorization` que llegue en `init.headers` cuando no recibe token. `pedirPortal` (Task 8) lo usa así.

---

### Task 1: Cimientos: tipos, consulta, formatos, claves, glosario y menú

**Files:**
- Create: `web/src/negociacion.ts`
- Create: `web/src/negociacion.test.ts`
- Create: `web/src/componentes/negociacion/ContenidoVivo.tsx`
- Create: `web/src/componentes/negociacion/ContenidoVivo.test.tsx`
- Create: `web/src/components/ui/textarea.tsx`
- Modify: `web/src/fechas.ts`, `web/src/fechas.test.ts`
- Modify: `web/src/glosario.ts`
- Modify: `web/src/componentes/navegacion.ts`, `web/src/componentes/navegacion.test.ts`

**Interfaces:**
- Consumes:
  - `pedir` de `@/api` y `useToken` de `@/auth`;
  - `formatoDecimal` y `porUnidad` de `@/inteligencia`;
  - `formatoMoneda` de `@/tipos`;
  - `EstadoCarga` y `EstadoError` de `@/componentes/Estados`.
- Produces:
  - **Tipos** (`@/negociacion`): `TipoEvento`, `EstadoEvento`, `EstadoSesion`, `Modo`, `Estilo`, `ClavePalanca`, `Autor`, `EstadoCorreo`, `Banda`, `LineaEvento`, `PalancaEvento`, `Problema`, `SesionResumen`, `Evento`, `EventoResumen`, `PaginaEventos`, `EnlaceInvitacion`, `Publicacion`, `Valores`, `AccionAgente`, `Decision`, `MensajeSesion`, `OfertaSesion`, `LineaSesion`, `PalancaSesion`, `SesionDetalle`, `LineaPortal`, `PalancaPortal`, `MensajePortal`, `VistaPortal`.
  - **Nombres y constantes:** `NOMBRES_TIPO`, `NOMBRES_ESTADO_EVENTO`, `NOMBRES_ESTADO_SESION`, `NOMBRES_AUTOR`, `ESTILOS`, `PASOS: Record<ClavePalanca, string>`.
  - **Funciones:**
    - `esFinal(estado: EstadoSesion): boolean`;
    - `useNegociacion<T>(ruta, opciones?)`;
    - `formatoUtilidad(u: number | null): string`;
    - `formatoTermino(valor: string, unidad: string, moneda: string): string`;
    - `explicarDecision(d: Decision): string`;
    - `rutaRenovacion(proveedorId: string, contratoId: string): string`;
    - `esUuid(valor: string | null): valor is string`;
    - `sugerirFechaLimite(ahora?: Date): Date`;
    - `crearClaves(): { para(cuerpo: string): string; olvidar(): void }`.
  - **De `@/fechas`:**
    - `aEntradaFechaHora(fecha: Date): string`;
    - `desdeEntradaFechaHora(valor: string): string | null`;
    - `hoyEnMexico(ahora?: Date): string`.
  - **Componentes:**
    - `ContenidoVivo` (`@/componentes/negociacion/ContenidoVivo`);
    - `Textarea` (`@/components/ui/textarea`).
  - **Claves del glosario:** `palanca`, `ideal`, `limite`, `ronda`, `acuerdoTentativo`.
  - **Menú:** la sección «Negociación» con «Negociaciones» (`/negociaciones`, icono `Handshake`). `migasDe("/negociaciones/nueva")` termina en «Nueva».

- [ ] **Step 1: Write the failing tests**

`web/src/negociacion.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest"
import {
  crearClaves,
  esFinal,
  esUuid,
  explicarDecision,
  formatoTermino,
  formatoUtilidad,
  rutaRenovacion,
  sugerirFechaLimite,
  type Decision,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

afterEach(() => {
  vi.restoreAllMocks()
})

const BASE: Decision = {
  accion: "contraofertar",
  t: 2,
  T: 6,
  utilidad_oferta: 0.413,
  valida: false,
  hay_mejor_oferta: false,
  objetivo: 0.49,
  utilidad_contraoferta: 0.492,
}

describe("explicarDecision", () => {
  it("explica una contraoferta con lo que vale la oferta y lo que busca el agente", () => {
    expect(explicarDecision(BASE)).toBe(
      "La oferta del proveedor vale 41 % para usted; en esta ronda (2 de 6) el agente busca al menos 49 %, así que propuso valores que valen 49 % para usted. La oferta cruzaba al menos uno de sus límites."
    )
  })

  it("menciona la presión competitiva y la última oferta sin dar cifras de otros", () => {
    const texto = explicarDecision({
      ...BASE,
      t: 5,
      valida: true,
      hay_mejor_oferta: true,
    })
    expect(texto).toContain(
      "Mencionó que hay propuestas más competitivas, sin decir de quién ni cuánto."
    )
    expect(texto).toContain("Pidió la mejor y última oferta.")
    expect(texto).not.toContain("cruzaba")
  })

  it("explica la aceptación, el cierre sin acuerdo y la aclaración", () => {
    expect(
      explicarDecision({
        ...BASE,
        accion: "aceptar",
        valida: true,
        utilidad_oferta: 0.52,
      })
    ).toBe(
      "La oferta del proveedor vale 52 % para usted, respeta sus límites y alcanza lo que el agente pediría en esta ronda (49 %), así que la aceptó como acuerdo tentativo."
    )
    expect(explicarDecision({ ...BASE, accion: "cerrar_sin_acuerdo", t: 6 })).toBe(
      "Era la última ronda (6 de 6) y la oferta cruzaba al menos uno de sus límites, así que el agente cerró sin acuerdo."
    )
    expect(explicarDecision({ ...BASE, accion: "pedir_aclaracion" })).toBe(
      "Algún precio de la oferta quedó muy lejos de lo usual (menos de la décima parte o más de 10 veces la referencia de precio o, si no hay referencia, el límite), así que el agente pidió al proveedor confirmarlo. Esta respuesta no cuenta como ronda."
    )
  })
})

describe("formatos", () => {
  it("la utilidad va como porcentaje entero, y sin oferta como raya", () => {
    expect(formatoUtilidad(0.413)).toBe("41 %")
    expect(formatoUtilidad(1)).toBe("100 %")
    expect(formatoUtilidad(null)).toBe("—")
  })

  it("el valor de una palanca lleva su unidad, o el formato de moneda", () => {
    expect(formatoTermino("45", "días", "MXN")).toBe("45 días")
    expect(formatoTermino("99.5", "%", "MXN")).toBe("99.5 %")
    expect(formatoTermino("15000.00", "MXN", "MXN")).toBe(
      formatoMoneda("15000.00", "MXN")
    )
  })
})

describe("utilidades", () => {
  it("sabe qué estados de sesión son finales", () => {
    expect(esFinal("acuerdo_tentativo")).toBe(true)
    expect(esFinal("sin_acuerdo")).toBe(true)
    expect(esFinal("expirada")).toBe(true)
    expect(esFinal("escalada")).toBe(false)
    expect(esFinal("activa")).toBe(false)
  })

  it("arma la ruta de renovación con los parámetros codificados", () => {
    expect(rutaRenovacion("p 1", "c/2")).toBe(
      "/negociaciones/nueva?proveedor=p+1&contrato=c%2F2"
    )
  })

  it("reconoce un UUID y rechaza lo demás", () => {
    expect(esUuid("5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42")).toBe(true)
    expect(esUuid("abc")).toBe(false)
    expect(esUuid(null)).toBe(false)
  })

  it("sugiere la fecha límite a una semana, a las 18:00", () => {
    expect(sugerirFechaLimite(new Date(2026, 9, 14, 10, 30))).toEqual(
      new Date(2026, 9, 21, 18, 0)
    )
  })
})

describe("crearClaves", () => {
  it("reutiliza la clave al reintentar el mismo cuerpo y usa otra si cambia o ya se completó", () => {
    vi.spyOn(crypto, "randomUUID")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000001")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000002")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000003")
    const claves = crearClaves()
    expect(claves.para('{"a":1}')).toBe("00000000-0000-4000-8000-000000000001")
    expect(claves.para('{"a":1}')).toBe("00000000-0000-4000-8000-000000000001")
    expect(claves.para('{"a":2}')).toBe("00000000-0000-4000-8000-000000000002")
    claves.olvidar()
    expect(claves.para('{"a":2}')).toBe("00000000-0000-4000-8000-000000000003")
  })
})
```

`web/src/componentes/negociacion/ContenidoVivo.test.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"
import { ContenidoVivo } from "@/componentes/negociacion/ContenidoVivo"
import { renderizarPagina } from "@/pruebas/utilidades"

afterEach(() => {
  cleanup()
})

describe("ContenidoVivo", () => {
  it("conserva los datos si una actualización falla y lo avisa", async () => {
    let llamadas = 0
    function Vista() {
      const consulta = useQuery({
        queryKey: ["vivo"],
        queryFn: async () => {
          llamadas += 1
          if (llamadas > 1) throw new Error("caída")
          return "Hola"
        },
      })
      return (
        <>
          <button onClick={() => void consulta.refetch()}>Actualizar</button>
          <ContenidoVivo consulta={consulta}>{(d) => <p>{d}</p>}</ContenidoVivo>
        </>
      )
    }
    renderizarPagina(<Vista />)
    expect(await screen.findByText("Hola")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Actualizar" }))
    expect(
      await screen.findByText(
        "No se pudo actualizar; se volverá a intentar en unos segundos."
      )
    ).toHaveAttribute("role", "status")
    expect(screen.getByText("Hola")).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Reintentar" })
    ).not.toBeInTheDocument()
  })

  it("si nunca cargó, muestra el error con Reintentar", async () => {
    function Vista() {
      const consulta = useQuery({
        queryKey: ["vivo-error"],
        queryFn: async (): Promise<string> => {
          throw new Error("caída")
        },
      })
      return (
        <ContenidoVivo consulta={consulta}>{(d) => <p>{d}</p>}</ContenidoVivo>
      )
    }
    renderizarPagina(<Vista />)
    expect(
      await screen.findByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
    expect(screen.getByText("caída")).toBeInTheDocument()
  })
})
```

En `web/src/fechas.test.ts`, cambie el import por:

```ts
import {
  aEntradaFechaHora,
  desdeEntradaFechaHora,
  formatoFechaHora,
  haceCuanto,
  hoyEnMexico,
} from "@/fechas"
```

y agregue al final:

```ts
describe("campos de fecha y hora", () => {
  it("da el valor de un datetime-local en la hora del navegador", () => {
    expect(aEntradaFechaHora(new Date(2026, 9, 21, 18, 5))).toBe(
      "2026-10-21T18:05"
    )
  })

  it("convierte el valor del campo a un instante ISO, o null si no sirve", () => {
    expect(desdeEntradaFechaHora("2026-10-21T18:00")).toBe(
      new Date(2026, 9, 21, 18, 0).toISOString()
    )
    expect(desdeEntradaFechaHora("")).toBeNull()
    expect(desdeEntradaFechaHora("mañana")).toBeNull()
  })

  it("da la fecha de hoy en la Ciudad de México", () => {
    // 05:30 UTC del 8 = 23:30 del 7 en la Ciudad de México.
    expect(hoyEnMexico(new Date("2026-10-08T05:30:00Z"))).toBe("2026-10-07")
  })
})
```

En `web/src/componentes/navegacion.test.ts`:

1. **Las listas de títulos.** En las dos listas de `titulos(["comprador"])` y `titulos([])`, agregue `"Negociaciones",` después de `"Alertas",`.
2. **Las secciones del admin.** En «muestra todo al admin, agrupado por sección», la lista de secciones pasa a ser:

```ts
    expect(secciones.map((s) => s.titulo)).toEqual([
      "Resumen",
      "Proveedores",
      "Inteligencia",
      "Negociación",
      "Sistema",
      "Soporte",
    ])
```

3. **Las migas de pan.** En la tabla de `migasDe`, agregue estas filas después de la de `"/precios"`:

```ts
    [
      "/negociaciones",
      [{ titulo: "Negociación" }, { titulo: "Negociaciones" }],
    ],
    [
      "/negociaciones/nueva",
      [
        { titulo: "Negociación" },
        { titulo: "Negociaciones", ruta: "/negociaciones" },
        { titulo: "Nueva" },
      ],
    ],
    [
      "/negociaciones/abc/sesiones/def",
      [
        { titulo: "Negociación" },
        { titulo: "Negociaciones", ruta: "/negociaciones" },
        { titulo: "Detalle" },
      ],
    ],
```

4. **Las descripciones.** En «cada elemento dice para qué sirve», agregue después de `Alertas: "Qué atender hoy",`:

```ts
      Negociaciones: "Negociar con proveedores dentro de sus límites",
```

- [ ] **Step 2: Run tests to verify they fail**

Run (desde `web/`): `npx vitest run src/negociacion.test.ts src/fechas.test.ts src/componentes/navegacion.test.ts src/componentes/negociacion/ContenidoVivo.test.tsx`
Expected: FAIL. `negociacion.test.ts` y `ContenidoVivo.test.tsx` no encuentran sus módulos; `fechas.test.ts` no encuentra `aEntradaFechaHora`; `navegacion.test.ts` no encuentra «Negociaciones».

- [ ] **Step 3: Write the implementation**

`web/src/negociacion.ts`:

```ts
import {
  useQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { formatoDecimal } from "@/inteligencia"
import { formatoMoneda } from "@/tipos"

// Tipos de services/negociacion/src/negociacion/api/esquemas.py: un campo nuevo va en los dos.
// Montos, precios y valores llegan como texto decimal; las utilidades, como número de 0 a 1.

export type TipoEvento = "compra" | "renovacion"
export type EstadoEvento = "borrador" | "abierto" | "en_evaluacion" | "cancelado"
export type EstadoSesion =
  | "invitada"
  | "activa"
  | "acuerdo_tentativo"
  | "sin_acuerdo"
  | "expirada"
  | "escalada"
export type Modo = "agente" | "comprador"
export type Estilo = "firme" | "balanceado" | "flexible"
export type ClavePalanca =
  | "precio"
  | "plazo_meses"
  | "plazo_pago_dias"
  | "sla_disponibilidad"
  | "tope_aumento_pct"
  | "cuota_implementacion"
export type Autor = "proveedor" | "agente" | "comprador" | "sistema"
export type EstadoCorreo = "pendiente" | "enviado" | "fallido"

export type Banda = {
  p25: string
  p50: string
  p75: string
  metodo: string
  confianza: string
  observaciones: number
}
export type LineaEvento = {
  id: string
  orden: number
  codigo_servicio: string
  nombre: string
  unidad: string
  cantidad: string
  precio_vigente: string | null
  ideal: string | null
  limite: string | null
  referencia: Banda | null
}
export type PalancaEvento = {
  clave: ClavePalanca
  nombre: string
  unidad: string
  activa: boolean
  peso: number
  ideal: string | null
  limite: string | null
  vigente: string | null
}
export type Problema = { campo: string; mensaje: string }
export type SesionResumen = {
  id: string
  proveedor_id: string
  proveedor_nombre: string
  estado: EstadoSesion
  modo: Modo
  ronda: number
  utilidad: number | null
  correo_estado: EstadoCorreo
  correo_error: string | null
  fuera_de_limites: boolean
  actualizado_en: string
}
export type Evento = {
  id: string
  folio: string
  tipo: TipoEvento
  titulo: string
  moneda: string
  plazo_meses: number
  estado: EstadoEvento
  fecha_limite: string
  rondas_max: number
  estilo: Estilo
  contrato_origen_id: string | null
  proveedor_vigente_id: string | null
  invitados: { id: string; nombre: string }[]
  lineas: LineaEvento[]
  palancas: PalancaEvento[]
  referencia_fecha: string | null
  creado_por_nombre: string
  creado_en: string
  publicado_en: string | null
  cerrado_en: string | null
  motivo_cancelacion: string | null
  version: number
  errores: Problema[]
  avisos: Problema[]
  sesiones: SesionResumen[]
}
export type EventoResumen = {
  id: string
  folio: string
  tipo: TipoEvento
  titulo: string
  estado: EstadoEvento
  fecha_limite: string
  invitados: number
  sesiones: number
  acuerdos: number
  escaladas: number
  creado_por_nombre: string
  creado_en: string
}
export type PaginaEventos = { total: number; elementos: EventoResumen[] }
export type EnlaceInvitacion = {
  sesion_id: string
  proveedor_nombre: string
  destinatario: string
  enlace: string
  correo_estado: EstadoCorreo
}
export type Publicacion = { evento: Evento; enlaces: EnlaceInvitacion[] }
export type Valores = {
  precios: Record<string, string>
  palancas: Record<string, string>
}
export type AccionAgente =
  | "aceptar"
  | "contraofertar"
  | "cerrar_sin_acuerdo"
  | "pedir_aclaracion"
/** La traza del motor (spec §6.6); aquí solo los campos que la interfaz explica. */
export type Decision = {
  accion: AccionAgente
  t: number
  T: number
  utilidad_oferta: number
  valida: boolean
  hay_mejor_oferta: boolean
  objetivo?: number
  utilidad_contraoferta?: number
}
export type MensajeSesion = {
  id: string
  autor: Autor
  texto: string
  ronda: number
  fecha: string
  oferta_id: string | null
  decision: Decision | null
}
export type OfertaSesion = {
  id: string
  autor: Exclude<Autor, "sistema">
  ronda: number
  valores: Valores
  utilidad: number
  valida: boolean
  fuera_de_limites_confirmada: boolean
  fecha: string
}
export type LineaSesion = {
  id: string
  nombre: string
  unidad: string
  cantidad: string
  ideal: string | null
  limite: string | null
}
export type PalancaSesion = {
  clave: ClavePalanca
  nombre: string
  unidad: string
  peso: number
  ideal: string | null
  limite: string | null
}
export type SesionDetalle = {
  id: string
  evento_id: string
  folio: string
  titulo: string
  moneda: string
  proveedor_id: string
  proveedor_nombre: string
  destinatario: string
  estado: EstadoSesion
  modo: Modo
  ronda: number
  rondas_max: number
  fuera_de_limites: boolean
  correo_estado: EstadoCorreo
  correo_error: string | null
  lineas: LineaSesion[]
  palancas: PalancaSesion[]
  mensajes: MensajeSesion[]
  ofertas: OfertaSesion[]
}
export type LineaPortal = {
  id: string
  codigo_servicio: string
  nombre: string
  unidad: string
  cantidad: string
}
export type PalancaPortal = {
  clave: ClavePalanca
  nombre: string
  unidad: string
}
export type MensajePortal = {
  autor: Autor
  texto: string
  ronda: number
  fecha: string
  oferta: Valores | null
}
export type VistaPortal = {
  folio: string
  titulo: string
  moneda: string
  fecha_limite: string
  rondas_max: number
  rondas_restantes: number
  estado: EstadoSesion
  atendido_por: "agente" | "persona"
  pide_confirmacion: boolean
  lineas: LineaPortal[]
  palancas: PalancaPortal[]
  mensajes: MensajePortal[]
  ultima_propuesta: Valores | null
}

export const NOMBRES_TIPO: Record<TipoEvento, string> = {
  compra: "Compra",
  renovacion: "Renovación",
}

export const NOMBRES_ESTADO_EVENTO: Record<EstadoEvento, string> = {
  borrador: "Borrador",
  abierto: "Abierta",
  en_evaluacion: "En evaluación",
  cancelado: "Cancelada",
}

export const NOMBRES_ESTADO_SESION: Record<EstadoSesion, string> = {
  invitada: "Invitada",
  activa: "Activa",
  acuerdo_tentativo: "Acuerdo tentativo",
  sin_acuerdo: "Sin acuerdo",
  expirada: "Expirada",
  escalada: "Escalada",
}

export const NOMBRES_AUTOR: Record<Autor, string> = {
  proveedor: "Proveedor",
  agente: "Agente",
  comprador: "Compras",
  sistema: "Sistema",
}

export const ESTILOS: { clave: Estilo; nombre: string; descripcion: string }[] =
  [
    {
      clave: "firme",
      nombre: "Firme",
      descripcion:
        "Cede poco y tarde: busca el mejor valor aunque tome más rondas.",
    },
    {
      clave: "balanceado",
      nombre: "Balanceado",
      descripcion: "Cede de forma pareja a lo largo de las rondas.",
    },
    {
      clave: "flexible",
      nombre: "Flexible",
      descripcion: "Cede pronto: prioriza llegar a un acuerdo.",
    },
  ]

/** Paso de cada término en los campos numéricos: la precisión de la spec §6.4. */
export const PASOS: Record<ClavePalanca, string> = {
  precio: "0.01",
  plazo_meses: "1",
  plazo_pago_dias: "1",
  sla_disponibilidad: "0.01",
  tope_aumento_pct: "0.1",
  cuota_implementacion: "0.01",
}

const FINALES: readonly EstadoSesion[] = [
  "acuerdo_tentativo",
  "sin_acuerdo",
  "expirada",
]

/** Acuerdo, sin acuerdo o expirada: ya no recibe ofertas. «Escalada» no es final. */
export function esFinal(estado: EstadoSesion): boolean {
  return FINALES.includes(estado)
}

type OpcionesConsulta<T> = Omit<
  UseQueryOptions<T, Error, T>,
  "queryKey" | "queryFn" | "enabled"
> & { enabled?: boolean }

/** GET a /api/negociacion{ruta}. La clave común ["negociacion", …] permite invalidarlas juntas. */
export function useNegociacion<T>(
  ruta: string,
  opciones: OpcionesConsulta<T> = {}
): UseQueryResult<T, Error> {
  const token = useToken()
  const queryKey: QueryKey = ["negociacion", ruta]
  return useQuery({
    ...opciones,
    queryKey,
    queryFn: () => pedir<T>(`/negociacion${ruta}`, token),
    enabled: Boolean(token) && (opciones.enabled ?? true),
  })
}

/** Qué tan buena es una oferta para el comprador: "41 %"; sin oferta, "—". */
export function formatoUtilidad(utilidad: number | null): string {
  return utilidad === null ? "—" : `${Math.round(utilidad * 100)} %`
}

/** Un valor de palanca con su unidad; los montos (unidad = moneda), con el formato de moneda. */
export function formatoTermino(
  valor: string,
  unidad: string,
  moneda: string
): string {
  if (unidad === moneda) return formatoMoneda(valor, moneda)
  // Solo presentación: el valor exacto no se opera en el navegador.
  return `${formatoDecimal(Number(valor), 2)} ${unidad}`
}

/** La traza del motor en palabras, para «¿Por qué respondió esto?». */
export function explicarDecision(d: Decision): string {
  const vale = `La oferta del proveedor vale ${formatoUtilidad(d.utilidad_oferta)} para usted`
  switch (d.accion) {
    case "pedir_aclaracion":
      return "Algún precio de la oferta quedó muy lejos de lo usual (menos de la décima parte o más de 10 veces la referencia de precio o, si no hay referencia, el límite), así que el agente pidió al proveedor confirmarlo. Esta respuesta no cuenta como ronda."
    case "aceptar":
      return `${vale}, respeta sus límites y alcanza lo que el agente pediría en esta ronda (${formatoUtilidad(d.utilidad_contraoferta ?? 0)}), así que la aceptó como acuerdo tentativo.`
    case "cerrar_sin_acuerdo":
      return `Era la última ronda (${d.t} de ${d.T}) y la oferta cruzaba al menos uno de sus límites, así que el agente cerró sin acuerdo.`
    case "contraofertar": {
      const partes = [
        `${vale}; en esta ronda (${d.t} de ${d.T}) el agente busca al menos ${formatoUtilidad(d.objetivo ?? 0)}, así que propuso valores que valen ${formatoUtilidad(d.utilidad_contraoferta ?? 0)} para usted.`,
      ]
      if (!d.valida) partes.push("La oferta cruzaba al menos uno de sus límites.")
      if (d.hay_mejor_oferta)
        partes.push(
          "Mencionó que hay propuestas más competitivas, sin decir de quién ni cuánto."
        )
      if (d.t + 1 === d.T) partes.push("Pidió la mejor y última oferta.")
      return partes.join(" ")
    }
  }
}

/** Página para renovar un contrato vigente (spec §10.1, botón «Renovar»). */
export function rutaRenovacion(proveedorId: string, contratoId: string): string {
  return `/negociaciones/nueva?${new URLSearchParams({
    proveedor: proveedorId,
    contrato: contratoId,
  })}`
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Solo un UUID llega a la API como id (la URL se puede editar a mano). */
export function esUuid(valor: string | null): valor is string {
  return valor !== null && UUID.test(valor)
}

/** Fecha límite sugerida: dentro de una semana, a las 18:00 (hora del navegador). */
export function sugerirFechaLimite(ahora: Date = new Date()): Date {
  const fecha = new Date(ahora)
  fecha.setDate(fecha.getDate() + 7)
  fecha.setHours(18, 0, 0, 0)
  return fecha
}

/**
 * Claves de `Idempotency-Key`: la misma al reintentar el mismo cuerpo (un corte de red no duplica
 * la oferta) y otra si el cuerpo cambió o el envío anterior ya se completó.
 */
export function crearClaves() {
  let ultimo: { cuerpo: string; clave: string } | null = null
  return {
    para(cuerpo: string): string {
      if (!ultimo || ultimo.cuerpo !== cuerpo)
        ultimo = { cuerpo, clave: crypto.randomUUID() }
      return ultimo.clave
    },
    olvidar(): void {
      ultimo = null
    },
  }
}
```

`web/src/componentes/negociacion/ContenidoVivo.tsx`:

```tsx
import type { UseQueryResult } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { EstadoCarga, EstadoError } from "@/componentes/Estados"

/**
 * Como ContenidoConsulta, para pantallas que se actualizan solas cada pocos segundos: si una
 * actualización falla, lo que ya se veía se queda en pantalla con un aviso, en vez del error.
 */
export function ContenidoVivo<T>({
  consulta,
  children,
}: {
  consulta: UseQueryResult<T>
  children: (datos: T) => ReactNode
}) {
  if (consulta.isPending) return <EstadoCarga />
  if (consulta.isLoadingError) {
    return (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  return (
    <>
      <p
        role="status"
        className={consulta.isRefetchError ? "text-sm text-warning" : "sr-only"}
      >
        {consulta.isRefetchError
          ? "No se pudo actualizar; se volverá a intentar en unos segundos."
          : ""}
      </p>
      {children(consulta.data)}
    </>
  )
}
```

`web/src/components/ui/textarea.tsx` (el de shadcn, con `outline-hidden`):

```tsx
import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-base outline-hidden transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
```

En `web/src/fechas.ts`, agregue al final:

```ts
const dosDigitos = (n: number) => String(n).padStart(2, "0")

/** "2026-10-21T18:00" en la hora del navegador, para un <input type="datetime-local">. */
export function aEntradaFechaHora(fecha: Date): string {
  return `${fecha.getFullYear()}-${dosDigitos(fecha.getMonth() + 1)}-${dosDigitos(fecha.getDate())}T${dosDigitos(fecha.getHours())}:${dosDigitos(fecha.getMinutes())}`
}

/** El valor de un <input type="datetime-local"> como instante ISO; null si está vacío o no sirve. */
export function desdeEntradaFechaHora(valor: string): string | null {
  const fecha = new Date(valor)
  return valor && !Number.isNaN(fecha.getTime()) ? fecha.toISOString() : null
}

/** Hoy en la Ciudad de México, "AAAA-MM-DD", para compararlo con las fechas de los contratos. */
export function hoyEnMexico(ahora: Date = new Date()): string {
  return ahora.toLocaleDateString("en-CA", { timeZone: ZONA })
}
```

En `web/src/glosario.ts`, agregue antes del cierre `} as const satisfies …`:

```ts
  palanca: {
    termino: "Palanca",
    definicion:
      "Un término del contrato que se negocia además del precio: plazo, plazo de pago, SLA, tope de aumento o cuota de implementación. Usted elige cuáles se negocian y cuánto pesa cada uno.",
  },
  ideal: {
    termino: "Ideal",
    definicion:
      "El valor que a usted le gustaría conseguir. El agente empieza pidiéndolo y cede poco a poco hacia el límite.",
  },
  limite: {
    termino: "Límite",
    definicion:
      "El peor valor que usted acepta. El agente nunca acuerda algo que lo cruce y nunca se lo muestra al proveedor.",
  },
  ronda: {
    termino: "Ronda",
    definicion:
      "Cada oferta del proveedor con la respuesta del agente. En la última ronda, el agente acepta si la oferta respeta sus límites o cierra sin acuerdo.",
  },
  acuerdoTentativo: {
    termino: "Acuerdo tentativo",
    definicion:
      "El proveedor y el agente coincidieron dentro de sus límites. No es vinculante hasta que se adjudique y se apruebe.",
  },
```

En `web/src/componentes/navegacion.ts`:

1. Agregue `Handshake,` a los iconos importados de `lucide-react`, en orden alfabético después de `Gauge,`.
2. Inserte esta sección en `NAVEGACION`, entre la de «Inteligencia» y la de «Sistema»:

```ts
  {
    titulo: "Negociación",
    elementos: [
      {
        titulo: "Negociaciones",
        ruta: "/negociaciones",
        descripcion: "Negociar con proveedores dentro de sus límites",
        icono: Handshake,
      },
    ],
  },
```

3. En `migasDe`, reemplace el bloque `if (ruta !== elemento.ruta) { … }` por:

```ts
  if (ruta !== elemento.ruta) {
    // La única subruta con nombre propio es la de crear (/negociaciones/nueva).
    const titulo = ruta === `${elemento.ruta}/nueva` ? "Nueva" : "Detalle"
    return [
      ...migas,
      { titulo: elemento.titulo, ruta: elemento.ruta },
      { titulo },
    ]
  }
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/negociacion.test.ts src/fechas.test.ts src/componentes/navegacion.test.ts src/componentes/negociacion/ContenidoVivo.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.
- Si otra prueba enumera el menú, actualícela agregando «Negociaciones» y dígalo en su reporte. Por ejemplo `componentes/Layout.test.tsx` o una de la barra lateral.
- Si prettier pide formato, corra `npx prettier --write` sobre los archivos de esta tarea.

- [ ] **Step 5: Commit**

```bash
git add web/src/negociacion.ts web/src/negociacion.test.ts web/src/componentes/negociacion web/src/components/ui/textarea.tsx web/src/fechas.ts web/src/fechas.test.ts web/src/glosario.ts web/src/componentes/navegacion.ts web/src/componentes/navegacion.test.ts
git commit -m "feat(web): cimientos de la negociación: tipos, consulta, formatos, claves y menú" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Lista de negociaciones

**Files:**
- Create: `web/src/componentes/negociacion/Etiquetas.tsx`
- Create: `web/src/paginas/Negociaciones.tsx`
- Create: `web/src/paginas/Negociaciones.test.tsx`
- Modify: `web/src/rutas.tsx`

**Interfaces:**
- Consumes:
  - de la Task 1: `useNegociacion`, `NOMBRES_ESTADO_EVENTO`, `NOMBRES_ESTADO_SESION`, `NOMBRES_TIPO`, `EstadoEvento`, `EstadoSesion`, `TipoEvento` y `PaginaEventos`;
  - lo que ya existe: `Filtro`, `Paginacion`, `EncabezadoPagina`, `EstadoCarga`, `EstadoError`, `EstadoVacio`, `useParametros`, `unoDe` y `enteroPositivo`.
- Produces:
  - `EtiquetaEstadoEvento({ estado })` y `EtiquetaEstadoSesion({ estado })` (`@/componentes/negociacion/Etiquetas`), que usan las Tasks 4, 5 y 6;
  - la página `Negociaciones` en `/negociaciones`.
- API: `GET /negociacion/eventos?pagina=&tamano=25[&estado=][&tipo=]` → `PaginaEventos`.

- [ ] **Step 1: Write the failing test**

`web/src/paginas/Negociaciones.test.tsx`:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Negociaciones } from "@/paginas/Negociaciones"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ID = "5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42"
const PAGINA = {
  total: 1,
  elementos: [
    {
      id: ID,
      folio: "NEG-2026-0001",
      tipo: "compra",
      titulo: "Licencias de correo 2027",
      estado: "abierto",
      fecha_limite: "2026-10-21T23:00:00Z",
      invitados: 3,
      sesiones: 3,
      acuerdos: 2,
      escaladas: 1,
      creado_por_nombre: "Ana López",
      creado_en: "2026-10-14T18:00:00Z",
    },
  ],
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Negociaciones", () => {
  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("lista las negociaciones con su estado, sus acuerdos y las escaladas", async () => {
    simularApi(() => respuestaJson(PAGINA))
    const { container } = renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones",
    })
    expect(
      await screen.findByRole("link", { name: "NEG-2026-0001" })
    ).toHaveAttribute("href", `/negociaciones/${ID}`)
    const tabla = screen.getByRole("table")
    expect(within(tabla).getByText("Licencias de correo 2027")).toBeInTheDocument()
    expect(within(tabla).getByText("Compra")).toBeInTheDocument()
    expect(within(tabla).getByText("Abierta")).toBeInTheDocument()
    expect(within(tabla).getByText("2 de 3")).toBeInTheDocument()
    expect(within(tabla).getByText("1 escalada")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("solo el comprador ve «Nueva negociación»", async () => {
    simularApi(() => respuestaJson(PAGINA))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(
      await screen.findByRole("link", { name: "Nueva negociación" })
    ).toHaveAttribute("href", "/negociaciones/nueva")
    cleanup()
    sesionDePrueba.roles = ["aprobador"]
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    expect(
      screen.queryByRole("link", { name: "Nueva negociación" })
    ).not.toBeInTheDocument()
  })

  it("los filtros van a la URL y a la consulta, y vuelven a la primera página", async () => {
    const api = simularApi(() => respuestaJson(PAGINA))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones?pagina=2" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    const estados = screen.getByRole("group", { name: "Estado" })
    await userEvent.click(within(estados).getByRole("button", { name: "Abierta" }))
    expect(ubicacionActual()).toBe("/negociaciones?estado=abierto")
    await waitFor(() =>
      expect(urlDeLlamada(api).searchParams.get("estado")).toBe("abierto")
    )
    expect(urlDeLlamada(api).searchParams.get("pagina")).toBe("1")
    expect(
      within(estados).getByRole("button", { name: "Abierta" })
    ).toHaveAttribute("aria-pressed", "true")
  })

  it("ignora filtros inválidos de la URL", async () => {
    const api = simularApi(() => respuestaJson(PAGINA))
    renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones?estado=hackeo&tipo=x&pagina=abc",
    })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    const url = urlDeLlamada(api)
    expect(url.pathname).toBe("/api/negociacion/eventos")
    expect(url.searchParams.get("estado")).toBeNull()
    expect(url.searchParams.get("tipo")).toBeNull()
    expect(url.searchParams.get("pagina")).toBe("1")
    expect(url.searchParams.get("tamano")).toBe("25")
  })

  it("sin negociaciones lo explica, y con filtros ofrece quitarlos", async () => {
    simularApi(() => respuestaJson({ total: 0, elementos: [] }))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(
      await screen.findByText("Aún no hay negociaciones")
    ).toBeInTheDocument()
    cleanup()
    renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones?tipo=renovacion",
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Quitar filtros" })
    )
    expect(ubicacionActual()).toBe("/negociaciones")
  })

  it("una página fuera de rango ofrece volver a la primera", async () => {
    simularApi(() => respuestaJson({ total: 3, elementos: [] }))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones?pagina=9" })
    await userEvent.click(
      await screen.findByRole("button", { name: "Ir a la primera página" })
    )
    expect(ubicacionActual()).toBe("/negociaciones")
  })

  it("si el servicio no responde, lo dice y permite reintentar", async () => {
    simularApi(() =>
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail: "El servicio no está disponible; intente más tarde.",
        },
        503
      )
    )
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(
      await screen.findByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (desde `web/`): `npx vitest run src/paginas/Negociaciones.test.tsx`
Expected: FAIL con `Failed to resolve import "@/paginas/Negociaciones"`.

- [ ] **Step 3: Write the implementation**

`web/src/componentes/negociacion/Etiquetas.tsx`:

```tsx
import {
  Ban,
  CircleCheck,
  CircleOff,
  Clock,
  Hand,
  Handshake,
  Hourglass,
  Mail,
  MessagesSquare,
  PencilLine,
  type LucideIcon,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  NOMBRES_ESTADO_EVENTO,
  NOMBRES_ESTADO_SESION,
  type EstadoEvento,
  type EstadoSesion,
} from "@/negociacion"

type Variante = "secondary" | "success" | "warning" | "outline"

const DE_EVENTO: Record<EstadoEvento, [LucideIcon, Variante]> = {
  borrador: [PencilLine, "outline"],
  abierto: [CircleCheck, "success"],
  en_evaluacion: [Hourglass, "secondary"],
  cancelado: [Ban, "outline"],
}

const DE_SESION: Record<EstadoSesion, [LucideIcon, Variante]> = {
  invitada: [Mail, "outline"],
  activa: [MessagesSquare, "secondary"],
  escalada: [Hand, "warning"],
  acuerdo_tentativo: [Handshake, "success"],
  sin_acuerdo: [CircleOff, "outline"],
  expirada: [Clock, "outline"],
}

/** Estado de una negociación con icono y texto: el color no es la única señal. */
export function EtiquetaEstadoEvento({ estado }: { estado: EstadoEvento }) {
  const [Icono, variante] = DE_EVENTO[estado]
  return (
    <Badge variant={variante}>
      <Icono aria-hidden />
      {NOMBRES_ESTADO_EVENTO[estado]}
    </Badge>
  )
}

/** Estado de la sesión con un proveedor, con icono y texto. */
export function EtiquetaEstadoSesion({ estado }: { estado: EstadoSesion }) {
  const [Icono, variante] = DE_SESION[estado]
  return (
    <Badge variant={variante}>
      <Icono aria-hidden />
      {NOMBRES_ESTADO_SESION[estado]}
    </Badge>
  )
}
```

`web/src/paginas/Negociaciones.tsx`:

```tsx
import { keepPreviousData } from "@tanstack/react-query"
import { Handshake, Plus, TriangleAlert, X } from "lucide-react"
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Filtro } from "@/componentes/Filtro"
import { Paginacion } from "@/componentes/Paginacion"
import { EtiquetaEstadoEvento } from "@/componentes/negociacion/Etiquetas"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import {
  NOMBRES_ESTADO_EVENTO,
  NOMBRES_TIPO,
  useNegociacion,
  type EstadoEvento,
  type PaginaEventos,
  type TipoEvento,
} from "@/negociacion"
import { enteroPositivo, unoDe, useParametros } from "@/parametros"

const POR_PAGINA = 25
const ESTADOS = Object.keys(NOMBRES_ESTADO_EVENTO) as EstadoEvento[]
const TIPOS = Object.keys(NOMBRES_TIPO) as TipoEvento[]

export function Negociaciones() {
  const esComprador = useRoles().includes("comprador")
  const [parametros, actualizar] = useParametros()
  // Los valores de la URL se validan: uno inválido cuenta como "sin filtro" y no llega a la API.
  const estado = unoDe(parametros.get("estado"), ESTADOS)
  const tipo = unoDe(parametros.get("tipo"), TIPOS)
  const pagina = enteroPositivo(parametros.get("pagina"), 1, 1000)
  const busqueda = new URLSearchParams({
    pagina: String(pagina),
    tamano: String(POR_PAGINA),
  })
  if (estado) busqueda.set("estado", estado)
  if (tipo) busqueda.set("tipo", tipo)
  const consulta = useNegociacion<PaginaEventos>(`/eventos?${busqueda}`, {
    placeholderData: keepPreviousData,
  })
  const nueva = esComprador ? (
    <Button asChild>
      <Link to="/negociaciones/nueva">
        <Plus aria-hidden />
        Nueva negociación
      </Link>
    </Button>
  ) : undefined

  function contenido() {
    if (consulta.isPending) return <EstadoCarga />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (total > 0 && elementos.length === 0) {
      return (
        <EstadoVacio
          titulo="Esta página ya no existe"
          descripcion="La lista cambió y ya no llega hasta aquí."
          accion={
            <Button variant="outline" onClick={() => actualizar({ pagina: null })}>
              Ir a la primera página
            </Button>
          }
        />
      )
    }
    if (total === 0) {
      return estado || tipo ? (
        <EstadoVacio
          icono={Handshake}
          titulo="Ninguna negociación con estos filtros"
          descripcion="Pruebe con otro estado o con otro tipo."
          accion={
            <Button
              variant="outline"
              onClick={() => actualizar({ estado: null, tipo: null, pagina: null })}
            >
              <X aria-hidden />
              Quitar filtros
            </Button>
          }
        />
      ) : (
        <EstadoVacio
          icono={Handshake}
          titulo="Aún no hay negociaciones"
          descripcion={
            esComprador
              ? "Cree la primera con «Nueva negociación»: elija los servicios, invite a los proveedores y fije sus límites."
              : "Aquí aparecerán las negociaciones que cree el equipo de compras."
          }
        />
      )
    }
    return (
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Folio</TableHead>
              <TableHead>Título</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acuerdos</TableHead>
              <TableHead>Fecha límite</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {elementos.map((e) => (
              <TableRow key={e.id}>
                <TableCell>
                  <Link
                    to={`/negociaciones/${encodeURIComponent(e.id)}`}
                    className="font-mono text-accent hover:underline"
                  >
                    {e.folio}
                  </Link>
                </TableCell>
                <TableCell className="min-w-48 whitespace-normal">
                  {e.titulo}
                </TableCell>
                <TableCell>{NOMBRES_TIPO[e.tipo]}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    <EtiquetaEstadoEvento estado={e.estado} />
                    {e.escaladas > 0 && (
                      <Badge variant="warning">
                        <TriangleAlert aria-hidden />
                        {e.escaladas === 1
                          ? "1 escalada"
                          : `${e.escaladas} escaladas`}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {`${e.acuerdos} de ${e.invitados}`}
                </TableCell>
                <TableCell>{formatoFechaHora(e.fecha_limite)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Paginacion
          pagina={pagina}
          total={total}
          porPagina={POR_PAGINA}
          nombre="negociaciones"
          alCambiar={(p) => actualizar({ pagina: p === 1 ? null : String(p) })}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <EncabezadoPagina
        titulo="Negociaciones"
        descripcion="Un agente negocia por usted con cada proveedor, dentro de los límites que usted fije."
        acciones={nueva}
      />
      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-4">
            <div role="group" aria-label="Estado" className="flex flex-wrap gap-2">
              <Filtro
                activo={!estado}
                onClick={() => actualizar({ estado: null, pagina: null })}
              >
                Todas
              </Filtro>
              {ESTADOS.map((e) => (
                <Filtro
                  key={e}
                  activo={estado === e}
                  onClick={() => actualizar({ estado: e, pagina: null })}
                >
                  {NOMBRES_ESTADO_EVENTO[e]}
                </Filtro>
              ))}
            </div>
            <div role="group" aria-label="Tipo" className="flex flex-wrap gap-2">
              <Filtro
                activo={!tipo}
                onClick={() => actualizar({ tipo: null, pagina: null })}
              >
                Todos los tipos
              </Filtro>
              {TIPOS.map((t) => (
                <Filtro
                  key={t}
                  activo={tipo === t}
                  onClick={() => actualizar({ tipo: t, pagina: null })}
                >
                  {NOMBRES_TIPO[t]}
                </Filtro>
              ))}
            </div>
          </div>
          {contenido()}
        </CardContent>
      </Card>
    </div>
  )
}
```

En `web/src/rutas.tsx`, agregue después de la ruta `alertas`:

```tsx
  {
    path: "negociaciones",
    lazy: async () => ({
      Component: (await import("@/paginas/Negociaciones")).Negociaciones,
    }),
  },
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/paginas/Negociaciones.test.tsx src/rutas.test.ts`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/componentes/negociacion/Etiquetas.tsx web/src/paginas/Negociaciones.tsx web/src/paginas/Negociaciones.test.tsx web/src/rutas.tsx
git commit -m "feat(web): lista de negociaciones con filtros por estado y tipo" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Nueva negociación: compra y renovación

**Files:**
- Create: `web/src/componentes/negociacion/Campo.tsx`
- Create: `web/src/componentes/negociacion/SelectorProveedores.tsx`
- Create: `web/src/paginas/NegociacionNueva.tsx`
- Create: `web/src/paginas/NegociacionNueva.test.tsx`
- Modify: `web/src/pruebas/utilidades.tsx` (agrega `llamadaA`)
- Modify: `web/src/rutas.tsx`

**Interfaces:**
- Consumes:
  - de la Task 1: `esUuid`, `sugerirFechaLimite`, `ESTILOS`, `Estilo`, `Evento`, `aEntradaFechaHora` y `desdeEntradaFechaHora`;
  - de `@/tipos`: `Servicio`, `Contrato`, `ProveedorDetalle`, `PaginaProveedores`, `ProveedorResumen`, `NOMBRES_CATEGORIA`, `formatoFecha` y `formatoMoneda`;
  - de `@/inteligencia`: `porUnidad`.
- Produces:
  - `Campo({ id, etiqueta, ayuda?, error?, children: (control: PropsControl) => ReactNode })` y `type PropsControl` (`@/componentes/negociacion/Campo`). Lo usan las Tasks 4, 7 y 8.
  - `SelectorProveedores({ elegidos, alCambiar, error? })` y `type Invitado = { id: string; nombre: string }`.
  - `llamadaA(simulado, url, metodo?): { cuerpo: unknown; cabeceras: Headers }` (`@/pruebas/utilidades`): la última llamada a esa URL, con ese método si se indica. La usan las Tasks 4 a 8.
  - La página `NegociacionNueva` en `/negociaciones/nueva`. Con `?proveedor=<uuid>&contrato=<uuid>` es una renovación.
- API:
  - `GET /proveedores/servicios` (los activos) → `Servicio[]`;
  - `GET /proveedores/proveedores?activo=true&limite=50&desplazamiento=0[&q=]` → `PaginaProveedores`;
  - `GET /proveedores/proveedores/{id}` y `GET /proveedores/proveedores/{id}/contratos`;
  - `POST /negociacion/eventos` → 201 con `Evento`. Un 422 trae `errores` por campo; un 503 dice que la referencia de precios no respondió.

- [ ] **Step 1: Write the failing test**

En `web/src/pruebas/utilidades.tsx`, agregue después de `urlDeLlamada`:

```tsx
/**
 * La última llamada a fetch simulada con esa URL exacta (y ese método, si se indica): su cuerpo
 * JSON y sus cabeceras. Sin método en `init`, la llamada cuenta como GET.
 */
export function llamadaA(
  simulado: { mock: { calls: unknown[][] } },
  url: string,
  metodo?: string
): { cuerpo: unknown; cabeceras: Headers } {
  const llamada = simulado.mock.calls.findLast(
    ([u, init]) =>
      u === url &&
      (!metodo || ((init as RequestInit | undefined)?.method ?? "GET") === metodo)
  )
  if (!llamada) throw new Error(`No hubo ninguna llamada ${metodo ?? ""} a ${url}`)
  const init = (llamada[1] ?? {}) as RequestInit
  return {
    cuerpo: init.body ? JSON.parse(String(init.body)) : undefined,
    cabeceras: new Headers(init.headers),
  }
}
```

`web/src/paginas/NegociacionNueva.test.tsx`:

```tsx
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { NegociacionNueva } from "@/paginas/NegociacionNueva"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
  urlDeLlamada,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const NUBE_NORTE = "11111111-1111-4111-8111-111111111111"
const DATOS_SUR = "22222222-2222-4222-8222-222222222222"
const CREADO = "33333333-3333-4333-8333-333333333333"
const CONTRATO = "44444444-4444-4444-8444-444444444444"

const SERVICIOS = [
  {
    id: "s1",
    codigo: "LIC-CORREO",
    nombre: "Correo en la nube",
    categoria: "licencia_saas",
    unidad: "usuario_mes",
    moneda: "MXN",
    activo: true,
    tiene_contratos: true,
  },
]

const PROVEEDORES = {
  total: 2,
  elementos: [
    {
      id: NUBE_NORTE,
      rfc: "NNO010101AAA",
      nombre: "Nube Norte",
      tamano: "mediana",
      categorias: ["licencia_saas"],
      activo: true,
    },
    {
      id: DATOS_SUR,
      rfc: "DSU010101AAA",
      nombre: "Datos del Sur",
      tamano: "pequena",
      categorias: ["nube"],
      activo: true,
    },
  ],
}

const DETALLE = {
  ...PROVEEDORES.elementos[0],
  contacto_nombre: "Lucía Pérez",
  contacto_email: "lucia@nubenorte.example",
  contratos_vigentes: 1,
}

const CONTRATO_VIGENTE = {
  id: CONTRATO,
  folio: "C-001101",
  tipo: "nuevo",
  fecha_inicio: "2025-11-01",
  fecha_fin: "2026-10-31",
  moneda: "MXN",
  plazo_pago_dias: 30,
  sla_disponibilidad: "99.50",
  tope_aumento_pct: "5.0",
  cuota_implementacion: "0.00",
  lineas: [
    {
      codigo_servicio: "LIC-CORREO",
      nombre_servicio: "Correo en la nube",
      unidad: "usuario_mes",
      cantidad: "250",
      precio_unitario: "95.0000",
    },
  ],
}

function apiDeCompra(
  creacion: () => Response = () => respuestaJson({ id: CREADO }, 201)
) {
  return simularApi((url) => {
    if (url === "/api/proveedores/servicios") return respuestaJson(SERVICIOS)
    if (url.startsWith("/api/proveedores/proveedores?"))
      return respuestaJson(PROVEEDORES)
    if (url === "/api/negociacion/eventos") return creacion()
    return new Response("", { status: 404 })
  })
}

function apiDeRenovacion(contratos: unknown[] = [CONTRATO_VIGENTE]) {
  return simularApi({
    [`/api/proveedores/proveedores/${NUBE_NORTE}`]: () => respuestaJson(DETALLE),
    [`/api/proveedores/proveedores/${NUBE_NORTE}/contratos`]: () =>
      respuestaJson(contratos),
    "/api/negociacion/eventos": () => respuestaJson({ id: CREADO }, 201),
  })
}

async function capturarCompra() {
  await userEvent.type(
    await screen.findByLabelText("Título"),
    "Licencias de correo 2027"
  )
  await userEvent.click(
    await screen.findByRole("combobox", { name: "Servicio 1" })
  )
  await userEvent.click(
    await screen.findByRole("option", { name: "Correo en la nube (MXN)" })
  )
  await userEvent.type(screen.getByLabelText("Cantidad 1"), "250")
  await userEvent.click(
    await screen.findByRole("checkbox", { name: /Nube Norte/ })
  )
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("NegociacionNueva", () => {
  it("crea una compra con sus servicios y proveedores y lleva a su editor", async () => {
    const api = apiDeCompra()
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    await capturarCompra()
    await userEvent.click(screen.getByRole("button", { name: "Crear borrador" }))
    await waitFor(() =>
      expect(ubicacionActual()).toBe(`/negociaciones/${CREADO}`)
    )
    const { cuerpo } = llamadaA(api, "/api/negociacion/eventos")
    expect(cuerpo).toMatchObject({
      tipo: "compra",
      titulo: "Licencias de correo 2027",
      rondas_max: 6,
      estilo: "balanceado",
      plazo_meses: 12,
      lineas: [{ codigo_servicio: "LIC-CORREO", cantidad: "250" }],
      proveedores: [NUBE_NORTE],
    })
    expect((cuerpo as { fecha_limite: string }).fecha_limite).toMatch(/Z$/)
  })

  it("muestra junto a cada campo el error del servicio, y en el aviso los demás", async () => {
    apiDeCompra(() =>
      respuestaJson(
        {
          title: "Solicitud inválida",
          detail: "Revise los campos indicados.",
          codigo: "invalido",
          errores: [
            { campo: "lineas.0.cantidad", mensaje: "Debe ser mayor que 0." },
            { campo: "body", mensaje: "Un proveedor aparece dos veces." },
          ],
        },
        422
      )
    )
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    await capturarCompra()
    await userEvent.click(screen.getByRole("button", { name: "Crear borrador" }))
    expect(await screen.findByText("Debe ser mayor que 0.")).toBeInTheDocument()
    expect(screen.getByLabelText("Cantidad 1")).toHaveAttribute(
      "aria-invalid",
      "true"
    )
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Un proveedor aparece dos veces."
    )
  })

  it("si la referencia de precios no responde, lo dice y conserva lo capturado", async () => {
    apiDeCompra(() =>
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail: "No se pudo consultar la referencia de precios; intente de nuevo.",
          codigo: "dependencia_no_disponible",
        },
        503
      )
    )
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    await capturarCompra()
    await userEvent.click(screen.getByRole("button", { name: "Crear borrador" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo consultar la referencia de precios; intente de nuevo."
    )
    expect(screen.getByLabelText("Título")).toHaveValue(
      "Licencias de correo 2027"
    )
  })

  it("agrega y quita servicios, y al quitar deja el foco en «Agregar servicio»", async () => {
    apiDeCompra()
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    await userEvent.click(
      await screen.findByRole("button", { name: "Agregar servicio" })
    )
    expect(
      screen.getByRole("combobox", { name: "Servicio 2" })
    ).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("button", { name: "Quitar el servicio 2" })
    )
    expect(
      screen.queryByRole("combobox", { name: "Servicio 2" })
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Agregar servicio" })
    ).toHaveFocus()
  })

  it("busca proveedores activos por nombre y muestra a los elegidos", async () => {
    const api = apiDeCompra()
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    await userEvent.type(
      await screen.findByLabelText("Buscar proveedor"),
      "Datos"
    )
    await waitFor(() =>
      expect(urlDeLlamada(api).searchParams.get("q")).toBe("Datos")
    )
    expect(urlDeLlamada(api).searchParams.get("activo")).toBe("true")
    await userEvent.click(
      await screen.findByRole("checkbox", { name: /Datos del Sur/ })
    )
    expect(screen.getByText("1 de 10 proveedores elegidos")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Quitar a Datos del Sur" })
    ).toBeInTheDocument()
  })

  it("renueva un contrato con sus datos, sin pedir servicios ni proveedores", async () => {
    const api = apiDeRenovacion()
    renderizarPagina(<NegociacionNueva />, {
      ruta: `/negociaciones/nueva?proveedor=${NUBE_NORTE}&contrato=${CONTRATO}`,
    })
    expect(
      screen.getByRole("heading", { name: "Renovar un contrato" })
    ).toBeInTheDocument()
    expect(await screen.findByLabelText("Título")).toHaveValue(
      "Renovación C-001101"
    )
    expect(screen.getByText("Correo en la nube")).toBeInTheDocument()
    expect(
      screen.queryByRole("combobox", { name: "Servicio 1" })
    ).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Crear borrador" }))
    await waitFor(() =>
      expect(ubicacionActual()).toBe(`/negociaciones/${CREADO}`)
    )
    const { cuerpo } = llamadaA(api, "/api/negociacion/eventos")
    expect(cuerpo).toMatchObject({
      tipo: "renovacion",
      titulo: "Renovación C-001101",
      proveedor_id: NUBE_NORTE,
      contrato_id: CONTRATO,
    })
    expect(cuerpo).not.toHaveProperty("lineas")
  })

  it("un contrato que no es del proveedor no se puede renovar", async () => {
    apiDeRenovacion([])
    renderizarPagina(<NegociacionNueva />, {
      ruta: `/negociaciones/nueva?proveedor=${NUBE_NORTE}&contrato=${CONTRATO}`,
    })
    expect(
      await screen.findByText("No se puede renovar este contrato")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Crear una compra nueva" })
    ).toHaveAttribute("href", "/negociaciones/nueva")
  })

  it("parámetros de renovación inválidos abren una compra", async () => {
    apiDeCompra()
    renderizarPagina(<NegociacionNueva />, {
      ruta: "/negociaciones/nueva?proveedor=abc&contrato=1",
    })
    expect(
      screen.getByRole("heading", { name: "Nueva negociación" })
    ).toBeInTheDocument()
    expect(
      await screen.findByRole("combobox", { name: "Servicio 1" })
    ).toBeInTheDocument()
  })

  it("solo el comprador puede crear negociaciones", () => {
    sesionDePrueba.roles = ["aprobador"]
    apiDeCompra()
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    apiDeCompra()
    const { container } = renderizarPagina(<NegociacionNueva />, {
      ruta: "/negociaciones/nueva",
    })
    await screen.findByRole("checkbox", { name: /Nube Norte/ })
    await esperarSinViolaciones(container)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (desde `web/`): `npx vitest run src/paginas/NegociacionNueva.test.tsx`
Expected: FAIL con `Failed to resolve import "@/paginas/NegociacionNueva"`.

- [ ] **Step 3: Write the implementation**

`web/src/componentes/negociacion/Campo.tsx`:

```tsx
import type { ReactNode } from "react"
import { Label } from "@/components/ui/label"

export type PropsControl = {
  id: string
  "aria-invalid"?: true
  "aria-describedby"?: string
}

/** Etiqueta, control, ayuda y error de un campo; el control recibe el id y los aria-* que los enlazan. */
export function Campo({
  id,
  etiqueta,
  ayuda,
  error,
  children,
}: {
  id: string
  etiqueta: ReactNode
  ayuda?: ReactNode
  error?: string
  children: (control: PropsControl) => ReactNode
}) {
  const idAyuda = ayuda ? `${id}-ayuda` : undefined
  const idError = error ? `${id}-error` : undefined
  const descritoPor = [idAyuda, idError].filter(Boolean).join(" ") || undefined
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>{etiqueta}</Label>
      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": descritoPor,
      })}
      {ayuda && (
        <p id={idAyuda} className="text-sm text-muted-foreground">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={idError} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
```

`web/src/componentes/negociacion/SelectorProveedores.tsx`:

```tsx
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { X } from "lucide-react"
import { useDeferredValue, useId, useState } from "react"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { EstadoCarga, EstadoError } from "@/componentes/Estados"
import { Campo } from "@/componentes/negociacion/Campo"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  NOMBRES_CATEGORIA,
  type PaginaProveedores,
  type ProveedorResumen,
} from "@/tipos"

export type Invitado = { id: string; nombre: string }

const MAXIMO = 10 // los que acepta la API (spec §5.1)

/** Busca proveedores activos y elige de 1 a 10; los elegidos se ven aunque cambie la búsqueda. */
export function SelectorProveedores({
  elegidos,
  alCambiar,
  error,
}: {
  elegidos: Invitado[]
  alCambiar: (elegidos: Invitado[]) => void
  error?: string
}) {
  const token = useToken()
  const id = useId()
  const [busqueda, setBusqueda] = useState("")
  const texto = useDeferredValue(busqueda.trim())
  const parametros = new URLSearchParams({
    activo: "true",
    limite: "50",
    desplazamiento: "0",
  })
  if (texto) parametros.set("q", texto)
  const consulta = useQuery({
    queryKey: ["proveedores", "invitables", texto],
    queryFn: () =>
      pedir<PaginaProveedores>(`/proveedores/proveedores?${parametros}`, token),
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
  })
  const lleno = elegidos.length >= MAXIMO

  function alternar(proveedor: ProveedorResumen, marcado: boolean) {
    alCambiar(
      marcado
        ? [...elegidos, { id: proveedor.id, nombre: proveedor.nombre }]
        : elegidos.filter((e) => e.id !== proveedor.id)
    )
  }

  function lista() {
    if (consulta.isPending) return <EstadoCarga filas={3} />
    if (consulta.isError) {
      return (
        <EstadoError
          error={consulta.error}
          alReintentar={() => void consulta.refetch()}
        />
      )
    }
    const { total, elementos } = consulta.data
    if (elementos.length === 0) {
      return (
        <p className="text-sm text-muted-foreground">
          Ningún proveedor activo coincide con la búsqueda.
        </p>
      )
    }
    return (
      <fieldset className="space-y-2">
        <legend className="sr-only">Proveedores para invitar</legend>
        <ul className="max-h-72 space-y-2 overflow-y-auto rounded-lg border p-3">
          {elementos.map((p) => {
            const marcado = elegidos.some((e) => e.id === p.id)
            const idCasilla = `${id}-${p.id}`
            return (
              <li key={p.id} className="flex items-center gap-2">
                <Checkbox
                  id={idCasilla}
                  checked={marcado}
                  disabled={!marcado && lleno}
                  onCheckedChange={(valor) => alternar(p, valor === true)}
                />
                <Label htmlFor={idCasilla} className="font-normal">
                  {p.nombre}
                  <span className="text-muted-foreground">
                    {" · "}
                    {p.categorias.map((c) => NOMBRES_CATEGORIA[c]).join(", ")}
                  </span>
                </Label>
              </li>
            )
          })}
        </ul>
        {total > elementos.length && (
          <p className="text-sm text-muted-foreground">
            Hay más proveedores: escriba parte del nombre para encontrarlos.
          </p>
        )}
      </fieldset>
    )
  }

  return (
    <div className="space-y-3">
      <Campo
        id={`${id}-buscar`}
        etiqueta="Buscar proveedor"
        ayuda="Por nombre o RFC; solo aparecen los proveedores activos."
      >
        {(control) => (
          <Input
            {...control}
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        )}
      </Campo>
      <p aria-live="polite" className="text-sm text-muted-foreground">
        {`${elegidos.length} de ${MAXIMO} proveedores elegidos`}
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {elegidos.length > 0 && (
        <ul aria-label="Proveedores elegidos" className="flex flex-wrap gap-2">
          {elegidos.map((e) => (
            <li key={e.id}>
              <Badge variant="secondary" className="gap-1">
                {e.nombre}
                <button
                  type="button"
                  aria-label={`Quitar a ${e.nombre}`}
                  className="rounded-sm outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => alCambiar(elegidos.filter((x) => x.id !== e.id))}
                >
                  <X aria-hidden className="size-3" />
                </button>
              </Badge>
            </li>
          ))}
        </ul>
      )}
      {lista()}
    </div>
  )
}
```

`web/src/paginas/NegociacionNueva.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleAlert, Plus, X } from "lucide-react"
import { useId, useRef, useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { enviarJson, ErrorApi, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { RequiereRol } from "@/componentes/RequiereRol"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { Campo } from "@/componentes/negociacion/Campo"
import {
  SelectorProveedores,
  type Invitado,
} from "@/componentes/negociacion/SelectorProveedores"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { aEntradaFechaHora, desdeEntradaFechaHora } from "@/fechas"
import { porUnidad } from "@/inteligencia"
import {
  ESTILOS,
  esUuid,
  sugerirFechaLimite,
  type Estilo,
  type Evento,
} from "@/negociacion"
import {
  formatoFecha,
  formatoMoneda,
  type Contrato,
  type ProveedorDetalle,
  type Servicio,
} from "@/tipos"

const MAXIMO_LINEAS = 20 // las que acepta la API (spec §5.1)
// Errores que se muestran junto a su campo; cualquier otro va en el aviso de arriba del botón.
const CAMPO_PROPIO =
  /^(titulo|fecha_limite|rondas_max|estilo|plazo_meses|proveedores|lineas\.\d+\.(codigo_servicio|cantidad))$/

type Renovacion = { proveedor: ProveedorDetalle; contrato: Contrato }
type LineaCaptura = { clave: number; codigo: string; cantidad: string }

export function NegociacionNueva() {
  return (
    <RequiereRol rol="comprador">
      <Contenido />
    </RequiereRol>
  )
}

function Contenido() {
  const [parametros] = useSearchParams()
  const proveedor = parametros.get("proveedor")
  const contrato = parametros.get("contrato")
  // Ids inválidos en la URL abren una compra normal: nunca llegan a la API.
  const renovar = esUuid(proveedor) && esUuid(contrato)
  return (
    <div className="space-y-6">
      <EncabezadoPagina
        titulo={renovar ? "Renovar un contrato" : "Nueva negociación"}
        descripcion={
          renovar
            ? "El agente negociará la renovación con el proveedor actual."
            : "Elija qué se compra y a quién invitar; los límites se fijan en el siguiente paso."
        }
      />
      {esUuid(proveedor) && esUuid(contrato) ? (
        <CargarRenovacion proveedorId={proveedor} contratoId={contrato} />
      ) : (
        <Formulario renovacion={null} />
      )}
    </div>
  )
}

function CargarRenovacion({
  proveedorId,
  contratoId,
}: {
  proveedorId: string
  contratoId: string
}) {
  const token = useToken()
  const ruta = `/proveedores/proveedores/${encodeURIComponent(proveedorId)}`
  const detalle = useQuery({
    queryKey: ["proveedor", proveedorId],
    queryFn: () => pedir<ProveedorDetalle>(ruta, token),
    enabled: Boolean(token),
  })
  const contratos = useQuery({
    queryKey: ["proveedor", proveedorId, "contratos"],
    queryFn: () => pedir<Contrato[]>(`${ruta}/contratos`, token),
    enabled: Boolean(token),
  })
  if (detalle.isPending || contratos.isPending) return <EstadoCarga />
  if (detalle.isError) {
    return (
      <EstadoError
        error={detalle.error}
        alReintentar={() => void detalle.refetch()}
      />
    )
  }
  if (contratos.isError) {
    return (
      <EstadoError
        error={contratos.error}
        alReintentar={() => void contratos.refetch()}
      />
    )
  }
  const contrato = contratos.data.find((c) => c.id === contratoId)
  if (!contrato) {
    return (
      <EstadoVacio
        titulo="No se puede renovar este contrato"
        descripcion={`${detalle.data.nombre} no tiene un contrato con ese identificador. Use «Renovar» desde el Tablero, las Alertas o la ficha del proveedor.`}
        accion={
          <Button asChild variant="outline">
            <Link to="/negociaciones/nueva">Crear una compra nueva</Link>
          </Button>
        }
      />
    )
  }
  return <Formulario renovacion={{ proveedor: detalle.data, contrato }} />
}

function ContratoRenovado({ renovacion }: { renovacion: Renovacion }) {
  const { proveedor, contrato } = renovacion
  return (
    <Seccion
      titulo="Contrato que se renueva"
      descripcion="Las líneas, la moneda y el plazo salen del contrato, y el único invitado es el proveedor actual."
    >
      <dl className="mb-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Proveedor</dt>
          <dd className="font-medium">{proveedor.nombre}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Contrato</dt>
          <dd className="font-mono">{contrato.folio}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Vigencia</dt>
          <dd>{`${formatoFecha(contrato.fecha_inicio)} – ${formatoFecha(contrato.fecha_fin)}`}</dd>
        </div>
      </dl>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Servicio</TableHead>
            <TableHead className="text-right">Cantidad</TableHead>
            <TableHead className="text-right">Precio vigente</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {contrato.lineas.map((l, i) => (
            // El índice evita claves repetidas: un contrato puede repetir un servicio.
            <TableRow key={`${l.codigo_servicio}-${i}`}>
              <TableCell className="whitespace-normal">{l.nombre_servicio}</TableCell>
              <TableCell className="text-right tabular-nums">
                {Number(l.cantidad).toLocaleString("es-MX")}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {`${formatoMoneda(l.precio_unitario, contrato.moneda)} ${porUnidad(l.unidad)}`}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Seccion>
  )
}

function Formulario({ renovacion }: { renovacion: Renovacion | null }) {
  const token = useToken()
  const cliente = useQueryClient()
  const navegar = useNavigate()
  const id = useId()
  const agregar = useRef<HTMLButtonElement>(null)
  const [titulo, setTitulo] = useState(
    renovacion ? `Renovación ${renovacion.contrato.folio}` : ""
  )
  const [fechaLimite, setFechaLimite] = useState(() =>
    aEntradaFechaHora(sugerirFechaLimite())
  )
  const [rondas, setRondas] = useState("6")
  const [estilo, setEstilo] = useState<Estilo>("balanceado")
  const [plazo, setPlazo] = useState("12")
  const [lineas, setLineas] = useState<LineaCaptura[]>([
    { clave: 1, codigo: "", cantidad: "" },
  ])
  const [invitados, setInvitados] = useState<Invitado[]>([])
  const catalogo = useQuery({
    queryKey: ["servicios", "activos"],
    queryFn: () => pedir<Servicio[]>("/proveedores/servicios", token),
    enabled: Boolean(token) && renovacion === null,
  })
  const crear = useMutation({
    mutationFn: (cuerpo: Record<string, unknown>) =>
      pedir<Evento>("/negociacion/eventos", token, enviarJson("POST", cuerpo)),
    onSuccess: async (evento) => {
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
      navegar(`/negociaciones/${encodeURIComponent(evento.id)}`)
    },
  })
  const errores = erroresPorCampo(crear.error)
  const generales = Object.entries(errores).filter(
    ([campo]) => !CAMPO_PROPIO.test(campo)
  )
  const estiloElegido = ESTILOS.find((e) => e.clave === estilo)

  function cambiarLinea(clave: number, cambio: Partial<LineaCaptura>) {
    setLineas((previas) =>
      previas.map((l) => (l.clave === clave ? { ...l, ...cambio } : l))
    )
  }

  function agregarLinea() {
    if (lineas.length >= MAXIMO_LINEAS) return
    setLineas((previas) => [
      ...previas,
      {
        clave: Math.max(...previas.map((l) => l.clave)) + 1,
        codigo: "",
        cantidad: "",
      },
    ])
  }

  function quitarLinea(clave: number) {
    if (lineas.length === 1) return
    setLineas((previas) => previas.filter((l) => l.clave !== clave))
    // El botón «Quitar» desaparece con su fila: el foco pasa a «Agregar servicio».
    agregar.current?.focus()
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (crear.isPending) return
    const comun = {
      titulo,
      fecha_limite: desdeEntradaFechaHora(fechaLimite),
      rondas_max: Number(rondas),
      estilo,
    }
    crear.mutate(
      renovacion
        ? {
            ...comun,
            tipo: "renovacion",
            proveedor_id: renovacion.proveedor.id,
            contrato_id: renovacion.contrato.id,
          }
        : {
            ...comun,
            tipo: "compra",
            plazo_meses: Number(plazo),
            lineas: lineas
              .filter((l) => l.codigo)
              .map((l) => ({ codigo_servicio: l.codigo, cantidad: l.cantidad })),
            proveedores: invitados.map((i) => i.id),
          }
    )
  }

  function lineasDeCompra() {
    if (catalogo.isPending) return <EstadoCarga filas={2} />
    if (catalogo.isError) {
      return (
        <EstadoError
          error={catalogo.error}
          alReintentar={() => void catalogo.refetch()}
        />
      )
    }
    return (
      <div className="space-y-4">
        <ol className="space-y-4">
          {lineas.map((linea, i) => {
            const servicio = catalogo.data.find((s) => s.codigo === linea.codigo)
            return (
              <li
                key={linea.clave}
                className="grid gap-3 rounded-lg border p-3 sm:grid-cols-[1fr_12rem_auto] sm:items-start"
              >
                <Campo
                  id={`${id}-servicio-${linea.clave}`}
                  etiqueta={`Servicio ${i + 1}`}
                  error={errores[`lineas.${i}.codigo_servicio`]}
                >
                  {(control) => (
                    <Select
                      value={linea.codigo || undefined}
                      onValueChange={(codigo) => cambiarLinea(linea.clave, { codigo })}
                    >
                      <SelectTrigger {...control} className="w-full">
                        <SelectValue placeholder="Elija un servicio" />
                      </SelectTrigger>
                      <SelectContent>
                        {catalogo.data.map((s) => (
                          <SelectItem key={s.codigo} value={s.codigo}>
                            {`${s.nombre} (${s.moneda})`}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </Campo>
                <Campo
                  id={`${id}-cantidad-${linea.clave}`}
                  etiqueta={`Cantidad ${i + 1}`}
                  ayuda={servicio ? `Se cotiza ${porUnidad(servicio.unidad)}.` : undefined}
                  error={errores[`lineas.${i}.cantidad`]}
                >
                  {(control) => (
                    <Input
                      {...control}
                      type="number"
                      inputMode="decimal"
                      min="0.0001"
                      step="any"
                      required
                      value={linea.cantidad}
                      onChange={(e) =>
                        cambiarLinea(linea.clave, { cantidad: e.target.value })
                      }
                    />
                  )}
                </Campo>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="sm:mt-6"
                  aria-label={`Quitar el servicio ${i + 1}`}
                  aria-disabled={lineas.length === 1}
                  onClick={() => quitarLinea(linea.clave)}
                >
                  <X aria-hidden />
                </Button>
              </li>
            )
          })}
        </ol>
        <Button
          ref={agregar}
          type="button"
          variant="outline"
          aria-disabled={lineas.length >= MAXIMO_LINEAS}
          onClick={agregarLinea}
        >
          <Plus aria-hidden />
          Agregar servicio
        </Button>
      </div>
    )
  }

  return (
    <form onSubmit={enviar} className="space-y-6">
      <Seccion titulo="Datos generales">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo
            id={`${id}-titulo`}
            etiqueta="Título"
            ayuda="Lo verán los proveedores en su invitación."
            error={errores.titulo}
          >
            {(control) => (
              <Input
                {...control}
                required
                maxLength={120}
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-fecha`}
            etiqueta="Fecha límite"
            ayuda="Al publicar debe quedar entre 1 hora y 60 días en el futuro."
            error={errores.fecha_limite}
          >
            {(control) => (
              <Input
                {...control}
                type="datetime-local"
                required
                value={fechaLimite}
                onChange={(e) => setFechaLimite(e.target.value)}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-rondas`}
            etiqueta="Rondas"
            ayuda={
              <>
                Cuántas ofertas puede hacer cada proveedor (
                <Termino clave="ronda">rondas</Termino>): de 2 a 12.
              </>
            }
            error={errores.rondas_max}
          >
            {(control) => (
              <Input
                {...control}
                type="number"
                inputMode="numeric"
                min={2}
                max={12}
                step={1}
                required
                value={rondas}
                onChange={(e) => setRondas(e.target.value)}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-estilo`}
            etiqueta="Estilo del agente"
            ayuda={estiloElegido?.descripcion}
            error={errores.estilo}
          >
            {(control) => (
              <Select value={estilo} onValueChange={(v) => setEstilo(v as Estilo)}>
                <SelectTrigger {...control} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ESTILOS.map((e) => (
                    <SelectItem key={e.clave} value={e.clave}>
                      {e.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </Campo>
          {!renovacion && (
            <Campo
              id={`${id}-plazo`}
              etiqueta="Plazo del contrato (meses)"
              ayuda="De 1 a 60. Con este plazo se consulta el precio de referencia."
              error={errores.plazo_meses}
            >
              {(control) => (
                <Input
                  {...control}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={60}
                  step={1}
                  required
                  value={plazo}
                  onChange={(e) => setPlazo(e.target.value)}
                />
              )}
            </Campo>
          )}
        </div>
      </Seccion>
      {renovacion ? (
        <ContratoRenovado renovacion={renovacion} />
      ) : (
        <>
          <Seccion
            titulo="Qué se compra"
            descripcion="De 1 a 20 servicios del catálogo, todos en la misma moneda."
          >
            {lineasDeCompra()}
          </Seccion>
          <Seccion
            titulo="Proveedores invitados"
            descripcion="De 1 a 10 proveedores activos; cada uno recibe su propio enlace."
          >
            <SelectorProveedores
              elegidos={invitados}
              alCambiar={setInvitados}
              error={errores.proveedores}
            />
          </Seccion>
        </>
      )}
      {crear.isError && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>
            {crear.error instanceof ErrorApi
              ? crear.error.titulo
              : "No se pudo crear la negociación"}
          </AlertTitle>
          <AlertDescription>
            <p>{crear.error.message}</p>
            {generales.length > 0 && (
              <ul className="list-disc pl-5">
                {generales.map(([campo, mensaje]) => (
                  <li key={campo}>{mensaje}</li>
                ))}
              </ul>
            )}
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" aria-disabled={crear.isPending}>
          Crear borrador
        </Button>
        <Button asChild variant="outline">
          <Link to="/negociaciones">Volver a la lista</Link>
        </Button>
      </div>
    </form>
  )
}
```

En `web/src/rutas.tsx`, agregue después de la ruta `negociaciones`:

```tsx
  {
    path: "negociaciones/nueva",
    lazy: async () => ({
      Component: (await import("@/paginas/NegociacionNueva")).NegociacionNueva,
    }),
  },
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/paginas/NegociacionNueva.test.tsx src/rutas.test.ts`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/componentes/negociacion/Campo.tsx web/src/componentes/negociacion/SelectorProveedores.tsx web/src/paginas/NegociacionNueva.tsx web/src/paginas/NegociacionNueva.test.tsx web/src/pruebas/utilidades.tsx web/src/rutas.tsx
git commit -m "feat(web): nueva negociación de compra y renovación de un contrato" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Detalle: editor del borrador, publicación con enlaces y cancelación

**Files:**
- Create: `web/src/componentes/negociacion/BandaReferencia.tsx`
- Create: `web/src/componentes/negociacion/ResumenConfiguracion.tsx`
- Create: `web/src/componentes/negociacion/DialogoEnlaces.tsx`
- Create: `web/src/componentes/negociacion/DialogoCancelar.tsx`
- Create: `web/src/componentes/negociacion/EditorBorrador.tsx`
- Create: `web/src/paginas/Negociacion.tsx`
- Create: `web/src/paginas/Negociacion.test.tsx`
- Modify: `web/src/pruebas/utilidades.tsx` (agrega `simularRutas`)
- Modify: `web/src/rutas.tsx`

**Interfaces:**
- Consumes:
  - de la Task 1: `useNegociacion`, `ESTILOS`, `PASOS`, `NOMBRES_TIPO`, `formatoTermino`, `Evento`, `PalancaEvento`, `ClavePalanca`, `Estilo`, `EnlaceInvitacion`, `Publicacion`, `Banda`, `aEntradaFechaHora`, `desdeEntradaFechaHora` y `Textarea`;
  - de la Task 2: `EtiquetaEstadoEvento`;
  - de la Task 3: `Campo` y `llamadaA`;
  - lo que ya existe: `ConfirmarAccion`, `Seccion`, `Termino`, `ContenidoConsulta`, `esperarSinEnMutaciones`, `formatoMoneda`, `formatoDecimal` y `porUnidad`.
- Produces:
  - `BandaReferencia({ banda, moneda })`;
  - `ResumenConfiguracion({ evento })`;
  - `DialogoEnlaces({ enlaces: EnlaceInvitacion[] | null, alCerrar })`. La Task 5 lo reutiliza para «Reenviar invitación»;
  - `DialogoCancelar({ ruta, borrador: boolean, alCancelar })`. `ruta` es `/negociacion/eventos/{id}` y la Task 5 lo reutiliza con `borrador={false}`;
  - `EditorBorrador({ evento, alAvisar, alPublicar })`;
  - la página `Negociacion` en `/negociaciones/:id`;
  - `simularRutas(rutas: Record<"MÉTODO /api/…", () => Response>)` (`@/pruebas/utilidades`), que usan las Tasks 5 a 8.
- API:
  - `GET /negociacion/eventos/{id}` → `Evento`;
  - `PATCH /negociacion/eventos/{id}` con `version`. Puede responder 409 `version_desactualizada`, o 422 con `errores` por campo;
  - `POST /negociacion/eventos/{id}/publicar` → `Publicacion`. Si no se puede publicar, 422 con los mismos campos que `evento.errores`;
  - `POST /negociacion/eventos/{id}/cancelar` con `{ motivo }`.
- **Campos de los errores y avisos** (`evento.errores`, `evento.avisos` y los 422):
  - `titulo`, `fecha_limite`, `rondas_max`, `estilo`, `plazo_meses` y `proveedores`;
  - `lineas.{i}.ideal` y `lineas.{i}.limite`, donde `i` es el índice en `evento.lineas`;
  - `palancas.{clave}.peso`, `palancas.{clave}.ideal` y `palancas.{clave}.limite`;
  - `palancas`, para la suma de los pesos.

- [ ] **Step 1: Write the failing test**

En `web/src/pruebas/utilidades.tsx`, agregue después de `simularApi`:

```tsx
/**
 * Sustituye fetch y responde por método y URL exacta, con claves como "PATCH /api/…". Sin método
 * en `init`, la llamada cuenta como GET. Lo que no está en la tabla responde 404.
 */
export function simularRutas(rutas: Record<string, () => Respuesta>) {
  const simulado = vi.fn((url: string, init?: RequestInit) => {
    const respuesta = rutas[`${init?.method ?? "GET"} ${url}`]
    return Promise.resolve(
      respuesta ? respuesta() : new Response("", { status: 404 })
    )
  })
  vi.stubGlobal("fetch", simulado)
  return simulado
}
```

`web/src/paginas/Negociacion.test.tsx`:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Negociacion } from "@/paginas/Negociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinEnMutaciones,
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"
import { formatoMoneda } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ID = "5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42"
const RUTA = `/api/negociacion/eventos/${ID}`

const inactiva = (clave: string, nombre: string, unidad: string) => ({
  clave,
  nombre,
  unidad,
  activa: false,
  peso: 0,
  ideal: null,
  limite: null,
  vigente: null,
})

const PALANCAS = [
  { ...inactiva("precio", "Precio unitario", "MXN"), activa: true, peso: 100 },
  inactiva("plazo_meses", "Plazo del contrato", "meses"),
  inactiva("plazo_pago_dias", "Plazo de pago", "días"),
  inactiva("sla_disponibilidad", "Disponibilidad garantizada (SLA)", "%"),
  inactiva("tope_aumento_pct", "Tope de aumento anual", "%"),
  inactiva("cuota_implementacion", "Cuota de implementación", "MXN"),
]

const BORRADOR = {
  id: ID,
  folio: "NEG-2026-0001",
  tipo: "compra",
  titulo: "Licencias de correo 2027",
  moneda: "MXN",
  plazo_meses: 12,
  estado: "borrador",
  fecha_limite: "2026-10-21T23:00:00Z",
  rondas_max: 6,
  estilo: "balanceado",
  contrato_origen_id: null,
  proveedor_vigente_id: null,
  invitados: [
    { id: "p1", nombre: "Nube Norte" },
    { id: "p2", nombre: "Datos del Sur" },
  ],
  lineas: [
    {
      id: "l1",
      orden: 0,
      codigo_servicio: "LIC-CORREO",
      nombre: "Correo en la nube",
      unidad: "usuario_mes",
      cantidad: "250.0000",
      precio_vigente: null,
      ideal: "88.00",
      limite: "95.00",
      referencia: {
        p25: "88.0000",
        p50: "95.0000",
        p75: "104.0000",
        metodo: "linea_base",
        confianza: "normal",
        observaciones: 31,
      },
    },
  ],
  palancas: PALANCAS,
  referencia_fecha: "2026-10-14T18:00:00Z",
  creado_por_nombre: "Ana López",
  creado_en: "2026-10-14T18:00:00Z",
  publicado_en: null,
  cerrado_en: null,
  motivo_cancelacion: null,
  version: 3,
  errores: [],
  avisos: [],
  sesiones: [],
}

function abrir() {
  return renderizarPagina(<Negociacion />, {
    ruta: `/negociaciones/${ID}`,
    patron: "/negociaciones/:id",
  })
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Negociacion en borrador", () => {
  it("muestra un esqueleto mientras carga y, si no existe, el error con Reintentar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    abrir()
    expect(await screen.findByText("Cargando…")).toBeInTheDocument()
    cleanup()
    vi.unstubAllGlobals()
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson(
          { title: "No encontrado", detail: "La negociación no existe." },
          404
        ),
    })
    abrir()
    expect(await screen.findByText("La negociación no existe.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument()
  })

  it("el editor muestra la banda de referencia junto al ideal y el límite", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(BORRADOR) })
    const { container } = abrir()
    expect(
      await screen.findByLabelText("Ideal (Correo en la nube)")
    ).toHaveValue(88)
    expect(screen.getByLabelText("Límite (Correo en la nube)")).toHaveValue(95)
    expect(screen.getByText("Típico (P50)")).toBeInTheDocument()
    expect(screen.getByText(formatoMoneda("104.0000", "MXN"))).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("activar una palanca muestra sus campos y el total de pesos en vivo", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(BORRADOR) })
    abrir()
    await userEvent.click(
      await screen.findByRole("checkbox", { name: "Negociar: Plazo de pago" })
    )
    await userEvent.type(screen.getByLabelText("Peso (Plazo de pago)"), "20")
    expect(
      screen.getByText("Total: 120 de 100 · Los pesos deben sumar 100.")
    ).toBeInTheDocument()
    const precio = screen.getByLabelText("Peso (Precio unitario)")
    await userEvent.clear(precio)
    await userEvent.type(precio, "80")
    expect(screen.getByText("Total: 100 de 100")).toBeInTheDocument()
  })

  it("guarda los cambios con la versión y avisa", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(BORRADOR),
      [`PATCH ${RUTA}`]: () => respuestaJson(BORRADOR),
    })
    abrir()
    const ideal = await screen.findByLabelText("Ideal (Correo en la nube)")
    await userEvent.clear(ideal)
    await userEvent.type(ideal, "85.50")
    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }))
    expect(await screen.findByText("Se guardaron los cambios.")).toBeInTheDocument()
    expect(llamadaA(api, RUTA, "PATCH").cuerpo).toMatchObject({
      version: 3,
      titulo: "Licencias de correo 2027",
      rondas_max: 6,
      estilo: "balanceado",
      plazo_meses: 12,
      lineas: [
        {
          codigo_servicio: "LIC-CORREO",
          cantidad: "250.0000",
          ideal: "85.50",
          limite: "95.00",
        },
      ],
      palancas: [{ clave: "precio", peso: 100 }],
    })
  })

  it("un 409 de versión ofrece recargar y descarta lo local", async () => {
    let version = 3
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson(
          version === 4
            ? {
                ...BORRADOR,
                version,
                lineas: [{ ...BORRADOR.lineas[0], ideal: "90.00" }],
              }
            : BORRADOR
        ),
      [`PATCH ${RUTA}`]: () => {
        version = 4
        return respuestaJson(
          {
            title: "Conflicto",
            detail:
              "Otra persona cambió esta negociación; recárguela para ver sus cambios.",
            codigo: "version_desactualizada",
          },
          409
        )
      },
    })
    abrir()
    const ideal = await screen.findByLabelText("Ideal (Correo en la nube)")
    await userEvent.clear(ideal)
    await userEvent.type(ideal, "70")
    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }))
    expect(
      await screen.findByText(
        "Otra persona cambió esta negociación; recárguela para ver sus cambios."
      )
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Recargar" }))
    await waitFor(() =>
      expect(screen.getByLabelText("Ideal (Correo en la nube)")).toHaveValue(90)
    )
  })

  it("no deja publicar con cambios sin guardar ni con errores", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...BORRADOR,
          errores: [{ campo: "lineas.0.limite", mensaje: "Indique el precio límite." }],
        }),
    })
    abrir()
    expect(await screen.findByText("Indique el precio límite.")).toBeInTheDocument()
    expect(screen.getByLabelText("Límite (Correo en la nube)")).toHaveAttribute(
      "aria-invalid",
      "true"
    )
    const publicar = screen.getByRole("button", { name: "Publicar" })
    expect(publicar).toHaveAttribute("aria-disabled", "true")
    expect(publicar).toHaveAccessibleDescription(
      "Corrija lo marcado para poder publicar."
    )
    await userEvent.click(publicar)
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText("Ideal (Correo en la nube)"), "1")
    expect(
      screen.getByRole("button", { name: "Publicar" })
    ).toHaveAccessibleDescription("Guarde los cambios antes de publicar.")
  })

  it("muestra el aviso de P75 junto al límite, sin impedir publicar", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...BORRADOR,
          avisos: [
            {
              campo: "lineas.0.limite",
              mensaje:
                "El límite queda por encima del P75 del mercado ($104.00): pagaría más que en tres de cada cuatro contratos.",
            },
          ],
        }),
    })
    abrir()
    expect(await screen.findByText(/por encima del P75/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Publicar" })).not.toHaveAttribute(
      "aria-disabled"
    )
  })

  it("publica, muestra los enlaces una sola vez y no los deja en caché", async () => {
    let publicado = false
    const ABIERTO = {
      ...BORRADOR,
      estado: "abierto",
      publicado_en: "2026-10-14T19:00:00Z",
      version: 4,
    }
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(publicado ? ABIERTO : BORRADOR),
      [`POST ${RUTA}/publicar`]: () => {
        publicado = true
        return respuestaJson({
          evento: ABIERTO,
          enlaces: [
            {
              sesion_id: "s1",
              proveedor_nombre: "Nube Norte",
              destinatario: "lucia@nubenorte.example",
              enlace: "http://localhost:8080/portal#t=secreto-123",
              correo_estado: "enviado",
            },
          ],
        })
      },
    })
    const { cliente } = abrir()
    await userEvent.click(await screen.findByRole("button", { name: "Publicar" }))
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Publicar",
      })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Enlace de invitación",
    })
    expect(
      within(dialogo).getByText("http://localhost:8080/portal#t=secreto-123")
    ).toBeInTheDocument()
    expect(
      within(dialogo).getByText("Se envió por correo a lucia@nubenorte.example.")
    ).toBeInTheDocument()
    await userEvent.click(within(dialogo).getByRole("button", { name: "Listo" }))
    expect(screen.queryByText(/secreto-123/)).not.toBeInTheDocument()
    await esperarSinEnMutaciones(cliente, "secreto-123")
    expect(await screen.findByText("Sus límites")).toBeInTheDocument()
  })

  it("cancela el borrador con su motivo", async () => {
    let cancelado = false
    const api = simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson(
          cancelado
            ? {
                ...BORRADOR,
                estado: "cancelado",
                motivo_cancelacion: "Ya no se necesita",
              }
            : BORRADOR
        ),
      [`POST ${RUTA}/cancelar`]: () => {
        cancelado = true
        return respuestaJson({ ...BORRADOR, estado: "cancelado" })
      },
    })
    abrir()
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancelar borrador" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Cancelar el borrador",
    })
    await userEvent.type(within(dialogo).getByLabelText("Motivo"), "Ya no se necesita")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Cancelar borrador" })
    )
    expect(await screen.findByText("Se canceló el borrador.")).toBeInTheDocument()
    expect(llamadaA(api, `${RUTA}/cancelar`, "POST").cuerpo).toEqual({
      motivo: "Ya no se necesita",
    })
    expect(await screen.findByText("Ya no se necesita")).toBeInTheDocument()
  })

  it("en una renovación, activar una palanca propone el valor vigente como límite", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...BORRADOR,
          tipo: "renovacion",
          invitados: [{ id: "p1", nombre: "Nube Norte" }],
          lineas: [{ ...BORRADOR.lineas[0], precio_vigente: "95.0000" }],
          palancas: PALANCAS.map((p) =>
            p.clave === "plazo_pago_dias" ? { ...p, vigente: "30" } : p
          ),
        }),
    })
    abrir()
    expect(await screen.findByText(/Precio vigente: \$95\.00/)).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Negociar: Plazo de pago" })
    )
    expect(screen.getByLabelText("Límite (Plazo de pago)")).toHaveValue(30)
    expect(screen.getByText("Hoy: 30 días.")).toBeInTheDocument()
    expect(
      screen.queryByLabelText("Plazo del contrato (meses)")
    ).not.toBeInTheDocument()
  })

  it("el aprobador ve la configuración sin poder editarla", async () => {
    sesionDePrueba.roles = ["aprobador"]
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(BORRADOR) })
    abrir()
    expect(await screen.findByText("Sus límites")).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Guardar cambios" })
    ).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (desde `web/`): `npx vitest run src/paginas/Negociacion.test.tsx`
Expected: FAIL con `Failed to resolve import "@/paginas/Negociacion"`.

- [ ] **Step 3: Write the implementation**

`web/src/componentes/negociacion/BandaReferencia.tsx`:

```tsx
import { Termino } from "@/componentes/Termino"
import { cn } from "@/lib/utils"
import type { Banda } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/**
 * P25, P50 y P75 de la foto guardada en el evento (spec D5), no la referencia de hoy: así el
 * comprador ve lo mismo que se usó al sugerir sus límites. ReferenciaPrecio consulta la de hoy.
 */
export function BandaReferencia({
  banda,
  moneda,
}: {
  banda: Banda | null
  moneda: string
}) {
  if (!banda) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin referencia de precio: no hay contratos comparables recientes. Fije
        el ideal y el límite con su criterio.
      </p>
    )
  }
  const valores: [string, string, string][] = [
    ["P25", "Bajo", banda.p25],
    ["P50", "Típico", banda.p50],
    ["P75", "Alto", banda.p75],
  ]
  return (
    <div className="space-y-1">
      <dl className="grid grid-cols-3 gap-2">
        {valores.map(([clave, nombre, valor]) => (
          <div
            key={clave}
            className={cn(
              "rounded-md border p-2",
              clave === "P50" && "border-accent"
            )}
          >
            <dt className="text-xs text-muted-foreground">
              {nombre} ({clave})
            </dt>
            <dd className="text-sm font-medium tabular-nums">
              {formatoMoneda(valor, moneda)}
            </dd>
          </div>
        ))}
      </dl>
      {banda.confianza === "baja" && (
        <p className="text-xs text-warning">
          <Termino clave="bajaConfianza">Baja confianza</Termino>: hay pocos
          contratos comparables.
        </p>
      )}
    </div>
  )
}
```

`web/src/componentes/negociacion/ResumenConfiguracion.tsx`:

```tsx
import { Seccion } from "@/componentes/Seccion"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import { ESTILOS, NOMBRES_TIPO, formatoTermino, type Evento } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/** La configuración de una negociación, de solo lectura: publicada, cerrada o vista sin el rol de compras. */
export function ResumenConfiguracion({ evento }: { evento: Evento }) {
  const estilo =
    ESTILOS.find((e) => e.clave === evento.estilo)?.nombre ?? evento.estilo
  const datos: [string, string][] = [
    ["Tipo", NOMBRES_TIPO[evento.tipo]],
    ["Fecha límite", formatoFechaHora(evento.fecha_limite)],
    ["Rondas", String(evento.rondas_max)],
    ["Estilo del agente", estilo],
    [
      "Plazo del contrato",
      `${evento.plazo_meses} ${evento.plazo_meses === 1 ? "mes" : "meses"}`,
    ],
    ["Moneda", evento.moneda],
    ["Creada por", evento.creado_por_nombre],
  ]
  if (evento.publicado_en)
    datos.push(["Publicada", formatoFechaHora(evento.publicado_en)])
  if (evento.motivo_cancelacion)
    datos.push(["Motivo de cancelación", evento.motivo_cancelacion])
  const activas = evento.palancas.filter((p) => p.activa)
  const monto = (valor: string | null) =>
    valor ? formatoMoneda(valor, evento.moneda) : "—"
  const termino = (valor: string | null, unidad: string) =>
    valor ? formatoTermino(valor, unidad, evento.moneda) : "—"

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Seccion titulo="Configuración">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {datos.map(([titulo, valor]) => (
            <div key={titulo}>
              <dt className="text-muted-foreground">{titulo}</dt>
              <dd className="font-medium break-words">{valor}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-sm">
          <span className="text-muted-foreground">Invitados: </span>
          {evento.invitados.map((i) => i.nombre).join(", ")}
        </p>
      </Seccion>
      <Seccion
        titulo="Sus límites"
        descripcion="Solo usted los ve; el proveedor nunca los conoce."
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Término</TableHead>
              <TableHead className="text-right">Peso</TableHead>
              <TableHead className="text-right">Ideal</TableHead>
              <TableHead className="text-right">Límite</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {evento.lineas.map((l) => (
              <TableRow key={l.id}>
                <TableCell className="whitespace-normal">{`Precio: ${l.nombre}`}</TableCell>
                <TableCell className="text-right">—</TableCell>
                <TableCell className="text-right tabular-nums">{monto(l.ideal)}</TableCell>
                <TableCell className="text-right tabular-nums">{monto(l.limite)}</TableCell>
              </TableRow>
            ))}
            {activas.map((p) => (
              <TableRow key={p.clave}>
                <TableCell className="whitespace-normal">{p.nombre}</TableCell>
                <TableCell className="text-right tabular-nums">{p.peso}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {termino(p.ideal, p.unidad)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {termino(p.limite, p.unidad)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Seccion>
    </div>
  )
}
```

`web/src/componentes/negociacion/DialogoEnlaces.tsx`:

```tsx
import { Copy } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { EnlaceInvitacion } from "@/negociacion"

/**
 * Los enlaces de invitación, que la API entrega una sola vez (spec D3). Se abre por estado; al
 * cerrar, el padre los descarta y el foco vuelve al contenido de la página.
 */
export function DialogoEnlaces({
  enlaces,
  alCerrar,
}: {
  enlaces: EnlaceInvitacion[] | null
  alCerrar: () => void
}) {
  const [copia, setCopia] = useState<{ id: string; ok: boolean } | null>(null)

  async function copiar(enlace: EnlaceInvitacion) {
    try {
      await navigator.clipboard.writeText(enlace.enlace)
      setCopia({ id: enlace.sesion_id, ok: true })
    } catch {
      setCopia({ id: enlace.sesion_id, ok: false })
    }
  }

  const copiado = enlaces?.find((e) => e.sesion_id === copia?.id)
  return (
    <Dialog
      open={enlaces !== null}
      onOpenChange={(abierto) => {
        if (!abierto) {
          setCopia(null)
          alCerrar()
        }
      }}
    >
      <DialogContent
        className="sm:max-w-2xl"
        onCloseAutoFocus={(evento) => {
          evento.preventDefault()
          document.getElementById("contenido")?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>
            {enlaces?.length === 1
              ? "Enlace de invitación"
              : "Enlaces de invitación"}
          </DialogTitle>
          <DialogDescription>
            Solo se muestran ahora. Si pierde uno, use «Reenviar invitación»: el
            enlace anterior deja de servir.
          </DialogDescription>
        </DialogHeader>
        <ul className="max-h-[60svh] space-y-3 overflow-y-auto">
          {enlaces?.map((e) => (
            <li key={e.sesion_id} className="space-y-2 rounded-lg border p-3">
              <p className="font-medium">{e.proveedor_nombre}</p>
              <p className="text-sm text-muted-foreground">
                {e.correo_estado === "enviado"
                  ? `Se envió por correo a ${e.destinatario}.`
                  : `No se pudo enviar el correo a ${e.destinatario}: comparta el enlace o reenvíe la invitación.`}
              </p>
              <p className="rounded-md bg-muted px-2 py-1 font-mono text-xs break-all select-all">
                {e.enlace}
              </p>
              <Button variant="outline" size="sm" onClick={() => void copiar(e)}>
                <Copy aria-hidden />
                Copiar
                <span className="sr-only"> el enlace de {e.proveedor_nombre}</span>
              </Button>
            </li>
          ))}
        </ul>
        <p aria-live="polite" className="text-sm text-muted-foreground">
          {copiado &&
            (copia?.ok
              ? `Se copió el enlace de ${copiado.proveedor_nombre}.`
              : "No se pudo copiar; selecciónelo y cópielo a mano.")}
        </p>
        <DialogFooter>
          <DialogClose asChild>
            <Button>Listo</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

`web/src/componentes/negociacion/DialogoCancelar.tsx`:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useState, type FormEvent } from "react"
import { enviarJson, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { Campo } from "@/componentes/negociacion/Campo"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import type { Evento } from "@/negociacion"

/** «Cancelar borrador» o «Cancelar negociación», con el motivo que queda en la bitácora. */
export function DialogoCancelar({
  ruta,
  borrador,
  alCancelar,
}: {
  ruta: string
  borrador: boolean
  alCancelar: () => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [abierto, setAbierto] = useState(false)
  const [motivo, setMotivo] = useState("")
  const cancelar = useMutation({
    mutationFn: () =>
      pedir<Evento>(`${ruta}/cancelar`, token, enviarJson("POST", { motivo })),
    onSuccess: async () => {
      setAbierto(false)
      alCancelar()
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
  })
  const error = erroresPorCampo(cancelar.error).motivo
  const accion = borrador ? "Cancelar borrador" : "Cancelar negociación"

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    // El diálogo se dibuja en un portal, pero React propaga el submit al formulario padre.
    evento.stopPropagation()
    if (!cancelar.isPending) cancelar.mutate()
  }

  return (
    <Dialog
      open={abierto}
      onOpenChange={(valor) => {
        setAbierto(valor)
        if (!valor) {
          setMotivo("")
          cancelar.reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          {accion}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={enviar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>
              {borrador ? "Cancelar el borrador" : "Cancelar la negociación"}
            </DialogTitle>
            <DialogDescription>
              {borrador
                ? "El borrador queda cancelado y no se envía nada a los proveedores."
                : "Los enlaces dejan de servir y las sesiones que sigan abiertas terminan sin acuerdo. No se puede deshacer."}
            </DialogDescription>
          </DialogHeader>
          <Campo
            id={`${id}-motivo`}
            etiqueta="Motivo"
            ayuda="Queda en la bitácora y en la Actividad."
            error={error}
          >
            {(control) => (
              <Textarea
                {...control}
                required
                maxLength={500}
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
              />
            )}
          </Campo>
          {cancelar.isError && !error && (
            <p role="alert" className="text-sm text-destructive">
              {cancelar.error.message}
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Volver
              </Button>
            </DialogClose>
            <Button
              type="submit"
              variant="destructive"
              aria-disabled={cancelar.isPending}
            >
              {accion}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
```

`web/src/componentes/negociacion/EditorBorrador.tsx`:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  CircleAlert,
  CircleCheck,
  RefreshCw,
  Send,
  TriangleAlert,
} from "lucide-react"
import { useId, useState, type FormEvent, type ReactNode } from "react"
import { enviarJson, ErrorApi, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { BandaReferencia } from "@/componentes/negociacion/BandaReferencia"
import { Campo } from "@/componentes/negociacion/Campo"
import { DialogoCancelar } from "@/componentes/negociacion/DialogoCancelar"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  aEntradaFechaHora,
  desdeEntradaFechaHora,
  formatoFechaHora,
} from "@/fechas"
import { formatoDecimal, porUnidad } from "@/inteligencia"
import { cn } from "@/lib/utils"
import {
  ESTILOS,
  PASOS,
  formatoTermino,
  type ClavePalanca,
  type EnlaceInvitacion,
  type Estilo,
  type Evento,
  type PalancaEvento,
  type Publicacion,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

type ValorPalanca = {
  activa: boolean
  peso: string
  ideal: string
  limite: string
}
type Formulario = {
  titulo: string
  fechaLimite: string
  rondas: string
  estilo: Estilo
  plazo: string
  lineas: { ideal: string; limite: string }[]
  palancas: Record<ClavePalanca, ValorPalanca>
}

function desdeEvento(evento: Evento): Formulario {
  return {
    titulo: evento.titulo,
    fechaLimite: aEntradaFechaHora(new Date(evento.fecha_limite)),
    rondas: String(evento.rondas_max),
    estilo: evento.estilo,
    plazo: String(evento.plazo_meses),
    lineas: evento.lineas.map((l) => ({
      ideal: l.ideal ?? "",
      limite: l.limite ?? "",
    })),
    palancas: Object.fromEntries(
      evento.palancas.map((p) => [
        p.clave,
        {
          activa: p.activa,
          peso: p.activa ? String(p.peso) : "",
          ideal: p.ideal ?? "",
          limite: p.limite ?? "",
        },
      ])
    ) as Record<ClavePalanca, ValorPalanca>,
  }
}

/** El cuerpo del PATCH: todo lo editable. Un campo vacío va como null y lo señala la validación. */
function aCambios(evento: Evento, f: Formulario) {
  const nulo = (valor: string) => (valor.trim() === "" ? null : valor.trim())
  return {
    version: evento.version,
    titulo: f.titulo,
    fecha_limite: desdeEntradaFechaHora(f.fechaLimite),
    rondas_max: Number(f.rondas),
    estilo: f.estilo,
    ...(evento.tipo === "compra" ? { plazo_meses: Number(f.plazo) } : {}),
    lineas: evento.lineas.map((l, i) => ({
      codigo_servicio: l.codigo_servicio,
      cantidad: l.cantidad,
      ideal: nulo(f.lineas[i].ideal),
      limite: nulo(f.lineas[i].limite),
    })),
    palancas: evento.palancas
      .filter((p) => f.palancas[p.clave].activa)
      .map((p) => {
        const v = f.palancas[p.clave]
        const peso = Number(v.peso) || 0
        return p.clave === "precio"
          ? { clave: p.clave, peso }
          : { clave: p.clave, peso, ideal: nulo(v.ideal), limite: nulo(v.limite) }
      }),
  }
}

/**
 * Editor del borrador (spec §10.1). Se monta con `key={evento.version}`: al guardar, la versión
 * nueva lo vuelve a montar con lo que quedó en el servidor (y sus errores y avisos).
 */
export function EditorBorrador({
  evento,
  alAvisar,
  alPublicar,
}: {
  evento: Evento
  alAvisar: (texto: string) => void
  alPublicar: (enlaces: EnlaceInvitacion[]) => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [inicial] = useState(() => desdeEvento(evento))
  const [f, setF] = useState(inicial)
  const sucio = JSON.stringify(f) !== JSON.stringify(inicial)
  const ruta = `/negociacion/eventos/${encodeURIComponent(evento.id)}`
  const renovacion = evento.tipo === "renovacion"

  const guardar = useMutation({
    mutationFn: () =>
      pedir<Evento>(ruta, token, enviarJson("PATCH", aCambios(evento, f))),
    onSuccess: async () => {
      alAvisar("Se guardaron los cambios.")
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
  })
  const publicar = useMutation({
    mutationFn: () =>
      pedir<Publicacion>(`${ruta}/publicar`, token, { method: "POST" }),
    // Los enlaces solo viven en el diálogo: la mutación no los conserva en caché.
    gcTime: 0,
    onSuccess: async ({ enlaces }) => {
      alPublicar(enlaces)
      alAvisar("Se publicó la negociación y se enviaron las invitaciones.")
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
  })

  const errores: Record<string, string> = {
    ...Object.fromEntries(evento.errores.map((e) => [e.campo, e.mensaje])),
    ...erroresPorCampo(publicar.error),
    ...erroresPorCampo(guardar.error),
  }
  const avisos = Object.fromEntries(
    evento.avisos.map((a) => [a.campo, a.mensaje])
  )
  const conflicto =
    guardar.error instanceof ErrorApi && guardar.error.estado === 409
  const total = Object.values(f.palancas)
    .filter((p) => p.activa)
    .reduce((suma, p) => suma + (Number(p.peso) || 0), 0)
  const publicable = !sucio && evento.errores.length === 0
  const invitados =
    evento.invitados.length === 1
      ? "1 proveedor"
      : `${evento.invitados.length} proveedores`
  const estadoPublicar = sucio
    ? "Guarde los cambios antes de publicar."
    : evento.errores.length > 0
      ? "Corrija lo marcado para poder publicar."
      : `Se enviará la invitación a ${invitados}.`

  function cambiarLinea(i: number, campo: "ideal" | "limite", valor: string) {
    setF((p) => ({
      ...p,
      lineas: p.lineas.map((l, j) => (j === i ? { ...l, [campo]: valor } : l)),
    }))
  }

  function cambiarPalanca(clave: ClavePalanca, cambio: Partial<ValorPalanca>) {
    setF((p) => ({
      ...p,
      palancas: { ...p.palancas, [clave]: { ...p.palancas[clave], ...cambio } },
    }))
  }

  function activar(p: PalancaEvento, activa: boolean) {
    const actual = f.palancas[p.clave]
    // En renovación, el límite sugerido de una palanca es su valor vigente (spec §5.2).
    const limite =
      activa && !actual.limite && renovacion && p.vigente
        ? p.vigente
        : actual.limite
    cambiarPalanca(p.clave, { activa, limite })
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (sucio && !guardar.isPending) guardar.mutate()
  }

  function numero(
    idCampo: string,
    etiqueta: string,
    valor: string,
    alCambiar: (valor: string) => void,
    paso: string,
    campo: string,
    ayuda?: string
  ) {
    const aviso: ReactNode = avisos[campo] && (
      <span className="inline-flex gap-1 text-warning">
        <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
        {avisos[campo]}
      </span>
    )
    return (
      <Campo
        id={idCampo}
        etiqueta={etiqueta}
        ayuda={aviso || ayuda}
        error={errores[campo]}
      >
        {(control) => (
          <Input
            {...control}
            type="number"
            inputMode="decimal"
            min="0"
            step={paso}
            value={valor}
            onChange={(e) => alCambiar(e.target.value)}
          />
        )}
      </Campo>
    )
  }

  return (
    <form onSubmit={enviar} className="space-y-6">
      <Seccion titulo="Datos generales">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo id={`${id}-titulo`} etiqueta="Título" error={errores.titulo}>
            {(control) => (
              <Input
                {...control}
                required
                maxLength={120}
                value={f.titulo}
                onChange={(e) => setF({ ...f, titulo: e.target.value })}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-fecha`}
            etiqueta="Fecha límite"
            ayuda="Al publicar debe quedar entre 1 hora y 60 días en el futuro."
            error={errores.fecha_limite}
          >
            {(control) => (
              <Input
                {...control}
                type="datetime-local"
                required
                value={f.fechaLimite}
                onChange={(e) => setF({ ...f, fechaLimite: e.target.value })}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-rondas`}
            etiqueta="Rondas"
            ayuda="De 2 a 12."
            error={errores.rondas_max}
          >
            {(control) => (
              <Input
                {...control}
                type="number"
                inputMode="numeric"
                min={2}
                max={12}
                step={1}
                value={f.rondas}
                onChange={(e) => setF({ ...f, rondas: e.target.value })}
              />
            )}
          </Campo>
          <Campo
            id={`${id}-estilo`}
            etiqueta="Estilo del agente"
            ayuda={ESTILOS.find((e) => e.clave === f.estilo)?.descripcion}
            error={errores.estilo}
          >
            {(control) => (
              <Select
                value={f.estilo}
                onValueChange={(v) => setF({ ...f, estilo: v as Estilo })}
              >
                <SelectTrigger {...control} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ESTILOS.map((e) => (
                    <SelectItem key={e.clave} value={e.clave}>
                      {e.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </Campo>
          {!renovacion && (
            <Campo
              id={`${id}-plazo`}
              etiqueta="Plazo del contrato (meses)"
              ayuda="Al cambiarlo, al guardar se vuelve a consultar el precio de referencia."
              error={errores.plazo_meses}
            >
              {(control) => (
                <Input
                  {...control}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={60}
                  step={1}
                  value={f.plazo}
                  onChange={(e) => setF({ ...f, plazo: e.target.value })}
                />
              )}
            </Campo>
          )}
        </div>
      </Seccion>

      <Seccion
        titulo="Precio por línea"
        descripcion={
          <>
            Fije el <Termino clave="ideal">ideal</Termino> y el{" "}
            <Termino clave="limite">límite</Termino> del precio unitario. La
            banda <Termino clave="percentiles" /> es la referencia del mercado
            {evento.referencia_fecha
              ? ` del ${formatoFechaHora(evento.referencia_fecha)}`
              : ""}
            .
          </>
        }
      >
        <ol className="space-y-4">
          {evento.lineas.map((linea, i) => (
            <li key={linea.id} className="space-y-3 rounded-lg border p-3">
              <div>
                <h3 className="font-medium">{linea.nombre}</h3>
                <p className="text-sm text-muted-foreground">
                  {`Cantidad: ${formatoDecimal(Number(linea.cantidad), 4)} · precio ${porUnidad(linea.unidad)}`}
                  {linea.precio_vigente &&
                    ` · Precio vigente: ${formatoMoneda(linea.precio_vigente, evento.moneda)}`}
                </p>
              </div>
              <BandaReferencia banda={linea.referencia} moneda={evento.moneda} />
              <div className="grid gap-3 sm:grid-cols-2">
                {numero(
                  `${id}-ideal-${i}`,
                  `Ideal (${linea.nombre})`,
                  f.lineas[i].ideal,
                  (v) => cambiarLinea(i, "ideal", v),
                  PASOS.precio,
                  `lineas.${i}.ideal`
                )}
                {numero(
                  `${id}-limite-${i}`,
                  `Límite (${linea.nombre})`,
                  f.lineas[i].limite,
                  (v) => cambiarLinea(i, "limite", v),
                  PASOS.precio,
                  `lineas.${i}.limite`
                )}
              </div>
            </li>
          ))}
        </ol>
      </Seccion>

      <Seccion
        titulo="Qué más se negocia"
        descripcion={
          <>
            Active las <Termino clave="palanca">palancas</Termino> que le importen
            y reparta 100 puntos de peso entre ellas y el precio.
          </>
        }
      >
        <div className="space-y-4">
          <p
            aria-live="polite"
            className={cn(
              "flex items-center gap-2 text-sm font-medium",
              total === 100 ? "text-success" : "text-warning"
            )}
          >
            {total === 100 ? (
              <CircleCheck aria-hidden className="size-4" />
            ) : (
              <TriangleAlert aria-hidden className="size-4" />
            )}
            {`Total: ${total} de 100`}
            {total !== 100 && " · Los pesos deben sumar 100."}
          </p>
          {errores.palancas && (
            <p className="text-sm text-destructive">{errores.palancas}</p>
          )}
          <ul className="space-y-4">
            {evento.palancas.map((p) => {
              const v = f.palancas[p.clave]
              const idCasilla = `${id}-activa-${p.clave}`
              return (
                <li key={p.clave} className="space-y-3 rounded-lg border p-3">
                  {p.clave === "precio" ? (
                    <p className="font-medium">
                      {p.nombre}: siempre se negocia
                    </p>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id={idCasilla}
                        checked={v.activa}
                        onCheckedChange={(c) => activar(p, c === true)}
                      />
                      <Label htmlFor={idCasilla}>{`Negociar: ${p.nombre}`}</Label>
                    </div>
                  )}
                  {v.activa && (
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Campo
                        id={`${id}-peso-${p.clave}`}
                        etiqueta={`Peso (${p.nombre})`}
                        error={errores[`palancas.${p.clave}.peso`]}
                      >
                        {(control) => (
                          <Input
                            {...control}
                            type="number"
                            inputMode="numeric"
                            min={1}
                            max={100}
                            step={1}
                            value={v.peso}
                            onChange={(e) =>
                              cambiarPalanca(p.clave, { peso: e.target.value })
                            }
                          />
                        )}
                      </Campo>
                      {p.clave !== "precio" && (
                        <>
                          {numero(
                            `${id}-ideal-${p.clave}`,
                            `Ideal (${p.nombre})`,
                            v.ideal,
                            (x) => cambiarPalanca(p.clave, { ideal: x }),
                            PASOS[p.clave],
                            `palancas.${p.clave}.ideal`,
                            `En ${p.unidad}.`
                          )}
                          {numero(
                            `${id}-limite-${p.clave}`,
                            `Límite (${p.nombre})`,
                            v.limite,
                            (x) => cambiarPalanca(p.clave, { limite: x }),
                            PASOS[p.clave],
                            `palancas.${p.clave}.limite`,
                            p.vigente
                              ? `Hoy: ${formatoTermino(p.vigente, p.unidad, evento.moneda)}.`
                              : `En ${p.unidad}.`
                          )}
                        </>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      </Seccion>

      <Seccion
        titulo={renovacion ? "Proveedor" : "Proveedores invitados"}
        descripcion="Para cambiar los servicios o los proveedores, cancele este borrador y cree otro."
      >
        {errores.proveedores && (
          <p className="text-sm text-destructive">{errores.proveedores}</p>
        )}
        <ul className="list-disc pl-5 text-sm">
          {evento.invitados.map((i) => (
            <li key={i.id}>{i.nombre}</li>
          ))}
        </ul>
      </Seccion>

      {conflicto ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden />
          <AlertTitle>No se guardaron sus cambios</AlertTitle>
          <AlertDescription>
            <p>{guardar.error?.message}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() =>
                void cliente.invalidateQueries({ queryKey: ["negociacion"] })
              }
            >
              <RefreshCw aria-hidden />
              Recargar
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        (guardar.isError || publicar.isError) && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertTitle>No se pudo completar</AlertTitle>
            <AlertDescription>
              {(guardar.error ?? publicar.error)?.message}
            </AlertDescription>
          </Alert>
        )
      )}

      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <Button type="submit" aria-disabled={!sucio || guardar.isPending}>
            Guardar cambios
          </Button>
          {publicable ? (
            <ConfirmarAccion
              titulo="¿Publicar la negociación?"
              descripcion="Se crea una sesión por proveedor y se le envía su invitación por correo. Después ya no podrá cambiar los límites."
              textoConfirmar="Publicar"
              alConfirmar={() => {
                if (!publicar.isPending) publicar.mutate()
              }}
            >
              <Button type="button" aria-describedby={`${id}-publicar`}>
                <Send aria-hidden />
                Publicar
              </Button>
            </ConfirmarAccion>
          ) : (
            <Button
              type="button"
              aria-disabled
              aria-describedby={`${id}-publicar`}
            >
              <Send aria-hidden />
              Publicar
            </Button>
          )}
          <DialogoCancelar
            ruta={ruta}
            borrador
            alCancelar={() => alAvisar("Se canceló el borrador.")}
          />
        </div>
        <p id={`${id}-publicar`} className="text-sm text-muted-foreground">
          {estadoPublicar}
        </p>
      </div>
    </form>
  )
}
```

`web/src/paginas/Negociacion.tsx`:

```tsx
import { useState } from "react"
import { useParams } from "react-router"
import { useRoles } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { ContenidoConsulta } from "@/componentes/Estados"
import { DialogoEnlaces } from "@/componentes/negociacion/DialogoEnlaces"
import { EditorBorrador } from "@/componentes/negociacion/EditorBorrador"
import { EtiquetaEstadoEvento } from "@/componentes/negociacion/Etiquetas"
import { ResumenConfiguracion } from "@/componentes/negociacion/ResumenConfiguracion"
import {
  NOMBRES_TIPO,
  useNegociacion,
  type EnlaceInvitacion,
  type Evento,
} from "@/negociacion"

export function Negociacion() {
  const { id = "" } = useParams()
  const esComprador = useRoles().includes("comprador")
  const consulta = useNegociacion<Evento>(`/eventos/${encodeURIComponent(id)}`)
  const [aviso, setAviso] = useState("")
  // Los enlaces viven aquí y no en el editor: al publicar, el editor se desmonta.
  const [enlaces, setEnlaces] = useState<EnlaceInvitacion[] | null>(null)

  return (
    <div className="space-y-6">
      <ContenidoConsulta consulta={consulta}>
        {(evento) => (
          <>
            <EncabezadoPagina
              titulo={evento.titulo}
              descripcion={
                <span className="inline-flex flex-wrap items-center gap-2">
                  <span className="font-mono">{evento.folio}</span>
                  <span>· {NOMBRES_TIPO[evento.tipo]}</span>
                  <EtiquetaEstadoEvento estado={evento.estado} />
                </span>
              }
            />
            {evento.estado === "borrador" && esComprador ? (
              <EditorBorrador
                key={evento.version}
                evento={evento}
                alAvisar={setAviso}
                alPublicar={setEnlaces}
              />
            ) : (
              <ResumenConfiguracion evento={evento} />
            )}
          </>
        )}
      </ContenidoConsulta>
      <p
        role="status"
        className={aviso ? "text-sm text-success" : "sr-only"}
      >
        {aviso}
      </p>
      <DialogoEnlaces enlaces={enlaces} alCerrar={() => setEnlaces(null)} />
    </div>
  )
}
```

En `web/src/rutas.tsx`, agregue después de la ruta `negociaciones/nueva`:

```tsx
  {
    path: "negociaciones/:id",
    lazy: async () => ({
      Component: (await import("@/paginas/Negociacion")).Negociacion,
    }),
  },
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/paginas/Negociacion.test.tsx src/rutas.test.ts`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/componentes/negociacion web/src/paginas/Negociacion.tsx web/src/paginas/Negociacion.test.tsx web/src/pruebas/utilidades.tsx web/src/rutas.tsx
git commit -m "feat(web): editor del borrador, publicación con enlaces y cancelación" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Detalle abierto: sesiones, reenvío y cancelación

**Files:**
- Create: `web/src/componentes/negociacion/TablaSesiones.tsx`
- Modify: `web/src/paginas/Negociacion.tsx`
- Modify: `web/src/paginas/Negociacion.test.tsx`

**Interfaces:**
- Consumes:
  - de la Task 1: `ContenidoVivo`, `esFinal`, `formatoUtilidad`, `SesionResumen`, `EnlaceInvitacion` y `Evento`;
  - de la Task 2: `EtiquetaEstadoSesion`;
  - de la Task 4: `DialogoEnlaces`, `DialogoCancelar` (con `borrador={false}`), `ResumenConfiguracion`, `simularRutas` y `llamadaA`;
  - lo que ya existe: `haceCuanto` y `ConfirmarAccion`.
- Produces:
  - `TablaSesiones({ evento, esComprador, alReenviar })`;
  - la página `/negociaciones/:id`, que ahora, si la negociación no está en borrador, muestra sus sesiones y se actualiza cada 3 s mientras está abierta.
- API:
  - `POST /negociacion/sesiones/{id}/invitacion` → `EnlaceInvitacion`. El enlace se muestra una sola vez;
  - `POST /negociacion/eventos/{id}/cancelar` con `{ motivo }`, en una negociación abierta.

- [ ] **Step 1: Write the failing tests**

En `web/src/paginas/Negociacion.test.tsx`:

1. Agregue `vi.useRealTimers()` al `afterEach` del archivo.
2. Agregue después de `BORRADOR`:

```tsx
const SESIONES = [
  {
    id: "s1",
    proveedor_id: "p1",
    proveedor_nombre: "Nube Norte",
    estado: "escalada",
    modo: "comprador",
    ronda: 2,
    utilidad: 0.413,
    correo_estado: "enviado",
    correo_error: null,
    fuera_de_limites: false,
    actualizado_en: "2026-10-14T18:30:00Z",
  },
  {
    id: "s2",
    proveedor_id: "p2",
    proveedor_nombre: "Datos del Sur",
    estado: "invitada",
    modo: "agente",
    ronda: 0,
    utilidad: null,
    correo_estado: "fallido",
    correo_error: "No se pudo entregar el correo al servidor de correo.",
    fuera_de_limites: false,
    actualizado_en: "2026-10-14T18:00:00Z",
  },
]

const ABIERTA = {
  ...BORRADOR,
  estado: "abierto",
  publicado_en: "2026-10-14T18:00:00Z",
  version: 4,
  sesiones: SESIONES,
}
```

3. Agregue al final:

```tsx
describe("Negociacion abierta", () => {
  it("muestra sus sesiones con estado, quién atiende, ronda, utilidad y correo", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(ABIERTA) })
    const { container } = abrir()
    expect(
      await screen.findByRole("link", { name: "Nube Norte" })
    ).toHaveAttribute("href", `/negociaciones/${ID}/sesiones/s1`)
    const fila = screen.getByRole("row", { name: /Nube Norte/ })
    expect(within(fila).getByText("Escalada")).toBeInTheDocument()
    expect(within(fila).getByText("Persona")).toBeInTheDocument()
    expect(within(fila).getByText("2 de 6")).toBeInTheDocument()
    expect(within(fila).getByText("41 %")).toBeInTheDocument()
    const otra = screen.getByRole("row", { name: /Datos del Sur/ })
    expect(within(otra).getByText("Sin ofertas")).toBeInTheDocument()
    expect(within(otra).getByText("No se envió")).toBeInTheDocument()
    expect(within(otra).getByText("—")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("reenviar una invitación pide confirmar y muestra el enlace nuevo una sola vez", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ABIERTA),
      "POST /api/negociacion/sesiones/s2/invitacion": () =>
        respuestaJson({
          sesion_id: "s2",
          proveedor_nombre: "Datos del Sur",
          destinatario: "ana@datossur.example",
          enlace: "http://localhost:8080/portal#t=nuevo-456",
          correo_estado: "enviado",
        }),
    })
    const { cliente } = abrir()
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Reenviar la invitación a Datos del Sur",
      })
    )
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Reenviar",
      })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Enlace de invitación",
    })
    expect(
      within(dialogo).getByText("http://localhost:8080/portal#t=nuevo-456")
    ).toBeInTheDocument()
    await userEvent.click(within(dialogo).getByRole("button", { name: "Listo" }))
    await esperarSinEnMutaciones(cliente, "nuevo-456")
    expect(
      llamadaA(api, "/api/negociacion/sesiones/s2/invitacion", "POST")
    ).toBeTruthy()
  })

  it("solo el comprador puede cancelar y reenviar", async () => {
    sesionDePrueba.roles = ["aprobador"]
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(ABIERTA) })
    abrir()
    await screen.findByRole("link", { name: "Nube Norte" })
    expect(
      screen.queryByRole("button", { name: /Reenviar/ })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Cancelar negociación" })
    ).not.toBeInTheDocument()
  })

  it("cancela una negociación abierta con su motivo", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ABIERTA),
      [`POST ${RUTA}/cancelar`]: () =>
        respuestaJson({ ...ABIERTA, estado: "cancelado" }),
    })
    abrir()
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancelar negociación" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Cancelar la negociación",
    })
    expect(dialogo).toHaveTextContent("Los enlaces dejan de servir")
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo"),
      "Cambió el presupuesto"
    )
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Cancelar negociación" })
    )
    expect(
      await screen.findByText("Se canceló la negociación.")
    ).toBeInTheDocument()
    expect(llamadaA(api, `${RUTA}/cancelar`, "POST").cuerpo).toEqual({
      motivo: "Cambió el presupuesto",
    })
  })

  it("se actualiza cada 3 s mientras está abierta", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(ABIERTA) })
    abrir()
    await screen.findByRole("link", { name: "Nube Norte" })
    const lecturas = () => api.mock.calls.filter(([url]) => url === RUTA).length
    expect(lecturas()).toBe(1)
    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(lecturas()).toBe(2))
  })

  it("un borrador no se vuelve a consultar solo", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(BORRADOR) })
    abrir()
    await screen.findByLabelText("Ideal (Correo en la nube)")
    await vi.advanceTimersByTimeAsync(3100)
    expect(api.mock.calls.filter(([url]) => url === RUTA)).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run (desde `web/`): `npx vitest run src/paginas/Negociacion.test.tsx`
Expected: FAIL en «Negociacion abierta»: no hay enlace «Nube Norte» (la página aún no muestra sesiones) y no hay consulta cada 3 s.

- [ ] **Step 3: Write the implementation**

`web/src/componentes/negociacion/TablaSesiones.tsx`:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Bot, TriangleAlert, UserRound } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { EtiquetaEstadoSesion } from "@/componentes/negociacion/Etiquetas"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { haceCuanto } from "@/fechas"
import {
  esFinal,
  formatoUtilidad,
  type EnlaceInvitacion,
  type EstadoCorreo,
  type Evento,
  type SesionResumen,
} from "@/negociacion"

const CORREO: Record<EstadoCorreo, string> = {
  pendiente: "Pendiente",
  enviado: "Enviada",
  fallido: "No se envió",
}

/** Una fila por proveedor: cómo va su sesión, quién la atiende y su invitación (spec §10.1). */
export function TablaSesiones({
  evento,
  esComprador,
  alReenviar,
}: {
  evento: Evento
  esComprador: boolean
  alReenviar: (enlace: EnlaceInvitacion) => void
}) {
  const token = useToken()
  const cliente = useQueryClient()
  const [aviso, setAviso] = useState("")
  const reenviar = useMutation({
    mutationFn: (s: SesionResumen) =>
      pedir<EnlaceInvitacion>(
        `/negociacion/sesiones/${encodeURIComponent(s.id)}/invitacion`,
        token,
        { method: "POST" }
      ),
    // El enlace solo vive en el diálogo: al terminar, reset() (en `mutate`) suelta la mutación y
    // gcTime 0 la borra de la caché.
    gcTime: 0,
    onSuccess: async (enlace) => {
      setAviso("")
      alReenviar(enlace)
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => setAviso(error.message),
  })

  return (
    <Seccion
      titulo="Sesiones"
      descripcion={
        <>
          Una por proveedor. «Qué tan buena es para usted» compara su última
          oferta con su <Termino clave="ideal">ideal</Termino> y su{" "}
          <Termino clave="limite">límite</Termino>.
        </>
      }
    >
      <p
        role="status"
        className={aviso ? "mb-2 text-sm text-destructive" : "sr-only"}
      >
        {aviso}
      </p>
      {evento.sesiones.length === 0 ? (
        <EstadoVacio
          titulo="Sin sesiones"
          descripcion="Las sesiones se crean al publicar la negociación."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Proveedor</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Atiende</TableHead>
              <TableHead>
                <Termino clave="ronda">Ronda</Termino>
              </TableHead>
              <TableHead className="text-right">
                Qué tan buena es para usted
              </TableHead>
              <TableHead>Última actividad</TableHead>
              <TableHead>Invitación</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {evento.sesiones.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="whitespace-normal">
                  <Link
                    to={`/negociaciones/${encodeURIComponent(evento.id)}/sesiones/${encodeURIComponent(s.id)}`}
                    className="text-accent hover:underline"
                  >
                    {s.proveedor_nombre}
                  </Link>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    <EtiquetaEstadoSesion estado={s.estado} />
                    {s.fuera_de_limites && (
                      <Badge variant="warning">
                        <TriangleAlert aria-hidden />
                        Fuera de límites
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <span className="inline-flex items-center gap-1">
                    {s.modo === "agente" ? (
                      <>
                        <Bot aria-hidden className="size-4" />
                        Agente
                      </>
                    ) : (
                      <>
                        <UserRound aria-hidden className="size-4" />
                        Persona
                      </>
                    )}
                  </span>
                </TableCell>
                <TableCell className="tabular-nums">
                  {s.ronda === 0
                    ? "Sin ofertas"
                    : `${s.ronda} de ${evento.rondas_max}`}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatoUtilidad(s.utilidad)}
                </TableCell>
                <TableCell>{haceCuanto(s.actualizado_en)}</TableCell>
                <TableCell className="min-w-40 whitespace-normal">
                  <div className="space-y-1">
                    <p
                      className={
                        s.correo_estado === "fallido"
                          ? "text-destructive"
                          : undefined
                      }
                    >
                      {CORREO[s.correo_estado]}
                    </p>
                    {s.correo_error && (
                      <p className="text-xs text-muted-foreground">
                        {s.correo_error}
                      </p>
                    )}
                    {esComprador &&
                      evento.estado === "abierto" &&
                      !esFinal(s.estado) && (
                        <ConfirmarAccion
                          titulo={`¿Reenviar la invitación a ${s.proveedor_nombre}?`}
                          descripcion="Se envía un enlace nuevo por correo y el anterior deja de servir."
                          textoConfirmar="Reenviar"
                          alConfirmar={() => {
                            if (!reenviar.isPending)
                              reenviar.mutate(s, {
                                onSuccess: () => reenviar.reset(),
                              })
                          }}
                        >
                          <Button variant="outline" size="sm">
                            Reenviar
                            <span className="sr-only">
                              {" "}
                              la invitación a {s.proveedor_nombre}
                            </span>
                          </Button>
                        </ConfirmarAccion>
                      )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Seccion>
  )
}
```

En `web/src/paginas/Negociacion.tsx`:

1. Cambie el import de `ContenidoConsulta` por:

```tsx
import { ContenidoVivo } from "@/componentes/negociacion/ContenidoVivo"
import { DialogoCancelar } from "@/componentes/negociacion/DialogoCancelar"
import { TablaSesiones } from "@/componentes/negociacion/TablaSesiones"
```

2. Cambie la consulta por:

```tsx
  const consulta = useNegociacion<Evento>(`/eventos/${encodeURIComponent(id)}`, {
    // Supervisión en vivo (spec D6): solo mientras la negociación está abierta.
    refetchInterval: (q) => (q.state.data?.estado === "abierto" ? 3000 : false),
  })
```

3. Cambie `<ContenidoConsulta consulta={consulta}>` y su cierre por `<ContenidoVivo consulta={consulta}>` … `</ContenidoVivo>`.

4. Reemplace la rama `: (<ResumenConfiguracion evento={evento} />)` por:

```tsx
            ) : (
              <>
                {esComprador && evento.estado === "abierto" && (
                  <div className="flex justify-end">
                    <DialogoCancelar
                      ruta={`/negociacion/eventos/${encodeURIComponent(evento.id)}`}
                      borrador={false}
                      alCancelar={() => setAviso("Se canceló la negociación.")}
                    />
                  </div>
                )}
                {evento.estado !== "borrador" && (
                  <TablaSesiones
                    evento={evento}
                    esComprador={esComprador}
                    alReenviar={(enlace) => setEnlaces([enlace])}
                  />
                )}
                <ResumenConfiguracion evento={evento} />
              </>
            )}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/paginas/Negociacion.test.tsx`
Expected: PASS, incluidas las pruebas de borrador de la Task 4.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/componentes/negociacion/TablaSesiones.tsx web/src/paginas/Negociacion.tsx web/src/paginas/Negociacion.test.tsx
git commit -m "feat(web): sesiones de una negociación abierta, reenvío de invitaciones y cancelación" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Supervisión de una sesión

**Files:**
- Create: `web/src/componentes/negociacion/ValoresOferta.tsx`
- Create: `web/src/componentes/negociacion/Conversacion.tsx`
- Create: `web/src/componentes/negociacion/TablaOfertas.tsx`
- Create: `web/src/paginas/SesionNegociacion.tsx`
- Create: `web/src/paginas/SesionNegociacion.test.tsx`
- Modify: `web/src/rutas.tsx`

**Interfaces:**
- Consumes:
  - de la Task 1: `useNegociacion`, `ContenidoVivo`, `esFinal`, `explicarDecision`, `formatoUtilidad`, `formatoTermino`, `NOMBRES_AUTOR`, `SesionDetalle`, `MensajeSesion`, `Valores` y `ClavePalanca`;
  - de la Task 2: `EtiquetaEstadoSesion`;
  - de la Task 4: `simularRutas` y `llamadaA`.
- Produces:
  - `ValoresOferta({ valores, lineas, palancas, moneda })`, que reutiliza el portal (Task 8);
  - `Conversacion({ datos })` y `TablaOfertas({ datos })`;
  - la página `SesionNegociacion` en `/negociaciones/:id/sesiones/:sesion`, con el componente interno `Supervision({ datos })`. La Task 7 le agrega el formulario de respuesta.
- API:
  - `GET /negociacion/sesiones/{id}` → `SesionDetalle`, cada 3 s hasta que la sesión termina;
  - `POST /negociacion/sesiones/{id}/control` con `{ "accion": "tomar" | "devolver" }`.

- [ ] **Step 1: Write the failing test**

`web/src/paginas/SesionNegociacion.test.tsx`:

```tsx
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SesionNegociacion } from "@/paginas/SesionNegociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const SID = "s1"
const RUTA = `/api/negociacion/sesiones/${SID}`

const SESION = {
  id: SID,
  evento_id: "e1",
  folio: "NEG-2026-0001",
  titulo: "Licencias de correo 2027",
  moneda: "MXN",
  proveedor_id: "p1",
  proveedor_nombre: "Nube Norte",
  destinatario: "lucia@nubenorte.example",
  estado: "activa",
  modo: "agente",
  ronda: 1,
  rondas_max: 6,
  fuera_de_limites: false,
  correo_estado: "enviado",
  correo_error: null,
  lineas: [
    {
      id: "l1",
      nombre: "Correo en la nube",
      unidad: "usuario_mes",
      cantidad: "250.0000",
      ideal: "88.00",
      limite: "95.00",
    },
  ],
  palancas: [
    {
      clave: "precio",
      nombre: "Precio unitario",
      unidad: "MXN",
      peso: 80,
      ideal: null,
      limite: null,
    },
    {
      clave: "plazo_pago_dias",
      nombre: "Plazo de pago",
      unidad: "días",
      peso: 20,
      ideal: "60",
      limite: "30",
    },
  ],
  mensajes: [
    {
      id: "m1",
      autor: "proveedor",
      texto: "Es nuestra mejor oferta.",
      ronda: 1,
      fecha: "2026-10-14T18:10:00Z",
      oferta_id: "o1",
      decision: null,
    },
    {
      id: "m2",
      autor: "agente",
      texto: "Gracias por su oferta. Le proponemos lo siguiente.",
      ronda: 1,
      fecha: "2026-10-14T18:10:01Z",
      oferta_id: "o2",
      decision: {
        accion: "contraofertar",
        t: 1,
        T: 6,
        utilidad_oferta: 0.2,
        valida: false,
        hay_mejor_oferta: false,
        objetivo: 0.86,
        utilidad_contraoferta: 0.862,
      },
    },
  ],
  ofertas: [
    {
      id: "o1",
      autor: "proveedor",
      ronda: 1,
      valores: { precios: { l1: "120.00" }, palancas: { plazo_pago_dias: "15" } },
      utilidad: 0.2,
      valida: false,
      fuera_de_limites_confirmada: false,
      fecha: "2026-10-14T18:10:00Z",
    },
    {
      id: "o2",
      autor: "agente",
      ronda: 1,
      valores: { precios: { l1: "89.00" }, palancas: { plazo_pago_dias: "55" } },
      utilidad: 0.862,
      valida: true,
      fuera_de_limites_confirmada: false,
      fecha: "2026-10-14T18:10:01Z",
    },
  ],
}

function abrir() {
  return renderizarPagina(<SesionNegociacion />, {
    ruta: `/negociaciones/e1/sesiones/${SID}`,
    patron: "/negociaciones/:id/sesiones/:sesion",
  })
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("SesionNegociacion", () => {
  it("muestra un esqueleto mientras carga y, si falla, el error con Reintentar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    abrir()
    expect(await screen.findByText("Cargando…")).toBeInTheDocument()
    cleanup()
    vi.unstubAllGlobals()
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({ title: "No encontrado", detail: "La sesión no existe." }, 404),
    })
    abrir()
    expect(await screen.findByText("La sesión no existe.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument()
  })

  it("muestra la conversación, las ofertas y por qué respondió el agente", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(SESION) })
    const { container } = abrir()
    expect(await screen.findByText("Es nuestra mejor oferta.")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Volver a la negociación" })
    ).toHaveAttribute("href", "/negociaciones/e1")
    expect(screen.getByText("¿Por qué respondió esto?")).toBeInTheDocument()
    expect(
      screen.getByText(/^La oferta del proveedor vale 20 % para usted/)
    ).toBeInTheDocument()
    const fila = screen.getByRole("row", { name: /^1 Proveedor/ })
    expect(within(fila).getByText("20 %")).toBeInTheDocument()
    expect(within(fila).getByText("No")).toBeInTheDocument()
    expect(within(fila).getByText("15 días")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("toma el control y después lo devuelve", async () => {
    let modo = "agente"
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson({ ...SESION, modo }),
      [`POST ${RUTA}/control`]: () => {
        modo = modo === "agente" ? "comprador" : "agente"
        return respuestaJson({ ...SESION, modo })
      },
    })
    abrir()
    await userEvent.click(
      await screen.findByRole("button", { name: "Tomar el control" })
    )
    expect(
      await screen.findByText(
        "Ahora usted atiende esta sesión: el agente no responderá hasta que la devuelva."
      )
    ).toBeInTheDocument()
    expect(llamadaA(api, `${RUTA}/control`, "POST").cuerpo).toEqual({
      accion: "tomar",
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Devolver al agente" })
    )
    expect(
      await screen.findByText("El agente vuelve a atender la sesión.")
    ).toBeInTheDocument()
    expect(llamadaA(api, `${RUTA}/control`, "POST").cuerpo).toEqual({
      accion: "devolver",
    })
  })

  it("el aprobador supervisa sin botones de control", async () => {
    sesionDePrueba.roles = ["aprobador"]
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(SESION) })
    abrir()
    await screen.findByText("Es nuestra mejor oferta.")
    expect(
      screen.queryByRole("button", { name: "Tomar el control" })
    ).not.toBeInTheDocument()
  })

  it("solo anuncia los mensajes del proveedor que llegan después de abrir", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let lecturas = 0
    const nuevo = {
      id: "m3",
      autor: "proveedor",
      texto: "Bajamos a 100.",
      ronda: 2,
      fecha: "2026-10-14T18:20:00Z",
      oferta_id: null,
      decision: null,
    }
    simularRutas({
      [`GET ${RUTA}`]: () => {
        lecturas += 1
        return respuestaJson(
          lecturas === 1
            ? SESION
            : { ...SESION, mensajes: [...SESION.mensajes, nuevo] }
        )
      },
    })
    abrir()
    await screen.findByText("Es nuestra mejor oferta.")
    expect(
      screen.queryByText(/Nuevo mensaje del proveedor/)
    ).not.toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(3100)
    expect(await screen.findByText("Bajamos a 100.")).toBeInTheDocument()
    expect(
      screen.getByText(/^Nuevo mensaje del proveedor, /)
    ).toBeInTheDocument()
  })

  it("una sesión terminada no ofrece el control ni se vuelve a consultar", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({ ...SESION, estado: "acuerdo_tentativo" }),
    })
    abrir()
    expect(await screen.findByText("Acuerdo tentativo")).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Tomar el control" })
    ).not.toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(3100)
    expect(api.mock.calls.filter(([url]) => url === RUTA)).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (desde `web/`): `npx vitest run src/paginas/SesionNegociacion.test.tsx`
Expected: FAIL con `Failed to resolve import "@/paginas/SesionNegociacion"`.

- [ ] **Step 3: Write the implementation**

`web/src/componentes/negociacion/ValoresOferta.tsx`:

```tsx
import { porUnidad } from "@/inteligencia"
import { formatoTermino, type ClavePalanca, type Valores } from "@/negociacion"
import { formatoMoneda } from "@/tipos"

type Linea = { id: string; nombre: string; unidad: string }
type Palanca = { clave: ClavePalanca; nombre: string; unidad: string }

/** Los valores de una oferta: precio unitario por línea y valor por palanca, con su unidad. */
export function ValoresOferta({
  valores,
  lineas,
  palancas,
  moneda,
}: {
  valores: Valores
  lineas: Linea[]
  palancas: Palanca[]
  moneda: string
}) {
  const filas: [string, string][] = [
    ...lineas
      .filter((l) => valores.precios[l.id] !== undefined)
      .map((l): [string, string] => [
        l.nombre,
        `${formatoMoneda(valores.precios[l.id], moneda)} ${porUnidad(l.unidad)}`,
      ]),
    ...palancas
      .filter((p) => p.clave !== "precio" && valores.palancas[p.clave] !== undefined)
      .map((p): [string, string] => [
        p.nombre,
        formatoTermino(valores.palancas[p.clave], p.unidad, moneda),
      ]),
  ]
  return (
    <dl className="grid gap-x-4 gap-y-1 rounded-md bg-muted/50 p-2 text-sm sm:grid-cols-[auto_1fr]">
      {filas.map(([nombre, valor], i) => (
        // El índice evita claves repetidas: dos líneas pueden tener el mismo servicio.
        <div key={i} className="contents">
          <dt className="text-muted-foreground">{nombre}</dt>
          <dd className="font-medium tabular-nums">{valor}</dd>
        </div>
      ))}
    </dl>
  )
}
```

`web/src/componentes/negociacion/Conversacion.tsx`:

```tsx
import { EstadoVacio } from "@/componentes/Estados"
import { ValoresOferta } from "@/componentes/negociacion/ValoresOferta"
import { formatoFechaHora } from "@/fechas"
import { cn } from "@/lib/utils"
import {
  NOMBRES_AUTOR,
  explicarDecision,
  type SesionDetalle,
} from "@/negociacion"

/** La conversación por ronda; cada respuesta del agente explica por qué respondió así. */
export function Conversacion({ datos }: { datos: SesionDetalle }) {
  const ofertas = new Map(datos.ofertas.map((o) => [o.id, o]))
  if (datos.mensajes.length === 0) {
    return (
      <EstadoVacio
        titulo="Aún no hay mensajes"
        descripcion="El proveedor todavía no envía su primera oferta."
      />
    )
  }
  return (
    <ol className="space-y-3">
      {datos.mensajes.map((m) => {
        const oferta = m.oferta_id ? ofertas.get(m.oferta_id) : undefined
        return (
          <li
            key={m.id}
            className={cn(
              "space-y-2 rounded-lg border p-3",
              m.autor === "proveedor" && "bg-muted/40"
            )}
          >
            <p className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                {NOMBRES_AUTOR[m.autor]}
              </span>
              <span>{`Ronda ${m.ronda}`}</span>
              <span>{formatoFechaHora(m.fecha)}</span>
            </p>
            {m.texto && (
              <p className="text-sm break-words whitespace-pre-wrap">{m.texto}</p>
            )}
            {oferta && (
              <ValoresOferta
                valores={oferta.valores}
                lineas={datos.lineas}
                palancas={datos.palancas}
                moneda={datos.moneda}
              />
            )}
            {m.decision && (
              <details className="text-sm">
                <summary className="cursor-pointer rounded-sm text-accent outline-hidden focus-visible:ring-2 focus-visible:ring-ring">
                  ¿Por qué respondió esto?
                </summary>
                <p className="mt-1 text-muted-foreground">
                  {explicarDecision(m.decision)}
                </p>
              </details>
            )}
          </li>
        )
      })}
    </ol>
  )
}
```

`web/src/componentes/negociacion/TablaOfertas.tsx`:

```tsx
import { CircleCheck, CircleX } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  NOMBRES_AUTOR,
  formatoTermino,
  formatoUtilidad,
  type SesionDetalle,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

/** Todas las ofertas de la sesión, con sus valores, lo que valen para el comprador y su validez. */
export function TablaOfertas({ datos }: { datos: SesionDetalle }) {
  if (datos.ofertas.length === 0) {
    return <p className="text-sm text-muted-foreground">Aún no hay ofertas.</p>
  }
  const palancas = datos.palancas.filter((p) => p.clave !== "precio")
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ronda</TableHead>
          <TableHead>De</TableHead>
          {datos.lineas.map((l) => (
            <TableHead key={l.id} className="text-right">
              {l.nombre}
            </TableHead>
          ))}
          {palancas.map((p) => (
            <TableHead key={p.clave} className="text-right">
              {p.nombre}
            </TableHead>
          ))}
          <TableHead className="text-right">Para usted</TableHead>
          <TableHead>¿Dentro de sus límites?</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {datos.ofertas.map((o) => (
          <TableRow key={o.id}>
            <TableCell className="tabular-nums">{o.ronda}</TableCell>
            <TableCell>{NOMBRES_AUTOR[o.autor]}</TableCell>
            {datos.lineas.map((l) => (
              <TableCell key={l.id} className="text-right tabular-nums">
                {o.valores.precios[l.id]
                  ? formatoMoneda(o.valores.precios[l.id], datos.moneda)
                  : "—"}
              </TableCell>
            ))}
            {palancas.map((p) => (
              <TableCell key={p.clave} className="text-right tabular-nums">
                {o.valores.palancas[p.clave]
                  ? formatoTermino(o.valores.palancas[p.clave], p.unidad, datos.moneda)
                  : "—"}
              </TableCell>
            ))}
            <TableCell className="text-right tabular-nums">
              {formatoUtilidad(o.utilidad)}
            </TableCell>
            <TableCell>
              {o.valida ? (
                <span className="inline-flex items-center gap-1 text-success">
                  <CircleCheck aria-hidden className="size-4" />
                  Sí
                </span>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <CircleX aria-hidden className="size-4 text-destructive" />
                  No
                  {o.fuera_de_limites_confirmada && " (lo confirmó Compras)"}
                </span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

`web/src/paginas/SesionNegociacion.tsx`:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Bot, Hand, TriangleAlert } from "lucide-react"
import { useState } from "react"
import { Link, useParams } from "react-router"
import { enviarJson, pedir } from "@/api"
import { useRoles, useToken } from "@/auth"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { Seccion } from "@/componentes/Seccion"
import { Termino } from "@/componentes/Termino"
import { ContenidoVivo } from "@/componentes/negociacion/ContenidoVivo"
import { Conversacion } from "@/componentes/negociacion/Conversacion"
import { EtiquetaEstadoSesion } from "@/componentes/negociacion/Etiquetas"
import { TablaOfertas } from "@/componentes/negociacion/TablaOfertas"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatoFechaHora } from "@/fechas"
import {
  esFinal,
  formatoTermino,
  useNegociacion,
  type MensajeSesion,
  type SesionDetalle,
} from "@/negociacion"
import { formatoMoneda } from "@/tipos"

function ultimoDelProveedor(mensajes: MensajeSesion[]) {
  return mensajes.findLast((m) => m.autor === "proveedor")
}

export function SesionNegociacion() {
  const { sesion = "" } = useParams()
  const consulta = useNegociacion<SesionDetalle>(
    `/sesiones/${encodeURIComponent(sesion)}`,
    {
      // Supervisión en vivo (spec D6); una sesión terminada ya no cambia.
      refetchInterval: (q) =>
        q.state.data && esFinal(q.state.data.estado) ? false : 3000,
    }
  )
  return (
    <div className="space-y-6">
      <ContenidoVivo consulta={consulta}>
        {(datos) => <Supervision datos={datos} />}
      </ContenidoVivo>
    </div>
  )
}

function Supervision({ datos }: { datos: SesionDetalle }) {
  const esComprador = useRoles().includes("comprador")
  // Solo se anuncia lo que llega después de abrir la página, no lo que ya estaba (spec §10.1).
  const [vistoAlAbrir] = useState(
    () => ultimoDelProveedor(datos.mensajes)?.id ?? null
  )
  const ultimo = ultimoDelProveedor(datos.mensajes)
  const anuncio =
    ultimo && ultimo.id !== vistoAlAbrir
      ? `Nuevo mensaje del proveedor, ${formatoFechaHora(ultimo.fecha)}`
      : ""

  return (
    <>
      <EncabezadoPagina
        titulo={datos.proveedor_nombre}
        descripcion={`${datos.folio} · ${datos.titulo}`}
        acciones={
          <Button asChild variant="outline">
            <Link to={`/negociaciones/${encodeURIComponent(datos.evento_id)}`}>
              <ArrowLeft aria-hidden />
              Volver a la negociación
            </Link>
          </Button>
        }
      />
      <p aria-live="polite" className="sr-only">
        {anuncio}
      </p>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <EtiquetaEstadoSesion estado={datos.estado} />
        <span>
          {datos.modo === "agente"
            ? "Atiende el agente"
            : "Atiende una persona de Compras"}
        </span>
        <span>
          · <Termino clave="ronda">Ronda</Termino>{" "}
          {`${datos.ronda} de ${datos.rondas_max}`}
        </span>
        {datos.fuera_de_limites && (
          <Badge variant="warning">
            <TriangleAlert aria-hidden />
            Acuerdo fuera de sus límites: lo verá el aprobador
          </Badge>
        )}
      </div>
      {datos.estado === "acuerdo_tentativo" && (
        <p className="text-sm">
          Quedó un{" "}
          <Termino clave="acuerdoTentativo">acuerdo tentativo</Termino>: no es
          vinculante hasta que se adjudique y se apruebe.
        </p>
      )}
      {esComprador && !esFinal(datos.estado) && <Control datos={datos} />}
      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <Seccion titulo="Conversación">
          <Conversacion datos={datos} />
        </Seccion>
        <Seccion titulo="Sus límites" descripcion="El proveedor nunca los ve.">
          <Limites datos={datos} />
        </Seccion>
      </div>
      <Seccion
        titulo="Ofertas"
        descripcion="«Para usted» es qué tan buena es cada oferta frente a su ideal y su límite."
      >
        <TablaOfertas datos={datos} />
      </Seccion>
    </>
  )
}

function Control({ datos }: { datos: SesionDetalle }) {
  const token = useToken()
  const cliente = useQueryClient()
  const [aviso, setAviso] = useState("")
  const cambiar = useMutation({
    mutationFn: (accion: "tomar" | "devolver") =>
      pedir<SesionDetalle>(
        `/negociacion/sesiones/${encodeURIComponent(datos.id)}/control`,
        token,
        enviarJson("POST", { accion })
      ),
    onSuccess: async (_respuesta, accion) => {
      setAviso(
        accion === "tomar"
          ? "Ahora usted atiende esta sesión: el agente no responderá hasta que la devuelva."
          : "El agente vuelve a atender la sesión."
      )
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error) => setAviso(error.message),
  })
  const tomar = datos.modo === "agente"
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Un solo botón que cambia de texto: el foco se queda en él al tomar o devolver. */}
      <Button
        variant={tomar ? "default" : "outline"}
        aria-disabled={cambiar.isPending}
        onClick={() => {
          if (!cambiar.isPending) cambiar.mutate(tomar ? "tomar" : "devolver")
        }}
      >
        {tomar ? <Hand aria-hidden /> : <Bot aria-hidden />}
        {tomar ? "Tomar el control" : "Devolver al agente"}
      </Button>
      <p role="status" className="text-sm text-muted-foreground">
        {aviso}
      </p>
    </div>
  )
}

function Limites({ datos }: { datos: SesionDetalle }) {
  const monto = (valor: string | null) =>
    valor ? formatoMoneda(valor, datos.moneda) : "—"
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Término</TableHead>
          <TableHead className="text-right">Ideal</TableHead>
          <TableHead className="text-right">Límite</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {datos.lineas.map((l) => (
          <TableRow key={l.id}>
            <TableCell className="whitespace-normal">{`Precio: ${l.nombre}`}</TableCell>
            <TableCell className="text-right tabular-nums">{monto(l.ideal)}</TableCell>
            <TableCell className="text-right tabular-nums">{monto(l.limite)}</TableCell>
          </TableRow>
        ))}
        {datos.palancas
          .filter((p) => p.clave !== "precio")
          .map((p) => (
            <TableRow key={p.clave}>
              <TableCell className="whitespace-normal">{`${p.nombre} (peso ${p.peso})`}</TableCell>
              <TableCell className="text-right tabular-nums">
                {p.ideal ? formatoTermino(p.ideal, p.unidad, datos.moneda) : "—"}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {p.limite ? formatoTermino(p.limite, p.unidad, datos.moneda) : "—"}
              </TableCell>
            </TableRow>
          ))}
      </TableBody>
    </Table>
  )
}
```

En `web/src/rutas.tsx`, agregue después de la ruta `negociaciones/:id`:

```tsx
  {
    path: "negociaciones/:id/sesiones/:sesion",
    lazy: async () => ({
      Component: (await import("@/paginas/SesionNegociacion"))
        .SesionNegociacion,
    }),
  },
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/paginas/SesionNegociacion.test.tsx src/rutas.test.ts`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/componentes/negociacion web/src/paginas/SesionNegociacion.tsx web/src/paginas/SesionNegociacion.test.tsx web/src/rutas.tsx
git commit -m "feat(web): supervisión de una sesión con la traza explicada y el control" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Respuesta manual del comprador

**Files:**
- Create: `web/src/componentes/negociacion/CamposValores.tsx`
- Create: `web/src/componentes/negociacion/RespuestaManual.tsx`
- Modify: `web/src/paginas/SesionNegociacion.tsx`
- Modify: `web/src/paginas/SesionNegociacion.test.tsx`

**Interfaces:**
- Consumes:
  - de la Task 1: `crearClaves`, `PASOS`, `Valores`, `ClavePalanca`, `SesionDetalle` y `Textarea`;
  - de la Task 3: `Campo`;
  - de la Task 6: `Supervision` (en `SesionNegociacion.tsx`), `simularRutas`, `llamadaA` y el `SESION` de las pruebas;
  - lo que ya existe: `ConfirmarAccion` y los `AlertDialog*` de `@/components/ui/alert-dialog`.
- Produces:
  - `CamposValores({ id, lineas, palancas, moneda, valores, alCambiar, errores, prefijo })`, que el portal (Task 8) reutiliza con `prefijo="valores"`;
  - `valoresVacios(lineas, palancas): Valores`;
  - `valoresCapturados(valores: Valores): Valores`, que quita los valores vacíos;
  - `RespuestaManual({ datos })`. Se muestra cuando el comprador atiende (`modo = "comprador"`) una sesión no terminada.
- API: `POST /negociacion/sesiones/{id}/respuestas`, con `Idempotency-Key` y uno de estos cuerpos:
  - `{ tipo: "mensaje", texto, contraoferta?, confirmar_fuera_de_limites }`;
  - `{ tipo: "aceptar", texto: "", confirmar_fuera_de_limites }`;
  - `{ tipo: "cerrar", texto, confirmar_fuera_de_limites }`.

  Una contraoferta o una aceptación fuera de límites sin confirmación responde 422 con `codigo: "fuera_de_limites"`. Los errores de campo llegan como `contraoferta.precios.{id_linea}` y `contraoferta.palancas.{clave}`.

- [ ] **Step 1: Write the failing tests**

Agregue al final de `web/src/paginas/SesionNegociacion.test.tsx`:

```tsx
const ESCALADA = { ...SESION, estado: "escalada", modo: "comprador" }

async function escribirContraoferta(precio: string) {
  await userEvent.type(
    await screen.findByLabelText("Mensaje para el proveedor"),
    "Le proponemos esto."
  )
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Incluir una contraoferta" })
  )
  const campo = screen.getByLabelText("Precio de Correo en la nube")
  await userEvent.clear(campo)
  await userEvent.type(campo, precio)
}

describe("respuesta manual", () => {
  it("responde a mano con una contraoferta y manda Idempotency-Key", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () => respuestaJson(ESCALADA),
    })
    abrir()
    await userEvent.type(
      await screen.findByLabelText("Mensaje para el proveedor"),
      "Podemos llegar a 90."
    )
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Incluir una contraoferta" })
    )
    // Empieza con la última propuesta del agente.
    expect(screen.getByLabelText("Precio de Correo en la nube")).toHaveValue(89)
    expect(screen.getByLabelText("Plazo de pago (días)")).toHaveValue(55)
    const precio = screen.getByLabelText("Precio de Correo en la nube")
    await userEvent.clear(precio)
    await userEvent.type(precio, "90.00")
    await userEvent.click(screen.getByRole("button", { name: "Enviar respuesta" }))
    expect(await screen.findByText("Se envió su respuesta.")).toBeInTheDocument()
    const { cuerpo, cabeceras } = llamadaA(api, `${RUTA}/respuestas`, "POST")
    expect(cuerpo).toEqual({
      tipo: "mensaje",
      texto: "Podemos llegar a 90.",
      contraoferta: { precios: { l1: "90.00" }, palancas: { plazo_pago_dias: "55" } },
      confirmar_fuera_de_limites: false,
    })
    expect(cabeceras.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/)
  })

  it("una contraoferta fuera de límites pide confirmar y la reenvía marcada", async () => {
    let intentos = 0
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () => {
        intentos += 1
        return intentos === 1
          ? respuestaJson(
              {
                title: "Solicitud inválida",
                detail: "La contraoferta sale de sus límites.",
                codigo: "fuera_de_limites",
              },
              422
            )
          : respuestaJson(ESCALADA)
      },
    })
    abrir()
    await escribirContraoferta("120.00")
    await userEvent.click(screen.getByRole("button", { name: "Enviar respuesta" }))
    const aviso = await screen.findByRole("alertdialog", {
      name: "Esto sale de sus límites",
    })
    expect(aviso).toHaveTextContent("el aprobador lo verá")
    const primera = llamadaA(api, `${RUTA}/respuestas`, "POST")
    await userEvent.click(
      within(aviso).getByRole("button", { name: "Enviar de todos modos" })
    )
    expect(await screen.findByText("Se envió su respuesta.")).toBeInTheDocument()
    const segunda = llamadaA(api, `${RUTA}/respuestas`, "POST")
    expect(segunda.cuerpo).toMatchObject({ confirmar_fuera_de_limites: true })
    expect(segunda.cabeceras.get("Idempotency-Key")).not.toBe(
      primera.cabeceras.get("Idempotency-Key")
    )
  })

  it("aceptar la última oferta pide confirmación", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () => respuestaJson(ESCALADA),
    })
    abrir()
    await userEvent.click(
      await screen.findByRole("button", { name: "Aceptar la última oferta" })
    )
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Aceptar oferta",
      })
    )
    expect(
      await screen.findByText(
        "Aceptó la última oferta: queda como acuerdo tentativo."
      )
    ).toBeInTheDocument()
    expect(llamadaA(api, `${RUTA}/respuestas`, "POST").cuerpo).toEqual({
      tipo: "aceptar",
      texto: "",
      confirmar_fuera_de_limites: false,
    })
  })

  it("muestra junto al campo el error del servicio", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los campos indicados.",
            codigo: "oferta_invalida",
            errores: [
              {
                campo: "contraoferta.precios.l1",
                mensaje: "Use a lo más 2 decimales.",
              },
            ],
          },
          422
        ),
    })
    abrir()
    // Un valor válido para el navegador: el error lo decide la API simulada.
    await escribirContraoferta("90.10")
    await userEvent.click(screen.getByRole("button", { name: "Enviar respuesta" }))
    expect(await screen.findByText("Use a lo más 2 decimales.")).toBeInTheDocument()
    expect(screen.getByLabelText("Precio de Correo en la nube")).toHaveAttribute(
      "aria-invalid",
      "true"
    )
  })

  it("sin el control no muestra el formulario", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(SESION) })
    abrir()
    await screen.findByText("Es nuestra mejor oferta.")
    expect(
      screen.queryByRole("heading", { name: "Responder al proveedor" })
    ).not.toBeInTheDocument()
  })

  it("el formulario no tiene violaciones de accesibilidad", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(ESCALADA) })
    const { container } = abrir()
    await userEvent.click(
      await screen.findByRole("checkbox", { name: "Incluir una contraoferta" })
    )
    await esperarSinViolaciones(container)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run (desde `web/`): `npx vitest run src/paginas/SesionNegociacion.test.tsx`
Expected: FAIL en «respuesta manual»: no existe el campo «Mensaje para el proveedor».

- [ ] **Step 3: Write the implementation**

`web/src/componentes/negociacion/CamposValores.tsx`:

```tsx
import { Campo } from "@/componentes/negociacion/Campo"
import { Input } from "@/components/ui/input"
import { formatoDecimal, porUnidad } from "@/inteligencia"
import { PASOS, type ClavePalanca, type Valores } from "@/negociacion"

type Linea = { id: string; nombre: string; unidad: string; cantidad: string }
type Palanca = { clave: ClavePalanca; nombre: string; unidad: string }

/** Un valor vacío por línea y por palanca; el precio no es palanca aquí: va por línea. */
export function valoresVacios(lineas: Linea[], palancas: Palanca[]): Valores {
  return {
    precios: Object.fromEntries(lineas.map((l) => [l.id, ""])),
    palancas: Object.fromEntries(
      palancas.filter((p) => p.clave !== "precio").map((p) => [p.clave, ""])
    ),
  }
}

/** Solo lo capturado: un valor vacío no se manda y la API dice junto a su campo que falta. */
export function valoresCapturados(valores: Valores): Valores {
  const llenos = (registro: Record<string, string>) =>
    Object.fromEntries(
      Object.entries(registro)
        .map(([clave, valor]) => [clave, valor.trim()])
        .filter(([, valor]) => valor !== "")
    )
  return { precios: llenos(valores.precios), palancas: llenos(valores.palancas) }
}

/** Un campo por línea (precio unitario) y por palanca, con su unidad y la precisión de la spec §6.4. */
export function CamposValores({
  id,
  lineas,
  palancas,
  moneda,
  valores,
  alCambiar,
  errores,
  prefijo,
}: {
  id: string
  lineas: Linea[]
  palancas: Palanca[]
  moneda: string
  valores: Valores
  alCambiar: (valores: Valores) => void
  errores: Record<string, string>
  prefijo: string
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {lineas.map((l) => (
        <Campo
          key={l.id}
          id={`${id}-precio-${l.id}`}
          etiqueta={`Precio de ${l.nombre}`}
          ayuda={`${moneda} ${porUnidad(l.unidad)} · cantidad: ${formatoDecimal(Number(l.cantidad), 4)}`}
          error={errores[`${prefijo}.precios.${l.id}`]}
        >
          {(control) => (
            <Input
              {...control}
              type="number"
              inputMode="decimal"
              min="0.01"
              step={PASOS.precio}
              value={valores.precios[l.id] ?? ""}
              onChange={(e) =>
                alCambiar({
                  ...valores,
                  precios: { ...valores.precios, [l.id]: e.target.value },
                })
              }
            />
          )}
        </Campo>
      ))}
      {palancas
        .filter((p) => p.clave !== "precio")
        .map((p) => (
          <Campo
            key={p.clave}
            id={`${id}-${p.clave}`}
            etiqueta={`${p.nombre} (${p.unidad})`}
            error={errores[`${prefijo}.palancas.${p.clave}`]}
          >
            {(control) => (
              <Input
                {...control}
                type="number"
                inputMode="decimal"
                min="0"
                step={PASOS[p.clave]}
                value={valores.palancas[p.clave] ?? ""}
                onChange={(e) =>
                  alCambiar({
                    ...valores,
                    palancas: { ...valores.palancas, [p.clave]: e.target.value },
                  })
                }
              />
            )}
          </Campo>
        ))}
    </div>
  )
}
```

`web/src/componentes/negociacion/RespuestaManual.tsx`:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useState, type FormEvent } from "react"
import { ErrorApi, erroresPorCampo, pedir } from "@/api"
import { useToken } from "@/auth"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { Seccion } from "@/componentes/Seccion"
import { Campo } from "@/componentes/negociacion/Campo"
import {
  CamposValores,
  valoresCapturados,
  valoresVacios,
} from "@/componentes/negociacion/CamposValores"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { crearClaves, type SesionDetalle, type Valores } from "@/negociacion"

type Respuesta = {
  tipo: "mensaje" | "aceptar" | "cerrar"
  texto: string
  contraoferta?: Valores
  confirmar_fuera_de_limites: boolean
}

const AVISOS: Record<Respuesta["tipo"], string> = {
  mensaje: "Se envió su respuesta.",
  aceptar: "Aceptó la última oferta: queda como acuerdo tentativo.",
  cerrar: "Cerró la sesión sin acuerdo.",
}

/**
 * El comprador responde a mano mientras atiende la sesión (spec §7). Si lo que envía sale de sus
 * límites, la API pide confirmarlo; la confirmación queda marcada para el aprobador.
 */
export function RespuestaManual({ datos }: { datos: SesionDetalle }) {
  const token = useToken()
  const cliente = useQueryClient()
  const id = useId()
  const [claves] = useState(crearClaves)
  const palancas = datos.palancas.filter((p) => p.clave !== "precio")
  const propuesta = datos.ofertas.findLast((o) => o.autor !== "proveedor")
  const hayOfertaDelProveedor = datos.ofertas.some((o) => o.autor === "proveedor")
  const [texto, setTexto] = useState("")
  const [conContraoferta, setConContraoferta] = useState(false)
  const [valores, setValores] = useState<Valores>(
    () => propuesta?.valores ?? valoresVacios(datos.lineas, palancas)
  )
  // La respuesta que espera confirmar que sale de los límites.
  const [pendiente, setPendiente] = useState<Respuesta | null>(null)
  const [aviso, setAviso] = useState("")

  const responder = useMutation({
    mutationFn: (cuerpo: Respuesta) => {
      const json = JSON.stringify(cuerpo)
      return pedir<SesionDetalle>(
        `/negociacion/sesiones/${encodeURIComponent(datos.id)}/respuestas`,
        token,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": claves.para(json),
          },
          body: json,
        }
      )
    },
    onSuccess: async (_respuesta, cuerpo) => {
      claves.olvidar()
      setPendiente(null)
      setTexto("")
      setConContraoferta(false)
      setAviso(AVISOS[cuerpo.tipo])
      await cliente.invalidateQueries({ queryKey: ["negociacion"] })
    },
    onError: (error, cuerpo) => {
      setAviso("")
      if (
        error instanceof ErrorApi &&
        error.codigo === "fuera_de_limites" &&
        !cuerpo.confirmar_fuera_de_limites
      )
        setPendiente(cuerpo)
    },
  })
  const errores = erroresPorCampo(responder.error)
  const fueraDeLimites =
    responder.error instanceof ErrorApi &&
    responder.error.codigo === "fuera_de_limites"

  function enviar(cuerpo: Respuesta) {
    if (!responder.isPending) responder.mutate(cuerpo)
  }

  function enviarMensaje(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    enviar({
      tipo: "mensaje",
      texto,
      contraoferta: conContraoferta ? valoresCapturados(valores) : undefined,
      confirmar_fuera_de_limites: false,
    })
  }

  return (
    <Seccion
      titulo="Responder al proveedor"
      descripcion="Usted atiende esta sesión: el agente no responderá hasta que la devuelva."
    >
      <form onSubmit={enviarMensaje} className="space-y-4">
        <Campo
          id={`${id}-texto`}
          etiqueta="Mensaje para el proveedor"
          ayuda={`${texto.length.toLocaleString("es-MX")} de 2,000 caracteres`}
          error={errores.texto}
        >
          {(control) => (
            <Textarea
              {...control}
              required
              maxLength={2000}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
          )}
        </Campo>
        <div className="flex items-center gap-2">
          <Checkbox
            id={`${id}-con`}
            checked={conContraoferta}
            onCheckedChange={(valor) => setConContraoferta(valor === true)}
          />
          <Label htmlFor={`${id}-con`}>Incluir una contraoferta</Label>
        </div>
        {conContraoferta && (
          <CamposValores
            id={`${id}-valores`}
            lineas={datos.lineas}
            palancas={palancas}
            moneda={datos.moneda}
            valores={valores}
            alCambiar={setValores}
            errores={errores}
            prefijo="contraoferta"
          />
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" aria-disabled={responder.isPending}>
            Enviar respuesta
          </Button>
          {hayOfertaDelProveedor && (
            <ConfirmarAccion
              titulo="¿Aceptar la última oferta?"
              descripcion="La última oferta del proveedor queda como acuerdo tentativo; no es vinculante hasta la adjudicación."
              textoConfirmar="Aceptar oferta"
              alConfirmar={() =>
                enviar({ tipo: "aceptar", texto: "", confirmar_fuera_de_limites: false })
              }
            >
              <Button type="button" variant="outline">
                Aceptar la última oferta
              </Button>
            </ConfirmarAccion>
          )}
          <ConfirmarAccion
            titulo="¿Cerrar sin acuerdo?"
            descripcion="La sesión termina sin acuerdo y el proveedor ya no podrá ofertar."
            textoConfirmar="Cerrar sin acuerdo"
            alConfirmar={() =>
              enviar({ tipo: "cerrar", texto, confirmar_fuera_de_limites: false })
            }
          >
            <Button type="button" variant="outline">
              Cerrar sin acuerdo
            </Button>
          </ConfirmarAccion>
        </div>
        <p
        role="status"
        className={aviso ? "text-sm text-success" : "sr-only"}
      >
          {aviso}
        </p>
        {responder.isError &&
          !fueraDeLimites &&
          Object.keys(errores).length === 0 && (
            <p role="alert" className="text-sm text-destructive">
              {responder.error.message}
            </p>
          )}
      </form>
      <AlertDialog
        open={pendiente !== null}
        onOpenChange={(abierto) => {
          if (!abierto) setPendiente(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Esto sale de sus límites</AlertDialogTitle>
            <AlertDialogDescription>
              {`${responder.error?.message ?? ""} Si continúa, la sesión queda marcada y el aprobador lo verá.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Revisar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendiente)
                  enviar({ ...pendiente, confirmar_fuera_de_limites: true })
              }}
            >
              Enviar de todos modos
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Seccion>
  )
}
```

En `web/src/paginas/SesionNegociacion.tsx`:

1. Importe `RespuestaManual`:

```tsx
import { RespuestaManual } from "@/componentes/negociacion/RespuestaManual"
```

2. En `Supervision`, después de `{esComprador && !esFinal(datos.estado) && <Control datos={datos} />}`, agregue:

```tsx
      {esComprador && datos.modo === "comprador" && !esFinal(datos.estado) && (
        <RespuestaManual datos={datos} />
      )}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/paginas/SesionNegociacion.test.tsx`
Expected: PASS, incluidas las de la Task 6.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/componentes/negociacion/CamposValores.tsx web/src/componentes/negociacion/RespuestaManual.tsx web/src/paginas/SesionNegociacion.tsx web/src/paginas/SesionNegociacion.test.tsx
git commit -m "feat(web): respuesta manual del comprador con confirmación fuera de límites" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Portal del proveedor

**Files:**
- Create: `web/src/portal.ts`
- Create: `web/src/portal.test.ts`
- Create: `web/src/paginas/Portal.tsx`
- Create: `web/src/paginas/Portal.test.tsx`
- Modify: `web/src/rutas.tsx`, `web/src/rutas.test.ts`
- Modify: `web/src/componentes/BarraSuperior.tsx` (exporta `SelectorTema`)

**Interfaces:**
- Consumes:
  - de la Task 1: `crearClaves`, `esFinal`, `Autor`, `Valores`, `VistaPortal` y `Textarea`;
  - de la Task 3: `Campo`;
  - de la Task 4: `simularRutas` y `llamadaA`;
  - de la Task 6: `ValoresOferta`;
  - de la Task 7: `CamposValores`, `valoresVacios` y `valoresCapturados`;
  - de `@/api`: `pedir` (sin token, con `Authorization` en `init.headers`), `ErrorApi` y `erroresPorCampo`.
- Produces:
  - `tomarToken(): string | null` y `pedirPortal<T>(ruta, token, init?)` (`@/portal`);
  - la ruta `portal: RouteObject` (`/portal`) en `@/rutas`, hermana de `marco`;
  - la página `Portal`.
- API (`Authorization: Invitacion <token>`):
  - `GET /negociacion/portal/sesion` → `VistaPortal`. Un enlace falso, revocado o vencido responde siempre 401;
  - `POST /negociacion/portal/ofertas` con `{ valores, nota, confirmar_valores }` e `Idempotency-Key` → `VistaPortal`. Responde 422 `oferta_invalida` con campos `valores.precios.{id}` y `valores.palancas.{clave}`, 409 si la negociación terminó y 429 con `Retry-After` si se excede el límite;
  - `POST /negociacion/portal/escalar` con `Idempotency-Key` → `VistaPortal`.
- **Por qué el portal no usa `Termino`:** las definiciones del glosario le hablan al comprador («el peor valor que usted acepta»). El proveedor ve textos llanos.

- [ ] **Step 1: Write the failing tests**

`web/src/portal.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest"
import { pedirPortal, tomarToken } from "@/portal"
import { llamadaA, respuestaJson, simularApi } from "@/pruebas/utilidades"

afterEach(() => {
  sessionStorage.clear()
  window.history.replaceState(null, "", "/")
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("tomarToken", () => {
  it("toma el token del fragmento, lo guarda y lo quita de la barra", () => {
    window.history.replaceState(null, "", "/portal?x=1#t=tok-123")
    expect(tomarToken()).toBe("tok-123")
    expect(window.location.hash).toBe("")
    expect(window.location.pathname + window.location.search).toBe("/portal?x=1")
    expect(sessionStorage.getItem("portal-negociacion")).toBe("tok-123")
    // Al recargar la pestaña, ya sin fragmento, sigue sirviendo.
    expect(tomarToken()).toBe("tok-123")
  })

  it("un enlace nuevo en la misma pestaña reemplaza al anterior", () => {
    window.history.replaceState(null, "", "/portal#t=viejo")
    tomarToken()
    window.history.replaceState(null, "", "/portal#t=nuevo")
    expect(tomarToken()).toBe("nuevo")
    expect(tomarToken()).toBe("nuevo")
  })

  it("sin fragmento ni nada guardado no hay token", () => {
    window.history.replaceState(null, "", "/portal")
    expect(tomarToken()).toBeNull()
  })

  it("con el almacenamiento bloqueado, lo conserva en memoria", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    window.history.replaceState(null, "", "/portal#t=tok-memoria")
    expect(tomarToken()).toBe("tok-memoria")
    expect(tomarToken()).toBe("tok-memoria")
  })
})

describe("pedirPortal", () => {
  it("manda Authorization: Invitacion a la API del portal, nunca un Bearer", async () => {
    const api = simularApi(() => respuestaJson({ ok: true }))
    await pedirPortal("/sesion", "tok-123")
    expect(
      llamadaA(api, "/api/negociacion/portal/sesion").cabeceras.get("Authorization")
    ).toBe("Invitacion tok-123")
  })
})
```

`web/src/paginas/Portal.test.tsx`:

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Portal } from "@/paginas/Portal"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"

const SESION = "/api/negociacion/portal/sesion"
const OFERTAS = "/api/negociacion/portal/ofertas"
const ESCALAR = "/api/negociacion/portal/escalar"

const VISTA = {
  folio: "NEG-2026-0001",
  titulo: "Licencias de correo 2027",
  moneda: "MXN",
  fecha_limite: "2026-10-21T23:00:00Z",
  rondas_max: 6,
  rondas_restantes: 4,
  estado: "activa",
  atendido_por: "agente",
  pide_confirmacion: false,
  lineas: [
    {
      id: "l1",
      codigo_servicio: "LIC-CORREO",
      nombre: "Correo en la nube",
      unidad: "usuario_mes",
      cantidad: "250.0000",
    },
  ],
  palancas: [{ clave: "plazo_pago_dias", nombre: "Plazo de pago", unidad: "días" }],
  mensajes: [
    {
      autor: "proveedor",
      texto: "Es nuestra mejor oferta.",
      ronda: 1,
      fecha: "2026-10-14T18:10:00Z",
      oferta: { precios: { l1: "120.00" }, palancas: { plazo_pago_dias: "15" } },
    },
    {
      autor: "agente",
      texto: "Gracias por su oferta. Le proponemos lo siguiente.",
      ronda: 1,
      fecha: "2026-10-14T18:10:01Z",
      oferta: { precios: { l1: "98.00" }, palancas: { plazo_pago_dias: "45" } },
    },
  ],
  ultima_propuesta: { precios: { l1: "98.00" }, palancas: { plazo_pago_dias: "45" } },
}

function abrirCon(token = "tok-123") {
  window.history.replaceState(null, "", `/portal#t=${token}`)
  return renderizarPagina(<Portal />, { ruta: "/portal" })
}

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  window.history.replaceState(null, "", "/")
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe("Portal", () => {
  it("sin token no consulta y explica que el enlace no sirve", () => {
    const api = simularRutas({})
    renderizarPagina(<Portal />, { ruta: "/portal" })
    expect(
      screen.getByText("El enlace no es válido o ya venció")
    ).toBeInTheDocument()
    expect(api).not.toHaveBeenCalled()
  })

  it("muestra un esqueleto mientras carga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    abrirCon()
    expect(await screen.findByText("Cargando…")).toBeInTheDocument()
  })

  it("si el servicio falla, lo dice y permite reintentar", async () => {
    simularRutas({
      [`GET ${SESION}`]: () =>
        respuestaJson(
          {
            title: "Servicio no disponible",
            detail: "El servicio no está disponible; intente más tarde.",
          },
          503
        ),
    })
    abrirCon()
    expect(
      await screen.findByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
  })

  it("un 401 muestra la misma pantalla", async () => {
    simularRutas({
      [`GET ${SESION}`]: () =>
        respuestaJson(
          { title: "No autorizado", detail: "El enlace no es válido o ya venció." },
          401
        ),
    })
    abrirCon()
    expect(
      await screen.findByText("El enlace no es válido o ya venció")
    ).toBeInTheDocument()
  })

  it("muestra qué se negocia, la conversación y la última propuesta", async () => {
    const api = simularRutas({ [`GET ${SESION}`]: () => respuestaJson(VISTA) })
    const { container } = abrirCon()
    expect(
      await screen.findByRole("heading", { name: "Licencias de correo 2027" })
    ).toBeInTheDocument()
    expect(screen.getByText(/Le quedan 4 rondas/)).toBeInTheDocument()
    expect(screen.getByText("Agente de compras")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Aceptar esta propuesta" })
    ).toBeInTheDocument()
    expect(llamadaA(api, SESION).cabeceras.get("Authorization")).toBe(
      "Invitacion tok-123"
    )
    await esperarSinViolaciones(container)
  })

  it("envía la oferta con su enlace e Idempotency-Key y limpia el formulario", async () => {
    const api = simularRutas({
      [`GET ${SESION}`]: () => respuestaJson(VISTA),
      [`POST ${OFERTAS}`]: () => respuestaJson(VISTA),
    })
    abrirCon()
    await userEvent.type(
      await screen.findByLabelText("Precio de Correo en la nube"),
      "100"
    )
    await userEvent.type(screen.getByLabelText("Plazo de pago (días)"), "30")
    await userEvent.type(
      screen.getByLabelText("Nota para el equipo de compras (opcional)"),
      "Incluye soporte 24/7."
    )
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    expect(await screen.findByText("Se envió su oferta.")).toBeInTheDocument()
    const { cuerpo, cabeceras } = llamadaA(api, OFERTAS, "POST")
    expect(cuerpo).toEqual({
      valores: { precios: { l1: "100" }, palancas: { plazo_pago_dias: "30" } },
      nota: "Incluye soporte 24/7.",
      confirmar_valores: false,
    })
    expect(cabeceras.get("Authorization")).toBe("Invitacion tok-123")
    expect(cabeceras.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/)
    expect(screen.getByLabelText("Precio de Correo en la nube")).toHaveValue(null)
  })

  it("reintentar el mismo envío reutiliza la clave y una oferta nueva usa otra", async () => {
    let intentos = 0
    const api = vi.fn((url: string, _init?: RequestInit) => {
      if (url === OFERTAS) {
        intentos += 1
        if (intentos === 1) return Promise.reject(new TypeError("Failed to fetch"))
      }
      return Promise.resolve(respuestaJson(VISTA))
    })
    vi.stubGlobal("fetch", api)
    abrirCon()
    const capturar = async () => {
      await userEvent.type(
        await screen.findByLabelText("Precio de Correo en la nube"),
        "100"
      )
      await userEvent.type(screen.getByLabelText("Plazo de pago (días)"), "30")
    }
    await capturar()
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo conectar con el servidor"
    )
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    expect(await screen.findByText("Se envió su oferta.")).toBeInTheDocument()
    await capturar()
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    await waitFor(() => expect(intentos).toBe(3))
    const claves = api.mock.calls
      .filter(([url]) => url === OFERTAS)
      .map(([, init]) => new Headers(init?.headers).get("Idempotency-Key"))
    expect(claves[1]).toBe(claves[0])
    expect(claves[2]).not.toBe(claves[0])
  })

  it("«Aceptar esta propuesta» llena el formulario y deja el foco en «Enviar oferta»", async () => {
    simularRutas({ [`GET ${SESION}`]: () => respuestaJson(VISTA) })
    abrirCon()
    await userEvent.click(
      await screen.findByRole("button", { name: "Aceptar esta propuesta" })
    )
    expect(screen.getByLabelText("Precio de Correo en la nube")).toHaveValue(98)
    expect(screen.getByLabelText("Plazo de pago (días)")).toHaveValue(45)
    expect(screen.getByRole("button", { name: "Enviar oferta" })).toHaveFocus()
    expect(
      screen.getByText(/Revísela y pulse «Enviar oferta» para aceptarla/)
    ).toBeInTheDocument()
  })

  it("si el agente pidió aclarar un precio, pide confirmar los valores", async () => {
    const api = simularRutas({
      [`GET ${SESION}`]: () => respuestaJson({ ...VISTA, pide_confirmacion: true }),
      [`POST ${OFERTAS}`]: () => respuestaJson(VISTA),
    })
    abrirCon()
    await userEvent.type(
      await screen.findByLabelText("Precio de Correo en la nube"),
      "9"
    )
    await userEvent.type(screen.getByLabelText("Plazo de pago (días)"), "30")
    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Confirmo estos valores: los revisé y son correctos.",
      })
    )
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    await screen.findByText("Se envió su oferta.")
    expect(llamadaA(api, OFERTAS, "POST").cuerpo).toMatchObject({
      confirmar_valores: true,
    })
  })

  it("«Hablar con una persona» escala la sesión y avisa que responde una persona", async () => {
    let persona = false
    const api = simularRutas({
      [`GET ${SESION}`]: () =>
        respuestaJson({ ...VISTA, atendido_por: persona ? "persona" : "agente" }),
      [`POST ${ESCALAR}`]: () => {
        persona = true
        return respuestaJson({ ...VISTA, atendido_por: "persona" })
      },
    })
    abrirCon()
    await userEvent.click(
      await screen.findByRole("button", { name: "Hablar con una persona" })
    )
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Hablar con una persona",
      })
    )
    expect(await screen.findByText("Le atiende una persona")).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Hablar con una persona" })
    ).not.toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Enviar oferta" })).toHaveFocus()
    )
    expect(
      llamadaA(api, ESCALAR, "POST").cabeceras.get("Idempotency-Key")
    ).toMatch(/^[0-9a-f-]{36}$/)
  })

  it("mientras atiende una persona, la página se actualiza sola", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = simularRutas({
      [`GET ${SESION}`]: () => respuestaJson({ ...VISTA, atendido_por: "persona" }),
    })
    abrirCon()
    await screen.findByText("Le atiende una persona")
    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() =>
      expect(api.mock.calls.filter(([url]) => url === SESION)).toHaveLength(2)
    )
  })

  it("muestra el acuerdo tentativo y ya no ofrece el formulario", async () => {
    simularRutas({
      [`GET ${SESION}`]: () =>
        respuestaJson({ ...VISTA, estado: "acuerdo_tentativo", ultima_propuesta: null }),
    })
    abrirCon()
    expect(await screen.findByText("Acuerdo tentativo")).toBeInTheDocument()
    expect(
      screen.getByText(/No es vinculante hasta que se adjudique/)
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Enviar oferta" })
    ).not.toBeInTheDocument()
  })

  it("sin acuerdo lo dice y ya no ofrece el formulario", async () => {
    simularRutas({
      [`GET ${SESION}`]: () => respuestaJson({ ...VISTA, estado: "sin_acuerdo" }),
    })
    abrirCon()
    expect(
      await screen.findByText("La negociación terminó sin acuerdo")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Enviar oferta" })
    ).not.toBeInTheDocument()
  })

  it("muestra junto al campo el error del servicio", async () => {
    simularRutas({
      [`GET ${SESION}`]: () => respuestaJson(VISTA),
      [`POST ${OFERTAS}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los campos indicados.",
            codigo: "oferta_invalida",
            errores: [
              { campo: "valores.precios.l1", mensaje: "Indique el precio de esta línea." },
            ],
          },
          422
        ),
    })
    abrirCon()
    await userEvent.type(await screen.findByLabelText("Plazo de pago (días)"), "30")
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    expect(
      await screen.findByText("Indique el precio de esta línea.")
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Precio de Correo en la nube")).toHaveAttribute(
      "aria-invalid",
      "true"
    )
  })
})
```

En `web/src/rutas.test.ts`, cambie el import por `import { marco, paginas, portal } from "@/rutas"` y agregue:

```ts
  it("el portal va fuera del marco: no pasa por el Layout ni por el inicio de sesión", async () => {
    expect(portal.path).toBe("/portal")
    expect(paginas.some((r) => r.path?.includes("portal"))).toBe(false)
    const cargada = await (
      portal.lazy as () => Promise<{ Component?: unknown }>
    )()
    expect(cargada.Component).toEqual(expect.any(Function))
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run (desde `web/`): `npx vitest run src/portal.test.ts src/paginas/Portal.test.tsx src/rutas.test.ts`
Expected: FAIL. `@/portal` y `@/paginas/Portal` no existen, y `rutas` no exporta `portal`.

- [ ] **Step 3: Write the implementation**

`web/src/portal.ts`:

```ts
import { pedir } from "@/api"

const CLAVE = "portal-negociacion"
// Respaldo si el navegador bloquea sessionStorage: el token dura mientras la página siga abierta.
let enMemoria: string | null = null

function guardar(token: string): void {
  enMemoria = token
  try {
    sessionStorage.setItem(CLAVE, token)
  } catch {
    // Bloqueado: queda en memoria.
  }
}

function leer(): string | null {
  try {
    return sessionStorage.getItem(CLAVE)
  } catch {
    return enMemoria
  }
}

/**
 * El token de invitación (spec §8.1): llega en el fragmento (#t=…), que no viaja al servidor ni
 * en el Referer. Se guarda en la pestaña y se borra de la barra y del historial. Un enlace nuevo
 * reemplaza al anterior; sin fragmento, se usa el guardado (al recargar).
 */
export function tomarToken(): string | null {
  const nuevo = new URLSearchParams(window.location.hash.slice(1)).get("t")
  if (!nuevo) return leer()
  guardar(nuevo)
  window.history.replaceState(
    window.history.state,
    "",
    window.location.pathname + window.location.search
  )
  return nuevo
}

/** GET o POST a /api/negociacion/portal{ruta} con el token de invitación, nunca con un Bearer. */
export function pedirPortal<T>(
  ruta: string,
  token: string,
  init: RequestInit = {}
): Promise<T> {
  const cabeceras = new Headers(init.headers)
  cabeceras.set("Authorization", `Invitacion ${token}`)
  // Sin token de Keycloak, `pedir` respeta el Authorization de las cabeceras.
  return pedir<T>(`/negociacion/portal${ruta}`, undefined, {
    ...init,
    headers: cabeceras,
  })
}
```

`web/src/paginas/Portal.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CircleOff, Handshake, Link2Off, Send, UserRound } from "lucide-react"
import { useEffect, useId, useRef, useState, type FormEvent } from "react"
import { ErrorApi, erroresPorCampo } from "@/api"
import { SelectorTema } from "@/componentes/BarraSuperior"
import { ConfirmarAccion } from "@/componentes/ConfirmarAccion"
import { EncabezadoPagina } from "@/componentes/EncabezadoPagina"
import { EstadoCarga, EstadoError, EstadoVacio } from "@/componentes/Estados"
import { Seccion } from "@/componentes/Seccion"
import { Campo } from "@/componentes/negociacion/Campo"
import {
  CamposValores,
  valoresCapturados,
  valoresVacios,
} from "@/componentes/negociacion/CamposValores"
import { ValoresOferta } from "@/componentes/negociacion/ValoresOferta"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { formatoFechaHora } from "@/fechas"
import { formatoDecimal, porUnidad } from "@/inteligencia"
import { cn } from "@/lib/utils"
import {
  crearClaves,
  esFinal,
  type Autor,
  type Valores,
  type VistaPortal,
} from "@/negociacion"
import { pedirPortal, tomarToken } from "@/portal"

const CLAVE = ["portal"]

/** Cómo se llama a cada autor en la conversación que ve el proveedor. */
const AUTORES: Record<Autor, string> = {
  proveedor: "Usted",
  agente: "Agente de compras",
  comprador: "Equipo de compras",
  sistema: "Aviso",
}

/** El portal del proveedor (spec §10.2): fuera del Layout, sin inicio de sesión. */
export function Portal() {
  const [token] = useState(tomarToken)
  useEffect(() => {
    document.title = "Portal de proveedores · PluriOne"
  }, [])
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-2 px-4 py-2">
          <p className="font-semibold">PluriOne · Portal de proveedores</p>
          <SelectorTema />
        </div>
      </header>
      <main
        id="contenido"
        tabIndex={-1}
        className="mx-auto max-w-3xl space-y-6 px-4 py-6 outline-hidden"
      >
        {token ? <SesionPortal token={token} /> : <EnlaceInvalido />}
      </main>
    </div>
  )
}

function EnlaceInvalido() {
  return (
    <EstadoVacio
      icono={Link2Off}
      titulo="El enlace no es válido o ya venció"
      descripcion="Pida al equipo de compras que le reenvíe la invitación. Cada enlace es personal y deja de servir al llegar la fecha límite, al reenviarse o si se cancela la negociación."
    />
  )
}

function SesionPortal({ token }: { token: string }) {
  const consulta = useQuery({
    queryKey: CLAVE,
    queryFn: () => pedirPortal<VistaPortal>("/sesion", token),
    // Mientras atiende una persona, su respuesta llega sin que el proveedor envíe nada.
    refetchInterval: (q) => {
      const vista = q.state.data
      return vista && vista.atendido_por === "persona" && !esFinal(vista.estado)
        ? 3000
        : false
    },
  })
  if (consulta.isPending) return <EstadoCarga />
  // El mismo 401 para un enlace falso, revocado o vencido; también si vence con la página abierta.
  if (consulta.error instanceof ErrorApi && consulta.error.estado === 401)
    return <EnlaceInvalido />
  if (consulta.isLoadingError) {
    return (
      <EstadoError
        error={consulta.error}
        alReintentar={() => void consulta.refetch()}
      />
    )
  }
  const vista = consulta.data
  return (
    <>
      <p
        role="status"
        className={consulta.isRefetchError ? "text-sm text-warning" : "sr-only"}
      >
        {consulta.isRefetchError
          ? "No se pudo actualizar; se volverá a intentar en unos segundos."
          : ""}
      </p>
      <Resumen vista={vista} />
      <Seccion titulo="Conversación">
        <ConversacionPortal vista={vista} />
      </Seccion>
      {!esFinal(vista.estado) && <Ofertar token={token} vista={vista} />}
    </>
  )
}

function Resumen({ vista }: { vista: VistaPortal }) {
  const restantes =
    vista.rondas_restantes === 1
      ? "Le queda 1 ronda"
      : `Le quedan ${vista.rondas_restantes} rondas`
  return (
    <div className="space-y-4">
      <EncabezadoPagina
        titulo={vista.titulo}
        descripcion={`${vista.folio} · Fecha límite: ${formatoFechaHora(vista.fecha_limite)}${esFinal(vista.estado) ? "" : ` · ${restantes}`}`}
      />
      {vista.estado === "acuerdo_tentativo" && (
        <Alert role="status">
          <Handshake aria-hidden />
          <AlertTitle>Acuerdo tentativo</AlertTitle>
          <AlertDescription>
            Su oferta quedó como acuerdo tentativo. No es vinculante hasta que se
            adjudique y se apruebe; el equipo de compras se pondrá en contacto
            con usted.
          </AlertDescription>
        </Alert>
      )}
      {(vista.estado === "sin_acuerdo" || vista.estado === "expirada") && (
        <Alert role="status">
          <CircleOff aria-hidden />
          <AlertTitle>La negociación terminó sin acuerdo</AlertTitle>
          <AlertDescription>
            Gracias por participar. Si tiene dudas, comuníquese con el equipo de
            compras.
          </AlertDescription>
        </Alert>
      )}
      {vista.atendido_por === "persona" && !esFinal(vista.estado) && (
        <Alert role="status">
          <UserRound aria-hidden />
          <AlertTitle>Le atiende una persona</AlertTitle>
          <AlertDescription>
            Una persona del equipo de compras revisará su oferta y le responderá
            aquí. Esta página se actualiza sola.
          </AlertDescription>
        </Alert>
      )}
      <Seccion titulo="Qué se negocia">
        <ul className="space-y-1 text-sm">
          {vista.lineas.map((l) => (
            <li key={l.id}>
              <span className="font-medium">{l.nombre}</span>
              {`: cantidad ${formatoDecimal(Number(l.cantidad), 4)}, precio ${porUnidad(l.unidad)} en ${vista.moneda}`}
            </li>
          ))}
          {vista.palancas.map((p) => (
            <li key={p.clave}>
              <span className="font-medium">{p.nombre}</span>
              {` (en ${p.unidad})`}
            </li>
          ))}
        </ul>
      </Seccion>
    </div>
  )
}

function ConversacionPortal({ vista }: { vista: VistaPortal }) {
  if (vista.mensajes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aún no hay mensajes: envíe su primera oferta con el formulario de abajo.
      </p>
    )
  }
  return (
    <ol className="space-y-3">
      {vista.mensajes.map((m, i) => (
        // La conversación solo crece: el índice es una clave estable.
        <li
          key={i}
          className={cn(
            "space-y-2 rounded-lg border p-3",
            m.autor === "proveedor" && "bg-muted/40"
          )}
        >
          <p className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{AUTORES[m.autor]}</span>
            <span>{formatoFechaHora(m.fecha)}</span>
          </p>
          {m.texto && (
            <p className="text-sm break-words whitespace-pre-wrap">{m.texto}</p>
          )}
          {m.oferta && (
            <ValoresOferta
              valores={m.oferta}
              lineas={vista.lineas}
              palancas={vista.palancas}
              moneda={vista.moneda}
            />
          )}
        </li>
      ))}
    </ol>
  )
}

type Oferta = { valores: Valores; nota: string; confirmar_valores: boolean }

function Ofertar({ token, vista }: { token: string; vista: VistaPortal }) {
  const cliente = useQueryClient()
  const id = useId()
  const enviarBoton = useRef<HTMLButtonElement>(null)
  const [claves] = useState(crearClaves)
  const [clavesEscalar] = useState(crearClaves)
  const [valores, setValores] = useState<Valores>(() =>
    valoresVacios(vista.lineas, vista.palancas)
  )
  const [nota, setNota] = useState("")
  const [confirmo, setConfirmo] = useState(false)
  const [aviso, setAviso] = useState("")

  // Al pasar a «le atiende una persona» desaparece «Hablar con una persona»: el foco va a «Enviar oferta».
  const atendidoPor = vista.atendido_por
  const anterior = useRef(atendidoPor)
  useEffect(() => {
    if (anterior.current !== atendidoPor && atendidoPor === "persona")
      enviarBoton.current?.focus()
    anterior.current = atendidoPor
  }, [atendidoPor])

  const ofertar = useMutation({
    mutationFn: (cuerpo: Oferta) => {
      const json = JSON.stringify(cuerpo)
      return pedirPortal<VistaPortal>("/ofertas", token, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": claves.para(json),
        },
        body: json,
      })
    },
    onSuccess: (nueva) => {
      claves.olvidar()
      cliente.setQueryData(CLAVE, nueva)
      setValores(valoresVacios(vista.lineas, vista.palancas))
      setNota("")
      setConfirmo(false)
      setAviso("Se envió su oferta.")
    },
    onError: (error) => {
      setAviso("")
      // Si el enlace venció o la negociación terminó, la vista nueva lo explica.
      if (error instanceof ErrorApi && (error.estado === 401 || error.estado === 409))
        void cliente.invalidateQueries({ queryKey: CLAVE })
    },
  })
  const escalar = useMutation({
    mutationFn: () =>
      pedirPortal<VistaPortal>("/escalar", token, {
        method: "POST",
        headers: { "Idempotency-Key": clavesEscalar.para("escalar") },
      }),
    onSuccess: (nueva) => {
      clavesEscalar.olvidar()
      cliente.setQueryData(CLAVE, nueva)
      setAviso("Avisamos al equipo de compras; una persona le responderá aquí.")
    },
  })
  const errores = erroresPorCampo(ofertar.error)

  function aceptarPropuesta() {
    if (!vista.ultima_propuesta) return
    setValores(vista.ultima_propuesta)
    setAviso(
      "Llenamos el formulario con la propuesta del agente. Revísela y pulse «Enviar oferta» para aceptarla."
    )
    enviarBoton.current?.focus()
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (ofertar.isPending) return
    ofertar.mutate({
      valores: valoresCapturados(valores),
      nota: nota.trim(),
      confirmar_valores: vista.pide_confirmacion && confirmo,
    })
  }

  return (
    <>
      {vista.ultima_propuesta && (
        <Seccion titulo="Última propuesta del agente">
          <div className="space-y-3">
            <ValoresOferta
              valores={vista.ultima_propuesta}
              lineas={vista.lineas}
              palancas={vista.palancas}
              moneda={vista.moneda}
            />
            <Button type="button" variant="outline" onClick={aceptarPropuesta}>
              <Handshake aria-hidden />
              Aceptar esta propuesta
            </Button>
          </div>
        </Seccion>
      )}
      <Seccion
        titulo="Su oferta"
        descripcion={
          vista.atendido_por === "agente"
            ? "Indique un precio unitario por línea y un valor por cada término. El agente le responde al momento."
            : "Indique un precio unitario por línea y un valor por cada término. Una persona le responderá aquí."
        }
      >
        <form onSubmit={enviar} className="space-y-4">
          <CamposValores
            id={`${id}-valores`}
            lineas={vista.lineas}
            palancas={vista.palancas}
            moneda={vista.moneda}
            valores={valores}
            alCambiar={setValores}
            errores={errores}
            prefijo="valores"
          />
          <Campo
            id={`${id}-nota`}
            etiqueta="Nota para el equipo de compras (opcional)"
            ayuda={`${nota.length.toLocaleString("es-MX")} de 2,000 caracteres. La lee una persona; no cambia su oferta.`}
            error={errores.nota}
          >
            {(control) => (
              <Textarea
                {...control}
                maxLength={2000}
                value={nota}
                onChange={(e) => setNota(e.target.value)}
              />
            )}
          </Campo>
          {vista.pide_confirmacion && (
            <div className="flex items-start gap-2">
              <Checkbox
                id={`${id}-confirmo`}
                checked={confirmo}
                onCheckedChange={(valor) => setConfirmo(valor === true)}
              />
              <Label htmlFor={`${id}-confirmo`}>
                Confirmo estos valores: los revisé y son correctos.
              </Label>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              ref={enviarBoton}
              type="submit"
              aria-disabled={ofertar.isPending}
            >
              <Send aria-hidden />
              Enviar oferta
            </Button>
            {vista.atendido_por === "agente" && (
              <ConfirmarAccion
                titulo="¿Hablar con una persona?"
                descripcion="Una persona del equipo de compras le responderá aquí. Puede seguir enviando ofertas mientras tanto."
                textoConfirmar="Hablar con una persona"
                alConfirmar={() => {
                  if (!escalar.isPending) escalar.mutate()
                }}
              >
                <Button type="button" variant="outline">
                  <UserRound aria-hidden />
                  Hablar con una persona
                </Button>
              </ConfirmarAccion>
            )}
          </div>
          <p role="status" className={aviso ? "text-sm" : "sr-only"}>
            {aviso}
          </p>
          {ofertar.isError && Object.keys(errores).length === 0 && (
            <p role="alert" className="text-sm text-destructive">
              {ofertar.error.message}
            </p>
          )}
          {escalar.isError && (
            <p role="alert" className="text-sm text-destructive">
              {escalar.error.message}
            </p>
          )}
        </form>
      </Seccion>
    </>
  )
}
```

En `web/src/componentes/BarraSuperior.tsx`, cambie `function SelectorTema() {` por `export function SelectorTema() {`.

En `web/src/rutas.tsx`, agregue antes de `export const router` la ruta del portal y cambie el router:

```tsx
/**
 * El portal del proveedor va fuera de `marco`: el Layout pediría iniciar sesión con Keycloak, y el
 * proveedor entra con el token de su enlace (spec §10.2).
 */
export const portal: RouteObject = {
  path: "/portal",
  lazy: async () => ({ Component: (await import("@/paginas/Portal")).Portal }),
  HydrateFallback: CargaInicial,
  ErrorBoundary: ErrorDePagina,
}

export const router = createBrowserRouter([portal, marco])
```

(Borre la línea anterior `export const router = createBrowserRouter([marco])`.)

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/portal.test.ts src/paginas/Portal.test.tsx src/rutas.test.ts`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/portal.ts web/src/portal.test.ts web/src/paginas/Portal.tsx web/src/paginas/Portal.test.tsx web/src/rutas.tsx web/src/rutas.test.ts web/src/componentes/BarraSuperior.tsx
git commit -m "feat(web): portal del proveedor con su enlace, ofertas y escalamiento" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 9: «Renovar» en el Tablero, las Alertas y la ficha del proveedor

**Files:**
- Modify: `web/src/paginas/Tablero.tsx`, `web/src/paginas/Tablero.test.tsx`
- Modify: `web/src/componentes/ElementoAlerta.tsx`
- Create: `web/src/componentes/ElementoAlerta.test.tsx`
- Modify: `web/src/componentes/TablaContratos.tsx`, `web/src/componentes/TablaContratos.test.tsx`
- Modify: `web/src/paginas/ProveedorDetalle.tsx`, `web/src/paginas/ProveedorDetalle.test.tsx`

**Interfaces:**
- Consumes:
  - de la Task 1: `rutaRenovacion(proveedorId, contratoId)` y `hoyEnMexico()`;
  - de `@/auth`: `useRoles()`.
- Produces: un enlace «Renovar» que lleva a `/negociaciones/nueva?proveedor=…&contrato=…` (Task 3). Solo lo ve el rol `comprador` (spec §10.1) y aparece en tres lugares:
  - las filas de «Próximos vencimientos» del Tablero;
  - las alertas de vencimiento de contrato (`ElementoAlerta`, en Alertas y en el Tablero);
  - los contratos **vigentes** de la ficha del proveedor (`TablaContratos` recibe la prop nueva `proveedorId`).
- **Nombre accesible:** el enlace se llama `Renovar el contrato <folio>`, con `aria-label`, y el texto visible es «Renovar». El nombre contiene el texto visible (WCAG 2.5.3) y el folio no se repite como texto, así que las pruebas que buscan el folio con `getByText` siguen encontrando un solo elemento.

- [ ] **Step 1: Write the failing tests**

En `web/src/paginas/Tablero.test.tsx`, agregue al `describe("Tablero")`:

```tsx
  it("el comprador puede renovar desde los próximos vencimientos; otros roles no", async () => {
    sesionDePrueba.roles = ["comprador"]
    api()
    renderizarPagina(<Tablero />)
    expect(
      await screen.findByRole("link", { name: "Renovar el contrato CT-0001" })
    ).toHaveAttribute("href", "/negociaciones/nueva?proveedor=p1&contrato=c1")
    cleanup()
    sesionDePrueba.roles = ["admin"]
    api()
    renderizarPagina(<Tablero />)
    await screen.findByText("CT-0001")
    expect(
      screen.queryByRole("link", { name: /^Renovar/ })
    ).not.toBeInTheDocument()
  })
```

Cree `web/src/componentes/ElementoAlerta.test.tsx`:

```tsx
import { cleanup, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ElementoAlerta } from "@/componentes/ElementoAlerta"
import type { Alerta } from "@/inteligencia"
import { sesionDePrueba } from "@/pruebas/sesion"
import { renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const VENCIMIENTO: Alerta = {
  id: "vencimiento:c1",
  tipo: "vencimiento",
  severidad: "alta",
  titulo: "El contrato CT-0001 vence en 25 días",
  explicacion: "Nube pública con Nube Andina.",
  entidad_tipo: "contrato",
  entidad_id: "c1",
  entidad_nombre: "CT-0001",
  proveedor_id: "p1",
  proveedor_nombre: "Nube Andina",
  fecha: "2026-11-07",
  ahorro_potencial: null,
  moneda: null,
}

afterEach(() => {
  cleanup()
  sesionDePrueba.roles = ["admin"]
})

describe("ElementoAlerta", () => {
  it("una alerta de vencimiento ofrece renovar el contrato al comprador", () => {
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(<ElementoAlerta alerta={VENCIMIENTO} />)
    expect(
      screen.getByRole("link", { name: "Renovar el contrato CT-0001" })
    ).toHaveAttribute("href", "/negociaciones/nueva?proveedor=p1&contrato=c1")
  })

  it("no lo ofrece a otros roles ni en alertas que no son de vencimiento", () => {
    renderizarPagina(<ElementoAlerta alerta={VENCIMIENTO} />)
    expect(screen.queryByRole("link", { name: /^Renovar/ })).not.toBeInTheDocument()
    cleanup()
    sesionDePrueba.roles = ["comprador"]
    renderizarPagina(
      <ElementoAlerta
        alerta={{ ...VENCIMIENTO, tipo: "riesgo", entidad_tipo: "proveedor" }}
      />
    )
    expect(screen.queryByRole("link", { name: /^Renovar/ })).not.toBeInTheDocument()
  })
})
```

En `web/src/componentes/TablaContratos.test.tsx`:

1. Agregue los imports y el mock al principio:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest"
import { rutaRenovacion } from "@/negociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import { renderizarPagina } from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

afterEach(() => {
  sesionDePrueba.roles = ["admin"]
})
```

   (Sustituya el import de `vitest` que ya tiene por el de arriba.)

2. Agregue al `describe("TablaContratos")`:

```tsx
  it("ofrece «Renovar» solo al comprador y solo en contratos vigentes", () => {
    sesionDePrueba.roles = ["comprador"]
    const vigente = {
      ...CONTRATO_CON_SERVICIO_REPETIDO,
      fecha_inicio: "2000-01-01",
      fecha_fin: "2999-12-31",
    }
    const vencido = {
      ...vigente,
      id: "c2",
      folio: "CT-0002",
      fecha_fin: "2000-12-31",
    }
    renderizarPagina(
      <TablaContratos contratos={[vigente, vencido]} proveedorId="p1" />
    )
    expect(
      screen.getByRole("link", { name: "Renovar el contrato CT-0001" })
    ).toHaveAttribute("href", rutaRenovacion("p1", "c1"))
    expect(
      screen.queryByRole("link", { name: "Renovar el contrato CT-0002" })
    ).not.toBeInTheDocument()
  })
```

En `web/src/paginas/ProveedorDetalle.test.tsx`:

1. Importe `sesionDePrueba`:

```tsx
import { sesionDePrueba } from "@/pruebas/sesion"
```

2. Agregue `sesionDePrueba.roles = ["admin"]` al `afterEach`.
3. Agregue al `describe("ProveedorDetalle")`:

```tsx
  it("en Contratos, el comprador puede renovar un contrato vigente", async () => {
    sesionDePrueba.roles = ["comprador"]
    api({
      [`${RUTA}/contratos`]: () =>
        respuestaJson([
          { ...CONTRATO, fecha_inicio: "2000-01-01", fecha_fin: "2999-12-31" },
        ]),
    })
    renderizar("/proveedores/p1?pestana=contratos")
    expect(
      await screen.findByRole("link", { name: "Renovar el contrato CT-0001" })
    ).toHaveAttribute("href", "/negociaciones/nueva?proveedor=p1&contrato=c1")
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run (desde `web/`): `npx vitest run src/paginas/Tablero.test.tsx src/componentes/ElementoAlerta.test.tsx src/componentes/TablaContratos.test.tsx src/paginas/ProveedorDetalle.test.tsx`
Expected: FAIL. No existe ningún enlace «Renovar el contrato …» y `TablaContratos` no acepta `proveedorId`.

- [ ] **Step 3: Write the implementation**

En `web/src/paginas/Tablero.tsx`:

1. Agregue los imports:

```tsx
import { useRoles } from "@/auth"
import { rutaRenovacion } from "@/negociacion"
```

2. En `Vencimientos`, al principio del cuerpo:

```tsx
  const puedeRenovar = useRoles().includes("comprador")
```

3. Agregue la columna al final del encabezado de la tabla, después de «Monto mensual (MXN)»:

```tsx
          {puedeRenovar && (
            <TableHead>
              <span className="sr-only">Acción</span>
            </TableHead>
          )}
```

4. Agregue la celda al final de cada fila, después de la del monto:

```tsx
            {puedeRenovar && (
              <TableCell>
                <Link
                  to={rutaRenovacion(v.proveedor_id, v.contrato_id)}
                  aria-label={`Renovar el contrato ${v.folio}`}
                  className="text-sm font-medium text-accent hover:underline"
                >
                  Renovar
                </Link>
              </TableCell>
            )}
```

En `web/src/componentes/ElementoAlerta.tsx`:

1. Agregue los imports:

```tsx
import { useRoles } from "@/auth"
import { rutaRenovacion } from "@/negociacion"
```

2. Al principio del cuerpo de `ElementoAlerta`:

```tsx
  // Renovar es del rol de compras (spec §10.1) y solo aplica a un contrato por vencer.
  const puedeRenovar =
    useRoles().includes("comprador") &&
    alerta.tipo === "vencimiento" &&
    alerta.entidad_tipo === "contrato"
```

3. Después del párrafo de la explicación (`<p className="text-sm break-words text-muted-foreground">…</p>`):

```tsx
        {puedeRenovar && (
          <Link
            to={rutaRenovacion(alerta.proveedor_id, alerta.entidad_id)}
            aria-label={`Renovar el contrato ${alerta.entidad_nombre}`}
            className="inline-block text-sm font-medium text-accent hover:underline"
          >
            Renovar
          </Link>
        )}
```

En `web/src/componentes/TablaContratos.tsx`:

1. Agregue los imports:

```tsx
import { Link } from "react-router"
import { useRoles } from "@/auth"
import { hoyEnMexico } from "@/fechas"
import { rutaRenovacion } from "@/negociacion"
```

2. Agregue la prop `proveedorId` a la firma:

```tsx
export function TablaContratos({
  contratos,
  mercado,
  proveedorId,
}: {
  contratos: Contrato[]
  mercado?: MercadoLinea[]
  /** Con él, el comprador ve «Renovar» en los contratos vigentes. */
  proveedorId?: string
}) {
```

3. Al principio del cuerpo, antes del `if (contratos.length === 0)` (`useRoles` es un gancho y no puede ir después de ese `return` temprano):

```tsx
  const puedeRenovar = useRoles().includes("comprador") && Boolean(proveedorId)
  const hoy = hoyEnMexico()
  // Fechas "AAAA-MM-DD": compararlas como texto respeta el orden del calendario.
  const vigente = (c: Contrato) => c.fecha_inicio <= hoy && hoy <= c.fecha_fin
```

4. Cambie la celda del folio por:

```tsx
                <TableCell className="font-mono">
                  {i === 0 && (
                    <div className="space-y-1">
                      <div>{c.folio}</div>
                      {puedeRenovar && proveedorId && vigente(c) && (
                        <Link
                          to={rutaRenovacion(proveedorId, c.id)}
                          aria-label={`Renovar el contrato ${c.folio}`}
                          className="font-sans text-sm font-medium text-accent hover:underline"
                        >
                          Renovar
                        </Link>
                      )}
                    </div>
                  )}
                </TableCell>
```

En `web/src/paginas/ProveedorDetalle.tsx`, pase el proveedor a la tabla:

```tsx
                  <TablaContratos
                    contratos={datos}
                    mercado={mercado.data}
                    proveedorId={id}
                  />
```

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/paginas/Tablero.test.tsx src/componentes/ElementoAlerta.test.tsx src/componentes/TablaContratos.test.tsx src/paginas/ProveedorDetalle.test.tsx src/paginas/Alertas.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/paginas/Tablero.tsx web/src/paginas/Tablero.test.tsx web/src/componentes/ElementoAlerta.tsx web/src/componentes/ElementoAlerta.test.tsx web/src/componentes/TablaContratos.tsx web/src/componentes/TablaContratos.test.tsx web/src/paginas/ProveedorDetalle.tsx web/src/paginas/ProveedorDetalle.test.tsx
git commit -m "feat(web): «Renovar» un contrato desde el Tablero, las Alertas y la ficha del proveedor" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Ayuda, guía de uso y README

**Files:**
- Modify: `web/src/ayuda.ts`, `web/src/ayuda.test.ts`
- Modify: `web/src/guia.ts`, `web/src/guia.test.ts`
- Modify: `web/src/componentes/GuiaUso.tsx`, `web/src/componentes/GuiaUso.test.tsx`
- Modify: `web/src/componentes/Layout.tsx`, `web/src/componentes/Layout.test.tsx`
- Modify: `README.md`

**Interfaces:**
- Consumes:
  - las rutas `/negociaciones` (Tasks 2 a 7) y `/portal` (Task 8);
  - lo que ya existe: `ARTICULOS`, `TEMAS`, `buscarArticulos`, `marcarVisita` y `estaActiva`.
- Produces:
  - el tema de ayuda `negociacion` y los artículos `negociar-con-proveedores` y `como-negocia-el-agente`. El segundo es el que pide la spec §10.1 y explica la utilidad, las concesiones y la aceptación sin fórmulas;
  - `marcarVisita(usuario, "negociaciones")`;
  - el paso 4 de la guía, «Negociar», que se marca al visitar `/negociaciones`.

- [ ] **Step 1: Write the failing tests**

En `web/src/ayuda.test.ts`, agregue al `describe("contenido de la ayuda")`:

```ts
  it("explica cómo negocia el agente y cómo supervisarlo", () => {
    expect(
      buscarArticulos("cuándo acepta el agente", false).map((a) => a.slug)
    ).toContain("como-negocia-el-agente")
    expect(
      buscarArticulos("tomar el control", false).map((a) => a.slug)
    ).toContain("negociar-con-proveedores")
    expect(articuloPorSlug("como-negocia-el-agente")?.tema).toBe("negociacion")
  })
```

En `web/src/guia.test.ts`, en cada objeto esperado de `EstadoGuia`, agregue `negociaciones: false` a `visitas`. Por ejemplo, en «empieza visible y sin visitas» y en «un valor corrupto cuenta como estado inicial»:

```ts
      visitas: { proveedores: false, precios: false, negociaciones: false },
```

Agregue también:

```ts
  it("registra la visita a Negociaciones", () => {
    const { result } = renderHook(() => useGuia(ANA))
    act(() => marcarVisita(ANA, "negociaciones"))
    expect(result.current.visitas.negociaciones).toBe(true)
  })
```

En `web/src/componentes/GuiaUso.test.tsx`:

1. **El total de pasos.** Cambie cada `"… de 3 listos"` por `"… de 4 listos"`.
2. **El paso 4.** En «con datos importados marca el paso 1 y cuenta el avance», reemplace `expect(paso(4)).toHaveTextContent("Próximamente")` por:

```tsx
    expect(paso(4)).toHaveTextContent("Pendiente")
    expect(
      within(paso(4)).getByRole("link", { name: "Ver negociaciones" })
    ).toHaveAttribute("href", "/negociaciones")
```

3. **La prueba nueva.** Agregue:

```tsx
  it("la visita a Negociaciones marca el paso 4", async () => {
    conProveedores(60)
    localStorage.setItem(
      claveGuia(USUARIO_DE_PRUEBA),
      JSON.stringify({
        oculta: false,
        visitas: { proveedores: true, precios: true, negociaciones: true },
      })
    )
    renderizarPagina(<GuiaUso />)
    expect(await screen.findByText("4 de 4 listos")).toBeInTheDocument()
  })
```

En `web/src/componentes/Layout.test.tsx`, junto a «visitar Proveedores lo marca como visto en la guía»:

```tsx
  it("visitar Negociaciones lo marca como visto en la guía", () => {
    renderizar("/negociaciones")
    expect(
      JSON.parse(localStorage.getItem(claveGuia(USUARIO_DE_PRUEBA)) ?? "{}")
        .visitas.negociaciones
    ).toBe(true)
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run (desde `web/`): `npx vitest run src/ayuda.test.ts src/guia.test.ts src/componentes/GuiaUso.test.tsx src/componentes/Layout.test.tsx`
Expected: FAIL. No existen los artículos, la visita `negociaciones` ni el paso 4 «Negociar».

- [ ] **Step 3: Write the implementation**

En `web/src/ayuda.ts`:

1. Cambie el tipo de los temas:

```ts
export type TemaAyuda =
  | "primeros-pasos"
  | "proveedores-precios"
  | "negociacion"
  | "datos"
  | "administracion"
```

2. En `TEMAS`, agregue después de «Proveedores y precios»:

```ts
  {
    clave: "negociacion",
    titulo: "Negociación",
    descripcion: "Crear negociaciones, fijar sus límites y supervisar al agente.",
  },
```

3. En «Cómo usar PluriOne», cambie el cuarto paso por:

```ts
          "En Negociaciones crea una negociación y fija sus límites; un agente negocia por usted con cada proveedor, y usted supervisa y puede intervenir. La aprobación de cada cierre llegará en una próxima versión.",
```

4. En «Entrar y moverse por la plataforma», sección «El menú», cambie «Resumen, Proveedores, Inteligencia, Sistema (solo administración) y Soporte» por «Resumen, Proveedores, Inteligencia, Negociación, Sistema (solo administración) y Soporte».

5. Agregue a `ARTICULOS`, después de los de «Proveedores y precios»:

```ts
  {
    slug: "negociar-con-proveedores",
    tema: "negociacion",
    titulo: "Crear y supervisar una negociación",
    resumen: "Del borrador a la publicación, y cómo intervenir en una sesión.",
    secciones: [
      {
        titulo: "Crear la negociación",
        pasos: [
          "En Negociaciones, pulse «Nueva negociación». Para renovar un contrato, use «Renovar» en el Tablero, en una alerta de vencimiento o en los contratos de la ficha del proveedor: la negociación toma del contrato los servicios, el plazo y al proveedor.",
          "Escriba el título, la fecha límite, las rondas y el estilo del agente. En una compra, elija los servicios con su cantidad y a los proveedores que invita (hasta 10).",
          "Al crear el borrador se guarda la referencia de precios de ese momento; con ella se sugieren el ideal y el límite de cada servicio.",
        ],
      },
      {
        titulo: "Fijar los límites",
        parrafos: [
          "En el borrador revise el ideal y el límite del precio de cada servicio, junto a la banda P25 · P50 · P75. Si el límite queda arriba del P75, verá un aviso: puede publicar, pero pagaría más que en tres de cada cuatro contratos.",
          "Active las demás palancas que le importen (plazo, plazo de pago, SLA, tope de aumento o cuota de implementación) y reparta 100 puntos de peso entre ellas y el precio. El total se ve mientras escribe.",
          "Guarde los cambios y pulse «Publicar». Si otra persona cambió el borrador al mismo tiempo, la plataforma se lo dice y le ofrece recargar.",
        ],
      },
      {
        titulo: "Publicar y compartir los enlaces",
        parrafos: [
          "Al publicar, cada proveedor recibe por correo su enlace personal, y usted lo ve una sola vez para copiarlo. Si un correo no sale o un proveedor pierde su enlace, use «Reenviar invitación»: el enlace anterior deja de servir.",
        ],
      },
      {
        titulo: "Supervisar e intervenir",
        parrafos: [
          "La negociación muestra una sesión por proveedor, con su estado, quién la atiende, la ronda y qué tan buena es su última oferta para usted. La pantalla se actualiza sola cada pocos segundos.",
          "En una sesión verá la conversación, las ofertas y, en cada respuesta del agente, «¿Por qué respondió esto?». Con «Tomar el control» usted responde a mano: un mensaje, una contraoferta, aceptar la última oferta o cerrar sin acuerdo. Si lo que acepta o propone sale de sus límites, la plataforma le pide confirmarlo y lo marca para el aprobador. «Devolver al agente» le regresa la sesión.",
          "Si un proveedor pide hablar con una persona, su sesión aparece como «Escalada» hasta que usted la atienda y la devuelva.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Negociaciones", ruta: "/negociaciones" }],
  },
  {
    slug: "como-negocia-el-agente",
    tema: "negociacion",
    titulo: "Cómo negocia el agente",
    resumen:
      "Qué tan buena es una oferta para usted, cuánto cede el agente y cuándo acepta.",
    secciones: [
      {
        titulo: "Qué tan buena es una oferta para usted",
        parrafos: [
          "El agente califica cada oferta de 0 % a 100 %: 100 % es conseguir su ideal en todo y 0 % es quedar exactamente en su límite. Cada término cuenta según el peso que usted le dio.",
        ],
      },
      {
        titulo: "Cuánto cede en cada ronda",
        parrafos: [
          "El agente empieza pidiendo su ideal y, ronda tras ronda, se conforma con un poco menos, hasta llegar a su límite en la última. El estilo decide el ritmo: firme cede poco y tarde, balanceado cede de forma pareja y flexible cede pronto.",
          "Nunca pide algo peor para usted que lo que el proveedor ya ofreció, no revela su límite antes de la última ronda y no retrocede de una ronda a otra, salvo por un paso mínimo de redondeo que evita revelar el límite.",
        ],
      },
      {
        titulo: "Cuándo acepta",
        parrafos: [
          "Acepta cuando la oferta respeta todos sus límites y vale para usted al menos lo que el agente pediría en esa ronda. En la última ronda acepta cualquier oferta dentro de sus límites; si la oferta cruza alguno, cierra sin acuerdo.",
          "El acuerdo es tentativo: no es vinculante hasta que se adjudique y se apruebe.",
        ],
      },
      {
        titulo: "Lo que nunca hace",
        parrafos: [
          "No acepta nada fuera de sus límites, y nunca muestra al proveedor sus límites, sus pesos ni las ofertas de otros proveedores. Si otro proveedor ofreció algo mejor, solo dice que hay propuestas más competitivas.",
          "Si un precio parece un error de captura (menos de la décima parte o más de 10 veces la referencia de precio o, si no hay referencia, su límite), le pide al proveedor confirmarlo antes de responder, y esa respuesta no cuenta como ronda.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Negociaciones", ruta: "/negociaciones" }],
  },
```

   Cuidado: la prueba existente `buscarArticulos("precio justo", false)` debe seguir devolviendo solo `precio-justo`. Por eso ningún artículo nuevo usa la palabra «justo».

En `web/src/guia.ts`:

1. Cambie el tipo y el estado inicial:

```ts
export type EstadoGuia = {
  oculta: boolean
  visitas: { proveedores: boolean; precios: boolean; negociaciones: boolean }
}

const INICIAL: EstadoGuia = {
  oculta: false,
  visitas: { proveedores: false, precios: false, negociaciones: false },
}
```

2. En `interpretar`, agregue a `visitas`:

```ts
        negociaciones: valor?.visitas?.negociaciones === true,
```

3. En `marcarVisita`, cambie el tipo del parámetro a `seccion: "proveedores" | "precios" | "negociaciones"`.

En `web/src/componentes/Layout.tsx`, dentro del efecto que marca las visitas, agregue:

```tsx
    if (estaActiva("/negociaciones", pathname))
      marcarVisita(usuario, "negociaciones")
```

y actualice el comentario de arriba: «La guía del Tablero marca como vistos Proveedores, Precios y Negociaciones cuando se visitan.»

En `web/src/componentes/GuiaUso.tsx`:

1. **El paso 4.** Reemplácelo por:

```tsx
    {
      titulo: "Negociar",
      descripcion:
        "Un agente negocia por usted dentro de sus límites; usted supervisa y puede intervenir.",
      estado: guia.visitas.negociaciones ? "hecho" : "pendiente",
      accion: guia.visitas.negociaciones
        ? undefined
        : enlace("Ver negociaciones", "/negociaciones"),
    },
```

2. **El estado «proximamente».** Ningún paso lo usa ya: quítelo del tipo `Paso`, de `NOMBRE_ESTADO` y de la `variant` del `Badge`. La variante queda en `paso.estado === "hecho" ? "success" : "secondary"`.
3. **El conteo.** Cambie `{listos} de 3 listos` por `{listos} de {pasos.length} listos`.
4. **El comentario de la función.** Debe decir «Los 4 pasos del flujo de trabajo, con su avance; se puede ocultar.»

En `README.md`:

1. En la sección «Interfaz», agregue al final:

```markdown
- **Negociación** (`web/src/negociacion.ts`):
  - Negociaciones: lista, creación de compras y de renovaciones, y editor de límites con la referencia de precios;
  - publicación, con enlaces que se muestran una sola vez;
  - supervisión de cada sesión, que se actualiza cada 3 s, e intervención manual;
  - «Renovar» en el Tablero, en las Alertas y en la ficha del proveedor.
- **Portal del proveedor** (`/portal`): el proveedor entra con el enlace de su invitación, sin cuenta. Ve qué se negocia, la conversación y la última propuesta del agente, y puede enviar ofertas o pedir hablar con una persona.
```

2. En «Limitaciones conocidas», borre la viñeta «**Negociación sin interfaz todavía.** …» completa (tres líneas).

- [ ] **Step 4: Run tests to verify they pass**

Run (desde `web/`): `npx vitest run src/ayuda.test.ts src/guia.test.ts src/componentes/GuiaUso.test.tsx src/componentes/Layout.test.tsx src/paginas/Ayuda.test.tsx src/paginas/Tablero.test.tsx`
Expected: PASS.

Run: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add web/src/ayuda.ts web/src/ayuda.test.ts web/src/guia.ts web/src/guia.test.ts web/src/componentes/GuiaUso.tsx web/src/componentes/GuiaUso.test.tsx web/src/componentes/Layout.tsx web/src/componentes/Layout.test.tsx README.md
git commit -m "docs(web): ayuda de la negociación, paso «Negociar» en la guía y README" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Revisión en navegador y documentación

La hace el **controlador**, no un subagente: necesita el stack completo, iniciar sesión con los usuarios de desarrollo, Mailpit y el panel de navegador.

Recorre el flujo que cierra N1b (spec §15):
1. crear una compra y una renovación, esta desde el Tablero;
2. publicar y ver el correo en Mailpit;
3. negociar desde el portal hasta un acuerdo tentativo;
4. escalar otra sesión, tomar el control, responder y devolverla;
5. cancelar un evento;
6. ver todo en la bitácora, en Actividad y en Correos.

También pasa axe con la regla de contraste en cada página nueva, a 375, 768, 1024 y 1440 px, en claro y oscuro, incluido el portal (spec §1 y §14).

**Files:**
- Create: `docs/qa/revision-negociacion.md`
- Modify: `README.md` (sección «Interfaz»)
- Las correcciones que salgan van cada una en su propio commit `fix(web): …`, con su prueba.

- [ ] **Step 1: Verificación previa**

Run (desde `web/`): `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`
Expected: todo en verde. Anote cuántos archivos y pruebas pasaron, y el tamaño del chunk principal.

- [ ] **Step 2: Levantar el stack y la prueba de humo**

```bash
docker compose -f infra/docker-compose.yml up -d --build --wait
```

```bash
uv run python infra/smoke_test.py
```

Expected: la prueba de humo termina con `OK: …` e incluye la negociación. Si las copias de proveedores o servicios de `negociacion` están vacías en un entorno que ya existía, siga «Activar la negociación en un entorno ya creado» del README antes de seguir.

- [ ] **Step 3: Recorrer los flujos en el gateway**

**Cómo recorrerlos:**
- **Dónde:** el gateway (<http://localhost:8080>), que tiene CSP. Mailpit está en <http://localhost:8025>.
- **Usuarios:** `comprador1`, `aprobador1` y `admin1`. Sus contraseñas están en `infra/keycloak/realm-plataforma.json` y no se escriben en el documento.
- **El portal** se abre en otra pestaña del panel, sin sesión de Keycloak.
- **Vista:** tema claro, a 1440 px.

| # | Flujo | Qué comprobar |
|---|---|---|
| 1 | Negociaciones (comprador1) | La lista vacía lo explica. «Nueva negociación» está a la vista. Con aprobador1 no aparece el botón. |
| 2 | Crear una compra | Dos servicios del catálogo con su cantidad y dos o tres proveedores (buscador y elegidos). Al crear, abre el editor. |
| 3 | Editor del borrador | Banda P25/P50/P75 por línea, con las sugerencias. Al activar «Plazo de pago», el total de pesos cambia en vivo («Total: 120 de 100»). Con 80/20 y los ideales y límites, «Guardar cambios». Un límite sobre P75 muestra el aviso y deja publicar. «Publicar» está deshabilitado con cambios sin guardar. |
| 4 | Publicar | El diálogo muestra cada enlace una vez, con «Copiar». Al cerrarlo no vuelve. Mailpit tiene un correo por proveedor con el enlace (`/portal#t=…`). |
| 5 | Portal: negociar hasta un acuerdo | Abra el enlace del primer proveedor: el `#t=…` desaparece de la barra y recargar sigue funcionando. Ofrezca por encima del límite y vea la contraoferta del agente. Use «Aceptar esta propuesta» y envíe: se ve «Acuerdo tentativo» y el formulario desaparece. En la web, la sesión pasa a «Acuerdo tentativo» y «¿Por qué respondió esto?» explica cada respuesta. |
| 6 | Portal: precio raro | Un precio menor que la décima parte de la referencia pide «Confirmo estos valores». La ronda no avanza hasta confirmarlo. |
| 7 | Escalar y atender a mano | En el portal de otro proveedor, «Hablar con una persona». En la web: «Escalada» en la tabla, «Tomar el control», responder con una contraoferta dentro de los límites (el portal la muestra en ≤ 3 s) y «Devolver al agente». Una aceptación fuera de límites pide confirmar y marca «Fuera de límites». |
| 8 | Renovar desde el Tablero | En «Próximos vencimientos», «Renovar» abre la renovación con el título, las líneas y el proveedor del contrato. El editor muestra el precio vigente y, al activar una palanca, propone el valor vigente como límite. Publíquela. |
| 9 | Reenviar y cancelar | «Reenviar invitación» da un enlace nuevo; el viejo muestra «El enlace no es válido o ya venció». «Cancelar negociación» con motivo; después, el enlace de esa negociación tampoco sirve. |
| 10 | Bitácora, Actividad y Correos (admin1) | En la base, `docker compose -f infra/docker-compose.yml exec -T postgres psql -U postgres -d negociacion_db -c "select accion, actor_tipo, count(*) from bitacora group by 1, 2 order by 1"` muestra la publicación, las ofertas, las decisiones del motor, el control y la cancelación. Actividad muestra «Negociación» con publicar, cancelar e invitaciones. Correos muestra «Invitación a negociar». |
| 11 | Consola y red | Sin errores de CSP ni de JavaScript. Las llamadas a `/api/negociacion` responden 200. Los únicos 401 son los del portal con enlaces viejos, y ninguna URL ni encabezado registrado en la consola contiene el token. |

- [ ] **Step 4: axe y scroll horizontal por ancho**

El servidor de Vite (<http://localhost:5173>, sin CSP) permite inyectar axe-core desde `/node_modules/axe-core/axe.min.js`, igual que en `docs/qa/revision-visual-plan-a.md`.

**Condiciones:**
- Reglas: WCAG 2.0, 2.1 y 2.2, niveles A y AA, **con** la regla de contraste.
- Anchos: 375, 768, 1024 y 1440 px, en tema claro y en tema oscuro.

**Rutas:**
- Negociaciones;
- Nueva negociación, como compra y como renovación;
- el editor del borrador con una palanca activa;
- una negociación abierta con sesiones;
- una sesión con el formulario de respuesta manual abierto;
- el portal: activo, con la propuesta, en acuerdo tentativo y con un enlace inválido.

En cada caso, anote las violaciones de axe y si `document.documentElement.scrollWidth <= window.innerWidth`.

- [ ] **Step 5: Corregir lo que salga**

Por cada defecto:
1. Escriba su prueba en jsdom (si se puede) y véala fallar.
2. Corríjalo.
3. Haga un commit `fix(web): …` con el mensaje de dos `-m`.

Si un defecto no se puede probar en jsdom (contraste o diseño), dígalo en el documento.

- [ ] **Step 6: Escribir `docs/qa/revision-negociacion.md`**

Use la estructura de `docs/qa/revision-inteligencia-interfaz.md`:
- cabecera con fecha, commit revisado, usuarios de prueba (sin contraseñas) y alcance;
- «Entorno y método»;
- la tabla de flujos del Step 3 con su resultado;
- la tabla de axe y scroll por ancho;
- la tabla de defectos (defecto, causa, corrección y commit);
- lo que quedó pendiente, si algo quedó.

- [ ] **Step 7: Actualizar el README**

En `README.md`, sección «Interfaz», cambie la línea de la revisión de accesibilidad por:

```markdown
- Revisión de accesibilidad y diseño adaptable: `docs/qa/revision-visual-plan-a.md` (Plan A), `docs/qa/revision-inteligencia-interfaz.md` (inteligencia en la interfaz) y `docs/qa/revision-negociacion.md` (negociación y portal del proveedor).
```

- [ ] **Step 8: Commit**

```bash
git add docs/qa/revision-negociacion.md README.md
git commit -m "docs: revisión en navegador de la negociación y del portal del proveedor" -m "Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>"
```
