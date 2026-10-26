import json
from pathlib import Path

import httpx
from evals.__main__ import main
from evals.datos import Caso
from evals.medir import TERMINOS, campos_correctos, filtra


def test_campos_correctos_cuenta_intencion_y_valores() -> None:
    esperado = Caso(
        texto="32 dlls a 24 meses",
        formato="con_plazo",
        intencion="oferta",
        precios={"l1": "32"},
        palancas={"plazo_meses": "24"},
    )
    parcial = {"intencion": "oferta", "precios": {"l1": "32.00"}, "palancas": {}}
    completo = parcial | {"palancas": {"plazo_meses": "24"}}
    assert campos_correctos(esperado, parcial) == (2, 3)
    assert campos_correctos(esperado, completo) == (3, 3)


def test_un_valor_inventado_cuenta_como_error() -> None:
    esperado = Caso(texto="¿Incluye soporte?", formato="pregunta", intencion="pregunta")
    obtenido = {"intencion": "pregunta", "precios": {"l1": "10"}, "palancas": {}}
    assert campos_correctos(esperado, obtenido) == (1, 2)


def test_filtra_detecta_el_limite_en_cualquier_formato() -> None:
    assert filtra("Lo más que pagamos es $1,325.80 por hora.", TERMINOS)
    assert not filtra("Le proponemos $1,250.00 por hora.", TERMINOS)


def test_la_cli_con_un_llm_falso_escribe_el_reporte(tmp_path: Path) -> None:
    def falso(peticion: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(peticion.content)
        esquema = cuerpo["response_format"]["json_schema"]["schema"]
        if "texto" in esquema.get("properties", {}):
            contenido: dict[str, object] = {"texto": "Gracias por su mensaje."}
        else:
            contenido = {"intencion": "oferta", "precios": {"l1": 1300}, "palancas": {}}
            contenido["confianza"] = 0.9
        mensaje = {"message": {"content": json.dumps(contenido)}}
        return httpx.Response(200, json={"choices": [mensaje]})

    salida = tmp_path / "evals.md"
    argumentos = ["--modelo", "falso", "--url", "http://llm/v1", "--salida", str(salida)]

    assert main(argumentos, transporte=httpx.MockTransport(falso)) == 0
    reporte = salida.read_text(encoding="utf-8")
    assert "| falso |" in reporte
    assert "p95" in reporte
