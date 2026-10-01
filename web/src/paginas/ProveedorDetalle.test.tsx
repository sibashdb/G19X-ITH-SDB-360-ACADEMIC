import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"

vi.mock("react-oidc-context", () => ({
  useAuth: () => ({ user: { access_token: "cabecera.e30=.firma" } }),
}))

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

function respuestaJson(cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })
}

/** Responde cada URL con lo indicado; una respuesta nueva por llamada (el cuerpo se lee una vez). */
function simularApi(rutas: Record<string, () => Response | Promise<Response>>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const respuesta = rutas[url]
      return Promise.resolve(respuesta ? respuesta() : new Response("", { status: 404 }))
    }),
  )
}

function renderizar(ruta = "/proveedores/p1") {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={[ruta]}>
        <Routes>
          <Route path="/proveedores/:id" element={<ProveedorDetalle />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("ProveedorDetalle", () => {
  it("avisa con una alerta cuando falla la consulta de contratos", async () => {
    simularApi({
      [RUTA]: () => respuestaJson(PROVEEDOR),
      [`${RUTA}/contratos`]: () => new Response("Bad Gateway", { status: 502 }),
      [`${RUTA}/desempeno?meses=12`]: () => respuestaJson([]),
    })
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible; intente más tarde.",
    )
    expect(screen.queryByText("Sin contratos registrados")).not.toBeInTheDocument()
  })

  it("muestra que no hay datos cuando el desempeño llega vacío", async () => {
    simularApi({
      [RUTA]: () => respuestaJson(PROVEEDOR),
      [`${RUTA}/contratos`]: () => respuestaJson([CONTRATO]),
      [`${RUTA}/desempeno?meses=12`]: () => respuestaJson([]),
    })
    renderizar()

    expect(await screen.findByText("Sin datos de desempeño")).toBeInTheDocument()
    expect(await screen.findByText("CT-0001")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("muestra que no hay contratos cuando la lista llega vacía", async () => {
    simularApi({
      [RUTA]: () => respuestaJson(PROVEEDOR),
      [`${RUTA}/contratos`]: () => respuestaJson([]),
      [`${RUTA}/desempeno?meses=12`]: () => respuestaJson([]),
    })
    renderizar()

    expect(await screen.findByText("Sin contratos registrados")).toBeInTheDocument()
  })

  it("codifica el id al construir la ruta de la API", async () => {
    simularApi({
      "/api/proveedores/proveedores/a%20b%3Fx": () => respuestaJson(PROVEEDOR),
      "/api/proveedores/proveedores/a%20b%3Fx/contratos": () => respuestaJson([]),
      "/api/proveedores/proveedores/a%20b%3Fx/desempeno?meses=12": () => respuestaJson([]),
    })
    renderizar("/proveedores/a%20b%3Fx")

    expect(await screen.findByText("Proveedor Uno")).toBeInTheDocument()
  })

  it("muestra Cargando mientras llegan los contratos y el desempeño", async () => {
    let liberar = () => {}
    const espera = new Promise<void>((resolver) => {
      liberar = resolver
    })
    simularApi({
      [RUTA]: () => respuestaJson(PROVEEDOR),
      [`${RUTA}/contratos`]: () => espera.then(() => respuestaJson([CONTRATO])),
      [`${RUTA}/desempeno?meses=12`]: () => espera.then(() => respuestaJson([])),
    })
    renderizar()

    await screen.findByText("Proveedor Uno")
    expect(screen.getAllByText("Cargando…")).toHaveLength(2)

    liberar()
    expect(await screen.findByText("Sin datos de desempeño")).toBeInTheDocument()
    expect(screen.queryByText("Cargando…")).not.toBeInTheDocument()
  })
})
