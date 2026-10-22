from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.exceptions import ModelError

from .rag_pipeline import (
    RAIZ_PROYECTO,
    crear_cadena_rag,
    crear_retriever,
)


DIRECTORIO_ENTREGA = Path(__file__).resolve().parent
RUTA_INFORME = DIRECTORIO_ENTREGA / "informe.md"
MARCADOR_A4 = "\n## A.4 — Trazabilidad de fuentes\n"

CONSULTAS: list[dict[str, str]] = [
    {
        "id": "A4-1",
        "tipo": "Factual directa",
        "consulta": (
            "¿De qué tamaño son los vasos de bagazo y para qué tipo "
            "de bebidas se utilizan?"
        ),
    },
    {
        "id": "A4-2",
        "tipo": "Consulta con sinónimos",
        "consulta": (
            "¿Qué alternativa ofrecen para sorber jugos en un local "
            "gastronómico?"
        ),
    },
]


def _bloque_codigo(texto: str) -> str:
    return "```text\n" + texto.replace("```", "` ` `") + "\n```"


def _formatear_fuente(
    documento: Any,
    posicion: int,
    confirmado_por_chain: bool,
) -> str:
    titulo = documento.metadata.get("titulo", "Sin título")
    metadatos = json.dumps(
        documento.metadata,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    etiqueta_fragmento = (
        "Fragmento utilizado por el chain"
        if confirmado_por_chain
        else (
            "Texto del documento candidato (no se pudo confirmar que "
            "se enviara al generador)"
        )
    )
    return f"""#### Fuente {posicion}: {titulo}

**Metadatos**

{_bloque_codigo(metadatos)}

**{etiqueta_fragmento}**

{_bloque_codigo(documento.page_content)}
"""


def _ejecutar_consultas() -> list[dict[str, Any]]:
    cadena = crear_cadena_rag(cantidad=3)
    retriever = crear_retriever(cantidad=3)
    resultados = []

    for caso in CONSULTAS:
        try:
            salida = cadena.invoke(caso["consulta"])
        except ModelError as error:
            status_code = getattr(error, "status_code", None) or getattr(
                error,
                "code",
                None,
            )
            mensaje = (
                f"Generación bloqueada por el proveedor (HTTP {status_code})."
                if status_code is not None
                else f"Generación bloqueada ({type(error).__name__})."
            )
            resultados.append(
                {
                    **caso,
                    "respuesta": None,
                    "fuentes": retriever.invoke(caso["consulta"]),
                    "fuentes_confirmadas_por_chain": False,
                    "error": mensaje,
                }
            )
        else:
            resultados.append(
                {
                    **caso,
                    "respuesta": salida["answer"],
                    "fuentes": salida["source_documents"],
                    "fuentes_confirmadas_por_chain": True,
                    "error": None,
                }
            )

    return resultados


def _generar_seccion(resultados: list[dict[str, Any]]) -> str:
    load_dotenv(RAIZ_PROYECTO / ".env")
    proveedor = os.getenv("RAG_PROVIDER", "openai")
    modelo = os.getenv(
        "GEMINI_MODEL" if proveedor.lower() == "gemini" else "OPENAI_MODEL",
        "gpt-4o-mini",
    )
    fecha = datetime.now().astimezone().isoformat(timespec="seconds")
    completas = sum(
        resultado["respuesta"] is not None
        and resultado["fuentes_confirmadas_por_chain"]
        for resultado in resultados
    )
    estado = (
        "Completada para las dos consultas."
        if completas == len(resultados)
        else (
            f"Parcial: {completas}/{len(resultados)} consultas completadas; "
            "las restantes se registran como fallidas."
        )
    )
    detalles = []

    for resultado in resultados:
        fuentes = resultado["fuentes"]
        bloques_fuente = (
            "\n".join(
                _formatear_fuente(
                    documento,
                    posicion,
                    confirmado_por_chain=resultado[
                        "fuentes_confirmadas_por_chain"
                    ],
                )
                for posicion, documento in enumerate(fuentes, start=1)
            )
            if fuentes
            else "_El chain no devolvió documentos fuente._"
        )
        respuesta = (
            f"> {resultado['respuesta'].replace(chr(10), chr(10) + '> ')}"
            if resultado["respuesta"]
            else resultado["error"]
        )
        etiqueta_fuente = (
            "Fuentes devueltas por el chain"
            if resultado["fuentes_confirmadas_por_chain"]
            else (
                "Candidatas recuperadas por separado; el chain no alcanzó "
                "a devolver fuentes"
            )
        )
        detalles.append(
            f"""### {resultado['id']} — {resultado['tipo']}

**Consulta:** {resultado['consulta']}

**Respuesta generada:**

{respuesta}

**{etiqueta_fuente}:** {len(fuentes)}

{bloques_fuente}
"""
        )

    return f"""{MARCADOR_A4.strip()}

Intento de ejecución del chain el **{fecha}** con proveedor `{proveedor}` y modelo
`{modelo}`. Estado: **{estado}** El retriever consultó la colección ChromaDB
`ecologix` con `k=3`.
Cada fragmento se muestra completo tal como fue recuperado y pasado al prompt;
los metadatos se copian del documento fuente devuelto por el chain.

{chr(10).join(detalles)}
"""


def _guardar_seccion(seccion: str) -> None:
    informe_actual = (
        RUTA_INFORME.read_text(encoding="utf-8")
        if RUTA_INFORME.exists()
        else "# Informe de Entrega 3\n"
    )
    inicio_a4 = informe_actual.find(MARCADOR_A4)
    if inicio_a4 >= 0:
        informe_actual = informe_actual[:inicio_a4].rstrip() + "\n"

    RUTA_INFORME.write_text(
        informe_actual.rstrip() + "\n\n" + seccion,
        encoding="utf-8",
    )


def main() -> None:
    resultados = _ejecutar_consultas()
    seccion = _generar_seccion(resultados)
    _guardar_seccion(seccion)
    print(f"Sección A.4 escrita en: {RUTA_INFORME}")
    consultas_completas = sum(
        resultado["respuesta"] is not None
        and resultado["fuentes_confirmadas_por_chain"]
        for resultado in resultados
    )
    print(
        f"Consultas registradas: {consultas_completas}/{len(resultados)} "
        "completas"
    )
    print(
        "Fuentes registradas: "
        f"{sum(len(resultado['fuentes']) for resultado in resultados)}"
    )
    if consultas_completas != len(resultados):
        raise RuntimeError(
            "A.4 se registró parcialmente; revisar errores en "
            f"{RUTA_INFORME} y volver a ejecutar las consultas pendientes."
        )


if __name__ == "__main__":
    main()
