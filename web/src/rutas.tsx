import { createBrowserRouter } from "react-router"
import { Layout } from "@/componentes/Layout"
import { Alertas } from "@/paginas/Alertas"
import { Configuracion } from "@/paginas/Configuracion"
import { Importacion } from "@/paginas/Importacion"
import { NoEncontrado } from "@/paginas/NoEncontrado"
import { Precios } from "@/paginas/Precios"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"
import { Proveedores } from "@/paginas/Proveedores"
import { Ranking } from "@/paginas/Ranking"
import { Tablero } from "@/paginas/Tablero"

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Tablero },
      { path: "proveedores", Component: Proveedores },
      { path: "proveedores/:id", Component: ProveedorDetalle },
      { path: "ranking", Component: Ranking },
      { path: "precios", Component: Precios },
      { path: "alertas", Component: Alertas },
      { path: "importacion", Component: Importacion },
      { path: "configuracion", Component: Configuracion },
      { path: "*", Component: NoEncontrado },
    ],
  },
])
