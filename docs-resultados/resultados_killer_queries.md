# Killer Queries — EcoLogix (Entrega 2, B.6)

Tres consultas trampa ejecutadas contra la colección ChromaDB
(`ecologix`, espacio `cosine`, embeddings locales
`paraphrase-multilingual-MiniLM-L12-v2`). Umbral de aceptación
definido: **0.35** (ver justificación al final).

## Tabla consolidada B.6

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
|---:|---|---|---|---|---|
| 1 | Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje | Poder semántico | `doc-005` primero y por encima de `0.35` | `doc-005` (0.585) | Sí |
| 2 | Necesito sorbetes para mi kiosco, que esten disponibles en stock | Filtro híbrido de categoría y estado | Con `categoria=sorbetes AND activo=true`, `doc-019` primero | Sin filtro: `doc-001` (0.432); con filtro: `doc-019` (0.4277) | Sí |
| 3 | Venden celulares o accesorios de telefonia? | Rechazo de consultas fuera del catálogo | No aceptar un resultado irrelevante | Con el umbral 0.35 el sistema devuelve `doc-013` (0.4874) (ancla 0.3345) | No (hallazgo documentado) |


## 1 — Poder semántico: jerga sin palabras exactas del documento

**Qué pone a prueba:** que la búsqueda entienda significado y no
coincidencia literal. La consulta no usa ninguna de las palabras
"cartón", "delivery" ni "catering" que sí aparecen en el texto de
`doc-005`.

> Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje

**Resultado esperado:** `doc-005` (Envases de cartón para alimentos)
en el primer puesto, por encima del umbral.

**Resultado real:**

1. `doc-005` Envases de cartón para alimentos — similitud: 0.585
2. `doc-003` Platos y bowls de bagazo — similitud: 0.5403
3. `doc-004` Sorbetes de papel — similitud: 0.4812
4. `doc-019` Vasos compostables para cafe — similitud: 0.4416
5. `doc-001` Bolsas compostables 40x50 cm — similitud: 0.4132

**¿Pasó?** Sí — `doc-005` (Envases de cartón para alimentos) supera el umbral (0.585 ≥ 0.35) → se acepta como resultado.

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

> Necesito sorbetes para mi kiosco, que esten disponibles en stock

**Resultado esperado:** sin filtro, `doc-019` queda mezclado (o
directamente superado) por productos de otras categorías; con el
filtro nativo `where={"categoria": "sorbetes", "activo": true}`,
sólo queda `doc-019` — el único sorbete activo — al frente del
resultado.

**Resultado real (sin filtro):**

1. `doc-001` Bolsas compostables 40x50 cm — similitud: 0.432
2. `doc-002` Vasos de bagazo 12 oz — similitud: 0.4297
3. `doc-013` Bolsas de papel kraft para comercio — similitud: 0.4278
4. `doc-019` Sorbetes compostables de bagazo — similitud: 0.4277
5. `doc-005` Envases de cartón para alimentos — similitud: 0.4003

**Resultado real (con filtro nativo `categoria=sorbetes AND activo=true`):**

1. `doc-019` Sorbetes compostables de bagazo — similitud: 0.4277

**¿Pasó?** Sí

## 3 — Prueba de estrés: consulta fuera de catálogo

**Qué pone a prueba:** que el sistema no fuerce un resultado cuando
no hay nada relevante en el catálogo. Esta consulta se eligió
deliberadamente por compartir vocabulario comercial genérico
("comercio", "accesorios") con documentos reales del corpus, para
forzar el caso más difícil en vez de uno obviamente irrelevante.

> Venden celulares o accesorios de telefonia?

**Resultado esperado:** ningún documento debería superar el umbral
de aceptación — EcoLogix no vende celulares ni accesorios de
telefonía.

**Resultado real:**

1. `doc-013` Bolsas de papel kraft para comercio — similitud: 0.4874
2. `doc-001` Bolsas compostables 40x50 cm — similitud: 0.3699
3. `doc-017` Jerga comercial del dominio — similitud: 0.2961
4. `doc-005` Envases de cartón para alimentos — similitud: 0.2837
5. `doc-014` Cubiertos y utensilios de bioplástico — similitud: 0.2794

**¿Pasó?** No (hallazgo documentado)

**Hallazgo:** el resultado con mayor similitud (`doc-013`,
0.4874) **supera** el umbral definido
(0.35), a pesar de ser completamente irrelevante al
pedido. La causa es semántica: el corpus es chico y varios textos
comparten vocabulario comercial genérico ("comercio", "accesorios",
"clientes"), así que la consulta aterriza cerca de un producto de
otra familia. Forzar ese resultado como respuesta sería alucinación.

**Por qué se quitó el filtro de palabras.** Antes esta consulta
devolvía "no tengo esa información" por un portero que exigía
vocabulario del dominio. Se midió su comportamiento y no resolvía el
problema: tapaba la KQ3 y además rechazaba consultas legítimas del
propio negocio. Con 8 consultas válidas de EcoLogix, el portero
rechazó 7, entre ellas:

| Consulta válida | Similitud real | Portero |
|---|---:|---|
| "hay algo para servir café para llevar?" | 0.5328 (`doc-002`) | la rechazaba (el acento de "café" no matchea "cafe") |
| "necesito unos pots" | 0.4401 (`doc-003`) | la rechazaba |
| "necesito algo para takeaway" | 0.3799 (`doc-003`) | la rechazaba, aunque "takeaway" está en `doc-002` |
| "tengo un pedido en curso, como va?" | 0.4760 (`doc-016`) | la rechazaba |
| "me llegaron unos paquetes rotos, quiero reclamar" | 0.3868 (`doc-012`) | la rechazaba |

En el otro extremo, el portero solo frenaba 2 de 6 consultas fuera de
catálogo, y esas dos quedan ahora como falso positivo conocido del
umbral: "venden notebooks y laptops" (0.4319) y "busco contratos de
alquiler" (0.4132). El balance —7 consultas legítimas tapadas por 2
falsos positivos frenados— es la razón del cambio.

**Lo que decide ahora.** Todo filtro duro viaja dentro del `where` de
ChromaDB (`tipo`, `categoria`, `activo`); no queda post-filtering en
Python. La aceptación la decide únicamente el umbral semántico
(0.35). Cada resultado reporta además
`similitud_ancla`: la cercanía de la consulta al centroide del corpus.
Para esta consulta da 0.3345, la más
baja entre las consultas reales del dominio medidas, lo que confirma
el diagnóstico sin tapar el veredicto. Queda anotado como límite
conocido del corpus y del modelo para la Entrega 3, en la misma línea
que los umbrales de confianza de la Entrega 1.

## Umbral de aceptación — justificación

Sobre este corpus y este modelo de embeddings, las consultas
genuinamente relevantes recuperan su mejor documento con similitud
≥ 0.39 (ver killer query 1, y los resultados de
`resultados_evento_caliente.md`), mientras que consultas
claramente fuera de dominio (notebooks, neumáticos, fletes) quedan
por debajo de 0.30 en la mayoría de los casos. Se definió
**0.35** como punto intermedio. La killer query 3
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
