# PRD — Plataforma de Negociación Automática con Proveedores

Entregable 1 del cronograma. Este archivo es la entrada corta; el documento completo es la
[especificación del 28/09/2026](superpowers/specs/2026-09-28-plataforma-negociacion-proveedores-design.md),
aprobada por el residente ese día. El alcance vigente, con los recortes posteriores, está en
[`MVP.md`](MVP.md).

## En una página

**Problema.** Una empresa mediana que compra servicios de TI negocia a mano, con la información
en correos y hojas de cálculo. Las renovaciones suben sin que nadie lo cuestione, el comprador no
sabe cuál es un precio justo, la elección del proveedor no queda documentada y no hay registro de
qué se ofreció ni por qué se concedió.

**Usuarios.** Administrador, comprador y aprobador (internos, con cuenta) y proveedor (externo,
entra con un enlace de invitación, sin cuenta).

**Qué hace** (las 10 capacidades del MVP, §1.3):

1. Proveedores, contratos e historial, con importación por CSV.
2. Inteligencia de precios: precio justo por servicio y alertas de sobreprecio y de renovación.
3. Desempeño del proveedor convertido en una puntuación.
4. Eventos de negociación con ideal y límite por término.
5. Negociación con un agente en el portal del proveedor, con escalamiento a una persona.
6. Propuestas de negociación para cuando el comprador negocia a mano.
7. Recomendación de adjudicación multicriterio y explicable.
8. Simulador de escenarios de costo total.
9. Aprobaciones y bitácora inmutable.
10. Tablero: ahorros, contratos por vencer, desempeño y estado de las negociaciones.

**Reglas que no cambian.** Ningún acuerdo sale de los límites del comprador. Todo cierre pasa por
una persona. Quien propone una adjudicación no la aprueba. Si hay LLM, solo redacta e interpreta:
la decisión es del motor ([ADR-002](arquitectura/adr/002-el-llm-habla-el-motor-decide.md)).

**Cómo se mide.** Las metas están en §1.6 y los resultados medidos, en el
[README](../README.md#qué-está-hecho-y-qué-falta).

## Dónde está cada parte del PRD completo

| Sección | Contenido |
|---|---|
| §0 | Decisiones de partida (uso, stack, costo cero, arquitectura) |
| §1 | Problema, roles, capacidades, fuera de alcance, simulador con bots y métricas de éxito |
| §2 | Servicios, comunicación, estructura del repositorio y recursos |
| §3 | Ciclo de la negociación y motor de concesiones |
| §4 | Datos simulados y modelos (precio justo, puntuación, adjudicación, simulador, evals del LLM) |
| §5 | Seguridad, errores, resiliencia y observabilidad |
| §6 | Pruebas, CI/CD, Scrum, ADR, entregables, plan, replanificación (§6.6.1 y §6.6.2), MoSCoW y riesgos |
| §7 | Stack |
| §8 | Glosario |
