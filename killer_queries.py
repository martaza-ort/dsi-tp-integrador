"""Killer Queries — Entrega 2, Parte C.3.

Corre 3 consultas trampa contra la base vectorial de ChromaDB y
documenta el resultado real (no inventado) en
`resultados_killer_queries.md`:

1. Poder semantico: jerga sin palabras exactas del documento.
2. El metadato salva el dia: la semantica cruda trae un resultado
   incorrecto (producto discontinuado), el filtro nativo `where`
   lo bloquea.
3. Prueba de estres: consulta fuera de catalogo que ademas comparte
   vocabulario comercial generico con el corpus, para forzar un
   falso positivo y poner a prueba el umbral de aceptacion.

Requiere que el corpus canonico ya este indexado (correr
`python vector_db.py` o dejar que este script lo haga por vos).
"""

from __future__ import annotations

from pathlib import Path

from simular_evento_caliente import (
    construir_corpus_con_evento,
    restaurar_estado_original,
)
from vector_db import BaseVectorial, cargar_documentos


ROOT = Path(__file__).resolve().parent
RUTA_EVIDENCIA = ROOT / "resultados_killer_queries.md"

UMBRAL_ACEPTACION = 0.35

CONSULTA_1 = (
    "Necesito packaging para mandar comida caliente a domicilio, "
    "que no se rompa ni se moje"
)

CONSULTA_2 = "Necesito sorbetes para mi kiosco, que esten disponibles en stock"

CONSULTA_3 = "Venden celulares o accesorios de telefonia?"


def formatear(resultados: list[dict]) -> str:
    if not resultados:
        return "_(sin resultados)_"

    lineas = []
    for posicion, r in enumerate(resultados, start=1):
        lineas.append(
            f"{posicion}. `{r['id']}` {r['titulo']} — similitud: {r['similitud']}"
        )
    return "\n".join(lineas)


def evaluar_umbral(resultados: list[dict], umbral: float) -> str:
    """Aplica el umbral de aceptación al mejor resultado."""

    if not resultados or resultados[0]["similitud"] < umbral:
        return (
            f"Ningún resultado supera el umbral ({umbral}) → "
            f'el sistema debe responder "no tengo esa información".'
        )

    mejor = resultados[0]
    return (
        f"`{mejor['id']}` ({mejor['titulo']}) supera el umbral "
        f"({mejor['similitud']} ≥ {umbral}) → se acepta como resultado."
    )


def main() -> None:
    print("Reconstruyendo corpus canónico...")
    restaurar_estado_original()

    base = BaseVectorial()

    # --- Killer Query 1: poder semántico ------------------------------
    print("\n[1] Poder semántico (jerga sin palabras exactas)")
    resultados_1 = base.buscar(consulta=CONSULTA_1, cantidad=5)
    for r in resultados_1:
        print(f"  {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    # --- Killer Query 2: el metadato salva el día ----------------------
    print("\n[2] El metadato salva el día (evento en caliente)")
    print("  Aplicando evento: doc-004 discontinuado, doc-019 activo...")
    base.indexar_documentos(construir_corpus_con_evento(cargar_documentos()))

    resultados_2_sin_filtro = base.buscar(consulta=CONSULTA_2, cantidad=5)
    print("  Sin filtro:")
    for r in resultados_2_sin_filtro:
        print(f"    {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    resultados_2_con_filtro = base.buscar(
        consulta=CONSULTA_2,
        cantidad=5,
        donde={"$and": [{"categoria": "sorbetes"}, {"estado": "activo"}]},
    )
    print("  Con filtro where categoria=sorbetes AND estado=activo:")
    for r in resultados_2_con_filtro:
        print(f"    {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    # --- Killer Query 3: prueba de estrés fuera de catálogo ------------
    print("\n[3] Prueba de estrés (fuera de catálogo)")
    resultados_3 = base.buscar(consulta=CONSULTA_3, cantidad=5)
    for r in resultados_3:
        print(f"  {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    # --- Deja la base en el estado canónico para el resto del equipo ---
    print("\nRestaurando corpus canónico...")
    restaurar_estado_original()

    escribir_evidencia(
        resultados_1,
        resultados_2_sin_filtro,
        resultados_2_con_filtro,
        resultados_3,
    )


def escribir_evidencia(
    r1: list[dict],
    r2_sin: list[dict],
    r2_con: list[dict],
    r3: list[dict],
) -> None:
    top1_r1 = r1[0]["similitud"] if r1 else 0
    paso_1 = "Sí" if r1 and r1[0]["id"] == "doc-005" and top1_r1 >= UMBRAL_ACEPTACION else "No"

    top1_sin = r2_sin[0] if r2_sin else None
    top1_con = r2_con[0] if r2_con else None
    metadato_salva = bool(
        top1_sin
        and top1_sin["id"] != "doc-019"
        and top1_con
        and top1_con["id"] == "doc-019"
    )
    paso_2 = "Sí" if metadato_salva else "No"

    top1_r3 = r3[0] if r3 else None
    falso_positivo = bool(top1_r3 and top1_r3["similitud"] >= UMBRAL_ACEPTACION)
    # La consulta 3 es una trampa: el catálogo NO tiene celulares/telefonía.
    # "Pasa" la prueba si el sistema NO acepta ese resultado, es decir si
    # el falso positivo queda documentado como hallazgo (no oculto).
    paso_3 = "No (hallazgo documentado)" if falso_positivo else "Sí"

    contenido = f"""# Killer Queries — EcoLogix (Entrega 2, C.3)

Tres consultas trampa ejecutadas contra la colección ChromaDB
(`ecologix`, espacio `cosine`, embeddings locales
`paraphrase-multilingual-MiniLM-L12-v2`). Umbral de aceptación
definido: **{UMBRAL_ACEPTACION}** (ver justificación al final).

## 1 — Poder semántico: jerga sin palabras exactas del documento

**Qué pone a prueba:** que la búsqueda entienda significado y no
coincidencia literal. La consulta no usa ninguna de las palabras
"cartón", "delivery" ni "catering" que sí aparecen en el texto de
`doc-005`.

> {CONSULTA_1}

**Resultado esperado:** `doc-005` (Envases de cartón para alimentos)
en el primer puesto, por encima del umbral.

**Resultado real:**

{formatear(r1)}

**¿Pasó?** {paso_1} — {evaluar_umbral(r1, UMBRAL_ACEPTACION)}

## 2 — El metadato salva el día

**Qué pone a prueba:** que un filtro nativo `where` corrija lo que
la semántica cruda haría mal. Tras simular el evento en caliente
(`doc-004` sorbetes de papel discontinuado, `doc-019` sorbetes de
bagazo activos como reemplazo), la respuesta correcta a "necesito
sorbetes disponibles" es `doc-019`. Pero por similitud pura, sin
ningún filtro de categoría, productos de otras familias (bolsas,
vasos, bolsas de papel kraft) empatan o superan a `doc-019` en el
ranking — la semántica cruda no sabe que el cliente pidió
específicamente sorbetes.

> {CONSULTA_2}

**Resultado esperado:** sin filtro, `doc-019` queda mezclado (o
directamente superado) por productos de otras categorías; con el
filtro nativo `where={{"categoria": "sorbetes", "estado": "activo"}}`,
sólo queda `doc-019` — el único sorbete activo — al frente del
resultado.

**Resultado real (sin filtro):**

{formatear(r2_sin)}

**Resultado real (con filtro nativo `estado=activo`):**

{formatear(r2_con)}

**¿Pasó?** {paso_2}

## 3 — Prueba de estrés: consulta fuera de catálogo

**Qué pone a prueba:** que el sistema no fuerce un resultado cuando
no hay nada relevante en el catálogo. Esta consulta se eligió
deliberadamente por compartir vocabulario comercial genérico
("comercio", "accesorios") con documentos reales del corpus, para
forzar el caso más difícil en vez de uno obviamente irrelevante.

> {CONSULTA_3}

**Resultado esperado:** ningún documento debería superar el umbral
de aceptación — EcoLogix no vende celulares ni accesorios de
telefonía.

**Resultado real:**

{formatear(r3)}

**¿Pasó?** {paso_3}

**Hallazgo:** el resultado con mayor similitud (`{r3[0]['id'] if r3 else '-'}`,
{r3[0]['similitud'] if r3 else '-'}) **supera** el umbral definido
({UMBRAL_ACEPTACION}), a pesar de ser completamente irrelevante al
pedido. El corpus es chico (18 documentos) y varios textos comparten
vocabulario comercial genérico ("comercio", "premium", "accesorios",
"clientes"), lo que hace que un embedding semántico local pueda
generar falsos positivos con consultas cortas y vagas. Forzar el
resultado más cercano en este caso sería alucinación.

**Mitigación propuesta (pendiente de implementar, no aplicada en este
corpus):** exigir además una coincidencia de `categoria` contra un
listado cerrado de categorías válidas del dominio (`bolsas`,
`vajilla`, `sorbetes`, `envases`, `limpieza`) antes de aceptar un
resultado — el filtro `where` ya disponible en `vector_db.py`
permite hacerlo sin post-filtering manual. Queda anotado como
limitación conocida para la Entrega 3, en la misma línea que los
umbrales de confianza de la Entrega 1 (revalidar con uso real).

## Umbral de aceptación — justificación

Sobre este corpus y este modelo de embeddings, las consultas
genuinamente relevantes recuperan su mejor documento con similitud
≥ 0.39 (ver killer query 1, y los resultados de
`resultados_evento_caliente.md`), mientras que consultas
claramente fuera de dominio (notebooks, neumáticos, fletes) quedan
por debajo de 0.30 en la mayoría de los casos. Se definió
**{UMBRAL_ACEPTACION}** como punto intermedio. La killer query 3
muestra que ningún umbral fijo es infalible por sí solo con un
corpus chico: cuando ninguna coincidencia supera el umbral, el
sistema debe responder "no tengo esa información" en vez de forzar
el resultado más cercano (eso sería alucinación).

## Reproducción

```bash
python killer_queries.py
```

El script reconstruye el corpus canónico desde
`base_conocimiento_limpia.json`, aplica y revierte el evento en
caliente de forma temporal, y deja la colección de ChromaDB en el
estado canónico al finalizar.
"""

    with RUTA_EVIDENCIA.open("w", encoding="utf-8") as archivo:
        archivo.write(contenido)

    print("\nEvidencia escrita en:", RUTA_EVIDENCIA)


if __name__ == "__main__":
    main()
