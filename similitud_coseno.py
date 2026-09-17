from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "base_conocimiento_limpia.json"

modelo = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def cargar_documentos() -> list[dict]:
    """Carga los documentos de la base de conocimiento limpia."""

    with DATASET_PATH.open("r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    return datos["documentos"]


def preparar_texto(documento: dict) -> str:
    """Une los campos relevantes que representarán al documento."""

    titulo = documento.get("titulo", "")
    texto = documento.get("texto", "")
    categoria = documento.get("categoria", "")
    tags = " ".join(documento.get("tags", []))

    return (
        f"Título: {titulo}. "
        f"Categoría: {categoria}. "
        f"Descripción: {texto}. "
        f"Etiquetas: {tags}."
    )


def generar_embeddings(textos: list[str]) -> np.ndarray:
    """Convierte los textos en embeddings utilizando un modelo local."""

    embeddings = modelo.encode(
        textos,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return embeddings.astype(np.float32)


def similitud_coseno(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    """Calcula manualmente la similitud coseno entre dos vectores."""

    producto_escalar = np.dot(vector_a, vector_b)
    norma_a = np.linalg.norm(vector_a)
    norma_b = np.linalg.norm(vector_b)

    if norma_a == 0 or norma_b == 0:
        return 0.0

    return float(producto_escalar / (norma_a * norma_b))


def main() -> None:
    documentos = cargar_documentos()
    textos = [preparar_texto(documento) for documento in documentos]

    embeddings = generar_embeddings(textos)

    print("Cantidad de documentos:", len(documentos))
    print("Forma de la matriz:", embeddings.shape)
    print("Dimensión de cada embedding:", embeddings.shape[1])

    consulta = "Necesito vasos biodegradables para una cafetería"
    embedding_consulta = generar_embeddings([consulta])[0]

    resultados = []

    for posicion, embedding_documento in enumerate(embeddings):
        similitud = similitud_coseno(
            embedding_consulta,
            embedding_documento,
        )

        resultados.append(
            {
                "documento": documentos[posicion],
                "similitud": similitud,
            }
        )

    resultados.sort(
        key=lambda resultado: resultado["similitud"],
        reverse=True,
    )

    print(f"\nConsulta: {consulta}")
    print("\nDocumentos más parecidos:")

    for resultado in resultados[:3]:
        documento = resultado["documento"]

        print(
            f"- {documento['titulo']} "
            f"(similitud: {resultado['similitud']:.4f})"
        )


if __name__ == "__main__":
    main()