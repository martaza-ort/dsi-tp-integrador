from __future__ import annotations

from pathlib import Path

from pipeline_vectorial import PipelineVectorial


ROOT = Path(__file__).resolve().parent
RUTA_RESULTADOS = ROOT / "resultados_a4.md"

CONSULTAS_PRUEBA = [
    (
        "CONSULTA_STOCK",
        "Tenés vasos biodegradables para una cafetería",
    ),
    (
        "CREAR_PEDIDO",
        "Quiero encargar dos cajas de bolsas compostables para mi súper",
    ),
    (
        "RECLAMO_ENTREGA",
        "Se rompieron varios envases de cartón en la entrega, quiero reclamar",
    ),
]

CANTIDAD = 3


def generar_resultados(pipeline: PipelineVectorial) -> list[dict]:
    """Ejecuta las 3 consultas de prueba y devuelve las tablas."""

    bloques = []

    for intencion, consulta in CONSULTAS_PRUEBA:
        resultados = pipeline.buscar_por_intencion(
            consulta=consulta,
            intencion=intencion,
            cantidad=CANTIDAD,
        )

        bloques.append(
            {
                "intencion": intencion,
                "consulta": consulta,
                "resultados": resultados,
            }
        )

    return bloques


def escribir_reporte(
    bloques: list[dict],
    n_vectores: int,
    dimension: int,
) -> None:
    """Escribe el log de las consultas de prueba en un archivo."""

    secciones = []

    for bloque in bloques:
        filas = [
            "| Puesto | Id | Documento | Score | Distancia |",
            "|--------|----|-----------|-------|-----------|",
        ]

        for puesto, item in enumerate(bloque["resultados"], start=1):
            distancia = round(1 - item["similitud"], 4)

            filas.append(
                f"| {puesto} | {item['id']} | "
                f"{item['titulo']} | "
                f"{item['similitud']} | {distancia} |"
            )

        secciones.append(
            f"### {bloque['intencion']}\n\n"
            f"> {bloque['consulta']}\n\n"
            + "\n".join(filas)
        )

    contenido = f"""# Búsqueda top-K del índice FAISS — A.4

Log de las 3 consultas de prueba sobre el índice persistido.

- Modelo de embeddings: `paraphrase-multilingual-MiniLM-L12-v2` (local).
- Índice: `indice_faiss/ecologix.index`, IndexFlatIP sobre vectores
  L2-normalizados (producto interno = similitud coseno).
- Forma: {n_vectores} vectores, dimensión {dimension}. La cantidad de
  vectores surge de ejecutar `python construir_indice_faiss.py`; el
  `score` es la similitud devuelta por `pipeline_vectorial.py` con
  umbral 0,25 y la `distancia` se reporta como `1 - score`
  (distancia coseno).

## Consultas

{chr(10).join(chr(10).join([seccion]) for seccion in secciones)}

## Reactivación

```powershell
venv\\Scripts\\python.exe construir_indice_faiss.py
venv\\Scripts\\python.exe reporte_a4.py
```
"""

    with RUTA_RESULTADOS.open("w", encoding="utf-8") as archivo:
        archivo.write(contenido)

    print("Log escrito en:", RUTA_RESULTADOS)


def main() -> None:
    print("Cargando el pipeline vectorial...")

    pipeline = PipelineVectorial()

    print(
        "Índice FAISS:",
        pipeline.indice.ntotal,
        "vectores, dimensión",
        pipeline.indice.d,
    )
    print()

    bloques = generar_resultados(pipeline)

    for bloque in bloques:
        print(f"### {bloque['intencion']}")
        print(f"> {bloque['consulta']}")

        for item in bloque["resultados"]:
            distancia = round(1 - item["similitud"], 4)
            print(
                f"  {item['id']}  {item['titulo']:<48} "
                f"score={item['similitud']}  distancia={distancia}"
            )

        print()

    escribir_reporte(
        bloques,
        pipeline.indice.ntotal,
        pipeline.indice.d,
    )


if __name__ == "__main__":
    main()