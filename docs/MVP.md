# MVP: alcance vigente

Actualizado al 22/10/2026. Parte de las 10 capacidades del [PRD](PRD.md) y aplica dos recortes:
la replanificación del 15/10/2026 (PRD §6.6.1, [ADR-010](arquitectura/adr/010-negociacion-determinista-antes-del-llm.md))
y la decisión sobre el LLM del 22/10/2026 (PRD §6.6.2). El estado detallado de cada capacidad
está en el [README](../README.md#qué-está-hecho-y-qué-falta).

## Qué entra

| # | Capacidad | Prioridad | Estado |
|---|---|---|---|
| 1 | Proveedores, contratos e historial | Must | Hecho |
| 2 | Inteligencia de precios | Must (línea base), Should (modelo) | Hecho |
| 3 | Desempeño del proveedor | Must | Hecho |
| 4 | Eventos de negociación | Must | Hecho |
| 5 | Negociación con agente en el portal | Must con el agente determinista; el LLM, Should | Hecho el agente determinista; el LLM, del 29/10 al 04/11 (abajo) |
| 7 | Recomendación de adjudicación | Must | Hecho |
| 9 | Aprobaciones y bitácora | Must | Hecho |
| 10 | Tablero | Should | Hecho: incluye el estado de las negociaciones y el ahorro logrado frente a la primera oferta |

## Qué no entra

- **Propuestas de negociación (6) y simulador de escenarios (8).** No caben en el calendario de
  abajo y quedan como trabajo futuro.
- Lo que el PRD ya dejaba fuera de v1 (§1.4): ERP y correo reales, varias empresas, firma
  electrónica, búsqueda en PDF de contratos, app móvil, Power BI e idiomas distintos al español.

## El recorte del 15/10/2026

El asesor revisó el código y señaló que la negociación, que da nombre al proyecto, todavía no
existía, y que el plan de 16 a 18 semanas no cabía. Se decidió:

- construir la negociación sin LLM (N1): motor de concesiones, portal del proveedor, supervisión
  y simulación con bots;
- después, la adjudicación con aprobación (4′), y no pulir pantallas mientras faltara el flujo
  completo;
- el LLM (N2), las propuestas y el simulador, solo si sobraba tiempo.

N1 se integró el 15/10 y 4′ el 20/10, antes de lo previsto: el flujo de evento a negociación,
recomendación, aprobación y contrato registrado ya funciona.

## La decisión sobre el LLM (22/10/2026)

El residente decidió que **el LLM entra, recortado y con fecha límite**:

- **Qué hace:** interpreta la nota libre del proveedor para sugerir los campos de su oferta, que
  el proveedor confirma, y redacta los mensajes del agente. El motor sigue decidiendo.
- **Cuándo:** del 29/10 al 04/11/2026.
- **Cómo se acepta:** con los evals del PRD (§4.8) y las metas de §1.6: 90 % o más de campos
  interpretados bien, 0 filtraciones del límite o de los pesos ante los ataques, y respuesta del
  agente en menos de 20 s en el percentil 95.
- **Si no se cumplen el 04/11:** el agente se queda con las plantillas, el LLM queda como
  trabajo futuro en el PRD y el 05/11 empieza el manual de usuario.
- **Límite del equipo:** la GPU de desarrollo tiene 4 GB, así que solo caben modelos locales de
  unos 3 mil millones de parámetros, cuantizados.

## Recorrido de demostración (5 minutos)

Recorre el flujo completo del MVP: una compra que negocia el agente, la adjudica el comprador,
la aprueba otra persona y termina en un contrato.

Se hizo el 24/10/2026 sobre el stack de `main` y tomó unos 4 minutos, sin contar el cambio de
usuario. Las cifras de abajo son las de esa corrida. Con otra fecha, la referencia de precios
puede variar unos centavos.

**Antes de empezar:**
- Levante el stack con `uv run python infra/arrancar.py` y abra <http://localhost:8080>.
- Los usuarios `comprador1` y `aprobador1` y sus contraseñas están en
  `infra/keycloak/realm-plataforma.json`.
- El proveedor no tiene cuenta. Entra con el enlace de su invitación, que se abre en una ventana
  privada o desde el correo que llega a Mailpit (<http://localhost:8025>).

| Paso | Quién | Qué hace | Qué se ve |
|---|---|---|---|
| 1 | `comprador1` | Entra. El Tablero ya muestra el gasto, los vencimientos y la fila de negociaciones con el ahorro logrado | El Tablero |
| 2 | `comprador1` | Va a Negociaciones y pulsa «Nueva negociación». Escribe un título y elige el servicio «Desarrollador(a) senior (MXN)» con cantidad 800 y al proveedor «Código del Pacífico S.A. de C.V.». Deja la fecha límite, las 6 rondas, el estilo «Balanceado» y el plazo de 12 meses que vienen por defecto. Pulsa «Crear borrador» | El borrador, con la banda de referencia: P25 $1,243.07 · P50 $1,325.80 · P75 $1,449.72 por hora |
| 3 | `comprador1` | Revisa los límites sugeridos (ideal $1,243.07 y límite $1,325.80, del P25 y el P50), pulsa «Publicar» y confirma. Copia el enlace con «Copiar» | «Enlace de invitación»: se muestra una sola vez y también se envía por correo |
| 4 | Proveedor | Abre el enlace en una ventana privada. Ofrece $1,500 por hora y pulsa «Enviar oferta» | El agente responde al momento con una contraoferta de $1,247.25, sin revelar el límite |
| 5 | Proveedor | Pulsa «Aceptar esta propuesta», que llena el formulario, y después «Enviar oferta» | «La negociación terminó con un acuerdo tentativo», que no es vinculante hasta que se apruebe |
| 6 | `comprador1` | Vuelve a la negociación, que ya está «En evaluación». Lee «Por qué se recomienda» y pulsa «Adjudicar a Código del Pacífico S.A. de C.V.» | La confirmación avisa que irá a un aprobador porque el costo total ($997,800.00) supera el umbral de $500,000.00 |
| 7 | `comprador1` | Pulsa «Confirmar» y cierra sesión, en el menú de su cuenta, abajo a la izquierda | La negociación queda «Pendiente de aprobación» |
| 8 | `aprobador1` | Entra. En el Tablero, la fila de negociaciones marca «Por aprobar 1»; pulsa ese número y abre la negociación | La propuesta de `comprador1`, el motivo («Supera el umbral de aprobación») y los botones «Aprobar» y «Rechazar». Quien propone nunca ve esos botones |
| 9 | `aprobador1` | Pulsa «Aprobar» | La negociación queda «Adjudicada». El «Resultado» muestra quién propuso, quién aprobó y el folio del contrato `C-NEG-…` |
| 10 | `aprobador1` | Vuelve al Tablero | El ahorro logrado sube unos $202,200: es (1,500 − 1,247.25) × 800 frente a la primera oferta. El contrato ya está en el historial del proveedor |

**Qué conviene mirar en el camino:**
- El agente nunca acepta fuera de los límites ni los revela.
- Cada respuesta del agente tiene «¿Por qué respondió esto?» en la sesión del comprador.
- El proveedor puede pulsar «Hablar con una persona» en cualquier momento.

## Calendario

El calendario completo hasta el 07/12, con el backlog y los riesgos, está en el
[plan del proyecto](plan-del-proyecto.md).

| Fechas | Trabajo |
|---|---|
| 22/10 – 28/10 | Atender las revisiones del asesor del 22/10 y del 23/10. Ya hecho: este documento y el PRD corto, el uso de IA en el README, la prueba de arranque desde cero, el Tablero (10), las vulnerabilidades de npm y el plan del proyecto (entregable 4). Falta: el recorrido de demostración y el contador de sesiones escaladas en el Tablero |
| 29/10 – 04/11 | El LLM recortado (N2) |
| 05/11 – 11/11 | Imágenes en GitHub Container Registry, sistema funcional (entregable 5) e inicio del manual de usuario |
| 12/11 – 07/12 | Reporte QA (6), manuales (7), plan de mantenimiento (8), capacitación (9) e informe final (10) |
