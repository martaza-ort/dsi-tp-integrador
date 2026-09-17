from __future__ import annotations

import json
from pathlib import Path

import chromadb
import numpy as np

from similitud_coseno import (
    preparar_texto,
    generar_embeddings,
)


ROOT = Path(__file__).resolve().parent

DIRECTORIO_CHROMA = ROOT / "chroma"
NOMBRE_COLECCION = "ecologix"
DATASET_PATH = ROOT / "base_conocimiento_limpia.json"

CAMPOS_PRINCIPALES = ("id", "titulo", "tipo", "categoria")

TIPOS_SIMPLES = (str, int, float, bool)


def cargar_documentos() -> list[dict]:
    """Carga los documentos de la base de conocimiento limpia."""

    with DATASET_PATH.open("r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    return datos["documentos"]


class BaseVectorial:

    def __init__(
        self,
        directorio: Path = DIRECTORIO_CHROMA,
    ) -> None:
        """Abre (o crea) la colección persistente en ChromaDB."""

        directorio.mkdir(exist_ok=True)

        self.cliente = chromadb.PersistentClient(
            path=str(directorio),
        )

        self.coleccion = self.cliente.get_or_create_collection(
            name=NOMBRE_COLECCION,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def aplanar_metadatos(documento: dict) -> dict:
        """
        Convierte los metadatos del corpus en metadatos planos
        compatibles con ChromaDB (tipos simples o listas de
        tipos simples, sin valores None).
        """

        metadatos = {
            campo: documento[campo]
            for campo in CAMPOS_PRINCIPALES
            if campo in documento
        }

        for clave, valor in documento.get("metadatos", {}).items():
            es_lista_valida = (
                isinstance(valor, list)
                and len(valor) > 0
                and all(isinstance(item, TIPOS_SIMPLES) for item in valor)
            )

            if isinstance(valor, TIPOS_SIMPLES) or es_lista_valida:
                metadatos[clave] = valor

        return metadatos

    def indexar_documentos(self, documentos: list[dict]) -> int:
        """Genera los embeddings y hace upsert de todo el corpus."""

        ids = [documento["id"] for documento in documentos]

        textos = [
            preparar_texto(documento)
            for documento in documentos
        ]

        embeddings = generar_embeddings(textos)
        metadatos = [
            self.aplanar_metadatos(documento)
            for documento in documentos
        ]

        self.coleccion.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatos,
            documents=textos,
        )

        return self.coleccion.count()

    def buscar(
        self,
        consulta: str,
        cantidad: int = 3,
        donde: dict | None = None,
    ) -> list[dict]:
        """
        Busca los documentos más parecidos a la consulta.

        El filtro se aplica con el `where` nativo de ChromaDB,
        sin post-filtering manual.
        """

        if not consulta.strip():
            return []

        cantidad = min(cantidad, self.coleccion.count())

        embeddings = generar_embeddings([consulta])
        embedding_consulta = embeddings[0].astype(np.float32)

        resultado = self.coleccion.query(
            query_embeddings=[embedding_consulta],
            n_results=cantidad,
            where=donde if donde else None,
            include=["metadatas", "documents", "distances"],
        )

        ids = resultado["ids"][0]
        distancias = resultado["distances"][0]
        metadatos = resultado["metadatas"][0]
        documentos = resultado["documents"][0]

        resultados = []

        for identificador, distancia, metadata, texto in zip(
            ids,
            distancias,
            metadatos,
            documentos,
        ):
            similitud = round(1 - float(distancia), 4)

            resultados.append(
                {
                    "id": identificador,
                    "titulo": metadata.get("titulo"),
                    "tipo": metadata.get("tipo"),
                    "categoria": metadata.get("categoria"),
                    "texto": texto,
                    "metadatos": {
                        clave: valor
                        for clave, valor in metadata.items()
                        if clave not in CAMPOS_PRINCIPALES
                    },
                    "similitud": similitud,
                }
            )

        return resultados


def verificar_persistencia() -> None:
    """Abre un cliente nuevo para comprobar que la data sobrevive."""

    cliente_nuevo = chromadb.PersistentClient(
        path=str(DIRECTORIO_CHROMA),
    )

    coleccion = cliente_nuevo.get_collection(NOMBRE_COLECCION)

    print("\nVerificación de persistencia:")
    print("Documentos persistidos:", coleccion.count())
    print("Espacio de distancia:", coleccion.metadata.get("hnsw:space"))

    if coleccion.count() > 0:
        print("Resultado: base persistente consistente")
    else:
        print("Resultado: base vacía, revisar indexación")


def main() -> None:
    print("Cargando documentos...")

    documentos = cargar_documentos()

    base = BaseVectorial()
    cantidad = base.indexar_documentos(documentos)

    print("Documentos indexados:", cantidad)

    consulta = (
        "Necesito vasos descartables biodegradables "
        "para una cafetería"
    )

    print("\nConsulta:", consulta)

    print("\n1) Búsqueda sin filtros:")
    for posicion, resultado in enumerate(
        base.buscar(consulta=consulta, cantidad=3),
        start=1,
    ):
        print(
            f"   {posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    print("\n2) Búsqueda con filtro where unidad_venta=caja:")
    for posicion, resultado in enumerate(
        base.buscar(
            consulta=consulta,
            cantidad=3,
            donde={"unidad_venta": "caja"},
        ),
        start=1,
    ):
        print(
            f"   {posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    print("\n3) Búsqueda con filtro combinado $and:")
    for posicion, resultado in enumerate(
        base.buscar(
            consulta=consulta,
            cantidad=3,
            donde={
                "$and": [
                    {"categoria": "vajilla"},
                    {"material": {"$eq": "bagazo"}},
                ]
            },
        ),
        start=1,
    ):
        print(
            f"   {posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    print("\n4) Búsqueda con filtro where material=carton:")
    for posicion, resultado in enumerate(
        base.buscar(
            consulta=consulta,
            cantidad=2,
            donde={"material": "carton"},
        ),
        start=1,
    ):
        print(
            f"   {posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    verificar_persistencia()


if __name__ == "__main__":
    main()