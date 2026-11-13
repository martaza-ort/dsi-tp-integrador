from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from herramientas_operativas import crear_herramientas_operativas


RAIZ = Path(__file__).resolve().parent
ID_CLIENTE_A = 1
ID_CLIENTE_B = 2
ID_PEDIDO_A = 101
ID_PEDIDO_B = 202


class EstadoPrueba(TypedDict):
    messages: list[Any]
    cliente_id: int


@pytest.fixture
def base_prueba(tmp_path: Path) -> Path:
    ruta_db = tmp_path / "ecologix_test.db"
    conexion = sqlite3.connect(ruta_db)
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
            (ID_CLIENTE_A, "Cliente A"),
            (ID_CLIENTE_B, "Cliente B"),
        ],
    )
    conexion.executemany(
        """
        INSERT INTO pedidos (id, cliente_id, direccion_entrega)
        VALUES (?, ?, ?)
        """,
        [
            (ID_PEDIDO_A, ID_CLIENTE_A, "Dirección A"),
            (ID_PEDIDO_B, ID_CLIENTE_B, "Dirección B"),
        ],
    )
    conexion.execute(
        """
        INSERT INTO envios (pedido_id, estado, despachado_en)
        VALUES (?, ?, ?)
        """,
        (ID_PEDIDO_A, "EN_CAMINO", "2026-11-12 10:00:00"),
    )
    conexion.commit()
    conexion.close()
    return ruta_db


def _invocar_tool(
    ruta_db: Path,
    nombre: str,
    argumentos: dict[str, Any],
    cliente_id: int,
) -> str:
    herramientas = crear_herramientas_operativas(ruta_db)
    nodo = ToolNode(herramientas)
    grafo = StateGraph(EstadoPrueba)
    grafo.add_node("herramientas", nodo)
    grafo.add_edge(START, "herramientas")
    grafo.add_edge("herramientas", END)
    llamada = {
        "name": nombre,
        "args": argumentos,
        "id": "llamada-prueba",
        "type": "tool_call",
    }
    resultado = grafo.compile().invoke(
        {
            "messages": [AIMessage(content="", tool_calls=[llamada])],
            "cliente_id": cliente_id,
        }
    )
    return resultado["messages"][-1].content


def test_identidad_no_se_expone_en_el_esquema_de_las_tools(
    base_prueba: Path,
) -> None:
    herramientas = crear_herramientas_operativas(base_prueba)

    assert herramientas[0].name == "consultar_estado_envio"
    assert set(herramientas[0].args) == {"nro_pedido"}
    assert "cliente_id" not in herramientas[0].args
    assert herramientas[1].name == "registrar_reclamo"
    assert "cliente_id" not in herramientas[1].args


def test_consulta_estado_envio_devuelve_solo_datos_operativos(
    base_prueba: Path,
) -> None:
    resultado = _invocar_tool(
        base_prueba,
        "consultar_estado_envio",
        {"nro_pedido": ID_PEDIDO_A},
        ID_CLIENTE_A,
    )

    assert resultado == (
        "Estado del envío: EN_CAMINO. "
        "Despachado: 2026-11-12 10:00:00."
    )
    assert "Cliente A" not in resultado
    assert "Dirección A" not in resultado


@pytest.mark.parametrize("nro_pedido", [ID_PEDIDO_B, 999])
def test_consulta_no_revela_pedido_ajeno_o_inexistente(
    base_prueba: Path,
    nro_pedido: int,
) -> None:
    resultado = _invocar_tool(
        base_prueba,
        "consultar_estado_envio",
        {"nro_pedido": nro_pedido},
        ID_CLIENTE_A,
    )

    assert resultado == "No se encontró un envío disponible para ese pedido."


def test_reclamo_se_registra_para_cliente_autenticado(
    base_prueba: Path,
) -> None:
    resultado = _invocar_tool(
        base_prueba,
        "registrar_reclamo",
        {
            "motivo": "El pedido llegó con productos dañados.",
            "nro_pedido": ID_PEDIDO_A,
        },
        ID_CLIENTE_A,
    )

    with sqlite3.connect(base_prueba) as conexion:
        reclamo = conexion.execute(
            """
            SELECT cliente_id, pedido_id, motivo, estado, nota_credito_monto
            FROM reclamos
            """
        ).fetchone()

    assert resultado == "Reclamo registrado con ID 1, estado ABIERTO."
    assert reclamo == (
        ID_CLIENTE_A,
        ID_PEDIDO_A,
        "El pedido llegó con productos dañados.",
        "ABIERTO",
        None,
    )


def test_reclamo_sin_pedido_es_admitido_por_el_esquema(
    base_prueba: Path,
) -> None:
    resultado = _invocar_tool(
        base_prueba,
        "registrar_reclamo",
        {"motivo": "Tengo un problema con una entrega."},
        ID_CLIENTE_A,
    )

    with sqlite3.connect(base_prueba) as conexion:
        reclamo = conexion.execute(
            "SELECT cliente_id, pedido_id, estado FROM reclamos"
        ).fetchone()

    assert resultado == "Reclamo registrado con ID 1, estado ABIERTO."
    assert reclamo == (ID_CLIENTE_A, None, "ABIERTO")


def test_reclamo_de_pedido_ajeno_no_es_insertado(
    base_prueba: Path,
) -> None:
    resultado = _invocar_tool(
        base_prueba,
        "registrar_reclamo",
        {
            "motivo": "Reclamo sobre pedido.",
            "nro_pedido": ID_PEDIDO_B,
        },
        ID_CLIENTE_A,
    )

    with sqlite3.connect(base_prueba) as conexion:
        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM reclamos"
        ).fetchone()[0]

    assert "No se pudo registrar" in resultado
    assert cantidad == 0


def test_reclamo_rechaza_motivo_vacio_sin_escritura(
    base_prueba: Path,
) -> None:
    with pytest.raises(ValueError, match="motivo del reclamo no puede estar vacío"):
        _invocar_tool(
            base_prueba,
            "registrar_reclamo",
            {"motivo": "   "},
            ID_CLIENTE_A,
        )

    with sqlite3.connect(base_prueba) as conexion:
        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM reclamos"
        ).fetchone()[0]

    assert cantidad == 0
