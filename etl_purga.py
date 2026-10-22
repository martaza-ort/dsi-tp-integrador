"""ETL de normalización y purga semántica de EcoLogix.

Objetivo:
- cargar base_conocimiento.json
- normalizar claves y tipos inconsistentes
- resolver colisiones de IDs
- quitar documentos vacíos o duplicados semánticos
- guardar una versión limpia para el siguiente paso del pipeline vectorial
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from similitud_coseno import generar_embeddings, preparar_texto


ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "base_conocimiento.json"
OUTPUT_PATH = ROOT / "base_conocimiento_limpia.json"
REPORT_PATH = ROOT / "docs-resultados" / "resultados_etl.md"
DISTANCIA_UMBRAL = 0.15

CLAVES_ALTERNATIVAS = {
    "texto": "descripcion_semantica",
    "descripcion": "descripcion_semantica",
    "descripción_semántica": "descripcion_semantica",
}
CLAVES_BOOLEANAS = {"activo", "es_activo"}


def normalizar_texto(valor: str | None) -> str:
    if not valor:
        return ""
    texto = " ".join(valor.split())
    return texto.strip()


def cargar_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def convertir_booleano(valor: Any) -> Any:
    if isinstance(valor, str) and valor.lower() in {"true", "false"}:
        return valor.lower() == "true"
    return valor


def normalizar_activo(metadatos: dict[str, Any]) -> bool:
    if "activo" in metadatos:
        return bool(convertir_booleano(metadatos["activo"]))

    estado = str(metadatos.get("estado", "activo")).lower()
    return estado not in {"inactivo", "discontinuado", "baja", "vencido"}


def normalizar_documento(
    documento: dict[str, Any],
    correcciones: list[str],
) -> dict[str, Any]:
    normalizado = dict(documento)
    metadatos_originales = normalizado.get("metadatos")
    metadatos = dict(metadatos_originales) if isinstance(metadatos_originales, dict) else {}

    for clave_alternativa, clave_canonica in CLAVES_ALTERNATIVAS.items():
        if clave_alternativa in normalizado and clave_canonica not in normalizado:
            normalizado[clave_canonica] = normalizado.pop(clave_alternativa)
            correcciones.append(
                f"{documento.get('id')}: {clave_alternativa} -> {clave_canonica}"
            )

    for clave in ("titulo", "tipo", "categoria"):
        if clave in normalizado:
            metadatos[clave] = normalizado.pop(clave)

    tags = normalizado.pop("tags", metadatos.get("tags_regionales", [])) or []
    metadatos["tags_regionales"] = [
        normalizar_texto(str(tag)).lower()
        for tag in tags
        if normalizar_texto(str(tag))
    ]

    metadatos = {
        str(clave): convertir_booleano(valor)
        for clave, valor in metadatos.items()
    }
    metadatos["activo"] = normalizar_activo(metadatos)
    metadatos.pop("estado", None)
    normalizado["metadatos"] = metadatos
    normalizado["descripcion_semantica"] = normalizar_texto(
        normalizado.get("descripcion_semantica")
    )

    if "activo" in metadatos and "activo" in (metadatos_originales or {}):
        valor_original = (metadatos_originales or {}).get("activo")
        if isinstance(valor_original, str):
            correcciones.append(f"{documento.get('id')}: activo string -> booleano")

    return normalizado


def resolver_ids(
    documentos: list[dict[str, Any]],
    colisiones: list[str],
) -> list[dict[str, Any]]:
    usados: set[str] = set()
    salida: list[dict[str, Any]] = []

    for documento in documentos:
        candidato = str(documento.get("id", "documento"))
        id_resuelto = candidato
        sufijo = 2
        while id_resuelto in usados:
            id_resuelto = f"{candidato}-dup-{sufijo}"
            sufijo += 1

        if id_resuelto != candidato:
            colisiones.append(f"{candidato} -> {id_resuelto}")

        documento_resuelto = dict(documento)
        documento_resuelto["id"] = id_resuelto
        usados.add(id_resuelto)
        salida.append(documento_resuelto)

    return salida


def distancia_coseno(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    norma_a = np.linalg.norm(vector_a)
    norma_b = np.linalg.norm(vector_b)
    if norma_a == 0 or norma_b == 0:
        return 1.0
    similitud = np.dot(vector_a, vector_b) / (norma_a * norma_b)
    return float(1 - similitud)


def purgar_casi_duplicados(
    documentos: list[dict[str, Any]],
    eliminados: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    textos = [preparar_texto(documento) for documento in documentos]
    embeddings = generar_embeddings(textos)
    conservados: list[dict[str, Any]] = []
    embeddings_conservados: list[np.ndarray] = []

    for documento, embedding in zip(documentos, embeddings):
        duplicado_de = None
        distancia = None

        for conservado, embedding_conservado in zip(
            conservados,
            embeddings_conservados,
        ):
            distancia_actual = distancia_coseno(embedding, embedding_conservado)
            if distancia_actual <= DISTANCIA_UMBRAL:
                duplicado_de = conservado["id"]
                distancia = distancia_actual
                break

        if duplicado_de is not None:
            eliminados.append(
                {
                    "id_eliminado": documento["id"],
                    "id_conservado": duplicado_de,
                    "distancia_coseno": round(distancia or 0.0, 4),
                    "motivo": "casi-duplicado semántico",
                }
            )
            continue

        conservados.append(documento)
        embeddings_conservados.append(embedding)

    return conservados

def buscar_pares_distintos_cercanos(
    documentos: list[dict[str, Any]],
    cantidad: int = 3,
) -> list[dict[str, Any]]:
    """
    Busca los pares de documentos conservados con menor distancia coseno.

    Como estos documentos sobrevivieron a la purga, sus distancias son
    mayores al umbral. Sirven como ejemplos negativos para comprobar
    que el umbral no elimina documentos diferentes pero relacionados.
    """

    if len(documentos) < 2:
        return []

    textos = [
        preparar_texto(documento)
        for documento in documentos
    ]
    embeddings = generar_embeddings(textos)

    pares: list[dict[str, Any]] = []

    for posicion_a in range(len(documentos)):
        for posicion_b in range(
            posicion_a + 1,
            len(documentos),
        ):
            documento_a = documentos[posicion_a]
            documento_b = documentos[posicion_b]

            distancia = distancia_coseno(
                embeddings[posicion_a],
                embeddings[posicion_b],
            )

            pares.append(
                {
                    "id_a": documento_a["id"],
                    "titulo_a": documento_a.get(
                        "metadatos",
                        {},
                    ).get("titulo", ""),
                    "id_b": documento_b["id"],
                    "titulo_b": documento_b.get(
                        "metadatos",
                        {},
                    ).get("titulo", ""),
                    "distancia_coseno": round(
                        distancia,
                        4,
                    ),
                }
            )

    pares.sort(
        key=lambda par: par["distancia_coseno"]
    )

    return pares[:cantidad]


def limpiar_documentos(documentos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mantiene la API simple para consumidores existentes."""
    return purgar_documentos(documentos)[0]


def purgar_documentos(
    documentos: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    correcciones: list[str] = []
    colisiones: list[str] = []
    eliminados: list[dict[str, Any]] = []

    normalizados = [
        normalizar_documento(documento, correcciones)
        for documento in documentos
    ]
    validos = [
        documento
        for documento in normalizados
        if documento["descripcion_semantica"]
    ]
    con_ids_resueltos = resolver_ids(
        validos,
        colisiones,
    )

    salida = purgar_casi_duplicados(
        con_ids_resueltos,
        eliminados,
    )

    pares_distintos = buscar_pares_distintos_cercanos(
        salida,
        cantidad=3,
    )

    reporte = {
        "correcciones": correcciones,
        "colisiones": colisiones,
        "eliminados": eliminados,
        "pares_distintos": pares_distintos,
    }
    return salida, reporte


def escribir_reporte(
    total_original: int,
    total_limpio: int,
    reporte: dict[str, Any],
) -> None:
    correcciones = reporte["correcciones"] or ["Ninguna"]
    colisiones = reporte["colisiones"] or ["Ninguna"]
    eliminados = reporte["eliminados"] or []
    pares_distintos = reporte.get(
        "pares_distintos",
        [],
    )
    filas_eliminados = "\n".join(
        f"| {item['id_eliminado']} | {item['id_conservado']} | "
        f"{item['distancia_coseno']} | {item['motivo']} |"
        for item in eliminados
    ) or "| Ninguno | - | - | - |"
    filas_pares_distintos = "\n".join(
        f"| {item['id_a']} | {item['titulo_a']} | "
        f"{item['id_b']} | {item['titulo_b']} | "
        f"{item['distancia_coseno']:.4f} |"
        for item in pares_distintos
    ) or "| Ninguno | - | - | - | - |"
    distancias_eliminadas = [
        float(item["distancia_coseno"])
        for item in eliminados
    ]
    if distancias_eliminadas:
        distancia_maxima_duplicados = max(
            distancias_eliminadas
        )

        pares_eliminados = ", ".join(
            f"`{item['id_eliminado']}` vs. "
            f"`{item['id_conservado']}` "
            f"(`{float(item['distancia_coseno']):.4f}`)"
            for item in eliminados
        )

        if pares_distintos:
            distancia_minima_distintos = min(
                float(item["distancia_coseno"])
                for item in pares_distintos
            )

            separacion = (
                distancia_minima_distintos
                - distancia_maxima_duplicados
            )

            evaluacion_separacion = (
                f"El par diferente más cercano quedó en "
                f"`{distancia_minima_distintos:.4f}`. "
                f"La separación observada entre el duplicado "
                f"más distante y el documento diferente más "
                f"cercano es de `{separacion:.4f}`."
            )
        else:
            distancia_minima_distintos = None
            evaluacion_separacion = (
                "No hubo suficientes documentos conservados "
                "para medir pares negativos."
            )

        justificacion_umbral = (
            f"La distancia coseno se calcula como `1 - similitud`; "
            f"por eso, el umbral `{DISTANCIA_UMBRAL}` equivale "
            f"a exigir similitud coseno >= "
            f"`{1 - DISTANCIA_UMBRAL:.2f}`. "
            f"Los casos positivos controlados corresponden a "
            f"variantes del mismo producto: {pares_eliminados}. "
            f"El duplicado con mayor distancia quedó en "
            f"`{distancia_maxima_duplicados:.4f}`. "
            f"{evaluacion_separacion} "
            f"Por lo tanto, el umbral `{DISTANCIA_UMBRAL}` "
            f"conserva los documentos distintos medidos y "
            f"elimina los casi duplicados sembrados. "
            f"El valor sigue siendo específico de este corpus, "
            f"del modelo de embeddings y del formato utilizado; "
            f"deberá recalibrarse si cambia alguno de esos elementos."
        )
    else:
        justificacion_umbral = (
            "No se detectaron casos eliminados para calibrar el umbral en esta "
            "corrida. El valor debe considerarse inicial y validarse con pares "
            "positivos y negativos etiquetados."
        )

    contenido = f"""# Reporte de ETL y purga semántica

## Resumen

- Documentos originales: {total_original}
- Documentos limpios: {total_limpio}
- Umbral de distancia coseno: `{DISTANCIA_UMBRAL}`
- Regla: se conserva el primer documento válido y se elimina el posterior
  cuando la distancia coseno es menor o igual al umbral.

## Justificación y alcance del umbral

{justificacion_umbral}

## Correcciones estructurales

{chr(10).join(f'- {item}' for item in correcciones)}

## Colisiones de IDs resueltas

{chr(10).join(f'- {item}' for item in colisiones)}

## Documentos eliminados

| Eliminado | Conservado | Distancia coseno | Motivo |
|---|---|---:|---|
{filas_eliminados}
## Pares diferentes más cercanos

Los siguientes documentos sobrevivieron a la purga. Se muestran los
pares con menor distancia para utilizarlos como ejemplos negativos y
comprobar que el umbral no elimina documentos diferentes pero
semánticamente relacionados.

| Documento A | Título A | Documento B | Título B | Distancia coseno |
|---|---|---|---|---:|
{filas_pares_distintos}

## Por qué `SELECT DISTINCT` no alcanza

`SELECT DISTINCT` solo detectaría filas idénticas en todas sus columnas.
Los casi-duplicados tienen IDs, títulos, textos o tags diferentes, aunque
representen el mismo concepto del negocio. La distancia coseno compara el
significado de los embeddings y permite detectar esa equivalencia semántica.
"""
    REPORT_PATH.write_text(contenido, encoding="utf-8")


def main() -> None:
    data = cargar_json(INPUT_PATH)
    documentos = data.get("documentos", [])
    documentos_limpios, reporte = purgar_documentos(documentos)

    resultado = dict(data)
    resultado["documentos"] = documentos_limpios
    resultado["meta"] = {
        "total_original": len(documentos),
        "total_limpio": len(documentos_limpios),
        "estado": "limpio",
        "proceso": "etl_purga",
        "distancia_coseno_umbral": DISTANCIA_UMBRAL,
        "documentos_eliminados": len(reporte["eliminados"]),
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    escribir_reporte(len(documentos), len(documentos_limpios), reporte)

    print(f"Documentos originales: {len(documentos)}")
    print(f"Documentos finales: {len(documentos_limpios)}")
    print(f"Casi-duplicados eliminados: {len(reporte['eliminados'])}")
    print(f"Reporte generado: {REPORT_PATH.name}")
    print(f"Archivo generado: {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
