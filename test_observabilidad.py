"""Pruebas de observabilidad y métricas de la API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from observabilidad import FormateadorJSON, MetricasAPI, validar_privacidad_langsmith
from utilidades_tests_api import (
    TOKEN_CLIENTE_1,
    ModeloFalso,
    crear_app_de_prueba,
    crear_base_negocio,
    encabezado,
)


@pytest.fixture
def rutas(tmp_path: Path) -> dict[str, Path]:
    return {
        "negocio": crear_base_negocio(tmp_path / "negocio.db"),
        "memoria": tmp_path / "memoria" / "checkpoints.sqlite",
    }


def test_metricas_iniciales_estan_vacias():
    metricas = MetricasAPI()
    resultado = metricas.obtener()

    assert resultado["consultas"] == {
        "total": 0,
        "exitosas": 0,
        "fallidas": 0,
        "bloqueadas": 0,
    }
    assert resultado["latencia_ms"]["promedio"] is None
    assert resultado["latencia_ms"]["p95"] is None
    assert resultado["latencia_ms"]["muestras"] == 0
    assert resultado["herramientas"]["invocaciones_por_nombre"] == {}
    assert resultado["herramientas"]["errores"] == 0
    assert resultado["alerta_latencia"] is False


def test_registra_resultados_y_herramientas():
    metricas = MetricasAPI()

    metricas.registrar_consulta(
        latencia_ms=100,
        exito=True,
        herramientas=["consultar_conocimiento"],
    )
    metricas.registrar_consulta(
        latencia_ms=200,
        exito=False,
        herramientas=["consultar_estado_envio"],
        errores_herramientas=1,
    )
    metricas.registrar_consulta(
        latencia_ms=50,
        exito=False,
        bloqueada=True,
    )

    resultado = metricas.obtener()

    assert resultado["consultas"] == {
        "total": 3,
        "exitosas": 1,
        "fallidas": 1,
        "bloqueadas": 1,
    }
    assert resultado["latencia_ms"]["promedio"] == pytest.approx(116.67)
    assert resultado["latencia_ms"]["p95"] is None
    assert resultado["herramientas"]["invocaciones_por_nombre"] == {
        "consultar_conocimiento": 1,
        "consultar_estado_envio": 1,
    }
    assert resultado["herramientas"]["errores"] == 1


def test_p95_y_alerta_requieren_muestra_minima():
    metricas = MetricasAPI(
        muestra_minima_p95=3,
        umbral_alerta_ms=100,
    )

    metricas.registrar_consulta(latencia_ms=50, exito=True)
    metricas.registrar_consulta(latencia_ms=80, exito=True)

    antes = metricas.obtener()
    assert antes["latencia_ms"]["p95"] is None
    assert antes["alerta_latencia"] is False

    metricas.registrar_consulta(latencia_ms=120, exito=True)

    despues = metricas.obtener()
    assert despues["latencia_ms"]["p95"] == 120
    assert despues["alerta_latencia"] is True


def test_formateador_genera_json_controlado():
    registro = logging.LogRecord(
        name="ecologix.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Consulta procesada.",
        args=(),
        exc_info=None,
    )
    registro.categoria = "consulta"
    registro.resultado = "exitosa"
    registro.correlacion_id = "correlacion-no-identificable"

    contenido = json.loads(FormateadorJSON().format(registro))

    assert contenido["nivel"] == "INFO"
    assert contenido["logger"] == "ecologix.api"
    assert contenido["evento"] == "Consulta procesada."
    assert contenido["categoria"] == "consulta"
    assert contenido["resultado"] == "exitosa"
    assert contenido["correlacion_id"] == "correlacion-no-identificable"
    assert "timestamp" in contenido


def test_endpoint_metricas_refleja_consulta_exitosa(rutas):
    modelo = ModeloFalso(
        responses=[AIMessage(content="Hola, ¿en qué puedo ayudarte?")]
    )

    with TestClient(
        crear_app_de_prueba(
            modelo,
            rutas["negocio"],
            rutas["memoria"],
        )
    ) as cliente:
        inicial = cliente.get("/metricas")
        consulta = cliente.post(
            "/consultar",
            json={"mensaje": "Hola"},
            headers=encabezado(TOKEN_CLIENTE_1),
        )
        final = cliente.get("/metricas")

    assert inicial.status_code == 200
    assert inicial.json()["consultas"]["total"] == 0

    assert consulta.status_code == 200
    assert consulta.json()["exito"] is True

    assert final.status_code == 200
    cuerpo = final.json()

    assert cuerpo["consultas"] == {
        "total": 1,
        "exitosas": 1,
        "fallidas": 0,
        "bloqueadas": 0,
    }
    assert cuerpo["latencia_ms"]["muestras"] == 1
    assert cuerpo["latencia_ms"]["promedio"] is not None
    assert cuerpo["latencia_ms"]["p95"] is None
    assert cuerpo["alerta_latencia"] is False

    def test_langsmith_inactivo_no_exige_configuracion(monkeypatch):
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        monkeypatch.delenv("LANGSMITH_HIDE_INPUTS", raising=False)
        monkeypatch.delenv("LANGSMITH_HIDE_OUTPUTS", raising=False)
        monkeypatch.delenv("LANGSMITH_HIDE_METADATA", raising=False)

    validar_privacidad_langsmith()


def test_langsmith_activo_exige_privacidad_completa(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_OUTPUTS", "false")
    monkeypatch.setenv("LANGSMITH_HIDE_METADATA", "true")

    with pytest.raises(RuntimeError, match="ocultar inputs, outputs y metadatos"):
        validar_privacidad_langsmith()


def test_langsmith_activo_acepta_configuracion_segura(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_OUTPUTS", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_METADATA", "true")

    validar_privacidad_langsmith()

def test_langsmith_inactivo_no_exige_configuracion(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_HIDE_INPUTS", raising=False)
    monkeypatch.delenv("LANGSMITH_HIDE_OUTPUTS", raising=False)
    monkeypatch.delenv("LANGSMITH_HIDE_METADATA", raising=False)

    validar_privacidad_langsmith()

def test_error_tecnico_se_registra_como_consulta_fallida(rutas):
    class ModeloQueFalla(ModeloFalso):
        def _generate(self, *args, **kwargs):
            raise RuntimeError("detalle interno simulado")

    with TestClient(
        crear_app_de_prueba(
            ModeloQueFalla(responses=[]),
            rutas["negocio"],
            rutas["memoria"],
        )
    ) as cliente:
        respuesta = cliente.post(
            "/consultar",
            json={"mensaje": "Consulta sintética"},
            headers=encabezado(TOKEN_CLIENTE_1),
        )
        metricas = cliente.get("/metricas")

    assert respuesta.status_code == 500
    assert metricas.status_code == 200
    assert metricas.json()["consultas"] == {
        "total": 1,
        "exitosas": 0,
        "fallidas": 1,
        "bloqueadas": 0,
    }


def test_solicitud_invalida_no_se_contabiliza(rutas):
    with TestClient(
        crear_app_de_prueba(
            ModeloFalso(responses=[]),
            rutas["negocio"],
            rutas["memoria"],
        )
    ) as cliente:
        respuesta = cliente.post(
            "/consultar",
            json={"mensaje": ["formato", "inválido"]},
            headers=encabezado(TOKEN_CLIENTE_1),
        )
        metricas = cliente.get("/metricas")

    assert respuesta.status_code == 422
    assert metricas.status_code == 200
    assert metricas.json()["consultas"]["total"] == 0