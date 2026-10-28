# ADR-009: Elección del modelo LLM local según los evals

- **Estado:** Aceptada (N2, 26/10/2026)
- **Fecha:** 2026-09-28

## Contexto

La GPU de desarrollo tiene 4 GB, así que solo caben modelos de unos 3 mil millones de parámetros,
cuantizados. Cuál conviene depende de qué tan bien interpreten las ofertas, de si se les escapa
un límite y de cuánto tardan.

## Decisión

Se usa **`qwen2.5:3b`**, elegido con los evals de [`docs/qa/evals-llm.md`](../../qa/evals-llm.md)
(PRD §4.8): 150 mensajes de proveedor etiquetados en 13 formatos y 30 ataques (inyección,
suplantación y petición de secretos), sobre una negociación de una línea, y otros 30 mensajes que
ponen precios a una, dos o las tres líneas de otra negociación. Las metas eran ≥ 90 % de campos
interpretados correctamente (también con 3 líneas), cero filtraciones de límites o pesos, cero
acuerdos fuera de límites y un turno (interpretar más redactar) de menos de 20 s en el
percentil 95.

Con la versión 2 de los prompts y las correcciones de la revisión final:

| Modelo | Campos correctos | Campos con 3 líneas | Filtraciones | Fuera de límites | Turno p95 | Carga en frío | Texto del LLM aceptado |
|---|---|---|---|---|---|---|---|
| `llama3.2:3b` | 96.0 % | 84.5 % | 0 | 0 | 2.4 s | 6.9 s | 55.0 % |
| `qwen2.5:3b` | 99.0 % | 100.0 % | 0 | 0 | 1.7 s | 9.3 s | 72.8 % |
| `gemma3:4b` | 93.0 % | 100.0 % | 0 | 0 | 8.6 s | 11.9 s | 57.2 % |

`qwen2.5:3b` y `gemma3:4b` cumplen las metas; `llama3.2:3b` no, porque con 3 líneas pone precios
en la línea equivocada. `qwen2.5:3b` tiene más campos correctos, el mejor p95 y el texto que más
pasa la verificación, y cabe completo en la GPU; `gemma3:4b` solo cabe en un 46 % y el resto
corre en CPU. «Texto del LLM aceptado» es la parte de las redacciones que pasa la verificación de
`negociacion`: cada número, también escrito con palabras, es una cifra del motor, y el texto no
afirma una aceptación ni habla de otras ofertas o de la última ronda. El resto lo cubren las
plantillas.

## Consecuencias

- `LLM_MODELO=qwen2.5:3b` en `infra/.env.example`, en el `docker-compose.yml` y en la
  configuración de `ia`.
- El error más común de los tres modelos es poner un valor en la palanca equivocada (el plazo de
  pago como plazo del contrato) o inventar una palanca que el mensaje no menciona. Por eso lo
  interpretado solo llena el formulario y el proveedor lo confirma (PRD §6.6.2).
- La versión 1 de los prompts daba la decisión al redactor como JSON, con las condiciones falsas
  incluidas. Con ella, la verificación numérica solo aceptó el 28.3 % de las redacciones de
  `llama3.2:3b`, y la revisión en el navegador encontró textos de `qwen2.5:3b` que decían «No hay
  mejores ofertas» o anunciaban una última ronda que no lo era
  ([`revision-ia-negociacion.md`](../../qa/revision-ia-negociacion.md)). Los evals miden números
  y esos candados, no el tono.
- El LLM ve las líneas como `l1`, `l2`…, no por su id. Así una negociación real se le presenta
  igual que en los evals, sin gastar tokens en los UUID. Los evals miden hasta 3 líneas; una
  negociación admite 20.
- Los evals se definieron en la spec y el plan de N2 antes de escribir código, pero su commit
  (`4be178f`) llegó después del primero del servicio `ia` (`319d6c5`), el mismo 26/10. La
  elección del modelo sí se hizo con ellos. La línea base sin el LLM, que no interpreta nada
  (0 % de campos, 0 filtraciones), se corrió el 27/10
  ([`evals-linea-base.md`](../../qa/evals-linea-base.md)).
- Las cifras se midieron en la GPU de desarrollo. La carga en frío varió de 6 a 9 s con
  `qwen2.5:3b` entre corridas. Otro equipo, u otro modelo, se vuelve a medir con
  `uv run python -m evals --modelo <modelo>`.
