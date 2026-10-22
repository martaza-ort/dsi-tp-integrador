from __future__ import annotations

import os
from pathlib import Path
import warnings

from dotenv import load_dotenv
from langchain_core.documents import Document

from entrega_3.indexar_chunks import NOMBRE_COLECCION_CHUNKS
from entrega_3.evaluar_b2 import CONSULTA_B1, MODELO_COMPARACION
from entrega_3.rag_pipeline import crear_cadena_rag_con_reranking


def crear_configuracion_traza() -> dict[str, object]:
    """Carga y valida LangSmith sin revelar ni registrar la API key."""

    raiz_proyecto = Path(__file__).resolve().parents[1]
    load_dotenv(raiz_proyecto / ".env", override=True)

    if os.getenv("LANGSMITH_TRACING", "").strip().lower() not in {
        "true",
        "1",
        "yes",
    }:
        raise RuntimeError(
            "La traza B.4 requiere LANGSMITH_TRACING=true en el archivo .env."
        )
    if not os.getenv("LANGSMITH_API_KEY"):
        raise RuntimeError(
            "La traza B.4 requiere LANGSMITH_API_KEY en el archivo .env."
        )

    proyecto = os.getenv("LANGSMITH_PROJECT", "").strip()
    if not proyecto:
        raise RuntimeError(
            "La traza B.4 requiere LANGSMITH_PROJECT en el archivo .env."
        )

    return {
        "run_name": "B4-reranking-gemini-35-flash-lite",
        "tags": [
            "entrega-3",
            "B4",
            "reranking",
            "gemini-3.5-flash-lite",
        ],
        "metadata": {
            "proyecto_langsmith": proyecto,
            "modelo": MODELO_COMPARACION,
            "coleccion": NOMBRE_COLECCION_CHUNKS,
            "cantidad_candidatos": 8,
            "cantidad_seleccionados_maxima": 4,
        },
    }


def limpiar_metadatos_agente_incompletos() -> None:
    """Evita metadatos locales de agente inválidos para una traza estándar."""

    if (
        os.getenv("LANGSMITH_AGENT_ENVIRONMENT")
        and not os.getenv("LANGSMITH_AGENT_ID")
    ):
        os.environ.pop("LANGSMITH_AGENT_ENVIRONMENT")
        warnings.warn(
            "Se ignora LANGSMITH_AGENT_ENVIRONMENT porque falta "
            "LANGSMITH_AGENT_ID; se usará el tracing estándar de LangChain.",
            RuntimeWarning,
            stacklevel=2,
        )


def imprimir_documentos(titulo: str, documentos: list[Document]) -> None:
    print(f"\n{titulo}:")
    for posicion, documento in enumerate(documentos, start=1):
        metadatos = documento.metadata
        titulo_fuente = metadatos.get(
            "titulo_documento_origen",
            metadatos.get("titulo", "Sin título"),
        )
        indice_chunk = metadatos.get("indice_chunk")
        sufijo_chunk = (
            f", chunk {indice_chunk}"
            if indice_chunk is not None
            else ""
        )
        print(f"{posicion}. {titulo_fuente}{sufijo_chunk}")
        print(documento.page_content)


def main() -> None:
    configuracion_traza = crear_configuracion_traza()
    cadena = crear_cadena_rag_con_reranking(
        cantidad_candidatos=8,
        cantidad_seleccionados=4,
        modelo=MODELO_COMPARACION,
        nombre_coleccion=NOMBRE_COLECCION_CHUNKS,
    )
    limpiar_metadatos_agente_incompletos()
    resultado = cadena.invoke(CONSULTA_B1, config=configuracion_traza)

    print(f"Consulta: {CONSULTA_B1}")
    print(f"Modelo juez y generador: {MODELO_COMPARACION}")
    print(f"Proyecto LangSmith: {os.environ['LANGSMITH_PROJECT']}")
    imprimir_documentos(
        "Los 8 candidatos recuperados",
        resultado["candidate_documents"],
    )
    imprimir_documentos(
        "Documentos seleccionados por el juez",
        resultado["selected_documents"],
    )
    print("\nRespuesta generada:")
    print(resultado["answer"])


if __name__ == "__main__":
    main()
