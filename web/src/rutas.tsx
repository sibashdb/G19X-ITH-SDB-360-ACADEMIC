import { createBrowserRouter } from "react-router"
import { Layout } from "@/componentes/Layout"
import { Actividad } from "@/paginas/Actividad"
import { Alertas } from "@/paginas/Alertas"
import { Catalogo } from "@/paginas/Catalogo"
import { Configuracion } from "@/paginas/Configuracion"
import { Correos } from "@/paginas/Correos"
import { EstadoSistema } from "@/paginas/EstadoSistema"
import { Importacion } from "@/paginas/Importacion"
import { NoEncontrado } from "@/paginas/NoEncontrado"
import { Panel } from "@/paginas/Panel"
import { Precios } from "@/paginas/Precios"
import { ProveedorDetalle } from "@/paginas/ProveedorDetalle"
import { Proveedores } from "@/paginas/Proveedores"
import { Ranking } from "@/paginas/Ranking"
import { Tablero } from "@/paginas/Tablero"
import { Usuarios } from "@/paginas/Usuarios"
import { UsuarioDetalle } from "@/paginas/UsuarioDetalle"

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
      { path: "sistema", Component: Panel },
      { path: "sistema/estado", Component: EstadoSistema },
      { path: "sistema/usuarios", Component: Usuarios },
      { path: "sistema/usuarios/:id", Component: UsuarioDetalle },
      { path: "sistema/correos", Component: Correos },
      { path: "sistema/actividad", Component: Actividad },
      { path: "sistema/catalogo", Component: Catalogo },
      { path: "*", Component: NoEncontrado },
    ],
  },
])
