import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Catalogo } from "@/paginas/Catalogo"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const SAAS = {
  id: "s1",
  codigo: "SAAS-OFI-EMP",
  nombre: "Suite de productividad",
  categoria: "licencia_saas",
  unidad: "usuario_mes",
  moneda: "USD",
  activo: true,
  tiene_contratos: true,
}
const MESA = {
  id: "s2",
  codigo: "SOP-MESA-TK",
  nombre: "Mesa de ayuda",
  categoria: "soporte",
  unidad: "ticket",
  moneda: "MXN",
  activo: false,
  tiene_contratos: false,
}

/** API simulada del catálogo; un PATCH a SAAS-OFI-EMP alterna su estado. */
function catalogo(alta?: () => Response) {
  let saas = { ...SAAS }
  return simularApi((url) => {
    if (url === "/api/proveedores/servicios?incluir_inactivos=true")
      return respuestaJson([saas, MESA])
    if (url === "/api/proveedores/servicios")
      return alta
        ? alta()
        : respuestaJson({ ...MESA, codigo: "NUBE-VM-2" }, 201)
    if (url === "/api/proveedores/servicios/SAAS-OFI-EMP") {
      saas = { ...saas, activo: !saas.activo }
      return respuestaJson(saas)
    }
    return new Response("", { status: 404 })
  })
}

function cuerpos(simulado: ReturnType<typeof catalogo>, metodo: string) {
  return simulado.mock.calls
    .map((llamada) => llamada as unknown as [string, RequestInit | undefined])
    .filter(([, init]) => init?.method === metodo)
    .map(([url, init]) => [url, JSON.parse(String(init?.body))])
}

async function elegir(combo: string, opcion: string) {
  await userEvent.click(screen.getByRole("combobox", { name: combo }))
  await userEvent.click(await screen.findByRole("option", { name: opcion }))
}

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Catalogo", () => {
  it("lista los servicios con nombres legibles y su estado en texto", async () => {
    catalogo()
    const { container } = renderizarPagina(<Catalogo />, {
      ruta: "/sistema/catalogo",
    })
    const fila = (await screen.findByText("Suite de productividad")).closest(
      "tr"
    )!
    expect(within(fila).getByText("Licencias SaaS")).toBeInTheDocument()
    expect(within(fila).getByText("Usuario al mes")).toBeInTheDocument()
    expect(within(fila).getByText("Activo")).toBeInTheDocument()
    const inactiva = screen.getByText("Mesa de ayuda").closest("tr")!
    expect(within(inactiva).getByText("Inactivo")).toBeInTheDocument()
    await esperarSinViolaciones(container)
  })

  it("filtra por estado y categoría desde la URL", async () => {
    catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(screen.getByRole("button", { name: "Inactivos" }))
    expect(ubicacionActual()).toBe("/sistema/catalogo?estado=inactivos")
    expect(screen.queryByText("Suite de productividad")).not.toBeInTheDocument()
    expect(screen.getByText("Mesa de ayuda")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Nube" }))
    expect(await screen.findByText("Sin resultados")).toBeInTheDocument()
  })

  it("da de alta un servicio y devuelve el foco a «Nuevo servicio»", async () => {
    const simulado = catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(
      screen.getByRole("button", { name: "Nuevo servicio" })
    )
    await userEvent.type(screen.getByLabelText("Código"), "nube-vm-2")
    await userEvent.type(screen.getByLabelText("Nombre"), "Máquina virtual")
    await elegir("Categoría", "Nube")
    await elegir("Unidad", "vCPU al mes")
    await elegir("Moneda", "USD")
    await userEvent.click(screen.getByRole("button", { name: "Dar de alta" }))

    expect(
      await screen.findByText("Se dio de alta el servicio NUBE-VM-2.")
    ).toBeInTheDocument()
    expect(cuerpos(simulado, "POST")).toEqual([
      [
        "/api/proveedores/servicios",
        {
          codigo: "nube-vm-2",
          nombre: "Máquina virtual",
          categoria: "nube",
          unidad: "vcpu_mes",
          moneda: "USD",
        },
      ],
    ])
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Nuevo servicio" })
      ).toHaveFocus()
    )
  })

  it("un código repetido se marca junto al campo", async () => {
    catalogo(() =>
      respuestaJson(
        {
          title: "Conflicto",
          detail: "Ya existe un servicio con ese código.",
          codigo: "servicio_duplicado",
          errores: [
            {
              campo: "codigo",
              mensaje: "Ya existe un servicio con ese código.",
            },
          ],
        },
        409
      )
    )
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(
      screen.getByRole("button", { name: "Nuevo servicio" })
    )
    await userEvent.type(screen.getByLabelText("Código"), "SOP-MESA-TK")
    await userEvent.type(screen.getByLabelText("Nombre"), "Otra")
    await elegir("Categoría", "Soporte")
    await elegir("Unidad", "Ticket")
    await elegir("Moneda", "MXN")
    await userEvent.click(screen.getByRole("button", { name: "Dar de alta" }))
    expect(
      await screen.findByText("Ya existe un servicio con ese código.")
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Código")).toHaveAttribute(
      "aria-invalid",
      "true"
    )
  })

  it("con contratos bloquea categoría y moneda y solo envía lo que cambió", async () => {
    const simulado = catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(
      screen.getByRole("button", { name: "Editar SAAS-OFI-EMP" })
    )
    expect(screen.getByLabelText("Código")).toHaveAttribute("readonly")
    for (const combo of ["Categoría", "Moneda"]) {
      const campo = screen.getByRole("combobox", { name: combo })
      expect(campo).toBeDisabled()
      expect(campo).toHaveAccessibleDescription(
        "La categoría y la moneda no se pueden cambiar: el servicio ya tiene contratos y sus precios dependen de ellas."
      )
    }
    const nombre = screen.getByLabelText("Nombre")
    await userEvent.clear(nombre)
    await userEvent.type(nombre, "Suite de oficina")
    await userEvent.click(
      screen.getByRole("button", { name: "Guardar cambios" })
    )
    await screen.findByText("Se guardaron los cambios de SAAS-OFI-EMP.")
    expect(cuerpos(simulado, "PATCH")).toEqual([
      [
        "/api/proveedores/servicios/SAAS-OFI-EMP",
        { nombre: "Suite de oficina" },
      ],
    ])
  })

  it("el panel de edición con campos bloqueados no tiene violaciones de accesibilidad", async () => {
    catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(
      screen.getByRole("button", { name: "Editar SAAS-OFI-EMP" })
    )
    await screen.findByLabelText("Código")
    await esperarSinViolaciones(document.body)
  })

  it("al reabrir el panel no conserva lo escrito antes", async () => {
    catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")

    await userEvent.click(
      screen.getByRole("button", { name: "Editar SAAS-OFI-EMP" })
    )
    await userEvent.type(screen.getByLabelText("Nombre"), " (borrador)")
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByLabelText("Código")).not.toBeInTheDocument()
    )
    await userEvent.click(
      screen.getByRole("button", { name: "Editar SAAS-OFI-EMP" })
    )
    expect(screen.getByLabelText("Nombre")).toHaveValue(
      "Suite de productividad"
    )
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByLabelText("Código")).not.toBeInTheDocument()
    )

    await userEvent.click(
      screen.getByRole("button", { name: "Nuevo servicio" })
    )
    await userEvent.type(screen.getByLabelText("Código"), "nube-vm-2")
    await userEvent.type(screen.getByLabelText("Nombre"), "Máquina virtual")
    await elegir("Categoría", "Nube")
    await elegir("Unidad", "vCPU al mes")
    await elegir("Moneda", "USD")
    await userEvent.click(screen.getByRole("button", { name: "Dar de alta" }))
    await screen.findByText("Se dio de alta el servicio NUBE-VM-2.")
    await waitFor(() =>
      expect(screen.queryByLabelText("Código")).not.toBeInTheDocument()
    )

    await userEvent.click(
      screen.getByRole("button", { name: "Nuevo servicio" })
    )
    expect(screen.getByLabelText("Código")).toHaveValue("")
    expect(screen.getByLabelText("Nombre")).toHaveValue("")
  })

  it("desactiva con confirmación y deja el foco en «Activar»", async () => {
    const simulado = catalogo()
    renderizarPagina(<Catalogo />, { ruta: "/sistema/catalogo" })
    await screen.findByText("Suite de productividad")
    await userEvent.click(
      screen.getByRole("button", { name: "Desactivar SAAS-OFI-EMP" })
    )
    await userEvent.click(
      await screen.findByRole("button", { name: "Desactivar" })
    )

    expect(
      await screen.findByText("Se desactivó el servicio SAAS-OFI-EMP.")
    ).toBeInTheDocument()
    expect(cuerpos(simulado, "PATCH")).toEqual([
      ["/api/proveedores/servicios/SAAS-OFI-EMP", { activo: false }],
    ])
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Activar SAAS-OFI-EMP" })
      ).toHaveFocus()
    )
  })

  it("solo administración edita el catálogo", () => {
    sesionDePrueba.roles = ["comprador"]
    catalogo()
    renderizarPagina(<Catalogo />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
