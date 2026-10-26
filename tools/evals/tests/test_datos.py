import json
from collections import Counter
from pathlib import Path

from evals.datos import FORMATOS, SEMILLA, a_json, generar

DATOS = Path(__file__).resolve().parents[1] / "datos"


def test_generar_es_determinista_y_tiene_150_y_30() -> None:
    casos, ataques = generar(SEMILLA)
    assert (len(casos), len(ataques)) == (150, 30)
    assert generar(SEMILLA) == (casos, ataques)
    por_formato = Counter(caso.formato for caso in casos)
    assert set(por_formato) == set(FORMATOS)
    assert min(por_formato.values()) >= 5
    assert Counter(ataque.tipo for ataque in ataques) == {
        "inyeccion": 10,
        "suplantacion": 10,
        "pide_secretos": 10,
    }


def test_los_archivos_versionados_coinciden_con_el_generador() -> None:
    casos, ataques = generar(SEMILLA)
    assert json.loads((DATOS / "mensajes.json").read_text(encoding="utf-8")) == a_json(casos)
    assert json.loads((DATOS / "ataques.json").read_text(encoding="utf-8")) == a_json(ataques)
