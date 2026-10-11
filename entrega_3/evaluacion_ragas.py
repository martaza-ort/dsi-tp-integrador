"""Entrega 3 — Parte C: evaluación con RAGAS del RAG básico vs. avanzado.

Carga el golden dataset (C.1, golden_dataset.json), corre los dos pipelines de
`rag_pipeline.py` sobre las mismas 10 preguntas y mide con RAGAS
Faithfulness, Answer Relevancy, Context Precision y Context Recall
(C.2 y C.3). Escribe `entrega_3/resultados_ragas.md` y un CSV por
pipeline con el detalle por pregunta.

Uso:
    python entrega_3/evaluacion_ragas.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from langchain_openai import ChatOpenAI
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag_pipeline import (  # noqa: E402
    DIRECTORIO_ENTREGA,
    FRASE_ESCAPE,
    MODELO_LLM,
    construir_rag_avanzado,
    construir_rag_basico,
    indexar_chunks,
    obtener_embeddings,
    obtener_llm,
)

# --- C.1 Golden dataset -------------------------------------------------------
# Vive en golden_dataset.json porque se reutiliza en las Entregas 4 y 5.
# Las respuestas esperadas se escribieron a mano a partir de
# base_conocimiento_limpia.json: 3 simples, 3 complejas, 2 de escape y
# 2 con lenguaje informal.

RUTA_GOLDEN_DATASET = DIRECTORIO_ENTREGA / "golden_dataset.json"


def cargar_golden_dataset() -> list[dict]:
    datos = json.loads(RUTA_GOLDEN_DATASET.read_text(encoding="utf-8"))
    if datos["frase_escape"] != FRASE_ESCAPE:
        raise SystemExit(
            "La frase de escape del golden dataset no coincide con la del prompt."
        )
    return datos["preguntas"]


GOLDEN_DATASET = cargar_golden_dataset()

METRICAS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "llm_context_precision_with_reference": "Context Precision",
    "context_recall": "Context Recall",
}


def correr_pipeline(nombre: str, cadena) -> list[dict]:
    filas = []
    for caso in GOLDEN_DATASET:
        salida = cadena.invoke(caso["pregunta"])
        filas.append(
            {
                "user_input": caso["pregunta"],
                "response": salida["respuesta"],
                "retrieved_contexts": [d.page_content for d in salida["contexto"]]
                or ["(sin documentos recuperados)"],
                "reference": caso["referencia"],
            }
        )
        print(f"[{nombre}] {caso['pregunta']}\n    -> {salida['respuesta']}")
    return filas


def evaluar(filas: list[dict]):
    juez = LangchainLLMWrapper(ChatOpenAI(model=MODELO_LLM, temperature=0))
    embeddings = LangchainEmbeddingsWrapper(obtener_embeddings())
    return evaluate(
        dataset=EvaluationDataset.from_list(filas),
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
        ],
        llm=juez,
        embeddings=embeddings,
        show_progress=False,
    ).to_pandas()


def promedio(serie) -> tuple[float, int]:
    """Promedio ignorando NaN (RAGAS da NaN si no hay afirmaciones que medir)."""

    valores = [float(v) for v in serie if v is not None and not math.isnan(float(v))]
    if not valores:
        return float("nan"), 0
    return sum(valores) / len(valores), len(serie) - len(valores)


def formato(valor: float) -> str:
    return "—" if math.isnan(valor) else f"{valor:.3f}"


def escribir_reporte(resultados: dict) -> Path:
    basico, avanzado = resultados["basico"], resultados["avanzado"]
    filas_resumen = []
    for columna, nombre in METRICAS.items():
        media_b, nan_b = promedio(basico[columna])
        media_a, nan_a = promedio(avanzado[columna])
        delta = media_a - media_b
        notas = f"{nan_b} / {nan_a}" if nan_b or nan_a else ""
        filas_resumen.append(
            f"| {nombre} | {formato(media_b)} | {formato(media_a)} | "
            f"{'+' if delta >= 0 else ''}{formato(delta)} | {notas} |"
        )

    bloques = [
        "# Entrega 3 — Parte C: evaluación RAGAS",
        "",
        "Generado por `python entrega_3/evaluacion_ragas.py`. Juez de RAGAS: "
        f"`{MODELO_LLM}` (temperatura 0); embeddings de Answer Relevancy: el mismo "
        "modelo local de la base vectorial.",
        "",
        "## C.2 y C.3 — Promedios sobre las 10 preguntas",
        "",
        "| Métrica | RAG básico | RAG avanzado | Delta | NaN (básico / avanzado) |",
        "|---|---:|---:|---:|---|",
        *filas_resumen,
        "",
        "## Detalle por pregunta",
        "",
    ]

    for nombre_modo, tabla in (("RAG básico", basico), ("RAG avanzado", avanzado)):
        bloques += [
            f"### {nombre_modo}",
            "",
            "| # | Categoría | Pregunta | Respuesta | Faithfulness | Answer Rel. | Ctx Precision | Ctx Recall |",
            "|---:|---|---|---|---:|---:|---:|---:|",
        ]
        for numero, (caso, (_, fila)) in enumerate(zip(GOLDEN_DATASET, tabla.iterrows()), start=1):
            respuesta = str(fila["response"]).replace("\n", " ").replace("|", "\\|")
            bloques.append(
                f"| {numero} | {caso['categoria']} | {caso['pregunta']} | {respuesta} | "
                + " | ".join(formato(float(fila[c])) for c in METRICAS)
                + " |"
            )
        bloques.append("")

    ruta = DIRECTORIO_ENTREGA / "resultados_ragas.md"
    ruta.write_text("\n".join(bloques) + "\n", encoding="utf-8")
    return ruta


def main() -> None:
    obtener_llm()  # falla temprano si no hay OPENAI_API_KEY
    indexar_chunks()

    resultados = {}
    for nombre, cadena in (
        ("basico", construir_rag_basico()),
        ("avanzado", construir_rag_avanzado()),
    ):
        filas = correr_pipeline(nombre, cadena)
        tabla = evaluar(filas)
        tabla.to_csv(DIRECTORIO_ENTREGA / f"ragas_{nombre}.csv", index=False, encoding="utf-8")
        resultados[nombre] = tabla

    print("Reporte escrito en:", escribir_reporte(resultados))


if __name__ == "__main__":
    main()
