from __future__ import annotations

from typing import Any, Sequence

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool, tool

from agente import (
    MAX_CICLOS_HERRAMIENTAS,
    MENSAJE_LIMITE_CICLOS,
    MENSAJE_LLAMADAS_PARALELAS,
    crear_grafo_agente,
    invocar_agente,
)


class ModeloFalsoConHerramientas(FakeMessagesListChatModel):
    _nombres_herramientas: list[str]

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ModeloFalsoConHerramientas:
        self._nombres_herramientas = [
            herramienta.name
            if isinstance(herramienta, BaseTool)
            else herramienta.__name__
            for herramienta in tools
        ]
        return self


def _crear_herramienta_contadora(
    contador: dict[str, int],
) -> BaseTool:
    @tool
    def consultar_dato(consulta: str) -> str:
        """Consulta un dato de prueba."""

        contador["ejecuciones"] += 1
        return f"Resultado para {consulta}"

    return consultar_dato


def _llamada_herramienta(
    identificador: str,
    consulta: str = "prueba",
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "consultar_dato",
                "args": {"consulta": consulta},
                "id": identificador,
                "type": "tool_call",
            }
        ],
    )


def test_grafo_responde_sin_invocar_herramientas() -> None:
    modelo = ModeloFalsoConHerramientas(
        responses=[AIMessage(content="Hola, ¿en qué puedo ayudarte?")]
    )
    contador = {"ejecuciones": 0}
    grafo = crear_grafo_agente(
        modelo,
        [_crear_herramienta_contadora(contador)],
    )

    resultado = invocar_agente(
        grafo, "Hola", cliente_id=1, thread_id="hilo-hola"
    )

    assert resultado["messages"][-1].content == (
        "Hola, ¿en qué puedo ayudarte?"
    )
    assert resultado["ciclos_herramientas"] == 0
    assert contador["ejecuciones"] == 0


def test_grafo_ejecuta_una_herramienta_y_vuelve_al_agente() -> None:
    modelo = ModeloFalsoConHerramientas(
        responses=[
            _llamada_herramienta("llamada-1"),
            AIMessage(content="Encontré el dato solicitado."),
        ]
    )
    contador = {"ejecuciones": 0}
    grafo = crear_grafo_agente(
        modelo,
        [_crear_herramienta_contadora(contador)],
    )

    resultado = invocar_agente(
        grafo, "Buscá el dato", cliente_id=1, thread_id="hilo-dato"
    )

    assert resultado["messages"][-1].content == (
        "Encontré el dato solicitado."
    )
    assert resultado["ciclos_herramientas"] == 1
    assert contador["ejecuciones"] == 1


def test_grafo_rechaza_llamadas_paralelas_sin_ejecutarlas() -> None:
    respuesta = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "consultar_dato",
                "args": {"consulta": "uno"},
                "id": "llamada-1",
                "type": "tool_call",
            },
            {
                "name": "consultar_dato",
                "args": {"consulta": "dos"},
                "id": "llamada-2",
                "type": "tool_call",
            },
        ],
    )
    modelo = ModeloFalsoConHerramientas(responses=[respuesta])
    contador = {"ejecuciones": 0}
    grafo = crear_grafo_agente(
        modelo,
        [_crear_herramienta_contadora(contador)],
    )

    resultado = invocar_agente(
        grafo, "Hacé dos consultas", cliente_id=1, thread_id="hilo-paralelo"
    )

    assert resultado["messages"][-1].content == MENSAJE_LLAMADAS_PARALELAS
    assert resultado["ciclos_herramientas"] == 0
    assert contador["ejecuciones"] == 0


def test_grafo_detiene_una_sexta_llamada_de_herramienta() -> None:
    respuestas = [
        *[
            _llamada_herramienta(f"llamada-{numero}")
            for numero in range(1, MAX_CICLOS_HERRAMIENTAS + 2)
        ],
        AIMessage(content="Esta respuesta no debe alcanzarse."),
    ]
    modelo = ModeloFalsoConHerramientas(responses=respuestas)
    contador = {"ejecuciones": 0}
    grafo = crear_grafo_agente(
        modelo,
        [_crear_herramienta_contadora(contador)],
    )

    resultado = invocar_agente(
        grafo, "Seguí consultando", cliente_id=1, thread_id="hilo-limite"
    )

    assert resultado["messages"][-1].content == MENSAJE_LIMITE_CICLOS
    assert resultado["ciclos_herramientas"] == MAX_CICLOS_HERRAMIENTAS
    assert contador["ejecuciones"] == MAX_CICLOS_HERRAMIENTAS


def test_grafo_propaga_errores_de_herramienta() -> None:
    @tool
    def herramienta_con_error(consulta: str) -> str:
        """Simula un error de infraestructura."""

        raise RuntimeError("Falló la herramienta.")

    modelo = ModeloFalsoConHerramientas(
        responses=[AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "herramienta_con_error",
                    "args": {"consulta": "prueba"},
                    "id": "llamada-error",
                    "type": "tool_call",
                }
            ],
        )]
    )
    grafo = crear_grafo_agente(modelo, [herramienta_con_error])

    with pytest.raises(RuntimeError, match="Falló la herramienta"):
        invocar_agente(
            grafo,
            "Ejecutá la operación",
            cliente_id=1,
            thread_id="hilo-error",
        )


def test_grafo_exige_cliente_id_confiable_positivo() -> None:
    modelo = ModeloFalsoConHerramientas(
        responses=[AIMessage(content="No debería invocar el modelo.")]
    )
    grafo = crear_grafo_agente(modelo, [_crear_herramienta_contadora({"ejecuciones": 0})])

    with pytest.raises(ValueError, match="cliente_id"):
        invocar_agente(
            grafo, "Consulta", cliente_id=0, thread_id="hilo-invalido"
        )


def test_grafo_requiere_al_menos_una_herramienta() -> None:
    modelo = ModeloFalsoConHerramientas(
        responses=[AIMessage(content="No debería invocar el modelo.")]
    )

    with pytest.raises(ValueError, match="al menos una herramienta"):
        crear_grafo_agente(modelo, [])
