# Adjudicación en la interfaz (4′b): plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cuando una negociación termina, el comprador ve en la web los acuerdos ordenados y explicados, los recalcula con otros pesos, adjudica o declara desierta, y el aprobador aprueba o rechaza. También se agregan los filtros nuevos, el aviso del portal, la sección «Adjudicación» de Configuración, la ayuda, el glosario y la revisión en navegador.

**Architecture:** Solo cambia la web, porque los servicios de 4′a ya están en esta rama (`a872ed5..0220b36`).
- **Módulo común:** `web/src/adjudicacion.ts` copia los esquemas de la evaluación y concentra el gancho, los nombres y los textos de la regla.
- **Componentes:** van en `web/src/componentes/adjudicacion/`, y la página `Negociacion.tsx` elige qué sección mostrar según el estado del evento.
- **Patrones de N1b:** se reutilizan `useNegociacion`, `ContenidoVivo`, `Campo`, el patrón de `DialogoCancelar` y el total de pesos de `FormularioPuntuacion`.

**Tech Stack:** React 19 + TypeScript 6, Vite 8, Tailwind v4 con los tokens de `web/src/index.css`, shadcn/radix, TanStack Query 5, react-router 8, lucide-react; Vitest + Testing Library + axe-core.

**Spec:** `docs/superpowers/specs/2026-10-16-adjudicacion-y-aprobacion-design.md`.
- Este plan sigue §7 (interfaz), §4.2 y §8 (las rutas y los errores que consume), §4.6 (los textos del portal), §9 (fila «Web») y §12 (4′b).
- Los rulings de 4′a que tocan la web están en el ledger de 4′a. La spec ya los recoge:
  - aprobar y rechazar llevan `adjudicacion_id`, y el 409 `propuesta_distinta`;
  - `pesos` viaja como texto;
  - la foto guardada se muestra fuera de `en_evaluacion`.

## Global Constraints

**Rama y entorno**
- Rama `feat/adjudicacion`, en el worktree `.claude/worktrees/feat+incremento-1`, sobre `0220b36`.
- Los comandos de la web se corren desde `web/`.
- Este plan **no cambia ningún servicio**. Si una tarea necesita algo que la API no da, se detiene y lo reporta.

**Contrato con el servicio**
- Los tipos de `web/src/adjudicacion.ts` copian estos esquemas; un campo nuevo en uno va en el otro:
  - `services/negociacion/src/negociacion/api/esquemas.py` (`Evaluacion`, `AdjudicacionSalida`, `Propuesta`, `Aprobacion`, `Rechazo`, `Desierta`);
  - `services/inteligencia/src/inteligencia/api/esquemas.py` (`RecomendacionSalida` y sus partes).
- Rutas, todas con `pedir("/negociacion/…")`:
  - `GET /eventos/{id}/evaluacion` o `GET /eventos/{id}/evaluacion?pesos=40,30,15,15` devuelve `Evaluacion`;
  - `POST /eventos/{id}/adjudicacion`, con `{sesion_id, pesos?, justificacion?}`;
  - `POST /eventos/{id}/adjudicacion/aprobar`, con `{adjudicacion_id}`;
  - `POST /eventos/{id}/adjudicacion/rechazar`, con `{adjudicacion_id, motivo}`;
  - `POST /eventos/{id}/desierta`, con `{motivo}`.
  - Los cuatro POST devuelven `Evaluacion`.
- `pesos` va siempre como el texto `"costo,desempeno,riesgo,sla"`, por ejemplo `"40,30,15,15"`, y nunca como objeto.
- `adjudicacion_id` es siempre el `vigente.id` de la evaluación que se ve en pantalla.
- Errores por `ErrorApi.codigo`:
  - 422: `justificacion_requerida` (campo `justificacion`), `sesion_no_candidata`, `pesos_invalidos`;
  - 409: `estado_invalido`, `propuesta_distinta`, `contrato_vigente_faltante`;
  - 403: `misma_persona`;
  - 503: `dependencia_no_disponible`.
  - El mensaje que se muestra es `error.message`, el texto del servicio.
- Después de cualquier POST se invalida todo con `{ queryKey: ["negociacion"] }`, porque la evaluación y el evento cambian juntos.
- Montos:
  - llegan como texto decimal y se muestran con `formatoMoneda(valor, moneda)`;
  - la web solo los compara para *anticipar* la regla (`superaUmbral`, Task 1). Quien decide es el servicio, y la pantalla muestra lo que respondió.
  - Los pesos son enteros y se suman en la web.
- La evaluación no se consulta periódicamente: solo se recarga al recalcular, tras un POST o con «Reintentar».

**Textos y formato**
- Español de México, de «usted».
- El primer término técnico de cada sección va con `Termino`: adjudicación, umbral de aprobación, desierta, SLA y fuera de límites (Task 8 los agrega al glosario).
- El color nunca es la única señal: la recomendación, el nivel de riesgo, el total de pesos y la regla de aprobación llevan texto, y donde aplica, icono.
- Los textos fijos de este plan se copian tal cual.

**Accesibilidad**
- 0 violaciones de axe en cada sección y diálogo nuevos, en claro y oscuro (`esperarSinViolaciones`).
- En el navegador se revisa con la regla de contraste, a 375, 768, 1024 y 1440 px y sin desplazamiento horizontal (Task 9).
- Un botón que no aplica pero puede tener el foco usa `aria-disabled` y una guarda en su manejador, no `disabled`.
- Mientras un envío está en curso, su botón queda en `aria-disabled` y un segundo clic no manda nada.
- Cuando un botón desaparece al usarse, por ejemplo al adjudicar o al aprobar, el foco pasa a `#contenido`. Use el patrón `onCloseAutoFocus` de `DialogoCancelar`.
- Los avisos de «se adjudicó / se aprobó» van al `<p role="status">` de `Negociacion.tsx`, que siempre está montado.

**Dependencias**
- No se agregan dependencias.

**Seguridad de credenciales**
- Nunca escriba contraseñas, tokens ni enlaces de invitación en comandos, archivos versionados o reportes.
- Las contraseñas de desarrollo están en `infra/keycloak/realm-plataforma.json`; no las repita.
- En la revisión en navegador, la persona inicia sesión sola.
- No haga `git push` ni toque los remotos.

**Calidad**
- Cada tarea deja limpio, desde `web/`: `npm run lint && npm run build && npx vitest run && npx prettier --check "src/**/*.{ts,tsx}"`.
- Las pruebas no dejan warnings: ni `act(...)` ni el `act` de React Query.
- No se editan planes ni bitácoras anteriores.

**Commits**
- Conventional Commits en español.
- El asunto va seguido de una línea en blanco y de `Co-Authored-By: Claude <modelo> 5.5 <noreply@anthropic.com>`, con el modelo real.
- No haga commit de `infra/.env`, `datos/`, `web/node_modules`, `web/dist`, `.superpowers/` ni PDFs.

## Review Focus

1. **El aprobador decide sobre una propuesta que ya cambió**, por ejemplo con otra pestaña u otro aprobador.
   - Se ve el texto del 409 `propuesta_distinta` y la evaluación se recarga sola.
   - No se decide nada, y el diálogo se cierra sin pasar el foco a `<body>`.
   - Prueba (Task 4): `un 409 de propuesta distinta explica, recarga la evaluación y no decide`.
2. **Doble clic en «Confirmar» al adjudicar, aprobar, rechazar o declarar desierta.**
   - Sale una sola petición.
   - El botón queda en `aria-disabled` mientras se envía.
   - Pruebas: Task 3 (`un doble clic en Confirmar manda una sola propuesta`) y Task 4 (`un doble clic en Aprobar manda una sola aprobación`).
3. **Pesos inválidos al recalcular:** vacíos, decimales, negativos, más de 100 o que no suman 100.
   - «Recalcular» no consulta y explica el total.
   - Lo que el servicio rechace (422 `pesos_invalidos`) se muestra junto a los campos.
   - Prueba (Task 2): `pesos que no suman 100 no recalculan y lo explican`.
4. **Roles mezclados.**
   - Quien propuso y también es aprobador no ve «Aprobar» ni «Rechazar», sino el texto de §7.1.
   - Un comprador sin el rol de aprobador ve «Esperando aprobación de un aprobador».
   - El administrador, y el aprobador mientras el evento está en evaluación, ven la evaluación sin «Adjudicar» ni «Declarar desierta».
   - Prueba (Task 4): `cada rol ve solo sus acciones`.
5. **`inteligencia` no responde mientras se evalúa.**
   - La sección «Evaluación» muestra el error con «Reintentar» y la tabla de sesiones sigue a la vista.
   - En «Pendiente de aprobación» la propuesta se ve igual, porque llega la foto guardada.
   - Pruebas: Task 2 (`con inteligencia caída la evaluación ofrece reintentar y las sesiones siguen`) y Task 4 (`la propuesta pendiente se muestra con la foto guardada`).

---

### Task 1: Módulo común de la adjudicación

**Files:**
- Create: `web/src/adjudicacion.ts`
- Test: `web/src/adjudicacion.test.ts`

**Interfaces:**
- Produces:
  - **Tipos.**
    - `Criterio = "costo" | "desempeno" | "riesgo" | "sla"`; `Pesos = Record<Criterio, number>`.
    - `Riesgo = { valor: number; nivel: "bajo" | "medio" | "alto"; concentracion: number; tendencia: number; sin_historial: boolean }`.
    - `Candidato = { id; proveedor_id; nombre; costo_total: string; costo_total_mxn: string; desempeno: number; riesgo: Riesgo; sla: string | null; normalizados: Record<Criterio, number>; aportes: Record<Criterio, number>; puntaje: number; lugar: number }`.
    - `Sensibilidad = { criterio: Criterio; peso_actual: number; peso_necesario: number | null; ganaria: string | null }`.
    - `Recomendacion = { pesos: Pesos; umbral_aprobacion: string; tipo_cambio: { periodo: string; usd_mxn: string } | null; candidatos: Candidato[]; recomendado: string; margen: number; explicacion: string[]; sensibilidad: Sensibilidad[] }`.
    - `MotivoAprobacion = "umbral" | "fuera_de_limites"`.
    - `Adjudicacion`, con los campos de `AdjudicacionSalida`:
      - `id`, `sesion_id`, `propuesta_por_id`, `propuesta_por_nombre`, `propuesta_en`, `recomendada_sesion_id`, `se_aparta`, `justificacion`;
      - `costo_total`, `costo_total_mxn`, `requiere_aprobacion`, `motivo_aprobacion: MotivoAprobacion[]`, `recomendacion: Recomendacion`;
      - `estado: "pendiente" | "aprobada" | "rechazada" | "directa"`;
      - `decidida_por_nombre`, `decidida_en`, `motivo_rechazo`, `contrato_folio`.
    - `Evaluacion = { recomendacion: Recomendacion | null; vigente: Adjudicacion | null; historial: Adjudicacion[] }`.
  - **Constantes.**
    - `PESOS_POR_OMISION: Pesos = { costo: 40, desempeno: 30, riesgo: 15, sla: 15 }`.
    - `NOMBRES_CRITERIO = { costo: "Costo total", desempeno: "Desempeño", riesgo: "Riesgo", sla: "SLA" }`.
    - `NOMBRES_NIVEL_RIESGO = { bajo: "Bajo", medio: "Medio", alto: "Alto" }`.
    - `NOMBRES_MOTIVO = { umbral: "Supera el umbral de aprobación", fuera_de_limites: "Fuera de límites" }`.
    - `TEXTOS_RESULTADO`, que copia `services/negociacion/src/negociacion/correo.py:18-20` tal cual:
      - `adjudicada`: «Su oferta fue adjudicada; el equipo de compras se pondrá en contacto»;
      - `no_elegida`: «La negociación se adjudicó a otra propuesta»;
      - `desierta`: «La negociación se declaró desierta».
  - **Funciones.**
    - `textoPesos(p: Pesos): string` devuelve `"40,30,15,15"`, en el orden costo, desempeño, riesgo y SLA.
    - `totalPesos(campos: Record<Criterio, string>): number`. Un campo vacío o no entero cuenta 0.
    - `pesosValidos(campos: Record<Criterio, string>): Pesos | null` devuelve null si algún campo no es un entero de 0 a 100 o si la suma no es 100.
    - `superaUmbral(costoMxn: string, umbral: string): boolean` compara con `>` estricto, como el servicio.
      - Solo sirve para anticipar el texto de la confirmación.
      - Comentario `ponytail:` con su techo: `Number` es exacto para montos con 2 decimales hasta unos 9e13.
    - `razonesAprobacion(costoMxn: string, umbral: string, fueraDeLimites: boolean): MotivoAprobacion[]` aplica la regla de la spec §4.3, en ese orden.
    - `useEvaluacion(eventoId: string, pesos: Pesos | null)` llama a `useNegociacion<Evaluacion>(`/eventos/${id}/evaluacion` + (pesos ? `?pesos=${textoPesos(pesos)}` : ""))`.

- [ ] **Step 1: Escriba las pruebas que fallan**

```ts
it("textoPesos respeta el orden del servicio", () => {
  expect(textoPesos({ costo: 40, desempeno: 30, riesgo: 15, sla: 15 })).toBe("40,30,15,15")
})
it("pesosValidos exige enteros de 0 a 100 que sumen 100", () => {
  expect(pesosValidos({ costo: "40", desempeno: "30", riesgo: "15", sla: "15" })).toEqual(PESOS_POR_OMISION)
  for (const malo of ["", "-1", "10.5", "101", "abc"])
    expect(pesosValidos({ costo: malo, desempeno: "30", riesgo: "15", sla: "15" })).toBeNull()
  expect(pesosValidos({ costo: "40", desempeno: "30", riesgo: "15", sla: "10" })).toBeNull()
})
it("superaUmbral es estricto como el servicio", () => {
  expect(superaUmbral("500000.00", "500000.00")).toBe(false)
  expect(superaUmbral("500000.01", "500000.00")).toBe(true)
})
it("razonesAprobacion junta el umbral y los límites", () => {
  expect(razonesAprobacion("600000.00", "500000.00", true)).toEqual(["umbral", "fuera_de_limites"])
  expect(razonesAprobacion("1.00", "500000.00", false)).toEqual([])
})
it("los textos del resultado son los del correo", () => {
  expect(TEXTOS_RESULTADO.no_elegida).toBe("La negociación se adjudicó a otra propuesta")
})
```

- [ ] **Step 2:** Run: `npx vitest run src/adjudicacion.test.ts`. Expected: FAIL (el módulo no existe).
- [ ] **Step 3: Implemente `web/src/adjudicacion.ts`.**
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): tipos y reglas de la adjudicación`

---

### Task 2: Sección «Evaluación» (lectura y pesos)

**Files:**
- Create:
  - `web/src/componentes/adjudicacion/TablaCandidatos.tsx`;
  - `Explicacion.tsx`;
  - `AjustarPesos.tsx`;
  - `SeccionEvaluacion.tsx`.
- Modify: `web/src/paginas/Negociacion.tsx` (la sección va antes de `TablaSesiones` cuando `evento.estado === "en_evaluacion"`).
- Test: `web/src/componentes/adjudicacion/SeccionEvaluacion.test.tsx`

**Interfaces:**
- Consumes: Task 1, más `Evento` y `SesionResumen` de `web/src/negociacion.ts`. `SesionResumen.fuera_de_limites` se obtiene por `sesion.id`, que es el `id` del candidato.
- Produces:
  - `TablaCandidatos({ recomendacion, evento, destacada?, accion? })`.
    - Columnas: Proveedor, Costo total, Desempeño, Riesgo, SLA, Puntaje y Lugar.
    - Si `evento.moneda === "USD"`, el costo lleva debajo «≈ {formatoMoneda(costo_total_mxn, "MXN")}».
    - El riesgo muestra su nivel, y su detalle lista los tres componentes como porcentaje entero: «Concentración», «Tendencia de incidentes» y «Sin historial: sí/no».
    - El SLA nulo se muestra «—».
    - El recomendado lleva un `Badge` con icono y el texto «Recomendado».
    - Una fila marcada como fuera de límites lleva «Fuera de límites».
    - `destacada` es el id de la sesión de una propuesta: su fila lleva «Propuesta».
    - `accion(candidato)` dibuja la celda final; la usa la Task 3.
  - `Explicacion({ recomendacion })` muestra un `<p>` por frase de `explicacion`.
  - `AjustarPesos({ pesos, alRecalcular(p: Pesos) })`.
    - Usa `CampoNumero` y el total en vivo, como `FormularioPuntuacion`.
    - Si los pesos no son válidos, dice «Los pesos deben sumar 100; ahora suman N.» y no recalcula.
    - El botón dice «Recalcular».
  - `SeccionEvaluacion({ evento })`.
    - Título «Evaluación».
    - Guarda los pesos elegidos (`Pesos | null`) en su estado y los pasa a `useEvaluacion`.
    - Con `recomendacion: null`, dice «No hay acuerdos tentativos para evaluar.».
    - La Task 3 le agrega las acciones.

- [ ] **Step 1: Escriba las pruebas que fallan** (con `simularRutas` y `renderizarPagina`, como las de `Negociacion.test.tsx`)

```tsx
it("muestra los candidatos en orden, con el recomendado marcado con texto", async () => { /* filas en orden de lugar; getByText("Recomendado") en la fila del recomendado */ })
it("en USD el costo lleva su equivalente en MXN", async () => {})
it("el riesgo muestra su nivel y sus componentes", async () => {})
it("la explicación se lee como texto", async () => {})
it("recalcular pide la evaluación con los pesos como texto", async () => { /* llamadaA(".../evaluacion?pesos=25,25,25,25") */ })
it("pesos que no suman 100 no recalculan y lo explican", async () => { /* ninguna llamada nueva; «ahora suman 90» */ })
it("un 422 de pesos se muestra junto a los campos", async () => {})
it("con inteligencia caída la evaluación ofrece reintentar y las sesiones siguen", async () => { /* 503 → EstadoError con «Reintentar»; la tabla de sesiones sigue */ })
it("sin acuerdos dice que no hay qué evaluar", async () => {})
it("no tiene violaciones de axe en claro ni en oscuro", async () => {})
```

- [ ] **Step 2:** Run: `npx vitest run src/componentes/adjudicacion`. Expected: FAIL.
- [ ] **Step 3: Implemente los cuatro componentes y la conexión en `Negociacion.tsx`.** La sección se muestra a los roles que pueden leer el evento; las acciones son de la Task 3.
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): evaluación de los acuerdos con su explicación y pesos ajustables`

---

### Task 3: Adjudicar y declarar desierta (comprador)

**Files:**
- Create:
  - `web/src/componentes/adjudicacion/DialogoAdjudicar.tsx`;
  - `DialogoDesierta.tsx`.
- Modify:
  - `SeccionEvaluacion.tsx` («Adjudicar» en cada fila y «Declarar desierta», solo para quien tiene el rol `comprador`);
  - `Negociacion.tsx` (los avisos).
- Test: `web/src/componentes/adjudicacion/DialogoAdjudicar.test.tsx`

**Interfaces:**
- Consumes: Tasks 1 y 2. `useRoles()` de `@/auth`.
- Produces:
  - `DialogoAdjudicar({ evento, candidato, recomendacion, alAdjudicar(resultado: Evaluacion) })`.
    - Manda `recomendacion.pesos`, los de la evaluación que se ve. Así el servicio recalcula con los mismos pesos.
    - Título: «Adjudicar a {nombre}».
    - Antes de confirmar, la regla anticipada con `razonesAprobacion`:
      - sin razones: «Se adjudicará directamente: el costo total ({MXN}) no supera el umbral de aprobación ({umbral}) y el acuerdo está dentro de sus límites.»;
      - con razones: «Irá a un aprobador porque » seguido de las razones unidas con « y »:
        - «el costo total ({MXN}) supera el umbral de aprobación ({umbral})»;
        - «el acuerdo está fuera de sus límites».
    - Si `candidato.id !== recomendacion.recomendado`, el campo «Justificación» es obligatorio. Su ayuda dice «Explique por qué se aparta de la recomendación (de 10 a 1,000 caracteres).». Si es el recomendado, el campo no se muestra.
    - El botón dice «Confirmar».
    - Hace `POST /eventos/{id}/adjudicacion` con `{ sesion_id: candidato.id, pesos: textoPesos(recomendacion.pesos), justificacion? }`.
    - Errores:
      - el 422 `justificacion_requerida` va junto al campo;
      - el 409 y el 503 muestran el texto del servicio en el diálogo.
    - Al terminar avisa según `resultado.vigente.estado`:
      - `directa`: «Se adjudicó la negociación a {nombre}.»;
      - `pendiente`: «Se envió la propuesta a un aprobador.».
  - `DialogoDesierta({ evento, alDeclarar })`.
    - Título: «Declarar desierta la negociación». Campo «Motivo», de 1 a 500 caracteres.
    - Hace `POST /eventos/{id}/desierta`.
    - Avisa «Se declaró desierta la negociación.».

- [ ] **Step 1: Escriba las pruebas que fallan**

```tsx
it("anticipa la adjudicación directa con el costo y el umbral", async () => {})
it("anticipa el aprobador por el umbral, por los límites o por los dos", async () => {})
it("pide la justificación solo si no es el recomendado", async () => {})
it("manda la sesión, los pesos como texto y la justificación", async () => { /* cuerpo exacto */ })
it("un 422 de justificación queda junto al campo", async () => {})
it("un doble clic en Confirmar manda una sola propuesta", async () => {})
it("al adjudicar avisa y el foco pasa al contenido", async () => {})
it("declarar desierta manda el motivo y avisa", async () => {})
it("quien no es comprador no ve Adjudicar ni Declarar desierta", async () => {})
it("no tiene violaciones de axe con el diálogo abierto", async () => {})
```

- [ ] **Step 2:** Run: `npx vitest run src/componentes/adjudicacion`. Expected: FAIL.
- [ ] **Step 3: Implemente los dos diálogos con el patrón de `DialogoCancelar`.** Use `useMutation`, `onCloseAutoFocus` hacia `#contenido` y la invalidación de `["negociacion"]`.
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): adjudicar o declarar desierta desde la evaluación`

---

### Task 4: Pendiente de aprobación (comprador y aprobador)

**Files:**
- Create:
  - `web/src/componentes/adjudicacion/SeccionAprobacion.tsx`;
  - `DialogoRechazar.tsx`.
- Modify: `Negociacion.tsx` (en `pendiente_aprobacion` muestra `SeccionAprobacion` antes de las sesiones).
- Test: `web/src/componentes/adjudicacion/SeccionAprobacion.test.tsx`

**Interfaces:**
- Consumes: Tasks 1 y 2. `useUsuarioId()` y `useRoles()` de `@/auth`.
- Produces: `SeccionAprobacion({ evento })`.
  - Lee `useEvaluacion(evento.id, null)`. Fuera de evaluación, el servicio devuelve la foto: no mande `pesos` aquí.
  - Muestra:
    - `TablaCandidatos` con `vigente.recomendacion` y `destacada = vigente.sesion_id`;
    - `Explicacion`;
    - «Propuesta de {propuesta_por_nombre}, {formatoFechaHora(propuesta_en)}»;
    - la justificación, si la hay;
    - el motivo de la regla, con `NOMBRES_MOTIVO` de cada `motivo_aprobacion`.
  - Acciones según la persona:
    - `useUsuarioId() === vigente.propuesta_por_id`: «Usted propuso esta adjudicación; la aprueba otra persona.», sin botones;
    - otra persona con el rol `aprobador`: «Aprobar» y «Rechazar»;
    - otra persona sin ese rol: «Esperando aprobación de un aprobador.».
  - «Aprobar»:
    - hace `POST …/adjudicacion/aprobar` con `{ adjudicacion_id: vigente.id }`;
    - avisa «Se aprobó la adjudicación.».
  - «Rechazar»:
    - abre `DialogoRechazar`, con el campo «Motivo del rechazo», de 1 a 500 caracteres;
    - hace `POST …/rechazar` con `{ adjudicacion_id: vigente.id, motivo }`;
    - avisa «Se rechazó la propuesta; la negociación vuelve a evaluación.».
  - Un 409 `propuesta_distinta` muestra el texto del servicio, invalida `["negociacion"]` y cierra el diálogo, sin decidir nada.

- [ ] **Step 1: Escriba las pruebas que fallan**

```tsx
it("la propuesta pendiente se muestra con la foto guardada", async () => { /* la GET sin ?pesos; la fila propuesta marcada «Propuesta» */ })
it("cada rol ve solo sus acciones", async () => { /* aprobador ajeno: botones; quien propuso con los dos roles: el texto; comprador: «Esperando…»; admin: «Esperando…» */ })
it("aprobar manda el id de la propuesta vista", async () => { /* cuerpo exacto {adjudicacion_id: vigente.id} */ })
it("rechazar exige el motivo y manda el id de la propuesta vista", async () => {})
it("un 409 de propuesta distinta explica, recarga la evaluación y no decide", async () => {})
it("un doble clic en Aprobar manda una sola aprobación", async () => {})
it("al aprobar avisa y el foco pasa al contenido", async () => {})
it("no tiene violaciones de axe en claro ni en oscuro", async () => {})
```

- [ ] **Step 2:** Run: `npx vitest run src/componentes/adjudicacion`. Expected: FAIL.
- [ ] **Step 3: Implemente `SeccionAprobacion` y `DialogoRechazar`.**
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): aprobar o rechazar la propuesta de adjudicación`

---

### Task 5: Resumen de la adjudicada o la desierta

**Files:**
- Create: `web/src/componentes/adjudicacion/ResumenAdjudicacion.tsx`
- Modify: `Negociacion.tsx` (en `adjudicado` y `desierto`, el resumen va antes de las sesiones).
- Test: `web/src/componentes/adjudicacion/ResumenAdjudicacion.test.tsx`

**Interfaces:**
- Consumes: Task 1; `Evento.motivo_desierta` (ya está en `web/src/negociacion.ts`).
- Produces: `ResumenAdjudicacion({ evento })`. Lee `useEvaluacion(evento.id, null)`.
  - **`adjudicado`.** Una lista de definición:
    - «Proveedor»: el nombre del candidato de `vigente.sesion_id` en `vigente.recomendacion`;
    - «Costo total»: `formatoMoneda(vigente.costo_total, evento.moneda)`, con el equivalente en MXN si es USD;
    - «Propuso»: nombre y fecha;
    - «Aprobó»: nombre y fecha, o «Adjudicación directa del comprador» si `estado === "directa"`;
    - «Folio del contrato»: `contrato_folio`, en `font-mono`.
  - **`desierto`.**
    - «La negociación se declaró desierta.»;
    - después, «Motivo: {motivo_desierta}», o si es nulo, «Ningún proveedor llegó a un acuerdo tentativo.».
  - **En los dos.** Si `historial` no está vacío, una lista «Propuestas rechazadas» con:
    - proveedor, quién la propuso y cuándo;
    - quién la rechazó y su motivo.

- [ ] **Step 1: Escriba las pruebas que fallan**

```tsx
it("la adjudicada aprobada dice quién propuso, quién aprobó y el folio", async () => {})
it("la directa dice que la adjudicó el comprador", async () => {})
it("la desierta automática explica que no hubo acuerdos", async () => {})
it("la desierta manual muestra el motivo", async () => {})
it("lista las propuestas rechazadas con su motivo", async () => {})
it("no tiene violaciones de axe", async () => {})
```

- [ ] **Step 2:** Run: `npx vitest run src/componentes/adjudicacion`. Expected: FAIL.
- [ ] **Step 3: Implemente el resumen.**
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): resumen de la negociación adjudicada o desierta`

---

### Task 6: Filtros de Negociaciones y aviso del portal

**Files:**
- Modify:
  - `web/src/paginas/Negociaciones.tsx`;
  - `web/src/negociacion.ts` (`NOMBRES_FILTRO_ESTADO`);
  - `web/src/paginas/Portal.tsx`.
- Test: `web/src/paginas/Negociaciones.test.tsx`, `web/src/paginas/Portal.test.tsx`

**Interfaces:**
- Consumes: Task 1 (`TEXTOS_RESULTADO`); `VistaPortal.resultado`, ya en `web/src/negociacion.ts`.
- Produces:
  - **`NOMBRES_FILTRO_ESTADO: Record<EstadoEvento, string>`.** Es igual a `NOMBRES_ESTADO_EVENTO` salvo `pendiente_aprobacion`, que dice «Por aprobar». Los chips de filtro lo usan y las etiquetas siguen con `NOMBRES_ESTADO_EVENTO`.
  - **El aprobador entra con «Por aprobar» si hay alguna (spec §7.2).**
    - Aplica cuando la persona tiene el rol `aprobador` y la URL no trae `estado`.
    - Se consulta una vez `/eventos?estado=pendiente_aprobacion&pagina=1&tamano=1`. Si `total > 0`, se fija `estado=pendiente_aprobacion` en la URL con `replace`, sin agregar historial.
    - Elegir «Todas» después lo respeta: la redirección corre solo al montar.
  - **Portal.**
    - Con `vista.resultado` distinto de null, muestra un aviso con el texto de `TEXTOS_RESULTADO[resultado]`.
    - Va en un elemento con `role="status"`, ya montado, en lugar del texto de «acuerdo tentativo».
    - No muestra nombres de otros proveedores ni montos ajenos.

- [ ] **Step 1: Escriba las pruebas que fallan**

```tsx
it("los filtros nuevos dicen Por aprobar, Adjudicada y Desierta", async () => {})
it("el aprobador entra con Por aprobar si hay alguna", async () => { /* ubicacionActual() incluye estado=pendiente_aprobacion */ })
it("sin propuestas pendientes el aprobador ve todas", async () => {})
it("quien no es aprobador no es redirigido", async () => {})
it("el portal muestra el resultado de la negociación", async () => { /* los tres resultados */ })
it("sin resultado el portal no muestra el aviso", async () => {})
```

- [ ] **Step 2:** Run: `npx vitest run src/paginas/Negociaciones.test.tsx src/paginas/Portal.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implemente.**
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): filtros de aprobación y el resultado en el portal`

---

### Task 7: Configuración «Adjudicación»

**Files:**
- Create: `web/src/componentes/FormularioAdjudicacion.tsx`
- Modify:
  - `web/src/inteligencia.ts` (`ConfiguracionInteligencia` gana `adjudicacion_costo`, `adjudicacion_desempeno`, `adjudicacion_riesgo`, `adjudicacion_sla: number` y `umbral_aprobacion: string`);
  - `web/src/paginas/Configuracion.tsx` (la sección nueva, después de la puntuación).
- Test: `web/src/componentes/FormularioAdjudicacion.test.tsx`

**Interfaces:**
- Consumes: `useInteligencia("/configuracion")`; `PUT /inteligencia/configuracion`.
  - El cuerpo exige los campos de la puntuación (`ConfiguracionEntrada`, `extra="forbid"`).
- Produces: `FormularioAdjudicacion({ inicial })`.
  - Una `Seccion` titulada «Adjudicación».
  - Cuatro pesos con las etiquetas de `NOMBRES_CRITERIO` y el total en vivo, con las mismas reglas y textos que la puntuación.
  - «Umbral de aprobación (MXN)», de 0 en adelante y 2 decimales, con la ayuda «Una adjudicación con un costo total mayor necesita un aprobador.».
  - El PUT manda:
    - los valores guardados de la puntuación (`inicial.peso_*`, `umbral_riesgo` e `inflacion_anual`), sin cambiarlos;
    - los cuatro `adjudicacion_*` como enteros;
    - `umbral_aprobacion` como texto.
  - Un 422 `pesos_invalidos` en `pesos_adjudicacion` va junto al total.
  - Al guardar, invalida `["inteligencia"]`, igual que la puntuación.

- [ ] **Step 1: Escriba las pruebas que fallan**

```tsx
it("muestra los pesos y el umbral guardados", async () => {})
it("guardar manda la puntuación sin cambios y la adjudicación nueva", async () => { /* cuerpo exacto del PUT */ })
it("pesos que no suman 100 no se envían", async () => {})
it("un 422 de pesos de adjudicación se muestra junto al total", async () => {})
it("no tiene violaciones de axe", async () => {})
```

- [ ] **Step 2:** Run: `npx vitest run src/componentes/FormularioAdjudicacion.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implemente.** Si `CampoNumero` sigue privado en `FormularioPuntuacion.tsx`, muévalo a `web/src/componentes/CampoNumero.tsx` e impórtelo en los dos formularios, en vez de copiarlo.
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(web): pesos de la adjudicación y umbral de aprobación en Configuración`

---

### Task 8: Ayuda, glosario y textos

**Files:**
- Modify:
  - `web/src/glosario.ts` (términos `adjudicacion`, `umbral_aprobacion`, `desierta` y, si no existe, `fuera_de_limites`);
  - `web/src/ayuda.ts` (el artículo «Adjudicar y aprobar», con slug `adjudicar-y-aprobar`, y el texto de `ayuda.ts:74`);
  - `web/src/paginas/Correos.tsx:127`;
  - las secciones de las Tasks 2 a 5 (`Termino` en el primer término técnico).
- Test: `web/src/ayuda.test.ts`, `web/src/paginas/Correos.test.tsx` y las pruebas de las secciones.

**Interfaces:**
- Produces:
  - **Glosario**, en una o dos frases sin jerga:
    - **adjudicación:** elegir el acuerdo que se convierte en contrato;
    - **umbral de aprobación:** el costo total en MXN a partir del cual decide un aprobador; por defecto, 500,000;
    - **desierta:** la negociación termina sin adjudicar.
  - **El artículo «Adjudicar y aprobar»** explica:
    - la evaluación y los pesos;
    - adjudicar, la justificación y la regla del aprobador;
    - aprobar y rechazar (quien propone no aprueba);
    - declarar desierta y el aviso a los proveedores.
  - **`ayuda.ts:74`:** el párrafo de «Cómo usar PluriOne» deja de decir «La aprobación de cada cierre llegará en una próxima versión.». Ahora describe la adjudicación con su aprobación.
  - **`Correos.tsx:127`:** la descripción dice «Invitaciones, restablecimientos de contraseña, invitaciones a negociar y sus resultados que envió la plataforma, y si salieron bien.».

- [ ] **Step 1: Escriba las pruebas que fallan**

```ts
it("el artículo Adjudicar y aprobar existe y se encuentra al buscar", () => { /* buscar("aprobador") lo incluye */ })
it("Cómo usar PluriOne ya no promete la aprobación para después", () => {})
it("los términos nuevos están en el glosario", () => {})
it("la descripción de Correos menciona los resultados", async () => {})
```

- [ ] **Step 2:** Run: `npx vitest run src/ayuda.test.ts src/paginas/Correos.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implemente.**
- [ ] **Step 4:** Corra la puerta de calidad. Expected: PASS.
- [ ] **Step 5: Commit:** `docs(web): ayuda y glosario de la adjudicación`

---

### Task 9: Revisión en navegador y cierre

La hace el controlador en el navegador integrado, como en N1b, con el stack levantado: `uv run python infra/arrancar.py`, que no borra nada.
- La persona inicia sesión sola con cada usuario: `comprador1`, `aprobador1` y `admin1`.
- Los datos se preparan con la API, como en la prueba de humo: una negociación con dos acuerdos tentativos y otra sin acuerdos.

**Files:**
- Create: `docs/qa/revision-adjudicacion.md`, con lo revisado, lo encontrado y lo corregido, como `docs/qa/revision-negociacion.md`.
- Modify:
  - `README.md`: las capacidades 7 y 9 a «Hecho», y quitar lo de 4′b de «Qué falta», «Lo siguiente» y «Limitaciones conocidas»;
  - `docs/arquitectura/c4.md:25` (quitar «(por la API hasta 4′b)»);
  - `docs/arquitectura/adr/011-quien-aprueba-una-adjudicacion.md` (la pantalla ya existe).

- [ ] **Step 1: Recorra los flujos, cada uno a 375, 768, 1024 y 1440 px, en claro y oscuro.**
  - El comprador evalúa, recalcula y adjudica:
    - el recomendado, directo;
    - otro, con justificación, que queda pendiente.
  - El aprobador entra con «Por aprobar», abre la propuesta y:
    - rechaza; el comprador vuelve a proponer;
    - aprueba.
  - Con los dos roles, quien propuso ve el texto y no los botones.
  - El comprador declara desierta otra negociación.
  - Se ven el resumen adjudicado (con el folio del contrato) y el desierto.
  - El portal muestra el resultado mientras el enlace sigue vigente.
  - El administrador cambia los pesos y el umbral en Configuración; la Actividad lo muestra legible.
- [ ] **Step 2: Corra axe con la regla de contraste en cada vista nueva.** Expected: 0 violaciones, y sin desplazamiento horizontal.
- [ ] **Step 3: Corrija lo encontrado.** Cada defecto lleva su prueba, si se puede escribir en jsdom, y su commit `fix(web): …`.
- [ ] **Step 4: Escriba `docs/qa/revision-adjudicacion.md` y actualice el README, la C4 y la ADR.**
- [ ] **Step 5:** Corra la puerta de calidad completa: la de la web y `uv run pytest libs/comun services tools -q`. Expected: PASS.
- [ ] **Step 6: Commit:** `docs: revisión en navegador de la adjudicación y capacidades 7 y 9 hechas`
