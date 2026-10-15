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
  palancas: [
    { clave: "plazo_pago_dias", nombre: "Plazo de pago", unidad: "días" },
  ],
  mensajes: [
    {
      autor: "proveedor",
      texto: "Es nuestra mejor oferta.",
      ronda: 1,
      fecha: "2026-10-14T18:10:00Z",
      oferta: {
        precios: { l1: "120.00" },
        palancas: { plazo_pago_dias: "15" },
      },
    },
    {
      autor: "agente",
      texto: "Gracias por su oferta. Le proponemos lo siguiente.",
      ronda: 1,
      fecha: "2026-10-14T18:10:01Z",
      oferta: { precios: { l1: "98.00" }, palancas: { plazo_pago_dias: "45" } },
    },
  ],
  ultima_propuesta: {
    precios: { l1: "98.00" },
    palancas: { plazo_pago_dias: "45" },
  },
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
          {
            title: "No autorizado",
            detail: "El enlace no es válido o ya venció.",
          },
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
    expect(screen.getByLabelText("Precio de Correo en la nube")).toHaveValue(
      null
    )
  })

  it("reintentar el mismo envío reutiliza la clave y una oferta nueva usa otra", async () => {
    let intentos = 0
    // El tipo declara `init` para leer las cabeceras de cada llamada sin un parámetro sin usar.
    const api = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(
      (url) => {
        if (url === OFERTAS) {
          intentos += 1
          if (intentos === 1)
            return Promise.reject(new TypeError("Failed to fetch"))
        }
        return Promise.resolve(respuestaJson(VISTA))
      }
    )
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
      [`GET ${SESION}`]: () =>
        respuestaJson({ ...VISTA, pide_confirmacion: true }),
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
        respuestaJson({
          ...VISTA,
          atendido_por: persona ? "persona" : "agente",
        }),
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
    expect(
      await screen.findByText("Le atiende una persona")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Hablar con una persona" })
    ).not.toBeInTheDocument()
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Enviar oferta" })
      ).toHaveFocus()
    )
    expect(
      llamadaA(api, ESCALAR, "POST").cabeceras.get("Idempotency-Key")
    ).toMatch(/^[0-9a-f-]{36}$/)
  })

  it("mientras atiende una persona, la página se actualiza sola", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = simularRutas({
      [`GET ${SESION}`]: () =>
        respuestaJson({ ...VISTA, atendido_por: "persona" }),
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
        respuestaJson({
          ...VISTA,
          estado: "acuerdo_tentativo",
          ultima_propuesta: null,
        }),
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
      [`GET ${SESION}`]: () =>
        respuestaJson({ ...VISTA, estado: "sin_acuerdo" }),
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
              {
                campo: "valores.precios.l1",
                mensaje: "Indique el precio de esta línea.",
              },
            ],
          },
          422
        ),
    })
    abrirCon()
    await userEvent.type(
      await screen.findByLabelText("Plazo de pago (días)"),
      "30"
    )
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    expect(
      await screen.findByText("Indique el precio de esta línea.")
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText("Precio de Correo en la nube")
    ).toHaveAttribute("aria-invalid", "true")
  })

  it("un error de campo que no es de ningún control también se muestra como alerta", async () => {
    simularRutas({
      [`GET ${SESION}`]: () => respuestaJson(VISTA),
      [`POST ${OFERTAS}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los campos indicados.",
            codigo: "oferta_invalida",
            errores: [
              { campo: "body", mensaje: "La nota no puede ir en blanco." },
            ],
          },
          422
        ),
    })
    abrirCon()
    await userEvent.type(
      await screen.findByLabelText("Precio de Correo en la nube"),
      "100"
    )
    await userEvent.type(screen.getByLabelText("Plazo de pago (días)"), "30")
    await userEvent.click(screen.getByRole("button", { name: "Enviar oferta" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Revise los campos indicados."
    )
  })
})
