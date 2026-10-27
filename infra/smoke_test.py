"""Prueba de humo contra el stack de Docker Compose: uv run python infra/smoke_test.py"""

import json
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

BASE = "http://localhost:8080"
BUZON = "http://localhost:8025"
CORREO_HUMO = "humo.prueba@plataforma.example"
ASUNTO_CORREO = "Defina su contraseña de PluriOne"
REALM = Path(__file__).parent / "keycloak" / "realm-plataforma.json"


def verificar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise SystemExit(f"FALLA: {mensaje}")


def contrasena_de_desarrollo(usuario: str) -> str:
    realm = json.loads(REALM.read_text(encoding="utf-8"))
    [datos] = [u for u in realm["users"] if u["username"] == usuario]
    return str(datos["credentials"][0]["value"])


def token_de(cliente: httpx.Client, usuario: str) -> dict[str, str]:
    respuesta = cliente.post(
        "/auth/realms/plataforma/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "pruebas-humo",
            "username": usuario,
            "password": contrasena_de_desarrollo(usuario),
        },
    )
    verificar(respuesta.status_code == 200, f"{usuario} no obtuvo token: {respuesta.text}")
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def correos_de_humo() -> dict[str, str]:
    """ID -> asunto de los correos que Mailpit tiene para el usuario de humo."""
    respuesta = httpx.get(
        f"{BUZON}/api/v1/search", params={"query": f"to:{CORREO_HUMO}"}, timeout=10
    )
    verificar(respuesta.status_code == 200, f"Mailpit no respondió: {respuesta.text}")
    return {m["ID"]: m["Subject"] for m in respuesta.json().get("messages", [])}


def sesiones_de_admin1(cliente: httpx.Client, admin: dict[str, str]) -> set[str]:
    """IDs de los inicios de sesión de admin1 en las 100 entradas más recientes de la bitácora."""
    respuesta = cliente.get(
        "/api/administracion/actividad",
        params={"tipo": "sesiones", "tamano": 100},
        headers=admin,
    )
    verificar(respuesta.status_code == 200, f"consultar la actividad falló: {respuesta.text}")
    return {e["id"] for e in respuesta.json()["elementos"] if e["actor_nombre"] == "admin1"}


def verificar_administracion(cliente: httpx.Client) -> None:
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")
    api = "/api/administracion"
    verificar(
        cliente.get(f"{api}/usuarios", headers=comprador).status_code == 403,
        "un comprador no debe gestionar usuarios",
    )
    lista = cliente.get(f"{api}/usuarios", headers=admin)
    verificar(lista.status_code == 200, f"listar usuarios falló: {lista.text}")

    # Usuario de humo reutilizable: se crea la primera vez y después se reactiva.
    datos = {
        "usuario": "humo.prueba",
        "nombre": "Humo",
        "apellidos": "Prueba",
        "correo": CORREO_HUMO,
        "roles": ["comprador"],
        "metodo": "invitacion",
    }
    # Los correos de corridas anteriores siguen en Mailpit: solo cuenta uno nuevo.
    correos_antes = set(correos_de_humo())
    alta = cliente.post(f"{api}/usuarios", json=datos, headers=admin)
    if alta.status_code == 201:
        usuario_id = alta.json()["usuario"]["id"]
        verificar(alta.json()["correo_enviado"] is True, "la invitación no se envió")
    else:
        verificar(alta.status_code == 409, f"alta falló: {alta.text}")
        # Con usuario y correo repetidos, Keycloak reporta primero el correo.
        verificar(
            alta.json().get("codigo") in ("usuario_duplicado", "correo_duplicado"),
            f"alta falló: {alta.text}",
        )
        [existente] = cliente.get(
            f"{api}/usuarios", params={"busqueda": "humo.prueba"}, headers=admin
        ).json()["elementos"]
        usuario_id = existente["id"]
        activar = cliente.post(f"{api}/usuarios/{usuario_id}/activar", headers=admin)
        verificar(activar.status_code == 200, f"activar falló: {activar.text}")
        correo = cliente.post(
            f"{api}/usuarios/{usuario_id}/contrasena", json={"metodo": "correo"}, headers=admin
        )
        verificar(correo.status_code == 200, f"el correo no se envió: {correo.text}")

    nuevos = [a for id_, a in correos_de_humo().items() if id_ not in correos_antes]
    verificar(
        ASUNTO_CORREO in nuevos,
        f"no llegó a Mailpit un correo nuevo con el asunto esperado: {nuevos}",
    )

    baja = cliente.post(f"{api}/usuarios/{usuario_id}/desactivar", headers=admin)
    verificar(
        baja.status_code == 200 and baja.json()["activo"] is False, f"desactivar falló: {baja.text}"
    )
    tipos = [
        e["tipo"]
        for e in cliente.get(
            f"{api}/actividad", params={"persona": usuario_id}, headers=admin
        ).json()["elementos"]
    ]
    verificar(
        "usuario.desactivado" in tipos and "usuario.correo_contrasena" in tipos,
        f"la bitácora no registró las acciones: {tipos}",
    )

    # Un inicio de sesión nuevo llega a la bitácora en menos de un minuto (lectura cada 30 s).
    # Los de corridas anteriores no cuentan: se compara contra los que ya estaban.
    sesiones_antes = sesiones_de_admin1(cliente, admin)
    admin = token_de(cliente, "admin1")
    limite = time.monotonic() + 75
    while time.monotonic() < limite:
        if sesiones_de_admin1(cliente, admin) - sesiones_antes:
            return
        time.sleep(5)
    raise SystemExit("FALLA: los inicios de sesión no llegaron a la bitácora en 75 s")


SERVICIO_HUMO = "HUMO-SERV"
# Los eventos viajan por el outbox en orden: tras un reproceso o una importación grande, los
# nuevos esperan detrás del resto (con el dataset completo, hasta un par de minutos).
ESPERA_EVENTOS_S = 180


def eventos_del_servicio_de_humo(cliente: httpx.Client, admin: dict[str, str]) -> set[str]:
    """IDs de los registros del catálogo sobre el servicio de humo (los 100 más recientes)."""
    respuesta = cliente.get(
        "/api/administracion/actividad",
        params={"tipo": "catalogo", "tamano": 100},
        headers=admin,
    )
    verificar(respuesta.status_code == 200, f"consultar la actividad falló: {respuesta.text}")
    return {e["id"] for e in respuesta.json()["elementos"] if e["objeto_id"] == SERVICIO_HUMO}


def verificar_operacion(cliente: httpx.Client) -> None:
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")

    estado = cliente.get("/api/administracion/estado", headers=admin)
    verificar(estado.status_code == 200, f"el estado del sistema falló: {estado.text}")
    caidos = [s["nombre"] for s in estado.json()["servicios"] if s["estado"] == "caido"]
    verificar(not caidos, f"servicios caídos según el estado del sistema: {caidos}")
    resumen = cliente.get("/api/administracion/resumen", headers=admin)
    verificar(
        resumen.status_code == 200 and resumen.json()["usuarios_activos"] is not None,
        f"el resumen del panel falló: {resumen.text}",
    )
    inactivos = cliente.get(
        "/api/proveedores/servicios", params={"incluir_inactivos": "true"}, headers=comprador
    )
    verificar(inactivos.status_code == 403, "un comprador no debe ver los servicios inactivos")

    # Servicio de humo reutilizable: se crea la primera vez; cada corrida lo desactiva y lo
    # reactiva. Solo cuentan los registros nuevos de esta corrida.
    antes = eventos_del_servicio_de_humo(cliente, admin)
    alta = cliente.post(
        "/api/proveedores/servicios",
        json={
            "codigo": SERVICIO_HUMO,
            "nombre": "Servicio de la prueba de humo",
            "categoria": "soporte",
            "unidad": "ticket",
            "moneda": "MXN",
        },
        headers=admin,
    )
    verificar(alta.status_code in (201, 409), f"el alta del servicio falló: {alta.text}")
    for activo in (False, True):
        cambio = cliente.patch(
            f"/api/proveedores/servicios/{SERVICIO_HUMO}", json={"activo": activo}, headers=admin
        )
        verificar(
            cambio.status_code == 200 and cambio.json()["activo"] is activo,
            f"cambiar el estado del servicio falló: {cambio.text}",
        )
    # Los cambios viajan por el outbox y RabbitMQ hasta la bitácora de administración.
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while time.monotonic() < limite:
        if len(eventos_del_servicio_de_humo(cliente, admin) - antes) >= 2:
            return
        time.sleep(1)
    raise SystemExit(
        f"FALLA: los cambios del catálogo no llegaron a la bitácora en {ESPERA_EVENTOS_S} s"
    )


def verificar_inteligencia(cliente: httpx.Client) -> None:
    """La copia local de inteligencia recibe lo importado y los cambios del catálogo."""
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")
    # Inteligencia se llena por eventos: con el dataset completo tarda de uno a dos minutos.
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while True:
        tablero = cliente.get("/api/inteligencia/tablero", headers=comprador)
        verificar(tablero.status_code == 200, f"el tablero de inteligencia falló: {tablero.text}")
        cuerpo = tablero.json()
        if cuerpo["total_proveedores"] > 0 and Decimal(cuerpo["gasto_anual"]) > 0:
            break
        verificar(
            time.monotonic() < limite,
            f"los datos importados no llegaron a inteligencia en {ESPERA_EVENTOS_S} s",
        )
        time.sleep(2)
    # Cada espera puede durar hasta ESPERA_EVENTOS_S y los tokens duran 300 s: se piden de nuevo.
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")
    # El servicio de humo ya está en la copia de corridas anteriores: un nombre nuevo en cada
    # corrida prueba que el cambio del catálogo llega por el evento.
    nombre = f"Servicio de la prueba de humo {uuid.uuid4().hex[:8]}"
    cambio = cliente.patch(
        f"/api/proveedores/servicios/{SERVICIO_HUMO}", json={"nombre": nombre}, headers=admin
    )
    verificar(cambio.status_code == 200, f"renombrar el servicio de humo falló: {cambio.text}")
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while True:
        servicios = cliente.get("/api/inteligencia/precios/servicios", headers=comprador)
        verificar(
            servicios.status_code == 200, f"los servicios de precios fallaron: {servicios.text}"
        )
        if any(s["codigo"] == SERVICIO_HUMO and s["nombre"] == nombre for s in servicios.json()):
            break
        verificar(
            time.monotonic() < limite,
            f"el nombre nuevo del servicio de humo no llegó a inteligencia en {ESPERA_EVENTOS_S} s",
        )
        time.sleep(1)
    admin = token_de(cliente, "admin1")
    comprador = token_de(cliente, "comprador1")
    copia = cliente.get("/api/inteligencia/datos", headers=admin)
    verificar(
        copia.status_code == 200 and copia.json()["registros"]["contratos"] > 0,
        f"los datos de inteligencia fallaron: {copia.text}",
    )
    sin_permiso = cliente.get("/api/inteligencia/datos", headers=comprador)
    verificar(sin_permiso.status_code == 403, "un comprador no debe ver los datos de inteligencia")


def esperar_actividad(cliente: httpx.Client, folio: str, tipo: str) -> None:
    """Espera a que el evento `tipo` de la negociación `folio` llegue a la Actividad."""
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while True:
        admin = token_de(cliente, "admin1")
        actividad = cliente.get(
            "/api/administracion/actividad",
            params={"tipo": "negociacion", "tamano": 100},
            headers=admin,
        ).json()["elementos"]
        if any(a["objeto_id"] == folio and a["tipo"] == tipo for a in actividad):
            return
        verificar(
            time.monotonic() < limite,
            f"{tipo} de la negociación {folio} no llegó a la Actividad en {ESPERA_EVENTOS_S} s",
        )
        time.sleep(2)


def publicar_compra(
    cliente: httpx.Client, cantidad: str
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any], dict[str, str]]:
    """Crea y publica una compra de humo con un proveedor activo y abre su portal con el enlace.

    Devuelve el token del comprador, el proveedor, el evento (con el `sesion_id` de su única
    sesión) y la cabecera de autorización del portal.
    """
    comprador = token_de(cliente, "comprador1")
    servicios = cliente.get("/api/inteligencia/precios/servicios", headers=comprador).json()
    servicio = next(s for s in servicios if s["observaciones"] > 0)
    proveedores = cliente.get("/api/proveedores/proveedores", headers=comprador).json()
    proveedor = next(p for p in proveedores["elementos"] if p["activo"])
    cuerpo = {
        "tipo": "compra",
        "titulo": f"Prueba de humo {uuid.uuid4().hex[:8]}",
        "fecha_limite": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "lineas": [{"codigo_servicio": servicio["codigo"], "cantidad": cantidad}],
        "proveedores": [proveedor["id"]],
    }
    # La copia de proveedores de negociacion se llena por eventos: se reintenta mientras llega.
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while True:
        creado = cliente.post("/api/negociacion/eventos", json=cuerpo, headers=comprador)
        if creado.status_code == 201:
            break
        verificar(
            creado.status_code == 422 and time.monotonic() < limite,
            f"crear la negociación de humo falló: {creado.text}",
        )
        time.sleep(2)
        comprador = token_de(cliente, "comprador1")
    evento = creado.json()
    verificar(
        evento["lineas"][0]["limite"] is not None,
        f"la línea no trae la referencia de precios: {evento['lineas'][0]}",
    )
    publicado = cliente.post(f"/api/negociacion/eventos/{evento['id']}/publicar", headers=comprador)
    verificar(publicado.status_code == 200, f"publicar la negociación falló: {publicado.text}")
    [enlace] = publicado.json()["enlaces"]
    # El enlace lleva el token de la invitación: ningún mensaje de falla lo incluye.
    verificar(
        enlace["correo_estado"] == "enviado",
        f"la invitación no salió (correo_estado: {enlace['correo_estado']})",
    )
    evento["sesion_id"] = enlace["sesion_id"]
    portal = {"Authorization": f"Invitacion {enlace['enlace'].split('#t=')[1]}"}
    verificar(
        cliente.get("/api/negociacion/portal/sesion", headers=portal).status_code == 200,
        "el portal no abrió la sesión con el enlace de la invitación",
    )
    return comprador, proveedor, evento, portal


# Con el LLM, el agente tiene hasta 18 s para redactar cada respuesta (ia_presupuesto_s).
ESPERA_AGENTE_S = 30


def ofertar(cliente: httpx.Client, portal: dict[str, str], valores: dict[str, Any]) -> Any:
    """Envía una oferta por el portal y devuelve la vista que el proveedor ve después."""
    respuesta = cliente.post(
        "/api/negociacion/portal/ofertas",
        json={"valores": valores},
        headers=portal | {"Idempotency-Key": uuid.uuid4().hex},
        timeout=ESPERA_AGENTE_S,
    )
    verificar(respuesta.status_code == 200, f"la oferta en el portal falló: {respuesta.text}")
    return respuesta.json()


def verificar_negociacion(cliente: httpx.Client) -> None:
    """Una compra de humo: se publica, la invitación llega a Mailpit y el agente responde."""
    comprador, _, evento, portal = publicar_compra(cliente, "10")
    linea = evento["lineas"][0]
    vista = ofertar(cliente, portal, {"precios": {linea["id"]: str(Decimal(linea["limite"]) * 2)}})
    verificar(
        vista["mensajes"][-1]["autor"] == "agente",
        f"el agente no respondió en el portal: {vista['mensajes'][-1]}",
    )
    # Con LLM, el agente interpreta el mensaje y redacta; sin LLM, pide usar el formulario.
    escrito = cliente.post(
        "/api/negociacion/portal/mensajes",
        json={"texto": "¿Cuándo empezaría el servicio?"},
        headers=portal | {"Idempotency-Key": uuid.uuid4().hex},
        timeout=ESPERA_AGENTE_S,
    )
    verificar(escrito.status_code == 200, f"el mensaje libre en el portal falló: {escrito.text}")
    verificar(
        escrito.json()["mensajes"][-1]["autor"] == "agente",
        "el agente no contestó el mensaje libre",
    )
    correos = httpx.get(
        f"{BUZON}/api/v1/search", params={"query": f'subject:"{evento["folio"]}"'}, timeout=10
    ).json()
    verificar(bool(correos.get("messages")), "la invitación a negociar no llegó a Mailpit")
    cancelada = cliente.post(
        f"/api/negociacion/eventos/{evento['id']}/cancelar",
        json={"motivo": "Prueba de humo"},
        headers=comprador,
    )
    verificar(cancelada.status_code == 200, f"cancelar la negociación falló: {cancelada.text}")
    # La publicación llega a la Actividad por RabbitMQ.
    esperar_actividad(cliente, evento["folio"], "negociacion.publicada")


def esperar_estado(cliente: httpx.Client, evento_id: str, estado: str) -> None:
    """Espera a que el evento llegue a ese estado (el cierre ocurre con la última oferta)."""
    limite = time.monotonic() + 30
    while True:
        comprador = token_de(cliente, "comprador1")
        actual = cliente.get(f"/api/negociacion/eventos/{evento_id}", headers=comprador).json()
        if actual["estado"] == estado:
            return
        verificar(
            time.monotonic() < limite,
            f"el evento quedó en «{actual['estado']}» y se esperaba «{estado}»",
        )
        time.sleep(1)


def verificar_adjudicacion(cliente: httpx.Client) -> None:
    """De la negociación al contrato: acuerdo, evaluación, propuesta, aprobación y contrato."""
    # Una cantidad grande: el costo debe superar el umbral para que pase por el aprobador.
    cantidad = "1000"
    comprador, proveedor, evento, portal = publicar_compra(cliente, cantidad)
    linea = evento["lineas"][0]
    # El agente contesta con una propuesta (la primera oferta va fuera del límite); ofrecerle esa
    # propuesta cierra el acuerdo. Si no propusiera, se ofrece el límite de la línea.
    valores = {"precios": {linea["id"]: str(Decimal(linea["limite"]) * 2)}}
    for _ in range(evento["rondas_max"]):
        vista = ofertar(cliente, portal, valores)
        if vista["estado"] == "acuerdo_tentativo":
            break
        valores = vista["ultima_propuesta"] or {"precios": {linea["id"]: linea["limite"]}}
    verificar(vista["estado"] == "acuerdo_tentativo", f"el agente no aceptó el acuerdo: {vista}")
    esperar_estado(cliente, evento["id"], "en_evaluacion")

    api = f"/api/negociacion/eventos/{evento['id']}"
    comprador = token_de(cliente, "comprador1")
    evaluacion = cliente.get(f"{api}/evaluacion", headers=comprador)
    verificar(evaluacion.status_code == 200, f"la evaluación falló: {evaluacion.text}")
    recomendacion = evaluacion.json()["recomendacion"]
    verificar(recomendacion is not None, f"la evaluación no trae recomendación: {evaluacion.text}")
    verificar(
        recomendacion["recomendado"] == evento["sesion_id"],
        f"la recomendación no es el único acuerdo: {recomendacion['recomendado']}",
    )
    costo = Decimal(recomendacion["candidatos"][0]["costo_total_mxn"])
    umbral = Decimal(recomendacion["umbral_aprobacion"])
    verificar(
        costo > umbral,
        f"la compra de humo cuesta {costo} MXN y no supera el umbral de aprobación de {umbral} "
        f"MXN, así que no pasaría por el aprobador: suba la cantidad ({cantidad})",
    )

    propuesta = cliente.post(
        f"{api}/adjudicacion", json={"sesion_id": recomendacion["recomendado"]}, headers=comprador
    )
    verificar(propuesta.status_code == 200, f"proponer la adjudicación falló: {propuesta.text}")
    vigente = propuesta.json()["vigente"]
    # La regla de aprobación (spec §4.3): sobre el umbral, la decide un aprobador.
    verificar(
        vigente["requiere_aprobacion"] is True
        and "umbral" in vigente["motivo_aprobacion"]
        and vigente["estado"] == "pendiente",
        f"la propuesta sobre el umbral debía quedar pendiente: {vigente}",
    )
    esperar_estado(cliente, evento["id"], "pendiente_aprobacion")
    aprobacion = {"adjudicacion_id": vigente["id"]}
    sin_rol = cliente.post(f"{api}/adjudicacion/aprobar", json=aprobacion, headers=comprador)
    verificar(sin_rol.status_code == 403, "un comprador no debe aprobar una adjudicación")
    aprobador = token_de(cliente, "aprobador1")
    otra = {"adjudicacion_id": str(uuid.uuid4())}
    distinta = cliente.post(f"{api}/adjudicacion/aprobar", json=otra, headers=aprobador)
    verificar(
        distinta.status_code == 409 and distinta.json().get("codigo") == "propuesta_distinta",
        f"aprobar otra propuesta debía dar 409 propuesta_distinta: {distinta.text}",
    )
    aprobada = cliente.post(f"{api}/adjudicacion/aprobar", json=aprobacion, headers=aprobador)
    verificar(aprobada.status_code == 200, f"aprobar la adjudicación falló: {aprobada.text}")
    vigente = aprobada.json()["vigente"]
    verificar(
        vigente["estado"] == "aprobada" and vigente["contrato_folio"] is not None,
        f"la adjudicación no quedó aprobada: {vigente}",
    )
    folio = f"C-{evento['folio']}"
    verificar(vigente["contrato_folio"] == folio, f"folio de contrato inesperado: {vigente}")
    esperar_estado(cliente, evento["id"], "adjudicado")

    # El contrato viaja por el outbox y RabbitMQ hasta proveedores.
    limite = time.monotonic() + ESPERA_EVENTOS_S
    while True:
        comprador = token_de(cliente, "comprador1")
        contratos = cliente.get(
            f"/api/proveedores/proveedores/{proveedor['id']}/contratos", headers=comprador
        )
        verificar(contratos.status_code == 200, f"consultar los contratos falló: {contratos.text}")
        contrato = next((c for c in contratos.json() if c["folio"] == folio), None)
        if contrato is not None:
            break
        verificar(
            time.monotonic() < limite,
            f"el contrato {folio} no llegó a proveedores en {ESPERA_EVENTOS_S} s",
        )
        time.sleep(2)
    [contratado] = contrato["lineas"]
    verificar(
        contrato["tipo"] == "nuevo"
        and contratado["codigo_servicio"] == linea["codigo_servicio"]
        and Decimal(contratado["cantidad"]) == Decimal(cantidad),
        f"el contrato no trae lo adjudicado: {contrato}",
    )
    # La adjudicación también llega a la Actividad por RabbitMQ.
    esperar_actividad(cliente, evento["folio"], "negociacion.adjudicada")


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=10) as cliente:
        spa = cliente.get("/")
        verificar(spa.status_code == 200 and 'id="root"' in spa.text, "el gateway no sirve la SPA")
        verificar(
            "frame-ancestors 'none'" in spa.headers.get("content-security-policy", ""),
            "falta la cabecera CSP",
        )
        acceso = cliente.get(
            "/auth/realms/plataforma/protocol/openid-connect/auth",
            params={
                "client_id": "web",
                "response_type": "code",
                "scope": "openid",
                "redirect_uri": f"{BASE}/",
                "code_challenge": "A" * 43,
                "code_challenge_method": "S256",
            },
        )
        verificar(
            acceso.status_code == 200 and "login/plataforma/css/plataforma.css" in acceso.text,
            "Keycloak no aplica el tema de inicio de sesión 'plataforma'",
        )
        verificar(
            "Pague el precio justo y elija a los mejores proveedores" in acceso.text,
            "el inicio de sesión no muestra el panel con el propósito del producto",
        )
        sin_token = cliente.get("/api/proveedores/proveedores")
        verificar(sin_token.status_code == 401, f"sin token se esperaba 401: {sin_token.text}")

        token = cliente.post(
            "/auth/realms/plataforma/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "pruebas-humo",
                "username": "comprador1",
                "password": contrasena_de_desarrollo("comprador1"),
            },
        )
        verificar(token.status_code == 200, f"Keycloak no emitió token: {token.text}")
        cabeceras = {"Authorization": f"Bearer {token.json()['access_token']}"}

        # Sin OTP: admin y aprobador obtienen token solo con usuario y contraseña.
        for usuario in ("admin1", "aprobador1"):
            respuesta = cliente.post(
                "/auth/realms/plataforma/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "pruebas-humo",
                    "username": usuario,
                    "password": contrasena_de_desarrollo(usuario),
                },
            )
            verificar(
                respuesta.status_code == 200,
                f"{usuario} no obtuvo token solo con contraseña (¿OTP pendiente?): "
                f"{respuesta.text}",
            )

        lista = cliente.get("/api/proveedores/proveedores", headers=cabeceras)
        verificar(lista.status_code == 200, f"listar proveedores falló: {lista.text}")
        verificar(bool(lista.headers.get("x-request-id")), "falta X-Request-ID en la respuesta")

        importar = cliente.post(
            "/api/proveedores/importaciones/servicios",
            headers=cabeceras,
            files={"archivo": ("s.csv", b"codigo,nombre,categoria,unidad,moneda\n", "text/csv")},
        )
        verificar(importar.status_code == 403, f"un comprador no debe importar: {importar.text}")

        openapi = cliente.get("/api/proveedores/openapi.json")
        verificar(openapi.status_code == 200, "no se publica el contrato OpenAPI")

        verificar_administracion(cliente)
        verificar_operacion(cliente)
        verificar_inteligencia(cliente)
        verificar_negociacion(cliente)
        verificar_adjudicacion(cliente)

    print(
        "OK: SPA, Keycloak, proveedores, administración, operación, inteligencia, "
        f"negociación y adjudicación responden ({lista.json()['total']} proveedores)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
