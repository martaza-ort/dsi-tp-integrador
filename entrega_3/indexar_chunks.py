from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from similitud_coseno import cargar_documentos, generar_embeddings, preparar_texto
from vector_db import (
    DIRECTORIO_CHROMA,
    NOMBRE_COLECCION,
    BaseVectorial,
)


TAMANO_CHUNK = 500
SOLAPAMIENTO_CHUNK = 100
NOMBRE_COLECCION_CHUNKS = "ecologix_chunks_500_100"
TAMANO_LOTE_BORRADO = 500


@dataclass(frozen=True)
class Fragmento:
    identificador: str
    texto: str
    metadatos: dict[str, Any]


def crear_chunks() -> list[Fragmento]:
    """Prepara chunks de los mismos textos usados por el índice original."""

    divisor = RecursiveCharacterTextSplitter(
        chunk_size=TAMANO_CHUNK,
        chunk_overlap=SOLAPAMIENTO_CHUNK,
        length_function=len,
    )
    chunks: list[Fragmento] = []

    for documento in cargar_documentos():
        texto = preparar_texto(documento)
        fragmentos = divisor.split_text(texto)
        metadatos = BaseVectorial.aplanar_metadatos(documento)
        metadatos["id_documento_origen"] = documento["id"]
        metadatos["titulo_documento_origen"] = metadatos.get("titulo", "")
        metadatos["cantidad_chunks_documento"] = len(fragmentos)

        for indice, fragmento in enumerate(fragmentos):
            metadatos_chunk = {
                **metadatos,
                "indice_chunk": indice,
            }
            chunks.append(
                Fragmento(
                    identificador=f"{documento['id']}-chunk-{indice:03d}",
                    texto=fragmento,
                    metadatos=metadatos_chunk,
                )
            )

    return chunks


def _reemplazar_contenido_coleccion(coleccion: chromadb.Collection) -> None:
    """Vacía solo la colección avanzada, manteniendo su esquema y configuración."""

    ids_existentes = coleccion.get(include=[])["ids"]
    for inicio in range(0, len(ids_existentes), TAMANO_LOTE_BORRADO):
        coleccion.delete(
            ids=ids_existentes[inicio : inicio + TAMANO_LOTE_BORRADO]
        )


def indexar_chunks() -> tuple[int, int]:
    """Reindexa el corpus fragmentado en su colección Chroma separada."""

    if not DIRECTORIO_CHROMA.is_dir():
        raise FileNotFoundError(
            f"No existe la base ChromaDB en {DIRECTORIO_CHROMA}. "
            "Ejecutá primero vector_db.py para crear el índice original."
        )

    cliente = chromadb.PersistentClient(path=str(DIRECTORIO_CHROMA))
    coleccion_original = cliente.get_collection(name=NOMBRE_COLECCION)
    coleccion_chunks = cliente.get_or_create_collection(
        name=NOMBRE_COLECCION_CHUNKS,
        metadata={"hnsw:space": "cosine"},
    )

    cantidad_original = coleccion_original.count()
    if cantidad_original == 0:
        raise ValueError(
            f"La colección original '{NOMBRE_COLECCION}' está vacía."
        )

    chunks = crear_chunks()
    textos = [chunk.texto for chunk in chunks]
    embeddings = generar_embeddings(textos)
    _reemplazar_contenido_coleccion(coleccion_chunks)
    coleccion_chunks.upsert(
        ids=[chunk.identificador for chunk in chunks],
        embeddings=embeddings.tolist(),
        metadatas=[chunk.metadatos for chunk in chunks],
        documents=textos,
    )

    return cantidad_original, coleccion_chunks.count()


def main() -> None:
    cantidad_original, cantidad_chunks = indexar_chunks()
    print(f"Colección original: {NOMBRE_COLECCION}")
    print(f"Documentos originales: {cantidad_original}")
    print(f"Colección con chunks: {NOMBRE_COLECCION_CHUNKS}")
    print(
        f"Configuración: tamaño={TAMANO_CHUNK}, "
        f"solapamiento={SOLAPAMIENTO_CHUNK} caracteres"
    )
    print(f"Chunks indexados: {cantidad_chunks}")


if __name__ == "__main__":
    main()
