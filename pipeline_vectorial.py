from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from similitud_coseno import generar_embeddings


ROOT = Path(__file__).resolve().parent

DIRECTORIO_INDICE = ROOT / "indice_faiss"
INDEX_PATH = DIRECTORIO_INDICE / "ecologix.index"
DOCUMENTOS_PATH = DIRECTORIO_INDICE / "documentos.json"


class PipelineVectorial:

    def __init__(self) -> None:

        if not INDEX_PATH.exists():
            raise FileNotFoundError(
                "No existe el índice FAISS. "
                "Ejecutá primero construir_indice_faiss.py."
            )

        if not DOCUMENTOS_PATH.exists():
            raise FileNotFoundError(
                "No existe el archivo documentos.json. "
                "Ejecutá primero construir_indice_faiss.py."
            )

        self.indice = faiss.read_index(str(INDEX_PATH))

        with DOCUMENTOS_PATH.open("r", encoding="utf-8") as archivo:
            self.documentos = json.load(archivo)

        self._validar_indice()

    def _validar_indice(self) -> None:

        cantidad_vectores = self.indice.ntotal
        cantidad_documentos = len(self.documentos)

        if cantidad_vectores != cantidad_documentos:
            raise ValueError(
                "El índice es inconsistente: "
                f"contiene {cantidad_vectores} vectores, "
                f"pero hay {cantidad_documentos} documentos."
            )

    def generar_embedding_consulta(
        self,
        consulta: str,
    ) -> np.ndarray:
        """Genera y normaliza el embedding de una consulta."""

        embeddings = generar_embeddings([consulta])

        if embeddings.shape[1] != self.indice.d:
            raise ValueError(
                "La dimensión de la consulta no coincide con "
                "la dimensión del índice. "
                f"Consulta: {embeddings.shape[1]}. "
                f"Índice: {self.indice.d}."
            )

        embedding_consulta = embeddings.astype(np.float32)

        faiss.normalize_L2(embedding_consulta)

        return embedding_consulta

    def buscar(
        self,
        consulta: str,
        cantidad: int = 3,
        umbral: float = 0.25,
    ) -> list[dict]:
        """Busca los documentos más parecidos a la consulta."""

        if not consulta.strip():
            return []

        cantidad = min(cantidad, self.indice.ntotal)

        embedding_consulta = self.generar_embedding_consulta(
            consulta
        )

        similitudes, posiciones = self.indice.search(
            embedding_consulta,
            cantidad,
        )

        resultados = []

        for similitud, posicion in zip(
            similitudes[0],
            posiciones[0],
        ):
            if posicion == -1:
                continue

            similitud = float(similitud)

            if similitud < umbral:
                continue

            documento = self.documentos[int(posicion)]
            metadatos = documento.get("metadatos", {})

            resultados.append(
                {
                    "id": documento.get("id"),
                    "titulo": metadatos.get("titulo"),
                    "tipo": metadatos.get("tipo"),
                    "categoria": metadatos.get("categoria"),
                    "descripcion_semantica": documento.get(
                        "descripcion_semantica"
                    ),
                    "metadatos": metadatos,
                    "similitud": round(similitud, 4),
                }
            )

        return resultados

    def buscar_por_intencion(
        self,
        consulta: str,
        intencion: str,
        cantidad: int = 3,
        umbral: float = 0.25,
    ) -> list[dict]:
        """
        Enriquece la consulta con la intención de negocio
        antes de realizar la búsqueda semántica.
        """

        descripciones = {
            "CONSULTA_STOCK": (
                "Consulta sobre productos, disponibilidad, "
                "stock y depósitos."
            ),
            "CREAR_PEDIDO": (
                "Compra de productos, cantidades, unidades "
                "de venta y confirmación de pedidos."
            ),
            "SEGUIMIENTO_PEDIDO": (
                "Seguimiento, estado, entrega o retiro "
                "de un pedido."
            ),
            "RECLAMO_ENTREGA": (
                "Reclamo por entrega, productos rotos, "
                "faltantes o problemas con el pedido."
            ),
            "OTRO": (
                "Consulta general que puede requerir "
                "derivación a una persona."
            ),
        }

        descripcion = descripciones.get(
            intencion,
            "Consulta general del negocio.",
        )

        consulta_enriquecida = (
            f"Intención: {intencion}. "
            f"{descripcion} "
            f"Mensaje del cliente: {consulta}"
        )

        return self.buscar(
            consulta=consulta_enriquecida,
            cantidad=cantidad,
            umbral=umbral,
        )

    def preparar_contexto(
        self,
        resultados: list[dict],
    ) -> str:
        """
        Convierte los documentos recuperados en texto
        utilizable por el pipeline principal.
        """

        if not resultados:
            return (
                "No se encontró información suficientemente "
                "relevante en la base de conocimiento."
            )

        fragmentos = []

        for resultado in resultados:
            fragmento = (
                f"Documento: {resultado['titulo']}\n"
                f"Tipo: {resultado['tipo']}\n"
                f"Categoría: {resultado['categoria']}\n"
                f"Contenido: {resultado['descripcion_semantica']}\n"
                f"Metadatos: {resultado['metadatos']}\n"
                f"Similitud: {resultado['similitud']}"
            )

            fragmentos.append(fragmento)

        return "\n\n---\n\n".join(fragmentos)


def main() -> None:
    """Permite probar el pipeline desde la terminal."""

    pipeline = PipelineVectorial()

    print("Pipeline vectorial de EcoLogix")
    print("Intenciones disponibles:")
    print("- CONSULTA_STOCK")
    print("- CREAR_PEDIDO")
    print("- SEGUIMIENTO_PEDIDO")
    print("- RECLAMO_ENTREGA")
    print("- OTRO")

    consulta = input("\nIngrese la consulta: ").strip()
    intencion = input("Ingrese la intención: ").strip().upper()

    resultados = pipeline.buscar_por_intencion(
        consulta=consulta,
        intencion=intencion,
        cantidad=3,
        umbral=0.25,
    )

    print("\nResultados recuperados:")

    if not resultados:
        print("No se encontraron resultados relevantes.")

    for posicion, resultado in enumerate(
        resultados,
        start=1,
    ):
        print(
            f"{posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    contexto = pipeline.preparar_contexto(resultados)

    print("\nContexto para el pipeline principal:\n")
    print(contexto)


if __name__ == "__main__":
    main()