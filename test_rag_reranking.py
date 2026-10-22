from __future__ import annotations

from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableLambda
from pydantic import PrivateAttr

from entrega_3.rag_pipeline import (
    SeleccionRelevancia,
    _construir_cadena,
    _construir_cadena_rag_con_reranking,
    _validar_seleccion_reranking,
)


class ModeloFalsoConRegistro(FakeListChatModel):
    _prompts_recibidos: list[str] = PrivateAttr(default_factory=list)

    def _call(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        mensajes = args[0]
        self._prompts_recibidos.append(
            "\n".join(str(mensaje.content) for mensaje in mensajes)
        )
        return super()._call(*args, **kwargs)


def test_cadena_basica_conserva_su_respuesta_y_fuentes() -> None:
    documento = Document(
        page_content="Contenido del índice básico.",
        metadata={"titulo": "Fuente básica"},
    )
    modelo = ModeloFalsoConRegistro(responses=["Respuesta básica."])
    cadena = _construir_cadena(
        retriever=RunnableLambda(lambda _: [documento]),
        modelo_chat=modelo,
    )

    resultado = cadena.invoke("Consulta básica")

    assert resultado == {
        "answer": "Respuesta básica.",
        "source_documents": [documento],
    }
    assert len(modelo._prompts_recibidos) == 1


def test_cadena_pasa_al_generador_solo_documentos_seleccionados() -> None:
    candidatos = [
        Document(
            page_content="Contenido irrelevante que no debe llegar al generador.",
            metadata={"titulo": "Irrelevante"},
        ),
        Document(
            page_content="Información pertinente que sí debe llegar al generador.",
            metadata={"titulo": "Pertinente"},
        ),
    ]
    modelo = ModeloFalsoConRegistro(
        responses=[
            '{"indices_seleccionados": [2]}',
            "Respuesta respaldada.",
        ]
    )
    cadena = _construir_cadena_rag_con_reranking(
        retriever=RunnableLambda(lambda _: candidatos),
        modelo_chat=modelo,
        cantidad_seleccionados=1,
    )

    resultado = cadena.invoke("¿Cuál es la información pertinente?")

    assert resultado["answer"] == "Respuesta respaldada."
    assert resultado["candidate_documents"] == candidatos
    assert resultado["selected_documents"] == [candidatos[1]]
    assert resultado["source_documents"] == [candidatos[1]]
    assert len(modelo._prompts_recibidos) == 2
    assert "Información pertinente" in modelo._prompts_recibidos[1]
    assert "Contenido irrelevante" not in modelo._prompts_recibidos[1]


def test_cadena_acepta_que_el_juez_no_seleccione_documentos() -> None:
    modelo = ModeloFalsoConRegistro(
        responses=[
            '{"indices_seleccionados": []}',
            "No poseo información suficiente en el contexto para responder.",
        ]
    )
    cadena = _construir_cadena_rag_con_reranking(
        retriever=RunnableLambda(
            lambda _: [Document(page_content="Contenido no pertinente.")]
        ),
        modelo_chat=modelo,
        cantidad_seleccionados=1,
    )

    resultado = cadena.invoke("Consulta fuera del contenido")

    assert resultado["candidate_documents"]
    assert resultado["selected_documents"] == []
    assert resultado["source_documents"] == []
    assert resultado["answer"] == (
        "No poseo información suficiente en el contexto para responder."
    )
    assert "No se recuperaron documentos relevantes." in (
        modelo._prompts_recibidos[1]
    )


def test_cadena_propaga_respuesta_estructurada_invalida_del_juez() -> None:
    modelo = ModeloFalsoConRegistro(
        responses=["No es JSON", "Esta respuesta no debería generarse."]
    )
    cadena = _construir_cadena_rag_con_reranking(
        retriever=RunnableLambda(
            lambda _: [Document(page_content="Candidato pertinente.")]
        ),
        modelo_chat=modelo,
        cantidad_seleccionados=1,
    )

    with pytest.raises(OutputParserException):
        cadena.invoke("Consulta")

    assert modelo.i == 1


@pytest.mark.parametrize(
    ("indices", "cantidad_maxima", "mensaje"),
    [
        ([1, 1], 2, "índices duplicados"),
        ([3], 2, "fuera del rango"),
        ([1, 2, 3], 2, "más fragmentos que el máximo"),
    ],
)
def test_rechaza_selecciones_invalidas_del_juez(
    indices: list[int],
    cantidad_maxima: int,
    mensaje: str,
) -> None:
    candidatos = [Document(page_content="Candidato")]
    decision = SeleccionRelevancia(indices_seleccionados=indices)

    with pytest.raises(ValueError, match=mensaje):
        _validar_seleccion_reranking(
            decision,
            candidatos,
            cantidad_maxima,
        )
