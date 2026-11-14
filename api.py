"""API REST del agente EcoLogix (Parte B del TP Final).

Endpoints:
    GET    /health                 Estado del servicio.
    POST   /consultar              Consulta al agente.
    GET    /estado/{thread_id}     Historial de una conversación propia.
    DELETE /estado/{thread_id}     Borra una conversación propia.

Identidad: cada solicitud a /consultar y /estado debe traer
`Authorization: Bearer <token>`. El token se resuelve a un `cliente_id` en el
backend (variable `API_CLIENTES`); nunca se toma del mensaje ni del LLM.
Esta tabla de tokens es una identidad fija para demo y tests, no una
autenticación de producción.

Aislamiento de hilos: el `thread_id` que ve el cliente no es una credencial.
Internamente se usa HMAC(secreto, cliente_id + thread_id), así que un cliente
no puede leer ni borrar el hilo de otro aunque adivine su `thread_id`, y el
identificador guardado en los checkpoints no revela al cliente.

Ejecutar con un solo proceso (ver README):
    uvicorn api:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from agente import crear_grafo_agente, crear_herramientas, invocar_agente
from memoria import MemoriaConversacional, validar_thread_id


RAIZ = Path(__file__).resolve().parent
RUTA_MEMORIA_DEFAULT = RAIZ / "runtime" / "checkpoints.sqlite"
RUTA_DB_NEGOCIO_DEFAULT = RAIZ / "runtime" / "ecologix.db"

MENSAJE_ERROR_INTERNO = (
    "No pudimos procesar tu consulta en este momento. Intentá de nuevo en "
    "unos minutos o comunicate con un operador."
)
MENSAJE_NO_AUTENTICADO = "Credenciales inválidas o ausentes."
MENSAJE_HILO_INEXISTENTE = "No se encontró una conversación con ese identificador."

logger = logging.getLogger("ecologix.api")


# --- Contratos de la API ----------------------------------------------------

class SolicitudConsulta(BaseModel):
    """Cuerpo de POST /consultar."""

    mensaje: str = Field(description="Consulta en lenguaje natural.")
    thread_id: str | None = Field(
        default=None,
        description="Conversación a continuar. Si se omite, se crea una nueva.",
    )

    @field_validator("mensaje")
    @classmethod
    def validar_mensaje(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("El mensaje no puede estar vacío.")
        return valor

    @field_validator("thread_id")
    @classmethod
    def validar_hilo(cls, valor: str | None) -> str | None:
        return validar_thread_id(valor) if valor is not None else None


class RespuestaConsulta(BaseModel):
    thread_id: str
    respuesta: str
    exito: bool
    herramientas_utilizadas: list[str]


class MensajeHistorial(BaseModel):
    rol: str
    contenido: str


class RespuestaEstado(BaseModel):
    thread_id: str
    cantidad_mensajes: int
    herramientas_ejecutadas: int
    mensajes: list[MensajeHistorial]


# --- Configuración ----------------------------------------------------------

@dataclass
class ConfiguracionAPI:
    """Dependencias inyectables; los tests pasan un modelo falso y bases temporales."""

    clientes_por_token: dict[str, int]
    secreto_hilos: bytes
    ruta_memoria: Path = RUTA_MEMORIA_DEFAULT
    fabrica_modelo: Callable[[], BaseChatModel] | None = None
    fabrica_herramientas: Callable[[], list[BaseTool]] | None = None


def _parsear_clientes(valor: str) -> dict[str, int]:
    """Lee `API_CLIENTES="token1:1,token2:2"`."""

    clientes: dict[str, int] = {}
    for par in filter(None, (parte.strip() for parte in valor.split(","))):
        token, _, cliente = par.rpartition(":")
        if not token or not cliente.isdigit() or int(cliente) < 1:
            raise RuntimeError(
                "API_CLIENTES debe tener el formato token:cliente_id separado por comas."
            )
        clientes[token] = int(cliente)
    return clientes


def configuracion_desde_entorno() -> ConfiguracionAPI:
    """Construye la configuración real a partir de `.env`."""

    load_dotenv(RAIZ / ".env")
    clientes = _parsear_clientes(os.getenv("API_CLIENTES", ""))
    if not clientes:
        raise RuntimeError("Configurá API_CLIENTES en .env (ver .env.example).")
    secreto = os.getenv("HILOS_SECRETO", "")
    if len(secreto) < 32:
        raise RuntimeError(
            "Configurá HILOS_SECRETO en .env con al menos 32 caracteres aleatorios."
        )

    ruta_db = Path(os.getenv("RUTA_DB_NEGOCIO", str(RUTA_DB_NEGOCIO_DEFAULT)))

    def fabrica_modelo() -> BaseChatModel:
        # Reutiliza el proveedor configurado para el RAG (RAG_PROVIDER).
        from entrega_3.rag_pipeline import _crear_modelo_chat

        return _crear_modelo_chat()

    return ConfiguracionAPI(
        clientes_por_token=clientes,
        secreto_hilos=secreto.encode("utf-8"),
        ruta_memoria=Path(os.getenv("RUTA_MEMORIA", str(RUTA_MEMORIA_DEFAULT))),
        fabrica_modelo=fabrica_modelo,
        fabrica_herramientas=lambda: crear_herramientas(ruta_db),
    )


# --- Utilidades -------------------------------------------------------------

def _hilo_interno(secreto: bytes, cliente_id: int, thread_id: str) -> str:
    """Identificador interno no derivable del cliente ni del thread_id público."""

    firma = hmac.new(
        secreto, f"{cliente_id}:{thread_id}".encode("utf-8"), hashlib.sha256
    )
    return firma.hexdigest()


def _texto(mensaje: BaseMessage) -> str:
    contenido = mensaje.content
    if isinstance(contenido, str):
        return contenido
    partes = [
        parte.get("text", "") if isinstance(parte, dict) else str(parte)
        for parte in contenido
    ]
    return "".join(partes)


def _mensajes_del_turno(mensajes: list[BaseMessage]) -> list[BaseMessage]:
    """Mensajes generados en la última interacción (después del último humano)."""

    for indice in range(len(mensajes) - 1, -1, -1):
        if isinstance(mensajes[indice], HumanMessage):
            return mensajes[indice + 1 :]
    return mensajes


def _resumir_turno(mensajes: list[BaseMessage]) -> dict[str, Any]:
    herramientas = [m.name or "desconocida" for m in mensajes if isinstance(m, ToolMessage)]
    errores = sum(
        1
        for m in mensajes
        if isinstance(m, ToolMessage) and getattr(m, "status", "success") == "error"
    )
    respuestas = [m for m in mensajes if isinstance(m, AIMessage) and not m.tool_calls]
    return {
        "herramientas": herramientas,
        "errores_herramientas": errores,
        "respuesta": _texto(respuestas[-1]) if respuestas else "",
    }


# --- Aplicación -------------------------------------------------------------

def crear_app(configuracion: ConfiguracionAPI | None = None) -> FastAPI:
    """Crea la aplicación FastAPI.

    Sin argumentos lee la configuración de `.env`; los tests inyectan una
    configuración con modelo falso, base temporal y tokens de prueba.
    """

    seguridad = HTTPBearer(auto_error=False)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        config = configuracion or configuracion_desde_entorno()
        if config.fabrica_modelo is None or config.fabrica_herramientas is None:
            raise RuntimeError("La configuración necesita fábrica de modelo y de herramientas.")

        memoria = MemoriaConversacional(config.ruta_memoria)
        memoria.__enter__()
        try:
            grafo = crear_grafo_agente(
                config.fabrica_modelo(),
                config.fabrica_herramientas(),
                checkpointer=memoria.checkpointer,
            )
            app.state.config = config
            app.state.memoria = memoria
            app.state.grafo = grafo
            logger.info("Servicio iniciado.")
            yield
        finally:
            memoria.__exit__(None, None, None)
            logger.info("Servicio detenido.")

    app = FastAPI(
        title="EcoLogix — Agente API",
        version="1.0.0",
        lifespan=ciclo_de_vida,
    )

    def cliente_autenticado(
        request: Request,
        credenciales: HTTPAuthorizationCredentials | None = Depends(seguridad),
    ) -> int:
        clientes = request.app.state.config.clientes_por_token
        if credenciales is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAJE_NO_AUTENTICADO)
        for token, cliente_id in clientes.items():
            if hmac.compare_digest(credenciales.credentials, token):
                return cliente_id
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAJE_NO_AUTENTICADO)

    @app.exception_handler(Exception)
    async def error_no_controlado(request: Request, error: Exception) -> JSONResponse:
        logger.error("Error no controlado (%s).", type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": MENSAJE_ERROR_INTERNO})

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        return {
            "estado": "ok",
            "agente": getattr(request.app.state, "grafo", None) is not None,
            "memoria": getattr(request.app.state, "memoria", None) is not None,
        }

    @app.post("/consultar", response_model=RespuestaConsulta)
    def consultar(
        solicitud: SolicitudConsulta,
        request: Request,
        cliente_id: int = Depends(cliente_autenticado),
    ) -> Any:
        thread_id = solicitud.thread_id or str(uuid.uuid4())
        config: ConfiguracionAPI = request.app.state.config
        try:
            resultado = invocar_agente(
                request.app.state.grafo,
                mensaje=solicitud.mensaje,
                cliente_id=cliente_id,
                thread_id=_hilo_interno(config.secreto_hilos, cliente_id, thread_id),
                memoria=request.app.state.memoria,
            )
        except Exception as error:
            # Solo el tipo de error: el mensaje puede incluir datos del usuario.
            logger.error("Falló la consulta al agente (%s).", type(error).__name__)
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, MENSAJE_ERROR_INTERNO
            ) from None

        turno = _resumir_turno(_mensajes_del_turno(resultado["messages"]))
        exito = turno["errores_herramientas"] == 0 and bool(turno["respuesta"])
        return RespuestaConsulta(
            thread_id=thread_id,
            respuesta=turno["respuesta"] or MENSAJE_ERROR_INTERNO,
            exito=exito,
            herramientas_utilizadas=turno["herramientas"],
        )

    def _validar_hilo_publico(thread_id: str) -> str:
        try:
            return validar_thread_id(thread_id)
        except ValueError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, MENSAJE_HILO_INEXISTENTE) from None

    @app.get("/estado/{thread_id}", response_model=RespuestaEstado)
    def obtener_estado(
        thread_id: str,
        request: Request,
        cliente_id: int = Depends(cliente_autenticado),
    ) -> Any:
        thread_id = _validar_hilo_publico(thread_id)
        config: ConfiguracionAPI = request.app.state.config
        interno = _hilo_interno(config.secreto_hilos, cliente_id, thread_id)
        foto = request.app.state.grafo.get_state({"configurable": {"thread_id": interno}})
        mensajes: list[BaseMessage] = (foto.values or {}).get("messages", [])
        if not mensajes:
            raise HTTPException(status.HTTP_404_NOT_FOUND, MENSAJE_HILO_INEXISTENTE)

        historial = []
        for mensaje in mensajes:
            if isinstance(mensaje, HumanMessage):
                historial.append(MensajeHistorial(rol="cliente", contenido=_texto(mensaje)))
            elif isinstance(mensaje, AIMessage) and not mensaje.tool_calls:
                historial.append(MensajeHistorial(rol="asistente", contenido=_texto(mensaje)))
        return RespuestaEstado(
            thread_id=thread_id,
            cantidad_mensajes=len(historial),
            herramientas_ejecutadas=sum(isinstance(m, ToolMessage) for m in mensajes),
            mensajes=historial,
        )

    @app.delete("/estado/{thread_id}")
    def borrar_estado(
        thread_id: str,
        request: Request,
        cliente_id: int = Depends(cliente_autenticado),
    ) -> dict[str, Any]:
        thread_id = _validar_hilo_publico(thread_id)
        config: ConfiguracionAPI = request.app.state.config
        interno = _hilo_interno(config.secreto_hilos, cliente_id, thread_id)
        try:
            existia = request.app.state.memoria.eliminar_hilo(interno)
        except Exception as error:
            logger.error("Falló el borrado de una conversación (%s).", type(error).__name__)
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "No se pudo borrar la conversación.",
            ) from None
        if not existia:
            raise HTTPException(status.HTTP_404_NOT_FOUND, MENSAJE_HILO_INEXISTENTE)
        return {"thread_id": thread_id, "eliminado": True}

    return app


def __getattr__(nombre: str) -> Any:
    """Crea `app` solo cuando uvicorn la pide (`uvicorn api:app`).

    Así importar este módulo en los tests no exige un `.env` real.
    """

    if nombre == "app":
        aplicacion = crear_app()
        globals()["app"] = aplicacion
        return aplicacion
    raise AttributeError(nombre)
