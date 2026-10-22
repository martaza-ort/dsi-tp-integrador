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

CAMPOS_PRINCIPALES = ("id",)
UMBRAL_ACEPTACION = 0.35
UMBRAL_MARGEN_DOMINIO = 0.05

EJEMPLOS_DOMINIO = [
    "Quiero comprar bolsas compostables para mi comercio",
    "Necesito vasos biodegradables para servir café",
    "Busco envases ecológicos para enviar comida",
    "Necesito sorbetes disponibles en stock",
    "Quiero consultar el estado de mi pedido",
    "Me llegó mercadería rota y quiero reclamar",
    "Quiero saber si hacen envíos a mi zona",
    "Cuál es el mínimo de compra",
    "Necesito productos sustentables para mi restaurante",
    "Busco artículos descartables biodegradables",
]

EJEMPLOS_FUERA_DOMINIO = [
    "Quiero comprar una computadora portátil",
    "Necesito accesorios electrónicos para mi teléfono",
    "Busco alquilar un departamento",
    "Necesito repuestos y neumáticos para mi auto",
    "Quiero reservar un pasaje de avión",
    "Necesito pedir un préstamo bancario",
    "Quiero sacar un turno médico",
    "Busco ropa y zapatillas deportivas",
]

TIPOS_SIMPLES = (str, int, float, bool)

_ANCLA_DOMINIO: np.ndarray | None = None
_EMBEDDINGS_EJEMPLOS_DOMINIO: np.ndarray | None = None
_EMBEDDINGS_EJEMPLOS_FUERA: np.ndarray | None = None

def cargar_documentos() -> list[dict]:
    """Carga los documentos de la base de conocimiento limpia."""

    with DATASET_PATH.open("r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    return datos["documentos"]


def _normalizar(vector: np.ndarray) -> np.ndarray:
    """Escala un embedding a longitud 1 para el producto interno."""

    return vector / np.linalg.norm(vector)

def _normalizar_matriz(matriz: np.ndarray) -> np.ndarray:
    """Normaliza cada fila de una matriz de embeddings."""

    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    return matriz / normas

def ancla_dominio() -> np.ndarray:
    """
    Embedding promedio del corpus: la representación del dominio.

    Permite preguntar si una consulta "habla" del dominio EcoLogix
    usando el propio corpus como referencia, en lugar de una lista
    de palabras clave.
    """

    global _ANCLA_DOMINIO

    if _ANCLA_DOMINIO is None:
        documentos = cargar_documentos()
        textos = [
            preparar_texto(documento)
            for documento in documentos
        ]
        matriz = generar_embeddings(textos)
        _ANCLA_DOMINIO = _normalizar(matriz.mean(axis=0))

    return _ANCLA_DOMINIO


def similitud_ancla(consulta: str) -> float:
    """Similitud coseno entre la consulta y el ancla del dominio."""

    embedding = _normalizar(generar_embeddings([consulta])[0])
    return float(embedding @ ancla_dominio())

def evaluar_dominio(consulta: str) -> dict:
    """
    Compara la consulta con ejemplos semánticos del dominio EcoLogix
    y con ejemplos representativos de dominios ajenos.

    No utiliza palabras clave. La consulta se acepta cuando su mejor
    similitud con los ejemplos de EcoLogix supera a su mejor similitud
    con ejemplos ajenos por un margen mínimo.
    """

    global _EMBEDDINGS_EJEMPLOS_DOMINIO
    global _EMBEDDINGS_EJEMPLOS_FUERA

    if _EMBEDDINGS_EJEMPLOS_DOMINIO is None:
        _EMBEDDINGS_EJEMPLOS_DOMINIO = _normalizar_matriz(
            generar_embeddings(EJEMPLOS_DOMINIO)
        )

    if _EMBEDDINGS_EJEMPLOS_FUERA is None:
        _EMBEDDINGS_EJEMPLOS_FUERA = _normalizar_matriz(
            generar_embeddings(EJEMPLOS_FUERA_DOMINIO)
        )

    embedding_consulta = _normalizar(
        generar_embeddings([consulta])[0]
    )

    similitud_dominio = float(
        np.max(_EMBEDDINGS_EJEMPLOS_DOMINIO @ embedding_consulta)
    )
    similitud_fuera = float(
        np.max(_EMBEDDINGS_EJEMPLOS_FUERA @ embedding_consulta)
    )
    margen = similitud_dominio - similitud_fuera

    return {
        "similitud_dominio": round(similitud_dominio, 4),
        "similitud_fuera": round(similitud_fuera, 4),
        "margen_dominio": round(margen, 4),
        "umbral_margen": UMBRAL_MARGEN_DOMINIO,
        "aceptada": margen >= UMBRAL_MARGEN_DOMINIO,
    }

def _expandir(condicion: dict) -> list[dict]:
    """Aplana un `$and` para componer filtros sin anidarlos."""

    if set(condicion) == {"$and"}:
        partes: list[dict] = []
        for interna in condicion["$and"]:
            partes.extend(_expandir(interna))
        return partes

    return [condicion]


def construir_where(
    filtro_x: dict | None = None,
    solo_activos: bool = False,
    donde: dict | None = None,
) -> dict | None:
    """
    Arma el filtro duro de la query.

    Regla de B.4: todo filtro de negocio viaja adentro del `where`
    de ChromaDB. Acá solo se combinan condiciones; nunca se descarta
    un documento con un `if` de Python después de la query.
    """

    condiciones: list[dict] = []

    for filtro in (donde, filtro_x):
        if filtro:
            condiciones.extend(_expandir(filtro))

    if solo_activos:
        condiciones.append({"activo": {"$eq": True}})

    if not condiciones:
        return None

    if len(condiciones) == 1:
        return condiciones[0]

    return {"$and": condiciones}


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

        metadatos = dict(documento.get("metadatos", {}))

        for clave, valor in documento.get("metadatos", {}).items():
            es_lista_valida = (
                isinstance(valor, list)
                and len(valor) > 0
                and all(isinstance(item, TIPOS_SIMPLES) for item in valor)
            )

            if isinstance(valor, TIPOS_SIMPLES) or es_lista_valida:
                metadatos[clave] = (
                    " ".join(str(item) for item in valor)
                    if isinstance(valor, list)
                    else valor
                )

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
        umbral: float = UMBRAL_ACEPTACION,
        validar_dominio: bool = True,
    ) -> list[dict]:
        """
        Busca los documentos más parecidos a la consulta.

        El filtrado de negocio va dentro del `where` de ChromaDB
        (ver `construir_where`). Acá no hay post-filtering en Python:
        lo único que se descarta es lo que quedó por debajo del
        umbral de aceptación de C.2. Si no queda nada, la salida es
        vacía para que el sistema responda "no tengo esa información".

        Cada resultado incluye `similitud_ancla`, la cercanía de la
        consulta al centroide del corpus. Es un diagnóstico: permite
        distinguir "no encontré nada" de "encontré algo del dominio
        correcto", y no decide el resultado.
        """

        if not consulta or not consulta.strip():
            return []

        diagnostico_dominio = evaluar_dominio(consulta)

        if validar_dominio and not diagnostico_dominio["aceptada"]:
            return []

        cantidad = min(cantidad, self.coleccion.count())
        if cantidad == 0:
            return []

        ancla = round(similitud_ancla(consulta), 4)
        cantidad = min(cantidad, self.coleccion.count())
        ancla = round(similitud_ancla(consulta), 4)

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

            if similitud < umbral:
                continue

            resultados.append(
                {
                    "id": identificador,
                    "titulo": metadata.get("titulo"),
                    "tipo": metadata.get("tipo"),
                    "categoria": metadata.get("categoria"),
                    "descripcion_semantica": texto,
                    "metadatos": {
                        clave: valor
                        for clave, valor in metadata.items()
                        if clave not in CAMPOS_PRINCIPALES
                    },
                    "similitud": similitud,
                    "similitud_ancla": ancla,
                    "similitud_dominio": diagnostico_dominio["similitud_dominio"],
                    "similitud_fuera": diagnostico_dominio["similitud_fuera"],
                    "margen_dominio": diagnostico_dominio["margen_dominio"],
                }
            )

        return resultados

    def buscar_ecologix(
        self,
        query_semantica: str,
        filtro_x: dict | None = None,
        solo_activos: bool = False,
        n_resultados: int = 3,
        umbral: float = UMBRAL_ACEPTACION,
        validar_dominio: bool = True,
    )     -> list[dict]:
            """
            CLI de búsqueda híbrida de B.4.

            Combina búsqueda semántica con filtro duro por operadores
            nativos de ChromaDB, en la firma que pide la consigna.
            """

            return self.buscar(
                consulta=query_semantica,
                cantidad=n_resultados,
                donde=construir_where(
                    filtro_x=filtro_x,
                    solo_activos=solo_activos,
                ),
                umbral=umbral,
                validar_dominio=validar_dominio,
            )


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
            donde={"unidad_venta": {"$eq": "caja"}},
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
                    {"categoria": {"$eq": "vajilla"}},
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
            donde={"material": {"$eq": "carton"}},
        ),
        start=1,
    ):
        print(
            f"   {posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    print("\n5) CLI de búsqueda híbrida (firma de la consigna):")
    for posicion, resultado in enumerate(
        base.buscar_ecologix(
            query_semantica="Necesito sorbetes para mi kiosco",
            filtro_x={"categoria": {"$eq": "sorbetes"}},
            solo_activos=True,
            n_resultados=3,
        ),
        start=1,
    ):
        print(
            f"   {posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    consulta_fuera = "Venden celulares o accesorios de telefonia?"

    print("\n6) Consulta fuera del catálogo (Killer Query 3):")
    print("   Consulta:", consulta_fuera)
    print("   similitud_ancla:", round(similitud_ancla(consulta_fuera), 4))

    for posicion, resultado in enumerate(
        base.buscar(consulta=consulta_fuera, cantidad=3),
        start=1,
    ):
        print(
            f"   {posicion}. {resultado['titulo']} "
            f"- similitud: {resultado['similitud']}"
        )

    print(
    "\n   El caso se decide mediante comparación semántica con ejemplos\n"
    "   del dominio y de dominios ajenos, sin utilizar palabras clave."
    )

    verificar_persistencia()


if __name__ == "__main__":
    main()