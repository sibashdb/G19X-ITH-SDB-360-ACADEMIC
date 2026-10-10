import { afterEach, describe, expect, it, vi } from "vitest"
import { descargar, enviarJson, ErrorApi, erroresPorCampo, pedir } from "@/api"

function simular(
  cuerpo: BodyInit | null,
  estado: number,
  tipo = "application/json"
) {
  const simulado = vi.fn().mockResolvedValue(
    new Response(cuerpo, {
      status: estado,
      headers: { "Content-Type": tipo },
    })
  )
  vi.stubGlobal("fetch", simulado)
  return simulado
}

async function errorDe(promesa: Promise<unknown>): Promise<ErrorApi> {
  const error = await promesa.then(
    () => null,
    (e: unknown) => e
  )
  expect(error).toBeInstanceOf(ErrorApi)
  return error as ErrorApi
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("pedir", () => {
  it("devuelve el JSON y envía el token en Authorization", async () => {
    const simulado = simular(JSON.stringify({ total: 1 }), 200)

    expect(await pedir("/proveedores/proveedores", "tk")).toEqual({ total: 1 })

    const [url, init] = simulado.mock.calls[0]
    expect(url).toBe("/api/proveedores/proveedores")
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tk")
  })

  it("convierte Problem Details en ErrorApi", async () => {
    simular(
      JSON.stringify({
        title: "Archivo con errores",
        detail: "Se encontraron 1 error(es).",
        errores: [{ fila: 2, campo: "rfc", mensaje: "Formato inválido" }],
      }),
      422,
      "application/problem+json"
    )

    const error = await errorDe(pedir("/x", "tk"))

    expect(error.estado).toBe(422)
    expect(error.titulo).toBe("Archivo con errores")
    expect(error.message).toBe("Se encontraron 1 error(es).")
    expect(error.errores).toEqual([
      { fila: 2, campo: "rfc", mensaje: "Formato inválido" },
    ])
  })

  it("muestra un mensaje en español cuando el cuerpo de un 413 no es JSON", async () => {
    simular("<html>Request Entity Too Large</html>", 413, "text/html")

    const error = await errorDe(pedir("/x", "tk"))

    expect(error.estado).toBe(413)
    expect(error.titulo).toBe("Contenido demasiado grande")
    expect(error.message).toBe("El archivo excede el límite de 10 MB.")
    expect(error.errores).toEqual([])
  })

  it.each([
    [429, "Demasiadas solicitudes", "Espere unos segundos e intente de nuevo."],
    [
      502,
      "Servicio no disponible",
      "El servicio no está disponible; intente más tarde.",
    ],
    [
      503,
      "Servicio no disponible",
      "El servicio no está disponible; intente más tarde.",
    ],
    [
      504,
      "Servicio no disponible",
      "El servicio no está disponible; intente más tarde.",
    ],
    [418, "Error", "Ocurrió un error (código 418)."],
  ])(
    "traduce el estado %i cuando el cuerpo no es JSON",
    async (estado, titulo, detalle) => {
      simular("texto", estado, "text/plain")

      const error = await errorDe(pedir("/x", undefined))

      expect([error.titulo, error.message]).toEqual([titulo, detalle])
    }
  )

  it("trata un cuerpo JSON nulo como no JSON", async () => {
    simular("null", 502)

    const error = await errorDe(pedir("/x", "tk"))

    expect(error.titulo).toBe("Servicio no disponible")
  })

  it("traduce un fallo de red (fetch rechazado) a un mensaje en español", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch"))
    )

    const error = await errorDe(pedir("/x", "tk"))

    expect(error.estado).toBe(0)
    expect(error.titulo).toBe("Sin conexión")
    expect(error.message).toBe(
      "No se pudo conectar con el servidor; revise su conexión e intente de nuevo."
    )
  })

  it("no reporta como fallo de red una petición cancelada por el llamador", async () => {
    const cancelacion = new DOMException(
      "The operation was aborted.",
      "AbortError"
    )
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(cancelacion))
    const controlador = new AbortController()
    controlador.abort()

    const error = await pedir("/x", "tk", { signal: controlador.signal }).then(
      () => null,
      (e: unknown) => e
    )

    expect(error).toBe(cancelacion)
    expect(error).not.toBeInstanceOf(ErrorApi)
  })
})

describe("administración", () => {
  it("expone el código del problema y los errores por campo sin el prefijo body.", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              title: "Conflicto",
              detail: "Ya existe un usuario con ese nombre de usuario.",
              codigo: "usuario_duplicado",
              errores: [{ campo: "body.correo", mensaje: "Formato inválido" }],
            }),
            {
              status: 409,
              headers: { "Content-Type": "application/problem+json" },
            }
          )
      )
    )
    const error = await errorDe(pedir("/administracion/usuarios", "t"))
    expect(error).toBeInstanceOf(ErrorApi)
    expect(error.codigo).toBe("usuario_duplicado")
    expect(erroresPorCampo(error)).toEqual({ correo: "Formato inválido" })
    vi.unstubAllGlobals()
  })

  it("un 204 no intenta leer JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 204 }))
    )
    await expect(
      pedir(
        "/administracion/usuarios/x/cerrar-sesiones",
        "t",
        enviarJson("POST")
      )
    ).resolves.toBeUndefined()
    vi.unstubAllGlobals()
  })

  it("enviarJson arma el cuerpo y la cabecera", () => {
    const init = enviarJson("PATCH", { roles: ["admin"] })
    expect(init.method).toBe("PATCH")
    expect(new Headers(init.headers).get("Content-Type")).toBe(
      "application/json"
    )
    expect(init.body).toBe('{"roles":["admin"]}')
  })
})

describe("descargar", () => {
  it("baja el archivo con el token y lo guarda con su nombre", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout"] })
    const simulado = simular("a,b\n", 200, "text/csv")
    const crear = vi.fn(() => "blob:archivo")
    const revocar = vi.fn()
    vi.stubGlobal(
      "URL",
      Object.assign(URL, { createObjectURL: crear, revokeObjectURL: revocar })
    )
    const clic = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        expect(this.download).toBe("actividad.csv")
        expect(this.href).toBe("blob:archivo")
      })

    await descargar(
      "/administracion/actividad/exportar?tipo=sesiones",
      "tk",
      "actividad.csv"
    )

    const [url, init] = simulado.mock.calls[0]
    expect(url).toBe("/api/administracion/actividad/exportar?tipo=sesiones")
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tk")
    expect(clic).toHaveBeenCalledOnce()
    // Safari y algunas versiones de Firefox cancelan la descarga si se revoca en el mismo ciclo.
    expect(revocar).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1000)
    expect(revocar).toHaveBeenCalledWith("blob:archivo")
    clic.mockRestore()
  })

  it("convierte un error de la API en ErrorApi", async () => {
    simular(
      JSON.stringify({
        title: "Solicitud inválida",
        detail: "Revise los campos indicados.",
      }),
      422,
      "application/problem+json"
    )
    const error = await errorDe(descargar("/x", "tk", "x.csv"))
    expect(error.estado).toBe(422)
  })
})
