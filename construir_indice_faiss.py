from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from similitud_coseno import (
    cargar_documentos,
    preparar_texto,
    generar_embeddings,
)


ROOT = Path(__file__).resolve().parent

DIRECTORIO_INDICE = ROOT / "indice_faiss"
INDEX_PATH = DIRECTORIO_INDICE / "ecologix.index"
DOCUMENTOS_PATH = DIRECTORIO_INDICE / "documentos.json"


def construir_indice(embeddings: np.ndarray) -> faiss.Index:
    """
    Normaliza los embeddings y construye el índice FAISS.

    IndexFlatIP utiliza producto interno.
    Si los vectores están normalizados, el producto interno
    equivale a la similitud coseno.
    """

    embeddings_normalizados = embeddings.copy()

    faiss.normalize_L2(embeddings_normalizados)

    dimension = embeddings_normalizados.shape[1]

    indice = faiss.IndexFlatIP(dimension)

    indice.add(embeddings_normalizados)

    return indice


def guardar_indice(
    indice: faiss.Index,
    documentos: list[dict],
) -> None:
    """Guarda el índice y los documentos asociados."""

    DIRECTORIO_INDICE.mkdir(exist_ok=True)

    faiss.write_index(
        indice,
        str(INDEX_PATH),
    )

    with DOCUMENTOS_PATH.open("w", encoding="utf-8") as archivo:
        json.dump(
            documentos,
            archivo,
            ensure_ascii=False,
            indent=2,
        )


def verificar_persistencia() -> None:
    """Carga nuevamente el índice guardado para comprobarlo."""

    indice_recuperado = faiss.read_index(str(INDEX_PATH))

    with DOCUMENTOS_PATH.open("r", encoding="utf-8") as archivo:
        documentos_recuperados = json.load(archivo)

    print("\nVerificación de persistencia:")
    print("Vectores recuperados:", indice_recuperado.ntotal)
    print("Documentos recuperados:", len(documentos_recuperados))
    print("Dimensión del índice:", indice_recuperado.d)

    if indice_recuperado.ntotal == len(documentos_recuperados):
        print("Resultado: índice consistente")
    else:
        print("Resultado: índice inconsistente")


def main() -> None:
    print("Cargando documentos...")

    documentos = cargar_documentos()

    textos = [
        preparar_texto(documento)
        for documento in documentos
    ]

    print("Generando embeddings localmente...")

    embeddings = generar_embeddings(textos)

    print("Forma de la matriz:", embeddings.shape)

    indice = construir_indice(embeddings)

    guardar_indice(indice, documentos)

    print("\nÍndice FAISS construido correctamente")
    print("Cantidad de vectores:", indice.ntotal)
    print("Dimensión de los vectores:", indice.d)
    print("Índice guardado en:", INDEX_PATH)
    print("Documentos guardados en:", DOCUMENTOS_PATH)

    verificar_persistencia()


if __name__ == "__main__":
    main()