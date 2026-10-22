from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RAIZ_PROYECTO = Path(__file__).resolve().parent
RUTA_DATASET = RAIZ_PROYECTO / "entrega_3" / "golden_dataset.json"
RUTA_CORPUS = RAIZ_PROYECTO / "base_conocimiento_limpia.json"
DISTRIBUCION_ESPERADA = {
    "simple": 3,
    "compleja": 3,
    "escape": 2,
    "ambigua_informal": 2,
}


def cargar_json(ruta: Path) -> dict[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def test_golden_dataset_tiene_las_categorias_y_cantidades_requeridas() -> None:
    dataset = cargar_json(RUTA_DATASET)
    casos = dataset["casos"]
    distribucion = {
        tipo: sum(caso["tipo"] == tipo for caso in casos)
        for tipo in DISTRIBUCION_ESPERADA
    }

    assert len(casos) == 10
    assert distribucion == DISTRIBUCION_ESPERADA


def test_casos_tienen_pregunta_referencia_e_identificador_unicos() -> None:
    casos = cargar_json(RUTA_DATASET)["casos"]

    assert len({caso["id"] for caso in casos}) == len(casos)
    assert len({caso["pregunta"] for caso in casos}) == len(casos)
    assert all(caso["pregunta"].strip() for caso in casos)
    assert all(caso["ground_truth"].strip() for caso in casos)


def test_fuentes_esperadas_existen_en_el_corpus_limpio() -> None:
    dataset = cargar_json(RUTA_DATASET)
    corpus = cargar_json(RUTA_CORPUS)
    fuentes_corpus = {
        documento["id"]: documento["metadatos"]["titulo"]
        for documento in corpus["documentos"]
    }

    for caso in dataset["casos"]:
        for fuente in caso["fuentes_esperadas"]:
            assert fuente["id"] in fuentes_corpus
            assert fuente["titulo"] == fuentes_corpus[fuente["id"]]


def test_preguntas_complejas_requieren_combinar_varias_fuentes() -> None:
    casos_complejos = [
        caso
        for caso in cargar_json(RUTA_DATASET)["casos"]
        if caso["tipo"] == "compleja"
    ]

    assert all(len(caso["fuentes_esperadas"]) >= 2 for caso in casos_complejos)


def test_preguntas_de_escape_no_tienen_fuentes_y_usan_la_respuesta_configurada() -> None:
    dataset = cargar_json(RUTA_DATASET)
    casos_escape = [
        caso for caso in dataset["casos"] if caso["tipo"] == "escape"
    ]

    assert all(not caso["fuentes_esperadas"] for caso in casos_escape)
    assert all(
        caso["ground_truth"] == dataset["respuesta_esperada_sin_informacion"]
        for caso in casos_escape
    )
