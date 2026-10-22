from __future__ import annotations

import os

import pytest

from entrega_3.evaluar_b3 import (
    crear_configuracion_traza,
    limpiar_metadatos_agente_incompletos,
)


def configurar_entorno_valido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "entrega_3.evaluar_b3.load_dotenv",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "clave-de-prueba-no-valida")
    monkeypatch.setenv("LANGSMITH_PROJECT", "proyecto-de-prueba")
    monkeypatch.setenv("LANGSMITH_AGENT_ID", "agente-de-prueba")


def test_configuracion_traza_requiere_tracing_activo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configurar_entorno_valido(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")

    with pytest.raises(RuntimeError, match="LANGSMITH_TRACING=true"):
        crear_configuracion_traza()


def test_configuracion_traza_requiere_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configurar_entorno_valido(monkeypatch)
    monkeypatch.setenv("LANGSMITH_API_KEY", "")

    with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY"):
        crear_configuracion_traza()


def test_configuracion_traza_requiere_proyecto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configurar_entorno_valido(monkeypatch)
    monkeypatch.setenv("LANGSMITH_PROJECT", "")

    with pytest.raises(RuntimeError, match="LANGSMITH_PROJECT"):
        crear_configuracion_traza()


def test_configuracion_traza_asigna_metadatos_sin_incluir_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configurar_entorno_valido(monkeypatch)

    configuracion = crear_configuracion_traza()

    assert configuracion["run_name"] == "B4-reranking-gemini-35-flash-lite"
    assert "B4" in configuracion["tags"]
    assert configuracion["metadata"]["proyecto_langsmith"] == (
        "proyecto-de-prueba"
    )
    assert "clave-de-prueba-no-valida" not in repr(configuracion)


def test_configuracion_traza_ignora_entorno_de_agente_incompleto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configurar_entorno_valido(monkeypatch)
    monkeypatch.setenv("LANGSMITH_AGENT_ENVIRONMENT", "local")
    monkeypatch.delenv("LANGSMITH_AGENT_ID", raising=False)

    with pytest.warns(RuntimeWarning, match="falta LANGSMITH_AGENT_ID"):
        limpiar_metadatos_agente_incompletos()

    assert "LANGSMITH_AGENT_ENVIRONMENT" not in os.environ
