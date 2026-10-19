# ADR-011: Quién aprueba una adjudicación

- **Estado:** Aceptada
- **Fecha:** 2026-10-16

## Contexto

Con N1, una negociación termina en «En evaluación» con varios acuerdos tentativos, y ninguno es
vinculante. El PRD (§3.1 y §5.1) dice que la adjudicación «siempre la aprueba un humano»: el
aprobador, si el monto supera el umbral, y si no, el propio comprador. Deja abiertas tres cosas:

- qué pasa con un acuerdo que el comprador aceptó o propuso a mano **fuera de los límites** que
  fijó, algo que N1 permite con confirmación y a lo que le prometió «lo verá el aprobador»;
- si una persona con los roles de comprador y de aprobador puede aprobar lo que ella misma
  propuso;
- cuánto vale el umbral: el PRD no da una cifra.

## Decisión

1. **Quién aprueba (D5).** Si el costo total de la propuesta, en MXN, supera el umbral, la aprueba
   un aprobador. Si no, la propuesta del comprador es la adjudicación: queda `directa`, el evento
   pasa a «Adjudicado» en la misma transacción y no hay un paso aparte.
2. **Quien propone nunca aprueba su propia propuesta (D5).** Aunque tenga los dos roles, recibe un
   403 con el código `misma_persona`.
3. **Fuera de límites siempre pasa por el aprobador (D6).** Un acuerdo que el comprador aceptó o
   propuso a mano fuera de los límites (la sesión queda marcada `fuera_de_limites`) requiere
   aprobación sin importar el monto.
4. **Umbral por defecto: $500,000 MXN de costo total (D7).** El costo total incluye la cuota de
   implementación y se compara en MXN al tipo de cambio más reciente; la regla es «mayor que», no
   «mayor o igual». El administrador lo cambia en Configuración junto a los pesos de la
   recomendación, y el cambio queda en la Actividad. La regla se evalúa al proponer y se guarda
   con la propuesta (`requiere_aprobacion` y `motivo_aprobacion`): cambiar el umbral después no
   mueve una propuesta que ya espera.
5. **La aprobación se liga a la propuesta revisada.** Aprobar o rechazar lleva el
   `adjudicacion_id` que el aprobador tenía abierto; si ya no es la pendiente, la respuesta es un
   409 `propuesta_distinta` y no se decide nada. Cada propuesta es una fila de `adjudicacion`, así
   que las rechazadas quedan como historial.

## Consecuencias

- Las dos cifras que cumplen el PRD se pueden probar: 0 adjudicaciones sin aprobación cuando
  superan el umbral o salen de límites, y 0 aprobaciones hechas por quien propuso. Las dos tienen
  pruebas de la API en `negociacion`, y la prueba de humo recorre el camino sobre el umbral de
  punta a punta.
- El umbral de $500,000 MXN es una decisión del diseño, no un dato de PluriOne. Es configurable
  precisamente por eso; conviene confirmarlo con el área de compras antes del uso real.
- Un equipo de una sola persona con los dos roles no puede adjudicar sobre el umbral: necesita a
  otra persona que apruebe. Es el costo de la separación de funciones y se acepta.
- Los acuerdos fuera de límites llegan al aprobador aunque sean pequeños, así que habrá más
  aprobaciones que si solo contara el monto. A cambio, la promesa de N1 se cumple y el aprobador
  ve la marca y el motivo de la regla.
- La bitácora distingue quién propuso y quién decidió (`adjudicacion.propuesta`,
  `adjudicacion.aprobada`, `adjudicacion.directa` y `adjudicacion.rechazada`), con el motivo de
  cada rechazo.
- Cambiar la regla (por ejemplo, umbrales por categoría o doble aprobación) toca solo la función
  de dominio que decide si una propuesta requiere aprobación y la configuración de `inteligencia`.
