import { normalizarTexto } from "@/tipos"

export type TemaAyuda =
  | "primeros-pasos"
  | "proveedores-precios"
  | "negociacion"
  | "datos"
  | "administracion"

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
    clave: "negociacion",
    titulo: "Negociación",
    descripcion:
      "Crear negociaciones, fijar sus límites y supervisar al agente.",
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
          "En Negociaciones crea una negociación y fija sus límites; un agente negocia por usted con cada proveedor, y usted supervisa y puede intervenir. Al terminar, usted adjudica el acuerdo que elija; si su costo supera el umbral de aprobación o el acuerdo sale de sus límites, un aprobador lo aprueba antes de que sea el contrato.",
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
          "El menú de la izquierda agrupa las pantallas por área: Resumen, Proveedores, Inteligencia, Negociación, Sistema (solo administración) y Soporte. El botón de la esquina superior izquierda lo contrae a solo iconos; al pasar el ratón por cada uno verá su nombre y para qué sirve. En pantallas pequeñas ese mismo botón abre el menú.",
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
    slug: "negociar-con-proveedores",
    tema: "negociacion",
    titulo: "Crear y supervisar una negociación",
    resumen: "Del borrador a la publicación, y cómo intervenir en una sesión.",
    secciones: [
      {
        titulo: "Crear la negociación",
        parrafos: [
          "Solo el rol de compras crea, publica, reenvía, cancela y atiende a mano las negociaciones; quien aprueba o administra las ve sin poder cambiarlas.",
        ],
        pasos: [
          "En Negociaciones, pulse «Nueva negociación». Para renovar un contrato, use «Renovar» en el Tablero, en una alerta de vencimiento o en los contratos de la ficha del proveedor: la negociación toma del contrato los servicios, el plazo y al proveedor.",
          "Escriba el título, la fecha límite, las rondas y el estilo del agente. En una compra, elija los servicios con su cantidad y a los proveedores que invita (hasta 10).",
          "Al crear el borrador se guarda la referencia de precios de ese momento; con ella se sugieren el ideal y el límite de cada servicio.",
        ],
      },
      {
        titulo: "Fijar los límites",
        parrafos: [
          "En el borrador revise el ideal y el límite del precio de cada servicio, junto a la banda P25 · P50 · P75. Si el límite queda arriba del P75, verá un aviso: puede publicar, pero pagaría más que en tres de cada cuatro contratos.",
          "Active las demás palancas que le importen (plazo, plazo de pago, SLA, tope de aumento o cuota de implementación) y reparta 100 puntos de peso entre ellas y el precio. El total se ve mientras escribe.",
          "Guarde los cambios y pulse «Publicar». Si otra persona cambió el borrador al mismo tiempo, la plataforma se lo dice y le ofrece recargar.",
        ],
      },
      {
        titulo: "Publicar y compartir los enlaces",
        parrafos: [
          "Al publicar, cada proveedor recibe por correo su enlace personal, y usted lo ve una sola vez para copiarlo. Si un correo no sale o un proveedor pierde su enlace, use «Reenviar» en la tabla de sesiones: el enlace anterior deja de servir.",
        ],
      },
      {
        titulo: "Supervisar e intervenir",
        parrafos: [
          "La negociación muestra una sesión por proveedor, con su estado, quién la atiende, la ronda y qué tan buena es su última oferta para usted. La pantalla se actualiza sola cada pocos segundos.",
          "En una sesión verá la conversación, las ofertas y, en cada respuesta del agente, «¿Por qué respondió esto?». Con «Tomar el control» usted responde a mano: un mensaje, una contraoferta, aceptar la última oferta o cerrar sin acuerdo. Si lo que acepta o propone sale de sus límites, la plataforma le pide confirmarlo y lo marca para el aprobador. «Devolver al agente» le regresa la sesión.",
          "Si un proveedor pide hablar con una persona, su sesión aparece como «Escalada» hasta que usted la atienda y la devuelva.",
        ],
      },
    ],
    enlaces: [
      { texto: "Ir a Negociaciones", ruta: "/negociaciones" },
      {
        texto: "Leer «Adjudicar y aprobar»",
        ruta: "/ayuda/adjudicar-y-aprobar",
      },
    ],
  },
  {
    slug: "como-negocia-el-agente",
    tema: "negociacion",
    titulo: "Cómo negocia el agente",
    resumen:
      "Qué tan buena es una oferta para usted, cuánto cede el agente y cuándo acepta.",
    secciones: [
      {
        titulo: "Qué tan buena es una oferta para usted",
        parrafos: [
          "El agente califica cada oferta de 0 % a 100 %: 100 % es conseguir su ideal en todo y 0 % es quedar exactamente en su límite. Cada término cuenta según el peso que usted le dio.",
        ],
      },
      {
        titulo: "Cuánto cede en cada ronda",
        parrafos: [
          "El agente empieza pidiendo casi su ideal y, ronda tras ronda, se conforma con un poco menos, hasta llegar a su límite en la última. El estilo decide el ritmo: firme cede muy poco hasta las últimas rondas, balanceado cede poco al principio y más hacia el final, y flexible cede de forma pareja desde la primera ronda.",
          "Nunca pide algo peor para usted que lo que el proveedor ya ofreció, no revela su límite antes de la última ronda y casi nunca vuelve a pedir más de lo que pidió en la ronda anterior.",
        ],
      },
      {
        titulo: "Cuándo acepta",
        parrafos: [
          "Acepta cuando la oferta respeta todos sus límites y vale para usted al menos lo que el agente pediría en esa ronda. En la última ronda acepta cualquier oferta dentro de sus límites; si la oferta cruza alguno, cierra sin acuerdo.",
          "El acuerdo es tentativo: no es vinculante hasta que se adjudique y se apruebe.",
        ],
      },
      {
        titulo: "Lo que nunca hace",
        parrafos: [
          "No acepta nada fuera de sus límites, y nunca muestra al proveedor sus límites, sus pesos ni las ofertas de otros proveedores. Si otro proveedor ofreció algo mejor, solo dice que hay propuestas más competitivas.",
          "Si un precio parece un error de captura (menos de la décima parte o más de 10 veces la referencia de precio o, si no hay referencia, su límite), le pide al proveedor confirmarlo antes de responder, y esa respuesta no cuenta como ronda.",
        ],
      },
    ],
    enlaces: [
      { texto: "Ir a Negociaciones", ruta: "/negociaciones" },
      {
        texto: "Leer «Adjudicar y aprobar»",
        ruta: "/ayuda/adjudicar-y-aprobar",
      },
    ],
  },
  {
    slug: "adjudicar-y-aprobar",
    tema: "negociacion",
    titulo: "Adjudicar y aprobar",
    resumen:
      "Elegir al proveedor, cuándo lo aprueba otra persona y qué pasa si nadie gana.",
    secciones: [
      {
        titulo: "La evaluación",
        parrafos: [
          "Cuando vence la fecha límite o todas las sesiones terminan, la negociación pasa a «En evaluación». Si hay acuerdos tentativos, la sección «Evaluación» los muestra del mejor al peor, con «Recomendado» en el primero, y, debajo, «Por qué se recomienda» explica con texto qué aporta cada criterio al recomendado y qué cambios en los pesos cambiarían al ganador.",
          "Cada acuerdo se califica con su costo total, el desempeño del proveedor, su riesgo y el SLA. Los pesos que reparten 100 puntos entre esos cuatro criterios (por defecto, 40 al costo, 30 al desempeño, 15 al riesgo y 15 al SLA) los fija administración en Configuración. Si quiere probar otro reparto, en «Ajustar pesos» escriba cuatro pesos que sumen 100 y pulse «Recalcular»: es una prueba suya y no cambia la configuración, aunque si adjudica con esos pesos, la propuesta guarda los que usó.",
          "La recomendación es una guía: la decisión es suya.",
        ],
      },
      {
        titulo: "Adjudicar",
        pasos: [
          "En la tabla de candidatos, pulse «Adjudicar» en la fila del proveedor que elija. Solo el rol de compras adjudica.",
          "Si elige a uno que no es el recomendado, escriba la justificación (de 10 a 1,000 caracteres): queda con la propuesta para quien la apruebe.",
          "Lea en la confirmación si la adjudicación será directa o irá a un aprobador, y por qué. Después pulse «Confirmar».",
        ],
      },
      {
        titulo: "Cuándo decide un aprobador",
        parrafos: [
          "La adjudicación va a un aprobador si el costo total del acuerdo supera el umbral de aprobación o si el acuerdo quedó fuera de sus límites (por ejemplo, porque se aceptó o se propuso a mano). El umbral es de 500,000 MXN, salvo que administración lo cambie en Configuración. El costo total incluye la cuota de implementación y se compara en pesos mexicanos (los dólares, al tipo de cambio más reciente); un costo igual al umbral no lo supera.",
          "Si no se da ninguna de las dos razones, la adjudicación es directa: la negociación queda «Adjudicada» en ese momento. La regla se aplica al proponer, así que un cambio posterior del umbral no mueve una propuesta que ya espera aprobación.",
          "Al adjudicarse, la plataforma crea el contrato con lo acordado; su folio aparece en el resumen.",
        ],
      },
      {
        titulo: "Aprobar o rechazar",
        parrafos: [
          "Si la propuesta necesita aprobación, la negociación queda «Pendiente de aprobación». Quien tiene el rol de aprobación ve la misma evaluación con la propuesta resaltada, la justificación, las marcas «Fuera de límites» y el motivo por el que requiere aprobación. La lista de Negociaciones de quien aprueba empieza en «Por aprobar» si hay propuestas esperando.",
          "Compras y el resto del equipo ven la propuesta, pero no deciden: ven «Esperando aprobación de un aprobador», incluso quien la propuso. Solo quien propuso y además tiene el rol de aprobación ve «Usted propuso esta adjudicación; la aprueba otra persona».",
        ],
        pasos: [
          "Revise la propuesta, su justificación y el motivo.",
          "Pulse «Aprobar» para adjudicar, o «Rechazar» y escriba el motivo; queda registrado con la propuesta rechazada.",
        ],
      },
      {
        titulo: "Reglas de la aprobación",
        parrafos: [
          "Quien propone no aprueba: aunque tenga también el rol de aprobación, en su propia propuesta no ve «Aprobar» ni «Rechazar». Cuando interviene un aprobador, siempre es una persona distinta de quien propuso.",
          "Si la propuesta cambia mientras la revisa, la plataforma se lo dice y reemplaza los botones por «Revisar la propuesta nueva»: solo se aprueba o se rechaza lo que ya leyó.",
          "Al aprobar, la negociación queda «Adjudicada». Al rechazar, vuelve a «En evaluación», donde la sección «Evaluación» muestra la última propuesta rechazada y su motivo, y Compras puede proponer el mismo acuerdo u otro, o declarar desierta la negociación. Las propuestas rechazadas quedan en el resumen, con su motivo.",
        ],
      },
      {
        titulo: "Declarar desierta",
        parrafos: [
          "Si ningún acuerdo le conviene, pulse «Declarar desierta» en la sección «Evaluación», escriba el motivo y confirme. La negociación termina sin adjudicar a ningún proveedor, y eso no se puede deshacer. Solo se puede declarar desierta mientras está «En evaluación»: si hay una propuesta esperando aprobación, primero debe aprobarse o rechazarse.",
          "Una negociación que termina sin ningún acuerdo tentativo se declara desierta sola, sin motivo.",
        ],
      },
      {
        titulo: "El aviso a los proveedores",
        parrafos: [
          "Poco después de que la negociación se adjudica o se declara desierta, la plataforma envía a cada proveedor invitado que tenga correo el resultado que le toca: que su oferta fue adjudicada y Compras se pondrá en contacto, que la negociación se adjudicó a otra propuesta, o que se declaró desierta. También lo ve en su portal mientras su enlace siga vigente. Ni el correo ni el aviso del portal dicen quién ganó ni muestran ningún monto.",
          "Administración ve estos correos en Correos, como «Resultado de negociación».",
        ],
      },
      {
        titulo: "El resultado",
        parrafos: [
          "Con la negociación «Adjudicada» o «Desierta», la sección «Resultado» resume quién propuso y quién aprobó (o que fue una adjudicación directa), el proveedor, el costo total, el folio del contrato, el motivo si quedó desierta y las propuestas rechazadas. En Actividad, administración ve la adjudicación (directa o aprobada), la declaración de desierta y los avisos enviados a cada proveedor; las propuestas rechazadas se consultan en la sección «Resultado» de la negociación.",
        ],
      },
    ],
    enlaces: [{ texto: "Ir a Negociaciones", ruta: "/negociaciones" }],
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
          "En Correos ve cada correo enviado y si salió bien: las invitaciones y restablecimientos de contraseña, y también las invitaciones a negociar y los resultados que se avisan a los proveedores. Si el de una persona no salió, reintente desde su ficha o asígnele una contraseña temporal. A una cuenta desactivada no se le puede enviar el correo: actívela primero.",
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
          "Actividad reúne los inicios de sesión (incluidos los intentos fallidos), las acciones sobre usuarios, las importaciones, los cambios del catálogo, los cambios de la configuración de la puntuación y de la adjudicación, los entrenamientos del modelo de precios y las negociaciones (su publicación, cancelación, adjudicación o declaración de desierta, y los correos a los proveedores). Nada de esto se puede borrar ni modificar.",
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
      "Pesos de la puntuación y de la adjudicación, umbrales de riesgo y de aprobación, inflación y reentrenamiento del modelo.",
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
        titulo: "Adjudicación",
        parrafos: [
          "La tarjeta «Adjudicación» fija cuánto pesa cada criterio (costo total, desempeño, riesgo y SLA; deben sumar 100) al recomendar a quién adjudicar, y el umbral de aprobación en MXN: una adjudicación con un costo total mayor necesita un aprobador. Se guarda con «Guardar adjudicación», aparte de la puntuación, y el cambio queda en la Actividad.",
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
          "Estado del sistema comprueba cada 30 segundos la base de datos, los servicios de proveedores, de inteligencia y de negociación, la identidad (Keycloak), la mensajería (RabbitMQ) y el buzón de correo. En la mensajería avisa si una cola acumula mensajes sin procesar o si algún mensaje falló 5 veces y quedó apartado.",
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
