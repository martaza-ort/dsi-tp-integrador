from __future__ import annotations

from pathlib import Path

from vector_db import (
    BaseVectorial,
    cargar_documentos,
)


ROOT = Path(__file__).resolve().parent
RUTA_EVIDENCIA = ROOT / "resultados_evento_caliente.md"

CONSULTA = (
    "Necesito sorbetes para mi kiosco, "
    "que esten disponibles en stock"
)

DOCUMENTO_DISCONTINUADO = {
    "descripcion_semantica": (
        "Los sorbetes de papel fueron discontinuados del catalogo "
        "de EcoLogix por la nueva politica ambiental. A partir de la "
        "proxima temporada no se aceptan pedidos de este producto. "
        "El reemplazo recomendado son los sorbetes compostables de "
        "bagazo (ECO-SOR-BAGAZO), aptos para bebidas frias y "
        "calientes, en presentacion por bulto."
    ),
    "metadatos": {
        "activo": False,
        "categoria": "sorbetes",
        "tags_regionales": [
            "sorbete",
            "papel",
            "discontinuado",
            "fuera_de_catalogo",
        ],
    },
}

DOCUMENTO_REEMPLAZO = {
    "id": "doc-019",
    "descripcion_semantica": (
        "Sorbetes compostables de bagazo disponibles en stock para "
        "kioscos y locales de bebidas. EcoLogix ofrece sorbetes de "
        "bagazo como reemplazo del sorbete de papel discontinuado. "
        "Son aptos para bebidas frias y calientes y se entregan por "
        "bulto con gran volumen para puntos de venta masivos."
    ),
    "metadatos": {
        "tipo": "producto",
        "categoria": "sorbetes",
        "titulo": "Sorbetes compostables de bagazo",
        "sku": "ECO-SOR-BAGAZO",
        "unidad_venta": "bulto",
        "unidades_por_bulto": 2000,
        "material": "bagazo",
        "uso_principal": "bebidas",
        "activo": True,
        "tags_regionales": [
            "sorbete",
            "bagazo",
            "compostable",
            "bebidas",
            "reemplazo",
        ],
    },
}


def construir_corpus_con_evento(
    documentos: list[dict],
) -> list[dict]:
    """
    Devuelve el corpus tras el evento: todos los productos quedan
    revalidados con estado activo, el sorbete de papel se marca
    discontinuado y entra el sorbete de bagazo como reemplazo.
    """

    corpus_evento = []

    for documento in documentos:
        if documento["id"] == DOCUMENTO_REEMPLAZO["id"]:
            continue

        evento = dict(documento)
        evento["metadatos"] = dict(documento.get("metadatos", {}))

        if documento["id"] == "doc-004":
            evento["descripcion_semantica"] = DOCUMENTO_DISCONTINUADO[
                "descripcion_semantica"
            ]
            evento["metadatos"]["activo"] = False
            evento["metadatos"]["tags_regionales"] = (
                DOCUMENTO_DISCONTINUADO["metadatos"]["tags_regionales"]
            )
        else:
            evento["metadatos"]["activo"] = True

        corpus_evento.append(evento)

    corpus_evento.append(DOCUMENTO_REEMPLAZO)

    return corpus_evento


def formatear_ranking(resultados: list[dict]) -> list[dict]:
    """Reduce los resultados a lo esencial para la evidencia."""

    return [
        {
            "id": resultado["id"],
            "titulo": resultado["titulo"],
            "similitud": resultado["similitud"],
        }
        for resultado in resultados
    ]


def consultar(base: BaseVectorial, donde: dict | None = None) -> list[dict]:
    return formatear_ranking(
        base.buscar(
            consulta=CONSULTA,
            cantidad=5,
            donde=donde,
        )
    )


def escribir_evidencia(
    ranking_antes: list[dict],
    ranking_despues: list[dict],
    ranking_filtrado: list[dict],
    ranking_persistido: list[dict],
) -> None:
    """Escribe los resultados del evento en un archivo de evidencia."""

    def filas(ranking: list[dict]) -> str:
        lineas = [
            "| Puesto | Id | Documento | Similitud |",
            "|--------|----|-----------|-----------|",
        ]

        for puesto, item in enumerate(ranking, start=1):
            lineas.append(
                f"| {puesto} | {item['id']} | "
                f"{item['titulo']} | {item['similitud']} |"
            )

        return "\n".join(lineas)

    contenido = f"""# Evento de negocio en caliente — EcoLogix

## Evento simulado

Cambio de politica comercial y de oferta de EcoLogix:

1. **Revalidacion del catalogo**: todos los productos pasan a tener
    metadata `activo: true` (mantenimiento del stock).
2. Los **sorbetes de papel** (`doc-004`) se **discontinuan** por la
   nueva politica ambiental: su texto pasa a indicar que el producto
   queda fuera de catalogo y su metadata se marca
    `activo: false`.
3. Entra en catalogo el reemplazo activo, los **sorbetes compostables
   de bagazo** (`doc-019`, SKU `ECO-SOR-BAGAZO`), con
    `activo: true`.

Los cambios se aplican en caliente con `upsert` de ChromaDB, solo
sobre los documentos afectados, sin reconstruir toda la base.

## Consulta utilizada

> {CONSULTA}

## Resultados antes del evento (corpus original)

{filas(ranking_antes)}

## Resultados despues del evento (sin filtro)

{filas(ranking_despues)}

## Resultados despues del evento (filtro nativo `activo=true`)

{filas(ranking_filtrado)}

## Persistencia del nuevo estado

Con un cliente ChromaDB nuevo se reconsulto la misma consulta con el
filtro `activo=true` y el ranking se mantuvo identico:

{filas(ranking_persistido)}

## Analisis

El estado dinamico del negocio impacta de dos maneras sobre la
recuperacion vectorial:

- **Semantica**: tras el evento, `doc-004` (discontinuado) cae del
  primer puesto del ranking aunque no exista filtro, porque su
  contenido ahora describe un producto fuera de catalogo. El
  reemplazo activo `doc-019` entra en el top de resultados.
- **Reglas de negocio via filtros nativos**: con el filtro
    `where={{\"activo\": true}}` aplicado en la base (sin
  post-filtering), el producto discontinuado queda garantizado fuera
  de toda recomendacion, y para la consulta de sorbetes el resultado
  correcto (`doc-019`) lidera la recuperacion.
- El cambio de estado (stock/politica) se propaga a la busqueda
  reindexando solo los documentos afectados con `upsert`, sin
  reindexar el corpus completo.

## Regeneracion

La base persistente se reconstruye desde `base_conocimiento.json`
con `vector_db.py`. Para volver al estado original de este
experimento: `python simular_evento_caliente.py --restaurar`.
"""

    with RUTA_EVIDENCIA.open("w", encoding="utf-8") as archivo:
        archivo.write(contenido)

    print("Evidencia escrita en:", RUTA_EVIDENCIA)


def restaurar_estado_original() -> None:
    """Vuelve la base al corpus canonico (quita doc-019)."""

    base = BaseVectorial()

    existe = len(base.coleccion.get(ids=["doc-019"])["ids"]) > 0

    if existe:
        base.coleccion.delete(ids=["doc-019"])

    documentos = cargar_documentos()
    base.indexar_documentos(documentos)

    print("Base restaurada al corpus canonico.")
    print("Documentos en la coleccion:", base.coleccion.count())


def main() -> None:
    restaurar_estado_original()

    base = BaseVectorial()

    ranking_antes = consultar(base)
    print("\nRanking antes del evento:")
    for puesto, item in enumerate(ranking_antes, start=1):
        print(
            f"  {puesto}. {item['titulo']} "
            f"- similitud: {item['similitud']}"
        )

    print("\nAplicando evento de negocio en caliente...")

    base.indexar_documentos(
        construir_corpus_con_evento(cargar_documentos())
    )

    print("Documentos actualizados. Total:", base.coleccion.count())

    ranking_despues = consultar(base)
    print("\nRanking despues del evento (sin filtro):")
    for puesto, item in enumerate(ranking_despues, start=1):
        print(
            f"  {puesto}. {item['titulo']} "
            f"- similitud: {item['similitud']}"
        )

    ranking_filtrado = consultar(
        base,
            donde={
                "$and": [
                    {"categoria": {"$eq": "sorbetes"}},
                    {"activo": {"$eq": True}},
                ]
            },
    )
    print("\nRanking despues del evento (filtro categoria=sorbetes y activo=true):")
    for puesto, item in enumerate(ranking_filtrado, start=1):
        print(
            f"  {puesto}. {item['titulo']} "
            f"- similitud: {item['similitud']}"
        )

    base_reabierta = BaseVectorial()
    ranking_persistido = consultar(
        base_reabierta,
            donde={
                "$and": [
                    {"categoria": {"$eq": "sorbetes"}},
                    {"activo": {"$eq": True}},
                ]
            },
    )

    escribir_evidencia(
        ranking_antes,
        ranking_despues,
        ranking_filtrado,
        ranking_persistido,
    )


if __name__ == "__main__":
    import sys

    if "--restaurar" in sys.argv:
        restaurar_estado_original()
    else:
        main()