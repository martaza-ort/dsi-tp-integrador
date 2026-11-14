"""Observabilidad de la API del agente (Parte C).

- Logs JSON estructurados, sin texto de consultas, datos personales ni
  credenciales. Para correlacionar se usa un identificador aleatorio por
  solicitud que no permite derivar la identidad del cliente ni el thread_id.
- Métricas en memoria, thread-safe, acumuladas desde el inicio del proceso
  y expuestas en `GET /metricas`.
- Configuración de trazas de LangSmith que oculta entradas y salidas.

Las métricas no se consolidan entre procesos: la API está pensada para un
único proceso (igual que la memoria SQLite).
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Literal


NOMBRE_LOGGER = "ecologix.api"
UMBRAL_ALERTA_P95_MS = 5000.0
# Decisión pendiente de la propuesta base: se fija una muestra mínima de 20
# consultas para no publicar un p95 con pocos datos. Configurable por .env.
MUESTRA_MINIMA_P95_DEFAULT = 20
# Precios de referencia de gpt-4o-mini en USD por millón de tokens. Verificar
# en la página de precios del proveedor y ajustar en .env si cambian.
PRECIO_ENTRADA_USD_MILLON_DEFAULT = 0.15
PRECIO_SALIDA_USD_MILLON_DEFAULT = 0.60

ResultadoConsulta = Literal["exitosa", "fallida", "bloqueada"]

# Campos estándar de LogRecord que no se copian al JSON.
_CAMPOS_ESTANDAR = set(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime"}


class FormateadorJSON(logging.Formatter):
    """Emite cada registro como una línea JSON."""

    def format(self, registro: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                registro.created, tz=timezone.utc
            ).isoformat(),
            "nivel": registro.levelname,
            "logger": registro.name,
            "evento": registro.getMessage(),
        }
        for clave, valor in registro.__dict__.items():
            if clave not in _CAMPOS_ESTANDAR and not clave.startswith("_"):
                datos[clave] = valor
        if registro.exc_info and registro.exc_info[0] is not None:
            # Solo el tipo de excepción: el mensaje puede incluir datos.
            datos["tipo_error"] = registro.exc_info[0].__name__
        return json.dumps(datos, ensure_ascii=False, default=str)


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Configura el logger de la API con salida JSON a stdout."""

    logger = logging.getLogger(NOMBRE_LOGGER)
    logger.setLevel(nivel)
    if not any(
        isinstance(manejador.formatter, FormateadorJSON)
        for manejador in logger.handlers
    ):
        manejador = logging.StreamHandler(sys.stdout)
        manejador.setFormatter(FormateadorJSON())
        logger.addHandler(manejador)
    logger.propagate = False
    return logger


def configurar_trazas_langsmith() -> bool:
    """Activa LangSmith solo si está configurado y oculta entradas/salidas.

    Con `LANGSMITH_TRACING=true` y una API key, las trazas registran la
    estructura (nodos, herramientas usadas, latencias y tokens) pero no el
    texto de las consultas ni de las respuestas, salvo que se desactive
    explícitamente el ocultamiento con datos sintéticos.

    Returns:
        True si el tracing quedó activo.
    """

    activo = os.getenv("LANGSMITH_TRACING", "false").strip().lower() == "true"
    if not activo or not os.getenv("LANGSMITH_API_KEY"):
        os.environ["LANGSMITH_TRACING"] = "false"
        return False
    os.environ.setdefault("LANGSMITH_HIDE_INPUTS", "true")
    os.environ.setdefault("LANGSMITH_HIDE_OUTPUTS", "true")
    return True


def _leer_float(nombre: str, por_defecto: float) -> float:
    try:
        return float(os.getenv(nombre, str(por_defecto)))
    except ValueError:
        return por_defecto


def percentil_nearest_rank(valores: list[float], percentil: float) -> float:
    """Percentil por rango más cercano (el criterio visto en la Unidad 6).

    Ordena las latencias y toma la posición ceil(p/100 * n).
    """

    ordenados = sorted(valores)
    posicion = max(1, math.ceil(percentil / 100 * len(ordenados)))
    return ordenados[posicion - 1]


class Metricas:
    """Contadores y latencias de `POST /consultar`, con acceso thread-safe."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
        muestra_minima_p95: int | None = None,
        umbral_p95_ms: float = UMBRAL_ALERTA_P95_MS,
    ) -> None:
        self._lock = threading.Lock()
        self._logger = logger or logging.getLogger(NOMBRE_LOGGER)
        self.muestra_minima_p95 = (
            muestra_minima_p95
            if muestra_minima_p95 is not None
            else int(
                _leer_float("MUESTRA_MINIMA_P95", MUESTRA_MINIMA_P95_DEFAULT)
            )
        )
        self.umbral_p95_ms = umbral_p95_ms
        self._precio_entrada = _leer_float(
            "PRECIO_ENTRADA_USD_MILLON", PRECIO_ENTRADA_USD_MILLON_DEFAULT
        )
        self._precio_salida = _leer_float(
            "PRECIO_SALIDA_USD_MILLON", PRECIO_SALIDA_USD_MILLON_DEFAULT
        )
        self._consultas = {"total": 0, "exitosas": 0, "fallidas": 0, "bloqueadas": 0}
        self._bloqueos_por_categoria: dict[str, int] = {}
        self._herramientas: dict[str, int] = {}
        self._errores_herramientas = 0
        self._latencias_ms: list[float] = []
        self._tokens_entrada = 0
        self._tokens_salida = 0
        self._alerta_activa = False
        self._inicio = datetime.now(timezone.utc)

    def registrar_consulta(
        self,
        resultado: ResultadoConsulta,
        latencia_ms: float,
        *,
        herramientas: list[str] | None = None,
        errores_herramientas: int = 0,
        tokens_entrada: int = 0,
        tokens_salida: int = 0,
        categoria_bloqueo: str | None = None,
    ) -> None:
        """Registra una solicitud que llegó al manejador de /consultar."""

        with self._lock:
            self._consultas["total"] += 1
            clave = {
                "exitosa": "exitosas",
                "fallida": "fallidas",
                "bloqueada": "bloqueadas",
            }[resultado]
            self._consultas[clave] += 1
            if resultado == "bloqueada" and categoria_bloqueo:
                self._bloqueos_por_categoria[categoria_bloqueo] = (
                    self._bloqueos_por_categoria.get(categoria_bloqueo, 0) + 1
                )
            for nombre in herramientas or []:
                self._herramientas[nombre] = self._herramientas.get(nombre, 0) + 1
            self._errores_herramientas += errores_herramientas
            self._tokens_entrada += tokens_entrada
            self._tokens_salida += tokens_salida
            self._latencias_ms.append(float(latencia_ms))
            self._evaluar_alerta()

    def _calcular_p95(self) -> float | None:
        if len(self._latencias_ms) < max(1, self.muestra_minima_p95):
            return None
        return percentil_nearest_rank(self._latencias_ms, 95)

    def _evaluar_alerta(self) -> None:
        p95 = self._calcular_p95()
        activa = p95 is not None and p95 > self.umbral_p95_ms
        if activa and not self._alerta_activa:
            self._logger.warning(
                "alerta_latencia_activada",
                extra={"p95_ms": round(p95, 1), "umbral_ms": self.umbral_p95_ms},
            )
        elif not activa and self._alerta_activa:
            self._logger.info("alerta_latencia_normalizada")
        self._alerta_activa = activa

    def _costo_usd(self) -> float:
        return (
            self._tokens_entrada * self._precio_entrada
            + self._tokens_salida * self._precio_salida
        ) / 1_000_000

    def obtener(self) -> dict[str, Any]:
        """Devuelve una foto de las métricas para `GET /metricas`."""

        with self._lock:
            latencias = list(self._latencias_ms)
            p95 = self._calcular_p95()
            total = self._consultas["total"]
            costo = self._costo_usd()
            return {
                "desde": self._inicio.isoformat(),
                "consultas": dict(self._consultas),
                "errores": self._consultas["fallidas"],
                "bloqueos": {
                    "total": self._consultas["bloqueadas"],
                    "por_categoria": dict(self._bloqueos_por_categoria),
                },
                "latencia_ms": {
                    "promedio": (
                        round(sum(latencias) / len(latencias), 1)
                        if latencias
                        else None
                    ),
                    "p95": round(p95, 1) if p95 is not None else None,
                    "muestras": len(latencias),
                    "muestra_minima_p95": self.muestra_minima_p95,
                    "umbral_alerta_p95": self.umbral_p95_ms,
                },
                "alerta_latencia": self._alerta_activa,
                "herramientas": {
                    "invocaciones": dict(self._herramientas),
                    "errores": self._errores_herramientas,
                },
                "costos": {
                    "tokens_entrada": self._tokens_entrada,
                    "tokens_salida": self._tokens_salida,
                    "costo_estimado_usd": round(costo, 6),
                    "costo_promedio_por_consulta_usd": (
                        round(costo / total, 6) if total else None
                    ),
                    "precio_entrada_usd_por_millon": self._precio_entrada,
                    "precio_salida_usd_por_millon": self._precio_salida,
                },
            }
