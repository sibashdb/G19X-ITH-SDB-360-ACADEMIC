import comun


def test_paquete_se_importa_con_su_version() -> None:
    assert comun.__version__ == "0.1.0"
