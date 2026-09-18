# Killer Queries — EcoLogix (Entrega 2, C.3)

Tres consultas trampa ejecutadas contra la colección ChromaDB
(`ecologix`, espacio `cosine`, embeddings locales
`paraphrase-multilingual-MiniLM-L12-v2`). Umbral de aceptación
definido: **0.35** (ver justificación al final).

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

**Resultado real (con filtro nativo `activo=true`):**

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
pedido. El corpus es chico (18 documentos) y varios textos comparten
vocabulario comercial genérico ("comercio", "premium", "accesorios",
"clientes"), lo que hace que un embedding semántico local pueda
generar falsos positivos con consultas cortas y vagas. Forzar el
resultado más cercano en este caso sería alucinación.

**Mitigación aplicada:** `vector_db.py` incorpora la regla de C.2 en
`BaseVectorial.buscar(...)`: la consulta debe tener vocabulario del
dominio EcoLogix y el mejor resultado debe superar el umbral de
aceptación `0.35`. Si la consulta parece fuera de dominio o si ningún
resultado alcanza el umbral, el sistema devuelve una lista vacía y
responde `no tengo esa información` en lugar de forzar el vecino más
cercano. Además, el filtro `where` nativo sigue siendo la capa
adecuada para validar `categoria` y `activo` antes de aceptar la
respuesta. Queda anotado como límite conocido del corpus y del modelo
para la Entrega 3, en la misma línea que los umbrales de confianza de
la Entrega 1 (revalidar con uso real).

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
