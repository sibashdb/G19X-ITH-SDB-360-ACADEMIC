import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "react-oidc-context"
import { RouterProvider } from "react-router/dom"
import { configuracionOidc } from "@/auth"
import { router } from "@/rutas"
import { ProveedorTema } from "@/tema"
import "./index.css"

const clienteConsultas = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ProveedorTema>
      <AuthProvider {...configuracionOidc}>
        <QueryClientProvider client={clienteConsultas}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AuthProvider>
    </ProveedorTema>
  </StrictMode>
)
