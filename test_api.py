"""Pruebas de la API (Parte B) sin proveedores externos."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from utilidades_tests_api import (
    PEDIDO_CLIENTE_1,
    TOKEN_CLIENTE_1,
    TOKEN_CLIENTE_2,
    ModeloFalso,
    crear_app_de_prueba,
    crear_base_negocio,
    encabezado,
    llamada_tool,
)


@pytest.fixture
def rutas(tmp_path: Path) -> dict[str, Path]:
    return {
        "negocio": crear_base_negocio(tmp_path / "negocio.db"),
        "memoria": tmp_path / "memoria" / "checkpoints.sqlite",
    }


def test_health(rutas):
    with TestClient(crear_app_de_prueba(ModeloFalso(responses=[]), rutas["negocio"], rutas["memoria"])) as cliente:
        respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "agente": True, "memoria": True}


def test_consultar_requiere_autenticacion(rutas):
    with TestClient(crear_app_de_prueba(ModeloFalso(responses=[]), rutas["negocio"], rutas["memoria"])) as cliente:
        sin_token = cliente.post("/consultar", json={"mensaje": "Hola"})
        token_falso = cliente.post("/consultar", json={"mensaje": "Hola"}, headers=encabezado("token-inventado"))
    assert sin_token.status_code == 401
    assert token_falso.status_code == 401


def test_consultar_usa_herramienta_y_devuelve_respuesta(rutas):
    modelo = ModeloFalso(
        responses=[
            llamada_tool("consultar_estado_envio", {"nro_pedido": PEDIDO_CLIENTE_1}),
            AIMessage(content="Tu pedido 101 está en camino."),
        ]
    )
    with TestClient(crear_app_de_prueba(modelo, rutas["negocio"], rutas["memoria"])) as cliente:
        respuesta = cliente.post(
            "/consultar",
            json={"mensaje": "¿En qué estado está mi pedido 101?", "thread_id": "conv-1"},
            headers=encabezado(TOKEN_CLIENTE_1),
        )
    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["exito"] is True
    assert cuerpo["thread_id"] == "conv-1"
    assert cuerpo["herramientas_utilizadas"] == ["consultar_estado_envio"]
    assert "en camino" in cuerpo["respuesta"]


def test_consultar_sin_thread_id_crea_uno(rutas):
    modelo = ModeloFalso(responses=[AIMessage(content="Hola, ¿en qué te ayudo?")])
    with TestClient(crear_app_de_prueba(modelo, rutas["negocio"], rutas["memoria"])) as cliente:
        respuesta = cliente.post("/consultar", json={"mensaje": "Hola"}, headers=encabezado(TOKEN_CLIENTE_1))
    assert respuesta.status_code == 200
    assert respuesta.json()["thread_id"]


def test_memoria_persiste_via_http_despues_de_reiniciar(rutas):
    """B.2: la conversación sobrevive a un reinicio del servicio."""

    primer_modelo = ModeloFalso(responses=[AIMessage(content="Anotado, sos de Almacén Verde.")])
    with TestClient(crear_app_de_prueba(primer_modelo, rutas["negocio"], rutas["memoria"])) as cliente:
        cliente.post(
            "/consultar",
            json={"mensaje": "Hola, escribo de Almacén Verde", "thread_id": "conv-persistente"},
            headers=encabezado(TOKEN_CLIENTE_1),
        )

    # "Reinicio": una aplicación nueva sobre el mismo archivo de memoria.
    segundo_modelo = ModeloFalso(responses=[AIMessage(content="Sí, me dijiste que sos de Almacén Verde.")])
    with TestClient(crear_app_de_prueba(segundo_modelo, rutas["negocio"], rutas["memoria"])) as cliente:
        estado = cliente.get("/estado/conv-persistente", headers=encabezado(TOKEN_CLIENTE_1))
        seguimiento = cliente.post(
            "/consultar",
            json={"mensaje": "¿Te acordás de dónde escribo?", "thread_id": "conv-persistente"},
            headers=encabezado(TOKEN_CLIENTE_1),
        )
        estado_final = cliente.get("/estado/conv-persistente", headers=encabezado(TOKEN_CLIENTE_1))

    assert estado.status_code == 200
    assert [m["contenido"] for m in estado.json()["mensajes"]] == [
        "Hola, escribo de Almacén Verde",
        "Anotado, sos de Almacén Verde.",
    ]
    assert seguimiento.status_code == 200
    assert estado_final.json()["cantidad_mensajes"] == 4


def test_estado_de_otro_cliente_no_es_visible(rutas):
    modelo = ModeloFalso(responses=[AIMessage(content="Listo.")])
    with TestClient(crear_app_de_prueba(modelo, rutas["negocio"], rutas["memoria"])) as cliente:
        cliente.post("/consultar", json={"mensaje": "Hola", "thread_id": "conv-privada"}, headers=encabezado(TOKEN_CLIENTE_1))
        ajeno = cliente.get("/estado/conv-privada", headers=encabezado(TOKEN_CLIENTE_2))
        borrado_ajeno = cliente.delete("/estado/conv-privada", headers=encabezado(TOKEN_CLIENTE_2))
        propio = cliente.get("/estado/conv-privada", headers=encabezado(TOKEN_CLIENTE_1))
    assert ajeno.status_code == 404
    assert borrado_ajeno.status_code == 404
    assert propio.status_code == 200


def test_delete_borra_la_conversacion(rutas):
    modelo = ModeloFalso(responses=[AIMessage(content="Listo.")])
    with TestClient(crear_app_de_prueba(modelo, rutas["negocio"], rutas["memoria"])) as cliente:
        cliente.post("/consultar", json={"mensaje": "Hola", "thread_id": "conv-borrar"}, headers=encabezado(TOKEN_CLIENTE_1))
        borrado = cliente.delete("/estado/conv-borrar", headers=encabezado(TOKEN_CLIENTE_1))
        despues = cliente.get("/estado/conv-borrar", headers=encabezado(TOKEN_CLIENTE_1))
        de_nuevo = cliente.delete("/estado/conv-borrar", headers=encabezado(TOKEN_CLIENTE_1))
    assert borrado.status_code == 200
    assert borrado.json() == {"thread_id": "conv-borrar", "eliminado": True}
    assert despues.status_code == 404
    assert de_nuevo.status_code == 404





def test_error_del_agente_devuelve_500_neutro(rutas):
    class ModeloQueFalla(ModeloFalso):
        def _generate(self, *args, **kwargs):
            raise RuntimeError("detalle interno con datos sensibles")

    with TestClient(crear_app_de_prueba(ModeloQueFalla(responses=[]), rutas["negocio"], rutas["memoria"])) as cliente:
        respuesta = cliente.post("/consultar", json={"mensaje": "Hola"}, headers=encabezado(TOKEN_CLIENTE_1))
    assert respuesta.status_code == 500
    assert "detalle interno" not in respuesta.text
