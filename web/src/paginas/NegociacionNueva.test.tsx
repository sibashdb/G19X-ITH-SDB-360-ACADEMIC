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
    [`/api/proveedores/proveedores/${NUBE_NORTE}`]: () =>
      respuestaJson(DETALLE),
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
    await userEvent.click(
      screen.getByRole("button", { name: "Crear borrador" })
    )
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
    await userEvent.click(
      screen.getByRole("button", { name: "Crear borrador" })
    )
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
          detail:
            "No se pudo consultar la referencia de precios; intente de nuevo.",
          codigo: "dependencia_no_disponible",
        },
        503
      )
    )
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    await capturarCompra()
    await userEvent.click(
      screen.getByRole("button", { name: "Crear borrador" })
    )
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

  it("al quitar a un proveedor elegido, el foco pasa al buscador", async () => {
    apiDeCompra()
    renderizarPagina(<NegociacionNueva />, { ruta: "/negociaciones/nueva" })
    await userEvent.click(
      await screen.findByRole("checkbox", { name: /Nube Norte/ })
    )
    await userEvent.click(
      screen.getByRole("button", { name: "Quitar a Nube Norte" })
    )
    expect(
      screen.queryByRole("button", { name: "Quitar a Nube Norte" })
    ).not.toBeInTheDocument()
    expect(screen.getByLabelText("Buscar proveedor")).toHaveFocus()
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
    await userEvent.click(
      screen.getByRole("button", { name: "Crear borrador" })
    )
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
