from __future__ import annotations

from langchain_core.documents import Document

from entrega_3.indexar_chunks import NOMBRE_COLECCION_CHUNKS
from entrega_3.evaluar_b2 import CONSULTA_B1, MODELO_COMPARACION
from entrega_3.rag_pipeline import crear_cadena_rag_con_reranking


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
    resultado = crear_cadena_rag_con_reranking(
        cantidad_candidatos=8,
        cantidad_seleccionados=4,
        modelo=MODELO_COMPARACION,
        nombre_coleccion=NOMBRE_COLECCION_CHUNKS,
    ).invoke(CONSULTA_B1)

    print(f"Consulta: {CONSULTA_B1}")
    print(f"Modelo juez y generador: {MODELO_COMPARACION}")
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
