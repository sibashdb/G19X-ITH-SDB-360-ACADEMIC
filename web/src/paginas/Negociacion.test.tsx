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
    const api = simularRutas({
      [`GET ${RUTA}`]: () => respuestaJson(BORRADOR),
      [`PATCH ${RUTA}`]: () => respuestaJson(BORRADOR),
    })
    abrir()
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
    await userEvent.click(
      await screen.findByRole("button", { name: "Publicar" })
    )
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
      within(dialogo).getByText(
        "Se envió por correo a lucia@nubenorte.example."
      )
    ).toBeInTheDocument()
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Listo" })
    )
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
