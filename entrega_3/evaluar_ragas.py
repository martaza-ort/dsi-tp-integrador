from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from dotenv import load_dotenv

from entrega_3.rag_pipeline import (
    RAIZ_PROYECTO,
    EmbeddingsEcoLogix,
    _crear_modelo_chat,
    crear_cadena_rag,
)
from vector_db import NOMBRE_COLECCION


DIRECTORIO_ENTREGA = Path(__file__).resolve().parent
RUTA_GOLDEN_DATASET = DIRECTORIO_ENTREGA / "golden_dataset.json"
RUTA_DATOS_BASELINE = (
    RAIZ_PROYECTO / "docs-resultados" / "datos_ragas_baseline.json"
)
RUTA_RESULTADOS_BASELINE = (
    RAIZ_PROYECTO / "docs-resultados" / "resultados_ragas_baseline.json"
)
CANTIDAD_DOCUMENTOS = 3
NOMBRES_METRICAS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)
MODULO_VERTEX_LEGACY = "langchain_community.chat_models.vertexai"


def cargar_golden_dataset() -> dict[str, Any]:
    with RUTA_GOLDEN_DATASET.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def _validar_casos(casos: list[dict[str, Any]]) -> None:
    if not casos:
        raise ValueError("El golden dataset no contiene casos.")

    ids = [caso.get("id") for caso in casos]
    if any(not identificador for identificador in ids):
        raise ValueError("Todos los casos del golden dataset deben tener id.")
    if len(set(ids)) != len(ids):
        raise ValueError("El golden dataset contiene ids duplicados.")

    for caso in casos:
        for campo in ("tipo", "pregunta", "ground_truth"):
            if not isinstance(caso.get(campo), str) or not caso[campo].strip():
                raise ValueError(
                    f"El caso {caso['id']} debe tener el campo "
                    f"{campo!r} como texto no vacío."
                )


def crear_registro_baseline(
    caso: dict[str, Any],
    salida: dict[str, Any],
) -> dict[str, Any]:
    respuesta = salida.get("answer")
    documentos = salida.get("source_documents")
    if not isinstance(respuesta, str) or not respuesta.strip():
        raise ValueError(
            f"El pipeline no devolvió una respuesta válida para {caso['id']}."
        )
    if not isinstance(documentos, list):
        raise TypeError(
            f"El pipeline no devolvió una lista de fuentes para {caso['id']}."
        )

    contextos = []
    for documento in documentos:
        texto = getattr(documento, "page_content", None)
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError(
                f"El pipeline devolvió un contexto vacío o inválido "
                f"para {caso['id']}."
            )
        contextos.append(texto)

    return {
        "id": caso["id"],
        "tipo": caso["tipo"],
        "pregunta": caso["pregunta"],
        "ground_truth": caso["ground_truth"],
        "user_input": caso["pregunta"],
        "reference": caso["ground_truth"],
        "response": respuesta,
        "retrieved_contexts": contextos,
    }


def preparar_filas_ragas(
    registros: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Selecciona el esquema requerido por las métricas RAGAS de C.2."""

    return [
        {
            "user_input": registro["user_input"],
            "response": registro["response"],
            "retrieved_contexts": registro["retrieved_contexts"],
            "reference": registro["reference"],
        }
        for registro in registros
    ]


def validar_datos_baseline(
    registros: list[dict[str, Any]],
    casos: list[dict[str, Any]],
) -> None:
    _validar_casos(casos)
    ids_esperados = [caso["id"] for caso in casos]
    ids_registrados = [registro.get("id") for registro in registros]
    if ids_registrados != ids_esperados:
        raise ValueError(
            "Los datos baseline no corresponden al golden dataset actual "
            "o están incompletos. Generalos nuevamente sin "
            "--reutilizar-respuestas."
        )

    casos_por_id = {caso["id"]: caso for caso in casos}
    for registro in registros:
        caso = casos_por_id[registro["id"]]
        if (
            registro.get("user_input") != caso["pregunta"]
            or registro.get("reference") != caso["ground_truth"]
        ):
            raise ValueError(
                f"Los datos baseline de {registro['id']} no coinciden con "
                "el golden dataset actual."
            )
        if not isinstance(registro.get("response"), str) or not registro[
            "response"
        ].strip():
            raise ValueError(
                f"El registro baseline {registro['id']} no tiene respuesta."
            )
        contextos = registro.get("retrieved_contexts")
        if not isinstance(contextos, list) or any(
            not isinstance(contexto, str) for contexto in contextos
        ):
            raise ValueError(
                f"Los contextos recuperados de {registro['id']} son inválidos."
            )


def guardar_json(ruta: Path, contenido: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def generar_datos_baseline(
    casos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    _validar_casos(casos)
    cadena = crear_cadena_rag(
        cantidad=CANTIDAD_DOCUMENTOS,
        nombre_coleccion=NOMBRE_COLECCION,
    )
    registros: list[dict[str, Any]] = []

    for posicion, caso in enumerate(casos, start=1):
        print(f"Generando respuesta {posicion}/{len(casos)}: {caso['id']}")
        salida = cadena.invoke(caso["pregunta"])
        registros.append(crear_registro_baseline(caso, salida))

    validar_datos_baseline(registros, casos)
    return registros


def cargar_datos_baseline(
    casos: list[dict[str, Any]],
) -> dict[str, Any]:
    with RUTA_DATOS_BASELINE.open(encoding="utf-8") as archivo:
        contenido = json.load(archivo)
    validar_datos_baseline(contenido["casos"], casos)
    return contenido


def _cargar_api_ragas() -> tuple[Any, Any, list[Any], Any]:
    modulo_vertex_original = sys.modules.get(MODULO_VERTEX_LEGACY)
    try:
        importlib.import_module(MODULO_VERTEX_LEGACY)
    except ModuleNotFoundError as error:
        if error.name != MODULO_VERTEX_LEGACY:
            raise

        # RAGAS 0.2 importa este tipo solo para detectar modelos Vertex.
        # Community 0.4 lo removió; esta evaluación usa Gemini.
        modulo_vertex_compatibilidad = ModuleType(MODULO_VERTEX_LEGACY)
        setattr(
            modulo_vertex_compatibilidad,
            "ChatVertexAI",
            type("ChatVertexAINoDisponible", (), {}),
        )
        sys.modules[MODULO_VERTEX_LEGACY] = modulo_vertex_compatibilidad

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from ragas.run_config import RunConfig
        return (
            Dataset,
            evaluate,
            [
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
            RunConfig,
        )
    except ImportError as error:
        raise RuntimeError(
            "Faltan dependencias de RAGAS. Instalá requirements.txt "
            "en el entorno virtual del proyecto."
        ) from error
    finally:
        if modulo_vertex_original is None:
            sys.modules.pop(MODULO_VERTEX_LEGACY, None)
        else:
            sys.modules[MODULO_VERTEX_LEGACY] = modulo_vertex_original


def evaluar_con_ragas(
    registros: list[dict[str, Any]],
) -> tuple[dict[str, float], list[dict[str, float]]]:
    clase_dataset, evaluar, metricas, clase_configuracion = _cargar_api_ragas()
    resultado = evaluar(
        dataset=clase_dataset.from_list(preparar_filas_ragas(registros)),
        metrics=metricas,
        llm=_crear_modelo_chat(),
        embeddings=EmbeddingsEcoLogix(),
        run_config=clase_configuracion(max_workers=1),
        raise_exceptions=True,
        show_progress=True,
    )

    tabla = resultado.to_pandas()
    faltantes = set(NOMBRES_METRICAS).difference(tabla.columns)
    if faltantes:
        raise RuntimeError(
            "RAGAS no devolvió todas las métricas esperadas: "
            + ", ".join(sorted(faltantes))
        )

    puntuaciones_por_caso: list[dict[str, float]] = []
    for _, fila in tabla.iterrows():
        puntuaciones = {}
        for nombre in NOMBRES_METRICAS:
            valor = float(fila[nombre])
            if not math.isfinite(valor):
                raise RuntimeError(
                    f"RAGAS devolvió un valor no numérico para {nombre}."
                )
            puntuaciones[nombre] = valor
        puntuaciones_por_caso.append(puntuaciones)

    if len(puntuaciones_por_caso) != len(registros):
        raise RuntimeError(
            "La cantidad de puntuaciones de RAGAS no coincide con la "
            "cantidad de casos evaluados."
        )

    promedios = {
        nombre: sum(
            puntuacion[nombre] for puntuacion in puntuaciones_por_caso
        )
        / len(puntuaciones_por_caso)
        for nombre in NOMBRES_METRICAS
    }
    return promedios, puntuaciones_por_caso


def _obtener_configuracion_modelo() -> tuple[str, str]:
    load_dotenv(RAIZ_PROYECTO / ".env")
    proveedor = os.getenv("RAG_PROVIDER", "openai").strip().lower()
    variable_modelo = (
        "GEMINI_MODEL" if proveedor == "gemini" else "OPENAI_MODEL"
    )
    modelo = os.getenv(variable_modelo, "").strip()
    if not modelo and proveedor == "openai":
        modelo = "gpt-4o-mini"
    return proveedor, modelo


def ejecutar(reutilizar_respuestas: bool = False) -> None:
    golden_dataset = cargar_golden_dataset()
    casos = golden_dataset["casos"]
    _validar_casos(casos)

    if reutilizar_respuestas:
        datos_baseline = cargar_datos_baseline(casos)
        registros = datos_baseline["casos"]
        proveedor_generacion = datos_baseline["proveedor"]
        modelo_generacion = datos_baseline["modelo"]
    else:
        registros = generar_datos_baseline(casos)
        proveedor_generacion, modelo_generacion = (
            _obtener_configuracion_modelo()
        )
        guardar_json(
            RUTA_DATOS_BASELINE,
            {
                "estado": "respuestas_generadas",
                "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
                "proveedor": proveedor_generacion,
                "modelo": modelo_generacion,
                "coleccion": NOMBRE_COLECCION,
                "k": CANTIDAD_DOCUMENTOS,
                "casos": registros,
            },
        )

    print(
        "Evaluando 10 respuestas del RAG básico con cuatro métricas RAGAS. "
        "Los evaluadores usan el proveedor configurado y embeddings locales."
    )
    promedios, puntuaciones = evaluar_con_ragas(registros)
    proveedor_evaluacion, modelo_evaluacion = _obtener_configuracion_modelo()
    contenido_resultados = {
        "estado": "completado",
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pipeline": "rag_basico",
        "proveedor_generacion": proveedor_generacion,
        "modelo_generacion": modelo_generacion,
        "proveedor_evaluacion": proveedor_evaluacion,
        "modelo_evaluacion": modelo_evaluacion,
        "coleccion": NOMBRE_COLECCION,
        "k": CANTIDAD_DOCUMENTOS,
        "cantidad_casos": len(registros),
        "metricas_promedio": promedios,
        "resultados_por_caso": [
            {
                "id": registro["id"],
                "tipo": registro["tipo"],
                "metricas": puntuaciones[posicion],
            }
            for posicion, registro in enumerate(registros)
        ],
    }
    guardar_json(RUTA_RESULTADOS_BASELINE, contenido_resultados)

    print("\nMétricas promedio del baseline:")
    for nombre, valor in promedios.items():
        print(f"- {nombre}: {valor:.4f}")
    print(f"\nResultados guardados en: {RUTA_RESULTADOS_BASELINE}")
    print(f"Respuestas y contextos guardados en: {RUTA_DATOS_BASELINE}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evalúa el pipeline RAG básico con el golden dataset y RAGAS."
        )
    )
    parser.add_argument(
        "--reutilizar-respuestas",
        action="store_true",
        help=(
            "Evalúa las respuestas y contextos ya guardados sin volver a "
            "llamar al pipeline RAG para generar respuestas."
        ),
    )
    argumentos = parser.parse_args()
    ejecutar(reutilizar_respuestas=argumentos.reutilizar_respuestas)


if __name__ == "__main__":
    main()
