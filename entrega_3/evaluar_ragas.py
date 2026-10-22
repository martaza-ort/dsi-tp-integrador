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
from typing import Any, Callable

from dotenv import load_dotenv
from langchain_core.rate_limiters import BaseRateLimiter, InMemoryRateLimiter

from entrega_3.rag_pipeline import (
    RAIZ_PROYECTO,
    EmbeddingsEcoLogix,
    _crear_modelo_chat,
    crear_cadena_rag,
    crear_cadena_rag_con_reranking,
)
from entrega_3.indexar_chunks import NOMBRE_COLECCION_CHUNKS
from vector_db import NOMBRE_COLECCION


DIRECTORIO_ENTREGA = Path(__file__).resolve().parent
RUTA_GOLDEN_DATASET = DIRECTORIO_ENTREGA / "golden_dataset.json"
RUTA_DATOS_BASELINE = (
    RAIZ_PROYECTO / "docs-resultados" / "datos_ragas_baseline.json"
)
RUTA_RESULTADOS_BASELINE = (
    RAIZ_PROYECTO / "docs-resultados" / "resultados_ragas_baseline.json"
)
RUTA_DATOS_AVANZADO = (
    RAIZ_PROYECTO / "docs-resultados" / "datos_ragas_avanzado.json"
)
RUTA_RESULTADOS_AVANZADO = (
    RAIZ_PROYECTO / "docs-resultados" / "resultados_ragas_avanzado.json"
)
CANTIDAD_DOCUMENTOS = 3
CANTIDAD_CANDIDATOS_AVANZADO = 8
CANTIDAD_SELECCIONADOS_AVANZADO = 4
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


def generar_datos_avanzado(
    casos: list[dict[str, Any]],
    registros_previos: list[dict[str, Any]] | None = None,
    guardar_progreso: Callable[[list[dict[str, Any]]], None] | None = None,
    limitador_tasa: BaseRateLimiter | None = None,
) -> list[dict[str, Any]]:
    _validar_casos(casos)
    registros = list(registros_previos or [])
    if registros:
        casos_por_id = {caso["id"]: caso for caso in casos}
        ids_guardados = [registro.get("id") for registro in registros]
        if (
            len(set(ids_guardados)) != len(ids_guardados)
            or any(identificador not in casos_por_id for identificador in ids_guardados)
            or ids_guardados
            != [caso["id"] for caso in casos[: len(ids_guardados)]]
        ):
            raise ValueError(
                "Los datos parciales del pipeline avanzado contienen ids "
                "duplicados, ajenos o fuera de orden respecto del golden dataset."
            )
        validar_datos_baseline(
            registros,
            [casos_por_id[identificador] for identificador in ids_guardados],
        )

    cadena = crear_cadena_rag_con_reranking(
        cantidad_candidatos=CANTIDAD_CANDIDATOS_AVANZADO,
        cantidad_seleccionados=CANTIDAD_SELECCIONADOS_AVANZADO,
        nombre_coleccion=NOMBRE_COLECCION_CHUNKS,
        limitador_tasa=limitador_tasa,
    )
    ids_guardados = {registro["id"] for registro in registros}

    for posicion, caso in enumerate(casos, start=1):
        if caso["id"] in ids_guardados:
            continue
        print(
            f"Generando respuesta avanzada {posicion}/{len(casos)}: "
            f"{caso['id']}"
        )
        salida = cadena.invoke(caso["pregunta"])
        registro = crear_registro_baseline(caso, salida)
        for campo_salida, campo_registro in (
            ("candidate_documents", "candidatos"),
            ("selected_documents", "seleccionados"),
        ):
            documentos = salida.get(campo_salida)
            if not isinstance(documentos, list):
                raise TypeError(
                    f"El pipeline avanzado no devolvió una lista válida "
                    f"en {campo_salida} para {caso['id']}."
                )
            registro[campo_registro] = [
                {
                    "texto": documento.page_content,
                    "titulo": documento.metadata.get(
                        "titulo_documento_origen",
                        documento.metadata.get("titulo", ""),
                    ),
                    "indice_chunk": documento.metadata.get("indice_chunk"),
                }
                for documento in documentos
            ]
        registros.append(registro)
        ids_guardados.add(caso["id"])
        if guardar_progreso is not None:
            guardar_progreso(registros)

    validar_datos_baseline(registros, casos)
    return registros


def cargar_datos_parciales_avanzado(
    casos: list[dict[str, Any]],
    ruta: Path = RUTA_DATOS_AVANZADO,
) -> list[dict[str, Any]]:
    if not ruta.is_file():
        return []

    with ruta.open(encoding="utf-8") as archivo:
        contenido = json.load(archivo)
    if (
        contenido.get("estado") != "generacion_parcial"
        or contenido.get("pipeline") != "avanzado"
        or not isinstance(contenido.get("casos"), list)
    ):
        return []

    casos_por_id = {caso["id"]: caso for caso in casos}
    registros = contenido["casos"]
    ids_guardados = [registro.get("id") for registro in registros]
    if (
        len(set(ids_guardados)) != len(ids_guardados)
        or any(identificador not in casos_por_id for identificador in ids_guardados)
        or ids_guardados != [caso["id"] for caso in casos[: len(ids_guardados)]]
    ):
        raise ValueError(
            "Los datos parciales del pipeline avanzado contienen ids "
            "duplicados, ajenos o fuera de orden respecto del golden dataset."
        )
    validar_datos_baseline(
        registros,
        [casos_por_id[identificador] for identificador in ids_guardados],
    )
    return registros


def cargar_datos_baseline(
    casos: list[dict[str, Any]],
    ruta: Path = RUTA_DATOS_BASELINE,
) -> dict[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
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
    limitador_tasa: BaseRateLimiter | None = None,
) -> tuple[dict[str, float], list[dict[str, float]]]:
    clase_dataset, evaluar, metricas, clase_configuracion = _cargar_api_ragas()
    resultado = evaluar(
        dataset=clase_dataset.from_list(preparar_filas_ragas(registros)),
        metrics=metricas,
        llm=_crear_modelo_chat(limitador_tasa=limitador_tasa),
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


def ejecutar(
    reutilizar_respuestas: bool = False,
    pipeline: str = "basico",
) -> None:
    if pipeline not in {"basico", "avanzado"}:
        raise ValueError("El pipeline debe ser 'basico' o 'avanzado'.")

    golden_dataset = cargar_golden_dataset()
    casos = golden_dataset["casos"]
    _validar_casos(casos)

    es_avanzado = pipeline == "avanzado"
    ruta_datos = RUTA_DATOS_AVANZADO if es_avanzado else RUTA_DATOS_BASELINE
    ruta_resultados = (
        RUTA_RESULTADOS_AVANZADO if es_avanzado else RUTA_RESULTADOS_BASELINE
    )
    nombre_coleccion = (
        NOMBRE_COLECCION_CHUNKS if es_avanzado else NOMBRE_COLECCION
    )
    limitador_tasa = (
        InMemoryRateLimiter(
            requests_per_second=0.2,
            check_every_n_seconds=0.1,
            max_bucket_size=1,
        )
        if es_avanzado
        else None
    )

    if reutilizar_respuestas:
        datos_baseline = cargar_datos_baseline(casos, ruta_datos)
        registros = datos_baseline["casos"]
        proveedor_generacion = datos_baseline["proveedor"]
        modelo_generacion = datos_baseline["modelo"]
    else:
        proveedor_generacion, modelo_generacion = (
            _obtener_configuracion_modelo()
        )
        if es_avanzado:
            registros_previos = cargar_datos_parciales_avanzado(casos)

            def guardar_progreso(
                registros_actuales: list[dict[str, Any]],
            ) -> None:
                guardar_json(
                    ruta_datos,
                    {
                        "estado": "generacion_parcial",
                        "fecha": datetime.now()
                        .astimezone()
                        .isoformat(timespec="seconds"),
                        "proveedor": proveedor_generacion,
                        "modelo": modelo_generacion,
                        "pipeline": pipeline,
                        "coleccion": nombre_coleccion,
                        "k": CANTIDAD_CANDIDATOS_AVANZADO,
                        "cantidad_seleccionados": (
                            CANTIDAD_SELECCIONADOS_AVANZADO
                        ),
                        "casos": registros_actuales,
                    },
                )

            registros = generar_datos_avanzado(
                casos,
                registros_previos=registros_previos,
                guardar_progreso=guardar_progreso,
                limitador_tasa=limitador_tasa,
            )
        else:
            registros = generar_datos_baseline(casos)

        guardar_json(
            ruta_datos,
            {
                "estado": "respuestas_generadas",
                "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
                "proveedor": proveedor_generacion,
                "modelo": modelo_generacion,
                "pipeline": pipeline,
                "coleccion": nombre_coleccion,
                "k": (
                    CANTIDAD_CANDIDATOS_AVANZADO
                    if es_avanzado
                    else CANTIDAD_DOCUMENTOS
                ),
                **(
                    {
                        "cantidad_seleccionados": (
                            CANTIDAD_SELECCIONADOS_AVANZADO
                        )
                    }
                    if es_avanzado
                    else {}
                ),
                "casos": registros,
            },
        )

    print(
        f"Evaluando {len(registros)} respuestas del RAG {pipeline} con "
        "cuatro métricas RAGAS. "
        "Los evaluadores usan el proveedor configurado y embeddings locales."
    )
    promedios, puntuaciones = evaluar_con_ragas(
        registros,
        limitador_tasa=limitador_tasa,
    )
    proveedor_evaluacion, modelo_evaluacion = _obtener_configuracion_modelo()
    contenido_resultados = {
        "estado": "completado",
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pipeline": f"rag_{pipeline}",
        "proveedor_generacion": proveedor_generacion,
        "modelo_generacion": modelo_generacion,
        "proveedor_evaluacion": proveedor_evaluacion,
        "modelo_evaluacion": modelo_evaluacion,
        "coleccion": nombre_coleccion,
        "k": (
            CANTIDAD_CANDIDATOS_AVANZADO
            if es_avanzado
            else CANTIDAD_DOCUMENTOS
        ),
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
    if es_avanzado:
        contenido_resultados["cantidad_seleccionados"] = (
            CANTIDAD_SELECCIONADOS_AVANZADO
        )
    guardar_json(ruta_resultados, contenido_resultados)

    print(f"\nMétricas promedio del RAG {pipeline}:")
    for nombre, valor in promedios.items():
        print(f"- {nombre}: {valor:.4f}")
    print(f"\nResultados guardados en: {ruta_resultados}")
    print(f"Respuestas y contextos guardados en: {ruta_datos}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evalúa el pipeline RAG con el golden dataset y RAGAS."
        )
    )
    parser.add_argument(
        "--pipeline",
        choices=("basico", "avanzado"),
        default="basico",
        help="Pipeline a evaluar; el avanzado incorpora chunks y reranking.",
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
    ejecutar(
        reutilizar_respuestas=argumentos.reutilizar_respuestas,
        pipeline=argumentos.pipeline,
    )


if __name__ == "__main__":
    main()
