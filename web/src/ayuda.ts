import { normalizarTexto } from "@/tipos"

export type TemaAyuda =
  "primeros-pasos" | "proveedores-precios" | "datos" | "administracion"

export const TEMAS: {
  clave: TemaAyuda
  titulo: string
  descripcion: string
  soloAdmin?: boolean
}[] = [
  {
    clave: "primeros-pasos",
    titulo: "Primeros pasos",
    descripcion: "Entrar, moverse por la plataforma y el flujo de trabajo.",
  },
  {
    clave: "proveedores-precios",
    titulo: "Proveedores y precios",
    descripcion: "Consultar proveedores, su desempeño y el precio justo.",
  },
  {
    clave: "datos",
    titulo: "Datos e importación",
    descripcion: "Cargar los datos del ERP y corregir archivos con errores.",
  },
  {
    clave: "administracion",
    titulo: "Administración",
    descripcion:
      "Usuarios, contraseñas, catálogo, actividad y estado del sistema.",
    soloAdmin: true,
  },
]

export type SeccionArticulo = {
  titulo?: string
  parrafos?: string[]
  pasos?: string[]
}

export type Articulo = {
  slug: string
  tema: TemaAyuda
  titulo: string
  resumen: string
  secciones: SeccionArticulo[]
  enlaces?: { texto: string; ruta: string }[]
}

export const ARTICULOS: Articulo[] = [
  {
    slug: "como-usar-pluri-one",
    tema: "primeros-pasos",
    titulo: "Cómo usar PluriOne",
    resumen:
      "El flujo de trabajo en cuatro pasos, de los datos a la adjudicación.",
    secciones: [
      {
        pasos: [
          "Administración importa del ERP el catálogo, los proveedores, los contratos y el desempeño.",
          "Usted revisa en Proveedores quién le vende, sus contratos y cómo rinde.",
          "En Precios compara lo que paga con el precio de referencia del mercado.",
          "La negociación asistida por IA, dentro de los límites que usted fije, llegará en una próxima versión; usted aprobará cada cierre.",
        ],
      },
      {
        parrafos: [
          "La guía del Tablero muestra su avance en estos pasos. Puede ocultarla y volver a mostrarla desde el menú de su cuenta, abajo a la izquierda.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir al Tablero", ruta: "/" }],
  },
  {
    slug: "entrar-y-moverse",
    tema: "primeros-pasos",
    titulo: "Entrar y moverse por la plataforma",
    resumen: "El inicio de sesión, el menú por áreas, su cuenta y el tema.",
    secciones: [
      {
        titulo: "Inicio de sesión",
        parrafos: [
          "Entre con su usuario o correo y su contraseña. La primera vez, use el enlace del correo de invitación para definir su contraseña, o la contraseña temporal que le entregó administración: la plataforma le pedirá cambiarla.",
          "Por seguridad, la sesión se cierra sola después de un tiempo. Si eso pasa, vuelva a iniciar sesión y regresará a la página donde estaba.",
        ],
      },
      {
        titulo: "El menú",
        parrafos: [
          "El menú de la izquierda agrupa las pantallas por área: Resumen, Proveedores, Inteligencia, Sistema (solo administración) y Soporte. El botón de la esquina superior izquierda lo contrae a solo iconos; al pasar el ratón por cada uno verá su nombre y para qué sirve. En pantallas pequeñas ese mismo botón abre el menú.",
        ],
      },
      {
        titulo: "Su cuenta y el tema",
        parrafos: [
          "Su nombre y su rol están abajo a la izquierda; desde ahí cierra sesión. El tema claro, el oscuro o el del sistema se elige con el botón de la barra superior.",
        ],
      },
    ],
  },
  {
    slug: "consultar-proveedores",
    tema: "proveedores-precios",
    titulo: "Consultar proveedores y su desempeño",
    resumen:
      "Buscar un proveedor, ordenar por puntuación o gasto y revisar sus contratos y su desempeño.",
    secciones: [
      {
        pasos: [
          "Abra Proveedores en el menú.",
          "Busque por nombre o RFC, o filtre por categoría, estado o «En riesgo».",
          "Ordene por puntuación, gasto anual, contratos vigentes o alertas con el encabezado de cada columna; un segundo clic invierte el orden.",
          "Abra un proveedor para ver su puntuación con su tendencia, sus alertas, sus contratos y su desempeño mensual.",
        ],
      },
      {
        titulo: "La puntuación",
        parrafos: [
          "Es una calificación de 0 a 100 de los últimos 12 meses, en la que pesa más lo reciente. Combina el cumplimiento del SLA, el tiempo de resolución, los incidentes críticos, las entregas a tiempo y la satisfacción. Cada proveedor se compara con los de su categoría principal, o con todos si su categoría tiene menos de 20 proveedores con desempeño.",
          "Cuanto menos historial tiene un proveedor, más se acerca su puntuación al promedio de su grupo; con menos de 6 meses lleva la marca «Historial corto». Un proveedor está en riesgo si su puntuación queda por debajo del umbral (40, salvo que administración lo cambie) o si bajó más de 10 puntos en 3 meses.",
        ],
      },
      {
        titulo: "Contratos frente al mercado",
        parrafos: [
          "En la pestaña Contratos, cada línea vigente dice si su precio está por debajo del P25, en el rango típico o sobre el P75. Haga clic en esa marca para ver el P25, el P50, el P75 y el ahorro potencial.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Proveedores", ruta: "/proveedores" }],
  },
  {
    slug: "precio-justo",
    tema: "proveedores-precios",
    titulo: "Entender el precio justo",
    resumen:
      "Qué significan el precio de referencia, los percentiles, el sobreprecio y el ahorro potencial.",
    secciones: [
      {
        parrafos: [
          "El precio de referencia es lo que se paga normalmente en el mercado por un servicio, en una cantidad y un plazo dados. Se expresa con tres valores: P25 (precio bajo), P50 (típico) y P75 (alto).",
          "Se calcula con el modelo de precios cuando hay uno que mejora la línea base; si no, con la línea base: los contratos del servicio de los últimos 24 meses, llevados a pesos de hoy con la inflación configurada. Precios dice cuál se usó y con cuántos contratos.",
          "Hay sobreprecio cuando usted paga más que el P75. El ahorro potencial es lo que ahorraría en lo que resta del contrato si pagara el P50.",
          "Si hay pocos contratos comparables (menos de 8), el precio se marca con baja confianza: tómelo como una estimación.",
        ],
      },
      {
        titulo: "Cómo consultarlo",
        pasos: [
          "Abra Precios y elija un servicio; puede buscarlo por nombre o código.",
          "Ajuste la cantidad y el plazo y pulse «Calcular».",
          "Revise el historial de precios y los contratos con sobreprecio del servicio, o cambie a «Todos los sobreprecios» para verlos de mayor a menor ahorro.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Precios", ruta: "/precios" }],
  },
  {
    slug: "importar-datos",
    tema: "datos",
    titulo: "Importar los datos del ERP",
    resumen: "El orden de los archivos y el formato que se acepta.",
    secciones: [
      {
        pasos: [
          "Abra Importación en el menú (solo administración).",
          "Elija el tipo de archivo en este orden: catálogo de servicios, proveedores, tipo de cambio, contratos y desempeño.",
          "Arrastre el archivo CSV o haga clic para elegirlo, y pulse «Importar».",
          "Revise el resultado: filas leídas, registros guardados y omitidos.",
        ],
      },
      {
        titulo: "Formato",
        parrafos: [
          "Archivos CSV en UTF-8, separados por coma o punto y coma, de hasta 10 MB. Contratos y desempeño hacen referencia a proveedores y servicios que ya deben estar importados.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Importación", ruta: "/importacion" }],
  },
  {
    slug: "errores-de-importacion",
    tema: "datos",
    titulo: "Qué hacer si un archivo tiene errores",
    resumen: "Leer la lista de errores y volver a intentarlo.",
    secciones: [
      {
        parrafos: [
          "Si un archivo tiene errores no se guarda ninguna fila: la importación es todo o nada. Verá una tabla con la fila, la columna y el problema de cada error.",
          "Corrija el archivo en su origen (el ERP o la hoja de cálculo), guárdelo de nuevo como CSV en UTF-8 y vuelva a importarlo con «Elegir otro archivo».",
          "Cada intento, completo o rechazado, queda en la bitácora de Actividad con quién lo hizo.",
        ],
      },
    ],
  },
  {
    slug: "gestionar-usuarios",
    tema: "administracion",
    titulo: "Dar de alta y administrar usuarios",
    resumen:
      "Altas por invitación o con contraseña temporal, roles y desactivación.",
    secciones: [
      {
        titulo: "Alta",
        pasos: [
          "En Usuarios, pulse «Nuevo usuario».",
          "Escriba nombre, apellidos y correo; el usuario se sugiere a partir del correo.",
          "Elija uno o más roles: Administración, Compras o Aprobación.",
          "Elija cómo obtendrá su contraseña: por invitación (recomendada) o con una contraseña temporal que usted verá una sola vez.",
        ],
      },
      {
        titulo: "Roles y protección",
        parrafos: [
          "Puede cambiar los roles desde la ficha de cada persona. Para proteger la plataforma, nadie puede quitarse a sí mismo el rol de administración ni desactivarse, y siempre debe quedar al menos un administrador activo.",
        ],
      },
      {
        titulo: "Desactivar",
        parrafos: [
          "Las cuentas se desactivan, no se borran: la persona deja de entrar, sus sesiones se cierran y su historial se conserva. Puede activarla de nuevo cuando quiera.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Usuarios", ruta: "/sistema/usuarios" }],
  },
  {
    slug: "contrasenas-y-correos",
    tema: "administracion",
    titulo: "Contraseñas y correos del sistema",
    resumen: "Invitaciones, restablecimientos y contraseñas temporales.",
    secciones: [
      {
        parrafos: [
          "La invitación es un correo con un enlace para que la persona defina su contraseña; vence en 72 horas. A quien ya entró antes se le envía un correo de restablecimiento que vence en 24 horas.",
          "La contraseña temporal se muestra una sola vez: cópiela y entréguela por un medio seguro. La persona deberá cambiarla al entrar.",
          "En Correos ve cada correo enviado y si salió bien. Si uno no salió, reintente desde la ficha de la persona o asígnele una contraseña temporal. A una cuenta desactivada no se le puede enviar el correo: actívela primero.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Correos", ruta: "/sistema/correos" }],
  },
  {
    slug: "revisar-actividad",
    tema: "administracion",
    titulo: "Revisar la actividad y exportarla",
    resumen: "La bitácora: quién hizo qué, cuándo y con qué resultado.",
    secciones: [
      {
        parrafos: [
          "Actividad reúne los inicios de sesión (incluidos los intentos fallidos), las acciones sobre usuarios, las importaciones, los cambios del catálogo y los cambios de la configuración de la puntuación y los entrenamientos del modelo de precios. Nada de esto se puede borrar ni modificar.",
          "Filtre por persona, tipo y fechas. Con «Exportar CSV» descarga los registros filtrados para abrirlos en Excel; se exportan como máximo los 10,000 más recientes, así que acote las fechas si necesita más.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Actividad", ruta: "/sistema/actividad" }],
  },
  {
    slug: "catalogo-de-servicios",
    tema: "administracion",
    titulo: "Mantener el catálogo de servicios",
    resumen: "Alta, edición y desactivación de los servicios de TI.",
    secciones: [
      {
        parrafos: [
          "El catálogo lista los servicios que aparecen en los contratos y en Precios. Puede darlos de alta, editarlos o desactivarlos; también se cargan con la importación del ERP.",
          "El código no cambia después de crearlo, porque las importaciones lo usan para identificar el servicio. Si un servicio ya tiene contratos, desde el Catálogo tampoco puede cambiar su categoría, su unidad ni su moneda, porque los precios históricos dependen de ellas.",
          "Un servicio desactivado deja de aparecer en Precios, pero sus contratos y su historial se conservan.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir al Catálogo", ruta: "/sistema/catalogo" }],
  },
  {
    slug: "configurar-puntuacion-y-modelo",
    tema: "administracion",
    titulo: "Configurar la puntuación y el modelo de precios",
    resumen:
      "Pesos de la puntuación, umbral de riesgo, inflación y reentrenamiento del modelo.",
    secciones: [
      {
        titulo: "Puntuación",
        pasos: [
          "Abra Configuración en el área Sistema.",
          "Reparta 100 puntos entre los cinco aspectos del desempeño; el total se muestra mientras escribe.",
          "Fije el umbral de riesgo: un proveedor con menos puntos queda en riesgo y genera una alerta.",
          "Ajuste la inflación anual que usa la línea base y pulse «Guardar cambios».",
        ],
      },
      {
        parrafos: [
          "Las puntuaciones, el ranking y las alertas se recalculan al guardar. Cada cambio queda en la Actividad con quién lo hizo y qué valores cambió.",
        ],
      },
      {
        titulo: "Modelo de precios",
        parrafos: [
          "El modelo se entrena solo cuando llegan 50 precios nuevos, y usted puede reentrenarlo con «Reentrenar modelo de precios». Solo se usa si su error (MAPE) es menor que el de la línea base; si no, el precio de referencia sigue con la línea base.",
          "Si el modelo promovido no se pudo cargar, por ejemplo después de una actualización, la página lo avisa y se usa la línea base hasta que lo reentrene.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Configuración", ruta: "/configuracion" }],
  },
  {
    slug: "estado-del-sistema",
    tema: "administracion",
    titulo: "Saber si el sistema está sano",
    resumen: "Qué significa cada estado y qué hacer si algo falla.",
    secciones: [
      {
        parrafos: [
          "Estado del sistema comprueba cada 30 segundos la base de datos, los servicios de proveedores y de inteligencia, la identidad (Keycloak), la mensajería (RabbitMQ) y el buzón de correo. En la mensajería avisa si una cola acumula mensajes sin procesar o si algún mensaje falló 5 veces y quedó apartado.",
          "Sano: responde en menos de un segundo. Con problemas: responde con lentitud o hay muchos mensajes pendientes. Caído: no responde en dos segundos o responde con un error.",
          "Si un servicio sigue caído, avise al equipo técnico con la hora y el detalle que muestra su tarjeta.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Estado del sistema", ruta: "/sistema/estado" }],
  },
]

export type Pregunta = {
  pregunta: string
  respuesta: string
  soloAdmin?: boolean
}

export const PREGUNTAS: Pregunta[] = [
  {
    pregunta: "No puedo entrar a la plataforma",
    respuesta:
      "Revise que su usuario y su contraseña sean correctos. Después de varios intentos fallidos la cuenta se bloquea unos minutos. Si olvidó su contraseña o su cuenta está desactivada, pida ayuda a administración.",
  },
  {
    pregunta: "Mi sesión se cerró sola",
    respuesta:
      "Por seguridad, la sesión vence después de un tiempo. Vuelva a iniciar sesión y regresará a la página donde estaba.",
  },
  {
    pregunta: "¿Por qué no veo el área Sistema?",
    respuesta:
      "Sistema es solo para el rol de Administración. Si necesita acceso, pídalo a una persona con ese rol.",
  },
  {
    pregunta: "¿Dónde cambio entre el tema claro y el oscuro?",
    respuesta:
      "Con el botón de tema de la barra superior: claro, oscuro o el del sistema. La preferencia se guarda en este navegador.",
  },
  {
    pregunta: "La invitación no llegó",
    respuesta:
      "Revise en Correos si se envió. Si no salió, reintente desde la ficha de la persona o asígnele una contraseña temporal. Pida también que revise su carpeta de correo no deseado.",
    soloAdmin: true,
  },
  {
    pregunta: "¿Puedo borrar un usuario o un servicio?",
    respuesta:
      "No. Se desactivan para conservar su historial y la bitácora; puede activarlos de nuevo cuando quiera.",
    soloAdmin: true,
  },
]

const TEMAS_DE_ADMIN = new Set(
  TEMAS.filter((t) => t.soloAdmin).map((t) => t.clave)
)

export function esSoloAdmin(articulo: Articulo): boolean {
  return TEMAS_DE_ADMIN.has(articulo.tema)
}

export function articulosVisibles(esAdmin: boolean): Articulo[] {
  return ARTICULOS.filter((a) => esAdmin || !esSoloAdmin(a))
}

function textoDe(articulo: Articulo): string {
  return normalizarTexto(
    [
      articulo.titulo,
      articulo.resumen,
      ...articulo.secciones.flatMap((s) => [
        s.titulo ?? "",
        ...(s.parrafos ?? []),
        ...(s.pasos ?? []),
      ]),
    ].join(" ")
  )
}

// No dicen de qué trata un artículo: "¿cómo importar?" no debe exigir que el texto diga "cómo".
const PALABRAS_DE_PREGUNTA = new Set([
  "como",
  "cual",
  "cuales",
  "cuando",
  "donde",
  "que",
  "quien",
])

/** Artículos visibles que contienen todas las palabras (sin acentos, mayúsculas, signos ni palabras de pregunta). */
export function buscarArticulos(texto: string, esAdmin: boolean): Articulo[] {
  const palabras = normalizarTexto(texto)
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter((p) => p && !PALABRAS_DE_PREGUNTA.has(p))
  return articulosVisibles(esAdmin).filter((a) => {
    const contenido = textoDe(a)
    return palabras.every((p) => contenido.includes(p))
  })
}

export function articuloPorSlug(
  slug: string | undefined
): Articulo | undefined {
  return ARTICULOS.find((a) => a.slug === slug)
}
