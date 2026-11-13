from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Sequence

import pytest
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from agente import crear_grafo_agente, invocar_agente
from herramientas_operativas import crear_herramientas_operativas
from herramientas_rag import crear_herramienta_rag


RAIZ = Path(__file__).resolve().parent
ID_CLIENTE_AUTENTICADO = 1
ID_CLIENTE_AJENO = 2
ID_PEDIDO_PROPIO = 101
ID_PEDIDO_AJENO = 202
TEXTO_EVIDENCIA_RAG = (
    "Las entregas se coordinan según la zona de cobertura."
)


class ModeloFalsoConHerramientas(FakeMessagesListChatModel):
    """Reproduce respuestas preparadas sin conectar con un proveedor externo."""

    llamadas_a_modelo: int = 0
    _nombres_herramientas: list[str] = PrivateAttr(default_factory=list)

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ModeloFalsoConHerramientas:
        self._nombres_herramientas = [herramienta.name for herramienta in tools]
        _ = tool_choice, kwargs
        return self

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        self.llamadas_a_modelo += 1
        return super()._generate(*args, **kwargs)


@pytest.fixture
def base_negocio(tmp_path: Path) -> Path:
    ruta_db = tmp_path / "ecologix_test.db"
    with sqlite3.connect(ruta_db) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(
            (RAIZ / "schema.sql").read_text(encoding="utf-8")
        )
        conexion.executemany(
            """
            INSERT INTO clientes (id, razon_social)
            VALUES (?, ?)
            """,
            [
                (ID_CLIENTE_AUTENTICADO, "Cliente autenticado"),
                (ID_CLIENTE_AJENO, "Cliente ajeno"),
            ],
        )
        conexion.executemany(
            """
            INSERT INTO pedidos (id, cliente_id, direccion_entrega)
            VALUES (?, ?, ?)
            """,
            [
                (ID_PEDIDO_PROPIO, ID_CLIENTE_AUTENTICADO, "Dirección propia"),
                (ID_PEDIDO_AJENO, ID_CLIENTE_AJENO, "Dirección ajena"),
            ],
        )
        conexion.executemany(
            """
            INSERT INTO envios (pedido_id, estado, despachado_en)
            VALUES (?, ?, ?)
            """,
            [
                (ID_PEDIDO_PROPIO, "EN_CAMINO", "2026-11-12 10:00:00"),
                (ID_PEDIDO_AJENO, "ENTREGADO", "2026-11-10 09:00:00"),
            ],
        )
    return ruta_db


def _llamada_tool(
    nombre: str,
    argumentos: dict[str, Any],
    identificador: str = "llamada-matriz",
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": nombre,
                "args": argumentos,
                "id": identificador,
                "type": "tool_call",
            }
        ],
    )


def _crear_rag_falso(consultas: list[str] | None = None):
    def recuperar(consulta: str) -> dict[str, list[Document]]:
        if consultas is not None:
            consultas.append(consulta)
        return {
            "selected_documents": [
                Document(
                    page_content=TEXTO_EVIDENCIA_RAG,
                    metadata={"titulo_documento_origen": "Cobertura"},
                )
            ]
        }

    return crear_herramienta_rag(
        recuperador=RunnableLambda(recuperar)
    )


def _ejecutar_escenario(
    ruta_db: Path,
    respuestas: list[AIMessage],
    mensaje: str,
    *,
    cliente_id: int = ID_CLIENTE_AUTENTICADO,
):
    modelo = ModeloFalsoConHerramientas(responses=respuestas)
    herramientas: list[BaseTool] = [
        _crear_rag_falso(),
        *crear_herramientas_operativas(ruta_db),
    ]
    grafo = crear_grafo_agente(modelo, herramientas)
    resultado = invocar_agente(
        grafo,
        mensaje,
        cliente_id=cliente_id,
        thread_id=f"matriz-{mensaje}",
    )
    return resultado, modelo


def _mensajes_tool(resultado: dict[str, Any]) -> list[ToolMessage]:
    return [
        mensaje
        for mensaje in resultado["messages"]
        if isinstance(mensaje, ToolMessage)
    ]


def test_matriz_consulta_rag_usa_fragmento_recuperado(
    base_negocio: Path,
) -> None:
    consulta = "¿Cómo se coordinan las entregas?"
    consultas_recibidas: list[str] = []
    modelo = ModeloFalsoConHerramientas(
        responses=[
            _llamada_tool(
                "buscar_conocimiento_ecologix",
                {"consulta": consulta},
            ),
            AIMessage(
                content=(
                    "Las entregas se coordinan según la zona de cobertura."
                )
            ),
        ]
    )
    herramientas: list[BaseTool] = [
        _crear_rag_falso(consultas_recibidas),
        *crear_herramientas_operativas(base_negocio),
    ]
    grafo = crear_grafo_agente(modelo, herramientas)
    resultado = invocar_agente(
        grafo,
        consulta,
        cliente_id=ID_CLIENTE_AUTENTICADO,
        thread_id="matriz-rag",
    )

    mensajes_tool = _mensajes_tool(resultado)
    assert len(mensajes_tool) == 1
    assert consultas_recibidas == [consulta]
    assert TEXTO_EVIDENCIA_RAG in mensajes_tool[0].content
    assert resultado["messages"][-1].content == (
        "Las entregas se coordinan según la zona de cobertura."
    )
    assert resultado["ciclos_herramientas"] == 1
    assert modelo.llamadas_a_modelo == 2


def test_matriz_consulta_envio_propio_devuelve_estado_autorizado(
    base_negocio: Path,
) -> None:
    resultado, _ = _ejecutar_escenario(
        base_negocio,
        [
            _llamada_tool(
                "consultar_estado_envio",
                {"nro_pedido": ID_PEDIDO_PROPIO},
            ),
            AIMessage(content="Tu pedido está en camino."),
        ],
        f"Consultá el envío {ID_PEDIDO_PROPIO}.",
    )

    assert len(_mensajes_tool(resultado)) == 1
    assert "EN_CAMINO" in _mensajes_tool(resultado)[0].content
    assert resultado["messages"][-1].content == "Tu pedido está en camino."


@pytest.mark.parametrize(
    ("nro_pedido", "esperado"),
    [
        (ID_PEDIDO_AJENO, "No se encontró un envío disponible para ese pedido."),
        (999, "No se encontró un envío disponible para ese pedido."),
    ],
)
def test_matriz_envio_ajeno_o_inexistente_tiene_respuesta_neutra(
    base_negocio: Path,
    nro_pedido: int,
    esperado: str,
) -> None:
    resultado, _ = _ejecutar_escenario(
        base_negocio,
        [
            _llamada_tool(
                "consultar_estado_envio",
                {"nro_pedido": nro_pedido},
            ),
            AIMessage(content=esperado),
        ],
        f"Consultá el envío {nro_pedido}.",
    )

    mensaje_tool = _mensajes_tool(resultado)[0]
    assert mensaje_tool.content == esperado
    assert resultado["messages"][-1].content == esperado
    assert "ENTREGADO" not in mensaje_tool.content
    assert "Dirección ajena" not in mensaje_tool.content


def test_matriz_registra_reclamo_sobre_pedido_propio(
    base_negocio: Path,
) -> None:
    resultado, _ = _ejecutar_escenario(
        base_negocio,
        [
            _llamada_tool(
                "registrar_reclamo",
                {
                    "motivo": "El pedido llegó con productos dañados.",
                    "nro_pedido": ID_PEDIDO_PROPIO,
                },
            ),
            AIMessage(content="Tu reclamo quedó registrado como abierto."),
        ],
        f"Registrá un reclamo para el pedido {ID_PEDIDO_PROPIO}.",
    )

    with sqlite3.connect(base_negocio) as conexion:
        reclamos = conexion.execute(
            """
            SELECT cliente_id, pedido_id, motivo, estado
            FROM reclamos
            """
        ).fetchall()

    assert resultado["messages"][-1].content == (
        "Tu reclamo quedó registrado como abierto."
    )
    assert len(_mensajes_tool(resultado)) == 1
    assert reclamos == [
        (
            ID_CLIENTE_AUTENTICADO,
            ID_PEDIDO_PROPIO,
            "El pedido llegó con productos dañados.",
            "ABIERTO",
        )
    ]


def test_matriz_rechaza_reclamo_de_pedido_ajeno_sin_escritura(
    base_negocio: Path,
) -> None:
    resultado, _ = _ejecutar_escenario(
        base_negocio,
        [
            _llamada_tool(
                "registrar_reclamo",
                {
                    "motivo": "El pedido llegó dañado.",
                    "nro_pedido": ID_PEDIDO_AJENO,
                },
            ),
            AIMessage(
                content=(
                    "No pude registrar el reclamo con ese pedido. "
                    "Consultá el número o contactá a un operador."
                )
            ),
        ],
        f"Registrá un reclamo para el pedido {ID_PEDIDO_AJENO}.",
    )

    with sqlite3.connect(base_negocio) as conexion:
        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM reclamos"
        ).fetchone()[0]

    assert len(_mensajes_tool(resultado)) == 1
    assert "No se pudo registrar" in _mensajes_tool(resultado)[0].content
    assert cantidad == 0
