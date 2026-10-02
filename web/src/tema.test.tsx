import { act, cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import guionPrevio from "../public/tema.js?raw"
import { CLAVE_TEMA, ProveedorTema, useTema, type Tema } from "@/tema"

function Interruptor() {
  const { tema, cambiarTema } = useTema()
  return (
    <>
      <span data-testid="tema">{tema}</span>
      {(["claro", "oscuro", "sistema"] as Tema[]).map((opcion) => (
        <button key={opcion} type="button" onClick={() => cambiarTema(opcion)}>
          {opcion}
        </button>
      ))}
    </>
  )
}

/** Simula la preferencia del sistema operativo y permite cambiarla en caliente. */
function simularSistema(oscuroInicial: boolean) {
  let oscuro = oscuroInicial
  const oyentes = new Set<() => void>()
  vi.stubGlobal("matchMedia", (consulta: string) => ({
    get matches() {
      return consulta.includes("dark") && oscuro
    },
    media: consulta,
    addEventListener: (_: string, oyente: () => void) => oyentes.add(oyente),
    removeEventListener: (_: string, oyente: () => void) =>
      oyentes.delete(oyente),
  }))
  return {
    cambiar(valor: boolean) {
      oscuro = valor
      oyentes.forEach((oyente) => oyente())
    },
  }
}

function renderizar() {
  return render(
    <ProveedorTema>
      <Interruptor />
    </ProveedorTema>
  )
}

const html = document.documentElement

afterEach(() => {
  cleanup()
  localStorage.clear()
  html.classList.remove("dark")
  html.style.colorScheme = ""
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("ProveedorTema", () => {
  it("usa 'sistema' por defecto y sigue al sistema operativo en caliente", () => {
    const sistema = simularSistema(true)
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("sistema")
    expect(html).toHaveClass("dark")

    act(() => sistema.cambiar(false))
    expect(html).not.toHaveClass("dark")
  })

  it("guarda la elección y aplica la clase y el color-scheme", async () => {
    simularSistema(false)
    renderizar()

    await userEvent.click(screen.getByRole("button", { name: "oscuro" }))
    expect(localStorage.getItem(CLAVE_TEMA)).toBe("oscuro")
    expect(html).toHaveClass("dark")
    expect(html.style.colorScheme).toBe("dark")

    await userEvent.click(screen.getByRole("button", { name: "claro" }))
    expect(html).not.toHaveClass("dark")
    expect(html.style.colorScheme).toBe("light")
  })

  it("recupera el tema guardado aunque el sistema prefiera otro", () => {
    simularSistema(false)
    localStorage.setItem(CLAVE_TEMA, "oscuro")
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("oscuro")
    expect(html).toHaveClass("dark")
  })

  it("trata un valor guardado desconocido como 'sistema'", () => {
    simularSistema(true)
    localStorage.setItem(CLAVE_TEMA, "azul")
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("sistema")
    expect(html).toHaveClass("dark")
  })

  it("funciona aunque el navegador bloquee localStorage", async () => {
    simularSistema(false)
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    renderizar()

    expect(screen.getByTestId("tema")).toHaveTextContent("sistema")
    await userEvent.click(screen.getByRole("button", { name: "oscuro" }))
    expect(html).toHaveClass("dark")
  })

  it("useTema fuera del proveedor avisa en español", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    expect(() => render(<Interruptor />)).toThrow(
      "useTema debe usarse dentro de ProveedorTema"
    )
  })
})

describe("script previo al render (public/tema.js)", () => {
  const ejecutar = () => new Function(guionPrevio)()

  it.each([
    ["oscuro", false, true],
    ["claro", true, false],
    ["sistema", true, true],
    ["azul", true, true],
    [null, false, false],
  ])(
    "con %s guardado y sistema oscuro=%s aplica dark=%s",
    (guardado, sistemaOscuro, esperado) => {
      simularSistema(sistemaOscuro)
      if (guardado) localStorage.setItem(CLAVE_TEMA, guardado)

      ejecutar()

      expect(html.classList.contains("dark")).toBe(esperado)
      expect(html.style.colorScheme).toBe(esperado ? "dark" : "light")
    }
  )

  it("no falla si localStorage está bloqueado", () => {
    simularSistema(true)
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })

    expect(ejecutar).not.toThrow()
    expect(html).toHaveClass("dark")
  })
})
