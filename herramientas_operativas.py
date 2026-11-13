from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolRuntime

from contexto_agente import ContextoAgente


def _validar_cliente_id(cliente_id: int) -> int:
    """Valida la identidad confiable inyectada por el backend."""

    if isinstance(cliente_id, bool) or not isinstance(cliente_id, int):
        raise ValueError("El contexto autenticado no contiene un cliente_id válido.")
    if cliente_id < 1:
        raise ValueError("El contexto autenticado no contiene un cliente_id válido.")
    return cliente_id


def _validar_nro_pedido(nro_pedido: int) -> int:
    if isinstance(nro_pedido, bool) or not isinstance(nro_pedido, int):
        raise ValueError("El número de pedido debe ser un entero positivo.")
    if nro_pedido < 1:
        raise ValueError("El número de pedido debe ser un entero positivo.")
    return nro_pedido


def _cliente_id_de_contexto(
    runtime: ToolRuntime[ContextoAgente],
) -> int:
    contexto = runtime.context
    if not isinstance(contexto, ContextoAgente):
        raise ValueError("El contexto autenticado del agente no es válido.")
    return _validar_cliente_id(contexto.cliente_id)


def _conectar_base(ruta_db: Path) -> sqlite3.Connection:
    if not ruta_db.is_file():
        raise FileNotFoundError(
            f"No existe la base SQLite en {ruta_db}. "
            "Inicializala usando schema.sql antes de invocar las herramientas."
        )

    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_herramientas_operativas(ruta_db: Path) -> list[BaseTool]:
    """Crea las tools de envío y reclamos ligadas a una base SQLite.

    `cliente_id` se inyecta desde el contexto confiable de ejecución de
    LangGraph y se excluye tanto del esquema visible para el modelo como del
    estado persistido. La API debe poblar ese contexto a partir de la identidad
    autenticada, nunca desde el mensaje ni desde argumentos del LLM.
    """

    ruta_db = Path(ruta_db)

    @tool
    def consultar_estado_envio(
        nro_pedido: int,
        runtime: ToolRuntime[ContextoAgente],
    ) -> str:
        """Consulta el estado de envío de un pedido propio del cliente.

        Args:
            nro_pedido: Número del pedido cuyo envío consulta el cliente.

        Returns:
            Estado y fechas operativas del envío si el pedido pertenece al
            cliente autenticado. Si el pedido no existe, no pertenece al
            cliente o aún no tiene envío, devuelve un mensaje neutro.

        Note:
            El cliente autenticado se inyecta desde el estado confiable del
            grafo; no se acepta un identificador de cliente del modelo.
        """

        id_cliente = _cliente_id_de_contexto(runtime)
        id_pedido = _validar_nro_pedido(nro_pedido)
        consulta = """
            SELECT envios.estado, envios.despachado_en, envios.entregado_en
            FROM pedidos
            JOIN envios ON envios.pedido_id = pedidos.id
            WHERE pedidos.id = ? AND pedidos.cliente_id = ?
            ORDER BY envios.id DESC
            LIMIT 1
        """

        with closing(_conectar_base(ruta_db)) as conexion:
            envio = conexion.execute(
                consulta,
                (id_pedido, id_cliente),
            ).fetchone()

        if envio is None:
            return "No se encontró un envío disponible para ese pedido."

        datos = [f"Estado del envío: {envio['estado']}"]
        if envio["despachado_en"]:
            datos.append(f"Despachado: {envio['despachado_en']}")
        if envio["entregado_en"]:
            datos.append(f"Entregado: {envio['entregado_en']}")
        return ". ".join(datos) + "."

    @tool
    def registrar_reclamo(
        runtime: ToolRuntime[ContextoAgente],
        motivo: str,
        nro_pedido: int | None = None,
    ) -> str:
        """Registra un reclamo solicitado por el cliente autenticado.

        Args:
            motivo: Descripción del problema informado por el cliente.
            nro_pedido: Número de un pedido propio relacionado, si se conoce.

        Returns:
            Identificador y estado inicial del reclamo creado.

        Note:
            La identidad se inyecta desde el estado confiable del grafo. Si se
            indica un pedido, se valida la titularidad antes de insertar. El
            alta no genera notas de crédito ni aprueba compensaciones.
        """

        id_cliente = _cliente_id_de_contexto(runtime)
        if not isinstance(motivo, str) or not motivo.strip():
            raise ValueError("El motivo del reclamo no puede estar vacío.")

        id_pedido = (
            _validar_nro_pedido(nro_pedido)
            if nro_pedido is not None
            else None
        )

        with closing(_conectar_base(ruta_db)) as conexion:
            try:
                with conexion:
                    if id_pedido is not None:
                        pedido = conexion.execute(
                            """
                            SELECT 1
                            FROM pedidos
                            WHERE id = ? AND cliente_id = ?
                            """,
                            (id_pedido, id_cliente),
                        ).fetchone()
                        if pedido is None:
                            return (
                                "No se pudo registrar el reclamo con ese "
                                "pedido. Verificá el número o consultá a "
                                "un operador."
                            )

                    cursor = conexion.execute(
                        """
                        INSERT INTO reclamos (pedido_id, cliente_id, motivo)
                        VALUES (?, ?, ?)
                        """,
                        (id_pedido, id_cliente, motivo.strip()),
                    )
                    id_reclamo = cursor.lastrowid
            except sqlite3.IntegrityError as error:
                raise RuntimeError(
                    "No se pudo registrar el reclamo por una inconsistencia "
                    "de datos."
                ) from error

        return f"Reclamo registrado con ID {id_reclamo}, estado ABIERTO."

    return [consultar_estado_envio, registrar_reclamo]
