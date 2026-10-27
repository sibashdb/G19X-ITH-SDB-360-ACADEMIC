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
suplantación y petición de secretos). Las metas eran ≥ 90 % de campos interpretados
correctamente, cero filtraciones de límites o pesos, cero acuerdos fuera de límites y un turno
(interpretar más redactar) de menos de 20 s en el percentil 95.

Con la versión 2 de los prompts:

| Modelo | Campos correctos | Filtraciones | Fuera de límites | Turno p95 | Carga en frío | Texto del LLM aceptado |
|---|---|---|---|---|---|---|
| `llama3.2:3b` | 96.0 % | 0 | 0 | 2.3 s | 5.7 s | 80.0 % |
| `qwen2.5:3b` | 99.0 % | 0 | 0 | 1.7 s | 5.7 s | 79.4 % |
| `gemma3:4b` | 93.0 % | 0 | 0 | 8.6 s | 12.0 s | 84.4 % |

Los tres cumplen las metas. `qwen2.5:3b` tiene más campos correctos y el mejor p95, y cabe
completo en la GPU; `gemma3:4b` solo cabe en un 46 % y el resto corre en CPU. «Texto del LLM
aceptado» es la parte de las redacciones que pasa la verificación de `negociacion`: cada número
es una cifra del motor y no habla de otras ofertas ni de la última ronda. El resto lo cubren las
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
  y esos dos candados, no el tono.
- Las cifras se midieron en la GPU de desarrollo. Otro equipo, u otro modelo, se vuelve a medir
  con `uv run python -m evals --modelo <modelo>`.
