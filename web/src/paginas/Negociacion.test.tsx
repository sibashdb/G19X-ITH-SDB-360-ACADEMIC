import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Negociacion } from "@/paginas/Negociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinEnMutaciones,
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaDiferida,
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

/** `junto` se dibuja al lado de la página, como el contenedor enfocable del Layout. */
function abrir(junto?: ReactNode) {
  return renderizarPagina(
    <>
      <Negociacion />
      {junto}
    </>,
    {
      ruta: `/negociaciones/${ID}`,
      patron: "/negociaciones/:id",
    }
  )
}

/** El servidor de una publicación: el GET devuelve el borrador y, tras publicar, la negociación abierta. */
function simularPublicacion(correoEstado = "enviado") {
  let publicado = false
  const ABIERTO = {
    ...BORRADOR,
    estado: "abierto",
    publicado_en: "2026-10-14T19:00:00Z",
    version: 4,
  }
  return simularRutas({
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
            correo_estado: correoEstado,
          },
        ],
      })
    },
  })
}

/** Publica desde el editor (botón y confirmación) y devuelve el diálogo con los enlaces. */
async function publicar() {
  await userEvent.click(await screen.findByRole("button", { name: "Publicar" }))
  await userEvent.click(
    within(await screen.findByRole("alertdialog")).getByRole("button", {
      name: "Publicar",
    })
  )
  return screen.findByRole("dialog", { name: "Enlace de invitación" })
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
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
    expect(
      await screen.findByText("La negociación no existe.")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Reintentar" })
    ).toBeInTheDocument()
  })

  it("el editor muestra la banda de referencia junto al ideal y el límite", async () => {
    simularRutas({ [`GET ${RUTA}`]: () => respuestaJson(BORRADOR) })
    const { container } = abrir()
    expect(
      await screen.findByLabelText("Ideal (Correo en la nube)")
    ).toHaveValue(88)
    expect(screen.getByLabelText("Límite (Correo en la nube)")).toHaveValue(95)
    // El tope de Monto en la API: el navegador lo marca antes de que la API responda 422 por índice.
    for (const campo of ["Ideal", "Límite"])
      expect(
        screen.getByLabelText(`${campo} (Correo en la nube)`)
      ).toHaveAttribute("max", "10000000")
    expect(screen.getByText("Típico (P50)")).toBeInTheDocument()
    expect(
      screen.getByText(formatoMoneda("104.0000", "MXN"))
    ).toBeInTheDocument()
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
    // Al guardar, el servidor sube la versión: el editor se vuelve a montar con lo guardado.
    let guardado = false
    const api = simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson(guardado ? { ...BORRADOR, version: 4 } : BORRADOR),
      [`PATCH ${RUTA}`]: () => {
        guardado = true
        return respuestaJson({ ...BORRADOR, version: 4 })
      },
    })
    abrir(<div id="contenido" tabIndex={-1} />)
    const ideal = await screen.findByLabelText("Ideal (Correo en la nube)")
    await userEvent.clear(ideal)
    await userEvent.type(ideal, "85.51")
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )
    expect(
      await screen.findByText("Se guardaron los cambios.")
    ).toBeInTheDocument()
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
          ideal: "85.51",
          limite: "95.00",
        },
      ],
      palancas: [{ clave: "precio", peso: 100 }],
    })
    // El editor se vuelve a montar y el botón enfocado desaparece: el foco pasa al contenido.
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("limpia el aviso al empezar a guardar otra vez, para que el siguiente se anuncie", async () => {
    let version = 3
    let guardados = 0
    const segunda = respuestaDiferida()
    simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson({ ...BORRADOR, version }),
      [`PATCH ${RUTA}`]: () => {
        guardados += 1
        if (guardados === 2) return segunda.promesa
        version += 1
        return respuestaJson({ ...BORRADOR, version })
      },
    })
    abrir()
    const primero = await screen.findByLabelText("Ideal (Correo en la nube)")
    await userEvent.clear(primero)
    await userEvent.type(primero, "85.51")
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )
    expect(
      await screen.findByText("Se guardaron los cambios.")
    ).toBeInTheDocument()
    // La versión nueva vuelve a montar el editor; se edita y se guarda otra vez.
    await waitFor(() => expect(primero).not.toBeInTheDocument())
    const otro = screen.getByLabelText("Ideal (Correo en la nube)")
    await userEvent.clear(otro)
    await userEvent.type(otro, "86.51")
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )
    await waitFor(() =>
      expect(
        screen.queryByText("Se guardaron los cambios.")
      ).not.toBeInTheDocument()
    )
    version = 5
    segunda.resolver(respuestaJson({ ...BORRADOR, version }))
    expect(
      await screen.findByText("Se guardaron los cambios.")
    ).toBeInTheDocument()
  })

  it("cancelar con cambios sin guardar no dispara el guardado del editor", async () => {
    let cancelado = false
    const api = simularRutas({
      [`GET ${RUTA}`]: () =>
        respuestaJson(
          cancelado ? { ...BORRADOR, estado: "cancelado" } : BORRADOR
        ),
      [`POST ${RUTA}/cancelar`]: () => {
        cancelado = true
        return respuestaJson({ ...BORRADOR, estado: "cancelado" })
      },
    })
    abrir()
    await userEvent.type(await screen.findByLabelText("Título"), " (v2)")
    await userEvent.click(
      screen.getByRole("button", { name: "Cancelar borrador" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Cancelar el borrador",
    })
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo"),
      "Ya no se necesita"
    )
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Cancelar borrador" })
    )
    expect(
      await screen.findByText("Se canceló el borrador.")
    ).toBeInTheDocument()
    expect(llamadaA(api, `${RUTA}/cancelar`, "POST").cuerpo).toEqual({
      motivo: "Ya no se necesita",
    })
    // El formulario del diálogo se dibuja en un portal dentro del del editor: no lo envía.
    expect(
      api.mock.calls.filter(([, init]) => init?.method === "PATCH")
    ).toHaveLength(0)
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
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )
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
          errores: [
            { campo: "lineas.0.limite", mensaje: "Indique el precio límite." },
          ],
        }),
    })
    abrir()
    expect(
      await screen.findByText("Indique el precio límite.")
    ).toBeInTheDocument()
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
    await userEvent.type(
      screen.getByLabelText("Ideal (Correo en la nube)"),
      "1"
    )
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
    expect(
      screen.getByRole("button", { name: "Publicar" })
    ).not.toHaveAttribute("aria-disabled")
  })

  it("publica, muestra los enlaces una sola vez y no los deja en caché", async () => {
    simularPublicacion()
    const { cliente } = abrir(<div id="contenido" tabIndex={-1} />)
    const dialogo = await publicar()
    expect(
      within(dialogo).getByText("http://localhost:8080/portal#t=secreto-123")
    ).toBeInTheDocument()
    expect(
      within(dialogo).getByText(
        "Se envió por correo a lucia@nubenorte.example."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Se publicó la negociación y se enviaron las invitaciones."
      )
    ).toBeInTheDocument()
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
    expect(screen.queryByText(/secreto-123/)).not.toBeInTheDocument()
    await esperarSinEnMutaciones(cliente, "secreto-123")
    expect(await screen.findByText("Sus límites")).toBeInTheDocument()
    // El botón «Publicar» ya no existe: el foco pasa al contenido, no a <body>.
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("avisa que no todas las invitaciones se enviaron si algún correo falló", async () => {
    simularPublicacion("fallido")
    abrir()
    const dialogo = await publicar()
    expect(
      within(dialogo).getByText(/No se pudo enviar el correo a lucia@nubenorte/)
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Se publicó la negociación; algunas invitaciones no se enviaron: revise los enlaces."
      )
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/se enviaron las invitaciones/)
    ).not.toBeInTheDocument()
  })

  it("los enlaces no se pierden por un clic fuera: solo Escape o «Listo» los cierran", async () => {
    simularPublicacion()
    abrir()
    await publicar()
    const fondo = document.querySelector('[data-slot="dialog-overlay"]')
    expect(fondo).not.toBeNull()
    await userEvent.click(fondo!)
    expect(
      screen.getByRole("dialog", { name: "Enlace de invitación" })
    ).toBeInTheDocument()
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
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
    // El Layout aporta #contenido; la página sola no lo tiene, así que se dibuja al lado.
    abrir(<div id="contenido" tabIndex={-1} />)
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancelar borrador" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Cancelar el borrador",
    })
    await userEvent.type(
      within(dialogo).getByLabelText("Motivo"),
      "Ya no se necesita"
    )
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Cancelar borrador" })
    )
    expect(
      await screen.findByText("Se canceló el borrador.")
    ).toBeInTheDocument()
    expect(llamadaA(api, `${RUTA}/cancelar`, "POST").cuerpo).toEqual({
      motivo: "Ya no se necesita",
    })
    expect(await screen.findByText("Ya no se necesita")).toBeInTheDocument()
    // El botón que abrió el diálogo se desmonta al quedar cancelada: el foco pasa al contenido.
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
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
    expect(
      await screen.findByText(/Precio vigente: \$95\.00/)
    ).toBeInTheDocument()
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
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
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
