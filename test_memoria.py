from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, tool

from agente import crear_grafo_agente, invocar_agente
from memoria import MemoriaConversacional


def _crear_herramienta_vacia() -> BaseTool:
    @tool
    def consultar_dato(consulta: str) -> str:
        """Devuelve el dato de prueba solicitado."""

        return f"Resultado: {consulta}"

    return consultar_dato


class ModeloFalsoConHerramientas(FakeMessagesListChatModel):
    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ModeloFalsoConHerramientas:
        return self


def _modelo(respuesta: str) -> ModeloFalsoConHerramientas:
    return ModeloFalsoConHerramientas(
        responses=[AIMessage(content=respuesta)]
    )


def _config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def test_memoria_persiste_mensajes_al_reabrir_sqlite(
    tmp_path: Path,
) -> None:
    ruta_db = tmp_path / "estado" / "checkpoints.sqlite"
    herramientas = [_crear_herramienta_vacia()]

    with MemoriaConversacional(ruta_db) as memoria:
        grafo = crear_grafo_agente(
            _modelo("Respuesta inicial."),
            herramientas,
            checkpointer=memoria.checkpointer,
        )
        invocar_agente(
            grafo,
            "Primer mensaje.",
            cliente_id=41,
            thread_id="conversacion-a",
            memoria=memoria,
        )

        estado = grafo.get_state(_config("conversacion-a"))
        assert "cliente_id" not in estado.values
        assert [m.content for m in estado.values["messages"]] == [
            "Primer mensaje.",
            "Respuesta inicial.",
        ]

    with MemoriaConversacional(ruta_db) as memoria:
        grafo = crear_grafo_agente(
            _modelo("Respuesta posterior."),
            herramientas,
            checkpointer=memoria.checkpointer,
        )
        resultado = invocar_agente(
            grafo,
            "Segundo mensaje.",
            cliente_id=41,
            thread_id="conversacion-a",
            memoria=memoria,
        )

    assert [m.content for m in resultado["messages"] if m.type == "human"] == [
        "Primer mensaje.",
        "Segundo mensaje.",
    ]


def test_hilos_no_comparten_historial(tmp_path: Path) -> None:
    ruta_db = tmp_path / "checkpoints.sqlite"

    with MemoriaConversacional(ruta_db) as memoria:
        grafo = crear_grafo_agente(
            _modelo("Respuesta."),
            [_crear_herramienta_vacia()],
            checkpointer=memoria.checkpointer,
        )
        invocar_agente(
            grafo,
            "Mensaje privado del hilo A.",
            cliente_id=1,
            thread_id="hilo-a",
            memoria=memoria,
        )
        invocar_agente(
            grafo,
            "Mensaje privado del hilo B.",
            cliente_id=2,
            thread_id="hilo-b",
            memoria=memoria,
        )

        mensajes_a = grafo.get_state(_config("hilo-a")).values["messages"]
        mensajes_b = grafo.get_state(_config("hilo-b")).values["messages"]

    assert [m.content for m in mensajes_a if m.type == "human"] == [
        "Mensaje privado del hilo A."
    ]
    assert [m.content for m in mensajes_b if m.type == "human"] == [
        "Mensaje privado del hilo B."
    ]


def test_purga_elimina_hilo_vencido_y_conserva_el_activo(
    tmp_path: Path,
) -> None:
    ruta_db = tmp_path / "checkpoints.sqlite"
    ruta_negocio = tmp_path / "negocio.sqlite"
    instante = datetime.now(timezone.utc)
    with closing(sqlite3.connect(ruta_negocio)) as conexion:
        with conexion:
            conexion.execute("CREATE TABLE reclamos (id INTEGER PRIMARY KEY)")
            conexion.execute("INSERT INTO reclamos DEFAULT VALUES")

    with MemoriaConversacional(ruta_db) as memoria:
        grafo = crear_grafo_agente(
            _modelo("Respuesta."),
            [_crear_herramienta_vacia()],
            checkpointer=memoria.checkpointer,
        )
        for thread_id, mensaje in (
            ("hilo-vencido", "Debe borrarse."),
            ("hilo-activo", "Debe conservarse."),
        ):
            invocar_agente(
                grafo,
                mensaje,
                cliente_id=1,
                thread_id=thread_id,
                memoria=memoria,
            )

        fecha_vencida = (instante - timedelta(days=31)).isoformat()
        with closing(sqlite3.connect(ruta_db)) as conexion:
            with conexion:
                conexion.execute(
                    """
                    UPDATE actividad_hilos
                    SET ultima_actividad = ?
                    WHERE thread_id = ?
                    """,
                    (fecha_vencida, "hilo-vencido"),
                )

        assert memoria.purgar_hilos_vencidos(ahora=instante) == 1
        assert grafo.get_state(_config("hilo-vencido")).values == {}
        assert [
            mensaje.content
            for mensaje in grafo.get_state(
                _config("hilo-activo")
            ).values["messages"]
            if mensaje.type == "human"
        ] == ["Debe conservarse."]

        with closing(sqlite3.connect(ruta_db)) as conexion:
            actividad = conexion.execute(
                "SELECT thread_id FROM actividad_hilos"
            ).fetchall()

    assert actividad == [("hilo-activo",)]
    with closing(sqlite3.connect(ruta_negocio)) as conexion:
        cantidad_reclamos = conexion.execute(
            "SELECT COUNT(*) FROM reclamos"
        ).fetchone()[0]
    assert cantidad_reclamos == 1


def test_inicio_purga_hilos_que_ya_estaban_vencidos(
    tmp_path: Path,
) -> None:
    ruta_db = tmp_path / "checkpoints.sqlite"
    instante = datetime.now(timezone.utc)
    thread_id = "hilo-vencido-al-iniciar"

    with MemoriaConversacional(ruta_db) as memoria:
        grafo = crear_grafo_agente(
            _modelo("Respuesta."),
            [_crear_herramienta_vacia()],
            checkpointer=memoria.checkpointer,
        )
        invocar_agente(
            grafo,
            "Mensaje antiguo.",
            cliente_id=1,
            thread_id=thread_id,
            memoria=memoria,
        )
        fecha_vencida = (instante - timedelta(days=31)).isoformat()
        with closing(sqlite3.connect(ruta_db)) as conexion:
            with conexion:
                conexion.execute(
                    """
                    UPDATE actividad_hilos
                    SET ultima_actividad = ?
                    WHERE thread_id = ?
                    """,
                    (fecha_vencida, thread_id),
                )

    with MemoriaConversacional(ruta_db) as memoria:
        grafo = crear_grafo_agente(
            _modelo("No debe usarse."),
            [_crear_herramienta_vacia()],
            checkpointer=memoria.checkpointer,
        )
        assert grafo.get_state(_config(thread_id)).values == {}


def test_purga_rechaza_fecha_sin_zona_horaria(tmp_path: Path) -> None:
    with MemoriaConversacional(tmp_path / "checkpoints.sqlite") as memoria:
        try:
            memoria.purgar_hilos_vencidos(
                ahora=datetime(2026, 11, 13)
            )
        except ValueError as error:
            assert "zona horaria" in str(error)
        else:
            raise AssertionError("Se esperaba rechazar una fecha sin zona.")
