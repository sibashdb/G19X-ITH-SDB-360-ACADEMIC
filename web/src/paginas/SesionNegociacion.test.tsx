import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SesionNegociacion } from "@/paginas/SesionNegociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaDiferida,
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

/** `junto` se dibuja al lado de la página, como el contenedor enfocable del Layout. */
function abrir(junto?: ReactNode) {
  return renderizarPagina(
    <>
      <SesionNegociacion />
      {junto}
    </>,
    {
      ruta: `/negociaciones/e1/sesiones/${SID}`,
      patron: "/negociaciones/:id/sesiones/:sesion",
    }
  )
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

  it("muestra lo interpretado del mensaje del proveedor", async () => {
    const libre = {
      id: "m3",
      autor: "proveedor",
      texto: "Le dejo el usuario en 1,300",
      ronda: 1,
      fecha: "2026-10-14T18:12:00Z",
      oferta_id: null,
      decision: null,
      interpretacion: {
        intencion: "oferta",
        precios: { l1: "1300" },
        palancas: {},
        confianza: 0.82,
        modelo: "qwen2.5:3b",
      },
      redaccion: null,
    }
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({ ...SESION, mensajes: [...SESION.mensajes, libre] }),
    })
    abrir()
    expect(
      await screen.findByText("Interpretado: oferta · confianza 82 %")
    ).toBeInTheDocument()
  })

  it("dice si la respuesta la redactó el LLM o la plantilla", async () => {
    const [primero, segundo] = SESION.mensajes
    const delLlm = {
      ...segundo,
      redaccion: { origen: "llm", modelo: "qwen2.5:3b", motivo: null },
    }
    const dePlantilla = {
      ...segundo,
      id: "m4",
      oferta_id: null,
      decision: null,
      redaccion: { origen: "plantilla", modelo: null, motivo: "sin_ia" },
    }
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({ ...SESION, mensajes: [primero, delLlm, dePlantilla] }),
    })
    abrir()
    expect(
      await screen.findByText("Redactado por el LLM (qwen2.5:3b)")
    ).toBeInTheDocument()
    expect(screen.getByText("Respuesta de plantilla")).toBeInTheDocument()
  })

  it("un mensaje anterior a la primera oferta no dice «Ronda 0»", async () => {
    const escalada = {
      id: "m0",
      autor: "proveedor",
      texto: "Pidió hablar con una persona del equipo de compras.",
      ronda: 0,
      fecha: "2026-10-14T18:09:00Z",
      oferta_id: null,
      decision: null,
    }
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson({ ...SESION, mensajes: [escalada, ...SESION.mensajes] }),
    })
    abrir()
    await screen.findByText(escalada.texto)
    expect(screen.queryByText("Ronda 0")).not.toBeInTheDocument()
    expect(screen.getAllByText("Ronda 1")).toHaveLength(2)
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

  it("«Devolver al agente» que termina la sesión deja el foco en el contenido", async () => {
    // Al devolverla, el agente contesta la respuesta pendiente y acepta: la sesión ya no se controla.
    let terminada = false
    const final = { ...SESION, estado: "acuerdo_tentativo", modo: "agente" }
    simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson(terminada ? final : { ...SESION, modo: "comprador" }),
      [`POST ${RUTA}/control`]: () => {
        terminada = true
        return respuestaJson(final)
      },
    })
    abrir(<div id="contenido" tabIndex={-1} />)
    await userEvent.click(
      await screen.findByRole("button", { name: "Devolver al agente" })
    )
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Devolver al agente" })
      ).not.toBeInTheDocument()
    )
    expect(document.getElementById("contenido")).toHaveFocus()
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
    // userEvent descarta los ceros finales de un decimal en un campo numérico de jsdom.
    fireEvent.change(precio, { target: { value: "90.00" } })
    await userEvent.click(
      screen.getByRole("button", { name: "Enviar respuesta" })
    )
    expect(
      await screen.findByText("Se envió su respuesta.")
    ).toBeInTheDocument()
    const { cuerpo, cabeceras } = llamadaA(api, `${RUTA}/respuestas`, "POST")
    expect(cuerpo).toEqual({
      tipo: "mensaje",
      texto: "Podemos llegar a 90.",
      contraoferta: {
        precios: { l1: "90.00" },
        palancas: { plazo_pago_dias: "55" },
      },
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
    await userEvent.click(
      screen.getByRole("button", { name: "Enviar respuesta" })
    )
    const aviso = await screen.findByRole("alertdialog", {
      name: "Esto sale de sus límites",
    })
    expect(aviso).toHaveTextContent("el aprobador lo verá")
    const primera = llamadaA(api, `${RUTA}/respuestas`, "POST")
    await userEvent.click(
      within(aviso).getByRole("button", { name: "Enviar de todos modos" })
    )
    expect(
      await screen.findByText("Se envió su respuesta.")
    ).toBeInTheDocument()
    const segunda = llamadaA(api, `${RUTA}/respuestas`, "POST")
    expect(segunda.cuerpo).toMatchObject({ confirmar_fuera_de_limites: true })
    expect(segunda.cabeceras.get("Idempotency-Key")).not.toBe(
      primera.cabeceras.get("Idempotency-Key")
    )
  })

  it("aceptar la última oferta pide confirmación y el foco pasa al contenido", async () => {
    // La petición tarda: el diálogo devuelve el foco a su botón antes de que termine.
    const respuesta = respuestaDiferida()
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () => respuesta.promesa,
    })
    // El contenedor enfocable del Layout: al terminar la sesión desaparece el botón con el foco.
    abrir(<div id="contenido" tabIndex={-1} />)
    const aceptar = await screen.findByRole("button", {
      name: "Aceptar la última oferta",
    })
    await userEvent.click(aceptar)
    await userEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Aceptar oferta",
      })
    )
    await waitFor(() => expect(aceptar).toHaveFocus())
    respuesta.resolver(respuestaJson(ESCALADA))
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
    // El foco se mueve después de recargar la sesión, no antes.
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
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
    await userEvent.click(
      screen.getByRole("button", { name: "Enviar respuesta" })
    )
    expect(
      await screen.findByText("Use a lo más 2 decimales.")
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText("Precio de Correo en la nube")
    ).toHaveAttribute("aria-invalid", "true")
  })

  it("muestra en un aviso el error del servicio aunque ningún campo lo muestre", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los campos indicados.",
            codigo: "invalido",
            errores: [
              {
                campo: "body",
                mensaje: "Escriba el mensaje para el proveedor.",
              },
            ],
          },
          422
        ),
    })
    abrir()
    // Solo espacios: pasa `required` del navegador y el servicio lo rechaza.
    await userEvent.type(
      await screen.findByLabelText("Mensaje para el proveedor"),
      "   "
    )
    await userEvent.click(
      screen.getByRole("button", { name: "Enviar respuesta" })
    )
    const alerta = await screen.findByRole("alert")
    expect(alerta).toHaveTextContent("Revise los campos indicados.")
    // El mensaje del campo que ningún control muestra no se pierde.
    expect(alerta).toHaveTextContent("Escriba el mensaje para el proveedor.")
  })

  it("al enviar un mensaje con Enter desde un precio el foco vuelve al mensaje", async () => {
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () => respuestaJson(ESCALADA),
    })
    abrir()
    await escribirContraoferta("90.10")
    // El cursor sigue en el precio: Enter envía el formulario y la contraoferta se cierra.
    await userEvent.keyboard("{Enter}")
    expect(
      await screen.findByText("Se envió su respuesta.")
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByLabelText("Mensaje para el proveedor")).toHaveFocus()
    )
  })

  it("Revisar cierra el aviso de límites sin enviar de nuevo", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "La contraoferta sale de sus límites.",
            codigo: "fuera_de_limites",
          },
          422
        ),
    })
    abrir()
    await escribirContraoferta("120.00")
    await userEvent.click(
      screen.getByRole("button", { name: "Enviar respuesta" })
    )
    const aviso = await screen.findByRole("alertdialog", {
      name: "Esto sale de sus límites",
    })
    await userEvent.click(
      within(aviso).getByRole("button", { name: "Revisar" })
    )
    await waitFor(() =>
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    )
    const envios = api.mock.calls.filter(
      ([url, init]) =>
        url === `${RUTA}/respuestas` &&
        (init as RequestInit | undefined)?.method === "POST"
    )
    expect(envios).toHaveLength(1)
  })

  it("dos mensajes iguales, uno tras otro, llevan Idempotency-Key distinta", async () => {
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(ESCALADA),
      [`POST ${RUTA}/respuestas`]: () => respuestaJson(ESCALADA),
    })
    abrir()
    const enviar = async () => {
      await userEvent.type(
        await screen.findByLabelText("Mensaje para el proveedor"),
        "Quedamos atentos."
      )
      await userEvent.click(
        screen.getByRole("button", { name: "Enviar respuesta" })
      )
    }
    const envios = () =>
      api.mock.calls.filter(
        ([url, init]) =>
          url === `${RUTA}/respuestas` &&
          (init as RequestInit | undefined)?.method === "POST"
      )
    await enviar()
    await waitFor(() => expect(envios()).toHaveLength(1))
    // El aviso del primero sigue en pantalla: la prueba espera a que el formulario se limpie.
    await waitFor(() =>
      expect(screen.getByLabelText("Mensaje para el proveedor")).toHaveValue("")
    )
    await enviar()
    await waitFor(() => expect(envios()).toHaveLength(2))
    const [primero, segundo] = envios().map(([, init]) =>
      new Headers((init as RequestInit).headers).get("Idempotency-Key")
    )
    expect(primero).toMatch(/^[0-9a-f-]{36}$/)
    expect(segundo).toMatch(/^[0-9a-f-]{36}$/)
    expect(segundo).not.toBe(primero)
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
