import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type {
  Adjudicacion,
  Candidato,
  Evaluacion,
  Recomendacion,
} from "@/adjudicacion"
import { Negociacion } from "@/paginas/Negociacion"
import { sesionDePrueba } from "@/pruebas/sesion"
import {
  esperarSinViolaciones,
  llamadaA,
  renderizarPagina,
  respuestaDiferida,
  respuestaJson,
  simularRutas,
} from "@/pruebas/utilidades"
import { formatoMoneda } from "@/tipos"

vi.mock("react-oidc-context", async () =>
  (await import("@/pruebas/sesion")).oidcSimulado()
)

const ID = "5d1c2b0e-6f4a-4a8e-9f61-3c2a7e0b9d42"
const RUTA = `/api/negociacion/eventos/${ID}`
const EVALUACION = `${RUTA}/evaluacion`
const ADJUDICACION = `${RUTA}/adjudicacion`
const DESIERTA = `${RUTA}/desierta`

const sesion = (
  id: string,
  proveedor: string,
  estado: string,
  fueraDeLimites = false
) => ({
  id,
  proveedor_id: `p-${id}`,
  proveedor_nombre: proveedor,
  estado,
  modo: "agente",
  ronda: 3,
  utilidad: 0.62,
  correo_estado: "enviado",
  correo_error: null,
  fuera_de_limites: fueraDeLimites,
  actualizado_en: "2026-10-14T18:30:00Z",
})

const EVENTO = {
  id: ID,
  folio: "NEG-2026-0001",
  tipo: "compra",
  titulo: "Licencias de correo 2027",
  moneda: "MXN",
  plazo_meses: 12,
  estado: "en_evaluacion",
  fecha_limite: "2026-10-21T23:00:00Z",
  rondas_max: 6,
  estilo: "balanceado",
  contrato_origen_id: null,
  proveedor_vigente_id: null,
  invitados: [
    { id: "p-s1", nombre: "Nube Norte" },
    { id: "p-s2", nombre: "Datos del Sur" },
  ],
  lineas: [],
  palancas: [],
  referencia_fecha: null,
  creado_por_nombre: "Ana López",
  creado_en: "2026-10-14T18:00:00Z",
  publicado_en: "2026-10-14T18:00:00Z",
  cerrado_en: "2026-10-21T23:00:00Z",
  motivo_cancelacion: null,
  motivo_desierta: null,
  version: 5,
  errores: [],
  avisos: [],
  sesiones: [
    sesion("s1", "Nube Norte", "acuerdo_tentativo"),
    sesion("s2", "Datos del Sur", "acuerdo_tentativo", true),
  ],
}

const NORMALIZADOS = { costo: 1, desempeno: 1, riesgo: 1, sla: 1 }

const NUBE_NORTE: Candidato = {
  id: "s1",
  proveedor_id: "p-s1",
  nombre: "Nube Norte",
  costo_total: "480000.00",
  costo_total_mxn: "480000.00",
  desempeno: 82.4,
  riesgo: {
    valor: 0.2,
    nivel: "bajo",
    concentracion: 0.35,
    tendencia: 0.1,
    sin_historial: false,
  },
  sla: "99.90",
  normalizados: NORMALIZADOS,
  aportes: { costo: 40, desempeno: 24, riesgo: 12, sla: 12 },
  puntaje: 78.3,
  lugar: 1,
}
const DATOS_DEL_SUR: Candidato = {
  ...NUBE_NORTE,
  id: "s2",
  proveedor_id: "p-s2",
  nombre: "Datos del Sur",
  costo_total: "510000.00",
  costo_total_mxn: "510000.00",
  puntaje: 66.1,
  lugar: 2,
}

const RECOMENDACION: Recomendacion = {
  pesos: { costo: 40, desempeno: 30, riesgo: 15, sla: 15 },
  umbral_aprobacion: "500000.00",
  tipo_cambio: null,
  candidatos: [NUBE_NORTE, DATOS_DEL_SUR],
  recomendado: "s1",
  margen: 12.2,
  explicacion: ["Nube Norte obtiene el mejor puntaje: 78.3 contra 66.1."],
  sensibilidad: [],
}
const CON_RECOMENDACION: Evaluacion = {
  recomendacion: RECOMENDACION,
  vigente: null,
  historial: [],
}

/** Lo que devuelve el servicio al proponer: la evaluación con la propuesta ya vigente. */
const propuesta = (
  sesionId: string,
  estado: Adjudicacion["estado"]
): Evaluacion => ({
  recomendacion: RECOMENDACION,
  historial: [],
  vigente: {
    id: "a1",
    sesion_id: sesionId,
    propuesta_por_id: "ana-1",
    propuesta_por_nombre: "Ana López",
    propuesta_en: "2026-10-22T16:00:00Z",
    recomendada_sesion_id: "s1",
    se_aparta: sesionId !== "s1",
    justificacion: null,
    costo_total: "480000.00",
    costo_total_mxn: "480000.00",
    requiere_aprobacion: estado === "pendiente",
    motivo_aprobacion: [],
    recomendacion: RECOMENDACION,
    estado,
    decidida_por_nombre: null,
    decidida_en: null,
    motivo_rechazo: null,
    contrato_folio: null,
  },
})

const JUSTIFICACION = "El costo es mayor, pero ofrece soporte local."
const MENSAJE_OBLIGATORIA =
  "Para elegir un proveedor distinto del recomendado, escriba la justificación (de 10 a 1,000 caracteres)."
const MENSAJE_LONGITUD = "La justificación debe tener de 10 a 1,000 caracteres."

function abrir() {
  return renderizarPagina(
    <>
      <Negociacion />
      <div id="contenido" tabIndex={-1} />
    </>,
    { ruta: `/negociaciones/${ID}`, patron: "/negociaciones/:id" }
  )
}

/** Abre la página con la evaluación y, opcionalmente, otra recomendación o sesiones. */
function abrirConEvaluacion(
  evaluacion: Evaluacion = CON_RECOMENDACION,
  evento: typeof EVENTO = EVENTO,
  rutas: Record<string, () => Response | Promise<Response>> = {}
) {
  const api = simularRutas({
    [`GET ${RUTA}`]: () => respuestaJson(evento),
    [`GET ${EVALUACION}`]: () => respuestaJson(evaluacion),
    ...rutas,
  })
  return { api, ...abrir() }
}

const nombreBoton = (proveedor: string) => `Adjudicar a ${proveedor}`

/** Abre la confirmación de un proveedor desde su fila de la tabla de candidatos. */
async function abrirDialogo(proveedor: string) {
  const tabla = await screen.findByRole("table", {
    name: "Candidatos de la evaluación",
  })
  await userEvent.click(
    within(tabla).getByRole("button", { name: nombreBoton(proveedor) })
  )
  return screen.findByRole("dialog", { name: nombreBoton(proveedor) })
}

beforeEach(() => {
  sesionDePrueba.roles = ["comprador"]
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Adjudicar", () => {
  it("anticipa la adjudicación directa con el costo y el umbral", async () => {
    abrirConEvaluacion()
    const dialogo = await abrirDialogo("Nube Norte")
    expect(dialogo).toHaveTextContent(
      `Se adjudicará directamente: el costo total (${formatoMoneda("480000.00", "MXN")}) no supera el umbral de aprobación (${formatoMoneda("500000.00", "MXN")}) y el acuerdo está dentro de sus límites.`
    )
    expect(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    ).toBeInTheDocument()
  })

  it("anticipa el aprobador por el umbral, por los límites o por los dos", async () => {
    const costo = formatoMoneda("510000.00", "MXN")
    const umbral = formatoMoneda("500000.00", "MXN")
    const casos: [string, Evaluacion, typeof EVENTO, string][] = [
      [
        "umbral",
        CON_RECOMENDACION,
        {
          ...EVENTO,
          sesiones: [
            sesion("s1", "Nube Norte", "acuerdo_tentativo"),
            sesion("s2", "Datos del Sur", "acuerdo_tentativo"),
          ],
        },
        `Irá a un aprobador porque el costo total (${costo}) supera el umbral de aprobación (${umbral}).`,
      ],
      [
        "límites",
        {
          ...CON_RECOMENDACION,
          recomendacion: { ...RECOMENDACION, umbral_aprobacion: "600000.00" },
        },
        EVENTO,
        "Irá a un aprobador porque el acuerdo está fuera de sus límites.",
      ],
      [
        "los dos",
        CON_RECOMENDACION,
        EVENTO,
        `Irá a un aprobador porque el costo total (${costo}) supera el umbral de aprobación (${umbral}) y el acuerdo está fuera de sus límites.`,
      ],
    ]
    for (const [, evaluacion, evento, texto] of casos) {
      abrirConEvaluacion(evaluacion, evento)
      const dialogo = await abrirDialogo("Datos del Sur")
      expect(dialogo).toHaveTextContent(texto)
      expect(dialogo).not.toHaveTextContent("Se adjudicará directamente")
      cleanup()
    }
  })

  it("pide la justificación solo si no es el recomendado", async () => {
    abrirConEvaluacion()
    const recomendado = await abrirDialogo("Nube Norte")
    expect(
      within(recomendado).queryByLabelText("Justificación")
    ).not.toBeInTheDocument()
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )

    const otro = await abrirDialogo("Datos del Sur")
    const campo = within(otro).getByLabelText("Justificación")
    expect(campo).toBeRequired()
    expect(campo).toHaveAccessibleDescription(
      "Explique por qué se aparta de la recomendación (de 10 a 1,000 caracteres)."
    )
  })

  it("valida la justificación antes de enviar y lo dice junto al campo", async () => {
    const { api } = abrirConEvaluacion()
    const dialogo = await abrirDialogo("Datos del Sur")
    const confirmar = within(dialogo).getByRole("button", { name: "Confirmar" })
    const campo = within(dialogo).getByLabelText("Justificación")

    await userEvent.click(confirmar)
    expect(within(dialogo).getByText(MENSAJE_OBLIGATORIA)).toBeInTheDocument()
    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription(
      expect.stringContaining(MENSAJE_OBLIGATORIA)
    )
    // El error del campo no es una región viva: el foco pasa al campo para que se lea.
    expect(campo).toHaveFocus()

    // Los espacios no cuentan: «corta» y espacios sobrantes siguen sin llegar a 10 caracteres.
    await userEvent.type(campo, "   corta   ")
    expect(within(dialogo).getByText(MENSAJE_LONGITUD)).toBeInTheDocument()
    await userEvent.click(confirmar)

    await userEvent.type(campo, " pero ya suficiente")
    expect(
      within(dialogo).queryByText(MENSAJE_LONGITUD)
    ).not.toBeInTheDocument()
    expect(
      api.mock.calls.filter(([, init]) => init?.method === "POST")
    ).toHaveLength(0)
  })

  it("manda la sesión, los pesos como texto y la justificación", async () => {
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () =>
        respuestaJson(propuesta("s2", "pendiente")),
    })
    const dialogo = await abrirDialogo("Datos del Sur")
    await userEvent.type(
      within(dialogo).getByLabelText("Justificación"),
      `  ${JUSTIFICACION}  `
    )
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    await screen.findByText("Se envió la propuesta a un aprobador.")
    expect(llamadaA(api, ADJUDICACION, "POST").cuerpo).toEqual({
      sesion_id: "s2",
      pesos: "40,30,15,15",
      justificacion: JUSTIFICACION,
    })
  })

  it("al elegir al recomendado no manda justificación", async () => {
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () => respuestaJson(propuesta("s1", "directa")),
    })
    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    await screen.findByText("Se adjudicó la negociación a Nube Norte.")
    expect(llamadaA(api, ADJUDICACION, "POST").cuerpo).toEqual({
      sesion_id: "s1",
      pesos: "40,30,15,15",
    })
  })

  it("manda los pesos de la evaluación que se ve, no los que el servicio rechazó", async () => {
    const rechazados = `${EVALUACION}?pesos=30,30,30,10`
    // La negociación no cambia de estado: así se ve si la sección queda atorada en los pesos rechazados.
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${rechazados}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los datos marcados.",
            codigo: "pesos_invalidos",
            errores: [{ campo: "pesos", mensaje: "Pesos inválidos." }],
          },
          422
        ),
      [`POST ${ADJUDICACION}`]: () => respuestaJson(propuesta("s1", "directa")),
    })
    for (const [i, nombre] of [
      "Costo total",
      "Desempeño",
      "Riesgo",
      "SLA",
    ].entries()) {
      const campo = await screen.findByLabelText(`Peso (${nombre})`)
      await userEvent.clear(campo)
      await userEvent.type(campo, ["30", "30", "30", "10"][i])
    }
    await userEvent.click(screen.getByRole("button", { name: "Recalcular" }))
    await screen.findByText(
      "Se muestran los resultados de los últimos pesos que se calcularon."
    )

    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    await screen.findByText("Se adjudicó la negociación a Nube Norte.")
    expect(llamadaA(api, ADJUDICACION, "POST").cuerpo).toEqual({
      sesion_id: "s1",
      pesos: "40,30,15,15",
    })
    // Tras la acción, la sección vuelve a los pesos configurados y ya no avisa del rechazo.
    await waitFor(() =>
      expect(
        screen.queryByText(
          "Se muestran los resultados de los últimos pesos que se calcularon."
        )
      ).not.toBeInTheDocument()
    )
  })

  it("un 422 de justificación queda junto al campo", async () => {
    const servicio =
      "Para elegir un proveedor distinto del recomendado, escriba la justificación (de 10 a 1,000 caracteres)."
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los datos marcados.",
            codigo: "justificacion_requerida",
            errores: [{ campo: "justificacion", mensaje: servicio }],
          },
          422
        ),
    })
    const dialogo = await abrirDialogo("Datos del Sur")
    const campo = within(dialogo).getByLabelText("Justificación")
    await userEvent.type(campo, JUSTIFICACION)
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    const mensaje = await within(dialogo).findByText(servicio)
    expect(campo).toBeInvalid()
    expect(campo.getAttribute("aria-describedby")).toContain(mensaje.id)
    expect(campo).toHaveFocus()
    // Es del campo: la región de avisos del diálogo no lo repite y el diálogo sigue abierto.
    expect(within(dialogo).getByRole("alert")).toBeEmptyDOMElement()
    expect(screen.getByRole("dialog")).toBe(dialogo)
  })

  it("los demás errores del servicio se muestran en el diálogo, que sigue abierto", async () => {
    const errores = [
      respuestaJson(
        {
          title: "Conflicto",
          detail: "La negociación ya no está en evaluación.",
          codigo: "estado_invalido",
        },
        409
      ),
      respuestaJson(
        {
          title: "Servicio no disponible",
          detail: "No se pudo consultar la recomendación; intente de nuevo.",
          codigo: "dependencia_no_disponible",
        },
        503
      ),
      respuestaJson(
        {
          title: "Solicitud inválida",
          detail: "Revise los datos marcados.",
          codigo: "sesion_no_candidata",
          errores: [
            {
              campo: "sesion_id",
              mensaje:
                "La sesión elegida no es un acuerdo tentativo de esta negociación.",
            },
          ],
        },
        422
      ),
    ]
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () => errores.shift()!,
    })
    const dialogo = await abrirDialogo("Nube Norte")
    const confirmar = within(dialogo).getByRole("button", { name: "Confirmar" })
    const alerta = within(dialogo).getByRole("alert")
    expect(alerta).toBeEmptyDOMElement()

    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "La negociación ya no está en evaluación."
      )
    )
    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "No se pudo consultar la recomendación; intente de nuevo."
      )
    )
    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(alerta).toHaveTextContent(
        "La sesión elegida no es un acuerdo tentativo de esta negociación."
      )
    )
    expect(screen.getByRole("dialog")).toBe(dialogo)
    // Al cerrar y volver a abrir, el error anterior ya no está.
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    const otra = await abrirDialogo("Nube Norte")
    expect(within(otra).getByRole("alert")).toBeEmptyDOMElement()
  })

  it("un doble clic en Confirmar manda una sola propuesta", async () => {
    const lenta = respuestaDiferida()
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${ADJUDICACION}`]: () => lenta.promesa,
    })
    const dialogo = await abrirDialogo("Nube Norte")
    const confirmar = within(dialogo).getByRole("button", { name: "Confirmar" })
    await userEvent.click(confirmar)
    await userEvent.click(confirmar)
    // aria-disabled y no disabled: el botón conserva el foco mientras se envía.
    expect(confirmar).toHaveAttribute("aria-disabled", "true")
    expect(confirmar).not.toBeDisabled()
    await act(async () =>
      lenta.resolver(respuestaJson(propuesta("s1", "directa")))
    )
    await screen.findByText("Se adjudicó la negociación a Nube Norte.")
    expect(
      api.mock.calls.filter(
        ([url, init]) => url === ADJUDICACION && init?.method === "POST"
      )
    ).toHaveLength(1)
  })

  it("al adjudicar avisa y el foco pasa al contenido", async () => {
    let adjudicada = false
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: adjudicada ? "adjudicado" : "en_evaluacion",
        }),
      [`POST ${ADJUDICACION}`]: () => {
        adjudicada = true
        return respuestaJson(propuesta("s1", "directa"))
      },
    })
    const dialogo = await abrirDialogo("Nube Norte")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Confirmar" })
    )
    const aviso = await screen.findByText(
      "Se adjudicó la negociación a Nube Norte."
    )
    expect(aviso).toHaveAttribute("role", "status")
    // La negociación salió de «En evaluación»: la sección y el botón que abrió el diálogo desaparecen.
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Evaluación" })
      ).not.toBeInTheDocument()
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("declarar desierta manda el motivo y avisa", async () => {
    let desierta = false
    const { api } = abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`GET ${RUTA}`]: () =>
        respuestaJson({
          ...EVENTO,
          estado: desierta ? "desierto" : "en_evaluacion",
        }),
      [`POST ${DESIERTA}`]: () => {
        desierta = true
        return respuestaJson({
          recomendacion: null,
          vigente: null,
          historial: [],
        })
      },
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    const motivo = within(dialogo).getByLabelText("Motivo")
    expect(motivo).toHaveAttribute("maxlength", "500")
    await userEvent.type(motivo, "Ninguna propuesta conviene")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Declarar desierta" })
    )
    expect(
      await screen.findByText("Se declaró desierta la negociación.")
    ).toHaveAttribute("role", "status")
    expect(llamadaA(api, DESIERTA, "POST").cuerpo).toEqual({
      motivo: "Ninguna propuesta conviene",
    })
    await waitFor(() =>
      expect(document.getElementById("contenido")).toHaveFocus()
    )
  })

  it("el motivo de la desierta que el servicio rechaza queda junto al campo", async () => {
    abrirConEvaluacion(CON_RECOMENDACION, EVENTO, {
      [`POST ${DESIERTA}`]: () =>
        respuestaJson(
          {
            title: "Solicitud inválida",
            detail: "Revise los datos marcados.",
            errores: [{ campo: "motivo", mensaje: "Escriba el motivo." }],
          },
          422
        ),
    })
    await userEvent.click(
      await screen.findByRole("button", { name: "Declarar desierta" })
    )
    const dialogo = await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    await userEvent.type(within(dialogo).getByLabelText("Motivo"), "   ")
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Declarar desierta" })
    )
    expect(await within(dialogo).findByText("Escriba el motivo.")).toBeVisible()
    expect(within(dialogo).getByLabelText("Motivo")).toBeInvalid()
  })

  it("quien no es comprador no ve Adjudicar ni Declarar desierta", async () => {
    sesionDePrueba.roles = ["aprobador"]
    abrirConEvaluacion()
    await screen.findByRole("table", { name: "Candidatos de la evaluación" })
    expect(
      screen.queryByRole("button", { name: /Adjudicar/ })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Declarar desierta" })
    ).not.toBeInTheDocument()
  })

  it("el comprador puede declarar desierta aunque no haya acuerdos que evaluar", async () => {
    abrirConEvaluacion({ recomendacion: null, vigente: null, historial: [] })
    await screen.findByText("No hay acuerdos tentativos para evaluar.")
    expect(
      screen.getByRole("button", { name: "Declarar desierta" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /Adjudicar/ })
    ).not.toBeInTheDocument()
  })

  it("no tiene violaciones de axe con el diálogo abierto", async () => {
    abrirConEvaluacion()
    await abrirDialogo("Datos del Sur")
    await esperarSinViolaciones(document.body)
    await userEvent.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    )
    await userEvent.click(
      screen.getByRole("button", { name: "Declarar desierta" })
    )
    await screen.findByRole("dialog", {
      name: "Declarar desierta la negociación",
    })
    await esperarSinViolaciones(document.body)
  })
})
