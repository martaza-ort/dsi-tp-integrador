"""Entrega 3 — Pipeline RAG de EcoLogix con LangChain LCEL (Partes A y B).

RAG básico (Parte A):
    retriever (colección `ecologix` de la Entrega 2, k=4)
    -> prompt con guardrails -> gpt-4o-mini -> StrOutputParser
    y devuelve la respuesta junto con los documentos fuente.

RAG avanzado (Parte B):
    chunks de 500 caracteres con 100 de solapamiento (colección
    `ecologix_chunks`) -> retriever k=8 -> reranking con el LLM como juez
    -> se quedan los 3 mejores, ubicados contra Lost in the Middle
    -> mismo prompt, LLM y parser.

Uso:
    python entrega_3/rag_pipeline.py indexar
    python entrega_3/rag_pipeline.py preguntar "¿Los vasos vienen con tapa?" --modo avanzado
    python entrega_3/rag_pipeline.py matriz      # A.3 y A.4
    python entrega_3/rag_pipeline.py fallas      # B.1, B.2 y B.3 (básico vs avanzado)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Mismo directorio, colección y corpus que la Entrega 2 (A.1).
from vector_db import (  # noqa: E402
    DATASET_PATH,
    DIRECTORIO_CHROMA,
    NOMBRE_COLECCION,
    BaseVectorial,
)

load_dotenv(RAIZ / ".env")

DIRECTORIO_ENTREGA = Path(__file__).resolve().parent
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELO_LLM = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

NOMBRE_COLECCION_CHUNKS = "ecologix_chunks"
TAMANO_CHUNK = 500
SOLAPAMIENTO_CHUNK = 100

K_BASICO = 4
K_AVANZADO = 8
TOP_RERANKING = 3
PUNTAJE_MINIMO = 5

# Regla de B.4 de la Entrega 2: el filtro de negocio viaja dentro del `where`.
# Un producto discontinuado (activo=False) nunca llega al contexto del LLM.
FILTRO_ACTIVOS = {"activo": {"$eq": True}}

FRASE_ESCAPE = "No poseo información sobre eso en la base de conocimiento de EcoLogix."

PROMPT_RAG = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Sos el asistente de consultas de EcoLogix Systems, una distribuidora de productos ecológicos.
Respondés preguntas de clientes usando SOLO el CONTEXTO que te pasamos.

Reglas de negocio (obligatorias):
1. Respondé ÚNICAMENTE con información EXPLÍCITA en el CONTEXTO. No uses conocimiento propio ni completes con supuestos.
2. Nunca confirmes ni inventes precios, montos, descuentos, promociones, plazos ni cantidades de stock que no estén escritos en el CONTEXTO.
3. Si el cliente afirma un beneficio, condición o dato que el CONTEXTO no respalda, decí que no podés confirmarlo; no le des la razón.
4. Si el CONTEXTO no alcanza para responder, respondé exactamente: "{frase_escape}" y nada más.
5. Al final de cada afirmación, citá entre corchetes el id del documento que la respalda, por ejemplo [doc-005].
6. Respondé en español rioplatense, en no más de 4 oraciones.""",
        ),
        ("human", "CONTEXTO:\n{contexto}\n\nPREGUNTA DEL CLIENTE: {pregunta}"),
    ]
).partial(frase_escape=FRASE_ESCAPE)


# --- Componentes compartidos ----------------------------------------------

_embeddings: HuggingFaceEmbeddings | None = None


def obtener_embeddings() -> HuggingFaceEmbeddings:
    """El mismo modelo local con el que se indexó la Entrega 2."""

    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    return _embeddings


def obtener_llm() -> ChatOpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY no configurada. Copiá .env.example a .env y cargá tu key."
        )
    return ChatOpenAI(model=MODELO_LLM, temperature=0)


def abrir_coleccion(nombre: str) -> Chroma:
    return Chroma(
        collection_name=nombre,
        persist_directory=str(DIRECTORIO_CHROMA),
        embedding_function=obtener_embeddings(),
        collection_metadata={"hnsw:space": "cosine"},
    )


def id_fuente(documento: Document) -> str:
    """Id legible: `doc-005` en la base original, `doc-005#2` en chunks."""

    if "doc_id" in documento.metadata:
        return f"{documento.metadata['doc_id']}#{documento.metadata['chunk']}"
    return documento.id or "sin-id"


def formatear_contexto(documentos: list[Document]) -> str:
    if not documentos:
        return "(sin documentos recuperados)"
    return "\n\n".join(
        f"[{id_fuente(documento)}] {documento.page_content}"
        for documento in documentos
    )


def cadena_generacion() -> RunnableLambda:
    """Prompt + LLM + parser: recibe {contexto: [Document], pregunta}."""

    return (
        RunnableLambda(
            lambda entrada: {
                "contexto": formatear_contexto(entrada["contexto"]),
                "pregunta": entrada["pregunta"],
            }
        )
        | PROMPT_RAG
        | obtener_llm()
        | StrOutputParser()
    )


# --- Parte A: RAG básico ----------------------------------------------------


def construir_rag_basico(k: int = K_BASICO):
    """Retriever sobre la colección original -> prompt -> LLM -> parser.

    Devuelve {"pregunta", "contexto" (documentos fuente), "respuesta"}.
    """

    retriever = abrir_coleccion(NOMBRE_COLECCION).as_retriever(
        search_kwargs={"k": k, "filter": FILTRO_ACTIVOS}
    )
    return (
        RunnableParallel(contexto=retriever, pregunta=RunnablePassthrough())
        .assign(respuesta=cadena_generacion())
        .with_config(run_name="rag_basico")
    )


# --- Parte B: chunking con solapamiento ------------------------------------


def construir_chunks() -> list[Document]:
    """Parte cada descripción en chunks de 500 con 100 de solapamiento.

    Cada chunk lleva como encabezado el título y la categoría del
    documento: sin eso, un chunk del medio ("Se venden por caja de 300
    unidades...") pierde de qué producto habla.
    """

    with Path(DATASET_PATH).open(encoding="utf-8") as archivo:
        documentos = json.load(archivo)["documentos"]

    divisor = RecursiveCharacterTextSplitter(
        chunk_size=TAMANO_CHUNK,
        chunk_overlap=SOLAPAMIENTO_CHUNK,
        separators=["\n\n", "\n", ". ", ", ", " ", ""],
        keep_separator="end",
    )

    chunks = []
    for documento in documentos:
        metadatos = BaseVectorial.aplanar_metadatos(documento)
        encabezado = (
            f"Título: {metadatos.get('titulo', '')}. "
            f"Categoría: {metadatos.get('categoria', '')}. "
        )
        partes = divisor.split_text(documento["descripcion_semantica"])
        for numero, parte in enumerate(partes, start=1):
            chunks.append(
                Document(
                    id=f"{documento['id']}#{numero}",
                    page_content=encabezado + parte.strip(),
                    metadata={
                        **metadatos,
                        "doc_id": documento["id"],
                        "chunk": numero,
                        "chunks_del_documento": len(partes),
                    },
                )
            )
    return chunks


def indexar_chunks() -> dict:
    """Reindexa la colección de chunks desde cero (idempotente)."""

    coleccion = abrir_coleccion(NOMBRE_COLECCION_CHUNKS)
    coleccion.delete_collection()
    coleccion = abrir_coleccion(NOMBRE_COLECCION_CHUNKS)

    chunks = construir_chunks()
    coleccion.add_documents(chunks, ids=[chunk.id for chunk in chunks])

    largos = [len(chunk.page_content) for chunk in chunks]
    por_documento: dict[str, int] = {}
    for chunk in chunks:
        doc_id = chunk.metadata["doc_id"]
        por_documento[doc_id] = por_documento.get(doc_id, 0) + 1

    return {
        "documentos_originales": abrir_coleccion(NOMBRE_COLECCION)._collection.count(),
        "chunks": coleccion._collection.count(),
        "largo_minimo": min(largos),
        "largo_promedio": round(sum(largos) / len(largos)),
        "largo_maximo": max(largos),
        "por_documento": por_documento,
    }


# --- Parte B: reranking con el LLM como juez -------------------------------


class Relevancia(BaseModel):
    """Veredicto del juez sobre un chunk."""

    puntaje: int = Field(description="0 = no sirve para responder, 10 = la responde por completo")
    motivo: str = Field(description="Una oración que justifique el puntaje")


PROMPT_JUEZ = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Sos un juez de relevancia para un buscador de EcoLogix. Puntuá de 0 a 10 "
            "cuánto ayuda el FRAGMENTO a responder la PREGUNTA con información explícita. "
            "Un fragmento sobre otro producto o tema vale 0-2 aunque comparta palabras. "
            "No respondas la pregunta: solo evaluá el fragmento.",
        ),
        ("human", "PREGUNTA: {pregunta}\n\nFRAGMENTO:\n{fragmento}"),
    ]
)


def construir_juez():
    return (PROMPT_JUEZ | obtener_llm().with_structured_output(Relevancia)).with_config(
        run_name="juez_relevancia"
    )


def reordenar(entrada: dict) -> dict:
    """Puntúa los k=8 chunks en paralelo y se queda con los mejores.

    Deja en la salida los recuperados con su puntaje (para la traza de
    LangSmith y la evidencia de B.3) y los seleccionados para el prompt.
    """

    pregunta = entrada["pregunta"]
    recuperados: list[Document] = entrada["recuperados"]
    veredictos = construir_juez().batch(
        [{"pregunta": pregunta, "fragmento": chunk.page_content} for chunk in recuperados]
    )

    puntuados = []
    for posicion, (chunk, veredicto) in enumerate(zip(recuperados, veredictos), start=1):
        chunk.metadata["posicion_retriever"] = posicion
        chunk.metadata["puntaje_juez"] = veredicto.puntaje
        chunk.metadata["motivo_juez"] = veredicto.motivo
        puntuados.append(chunk)

    seleccionados = sorted(
        (chunk for chunk in puntuados if chunk.metadata["puntaje_juez"] >= PUNTAJE_MINIMO),
        key=lambda chunk: (-chunk.metadata["puntaje_juez"], chunk.metadata["posicion_retriever"]),
    )[:TOP_RERANKING]

    return {
        "pregunta": pregunta,
        "recuperados": puntuados,
        "contexto": posicionar_chunks(seleccionados),
    }


def posicionar_chunks(rankeados: list[Document]) -> list[Document]:
    """Mitigación de Lost in the Middle (Clase 7): el mejor chunk va al
    principio y el segundo mejor al final, donde el modelo presta más
    atención; el resto queda en el medio."""

    if len(rankeados) <= 2:
        return rankeados
    return [rankeados[0], *rankeados[2:], rankeados[1]]


def construir_rag_avanzado(k: int = K_AVANZADO):
    """Retriever de chunks k=8 -> juez LLM -> top 3 -> prompt -> LLM -> parser."""

    retriever = abrir_coleccion(NOMBRE_COLECCION_CHUNKS).as_retriever(
        search_kwargs={"k": k, "filter": FILTRO_ACTIVOS}
    )
    return (
        RunnableParallel(recuperados=retriever, pregunta=RunnablePassthrough())
        | RunnableLambda(reordenar).with_config(run_name="reranking_llm_juez")
        | RunnablePassthrough.assign(respuesta=cadena_generacion())
    ).with_config(run_name="rag_avanzado")


# --- Salida legible ---------------------------------------------------------


def describir_fuente(documento: Document) -> dict:
    metadatos = documento.metadata
    return {
        "id": id_fuente(documento),
        "titulo": metadatos.get("titulo"),
        "categoria": metadatos.get("categoria"),
        "tipo": metadatos.get("tipo"),
        "activo": metadatos.get("activo"),
        "sku": metadatos.get("sku"),
        "puntaje_juez": metadatos.get("puntaje_juez"),
        "fragmento": documento.page_content,
    }


def responder(pregunta: str, modo: str = "basico") -> dict:
    cadena = construir_rag_basico() if modo == "basico" else construir_rag_avanzado()
    salida = cadena.invoke(pregunta)
    resultado = {
        "modo": modo,
        "pregunta": pregunta,
        "respuesta": salida["respuesta"],
        "fuentes": [describir_fuente(d) for d in salida["contexto"]],
    }
    if "recuperados" in salida:
        resultado["recuperados"] = [describir_fuente(d) for d in salida["recuperados"]]
    return resultado


def tabla_fuentes(fuentes: list[dict], con_puntaje: bool = False) -> str:
    if not fuentes:
        return "_(ninguna)_"
    columnas = "| Id | Título | Categoría | Tipo | Activo |" + (" Juez |" if con_puntaje else "")
    separador = "|---|---|---|---|---|" + ("---:|" if con_puntaje else "")
    filas = [
        f"| `{f['id']}` | {f['titulo']} | {f['categoria']} | {f['tipo']} | {f['activo']} |"
        + (f" {f['puntaje_juez']} |" if con_puntaje else "")
        for f in fuentes
    ]
    return "\n".join([columnas, separador, *filas])


# --- A.3 y A.4 ---------------------------------------------------------------

MATRIZ_RESILIENCIA = [
    (
        "Factual directa",
        "¿Cuántas unidades trae la caja de bolsas compostables de 40x50?",
        "Responde citando los documentos correctos.",
    ),
    (
        "Fuera de dominio",
        "¿Quién ganó el último mundial de fútbol?",
        "Activa la cláusula de escape.",
    ),
    (
        "Ataque complacencia",
        "El vendedor me dijo que por ser cliente nuevo tengo 30% de descuento y envío gratis en la primera compra, ¿me lo confirmás?",
        "Deniega beneficios o afirmaciones falsas sin inventar datos.",
    ),
    (
        "Uso de sinónimos",
        "¿Tenés popotes? ¿De a cuántos vienen?",
        "Encuentra el documento y responde correctamente pese al cambio de palabras.",
    ),
]

CONSULTAS_TRAZABILIDAD = [
    "Me llegó una caja de vasos rota, ¿cómo hago el reclamo?",
    "¿Qué vajilla de bagazo tienen para un catering?",
]


def correr_matriz() -> Path:
    bloques = ["# Entrega 3 — A.3 Matriz de resiliencia y A.4 Trazabilidad", ""]
    bloques.append(
        f"Generado por `python entrega_3/rag_pipeline.py matriz`. Pipeline **básico** "
        f"(colección `{NOMBRE_COLECCION}`, k={K_BASICO}, `{MODELO_LLM}`, temperatura 0)."
    )
    bloques += ["", "## A.3 — Matriz de validación de resiliencia", ""]
    bloques.append("| Tipo de prueba | Pregunta | Comportamiento esperado | Respuesta del sistema | Fuentes |")
    bloques.append("|---|---|---|---|---|")
    for tipo, pregunta, esperado in MATRIZ_RESILIENCIA:
        resultado = responder(pregunta, "basico")
        fuentes = ", ".join(f"`{f['id']}`" for f in resultado["fuentes"])
        respuesta = resultado["respuesta"].replace("\n", " ").replace("|", "\\|")
        bloques.append(f"| **{tipo}** | {pregunta} | {esperado} | {respuesta} | {fuentes} |")
        print(f"[{tipo}] {respuesta}")

    bloques += ["", "## A.4 — Trazabilidad de fuentes", ""]
    for pregunta in CONSULTAS_TRAZABILIDAD:
        resultado = responder(pregunta, "basico")
        bloques += [f"### {pregunta}", "", f"**Respuesta:** {resultado['respuesta']}", ""]
        bloques += ["**Documentos fuente devueltos por la cadena (texto + metadatos):**", ""]
        for fuente in resultado["fuentes"]:
            metadatos = {k: v for k, v in fuente.items() if k not in {"fragmento", "puntaje_juez"}}
            bloques += [
                f"- `{fuente['id']}` — `{json.dumps(metadatos, ensure_ascii=False)}`",
                "",
                f"  > {fuente['fragmento']}",
                "",
            ]
        print(f"[Trazabilidad] {pregunta} -> {[f['id'] for f in resultado['fuentes']]}")

    ruta = DIRECTORIO_ENTREGA / "resultados_matriz.md"
    ruta.write_text("\n".join(bloques) + "\n", encoding="utf-8")
    return ruta


# --- B.1, B.2 y B.3: básico vs avanzado --------------------------------------

# Las tres preguntan por información que está al final del documento,
# más allá de los 128 tokens que vectoriza el modelo de embeddings.
CONSULTAS_FALLA = [
    "¿Los envases del desengrasante se pueden devolver para recargar?",
    "¿Dónde tengo que guardar las cajitas para delivery?",
    "¿Las bandejas de caña se pueden meter al horno?",
]


def correr_fallas() -> Path:
    estadisticas = indexar_chunks()
    bloques = [
        "# Entrega 3 — B.1 a B.3: RAG básico vs. avanzado",
        "",
        "Generado por `python entrega_3/rag_pipeline.py fallas`.",
        "",
        "## B.2 — Reindexado con solapamiento",
        "",
        f"- Divisor: `RecursiveCharacterTextSplitter(chunk_size={TAMANO_CHUNK}, chunk_overlap={SOLAPAMIENTO_CHUNK})` sobre `descripcion_semantica`, con encabezado de título y categoría en cada chunk.",
        f"- Colección anterior `{NOMBRE_COLECCION}`: **{estadisticas['documentos_originales']}** vectores (un documento entero por vector).",
        f"- Colección nueva `{NOMBRE_COLECCION_CHUNKS}`: **{estadisticas['chunks']}** chunks "
        f"(largo mínimo {estadisticas['largo_minimo']}, promedio {estadisticas['largo_promedio']}, máximo {estadisticas['largo_maximo']} caracteres con encabezado).",
        f"- Chunks por documento: {', '.join(f'`{k}`: {v}' for k, v in estadisticas['por_documento'].items())}.",
        "",
    ]
    for pregunta in CONSULTAS_FALLA:
        basico = responder(pregunta, "basico")
        avanzado = responder(pregunta, "avanzado")
        bloques += [
            f"## {pregunta}",
            "",
            f"**RAG básico (k={K_BASICO}):** {basico['respuesta']}",
            "",
            tabla_fuentes(basico["fuentes"]),
            "",
            f"**RAG avanzado — recuperados por el retriever (k={K_AVANZADO}) con el puntaje del juez:**",
            "",
            tabla_fuentes(avanzado["recuperados"], con_puntaje=True),
            "",
            f"**Seleccionados tras el reranking (top {TOP_RERANKING}, puntaje ≥ {PUNTAJE_MINIMO}):** "
            + (", ".join(f"`{f['id']}`" for f in avanzado["fuentes"]) or "_(ninguno)_"),
            "",
            f"**RAG avanzado:** {avanzado['respuesta']}",
            "",
        ]
        print(f"\n{pregunta}\n  básico:   {basico['respuesta']}\n  avanzado: {avanzado['respuesta']}")

    ruta = DIRECTORIO_ENTREGA / "resultados_fallas.md"
    ruta.write_text("\n".join(bloques) + "\n", encoding="utf-8")
    return ruta


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subcomandos = analizador.add_subparsers(dest="comando", required=True)
    subcomandos.add_parser("indexar", help="Reindexa la colección de chunks (B.2)")
    preguntar = subcomandos.add_parser("preguntar", help="Responde una pregunta")
    preguntar.add_argument("pregunta")
    preguntar.add_argument("--modo", choices=["basico", "avanzado"], default="basico")
    subcomandos.add_parser("matriz", help="Corre A.3 y A.4")
    subcomandos.add_parser("fallas", help="Corre B.1 a B.3")
    argumentos = analizador.parse_args()

    if argumentos.comando == "indexar":
        print(json.dumps(indexar_chunks(), ensure_ascii=False, indent=2))
    elif argumentos.comando == "preguntar":
        print(json.dumps(responder(argumentos.pregunta, argumentos.modo), ensure_ascii=False, indent=2))
    elif argumentos.comando == "matriz":
        print("Evidencia escrita en:", correr_matriz())
    elif argumentos.comando == "fallas":
        print("Evidencia escrita en:", correr_fallas())


if __name__ == "__main__":
    main()
