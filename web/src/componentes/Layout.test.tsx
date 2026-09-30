import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Layout } from "@/componentes/Layout"

const removeUser = vi.fn().mockResolvedValue(undefined)
const signinRedirect = vi.fn().mockResolvedValue(undefined)
const autenticacion = {
  error: new Error("invalid_grant: Token is not active"),
  isAuthenticated: false,
  isLoading: false,
  activeNavigator: undefined,
  user: null,
  removeUser,
  signinRedirect,
}

vi.mock("react-oidc-context", () => ({
  hasAuthParams: () => false,
  useAuth: () => autenticacion,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("Layout con la sesión en error", () => {
  it("muestra un mensaje en español y permite volver a iniciar sesión", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>,
    )

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Tu sesión expiró o no se pudo iniciar sesión.",
    )
    expect(screen.queryByText(/invalid_grant/)).not.toBeInTheDocument()
    expect(signinRedirect).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: "Volver a iniciar sesión" }))

    expect(removeUser).toHaveBeenCalledOnce()
    expect(signinRedirect).toHaveBeenCalledOnce()
    expect(removeUser.mock.invocationCallOrder[0]).toBeLessThan(
      signinRedirect.mock.invocationCallOrder[0],
    )
  })
})
