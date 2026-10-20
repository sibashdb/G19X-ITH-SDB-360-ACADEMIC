import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useNavigate } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Negociaciones } from "@/paginas/Negociaciones"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaDiferida,
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

// La consulta de una sola fila con la que el aprobador sabe si tiene propuestas por aprobar.
const PENDIENTES =
  "/api/negociacion/eventos?estado=pendiente_aprobacion&pagina=1&tamano=1"

const POR_APROBAR = {
  total: 2,
  elementos: [{ ...PAGINA.elementos[0], estado: "pendiente_aprobacion" }],
}

/** «Atrás» del navegador: si la redirección hubiera agregado una entrada, volvería a la URL sin filtro. */
function Atras() {
  const navegar = useNavigate()
  return (
    <button type="button" onClick={() => void navegar(-1)}>
      Atrás
    </button>
  )
}

/** Responde la consulta de una fila con `pendientes`, la lista filtrada por las pendientes y, si no, la lista completa. */
function simularAprobador(pendientes: () => Response | Promise<Response>) {
  return simularApi((url) =>
    url === PENDIENTES
      ? pendientes()
      : respuestaJson(
          url.includes("estado=pendiente_aprobacion") ? POR_APROBAR : PAGINA
        )
  )
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
    expect(
      within(tabla).getByText("Licencias de correo 2027")
    ).toBeInTheDocument()
    expect(within(tabla).getByText("Compra")).toBeInTheDocument()
    expect(within(tabla).getByText("Abierta")).toBeInTheDocument()
    expect(within(tabla).getByText("2 de 3")).toBeInTheDocument()
    expect(within(tabla).getByText("1 escalada")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("lista también las negociaciones propuestas, adjudicadas y desiertas", async () => {
    const estados = [
      ["pendiente_aprobacion", "Pendiente de aprobación"],
      ["adjudicado", "Adjudicada"],
      ["desierto", "Desierta"],
    ] as const
    simularApi(() =>
      respuestaJson({
        total: 3,
        elementos: estados.map(([estado], i) => ({
          ...PAGINA.elementos[0],
          id: `5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d4${String(i)}`,
          folio: `NEG-2026-000${String(i + 1)}`,
          estado,
        })),
      })
    )
    const { container } = renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones",
    })
    const tabla = await screen.findByRole("table")
    for (const [, nombre] of estados)
      expect(await within(tabla).findByText(nombre)).toBeInTheDocument()
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
    await userEvent.click(
      within(estados).getByRole("button", { name: "Abierta" })
    )
    expect(ubicacionActual()).toBe("/negociaciones?estado=abierto")
    await waitFor(() =>
      expect(urlDeLlamada(api).searchParams.get("estado")).toBe("abierto")
    )
    expect(urlDeLlamada(api).searchParams.get("pagina")).toBe("1")
    expect(
      within(estados).getByRole("button", { name: "Abierta" })
    ).toHaveAttribute("aria-pressed", "true")
  })

  it("los filtros dicen Por aprobar, Adjudicada y Desierta, y Por aprobar filtra por las pendientes", async () => {
    const api = simularApi(() => respuestaJson(PAGINA))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    const estados = screen.getByRole("group", { name: "Estado" })
    for (const nombre of ["Por aprobar", "Adjudicada", "Desierta"])
      expect(
        within(estados).getByRole("button", { name: nombre })
      ).toBeInTheDocument()
    // El filtro se llama «Por aprobar»; la etiqueta de la fila sigue diciendo «Pendiente de aprobación».
    expect(
      within(estados).queryByRole("button", { name: "Pendiente de aprobación" })
    ).not.toBeInTheDocument()
    await userEvent.click(
      within(estados).getByRole("button", { name: "Por aprobar" })
    )
    expect(ubicacionActual()).toBe("/negociaciones?estado=pendiente_aprobacion")
    await waitFor(() =>
      expect(urlDeLlamada(api).searchParams.get("estado")).toBe(
        "pendiente_aprobacion"
      )
    )
  })

  it("el aprobador entra con Por aprobar si hay alguna, sin agregar historial", async () => {
    sesionDePrueba.roles = ["aprobador"]
    const api = simularAprobador(() => respuestaJson(POR_APROBAR))
    renderizarPagina(
      <>
        <Negociaciones />
        <Atras />
      </>,
      { ruta: "/negociaciones?pagina=2" }
    )
    expect(
      await within(await screen.findByRole("table")).findByText(
        "Pendiente de aprobación"
      )
    ).toBeInTheDocument()
    expect(ubicacionActual()).toBe("/negociaciones?estado=pendiente_aprobacion")
    expect(
      within(screen.getByRole("group", { name: "Estado" })).getByRole(
        "button",
        { name: "Por aprobar" }
      )
    ).toHaveAttribute("aria-pressed", "true")
    // Solo se pidió la consulta de una fila y la lista ya filtrada: nunca la lista completa.
    expect(api.mock.calls.map(([url]) => String(url))).toEqual([
      PENDIENTES,
      "/api/negociacion/eventos?pagina=1&tamano=25&estado=pendiente_aprobacion",
    ])
    // Con `replace`, «Atrás» no tiene a dónde volver: la URL sigue filtrada.
    await userEvent.click(screen.getByRole("button", { name: "Atrás" }))
    expect(ubicacionActual()).toBe("/negociaciones?estado=pendiente_aprobacion")
  })

  it("mientras revisa si hay propuestas por aprobar muestra la carga, no la lista completa", async () => {
    sesionDePrueba.roles = ["aprobador"]
    const revision = respuestaDiferida()
    const api = simularAprobador(() => revision.promesa)
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
    expect(api.mock.calls.map(([url]) => String(url))).toEqual([PENDIENTES])
    revision.resolver(respuestaJson(POR_APROBAR))
    await screen.findByRole("table")
    expect(ubicacionActual()).toBe("/negociaciones?estado=pendiente_aprobacion")
  })

  it("sin propuestas por aprobar el aprobador ve todas", async () => {
    sesionDePrueba.roles = ["aprobador"]
    simularAprobador(() => respuestaJson({ total: 0, elementos: [] }))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    expect(ubicacionActual()).toBe("/negociaciones")
    expect(
      within(screen.getByRole("group", { name: "Estado" })).getByRole(
        "button",
        { name: "Todas" }
      )
    ).toHaveAttribute("aria-pressed", "true")
  })

  it("si no se puede saber si hay propuestas por aprobar, el aprobador ve todas", async () => {
    sesionDePrueba.roles = ["aprobador"]
    simularAprobador(() =>
      respuestaJson(
        { title: "Servicio no disponible", detail: "Intente más tarde." },
        503
      )
    )
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    expect(ubicacionActual()).toBe("/negociaciones")
  })

  it("quien no es aprobador no es redirigido ni consulta las pendientes", async () => {
    const api = simularAprobador(() => respuestaJson(POR_APROBAR))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    expect(ubicacionActual()).toBe("/negociaciones")
    expect(api.mock.calls.map(([url]) => String(url))).toEqual([
      "/api/negociacion/eventos?pagina=1&tamano=25",
    ])
  })

  it("si la URL ya trae un estado, el aprobador no es redirigido", async () => {
    sesionDePrueba.roles = ["aprobador"]
    const api = simularAprobador(() => respuestaJson(POR_APROBAR))
    renderizarPagina(<Negociaciones />, {
      ruta: "/negociaciones?estado=abierto",
    })
    await screen.findByRole("link", { name: "NEG-2026-0001" })
    expect(ubicacionActual()).toBe("/negociaciones?estado=abierto")
    expect(api.mock.calls.some(([url]) => String(url) === PENDIENTES)).toBe(
      false
    )
  })

  it("después de entrar, elegir Todas se respeta y no regresa a Por aprobar", async () => {
    sesionDePrueba.roles = ["aprobador"]
    const api = simularAprobador(() => respuestaJson(POR_APROBAR))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones" })
    await screen.findByRole("table")
    expect(ubicacionActual()).toBe("/negociaciones?estado=pendiente_aprobacion")
    await userEvent.click(
      within(screen.getByRole("group", { name: "Estado" })).getByRole(
        "button",
        { name: "Todas" }
      )
    )
    await within(screen.getByRole("table")).findByText("Abierta")
    expect(ubicacionActual()).toBe("/negociaciones")
    expect(urlDeLlamada(api).searchParams.get("estado")).toBeNull()
    expect(
      api.mock.calls.filter(([url]) => String(url) === PENDIENTES)
    ).toHaveLength(1)
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
    expect(
      within(screen.getByRole("group", { name: "Estado" })).getByRole(
        "button",
        {
          name: "Todas",
        }
      )
    ).toHaveFocus()
  })

  it("una página fuera de rango ofrece volver a la primera", async () => {
    simularApi(() => respuestaJson({ total: 3, elementos: [] }))
    renderizarPagina(<Negociaciones />, { ruta: "/negociaciones?pagina=9" })
    await userEvent.click(
      await screen.findByRole("button", { name: "Ir a la primera página" })
    )
    expect(ubicacionActual()).toBe("/negociaciones")
    expect(
      within(screen.getByRole("group", { name: "Estado" })).getByRole(
        "button",
        {
          name: "Todas",
        }
      )
    ).toHaveFocus()
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
