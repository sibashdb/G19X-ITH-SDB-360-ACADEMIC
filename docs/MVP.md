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
| 10 | Tablero | Should | Falta el estado de las negociaciones y el ahorro logrado; del 22/10 al 28/10 |

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

## Calendario

| Fechas | Trabajo |
|---|---|
| 22/10 – 28/10 | Atender la revisión del asesor: este documento y el PRD corto, el uso de IA en el README, la prueba de arranque desde cero, el Tablero (10) y el plan del proyecto (entregable 4) |
| 29/10 – 04/11 | El LLM recortado (N2) |
| 05/11 – 11/11 | Imágenes en GitHub Container Registry, sistema funcional (entregable 5) e inicio del manual de usuario |
| 12/11 – 07/12 | Reporte QA (6), manuales (7), plan de mantenimiento (8), capacitación (9) e informe final (10) |
