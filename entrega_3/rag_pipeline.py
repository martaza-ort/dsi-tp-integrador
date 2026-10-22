from __future__ import annotations

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever

from similitud_coseno import generar_embeddings
from vector_db import DIRECTORIO_CHROMA, NOMBRE_COLECCION


class EmbeddingsEcoLogix(Embeddings):
    """Adapta el modelo local ya usado para indexar la colección."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return generar_embeddings(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        return generar_embeddings([text])[0].tolist()


def crear_retriever(
    cantidad: int = 3,
) -> BaseRetriever:
    """Abre la colección persistida de Entrega 2 sin reindexarla."""

    if cantidad < 1:
        raise ValueError("La cantidad de documentos debe ser al menos 1.")

    if not DIRECTORIO_CHROMA.is_dir():
        raise FileNotFoundError(
            f"No existe la base ChromaDB en {DIRECTORIO_CHROMA}. "
            "Ejecutá vector_db.py para construirla."
        )

    cliente = chromadb.PersistentClient(path=str(DIRECTORIO_CHROMA))
    coleccion = cliente.get_collection(name=NOMBRE_COLECCION)

    if coleccion.count() == 0:
        raise ValueError(
            f"La colección ChromaDB '{NOMBRE_COLECCION}' está vacía. "
            "Ejecutá vector_db.py para indexar el corpus."
        )

    base_vectorial = Chroma(
        client=cliente,
        collection_name=NOMBRE_COLECCION,
        embedding_function=EmbeddingsEcoLogix(),
        create_collection_if_not_exists=False,
    )

    return base_vectorial.as_retriever(
        search_type="similarity",
        search_kwargs={"k": cantidad},
    )


def main() -> None:
    retriever = crear_retriever()
    documentos = retriever.invoke(
        "Necesito vasos biodegradables para una cafetería."
    )

    print(f"Ruta persistida: {DIRECTORIO_CHROMA}")
    print(f"Colección: {NOMBRE_COLECCION}")
    print(f"Documentos recuperados: {len(documentos)}")

    for posicion, documento in enumerate(documentos, start=1):
        print(
            f"{posicion}. {documento.metadata.get('titulo', 'Sin título')} "
            f"(categoría: {documento.metadata.get('categoria', 'Sin categoría')})"
        )
        print(documento.page_content)


if __name__ == "__main__":
    main()
