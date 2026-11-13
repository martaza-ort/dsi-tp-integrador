from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda
from pydantic import PrivateAttr

from entrega_3 import rag_pipeline
from herramientas_rag import crear_herramienta_rag


class ModeloFalsoConRegistro(FakeListChatModel):
    _cantidad_llamadas: int = PrivateAttr(default=0)

    def _call(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        self._cantidad_llamadas += 1
        return super()._call(*args, **kwargs)


def test_recuperador_reranquea_y_no_genera_una_respuesta() -> None:
    documentos = [
        Document(page_content="Fragmento descartado."),
        Document(
            page_content="Información sobre entrega.",
            metadata={"titulo": "Entrega EcoLogix"},
        ),
    ]
    modelo = ModeloFalsoConRegistro(
        responses=['{"indices_seleccionados": [2]}']
    )
    recuperador = rag_pipeline._construir_recuperador_rag_con_reranking(
        retriever=RunnableLambda(lambda _: documentos),
        modelo_chat=modelo,
        cantidad_seleccionados=4,
    )

    resultado = recuperador.invoke("¿Cómo funciona la entrega?")

    assert resultado["candidate_documents"] == documentos
    assert resultado["selected_documents"] == [documentos[1]]
    assert modelo._cantidad_llamadas == 1


def test_herramienta_devuelve_fragmentos_seleccionados_y_fuentes() -> None:
    documento = Document(
        page_content="EcoLogix coordina la entrega según la zona.",
        metadata={"titulo_documento_origen": "Cobertura de entrega"},
    )
    herramienta = crear_herramienta_rag(
        recuperador=RunnableLambda(
            lambda _: {"selected_documents": [documento]}
        )
    )

    resultado = herramienta.invoke(
        {"consulta": "¿Entregan en mi zona?"}
    )

    assert resultado == (
        "[Cobertura de entrega]\n"
        "EcoLogix coordina la entrega según la zona."
    )
    assert herramienta.name == "buscar_conocimiento_ecologix"
    assert "consulta" in herramienta.args


def test_herramienta_informa_si_no_hay_fuentes_seleccionadas() -> None:
    herramienta = crear_herramienta_rag(
        recuperador=RunnableLambda(
            lambda _: {"selected_documents": []}
        )
    )

    assert herramienta.invoke({"consulta": "Consulta sin evidencia"}) == (
        "No se recuperaron fuentes relevantes para la consulta."
    )


def test_configuracion_predeterminada_del_recuperador_es_ocho_a_cuatro(
    monkeypatch,
) -> None:
    llamadas: dict[str, Any] = {}
    recuperador_falso = RunnableLambda(lambda _: {})
    modelo_falso = FakeListChatModel(responses=["{}"])

    def crear_retriever(
        cantidad: int,
        nombre_coleccion: str,
    ) -> RunnableLambda:
        llamadas["cantidad"] = cantidad
        llamadas["nombre_coleccion"] = nombre_coleccion
        return recuperador_falso

    monkeypatch.setattr(rag_pipeline, "crear_retriever", crear_retriever)
    monkeypatch.setattr(
        rag_pipeline,
        "_crear_modelo_chat",
        lambda modelo, limitador_tasa: modelo_falso,
    )

    rag_pipeline.crear_recuperador_rag_con_reranking()

    assert llamadas == {
        "cantidad": rag_pipeline.CANTIDAD_CANDIDATOS_RERANKING,
        "nombre_coleccion": rag_pipeline.NOMBRE_COLECCION_CHUNKS,
    }
    assert rag_pipeline.CANTIDAD_CANDIDATOS_RERANKING == 8
    assert rag_pipeline.CANTIDAD_DOCUMENTOS_RERANKEADOS == 4
