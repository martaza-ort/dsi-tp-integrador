"""Killer Queries — Entrega 2, Parte B.6.

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
from vector_db import (
    BaseVectorial,
    UMBRAL_MARGEN_DOMINIO,
    cargar_documentos,
    evaluar_dominio,
    similitud_ancla,
)


ROOT = Path(__file__).resolve().parent
RUTA_EVIDENCIA = ROOT / "docs-resultados" / "resultados_killer_queries.md"

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


def resumen_resultado(resultado: list[dict], cantidad: int = 1) -> str:
    if not resultado:
        return "Sin resultados"

    mejores = resultado[:cantidad]
    return "; ".join(
        f"`{item['id']}` ({item['similitud']})" for item in mejores
    )


def main() -> None:
    print("Reconstruyendo corpus canónico...")
    restaurar_estado_original()

    base = BaseVectorial()

    # --- Killer Query 1: poder semántico ------------------------------
    print("\n[1] Poder semántico (jerga sin palabras exactas)")
    resultados_1 = base.buscar_ecologix(
        query_semantica=CONSULTA_1,
        solo_activos=True,
        n_resultados=5,
    )
    for r in resultados_1:
        print(f"  {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    # --- Killer Query 2: el metadato salva el día ----------------------
    print("\n[2] El metadato salva el día (evento en caliente)")
    print("  Aplicando evento: doc-004 discontinuado, doc-019 activo...")
    base.indexar_documentos(construir_corpus_con_evento(cargar_documentos()))

    resultados_2_sin_filtro = base.buscar(
        consulta=CONSULTA_2,
        cantidad=5,
        umbral=0.0,
    )
    print("  Sin filtro:")
    for r in resultados_2_sin_filtro:
        print(f"    {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    resultados_2_con_filtro = base.buscar_ecologix(
        query_semantica=CONSULTA_2,
        filtro_x={"categoria": {"$eq": "sorbetes"}},
        solo_activos=True,
        n_resultados=5,
    )
    print("  Con filtro where categoria=sorbetes AND activo=true:")
    for r in resultados_2_con_filtro:
        print(f"    {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    # --- Killer Query 3: prueba de estrés fuera de catálogo ------------
    print("\n[3] Prueba de estrés (fuera de catálogo)")
    print("  similitud_ancla:", round(similitud_ancla(CONSULTA_3), 4))

    diagnostico_3 = evaluar_dominio(CONSULTA_3)
    print("  diagnóstico de dominio:", diagnostico_3)

    # Ranking crudo: se conserva para demostrar el falso positivo que
    # produciría la similitud vectorial si actuara sin control de dominio.
    resultados_3 = base.buscar(
        consulta=CONSULTA_3,
        cantidad=5,
        umbral=0.0,
        validar_dominio=False,
    )
    print("  Ranking crudo sin validación de dominio:")
    for r in resultados_3:
        print(f"    {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    # Respuesta final: aplica tanto el umbral del resultado como la
    # validación semántica del dominio implementada en vector_db.py.
    resultados_3_aceptados = base.buscar(
        consulta=CONSULTA_3,
        cantidad=5,
        umbral=UMBRAL_ACEPTACION,
    )
    print("  Resultados aceptados por el sistema:")
    for r in resultados_3_aceptados:
        print(f"    {r['id']} {r['titulo']} - similitud: {r['similitud']}")

    if not resultados_3_aceptados:
        print('    Sin resultados: responder "no tengo esa información".')

    # --- Deja la base en el estado canónico para el resto del equipo ---
    print("\nRestaurando corpus canónico...")
    restaurar_estado_original()

    escribir_evidencia(
        resultados_1,
        resultados_2_sin_filtro,
        resultados_2_con_filtro,
        resultados_3,
        resultados_3_aceptados,
        diagnostico_3,
    )


def escribir_evidencia(
    r1: list[dict],
    r2_sin: list[dict],
    r2_con: list[dict],
    r3: list[dict],
    r3_aceptados: list[dict],
    diagnostico_3: dict,
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

    dominio_rechazado = not diagnostico_3["aceptada"]
    paso_3 = "Sí" if dominio_rechazado and not r3_aceptados else "No"

    tabla_b6 = f"""## Tabla consolidada B.6

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
|---:|---|---|---|---|---|
| 1 | {CONSULTA_1} | Poder semántico | `doc-005` primero y por encima de `{UMBRAL_ACEPTACION}` | {resumen_resultado(r1)} | {paso_1} |
| 2 | {CONSULTA_2} | Filtro híbrido de categoría y estado | Con `categoria=sorbetes AND activo=true`, `doc-019` primero | Sin filtro: {resumen_resultado(r2_sin)}; con filtro: {resumen_resultado(r2_con)} | {paso_2} |
| 3 | {CONSULTA_3} | Rechazo de consultas fuera del catálogo | No aceptar un resultado irrelevante | Ranking crudo: {resumen_resultado(r3)}; respuesta final: {resumen_resultado(r3_aceptados)}; margen de dominio: {diagnostico_3['margen_dominio']} | {paso_3} |
"""

    contenido = f"""# Killer Queries — EcoLogix (Entrega 2, B.6)

Tres consultas trampa ejecutadas contra la colección ChromaDB
(`ecologix`, espacio `cosine`, embeddings locales
`paraphrase-multilingual-MiniLM-L12-v2`). Umbral de aceptación
definido: **{UMBRAL_ACEPTACION}** (ver justificación al final).

{tabla_b6}

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
filtro nativo `where={{"categoria": "sorbetes", "activo": true}}`,
sólo queda `doc-019` — el único sorbete activo — al frente del
resultado.

**Resultado real (sin filtro):**

{formatear(r2_sin)}

**Resultado real (con filtro nativo `categoria=sorbetes AND activo=true`):**

{formatear(r2_con)}

**¿Pasó?** {paso_2}

## 3 — Prueba de estrés: consulta fuera de catálogo

**Qué pone a prueba:** que el sistema no fuerce un resultado cuando
no hay nada relevante en el catálogo. Esta consulta se eligió
deliberadamente por compartir vocabulario comercial genérico
("comercio", "accesorios") con documentos reales del corpus, para
forzar el caso más difícil en vez de uno obviamente irrelevante.

> {CONSULTA_3}

**Resultado esperado:** el sistema debe rechazar la consulta porque
EcoLogix no vende celulares ni accesorios de telefonía, aunque el
ranking vectorial crudo encuentre algún documento cercano.

**Ranking vectorial crudo, con la validación de dominio desactivada
únicamente para mostrar la trampa:**

{formatear(r3)}

**Diagnóstico semántico del dominio:** similitud con ejemplos de
EcoLogix `{diagnostico_3['similitud_dominio']}`, similitud con ejemplos
ajenos `{diagnostico_3['similitud_fuera']}` y margen
`{diagnostico_3['margen_dominio']}`. Como el margen es inferior al
mínimo `{UMBRAL_MARGEN_DOMINIO}`, la consulta se rechaza.

**Respuesta final del sistema:** {resumen_resultado(r3_aceptados)}.
Debe responder "no tengo esa información".

**¿Pasó?** {paso_3}

La decisión no usa palabras clave. Compara el embedding de la consulta
con ejemplos semánticos válidos de EcoLogix y con ejemplos de dominios
ajenos. Esto evita aceptar el falso positivo del ranking crudo sin
rechazar consultas legítimas como pedidos, reclamos o seguimiento.

## Umbral de aceptación — justificación

Sobre este corpus y este modelo de embeddings, las consultas
genuinamente relevantes recuperan su mejor documento con similitud
≥ 0.39 (ver killer query 1, y los resultados de
`resultados_evento_caliente.md`), mientras que consultas
claramente fuera de dominio (notebooks, neumáticos, fletes) quedan
por debajo de 0.30 en la mayoría de los casos. Se definió
**{UMBRAL_ACEPTACION}** como punto intermedio. La killer query 3
muestra que este umbral no alcanza por sí solo con un corpus chico.
Por eso se complementa con un margen de dominio de
**{UMBRAL_MARGEN_DOMINIO}**: la consulta debe parecerse más a ejemplos
de EcoLogix que a ejemplos ajenos antes de aceptar cualquier documento.

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
