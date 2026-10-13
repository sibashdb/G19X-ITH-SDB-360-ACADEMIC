import { cleanup, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Panel } from "@/paginas/Panel"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  renderizarPagina,
  respuestaJson,
  simularApi,
} from "@/pruebas/utilidades"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ESTADO = {
  version: "abc1234",
  comprobado_en: new Date().toISOString(),
  servicios: [
    {
      clave: "base_de_datos",
      nombre: "Base de datos de administración",
      estado: "sano",
      tiempo_ms: 4,
      detalle: "Funciona con normalidad.",
    },
    {
      clave: "correo",
      nombre: "Buzón de correo (Mailpit)",
      estado: "con_problemas",
      tiempo_ms: 1500,
      detalle: "Responde con lentitud.",
    },
  ],
}
const ACTIVIDAD = {
  total: 1,
  elementos: [
    {
      id: "a1",
      fecha: "2026-10-09T18:00:00Z",
      actor_id: "admin-1",
      actor_nombre: "admin1",
      tipo: "servicio.creado",
      objeto_tipo: "servicio",
      objeto_id: "NUBE-VM-2",
      objeto_nombre: "NUBE-VM-2",
      detalle: {},
      resultado: "exito",
      ip: null,
    },
  ],
}
const DATOS = {
  registros: {
    proveedores: 60,
    servicios: 24,
    contratos: 1600,
    lineas_contrato: 2400,
    desempeno: 1440,
    tipo_cambio: 36,
  },
  ultimo_evento: "2026-10-12T15:00:00Z",
  modelo: {
    version: 2,
    entrenado_en: "2026-10-10T18:00:00Z",
    origen: "manual",
    actor_nombre: "admin1",
    observaciones: 1520,
    datos_hasta: "2026-09-30",
    mape: "0.083000",
    mape_linea_base: "0.093000",
    cobertura: "0.520000",
    pinball: "0.010000",
    promovido: true,
  },
  en_uso: 2,
  entrenando: false,
}

function api(resumen: object, datos: object = DATOS) {
  return simularApi((url) => {
    if (url.startsWith("/api/administracion/resumen"))
      return respuestaJson(resumen)
    if (url.startsWith("/api/administracion/estado"))
      return respuestaJson(ESTADO)
    if (url.startsWith("/api/inteligencia/datos")) return respuestaJson(datos)
    return respuestaJson(ACTIVIDAD)
  })
}

const tarjeta = (titulo: string) =>
  screen.getByText(titulo).closest<HTMLElement>("[data-slot=card]")!

beforeEach(() => {
  sesionDePrueba.roles = ["admin"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Panel", () => {
  it("resume usuarios, intentos fallidos, servicios y correos", async () => {
    api({ usuarios_activos: 12, intentos_fallidos_24h: 6, correos_7d: 3 })
    const { container } = renderizarPagina(<Panel />, { ruta: "/sistema" })
    await screen.findByText("Usuarios activos")
    expect(
      await within(tarjeta("Usuarios activos")).findByText("12")
    ).toBeInTheDocument()
    const fallidos = tarjeta("Intentos fallidos (24 h)")
    expect(within(fallidos).getByText("6")).toBeInTheDocument()
    expect(fallidos.querySelector("[data-tono]")).toHaveAttribute(
      "data-tono",
      "riesgo"
    )
    const servicios = tarjeta("Servicios con problemas")
    expect(await within(servicios).findByText("1")).toBeInTheDocument()
    expect(
      within(servicios).getByText("Buzón de correo (Mailpit)")
    ).toBeInTheDocument()
    expect(servicios.querySelector("[data-tono]")).toHaveAttribute(
      "data-tono",
      "advertencia"
    )
    expect(
      within(tarjeta("Correos (7 días)")).getByText("3")
    ).toBeInTheDocument()
    expect(
      await screen.findAllByText("Dio de alta el servicio NUBE-VM-2")
    ).not.toHaveLength(0)
    expect(
      screen.getByRole("link", { name: "Ver toda la actividad" })
    ).toHaveAttribute("href", "/sistema/actividad")
    await esperarSinViolaciones(container)
  })

  it("con un intento fallido el tono es de advertencia; sin ninguno, de éxito", async () => {
    api({ usuarios_activos: 1, intentos_fallidos_24h: 1, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })
    await screen.findByText("Intentos fallidos (24 h)")
    const fallidos = tarjeta("Intentos fallidos (24 h)")
    expect(await within(fallidos).findByText("1")).toBeInTheDocument()
    expect(fallidos.querySelector("[data-tono]")).toHaveAttribute(
      "data-tono",
      "advertencia"
    )
  })

  it("sin el servicio de identidad, los usuarios activos quedan sin dato", async () => {
    api({ usuarios_activos: null, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })
    expect(
      await screen.findByText("No se pudo consultar el servicio de identidad.")
    ).toBeInTheDocument()
    expect(
      within(tarjeta("Usuarios activos")).getByText("Sin datos")
    ).toBeInTheDocument()
  })

  it("la tarjeta Datos y modelo resume la copia local y el modelo en uso", async () => {
    api({ usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })

    const datos = tarjeta("Datos y modelo")
    expect(await within(datos).findByText("1,600")).toBeInTheDocument()
    expect(within(datos).getByText("Líneas de contrato")).toBeInTheDocument()
    expect(datos).toHaveTextContent("Modelo de precios: versión 2, MAPE 8.3 %.")
    // El término técnico lleva su definición.
    expect(
      within(datos).getByRole("button", { name: "MAPE" })
    ).toBeInTheDocument()
    expect(
      within(datos).getByRole("link", { name: "Ir a Configuración" })
    ).toHaveAttribute("href", "/configuracion")
  })

  it("si el modelo guardado no se pudo cargar, la tarjeta lo dice y explica la línea base", async () => {
    api(
      { usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 },
      { ...DATOS, en_uso: null }
    )
    renderizarPagina(<Panel />, { ruta: "/sistema" })

    const datos = tarjeta("Datos y modelo")
    await within(datos).findByText("1,600")
    expect(datos).toHaveTextContent(
      "Modelo de precios: la versión 2 no se pudo cargar y se usa la línea base; reentrénelo en Configuración."
    )
    expect(
      within(datos).getByRole("button", { name: "línea base" })
    ).toBeInTheDocument()
  })

  it("sin ningún modelo, la tarjeta dice que se usa la línea base", async () => {
    api(
      { usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 },
      { ...DATOS, modelo: null, en_uso: null }
    )
    renderizarPagina(<Panel />, { ruta: "/sistema" })

    const datos = tarjeta("Datos y modelo")
    await within(datos).findByText("1,600")
    expect(datos).toHaveTextContent(
      "Modelo de precios: línea base (ningún modelo la ha mejorado todavía)."
    )
    expect(
      within(datos).getByRole("button", { name: "línea base" })
    ).toBeInTheDocument()
  })

  it("con un entrenamiento en curso, la tarjeta lo avisa", async () => {
    api(
      { usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 },
      { ...DATOS, entrenando: true }
    )
    renderizarPagina(<Panel />, { ruta: "/sistema" })

    const datos = tarjeta("Datos y modelo")
    await within(datos).findByText("1,600")
    expect(datos).toHaveTextContent(
      "Modelo de precios: versión 2, MAPE 8.3 %. Hay un entrenamiento en curso."
    )
  })

  it("la fecha del último dato no lleva dos puntos al final", async () => {
    api({ usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />, { ruta: "/sistema" })

    const datos = tarjeta("Datos y modelo")
    await within(datos).findByText("1,600")
    expect(datos).toHaveTextContent("Último dato recibido: 12 oct 2026")
    expect(datos).not.toHaveTextContent("..")
  })

  it("sin ningún dato recibido, la tarjeta lo dice con un solo punto", async () => {
    api(
      { usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 },
      { ...DATOS, ultimo_evento: null }
    )
    renderizarPagina(<Panel />, { ruta: "/sistema" })

    const datos = tarjeta("Datos y modelo")
    await within(datos).findByText("1,600")
    expect(datos).toHaveTextContent("Último dato recibido: ninguno todavía.")
    expect(datos).not.toHaveTextContent("..")
  })

  it("solo administración lo ve", () => {
    sesionDePrueba.roles = ["comprador"]
    api({ usuarios_activos: 1, intentos_fallidos_24h: 0, correos_7d: 0 })
    renderizarPagina(<Panel />)
    expect(screen.getByText("Acceso restringido")).toBeInTheDocument()
  })
})
