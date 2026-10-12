from collections import defaultdict
from pathlib import Path

import pytest
import sklearn
from inteligencia.dominio.precios import Observacion
from inteligencia.modelo import (
    Consulta,
    DatosInsuficientes,
    ajustar_modelo,
    cargar_modelo,
    consulta_de,
    entrenar,
    guardar_modelo,
)
from inteligencia.precio_justo import referencias

INFLACION = 0.045


def _por_categoria(datos: list[Observacion]) -> dict[str, list[Observacion]]:
    grupos: dict[str, list[Observacion]] = defaultdict(list)
    for o in datos:
        grupos[o.categoria].append(o)
    return grupos


def test_entrena_valida_y_solo_promueve_si_mejora_la_linea_base(
    generadas: list[Observacion],
) -> None:
    resultado = entrenar(generadas, INFLACION, version=1)
    assert resultado.mape < 0.15
    assert resultado.mape_linea_base < 0.15
    assert 0.3 <= resultado.cobertura <= 0.7
    assert 0.3 <= resultado.cobertura_linea_base <= 0.7
    assert resultado.pinball > 0
    assert resultado.promovido == (resultado.mape < resultado.mape_linea_base)
    assert resultado.observaciones == len(generadas)
    assert resultado.datos_hasta == max(o.fecha for o in generadas)
    if resultado.modelo is not None:
        assert resultado.modelo.version == 1


def test_las_predicciones_estan_ordenadas_y_son_positivas(generadas: list[Observacion]) -> None:
    modelo = ajustar_modelo(generadas, INFLACION, version=3)
    bandas = modelo.predecir([consulta_de(o) for o in generadas[:50]])
    assert len(bandas) == 50
    assert all(0 < b.p25 <= b.p50 <= b.p75 for b in bandas)
    assert modelo.predecir([]) == []


def test_un_servicio_que_el_modelo_no_conoce_usa_la_linea_base(
    generadas: list[Observacion],
) -> None:
    servicio = generadas[0].servicio
    modelo = ajustar_modelo([o for o in generadas if o.servicio != servicio], INFLACION, 2)
    fecha = max(o.fecha for o in generadas)
    desconocida = Consulta(servicio, generadas[0].categoria, generadas[0].moneda, 100.0, 12, fecha)
    conocida_obs = next(o for o in generadas if o.servicio != servicio)
    conocida = Consulta(
        conocida_obs.servicio, conocida_obs.categoria, conocida_obs.moneda, 100.0, 12, fecha
    )
    [primera, segunda] = referencias(
        [desconocida, conocida], _por_categoria(generadas), modelo, INFLACION
    )
    assert primera is not None and primera.metodo == "linea_base"
    assert segunda is not None and (segunda.metodo, segunda.version) == ("modelo", 2)


def test_sin_modelo_usa_la_linea_base(generadas: list[Observacion]) -> None:
    o = generadas[0]
    [referencia] = referencias(
        [Consulta(o.servicio, o.categoria, o.moneda, 100.0, 12, o.fecha)],
        _por_categoria(generadas),
        None,
        INFLACION,
    )
    assert referencia is not None and referencia.metodo == "linea_base"


def test_sin_datos_suficientes_no_entrena(generadas: list[Observacion]) -> None:
    with pytest.raises(DatosInsuficientes):
        entrenar(generadas[:10], INFLACION, version=1)


def test_guardar_y_cargar(generadas: list[Observacion], tmp_path: Path) -> None:
    modelo = ajustar_modelo(generadas, INFLACION, version=5)
    ruta = tmp_path / "modelo-v5.joblib"
    guardar_modelo(modelo, ruta)
    cargado = cargar_modelo(ruta)
    consulta = consulta_de(generadas[0])
    assert cargado.version == 5
    assert cargado.version_sklearn == sklearn.__version__
    assert cargado.predecir([consulta]) == modelo.predecir([consulta])


def test_si_el_modelo_falla_al_predecir_se_usa_la_linea_base(
    generadas: list[Observacion],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    modelo = ajustar_modelo(generadas, INFLACION, version=4)

    def falla(_consultas: object) -> None:
        raise ValueError("el artefacto no es compatible con esta versión")

    monkeypatch.setattr(modelo, "predecir", falla)
    o = generadas[0]
    consulta = Consulta(o.servicio, o.categoria, o.moneda, 100.0, 12, o.fecha)
    [con_falla] = referencias([consulta], _por_categoria(generadas), modelo, INFLACION)
    [sin_modelo] = referencias([consulta], _por_categoria(generadas), None, INFLACION)
    assert con_falla is not None and con_falla.metodo == "linea_base"
    assert con_falla == sin_modelo
    assert "El modelo de precios v4 falló al predecir" in caplog.text
