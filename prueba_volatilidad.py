"""Prueba destructiva de volatilidad — Entrega 2, A.5.

Demuestra con evidencia real (no narrativa) que la persistencia del
índice FAISS es la diferencia entre un índice efímero y uno reutilizable:

1. Sin `write_index()`: el índice vive solo en memoria. Si el proceso
   termina (se "reinicia el entorno"), no hay nada en disco para
   recargar — hay que regenerar embeddings desde cero (pagar de nuevo).
2. Con `write_index()`: el índice se persiste a disco. Un proceso
   nuevo (simulado acá borrando los objetos en memoria) lo recarga
   con `read_index()` sin volver a llamar `generar_embeddings()`.

No modifica `construir_indice_faiss.py` ni `similitud_coseno.py`:
solo los importa, para no pisar el trabajo de nadie en esos archivos.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

import faiss

from construir_indice_faiss import construir_indice
from similitud_coseno import (
    cargar_documentos,
    preparar_texto,
    generar_embeddings,
)


ROOT = Path(__file__).resolve().parent
RUTA_EVIDENCIA = ROOT / "docs-resultados" / "resultados_a5_volatilidad.md"
RUTA_PRUEBA = ROOT / "indice_faiss" / "prueba_a5.index"

def escenario_sin_persistencia(directorio_temporal: Path) -> dict:
    """Construye el índice en memoria y NUNCA lo persiste."""

    documentos = cargar_documentos()
    textos = [preparar_texto(doc) for doc in documentos]

    embeddings = generar_embeddings(textos)
    indice = construir_indice(embeddings)

    vectores_en_memoria = indice.ntotal

    # "Reiniciar el entorno": el proceso termina, el objeto `indice`
    # desaparece de la RAM. Nunca se llamó a write_index(), así que
    # en el path del índice no hay nada.
    ruta_index_temporal = directorio_temporal / "sin_persistencia.index"

    del indice

    existe_en_disco = ruta_index_temporal.exists()

    error_al_recargar = None
    try:
        faiss.read_index(str(ruta_index_temporal))
    except RuntimeError as excepcion:
        error_al_recargar = str(excepcion)

    return {
        "vectores_en_memoria": vectores_en_memoria,
        "existe_en_disco": existe_en_disco,
        "error_al_recargar": error_al_recargar,
        "hay_que_regenerar": error_al_recargar is not None,
    }


def escenario_con_persistencia(directorio_temporal: Path) -> dict:
    """Construye el índice, lo persiste con write_index() y simula
    un reinicio del proceso recargándolo con read_index()."""

    documentos = cargar_documentos()
    textos = [preparar_texto(doc) for doc in documentos]

    embeddings = generar_embeddings(textos)
    indice = construir_indice(embeddings)

    ruta_index_temporal = directorio_temporal / "con_persistencia.index"
    faiss.write_index(indice, str(ruta_index_temporal))

    vectores_antes_de_reiniciar = indice.ntotal
    dimension_antes_de_reiniciar = indice.d

    # "Reiniciar el entorno": se borran los objetos en memoria.
    # A partir de acá, nada de lo que sigue vuelve a llamar a
    # generar_embeddings(): todo sale del archivo en disco.
    del indice
    del embeddings
    del textos

    indice_recargado = faiss.read_index(str(ruta_index_temporal))

    return {
        "vectores_antes_de_reiniciar": vectores_antes_de_reiniciar,
        "dimension_antes_de_reiniciar": dimension_antes_de_reiniciar,
        "vectores_recargados": indice_recargado.ntotal,
        "dimension_recargada": indice_recargado.d,
        "coincide": (
            indice_recargado.ntotal == vectores_antes_de_reiniciar
            and indice_recargado.d == dimension_antes_de_reiniciar
        ),
    }

def escribir_indice_persistido() -> None:
    """Construye y guarda el índice. Este proceso termina después de escribirlo."""

    documentos = cargar_documentos()
    textos = [preparar_texto(doc) for doc in documentos]

    embeddings = generar_embeddings(textos)
    indice = construir_indice(embeddings)

    RUTA_PRUEBA.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(indice, str(RUTA_PRUEBA))

    print("Índice persistido correctamente.")
    print("Ruta:", RUTA_PRUEBA)
    print("Vectores:", indice.ntotal)
    print("Dimensión:", indice.d)


def leer_indice_persistido() -> None:
    """Carga el índice en un proceso nuevo sin regenerar embeddings."""

    if not RUTA_PRUEBA.exists():
        raise FileNotFoundError(
            f"No existe el índice persistido: {RUTA_PRUEBA}"
        )

    # En este modo no se llama a cargar_documentos(),
    # preparar_texto() ni generar_embeddings().
    indice = faiss.read_index(str(RUTA_PRUEBA))

    print("Índice recuperado desde disco.")
    print("Ruta:", RUTA_PRUEBA)
    print("Vectores recuperados:", indice.ntotal)
    print("Dimensión recuperada:", indice.d)
    print("No se regeneraron embeddings.")


def escribir_evidencia(resultado_sin: dict, resultado_con: dict) -> None:
    paso_sin = (
        "Sí"
        if resultado_sin["hay_que_regenerar"]
        and not resultado_sin["existe_en_disco"]
        else "No"
    )
    paso_con = "Sí" if resultado_con["coincide"] else "No"

    contenido = f"""# Prueba destructiva de volatilidad — EcoLogix (Entrega 2, A.5)

Evidencia real de que la persistencia del índice FAISS no es una
afirmación: se construyó el mismo corpus dos veces, una sin
`write_index()` y otra con, simulando en ambos casos el reinicio del
proceso (se borran los objetos de Python en memoria y se intenta
recargar desde el path en disco).

Reproducible con `python prueba_volatilidad.py`.

## Escenario 1 — Sin `write_index()`

| Medición | Resultado |
|---|---|
| Vectores construidos en memoria | {resultado_sin['vectores_en_memoria']} |
| ¿Existe el archivo en disco tras "reiniciar"? | {resultado_sin['existe_en_disco']} |
| Error al intentar `faiss.read_index()` | `{resultado_sin['error_al_recargar']}` |
| ¿Hay que regenerar embeddings (pagar de nuevo)? | **{'Sí' if resultado_sin['hay_que_regenerar'] else 'No'}** |

**¿Pasó la prueba (se perdió el índice)?** {paso_sin}

Sin `write_index()`, el índice vive únicamente en la RAM del proceso
de Python. Al terminar el proceso ("reiniciar el entorno"), el objeto
`faiss.Index` desaparece con él. No queda ningún archivo para
recargar: `faiss.read_index()` sobre ese path falla, y la única forma
de volver a tener el índice es correr `generar_embeddings()` de nuevo
sobre todo el corpus — es decir, pagar tokens/cómputo otra vez.

## Escenario 2 — Con `write_index()`

| Medición | Antes de "reiniciar" | Después de recargar desde disco |
|---|---|---|
| Vectores | {resultado_con['vectores_antes_de_reiniciar']} | {resultado_con['vectores_recargados']} |
| Dimensión | {resultado_con['dimension_antes_de_reiniciar']} | {resultado_con['dimension_recargada']} |

**¿Coincide el índice recargado con el original?** {resultado_con['coincide']}

**¿Pasó la prueba (el índice sobrevivió al "reinicio")?** {paso_con}

Con `write_index()`, el índice queda serializado en disco. Tras
borrar los objetos en memoria (simulando que el proceso terminó y
arrancó de nuevo), `faiss.read_index()` reconstruye el mismo índice
— mismo `ntotal`, misma dimensión — sin volver a llamar
`generar_embeddings()` en ningún momento de este segundo escenario.
La diferencia entre los dos escenarios es, literalmente, esa única
línea de código.

## Reflexión

**¿Qué pasa en producción si el servidor se reinicia?** Sin
persistencia en disco, cada reinicio (deploy, crash, escalado)
obliga a reconstruir el índice completo desde cero, con el costo de
cómputo/tokens que eso implica y un período sin búsqueda disponible
mientras se regenera. Con `write_index()`/`read_index()` sobre un
volumen persistente, el servidor vuelve a estar operativo apenas
termina de leer el archivo.

**¿Y si hay dos servidores?** FAISS no tiene control de concurrencia
ni mecanismo de sincronización propio: si cada instancia construye
su índice por separado, pueden terminar desincronizadas (una ve un
producto que la otra no, por ejemplo tras un evento como el de B.3).
Para dos servidores hace falta un paso adicional que FAISS no
resuelve solo: compartir el mismo archivo de índice (disco
compartido, objeto en un bucket, o reconstrucción centralizada que
los demás solo leen) — exactamente el problema que `PersistentClient`
de ChromaDB sí resuelve de fábrica (ver B.2).
"""

    with RUTA_EVIDENCIA.open("w", encoding="utf-8") as archivo:
        archivo.write(contenido)

    print("Evidencia escrita en:", RUTA_EVIDENCIA)


def main() -> None:
    directorio_temporal = Path(tempfile.mkdtemp(prefix="prueba_volatilidad_"))

    try:
        print("Escenario 1 — construyendo SIN write_index()...")
        resultado_sin = escenario_sin_persistencia(directorio_temporal)
        print(
            "  Vectores en memoria:",
            resultado_sin["vectores_en_memoria"],
        )
        print(
            "  Existe en disco tras 'reiniciar':",
            resultado_sin["existe_en_disco"],
        )
        print(
            "  Hay que regenerar:",
            resultado_sin["hay_que_regenerar"],
        )

        print("\nEscenario 2 — construyendo CON write_index()...")
        resultado_con = escenario_con_persistencia(directorio_temporal)
        print(
            "  Vectores antes/recargados:",
            resultado_con["vectores_antes_de_reiniciar"],
            "/",
            resultado_con["vectores_recargados"],
        )
        print("  Coincide tras recargar:", resultado_con["coincide"])

        escribir_evidencia(resultado_sin, resultado_con)
    finally:
        shutil.rmtree(directorio_temporal, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prueba de persistencia del índice FAISS"
    )
    parser.add_argument(
        "--modo",
        choices=["completa", "escribir", "leer"],
        default="completa",
        help="Modo de ejecución de la prueba",
    )
    args = parser.parse_args()

    if args.modo == "escribir":
        escribir_indice_persistido()
    elif args.modo == "leer":
        leer_indice_persistido()
    else:
        main()
