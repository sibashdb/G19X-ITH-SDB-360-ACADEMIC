import { createBrowserRouter } from "react-router"
import { Layout } from "@/componentes/Layout"
import { Importacion } from "@/paginas/Importacion"
import { Inicio } from "@/paginas/Inicio"
import { NoEncontrado } from "@/paginas/NoEncontrado"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"
import { Proveedores } from "@/paginas/Proveedores"

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Inicio },
      { path: "proveedores", Component: Proveedores },
      { path: "proveedores/:id", Component: ProveedorDetalle },
      { path: "importacion", Component: Importacion },
      { path: "*", Component: NoEncontrado },
    ],
  },
])
