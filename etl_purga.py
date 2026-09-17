"""ETL básico para limpiar y normalizar la base de conocimiento de EcoLogix.

Objetivo:
- cargar base_conocimiento.json
- quitar documentos vacíos o sin texto útil
- normalizar texto y tags
- eliminar duplicados por título/texto
- guardar una versión limpia para el siguiente paso del pipeline vectorial
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "base_conocimiento.json"
OUTPUT_PATH = ROOT / "base_conocimiento_limpia.json"


def normalizar_texto(valor: str | None) -> str:
    if not valor:
        return ""
    texto = " ".join(valor.split())
    return texto.strip()


def cargar_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def limpiar_documentos(documentos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vistos: set[str] = set()
    salida: list[dict[str, Any]] = []

    for doc in documentos:
        titulo = normalizar_texto(doc.get("titulo"))
        texto = normalizar_texto(doc.get("texto"))

        if not titulo or not texto:
            continue

        clave = (titulo.lower(), texto.lower())
        if clave in vistos:
            continue

        vistos.add(clave)

        doc_limpio = dict(doc)
        doc_limpio["titulo"] = titulo
        doc_limpio["texto"] = texto

        tags = doc_limpio.get("tags") or []
        doc_limpio["tags"] = [normalizar_texto(str(tag)).lower() for tag in tags if normalizar_texto(str(tag))]

        if "metadatos" in doc_limpio and isinstance(doc_limpio["metadatos"], dict):
            doc_limpio["metadatos"] = {str(k): v for k, v in doc_limpio["metadatos"].items()}

        salida.append(doc_limpio)

    return salida


def main() -> None:
    data = cargar_json(INPUT_PATH)
    documentos = data.get("documentos", [])
    documentos_limpios = limpiar_documentos(documentos)

    resultado = dict(data)
    resultado["documentos"] = documentos_limpios
    resultado["meta"] = {
        "total_original": len(documentos),
        "total_limpio": len(documentos_limpios),
        "estado": "limpio",
        "proceso": "etl_purga",
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"Documentos originales: {len(documentos)}")
    print(f"Documentos finales: {len(documentos_limpios)}")
    print(f"Archivo generado: {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
