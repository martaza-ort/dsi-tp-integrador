"""Apoyo compartido por `test_api.py`.

Arma la API con un modelo falso, un RAG falso y bases SQLite temporales:
no consume proveedores externos ni toca datos reales.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Sequence

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import PrivateAttr

from api import ConfiguracionAPI, crear_app
from herramientas_operativas import crear_herramientas_operativas
from herramientas_rag import crear_herramienta_rag


RAIZ = Path(__file__).resolve().parent
TOKEN_CLIENTE_1 = "token-demo-cliente-1"
TOKEN_CLIENTE_2 = "token-demo-cliente-2"
CLIENTE_1 = 1
CLIENTE_2 = 2
PEDIDO_CLIENTE_1 = 101
PEDIDO_CLIENTE_2 = 202
SECRETO_TEST = b"secreto-de-pruebas-con-mas-de-32-caracteres"


class ModeloFalso(FakeMessagesListChatModel):
    """Modelo con respuestas preparadas que cuenta cuántas veces se invocó."""

    llamadas: int = 0
    _herramientas: list[str] = PrivateAttr(default_factory=list)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ModeloFalso":
        self._herramientas = [herramienta.name for herramienta in tools]
        return self

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        self.llamadas += 1
        return super()._generate(*args, **kwargs)


def llamada_tool(nombre: str, argumentos: dict[str, Any], id_llamada: str = "llamada-1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": nombre, "args": argumentos, "id": id_llamada, "type": "tool_call"}],
    )


def crear_base_negocio(ruta: Path) -> Path:
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript((RAIZ / "schema.sql").read_text(encoding="utf-8"))
        conexion.executemany(
            "INSERT INTO clientes (id, razon_social) VALUES (?, ?)",
            [(CLIENTE_1, "Cliente uno"), (CLIENTE_2, "Cliente dos")],
        )
        conexion.executemany(
            "INSERT INTO pedidos (id, cliente_id, direccion_entrega) VALUES (?, ?, ?)",
            [(PEDIDO_CLIENTE_1, CLIENTE_1, "Dirección uno"), (PEDIDO_CLIENTE_2, CLIENTE_2, "Dirección dos")],
        )
        conexion.executemany(
            "INSERT INTO envios (pedido_id, estado, despachado_en) VALUES (?, ?, ?)",
            [
                (PEDIDO_CLIENTE_1, "EN_CAMINO", "2026-11-12 10:00:00"),
                (PEDIDO_CLIENTE_2, "ENTREGADO", "2026-11-10 09:00:00"),
            ],
        )
    return ruta


def _rag_falso():
    def recuperar(consulta: str) -> dict[str, list[Document]]:
        return {
            "selected_documents": [
                Document(
                    page_content="Las entregas se coordinan según la zona de cobertura.",
                    metadata={"titulo_documento_origen": "Política de entregas"},
                )
            ]
        }

    return crear_herramienta_rag(recuperador=RunnableLambda(recuperar))


def crear_app_de_prueba(
    modelo: ModeloFalso,
    ruta_negocio: Path,
    ruta_memoria: Path,
):
    configuracion = ConfiguracionAPI(
        clientes_por_token={TOKEN_CLIENTE_1: CLIENTE_1, TOKEN_CLIENTE_2: CLIENTE_2},
        secreto_hilos=SECRETO_TEST,
        ruta_memoria=ruta_memoria,
        fabrica_modelo=lambda: modelo,
        fabrica_herramientas=lambda: [_rag_falso(), *crear_herramientas_operativas(ruta_negocio)],
    )
    return crear_app(configuracion)


def encabezado(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def contar_reclamos(ruta_negocio: Path) -> int:
    with sqlite3.connect(ruta_negocio) as conexion:
        return conexion.execute("SELECT COUNT(*) FROM reclamos").fetchone()[0]
