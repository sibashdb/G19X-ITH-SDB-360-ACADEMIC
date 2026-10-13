import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useNavigate } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Precios } from "@/paginas/Precios"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
  ubicacionActual,
} from "@/pruebas/utilidades"
import { normalizarTexto } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const SERVICIOS = [
  {
    codigo: "CONS-01",
    nombre: "Consultoría SAP",
    categoria: "consultoria",
    unidad: "hora",
    moneda: "MXN",
    observaciones: 37,
  },
  {
    codigo: "NUBE-01",
    nombre: "Cómputo en la nube",
    categoria: "nube",
    unidad: "mes",
    moneda: "USD",
    observaciones: 12,
  },
  {
    codigo: "NUBE-02",
    nombre: "Almacenamiento de objetos",
    categoria: "nube",
    unidad: "gb_mes",
    moneda: "USD",
    observaciones: 0,
  },
]

const REFERENCIA = {
  codigo: "CONS-01",
  moneda: "MXN",
  unidad: "hora",
  cantidad: "40",
  plazo: 12,
  fecha: "2026-10-12",
  p25: "1000.0000",
  p50: "1200.0000",
  p75: "1400.0000",
  metodo: "modelo",
  version: 3,
  confianza: "normal",
  observaciones: 37,
}

const HISTORIAL = {
  codigo: "CONS-01",
  moneda: "MXN",
  cantidad: "40",
  puntos: [
    {
      fecha: "2025-12-01",
      precio: "1100.0000",
      cantidad: "40",
      folio: "CT-0002",
      proveedor: "Consultores Bajío",
    },
    {
      fecha: "2026-03-01",
      precio: "1500.0000",
      cantidad: "40",
      folio: "CT-0001",
      proveedor: "Nube Andina",
    },
  ],
  bandas: [
    { mes: "2026-09-01", p25: "1000.0000", p50: "1200.0000", p75: "1400.0000" },
    { mes: "2026-10-01", p25: "1010.0000", p50: "1210.0000", p75: "1410.0000" },
  ],
}

const SOBREPRECIO = {
  contrato_id: "c1",
  folio: "CT-0001",
  proveedor_id: "p1",
  proveedor: "Nube Andina",
  codigo_servicio: "CONS-01",
  servicio: "Consultoría SAP",
  moneda: "MXN",
  precio: "1500.0000",
  p25: "1000.0000",
  p50: "1200.0000",
  p75: "1400.0000",
  fecha_fin: "2026-12-31",
  ahorro_potencial: "3600.00",
  ahorro_potencial_mxn: "3600.00",
}

function api({
  catalogo = () => respuestaJson(SERVICIOS),
  referencia = () => respuestaJson(REFERENCIA),
  todos = [SOBREPRECIO],
}: {
  catalogo?: () => Response
  referencia?: (url: string) => Response
  todos?: object[]
} = {}) {
  return simularApi((url) => {
    const base = "/api/inteligencia/precios"
    if (url === `${base}/servicios`) return catalogo()
    if (url.startsWith(`${base}/servicios/CONS-01/referencia?`))
      return referencia(url)
    if (url === `${base}/servicios/CONS-01/historial`)
      return respuestaJson(HISTORIAL)
    if (url === `${base}/sobreprecios?codigo=CONS-01`)
      return respuestaJson([SOBREPRECIO])
    if (url === `${base}/sobreprecios`) return respuestaJson(todos)
    return new Response("", { status: 404 })
  })
}

/** Parámetros de cada consulta de referencia, en orden. */
function referenciasPedidas(simulado: ReturnType<typeof simularApi>) {
  return simulado.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes("/referencia?"))
    .map((url) => new URL(url, "http://localhost").searchParams)
}

/** Responde la referencia con la cantidad y el plazo que se le piden, como hace la API. */
const referenciaPedida = (url: string) => {
  const pedidos = new URL(url, "http://localhost").searchParams
  return respuestaJson({
    ...REFERENCIA,
    cantidad: pedidos.get("cantidad"),
    plazo: Number(pedidos.get("plazo")),
  })
}

/** El botón Atrás del navegador: retrocede una entrada del historial. */
function Atras() {
  const navegar = useNavigate()
  return (
    <button type="button" onClick={() => void navegar(-1)}>
      Atrás
    </button>
  )
}

const renderizar = (ruta = "/precios") =>
  renderizarPagina(<Precios />, { ruta })
const lista = () => screen.getByRole("list", { name: "Servicios del catálogo" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  sesionDePrueba.roles = ["admin"]
})

describe("normalizarTexto", () => {
  it("quita acentos y mayúsculas", () => {
    expect(normalizarTexto("Consultoría ÓPTIMA")).toBe("consultoria optima")
  })
})

describe("Precios", () => {
  it("muestra un esqueleto mientras carga el catálogo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {}))
    )
    renderizar()
    expect(await screen.findByRole("status")).toHaveTextContent("Cargando…")
  })

  it("agrupa los servicios por categoría", async () => {
    api()
    renderizar()

    expect(
      await screen.findByRole("button", { name: /Consultoría SAP/ })
    ).toBeInTheDocument()
    expect(within(lista()).getByText("Consultoría")).toBeInTheDocument()
    expect(within(lista()).getByText("Nube")).toBeInTheDocument()
    expect(screen.getByText("Elija un servicio")).toBeInTheDocument()
  })

  // jsdom no pinta el foco: se revisan las clases. La lista tiene overflow-y-auto, que recorta el
  // contorno por defecto, así que el anillo va hacia adentro; outline-hidden (y no outline-none)
  // conserva un contorno transparente que el modo de alto contraste sí muestra.
  it("los botones de la lista muestran un anillo de foco que el scroll no recorta", async () => {
    api()
    renderizar()

    const boton = await screen.findByRole("button", { name: /Consultoría SAP/ })

    expect(boton).toHaveClass(
      "outline-hidden",
      "focus-visible:ring-2",
      "focus-visible:ring-inset"
    )
    expect(boton).not.toHaveClass("outline-none")
  })

  // jsdom no calcula el diseño: se revisa la clase. Sin una plantilla de columnas por debajo de lg,
  // la única columna implícita crece hasta el ancho mínimo del contenido y la página se desplaza.
  it("la lista y el detalle comparten una rejilla de una columna por debajo de lg", async () => {
    api()
    renderizar("/precios?servicio=NUBE-01")

    await screen.findByRole("heading", { level: 2, name: "Cómputo en la nube" })

    const rejilla = lista().closest("[data-slot=card]")!.parentElement
    expect(rejilla).toHaveClass("grid", "grid-cols-1")
  })

  it("busca por nombre o código sin importar acentos ni mayúsculas", async () => {
    api()
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })
    const buscador = screen.getByRole("searchbox", {
      name: "Buscar servicio por nombre o código",
    })

    await userEvent.type(buscador, "CONSULTORIA")
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "nube-02")
    expect(
      within(lista()).getByRole("button", { name: /Almacenamiento de objetos/ })
    ).toBeInTheDocument()
    expect(within(lista()).getAllByRole("button")).toHaveLength(1)

    await userEvent.clear(buscador)
    await userEvent.type(buscador, "zzz")
    expect(screen.getByText("Ningún servicio coincide con «zzz».")).toHaveClass(
      "break-words"
    )
  })

  it("elegir un servicio lo refleja en la URL, muestra su detalle y le lleva el foco en una sola columna", async () => {
    api()
    renderizar()

    await userEvent.click(
      await screen.findByRole("button", { name: /Cómputo en la nube/ })
    )

    expect(ubicacionActual()).toBe("/precios?servicio=NUBE-01")
    expect(
      screen.getByRole("button", { name: /Cómputo en la nube/ })
    ).toHaveAttribute("aria-pressed", "true")
    const titulo = screen.getByRole("heading", {
      level: 2,
      name: "Cómputo en la nube",
    })
    // En las pruebas matchMedia nunca coincide: la página se comporta como en una pantalla angosta.
    await waitFor(() => expect(titulo).toHaveFocus())
    expect(
      screen.getByText("NUBE-01 · Nube · por mes · USD")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /Ver proveedores de esta categoría/ })
    ).toHaveAttribute("href", "/proveedores?categoria=nube")
  })

  it("muestra el precio de referencia con la cantidad sugerida y lo recalcula con otra cantidad y plazo", async () => {
    const simulado = api()
    renderizar("/precios?servicio=CONS-01")

    // "$1,400.00" también aparece en la tabla de sobreprecios: se busca dentro de los tres valores.
    const valores = (await screen.findByText("Típico (P50)")).closest("dl")!
    expect(valores).toHaveTextContent("$1,000.00")
    expect(valores).toHaveTextContent("$1,200.00")
    expect(valores).toHaveTextContent("$1,400.00")
    expect(
      screen.getByText(/Calculado con el modelo de precios versión 3/)
    ).toBeInTheDocument()
    expect(screen.getByText(/37 contratos comparables/)).toBeInTheDocument()
    const [primera] = referenciasPedidas(simulado)
    expect(primera.get("cantidad")).toBe("40")
    expect(primera.get("plazo")).toBe("12")

    const cantidad = screen.getByLabelText("Cantidad")
    const plazo = screen.getByLabelText("Plazo (meses)")
    await userEvent.clear(cantidad)
    await userEvent.type(cantidad, "100")
    await userEvent.clear(plazo)
    await userEvent.type(plazo, "24")
    await userEvent.click(screen.getByRole("button", { name: "Calcular" }))

    expect(ubicacionActual()).toBe(
      "/precios?servicio=CONS-01&cantidad=100&plazo=24"
    )
    await waitFor(() => {
      const ultima = referenciasPedidas(simulado).at(-1)!
      expect(ultima.get("cantidad")).toBe("100")
      expect(ultima.get("plazo")).toBe("24")
    })
  })

  it("el resultado dice para qué cantidad y plazo se calculó", async () => {
    api({ referencia: referenciaPedida })
    renderizar("/precios?servicio=CONS-01")

    expect(
      await screen.findByText(
        /Precio por hora para una cantidad de 40 y un plazo de 12 meses/
      )
    ).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText("Cantidad"))
    await userEvent.type(screen.getByLabelText("Cantidad"), "100")
    await userEvent.clear(screen.getByLabelText("Plazo (meses)"))
    await userEvent.type(screen.getByLabelText("Plazo (meses)"), "24")
    await userEvent.click(screen.getByRole("button", { name: "Calcular" }))

    expect(
      await screen.findByText(
        /Precio por hora para una cantidad de 100 y un plazo de 24 meses/
      )
    ).toBeInTheDocument()
  })

  it("al volver atrás, el formulario y el resultado regresan a la cantidad y el plazo anteriores", async () => {
    api({ referencia: referenciaPedida })
    renderizarPagina(
      <>
        <Precios />
        <Atras />
      </>,
      { ruta: "/precios?servicio=CONS-01" }
    )
    await screen.findByText(/una cantidad de 40 y un plazo de 12 meses/)

    await userEvent.clear(screen.getByLabelText("Cantidad"))
    await userEvent.type(screen.getByLabelText("Cantidad"), "100")
    await userEvent.clear(screen.getByLabelText("Plazo (meses)"))
    await userEvent.type(screen.getByLabelText("Plazo (meses)"), "24")
    await userEvent.click(screen.getByRole("button", { name: "Calcular" }))
    await screen.findByText(/una cantidad de 100 y un plazo de 24 meses/)
    // El foco se queda en el botón: el formulario no se vuelve a montar.
    expect(screen.getByRole("button", { name: "Calcular" })).toHaveFocus()

    await userEvent.click(screen.getByRole("button", { name: "Atrás" }))

    expect(ubicacionActual()).toBe("/precios?servicio=CONS-01")
    expect(
      await screen.findByText(/una cantidad de 40 y un plazo de 12 meses/)
    ).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByLabelText("Cantidad")).toHaveValue(40)
      expect(screen.getByLabelText("Plazo (meses)")).toHaveValue(12)
    })
  })

  it("una cantidad inválida en la URL usa la sugerida", async () => {
    const simulado = api()
    renderizar("/precios?servicio=CONS-01&cantidad=-5&plazo=999")

    await screen.findByText("$1,200.00")
    const [primera] = referenciasPedidas(simulado)
    expect(primera.get("cantidad")).toBe("40")
    expect(primera.get("plazo")).toBe("120")
  })

  it("una cantidad de cero en el formulario no se envía", async () => {
    api()
    renderizar("/precios?servicio=CONS-01")
    await screen.findByText("$1,200.00")

    const cantidad = screen.getByLabelText("Cantidad")
    await userEvent.clear(cantidad)
    await userEvent.type(cantidad, "0")
    await userEvent.click(screen.getByRole("button", { name: "Calcular" }))

    expect(ubicacionActual()).toBe("/precios?servicio=CONS-01")
  })

  it("sin contratos recientes explica por qué no hay precio de referencia", async () => {
    api({
      referencia: () =>
        respuestaJson(
          {
            title: "No encontrado",
            detail:
              "No hay contratos de este servicio en los últimos 24 meses.",
            codigo: "sin_observaciones",
          },
          404
        ),
    })
    renderizar("/precios?servicio=CONS-01")

    expect(
      await screen.findByText("Sin contratos recientes")
    ).toBeInTheDocument()
  })

  it("muestra el historial y los contratos con sobreprecio del servicio", async () => {
    api()
    renderizar("/precios?servicio=CONS-01")

    expect(
      await screen.findByRole("figure", { name: /Precios de 2 contratos/ })
    ).toBeInTheDocument()
    expect(
      screen.getByText("Ver los precios de cada contrato")
    ).toBeInTheDocument()
    expect(screen.getByText("CT-0002")).toBeInTheDocument()
    // Las bandas mensuales de la gráfica también van en una tabla con nombre.
    const bandas = screen.getByRole("table", {
      name: "Rango típico del mercado por mes",
    })
    expect(within(bandas).getByText("$1,210.00")).toBeInTheDocument()
    expect(within(bandas).getAllByRole("row")).toHaveLength(3)
    expect(
      screen.getByRole("table", { name: "Precio de cada contrato" })
    ).toBeInTheDocument()

    const sobreprecios = screen
      .getByRole("heading", { name: "Contratos con sobreprecio" })
      .closest<HTMLElement>("[data-slot=card]")!
    expect(
      await within(sobreprecios).findByRole("link", { name: "Nube Andina" })
    ).toHaveAttribute("href", "/proveedores/p1?pestana=contratos")
    expect(within(sobreprecios).getByText("$3,600.00")).toBeInTheDocument()
  })

  it("un servicio desconocido en la URL pide elegir uno", async () => {
    api()
    renderizar("/precios?servicio=NO-EXISTE")
    expect(await screen.findByText("Elija un servicio")).toBeInTheDocument()
  })

  it("la vista de todos los sobreprecios los pagina y enlaza a cada servicio", async () => {
    const treinta = Array.from({ length: 30 }, (_, i) => ({
      ...SOBREPRECIO,
      contrato_id: `c${i}`,
      folio: `CT-${String(i).padStart(4, "0")}`,
    }))
    api({ todos: treinta })
    renderizar()
    await screen.findByRole("button", { name: /Consultoría SAP/ })

    await userEvent.click(
      screen.getByRole("button", { name: "Todos los sobreprecios" })
    )

    expect(ubicacionActual()).toBe("/precios?vista=sobreprecios")
    expect(
      screen.getByRole("button", { name: "Todos los sobreprecios" })
    ).toHaveAttribute("aria-pressed", "true")
    expect(
      await screen.findByText("Mostrando 1–25 de 30 líneas con sobreprecio")
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole("link", { name: "Consultoría SAP" })[0]
    ).toHaveAttribute("href", "/precios?servicio=CONS-01")

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }))
    expect(ubicacionActual()).toBe("/precios?vista=sobreprecios&pagina=2")
    expect(screen.getByText("CT-0029")).toBeInTheDocument()
  })

  it("con el catálogo vacío invita al administrador a importar", async () => {
    api({ catalogo: () => respuestaJson([]) })
    renderizar()
    expect(
      await screen.findByText("El catálogo está vacío")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Ir a Importación" })
    ).toHaveAttribute("href", "/importacion")
  })

  it("muestra el error en español y permite reintentar", async () => {
    let fallar = true
    api({
      catalogo: () =>
        fallar ? new Response("", { status: 502 }) : respuestaJson(SERVICIOS),
    })
    renderizar()

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servicio no está disponible"
    )
    fallar = false
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(
      await screen.findByRole("button", { name: /Consultoría SAP/ })
    ).toBeInTheDocument()
  })

  it("no tiene violaciones de accesibilidad", async () => {
    api()
    const { container } = renderizar("/precios?servicio=CONS-01")
    await screen.findByText("$1,200.00")
    await screen.findByRole("figure", { name: /Precios de 2 contratos/ })
    await esperarSinViolaciones(container)
  })
})
