from __future__ import annotations

from entrega_3.indexar_chunks import NOMBRE_COLECCION_CHUNKS
from entrega_3.rag_pipeline import crear_cadena_rag
from vector_db import NOMBRE_COLECCION


CONSULTA_B1 = (
    "Quiero pedir 20 cajas de vasos de bagazo y un bulto de sorbetes "
    "para el jueves. ¿Qué habría que validar antes de confirmar el pedido "
    "y qué determina si pueden entregarlo en mi domicilio?"
)
MODELO_COMPARACION = "gemini-3.5-flash-lite"
COLECCIONES_COMPARACION = (
    ("B.1 — RAG básico", NOMBRE_COLECCION),
    ("B.2 — RAG con chunks 500/100", NOMBRE_COLECCION_CHUNKS),
)


def main() -> None:
    print(f"Consulta: {CONSULTA_B1}")
    print(f"Modelo compartido: {MODELO_COMPARACION}")

    for etiqueta, nombre_coleccion in COLECCIONES_COMPARACION:
        print(
            f"\n=== {etiqueta} "
            f"(colección {nombre_coleccion}, k=3) ==="
        )
        resultado = crear_cadena_rag(
            cantidad=3,
            modelo=MODELO_COMPARACION,
            nombre_coleccion=nombre_coleccion,
        ).invoke(CONSULTA_B1)

        print("\nRespuesta:")
        print(resultado["answer"])
        print("\nFuentes recuperadas:")
        for posicion, documento in enumerate(
            resultado["source_documents"],
            start=1,
        ):
            titulo = documento.metadata.get(
                "titulo_documento_origen",
                documento.metadata.get("titulo", "Sin título"),
            )
            indice_chunk = documento.metadata.get("indice_chunk")
            referencia_chunk = (
                f", chunk {indice_chunk}"
                if indice_chunk is not None
                else ""
            )
            print(f"{posicion}. {titulo}{referencia_chunk}")
            print(documento.page_content)


if __name__ == "__main__":
    main()
