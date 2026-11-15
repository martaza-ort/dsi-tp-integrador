"""Métricas y logging estructurado para la API EcoLogix."""

from __future__ import annotations

import json
import logging
import math
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Any
import os

MUESTRA_MINIMA_P95 = 20
UMBRAL_ALERTA_MS = 5_000.0

VARIABLES_PRIVACIDAD_LANGSMITH = (
    "LANGSMITH_HIDE_INPUTS",
    "LANGSMITH_HIDE_OUTPUTS",
    "LANGSMITH_HIDE_METADATA",
)


def _variable_verdadera(nombre: str) -> bool:
    return os.getenv(nombre, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def validar_privacidad_langsmith() -> None:
    """Impide activar tracing sin ocultamiento completo del contenido."""

    tracing_activo = _variable_verdadera("LANGSMITH_TRACING")

    if not tracing_activo:
        return

    faltantes = [
        nombre
        for nombre in VARIABLES_PRIVACIDAD_LANGSMITH
        if not _variable_verdadera(nombre)
    ]

    if faltantes:
        raise RuntimeError(
            "LangSmith requiere ocultar inputs, outputs y metadatos. "
            "Revisá la configuración de privacidad del tracing."
        )


class FormateadorJSON(logging.Formatter):
    """Convierte registros controlados de la aplicación a JSON."""

    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "evento": record.getMessage(),
        }

        categoria = getattr(record, "categoria", None)
        if categoria is not None:
            evento["categoria"] = categoria

        resultado = getattr(record, "resultado", None)
        if resultado is not None:
            evento["resultado"] = resultado

        correlacion_id = getattr(record, "correlacion_id", None)
        if correlacion_id is not None:
            evento["correlacion_id"] = correlacion_id

        return json.dumps(evento, ensure_ascii=False)


def configurar_logging_json() -> None:
    """Configura los logs propios de EcoLogix en formato JSON."""

    logger_ecologix = logging.getLogger("ecologix")

    if any(
        getattr(handler, "_ecologix_json", False)
        for handler in logger_ecologix.handlers
    ):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(FormateadorJSON())
    handler._ecologix_json = True  # type: ignore[attr-defined]

    logger_ecologix.handlers.clear()
    logger_ecologix.addHandler(handler)
    logger_ecologix.setLevel(logging.INFO)
    logger_ecologix.propagate = False


class MetricasAPI:
    """Acumula métricas en memoria con acceso thread-safe."""

    def __init__(
        self,
        muestra_minima_p95: int = MUESTRA_MINIMA_P95,
        umbral_alerta_ms: float = UMBRAL_ALERTA_MS,
    ) -> None:
        if muestra_minima_p95 < 1:
            raise ValueError("La muestra mínima de p95 debe ser positiva.")
        if umbral_alerta_ms <= 0:
            raise ValueError("El umbral de latencia debe ser positivo.")

        self._lock = threading.Lock()
        self._inicio = datetime.now(timezone.utc)
        self._muestra_minima_p95 = muestra_minima_p95
        self._umbral_alerta_ms = float(umbral_alerta_ms)

        self._total = 0
        self._exitosas = 0
        self._fallidas = 0
        self._bloqueadas = 0
        self._latencias_ms: list[float] = []
        self._herramientas: Counter[str] = Counter()
        self._errores_herramientas = 0
        self._alerta_latencia = False

        self._logger = logging.getLogger("ecologix.metricas")

    @staticmethod
    def _percentil_95(valores: list[float]) -> float:
        """Calcula p95 mediante el método de rango más próximo."""

        ordenados = sorted(valores)
        posicion = max(0, math.ceil(0.95 * len(ordenados)) - 1)
        return ordenados[posicion]

    def registrar_consulta(
        self,
        *,
        latencia_ms: float,
        exito: bool,
        bloqueada: bool = False,
        herramientas: list[str] | None = None,
        errores_herramientas: int = 0,
    ) -> None:
        """Registra una solicitud válida que ingresó a POST /consultar."""

        if latencia_ms < 0:
            raise ValueError("La latencia no puede ser negativa.")
        if errores_herramientas < 0:
            raise ValueError("Los errores de herramientas no pueden ser negativos.")
        if bloqueada and exito:
            raise ValueError("Una consulta bloqueada no puede ser exitosa.")

        activar_alerta = False

        with self._lock:
            self._total += 1
            self._latencias_ms.append(float(latencia_ms))

            if bloqueada:
                self._bloqueadas += 1
            elif exito:
                self._exitosas += 1
            else:
                self._fallidas += 1

            self._herramientas.update(herramientas or [])
            self._errores_herramientas += errores_herramientas

            if len(self._latencias_ms) >= self._muestra_minima_p95:
                p95 = self._percentil_95(self._latencias_ms)
                nueva_alerta = p95 > self._umbral_alerta_ms
                activar_alerta = nueva_alerta and not self._alerta_latencia
                self._alerta_latencia = nueva_alerta
            else:
                self._alerta_latencia = False

        if activar_alerta:
            self._logger.warning(
                "Umbral de latencia p95 superado.",
                extra={
                    "categoria": "latencia",
                    "resultado": "alerta_activada",
                },
            )

    def obtener(self) -> dict[str, Any]:
        """Devuelve una fotografía consistente de las métricas acumuladas."""

        with self._lock:
            latencias = list(self._latencias_ms)
            promedio = (
                sum(latencias) / len(latencias)
                if latencias
                else None
            )
            p95 = (
                self._percentil_95(latencias)
                if len(latencias) >= self._muestra_minima_p95
                else None
            )

            return {
                "desde": self._inicio.isoformat(),
                "consultas": {
                    "total": self._total,
                    "exitosas": self._exitosas,
                    "fallidas": self._fallidas,
                    "bloqueadas": self._bloqueadas,
                },
                "latencia_ms": {
                    "promedio": round(promedio, 2) if promedio is not None else None,
                    "p95": round(p95, 2) if p95 is not None else None,
                    "muestras": len(latencias),
                    "muestra_minima_p95": self._muestra_minima_p95,
                },
                "herramientas": {
                    "invocaciones_por_nombre": dict(self._herramientas),
                    "errores": self._errores_herramientas,
                },
                "alerta_latencia": self._alerta_latencia,
                "umbral_alerta_ms": self._umbral_alerta_ms,
            }