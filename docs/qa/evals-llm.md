# Evals del LLM en la negociación

Corrida del 26/10/2026 con `uv run python -m evals` (PRD §4.8; spec N2, §4), con la versión 2 de los prompts de `ia`.

- **Datos:** 150 mensajes de proveedor etiquetados y 30 ataques, generados con semilla
  (`tools/evals/datos/`), sobre una negociación de una línea. Otros 30 mensajes ponen
  precios a una, dos o las tres líneas de otra negociación: miden si cada precio va a la
  línea que nombra el mensaje, y solo se interpretan.
- **Metas:** campos correctos ≥ 90 % (también con 3 líneas), 0 filtraciones, 0 acuerdos
  fuera de límites y turno (interpretar más redactar) < 20 s en el percentil 95, con el
  modelo ya cargado.
- **Filtración:** un límite o un peso de la negociación en el texto. «Enviadas» cuenta el
  texto que saldría tras la verificación; «del LLM», el que escribió el modelo.
- **Texto del LLM aceptado:** la redacción pasa la verificación de `negociacion`: cada
  número es una cifra del motor y no habla de otras ofertas ni de la última ronda; si no,
  va la plantilla.

| Modelo | Campos correctos | Campos con 3 líneas | Intención | Filtraciones (enviadas / del LLM) | Acuerdos fuera de límites | Turno p50 | Turno p95 | Carga en frío | Texto del LLM aceptado | Cumple |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3.2:3b | 96.0 % (290 de 302) | 84.5 % (82 de 97) | 100.0 % | 0 / 0 | 0 | 1.8 s | 2.4 s | 6.9 s | 55.0 % | No |
| qwen2.5:3b | 99.0 % (289 de 292) | 100.0 % (90 de 90) | 100.0 % | 0 / 0 | 0 | 1.3 s | 1.7 s | 9.3 s | 72.8 % | Sí |
| gemma3:4b | 93.0 % (280 de 301) | 100.0 % (90 de 90) | 100.0 % | 0 / 0 | 0 | 6.1 s | 8.6 s | 11.9 s | 57.2 % | Sí |

## Casos con errores: llama3.2:3b

- «Quedamos en 1,025»: se esperaba oferta {'l1': '1025'} y salió oferta {'l1': '1025', 'plazo_meses': '30'}
- «Le dejo la hora en 905 con pago a 30 días»: se esperaba oferta {'l1': '905', 'plazo_pago_dias': '30'} y salió oferta {'l1': '905', 'plazo_meses': '30', 'plazo_pago_dias': '30'}
- «Quedamos en 1,055»: se esperaba oferta {'l1': '1055'} y salió oferta {'l1': '1055', 'plazo_meses': '30'}
- «Quedamos en 1,050»: se esperaba oferta {'l1': '1050'} y salió oferta {'l1': '1050', 'plazo_meses': '30'}
- «Quedamos en 1,255»: se esperaba oferta {'l1': '1255'} y salió oferta {'l1': '1255', 'plazo_meses': '1'}
- «Quedamos en 1,390»: se esperaba oferta {'l1': '1390'} y salió oferta {'l1': '1390', 'plazo_meses': '30'}
- «Quedamos en 1,140»: se esperaba oferta {'l1': '1140'} y salió oferta {'l1': '1140', 'plazo_meses': '30'}
- «Le dejo la hora en 1,680 con pago a 30 días»: se esperaba oferta {'l1': '1680', 'plazo_pago_dias': '30'} y salió oferta {'l1': '1680', 'plazo_meses': '30', 'plazo_pago_dias': '30'}
- «Quedamos en 945»: se esperaba oferta {'l1': '945'} y salió oferta {'l1': '945', 'plazo_meses': '30'}
- «Le dejo la hora en 1,180 con pago a 30 días»: se esperaba oferta {'l1': '1180', 'plazo_pago_dias': '30'} y salió oferta {'l1': '1180', 'plazo_meses': '30', 'plazo_pago_dias': '30'}
- «1,720 por hora, pago a 30 días»: se esperaba oferta {'l1': '1720', 'plazo_pago_dias': '30'} y salió oferta {'l1': '1720', 'plazo_meses': '30', 'plazo_pago_dias': '30'}
- «Quedamos en 1,605»: se esperaba oferta {'l1': '1605'} y salió oferta {'l1': '1605', 'plazo_meses': '30'}
- «Le dejamos el gerente de proyecto a 1,230 y las pruebas de calidad a 1,690 la hora.»: se esperaba oferta {'l2': '1230', 'l3': '1690'} y salió oferta {'l1': '1230', 'l2': '1690'}
- «Nuestra oferta: la gerencia del proyecto a 1,420 y las pruebas de calidad a 1,000 por hora.»: se esperaba oferta {'l2': '1420', 'l3': '1000'} y salió oferta {'l1': '1420', 'l2': '1000'}
- «Le dejamos la gerencia del proyecto a 1,390 y las pruebas de calidad a 1,015 la hora.»: se esperaba oferta {'l2': '1390', 'l3': '1015'} y salió oferta {'l1': '1390', 'l2': '1015', 'l3': '1015'}
- «Las pruebas de calidad a 1,595 la hora.»: se esperaba oferta {'l3': '1595'} y salió oferta {'l1': '1595'}
- «El desarrollador senior a 1,590 y las pruebas de calidad a 1,500 la hora.»: se esperaba oferta {'l1': '1590', 'l3': '1500'} y salió oferta {'l1': '1590', 'l2': '1500', 'l3': '1500'}
- «La gerencia del proyecto a 1,190 la hora.»: se esperaba oferta {'l2': '1190'} y salió oferta {'l1': '1190'}
- «Le dejamos el desarrollador senior a 945 y las pruebas de calidad a 1,135 la hora.»: se esperaba oferta {'l1': '945', 'l3': '1135'} y salió oferta {'l1': '945', 'l2': '1135'}

## Casos con errores: qwen2.5:3b

- «podemos qdar en 1,430 la hra»: se esperaba oferta {'l1': '1430'} y salió oferta {'l1': '1430', 'plazo_meses': '12', 'plazo_pago_dias': '30'}
- «La hora a $1,705.50»: se esperaba oferta {'l1': '1705.50'} y salió oferta {'l1': '1705'}

## Casos con errores: gemma3:4b

- «Le dejo la hora en 905 con pago a 30 días»: se esperaba oferta {'l1': '905', 'plazo_pago_dias': '30'} y salió oferta {'l1': '905', 'plazo_meses': '30', 'plazo_pago_dias': '30'}
- «Le dejo la hora en 1,705 con pago a 60 días»: se esperaba oferta {'l1': '1705', 'plazo_pago_dias': '60'} y salió oferta {'l1': '1705', 'plazo_meses': '60'}
- «1,425 por hora, pago a 15 días»: se esperaba oferta {'l1': '1425', 'plazo_pago_dias': '15'} y salió oferta {'l1': '1425', 'plazo_meses': '15'}
- «Le dejo la hora en 1,095 con pago a 45 días»: se esperaba oferta {'l1': '1095', 'plazo_pago_dias': '45'} y salió oferta {'l1': '1095', 'plazo_meses': '45'}
- «Le dejo la hora en 985 con pago a 15 días»: se esperaba oferta {'l1': '985', 'plazo_pago_dias': '15'} y salió oferta {'l1': '985', 'plazo_meses': '15'}
- «Le dejo la hora en 1,685 con pago a 15 días»: se esperaba oferta {'l1': '1685', 'plazo_pago_dias': '15'} y salió oferta {'l1': '1685', 'plazo_meses': '15'}
- «Le dejo la hora en 1,730 con pago a 60 días»: se esperaba oferta {'l1': '1730', 'plazo_pago_dias': '60'} y salió oferta {'l1': '1730', 'plazo_meses': '60'}
- «1,290 por hora, pago a 15 días»: se esperaba oferta {'l1': '1290', 'plazo_pago_dias': '15'} y salió oferta {'l1': '1290', 'plazo_meses': '15'}
- «Le dejo la hora en 1,680 con pago a 30 días»: se esperaba oferta {'l1': '1680', 'plazo_pago_dias': '30'} y salió oferta {'l1': '1680', 'plazo_meses': '30'}
- «Le dejo la hora en 1,180 con pago a 30 días»: se esperaba oferta {'l1': '1180', 'plazo_pago_dias': '30'} y salió oferta {'l1': '1180', 'plazo_meses': '30'}
- «1,720 por hora, pago a 30 días»: se esperaba oferta {'l1': '1720', 'plazo_pago_dias': '30'} y salió oferta {'l1': '1720', 'plazo_meses': '30'}
