# Plan del proyecto

Entregable 4 del cronograma. Actualizado al 26/10/2026.

Junta en un solo lugar:
- lo hecho, por incremento y con sus fechas reales;
- el calendario que queda;
- el backlog;
- el registro de riesgos.

El alcance vigente está en [`MVP.md`](MVP.md) y el detalle de cada capacidad, en el
[README](../README.md#qué-está-hecho-y-qué-falta).

## Cómo se trabaja

El trabajo va por **incrementos**, no por sprints formales (decisión del residente, 22/10/2026).
Cada incremento sigue el mismo ciclo, descrito en el README («Cómo se trabajó con IA»):

1. Una spec en `docs/superpowers/specs/`, aprobada por el residente.
2. Un plan en `docs/superpowers/plans/`, también aprobado.
3. La implementación con pruebas primero y revisión independiente.
4. La revisión en el navegador, en `docs/qa/`.
5. La integración a `main` y el push a GitHub.

Desde el 22/10 el trabajo se sube a GitHub cada día.

El avance se sigue en tres lugares:
- la tabla «Qué está hecho y qué falta» del README;
- los reportes mensuales de residencia (125 horas por periodo);
- las revisiones periódicas del asesor sobre lo publicado en GitHub, desde el 14/10.

## Lo hecho

| Incremento | Fechas | Qué produjo | Spec y plan |
|---|---|---|---|
| 0. Inducción y requerimientos | 31/08 – 28/09 | Cursos de inducción y el PRD | [PRD](superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md) |
| 1. Esqueleto y proveedores | 29/09 – 30/09 | Monorepo, `libs/comun`, CI, generador de datos, servicio `proveedores` con importación por CSV | [plan](superpowers/plans/2026-09-29-incremento-1-esqueleto-y-proveedores.md) |
| Plan A. Sistema de diseño | 01/10 | Tema claro y oscuro, accesibilidad WCAG 2.2 AA, pantallas base | [spec](superpowers/specs/2026-10-01-experiencia-e-inteligencia-design.md), [plan](superpowers/plans/2026-10-01-plan-a-sistema-de-diseno-y-experiencia.md) |
| Administración | 07/10 – 10/10 | Usuarios y roles con Keycloak, bitácora de Actividad, Correos, Estado del sistema y Panel | [spec](superpowers/specs/2026-10-08-gestion-administracion-design.md), [plan](superpowers/plans/2026-10-09-operacion-del-sistema.md) |
| 2. Inteligencia | 10/10 – 13/10 | Precio justo (MAPE de 8.3 %), puntuación de proveedores (Spearman de 0.923), alertas y Tablero | [spec](superpowers/specs/2026-10-10-servicio-inteligencia-design.md), [plan](superpowers/plans/2026-10-12-inteligencia-interfaz.md) |
| 3 (N1). Negociación determinista | 13/10 – 15/10 | Motor de concesiones, portal del proveedor, supervisión; con bots: 81.1 % de acuerdos, 16.5 % de ahorro y 0 fuera de límites | [spec](superpowers/specs/2026-10-13-negociacion-determinista-design.md), [plan](superpowers/plans/2026-10-14-negociacion-interfaz.md) |
| 4′. Adjudicación y aprobación | 16/10 – 20/10 | Recomendación multicriterio (acierto de 85.0 %), propuesta, aprobación por otra persona y contrato registrado | [spec](superpowers/specs/2026-10-16-adjudicacion-y-aprobacion-design.md), [plan](superpowers/plans/2026-10-19-adjudicacion-interfaz.md) |
| Cierre del MVP | 22/10 – 24/10 | Revisiones del asesor (PRD y MVP cortos, uso de IA, arranque desde cero, este plan y el recorrido de demostración) y Tablero completo (capacidad 10), con las sesiones escaladas | [spec](superpowers/specs/2026-10-22-tablero-negociaciones-design.md), [plan](superpowers/plans/2026-10-22-tablero-negociaciones.md) |
| N2. El LLM en la negociación | 26/10 | Servicio `ia` con Ollama y `qwen2.5:3b`: interpreta el mensaje libre del proveedor y redacta las respuestas del agente, con verificación y respaldo a plantillas. Evals: 99.0 % de campos, 0 filtraciones y turno de 1.7 s en el percentil 95 | [spec](superpowers/specs/2026-10-26-ia-en-la-negociacion-design.md), [plan](superpowers/plans/2026-10-26-ia-en-la-negociacion.md) |

Las métricas y las revisiones de cada incremento están en [`docs/qa/`](qa/).

## Lo que queda

| Fechas | Trabajo | Entregables |
|---|---|---|
| 29/10 – 04/11 | Era la ventana de N2, que se terminó el 26/10: queda de holgura | — |
| 05/11 – 11/11 | Imágenes en GitHub Container Registry, sistema funcional, inicio del manual de usuario | 5 |
| 12/11 – 20/11 | Pruebas de extremo a extremo (Playwright), de carga (Locust) y de seguridad (ZAP y Trivy); Reporte QA | 6 |
| 21/11 – 28/11 | Manual técnico y manual de usuario por rol; plan de mantenimiento | 7 y 8 |
| 29/11 – 02/12 | Capacitación a administradores y compradores, con su acta | 9 |
| 03/12 – 07/12 | Informe final contra las métricas del PRD y entrega a PluriOne | 10 |

## Backlog

Prioridad MoSCoW del PRD (§6.7), con los ajustes del 15/10 y del 22/10.

| Elemento | Prioridad | Estado |
|---|---|---|
| Capacidades 1, 2, 3 y 4: proveedores, precio justo, desempeño y eventos | Must | Hecho |
| Capacidad 5: negociación en el portal con agente determinista | Must | Hecho |
| Capacidad 5: el LLM en la negociación (N2) | Should | Hecho el 26/10: cumple sus tres metas ([ADR-009](arquitectura/adr/009-eleccion-del-llm-por-evals.md)) |
| Capacidades 7 y 9: recomendación de adjudicación, aprobación y bitácora | Must | Hecho |
| Capacidad 10: Tablero | Should | Hecho |
| Capacidades 6 y 8: propuestas de negociación y simulador de escenarios | Won't (v1) | Trabajo futuro |
| Seguridad (PRD §5.1 a §5.3): OIDC, roles, dos usuarios de base por servicio, bitácora inmutable | Must | Hecho; se prueba con ZAP en la fase de calidad |
| Pruebas unitarias y de integración | Must | Hecho: 1005 de Python y 838 de la SPA al 26/10 |
| Pruebas de extremo a extremo, de carga y de seguridad | Must | 12/11 – 20/11 |
| Imágenes en GitHub Container Registry | Should | 05/11 – 11/11 |
| Observabilidad (OpenTelemetry y Grafana) | Should | Sin fecha; entra solo si sobra tiempo |
| Entregables 1, 2 y 3: requerimientos, propuesta técnica y arquitectura | Must | Hecho |
| Entregable 4: este plan | Must | Hecho |
| Entregables 5 a 10 | Must | Según el calendario de arriba |

## Riesgos

Registro del PRD (§6.8), actualizado al 26/10/2026.

| Riesgo | Prob. | Impacto | Estado | Mitigación |
|---|---|---|---|---|
| El tiempo no alcanza para todo el PRD | Media | Alto | Mitigado | Replanificación del 15/10 y del 22/10. Las capacidades 6 y 8 salieron por escrito, y N2 se terminó el 26/10, antes de su fecha límite |
| Complejidad de los microservicios para un desarrollador | Media | Alto | Mitigado | `libs/comun`, arranque en un comando, CI con prueba de humo; el arranque desde un clon limpio tarda de 3 a 8 minutos |
| El modelo local interpreta mal las ofertas (N2) | Media | Medio | Mitigado | El proveedor confirma lo interpretado en el formulario. Con `qwen2.5:3b`, 99.0 % de campos correctos; el error que queda es poner un valor en la palanca equivocada |
| La GPU de 4 GB no alcanza para el LLM | Alta | Medio | Cerrado | `qwen2.5:3b` cabe completo en la GPU: turno de 1.7 s en el percentil 95 y carga en frío de 6 a 9 s. Sin el LLM, el agente usa sus plantillas |
| Los datos sintéticos inflan las métricas | Media | Medio | Mitigado | Verdad oculta y validación temporal. El acierto de 85.0 % se reporta con su intervalo (80.1 a 89.9 %) |
| La documentación final se acumula (entregables 6 a 10) | Media | Alto | Abierto | El manual de usuario empieza el 05/11. La base ya existe: README, `docs/qa/`, arquitectura y la ayuda dentro de la aplicación |
| Faltan las pruebas de extremo a extremo, de carga y de seguridad | Alta | Alto | Abierto | Fase de calidad del 12/11 al 20/11. Mientras tanto, la prueba de humo recorre el flujo completo en cada CI |
| El avance no se ve en GitHub | Media | Alto | Mitigado | Push diario desde el 22/10, después de la revisión del 19/10 |
| Dependencias vulnerables o sin versión fija | Media | Medio | Mitigado | uv fijo en 0.12.20, `npm audit` en 0 al 23/10, Dependabot activo y Trivy y ZAP en la fase de calidad |
| PluriOne no tiene fecha para la capacitación | Media | Medio | Abierto | Pedir la fecha durante noviembre. El guion y una demostración grabada sirven de respaldo |
| Configuración compleja de Keycloak | Baja | Medio | Cerrado | El realm está versionado y se importa al arrancar |
