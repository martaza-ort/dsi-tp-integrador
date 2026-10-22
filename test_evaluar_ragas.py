from __future__ import annotations

from typing import Any

import pytest
from langchain_core.documents import Document

from entrega_3 import evaluar_ragas as modulo_evaluador
from entrega_3.evaluar_ragas import (
    CANTIDAD_CANDIDATOS_AVANZADO,
    CANTIDAD_SELECCIONADOS_AVANZADO,
    NOMBRES_METRICAS,
    _cargar_api_ragas,
    crear_registro_baseline,
    evaluar_con_ragas,
    generar_datos_avanzado,
    preparar_filas_ragas,
    validar_datos_baseline,
)


def caso_prueba() -> dict[str, Any]:
    return {
        "id": "C1-S1",
        "tipo": "simple",
        "pregunta": "¿Qué tamaño tienen los vasos?",
        "ground_truth": "Tienen 12 oz.",
    }


def test_crear_registro_conserva_respuesta_referencia_y_contextos() -> None:
    caso = caso_prueba()
    documento = Document(
        page_content="Los vasos son de 12 oz.",
        metadata={"titulo": "Vasos de bagazo 12 oz"},
    )

    registro = crear_registro_baseline(
        caso,
        {
            "answer": "Son de 12 oz.",
            "source_documents": [documento],
        },
    )

    assert registro["id"] == "C1-S1"
    assert registro["user_input"] == caso["pregunta"]
    assert registro["reference"] == caso["ground_truth"]
    assert registro["response"] == "Son de 12 oz."
    assert registro["retrieved_contexts"] == ["Los vasos son de 12 oz."]


def test_rechaza_respuesta_vacia_o_fuentes_de_tipo_invalido() -> None:
    caso = caso_prueba()

    with pytest.raises(ValueError, match="respuesta válida"):
        crear_registro_baseline(
            caso,
            {"answer": " ", "source_documents": []},
        )

    with pytest.raises(TypeError, match="lista de fuentes"):
        crear_registro_baseline(
            caso,
            {"answer": "Respuesta", "source_documents": None},
        )


def test_preparar_filas_selecciona_el_esquema_requerido_por_ragas() -> None:
    registro = crear_registro_baseline(
        caso_prueba(),
        {
            "answer": "Son de 12 oz.",
            "source_documents": [
                Document(page_content="Los vasos son de 12 oz.")
            ],
        },
    )

    assert preparar_filas_ragas([registro]) == [
        {
            "user_input": "¿Qué tamaño tienen los vasos?",
            "response": "Son de 12 oz.",
            "retrieved_contexts": ["Los vasos son de 12 oz."],
            "reference": "Tienen 12 oz.",
        }
    ]


def test_validar_datos_baseline_detecta_dataset_incompleto() -> None:
    with pytest.raises(ValueError, match="incompletos"):
        validar_datos_baseline([], [caso_prueba()])


def test_validar_datos_baseline_rechaza_referencia_desactualizada() -> None:
    registro = crear_registro_baseline(
        caso_prueba(),
        {
            "answer": "Son de 12 oz.",
            "source_documents": [
                Document(page_content="Los vasos son de 12 oz.")
            ],
        },
    )
    registro["reference"] = "Referencia antigua."

    with pytest.raises(ValueError, match="no coinciden"):
        validar_datos_baseline([registro], [caso_prueba()])


def test_generar_datos_avanzado_registra_candidatos_y_seleccionados(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caso = caso_prueba()
    candidatos = [
        Document(
            page_content="Contexto candidato.",
            metadata={
                "titulo_documento_origen": "Título candidato",
                "indice_chunk": 2,
            },
        )
    ]
    seleccionados = [
        Document(
            page_content="Contexto seleccionado.",
            metadata={
                "titulo_documento_origen": "Título seleccionado",
                "indice_chunk": 3,
            },
        )
    ]
    parametros: list[dict[str, Any]] = []

    class CadenaFalsa:
        def invoke(self, pregunta: str) -> dict[str, Any]:
            assert pregunta == caso["pregunta"]
            return {
                "answer": "Son de 12 oz.",
                "source_documents": seleccionados,
                "candidate_documents": candidatos,
                "selected_documents": seleccionados,
            }

    def crear_cadena_falsa(**argumentos: Any) -> CadenaFalsa:
        parametros.append(argumentos)
        return CadenaFalsa()

    monkeypatch.setattr(
        modulo_evaluador,
        "crear_cadena_rag_con_reranking",
        crear_cadena_falsa,
    )

    registros = generar_datos_avanzado([caso])

    assert parametros[0]["cantidad_candidatos"] == CANTIDAD_CANDIDATOS_AVANZADO
    assert (
        parametros[0]["cantidad_seleccionados"]
        == CANTIDAD_SELECCIONADOS_AVANZADO
    )
    assert registros[0]["retrieved_contexts"] == [
        "Contexto seleccionado."
    ]
    assert registros[0]["candidatos"] == [
        {
            "texto": "Contexto candidato.",
            "titulo": "Título candidato",
            "indice_chunk": 2,
        }
    ]
    assert registros[0]["seleccionados"] == [
        {
            "texto": "Contexto seleccionado.",
            "titulo": "Título seleccionado",
            "indice_chunk": 3,
        }
    ]


def test_api_ragas_disponible_con_las_metricas_requeridas() -> None:
    clase_dataset, _, metricas, clase_configuracion = _cargar_api_ragas()
    dataset = clase_dataset.from_list(
        preparar_filas_ragas(
            [
                crear_registro_baseline(
                    caso_prueba(),
                    {
                        "answer": "Son de 12 oz.",
                        "source_documents": [
                            Document(page_content="Los vasos son de 12 oz.")
                        ],
                    },
                )
            ]
        )
    )

    assert tuple(metrica.name for metrica in metricas) == NOMBRES_METRICAS
    assert set(dataset.column_names) == {
        "user_input",
        "response",
        "retrieved_contexts",
        "reference",
    }
    assert clase_configuracion(max_workers=1).max_workers == 1


def test_evaluar_con_ragas_ensambla_metricas_y_calcula_promedios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filas = []

    class DatasetFalso:
        def __init__(self) -> None:
            self.registros: list[dict[str, Any]] = []

        @classmethod
        def from_list(
            cls, registros: list[dict[str, Any]]
        ) -> "DatasetFalso":
            dataset = cls()
            dataset.registros = registros
            return dataset

    class TablaFalsa:
        columns = list(NOMBRES_METRICAS)

        def iterrows(self):
            return iter(
                [
                    (0, dict.fromkeys(NOMBRES_METRICAS, 0.2)),
                    (1, dict.fromkeys(NOMBRES_METRICAS, 0.8)),
                ]
            )

    class ResultadoFalso:
        def to_pandas(self) -> TablaFalsa:
            return TablaFalsa()

    def evaluar_falso(**argumentos: Any) -> ResultadoFalso:
        filas.append(argumentos)
        return ResultadoFalso()

    metricas_falsas = [object() for _ in NOMBRES_METRICAS]

    class ConfiguracionFalsa:
        def __init__(self, **argumentos: Any) -> None:
            self.argumentos = argumentos

    monkeypatch.setattr(
        modulo_evaluador,
        "_cargar_api_ragas",
        lambda: (
            DatasetFalso,
            evaluar_falso,
            metricas_falsas,
            ConfiguracionFalsa,
        ),
    )
    monkeypatch.setattr(
        modulo_evaluador,
        "_crear_modelo_chat",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        modulo_evaluador, "EmbeddingsEcoLogix", lambda: object()
    )

    registro = crear_registro_baseline(
        caso_prueba(),
        {
            "answer": "Son de 12 oz.",
            "source_documents": [
                Document(page_content="Los vasos son de 12 oz.")
            ],
        },
    )
    registros = [registro, {**registro, "id": "C1-S2"}]

    promedios, puntuaciones = evaluar_con_ragas(registros)

    assert promedios == dict.fromkeys(NOMBRES_METRICAS, 0.5)
    assert puntuaciones == [
        dict.fromkeys(NOMBRES_METRICAS, 0.2),
        dict.fromkeys(NOMBRES_METRICAS, 0.8),
    ]
    assert filas[0]["dataset"].registros == preparar_filas_ragas(registros)
    assert filas[0]["metrics"] == metricas_falsas
    assert filas[0]["run_config"].argumentos == {"max_workers": 1}
    assert filas[0]["raise_exceptions"] is True
