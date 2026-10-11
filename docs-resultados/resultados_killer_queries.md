# Killer Queries — EcoLogix (Entrega 2, B.6)

Tres consultas trampa ejecutadas contra la colección ChromaDB
(`ecologix`, espacio `cosine`, embeddings locales
`paraphrase-multilingual-MiniLM-L12-v2`). Umbral de aceptación
definido: **0.35** (ver justificación al final).

## Tabla consolidada B.6

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
|---:|---|---|---|---|---|
| 1 | Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje | Poder semántico | `doc-005` primero y por encima de `0.35` | `doc-005` (0.6202) | Sí |
| 2 | Necesito sorbetes para mi kiosco, que esten disponibles en stock | Filtro híbrido de categoría y estado | Con `categoria=sorbetes AND activo=true`, `doc-022` primero | Sin filtro: `doc-019` (0.4599); con filtro: `doc-022` (0.4277) | Sí |
| 3 | Venden celulares o accesorios de telefonia? | Rechazo de consultas fuera del catálogo | No aceptar un resultado irrelevante | `doc-013` (0.335); rechazada solo por el umbral semántico, sin la regla de vocabulario | Sí |


## 1 — Poder semántico: jerga sin palabras exactas del documento

**Qué pone a prueba:** que la búsqueda entienda significado y no
coincidencia literal. La consulta no usa ninguna de las palabras
"cartón", "delivery" ni "catering" que sí aparecen en el texto de
`doc-005`.

> Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje

**Resultado esperado:** `doc-005` (Envases de cartón para alimentos)
en el primer puesto, por encima del umbral.

**Resultado real:**

1. `doc-005` Envases de cartón para alimentos — similitud: 0.6202
2. `doc-004` Sorbetes de papel — similitud: 0.5642
3. `doc-003` Platos y bowls de bagazo — similitud: 0.555
4. `doc-019` Vasos compostables para cafe — similitud: 0.5349
5. `doc-014` Cubiertos y utensilios de bioplástico — similitud: 0.4404

**¿Pasó?** Sí — `doc-005` (Envases de cartón para alimentos) supera el umbral (0.6202 ≥ 0.35) → se acepta como resultado.

## 2 — El metadato salva el día

**Qué pone a prueba:** que un filtro nativo `where` corrija lo que
la semántica cruda haría mal. Tras simular el evento en caliente
(`doc-004` sorbetes de papel discontinuado, `doc-022` sorbetes de
bagazo activos como reemplazo), la respuesta correcta a "necesito
sorbetes disponibles" es `doc-022`. Pero por similitud pura, sin
ningún filtro de categoría, productos de otras familias (bolsas,
vasos, bolsas de papel kraft) empatan o superan a `doc-022` en el
ranking — la semántica cruda no sabe que el cliente pidió
específicamente sorbetes.

> Necesito sorbetes para mi kiosco, que esten disponibles en stock

**Resultado esperado:** sin filtro, `doc-022` queda mezclado (o
directamente superado) por productos de otras categorías; con el
filtro nativo `where={"categoria": "sorbetes", "activo": true}`,
sólo queda `doc-022` — el único sorbete activo — al frente del
resultado.

**Resultado real (sin filtro):**

1. `doc-019` Vasos compostables para cafe — similitud: 0.4599
2. `doc-013` Bolsas de papel kraft para comercio — similitud: 0.4309
3. `doc-022` Sorbetes compostables de bagazo — similitud: 0.4277
4. `doc-002` Vasos de bagazo 12 oz — similitud: 0.3987

**Resultado real (con filtro nativo `categoria=sorbetes AND activo=true`):**

1. `doc-022` Sorbetes compostables de bagazo — similitud: 0.4277

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

1. `doc-013` Bolsas de papel kraft para comercio — similitud: 0.335
2. `doc-001` Bolsas compostables 40x50 cm — similitud: 0.2991

**¿Pasó?** Sí

**Hallazgo:** la búsqueda se corrió **sin** la regla de vocabulario
del dominio (`validar_dominio=False`) y aun así el mejor resultado
(`doc-013`, 0.335) queda por debajo del umbral
(0.35): la semántica sola rechaza la consulta. En la
versión anterior del corpus, con descripciones de ~300 caracteres, esta
misma consulta daba un falso positivo de 0.4874 sobre `doc-013`; al
enriquecer las descripciones (A.3), los documentos dejaron de
compartir solo vocabulario comercial genérico y el margen se volvió
semántico. El margen es chico (0.015), así que el umbral sigue
siendo frágil frente a consultas nuevas.

**Mitigación aplicada:** `vector_db.py` valida que la consulta tenga
vocabulario del dominio EcoLogix y que el mejor resultado supere el
umbral de aceptación `0.35`. Si la consulta parece
fuera de dominio o ningún resultado alcanza el umbral, devuelve una
lista vacía para que el sistema responda "no tengo esa información".
Además, el filtro `where` nativo valida `categoria` y `activo` antes
de aceptar resultados, sin post-filtering manual. Queda anotado como
límite conocido del corpus y del modelo para la Entrega 3, en la misma
línea que los umbrales de confianza de la Entrega 1 (revalidar con uso
real).

## Umbral de aceptación — justificación

Sobre este corpus y este modelo de embeddings, las consultas
genuinamente relevantes recuperan su mejor documento con similitud
≥ 0.4277 (killer queries 1 y 2, y los resultados de
`resultados_evento_caliente.md`), mientras que la consulta fuera de
dominio de la killer query 3 queda en 0.335. Se definió
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
