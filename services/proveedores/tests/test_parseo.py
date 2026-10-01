from decimal import Decimal
from typing import Literal

import pytest
from proveedores.importacion import parseo
from proveedores.importacion.esquemas import (
    FilaContrato,
    FilaDesempeno,
    FilaProveedor,
    FilaServicio,
)
from proveedores.importacion.parseo import ErrorFila, agrupar_contratos, duplicados, leer_csv
from pydantic import BaseModel

SERVICIOS = (
    "codigo,nombre,categoria,unidad,moneda\n"
    "SAAS-OFI-EMP,Suite de productividad en la nube - plan empresarial,"
    "licencia_saas,usuario_mes,USD\n"
    "CONS-DEV-SR,Desarrollador(a) senior - hora,consultoria,hora,MXN\n"
)

CONTRATO_ENC = (
    "folio,rfc_proveedor,tipo,fecha_inicio,fecha_fin,moneda,plazo_pago_dias,"
    "sla_disponibilidad,tope_aumento_pct,cuota_implementacion,codigo_servicio,"
    "cantidad,precio_unitario\n"
)


def _contrato(folio: str = "C-0001", servicio: str = "SAAS-OFI-EMP", **cambios: str) -> str:
    valores = {
        "folio": folio,
        "rfc_proveedor": "NAZ210315AB1",
        "tipo": "nuevo",
        "fecha_inicio": "2025-01-01",
        "fecha_fin": "2025-12-31",
        "moneda": "USD",
        "plazo_pago_dias": "30",
        "sla_disponibilidad": "99.9",
        "tope_aumento_pct": "5",
        "cuota_implementacion": "",
        "codigo_servicio": servicio,
        "cantidad": "250",
        "precio_unitario": "21.5",
    }
    valores.update(cambios)
    return ",".join(valores.values()) + "\n"


def test_csv_valido_con_comas() -> None:
    resultado = leer_csv(SERVICIOS.encode(), FilaServicio)
    assert resultado.errores == []
    assert [numero for numero, _ in resultado.filas] == [2, 3]
    assert resultado.filas[0][1].codigo == "SAAS-OFI-EMP"


def test_csv_de_excel_en_espanol_con_bom_y_punto_y_coma() -> None:
    excel = SERVICIOS.replace(",", ";").encode("utf-8-sig")
    resultado = leer_csv(excel, FilaServicio)
    assert resultado.errores == []
    assert len(resultado.filas) == 2


def test_archivo_que_no_es_utf8_da_un_error_claro() -> None:
    contenido = SERVICIOS.replace("Suite", "Compañía").encode("cp1252")
    resultado = leer_csv(contenido, FilaServicio)
    assert resultado.filas == []
    assert resultado.errores == [
        ErrorFila(0, "archivo", "El archivo debe estar codificado en UTF-8")
    ]


def test_archivo_con_byte_nulo_se_rechaza_como_archivo() -> None:
    contenido = SERVICIOS.replace("Suite", "Su\x00ite").encode()
    resultado = leer_csv(contenido, FilaServicio)
    assert resultado.filas == []
    assert resultado.errores == [
        ErrorFila(0, "archivo", "El archivo contiene caracteres no válidos (byte nulo).")
    ]


def test_incidentes_criticos_tiene_cota_superior() -> None:
    encabezado = (
        "rfc_proveedor,periodo,sla_cumplimiento_pct,tiempo_resolucion_h,"
        "incidentes_criticos,entregas_a_tiempo_pct,satisfaccion\n"
    )
    fila = "NAZ210315AB1,2025-01-01,99.5,4.25,{},97,4.6\n"
    enorme = leer_csv((encabezado + fila.format("99999999999999999999")).encode(), FilaDesempeno)
    assert enorme.filas == []
    assert enorme.errores == [
        ErrorFila(2, "incidentes_criticos", "Debe ser menor o igual que 1000000")
    ]
    limite = leer_csv((encabezado + fila.format("1000000")).encode(), FilaDesempeno)
    assert limite.errores == []


def test_encabezado_con_columnas_faltantes_y_desconocidas() -> None:
    [error] = leer_csv(b"codigo,nombre,precio\nX,Y,1\n", FilaServicio).errores
    assert (error.fila, error.campo) == (1, "encabezado")
    assert "faltan: categoria, moneda, unidad" in error.mensaje
    assert "no reconocidas: precio" in error.mensaje


def test_errores_por_fila_en_espanol() -> None:
    texto = (
        CONTRATO_ENC
        + _contrato(precio_unitario="-3")
        + _contrato(folio="C-0002", fecha_inicio="2025-02-30")
    )
    errores = leer_csv(texto.encode(), FilaContrato).errores
    assert ErrorFila(2, "precio_unitario", "Debe ser mayor que 0") in errores
    assert ErrorFila(3, "fecha_inicio", "Fecha inválida; use AAAA-MM-DD") in errores


def test_opcionales_vacios_toman_su_valor_por_defecto() -> None:
    texto = CONTRATO_ENC + _contrato(sla_disponibilidad="", tope_aumento_pct="")
    [(_, fila)] = leer_csv(texto.encode(), FilaContrato).filas
    assert fila.sla_disponibilidad is None
    assert fila.tope_aumento_pct is None
    assert fila.cuota_implementacion == Decimal(0)


def test_obligatorio_vacio_y_fila_con_valores_de_mas() -> None:
    texto = (
        CONTRATO_ENC
        + _contrato(rfc_proveedor="")
        + _contrato(folio="C-0003").replace("\n", ",extra\n")
    )
    errores = leer_csv(texto.encode(), FilaContrato).errores
    assert ErrorFila(2, "rfc_proveedor", "Campo obligatorio") in errores
    assert ErrorFila(3, "fila", "La fila tiene más valores que columnas") in errores


def test_vigencia_invertida() -> None:
    texto = CONTRATO_ENC + _contrato(fecha_fin="2024-01-01")
    assert leer_csv(texto.encode(), FilaContrato).errores == [
        ErrorFila(2, "fila", "fecha_fin debe ser posterior a fecha_inicio")
    ]


def test_periodo_debe_ser_primer_dia_del_mes() -> None:
    texto = (
        "rfc_proveedor,periodo,sla_cumplimiento_pct,tiempo_resolucion_h,"
        "incidentes_criticos,entregas_a_tiempo_pct,satisfaccion\n"
        "NAZ210315AB1,2025-03-15,99.5,4.25,0,97,4.6\n"
    )
    assert leer_csv(texto.encode(), FilaDesempeno).errores == [
        ErrorFila(2, "periodo", "El periodo debe ser el primer día del mes")
    ]


def test_categorias_separadas_por_barra_y_activo_por_defecto() -> None:
    texto = (
        "rfc,nombre,tamano,categorias,contacto_nombre,contacto_email\n"
        "NAZ210315AB1,Nube Azteca S.A. de C.V.,mediana,licencia_saas|nube,"
        "Laura Méndez,ventas01@proveedor01.example\n"
    )
    [(_, fila)] = leer_csv(texto.encode(), FilaProveedor).filas
    assert fila.categorias == ["licencia_saas", "nube"]
    assert fila.activo is True


def test_limite_de_filas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parseo, "MAX_FILAS", 1)
    resultado = leer_csv(SERVICIOS.encode(), FilaServicio)
    assert len(resultado.filas) == 1
    assert resultado.errores == [ErrorFila(3, "archivo", "El archivo excede 1 filas")]


def test_duplicados_por_clave() -> None:
    repetida = SERVICIOS.splitlines(keepends=True)[1]
    resultado = leer_csv((SERVICIOS + repetida).encode(), FilaServicio)
    assert duplicados(resultado, lambda fila: fila.codigo, "codigo") == [
        ErrorFila(4, "codigo", "Duplicado de la fila 2")
    ]


def test_agrupar_contratos_detecta_cabeceras_distintas_y_servicios_repetidos() -> None:
    texto = (
        CONTRATO_ENC
        + _contrato()
        + _contrato(servicio="CONS-DEV-SR", plazo_pago_dias="60")
        + _contrato()
    )
    grupos, errores = agrupar_contratos(leer_csv(texto.encode(), FilaContrato).filas)
    assert list(grupos) == ["C-0001"]
    assert (
        ErrorFila(3, "folio", "Los datos del contrato C-0001 no coinciden con la fila 2") in errores
    )
    assert ErrorFila(4, "codigo_servicio", "Servicio repetido en el contrato C-0001") in errores


def test_csv_mal_formado_no_lanza_excepcion() -> None:
    # Una comilla sin cerrar seguida de más de 128 KB desborda el límite de campo de csv.
    texto = "codigo,nombre,categoria,unidad,moneda\n" + '"' + "x" * 140_000 + "\n"
    resultado = leer_csv(texto.encode(), FilaServicio)
    assert resultado.filas == []
    assert resultado.errores == [
        ErrorFila(
            0,
            "archivo",
            "El archivo CSV está mal formado "
            "(revise comillas sin cerrar o campos demasiado largos)",
        )
    ]


def test_valor_no_permitido_lista_las_opciones_en_espanol() -> None:
    texto = CONTRATO_ENC + _contrato(moneda="EUR")
    assert leer_csv(texto.encode(), FilaContrato).errores == [
        ErrorFila(2, "moneda", "Valor no permitido; opciones: MXN o USD")
    ]
    cuatro = SERVICIOS.replace("consultoria", "otra")
    assert leer_csv(cuatro.encode(), FilaServicio).errores == [
        ErrorFila(
            3,
            "categoria",
            "Valor no permitido; opciones: licencia_saas, nube, consultoria o soporte",
        )
    ]


def test_valor_no_permitido_sin_opciones_legibles_no_muestra_ingles() -> None:
    class Numeros(BaseModel):
        n: Literal[1, 2]

    assert leer_csv(b"n\n3\n", Numeros).errores == [ErrorFila(2, "n", "Valor no permitido")]


def test_numero_no_finito_y_fecha_con_hora_en_espanol() -> None:
    texto = (
        CONTRATO_ENC
        + _contrato(precio_unitario="NaN")
        + _contrato(folio="C-0002", fecha_inicio="2025-01-01T10:00:00")
    )
    errores = leer_csv(texto.encode(), FilaContrato).errores
    assert ErrorFila(2, "precio_unitario", "Debe ser un número finito") in errores
    assert ErrorFila(3, "fecha_inicio", "Fecha inválida; use AAAA-MM-DD") in errores


def test_encabezado_con_columnas_duplicadas() -> None:
    texto = "codigo,nombre,nombre,categoria,unidad,moneda\nX,Y,Z,nube,hora,MXN\n"
    assert leer_csv(texto.encode(), FilaServicio).errores == [
        ErrorFila(1, "encabezado", "Columnas inválidas; duplicadas: nombre")
    ]


def test_celda_con_solo_espacios_equivale_a_vacia() -> None:
    texto = CONTRATO_ENC + _contrato(sla_disponibilidad="   ", cuota_implementacion="  ")
    [(_, fila)] = leer_csv(texto.encode(), FilaContrato).filas
    assert fila.sla_disponibilidad is None
    assert fila.cuota_implementacion == Decimal(0)
    obligatorio = CONTRATO_ENC + _contrato(rfc_proveedor="   ")
    assert leer_csv(obligatorio.encode(), FilaContrato).errores == [
        ErrorFila(2, "rfc_proveedor", "Campo obligatorio")
    ]


def test_rfc_rechaza_digitos_no_ascii() -> None:
    arabes = "٢١٠٣١٥"
    texto = CONTRATO_ENC + _contrato(rfc_proveedor=f"NAZ{arabes}AB1")
    assert leer_csv(texto.encode(), FilaContrato).errores == [
        ErrorFila(2, "rfc_proveedor", "Formato inválido")
    ]
