import { createBrowserRouter } from "react-router"
import { Layout } from "@/componentes/Layout"
import { Inicio } from "@/paginas/Inicio"
import { NoEncontrado } from "@/paginas/NoEncontrado"

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Inicio },
      { path: "*", Component: NoEncontrado },
    ],
  },
])
