from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver


RETENCION_DIAS = 30
INTERVALO_PURGA_SEGUNDOS = 24 * 60 * 60
_LOGGER = logging.getLogger(__name__)


def validar_thread_id(thread_id: str) -> str:
    """Valida un identificador de hilo apto para la API de LangGraph."""

    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("thread_id debe ser un texto no vacío.")
    if thread_id != thread_id.strip() or len(thread_id) > 255:
        raise ValueError("thread_id debe tener entre 1 y 255 caracteres.")
    return thread_id


class MemoriaConversacional:
    """Administra checkpoints SQLite, actividad por hilo y purga por retención.

    Usar una única instancia por proceso y mantenerla abierta durante la vida
    del agente. La base configurada debe ser exclusiva para checkpoints y
    metadatos de actividad, separada de la base de negocio.

    `purgados_al_abrir` queda disponible después de `__enter__` con la
    cantidad de hilos vencidos que se purgaron al abrir la conexión. Una
    purga explícita posterior sobre esos mismos hilos no va a encontrar
    nada pendiente, así que quien necesite reportar cuánto se purgó al
    iniciar debe leer este atributo en vez de llamar de nuevo a
    `purgar_hilos_vencidos()`.
    """

    def __init__(self, ruta_db: Path) -> None:
        self.ruta_db = Path(ruta_db)
        self._conexion: sqlite3.Connection | None = None
        self._checkpointer: SqliteSaver | None = None
        self._lock_mapa = threading.Lock()
        self._locks_hilos: dict[str, threading.RLock] = {}
        self._detener_mantenimiento = threading.Event()
        self._hilo_mantenimiento: threading.Thread | None = None
        self.purgados_al_abrir: int = 0

    @property
    def checkpointer(self) -> SqliteSaver:
        if self._checkpointer is None:
            raise RuntimeError("La memoria SQLite todavía no está abierta.")
        return self._checkpointer

    def __enter__(self) -> MemoriaConversacional:
        if self._conexion is not None:
            raise RuntimeError("La memoria SQLite ya está abierta.")
        self.ruta_db.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )
        if os.name != "nt":
            descriptor = os.open(
                self.ruta_db,
                os.O_CREAT | os.O_RDWR,
                0o600,
            )
            os.close(descriptor)
            self.ruta_db.chmod(0o600)
        self._conexion = sqlite3.connect(
            self.ruta_db,
            check_same_thread=False,
        )
        self._conexion.execute("PRAGMA journal_mode=WAL")
        try:
            self._checkpointer = SqliteSaver(
                self._conexion,
                serde=JsonPlusSerializer(allowed_msgpack_modules=None),
            )
            self._checkpointer.setup()
            self._crear_tabla_actividad()
            self._restringir_permisos()
            self.purgados_al_abrir = self.purgar_hilos_vencidos()
            self._detener_mantenimiento.clear()
            self._hilo_mantenimiento = threading.Thread(
                target=self._mantener_retencion,
                name="purga-memoria-langgraph",
                daemon=True,
            )
            self._hilo_mantenimiento.start()
        except Exception:
            self._conexion.close()
            self._conexion = None
            self._checkpointer = None
            raise
        return self

    def __exit__(self, tipo: Any, valor: Any, traza: Any) -> None:
        self._detener_mantenimiento.set()
        if self._hilo_mantenimiento is not None:
            self._hilo_mantenimiento.join()
            self._hilo_mantenimiento = None
        if self._conexion is not None:
            self._conexion.close()
            self._conexion = None
            self._checkpointer = None

    def invocar(
        self,
        grafo: Any,
        entrada: dict[str, Any],
        *,
        thread_id: str,
        contexto: Any,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Registra actividad y ejecuta una interacción protegida contra purga."""

        identificador = validar_thread_id(thread_id)
        lock_hilo = self._lock_hilo(identificador)
        with lock_hilo:
            try:
                self._registrar_actividad(
                    identificador,
                    datetime.now(timezone.utc),
                )
                return grafo.invoke(entrada, config=config, context=contexto)
            finally:
                self._restringir_permisos()

    def purgar_hilos_vencidos(
        self,
        ahora: datetime | None = None,
    ) -> int:
        """Elimina hilos inactivos por 30 días con la API del checkpointer.

        Returns:
            Cantidad de hilos purgados.

        Raises:
            RuntimeError: Si la memoria no está abierta.
            Exception: Si falla la purga; el error se propaga al invocador.
        """

        checkpointer = self.checkpointer
        instante = ahora or datetime.now(timezone.utc)
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError("ahora debe incluir zona horaria.")
        limite = (instante.astimezone(timezone.utc) - timedelta(
            days=RETENCION_DIAS
        )).isoformat()
        vencidos = self._buscar_hilos_vencidos(limite)
        cantidad_purgada = 0

        for thread_id in vencidos:
            with self._lock_hilo(thread_id):
                if not self._sigue_vencido(thread_id, limite):
                    continue
                checkpointer.delete_thread(thread_id)
                self._eliminar_actividad(thread_id)
                self._restringir_permisos()
                cantidad_purgada += 1
            self._olvidar_lock_hilo(thread_id)

        return cantidad_purgada

    def _lock_hilo(self, thread_id: str) -> threading.RLock:
        with self._lock_mapa:
            return self._locks_hilos.setdefault(thread_id, threading.RLock())

    def _olvidar_lock_hilo(self, thread_id: str) -> None:
        """Libera el lock de un hilo purgado para no crecer sin límite."""

        with self._lock_mapa:
            self._locks_hilos.pop(thread_id, None)

    def _mantener_retencion(self) -> None:
        while not self._detener_mantenimiento.wait(
            INTERVALO_PURGA_SEGUNDOS
        ):
            try:
                purgados = self.purgar_hilos_vencidos()
                if purgados:
                    _LOGGER.info(
                        "Se purgaron hilos vencidos de la memoria conversacional."
                    )
            except Exception:
                _LOGGER.exception(
                    "Falló la purga periódica de memoria SQLite."
                )

    def _crear_tabla_actividad(self) -> None:
        with self._conexion:
            self._conexion.execute(
                """
                CREATE TABLE IF NOT EXISTS actividad_hilos (
                    thread_id TEXT PRIMARY KEY,
                    ultima_actividad TEXT NOT NULL
                )
                """
            )

    def _restringir_permisos(self) -> None:
        if os.name == "nt":
            return
        rutas = (
            self.ruta_db,
            Path(f"{self.ruta_db}-wal"),
            Path(f"{self.ruta_db}-shm"),
        )
        for ruta in rutas:
            if ruta.exists():
                ruta.chmod(0o600)

    def _registrar_actividad(
        self,
        thread_id: str,
        instante: datetime,
    ) -> None:
        marca_tiempo = instante.astimezone(timezone.utc).isoformat()
        with self._conexion:
            self._conexion.execute(
                """
                INSERT INTO actividad_hilos (thread_id, ultima_actividad)
                VALUES (?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    ultima_actividad = excluded.ultima_actividad
                """,
                (thread_id, marca_tiempo),
            )

    def _buscar_hilos_vencidos(self, limite: str) -> list[str]:
        filas = self._conexion.execute(
            """
            SELECT thread_id
            FROM actividad_hilos
            WHERE ultima_actividad <= ?
            """,
            (limite,),
        ).fetchall()
        return [fila[0] for fila in filas]

    def _sigue_vencido(self, thread_id: str, limite: str) -> bool:
        fila = self._conexion.execute(
            """
            SELECT 1
            FROM actividad_hilos
            WHERE thread_id = ? AND ultima_actividad <= ?
            """,
            (thread_id, limite),
        ).fetchone()
        return fila is not None

    def _eliminar_actividad(self, thread_id: str) -> None:
        with self._conexion:
            self._conexion.execute(
                "DELETE FROM actividad_hilos WHERE thread_id = ?",
                (thread_id,),
            )
