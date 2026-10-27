import json
from collections import Counter
from pathlib import Path

from evals.datos import FORMATOS, SEMILLA, a_json, generar, generar_varias

DATOS = Path(__file__).resolve().parents[1] / "datos"


def test_generar_varias_pone_precios_a_una_dos_o_tres_lineas() -> None:
    """En producción hay hasta 20 líneas: los evals también miden a cuál va cada precio (I4)."""
    casos = generar_varias(SEMILLA)
    assert len(casos) == 30
    assert generar_varias(SEMILLA) == casos
    assert Counter(len(caso.precios) for caso in casos) == {1: 10, 2: 10, 3: 10}
    assert {clave for caso in casos for clave in caso.precios} == {"l1", "l2", "l3"}
    assert all(caso.intencion == "oferta" and not caso.palancas for caso in casos)
    varias = json.loads((DATOS / "mensajes_varias.json").read_text(encoding="utf-8"))
    assert varias == a_json(casos)


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
