# Revisión en navegador de la adjudicación y la aprobación (4′b)

- **Fecha:** 2026-10-20.
- **Rama y commits:** `feat/adjudicacion`.
  - Los flujos corrieron sobre el gateway con la imagen de `7787ede`, anterior a las correcciones.
  - axe corrió sobre el servidor de Vite con el código de la rama.
    - Las vistas de negociación, la ayuda y el portal se revisaron con `7787ede`, antes de las correcciones.
    - Configuración, Actividad, Correos y el botón destructivo se revisaron con `6eafde4`, que ya incluía las correcciones D1 a D5.
  - Las correcciones están en `d7d1c87`, `6b320fc`, `39f291e`, `ffc0784`, `3c2417f`, `a670551`, `6eafde4` y `f1a3c0b`.
- **Usuarios de prueba:** `comprador1` (rol comprador), `aprobador1` (rol aprobador) y `admin1` (rol admin).
  - Sus contraseñas están en el realm de desarrollo y no se repiten aquí.
  - La persona que hizo la revisión inició cada sesión en el panel del navegador; las contraseñas no pasaron por el agente.
  - Los enlaces del portal se abrieron desde el diálogo de publicación o desde Mailpit, sin copiarlos fuera del navegador.
- **Alcance:**
  - evaluación de los acuerdos, con la recomendación explicada y los pesos ajustables;
  - adjudicación directa y propuesta al aprobador, con justificación;
  - aprobación y rechazo;
  - negociación desierta, manual y automática;
  - resumen de la negociación adjudicada o desierta;
  - filtro «Por aprobar», correos y aviso del resultado en el portal;
  - sección «Adjudicación» de Configuración, Actividad y Correos.

## Entorno y método

- **Verificación previa** (desde `web/`): `npm run lint`, `npm run build`, `npx vitest run` y `npx prettier --check` limpios. Con las correcciones son 810 pruebas en 62 archivos.
- **Stack y prueba de humo:**
  - el stack se levantó con `uv run python infra/arrancar.py`, que reconstruye las imágenes;
  - la prueba de humo respondió «OK: SPA, Keycloak, proveedores, administración, operación, inteligencia, negociación y adjudicación responden (60 proveedores).».
- **Gateway** (<http://localhost:8080>, con CSP): los flujos de la tabla siguiente, comprobados con el texto de la página, el árbol de accesibilidad, el foco, las regiones vivas y las peticiones de red.
- **Servidor de Vite** (<http://localhost:5173>, sin CSP):
  - axe-core 4.13 cargado desde `/node_modules/axe-core/axe.min.js` dentro de cada vista;
  - reglas WCAG 2.0, 2.1 y 2.2, niveles A y AA, **con** la regla de contraste;
  - cada vista se cargó en un `iframe` del mismo origen con el ancho de la prueba (375, 768, 1024 y 1440 px), en tema claro y en tema oscuro (`prefers-color-scheme` emulado; el tema de la aplicación está en «Sistema»);
  - los diálogos se abrieron dentro del `iframe` antes de correr axe.
- **Desplazamiento horizontal:** se considera correcto si `document.documentElement.scrollWidth <= window.innerWidth`.
- **Datos que deja la revisión:**
  - **NEG-2026-0018** «QA adjudicación con dos proveedores»: compra de 2,000 «Soporte de base de datos» por 12 meses, con dos acuerdos tentativos. Quedó adjudicada a Datos Azteca con aprobación, contrato `C-NEG-2026-0018`, y una propuesta rechazada.
  - **NEG-2026-0019** «QA adjudicación directa»: adjudicada directamente, contrato `C-NEG-2026-0019`.
  - **NEG-2026-0020** «QA desierta automática»: desierta sin acuerdos.
  - **NEG-2026-0021** «QA evaluación para axe»: queda «En evaluación».
  - **NEG-2026-0005** (renovación de C-000302, de la revisión de N1b): declarada desierta con motivo.
  - La configuración se cambió a 45/30/15/10 con umbral de $600,000 y se dejó otra vez en 40/30/15/15 con $500,000.00.

## Flujos

| # | Flujo | Resultado |
|---|---|---|
| 1 | Evaluación con dos candidatos | **comprador1** abre NEG-2026-0018 «En evaluación». La tabla ordena a Datos Azteca (100 puntos, «Recomendado» con icono y texto) y a Datos Digitales (15). «Por qué se recomienda» explica el margen, el aporte de cada criterio y la sensibilidad. El SLA, que nadie negoció, no aparece en la sensibilidad. |
| 2 | Ajustar pesos | Con 60/20/10/5 el total en vivo dice «Total: 95 de 100 · Los pesos deben sumar 100» y «Recalcular» no consulta. Con 60/20/10/10 hace una sola petición, `GET …/evaluacion?pesos=60,20,10,10`, con las comas sin codificar. |
| 3 | Proponer al no recomendado | El diálogo anticipa «Irá a un aprobador porque el costo total ($147,840,000.00) supera el umbral de aprobación ($500,000.00).» y pide la justificación. Sin ella, «Confirmar» no envía nada, el foco pasa al campo y el campo queda inválido con el mensaje. Con justificación, la negociación queda «Pendiente de aprobación», el aviso dice «Se envió la propuesta a un aprobador.» y el foco pasa al contenido. |
| 4 | Vista pendiente | La propuesta muestra la foto guardada: los pesos 60/20/10/10, la fila «Propuesta», la justificación y «Supera el umbral de aprobación». Aquí se encontró el defecto D2. |
| 5 | Por aprobar | **aprobador1** entra a Negociaciones y la lista se abre sola con «Por aprobar», que muestra solo NEG-2026-0018. |
| 6 | Rechazar | Con el motivo vacío, el diálogo dice «Escriba el motivo.», marca el campo y le pasa el foco, sin enviar nada. Con motivo, la negociación vuelve a «En evaluación», el aviso dice «Se rechazó la propuesta; la negociación vuelve a evaluación.» y el foco pasa al contenido. El aprobador ve la evaluación sin «Adjudicar» ni «Declarar desierta». Aquí se encontró el defecto D3. |
| 7 | Proponer de nuevo y aprobar | **comprador1** propone al recomendado, que vuelve a ir al aprobador por el umbral. **aprobador1** aprueba: «Se aprobó la adjudicación.» y el estado pasa a «Adjudicada». El resumen muestra a quién propuso, a quién aprobó con fecha, el costo total, el folio `C-NEG-2026-0018` y la propuesta rechazada con su motivo. |
| 8 | Adjudicación directa | En NEG-2026-0019 el diálogo anticipa «Se adjudicará directamente: el costo total ($2,900.00) no supera el umbral de aprobación ($500,000.00) y el acuerdo está dentro de sus límites.». El resumen dice «Adjudicación directa del comprador» y el folio `C-NEG-2026-0019`. Aquí se encontró el defecto D1. |
| 9 | Desierta manual | En NEG-2026-0005, «Declarar desierta» con motivo deja «Desierta» y el resumen dice «La negociación se declaró desierta.» y el motivo. El aviso y el foco funcionan como en el flujo 3. |
| 10 | Desierta automática | En NEG-2026-0020, el comprador toma el control de la única sesión y la cierra sin acuerdo. La negociación queda «Desierta» y el resumen dice «Ningún proveedor llegó a un acuerdo tentativo.». |
| 11 | Correos de resultado | Mailpit recibió un correo «Resultado de la negociación …» por proveedor: «Su oferta fue adjudicada; el equipo de compras se pondrá en contacto», «La negociación se adjudicó a otra propuesta» y «La negociación se declaró desierta». Ninguno nombra al ganador ni muestra montos. |
| 12 | Portal | El enlace de invitación del proveedor de NEG-2026-0019 abre el portal con el aviso «Su oferta fue adjudicada; el equipo de compras se pondrá en contacto.». El token sale de la barra de direcciones al abrir. |
| 13 | Configuración y Actividad | **admin1** cambia la sección «Adjudicación» a 45/30/15/10 y $600,000: «Se guardó la configuración de la adjudicación.». Actividad nombra los campos en español: «peso del costo en la adjudicación», «peso del SLA en la adjudicación» y «umbral de aprobación». También muestra la adjudicación aprobada y la directa, la desierta automática y los avisos. Aquí se encontró el defecto D6. |
| 14 | Correos | La página dice «Invitaciones, restablecimientos de contraseña, invitaciones a negociar y sus resultados que envió la plataforma, y si salieron bien.» y muestra el tipo «Resultado de negociación». |

## axe y desplazamiento horizontal por ancho

En todas las vistas siguientes axe no encontró violaciones y no hubo desplazamiento horizontal, en los cuatro anchos y en los dos temas:

- la lista de Negociaciones y la lista filtrada «Por aprobar»;
- la evaluación de NEG-2026-0021, con los diálogos «Adjudicar a …» y «Declarar desierta» abiertos;
- la vista pendiente de NEG-2026-0018, como comprador y como aprobador, con el diálogo «Rechazar» abierto;
- los resúmenes de NEG-2026-0018 (con la propuesta rechazada), NEG-2026-0019, NEG-2026-0020 y NEG-2026-0005;
- el artículo de ayuda «Adjudicar y aprobar»;
- el portal con el aviso del resultado;
- Configuración, Actividad y Correos.

La única excepción fue el botón destructivo de confirmación (defecto D4), en los dos temas, antes de su corrección. Después de `ffc0784` pasa la regla de contraste en el navegador: blanco sobre #DC2626 en claro y #0B1220 sobre #F87171 en oscuro.

## Defectos encontrados y corregidos

| # | Defecto | Corrección |
|---|---|---|
| D1 | El aviso «Se adjudicó la negociación a Datos Integrales S.A. de C.V..» duplicaba el punto, porque el nombre ya termina en punto. Lo mismo pasaba en la explicación de la recomendación («…ganaría Datos Integrales S.A. de C.V..») y en el aviso «Se copió el enlace de …» de N1. | `d7d1c87` y `a670551`: un solo ayudante, `conPuntoFinal`, cierra esas frases, con sus pruebas. |
| D2 | Quien propuso sin tener el rol de aprobador veía «Usted propuso esta adjudicación; la aprueba otra persona.». La spec §7.1 reserva ese texto para quien propuso y además es aprobador; el comprador ve «Esperando aprobación de un aprobador». | `6b320fc`, con una prueba por cada combinación de rol y persona. |
| D3 | Después de un rechazo, la evaluación no decía al comprador quién rechazó ni por qué; solo lo mostraba el resumen final. | `39f291e`: la evaluación muestra la propuesta rechazada más reciente, con su proveedor, quién la propuso y quién la rechazó, cuándo y el motivo. Comparte el componente con el resumen. |
| D4 | El botón destructivo compartido tenía un contraste de 3.82:1 en claro y 4.38:1 en oscuro (se exige 4.5:1). Afectaba a «Declarar desierta», «Rechazar propuesta» y «Cancelar negociación» de N1. | `ffc0784` y `6eafde4`: relleno sólido con 4.83:1 y 6.77:1 en reposo, y 5.82:1 y 7.36:1 al pasar el cursor. Una prueba de tokens protege también el hover. |
| D5 | La ayuda del rechazo decía «Queda en la bitácora.», una bitácora que la web no muestra. | `3c2417f`: «Queda con la propuesta rechazada.». |
| D6 | Actividad decía «Cambió la configuración de la puntuación» también cuando solo cambiaba la adjudicación, y su descripción no mencionaba las negociaciones. | `f1a3c0b`: el texto nombra la sección que cambió, igual en el servidor y en la web, y la descripción menciona la adjudicación y las negociaciones. |

## Lo que no se revisó en el navegador

- **Dos aprobadores sobre una misma propuesta** (el 409 `propuesta_distinta` y «Revisar la propuesta nueva»): no se reprodujo con dos sesiones. Lo cubren las pruebas de la API y de la interfaz.
- **Quien propuso con los dos roles:** el realm de desarrollo no tiene un usuario con comprador y aprobador a la vez. Lo cubren las pruebas de `SeccionAprobacion`.
- **Las correcciones D1, D2, D3, D5 y D6 no se volvieron a ver en el navegador.** Se hicieron después de los flujos y las cubren sus pruebas en jsdom. En particular:
  - el aviso de la propuesta rechazada en la evaluación (D3) queda por mirar a 375 px;
  - el texto nuevo de Actividad (D6) es de `f1a3c0b`, posterior a la imagen que servía el gateway.
- **El foco y el hover del botón destructivo:** el contraste en reposo se comprobó en el navegador; el del hover y el foco se calcularon a partir de los tokens.
