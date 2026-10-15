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
      valores: {
        precios: { l1: "120.00" },
        palancas: { plazo_pago_dias: "15" },
      },
      utilidad: 0.2,
      valida: false,
      fuera_de_limites_confirmada: false,
      fecha: "2026-10-14T18:10:00Z",
    },
    {
      id: "o2",
      autor: "agente",
      ronda: 1,
      valores: {
        precios: { l1: "89.00" },
        palancas: { plazo_pago_dias: "55" },
      },
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
        respuestaJson(
          { title: "No encontrado", detail: "La sesión no existe." },
          404
        ),
    })
    abrir()
    expect(await screen.findByText("La sesión no existe.")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
  })

  it("muestra la conversación, las ofertas y por qué respondió el agente", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(SESION) })
    const { container } = abrir()
    expect(
      await screen.findByText("Es nuestra mejor oferta.")
    ).toBeInTheDocument()
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

  it("anuncia cada mensaje nuevo del proveedor aunque lleguen en el mismo minuto", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let lecturas = 0
    const mensajeNuevo = (id: string, texto: string, fecha: string) => ({
      id,
      autor: "proveedor",
      texto,
      ronda: 2,
      fecha,
      oferta_id: null,
      decision: null,
    })
    const m3 = mensajeNuevo("m3", "Bajamos a 100.", "2026-10-14T18:20:00Z")
    const m4 = mensajeNuevo("m4", "Bajamos a 95.", "2026-10-14T18:20:30Z")
    simularRutas({
      [`GET ${RUTA}`]: () => {
        lecturas += 1
        const nuevos = lecturas === 1 ? [] : lecturas === 2 ? [m3] : [m3, m4]
        return respuestaJson({
          ...SESION,
          mensajes: [...SESION.mensajes, ...nuevos],
        })
      },
    })
    abrir()
    await screen.findByText("Es nuestra mejor oferta.")
    await vi.advanceTimersByTimeAsync(3100)
    await screen.findByText("Bajamos a 100.")
    const anuncio = screen.getByText(/^Nuevo mensaje del proveedor, /)
    expect(anuncio).toHaveAttribute("aria-atomic", "true")
    const primero = anuncio.textContent
    await vi.advanceTimersByTimeAsync(3100)
    await screen.findByText("Bajamos a 95.")
    expect(
      screen.getByText(/^Nuevo mensaje del proveedor, /).textContent
    ).not.toBe(primero)
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
