import { createBrowserRouter, type RouteObject } from "react-router"
import { Layout } from "@/componentes/Layout"

// Cada página es un archivo aparte que se descarga la primera vez que se visita: el arranque no
// carga Recharts ni las pantallas de administración que la persona quizá nunca abra.
export const paginas: RouteObject[] = [
  {
    index: true,
    lazy: async () => ({
      Component: (await import("@/paginas/Tablero")).Tablero,
    }),
  },
  {
    path: "proveedores",
    lazy: async () => ({
      Component: (await import("@/paginas/Proveedores")).Proveedores,
    }),
  },
  {
    path: "proveedores/:id",
    lazy: async () => ({
      Component: (await import("@/paginas/ProveedorDetalle")).ProveedorDetalle,
    }),
  },
  {
    path: "ranking",
    lazy: async () => ({
      Component: (await import("@/paginas/Ranking")).Ranking,
    }),
  },
  {
    path: "precios",
    lazy: async () => ({
      Component: (await import("@/paginas/Precios")).Precios,
    }),
  },
  {
    path: "alertas",
    lazy: async () => ({
      Component: (await import("@/paginas/Alertas")).Alertas,
    }),
  },
  {
    path: "importacion",
    lazy: async () => ({
      Component: (await import("@/paginas/Importacion")).Importacion,
    }),
  },
  {
    path: "configuracion",
    lazy: async () => ({
      Component: (await import("@/paginas/Configuracion")).Configuracion,
    }),
  },
  {
    path: "sistema",
    lazy: async () => ({ Component: (await import("@/paginas/Panel")).Panel }),
  },
  {
    path: "sistema/estado",
    lazy: async () => ({
      Component: (await import("@/paginas/EstadoSistema")).EstadoSistema,
    }),
  },
  {
    path: "sistema/usuarios",
    lazy: async () => ({
      Component: (await import("@/paginas/Usuarios")).Usuarios,
    }),
  },
  {
    path: "sistema/usuarios/:id",
    lazy: async () => ({
      Component: (await import("@/paginas/UsuarioDetalle")).UsuarioDetalle,
    }),
  },
  {
    path: "sistema/correos",
    lazy: async () => ({
      Component: (await import("@/paginas/Correos")).Correos,
    }),
  },
  {
    path: "sistema/actividad",
    lazy: async () => ({
      Component: (await import("@/paginas/Actividad")).Actividad,
    }),
  },
  {
    path: "sistema/catalogo",
    lazy: async () => ({
      Component: (await import("@/paginas/Catalogo")).Catalogo,
    }),
  },
  {
    path: "ayuda",
    lazy: async () => ({ Component: (await import("@/paginas/Ayuda")).Ayuda }),
  },
  {
    path: "ayuda/:articulo",
    lazy: async () => ({
      Component: (await import("@/paginas/ArticuloAyuda")).ArticuloAyuda,
    }),
  },
  {
    path: "*",
    lazy: async () => ({
      Component: (await import("@/paginas/NoEncontrado")).NoEncontrado,
    }),
  },
]

/** Lo que se ve mientras llega la primera página (unos milisegundos en la red local). */
function CargaInicial() {
  return (
    <p role="status" className="p-6 text-muted-foreground">
      Cargando…
    </p>
  )
}

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    HydrateFallback: CargaInicial,
    children: paginas,
  },
])
