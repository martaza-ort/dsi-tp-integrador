# TP Integrador — Entrega 2: Del Prompt Saturado a la Base de Conocimiento Vectorial

**Dominio:** EcoLogix Systems (el mismo de la Entrega 1).

- Marta Artaza (`martaza-ort`) — `base_conocimiento.json`, `etl_purga.py`
- Lucía López Guerrero (`LuciaLG1988`) — similitud coseno, índice FAISS, `pipeline_vectorial.py`
- Facundo Folgueira (`Folguee`) — ChromaDB, filtros nativos, evento en caliente
- Agustina Salatino (`agustinasalatino`) — `killer_queries.py`, `docs-resultados/resultados_killer_queries.md`
- Gisella Aramayo (`giaramayo`) — este informe, cierre del repo

---

## Parte A — Embeddings y Búsqueda Semántica

**A.1 — Los tres problemas.** Meter los 22 registros sucios del catálogo en cada prompt cuesta más tokens que el corpus original de 18 documentos; recuperando solo los más relevantes por similitud se evita enviar documentos irrelevantes en cada consulta. *Lost in the Middle*: el modelo presta menos atención a lo que queda en el medio de un bloque largo. *Estado concurrente*: stock, discontinuados y reemplazos cambian en vivo; el evento de B.3 lo demuestra sin modificar ningún prompt. Un `LIKE '%...%'` tampoco alcanza porque matchea texto literal, no significado, y no rankea por relevancia.

**A.2 — Similitud coseno a mano.** Dos ejes: X=afinidad con bebidas, Y=afinidad con empaque seco. Consulta "vaso para café caliente" → Q=(0,8; 0,2); vasos de bagazo A=(0,9; 0,1). Paso a paso: producto punto `0,8×0,9 + 0,2×0,1 = 0,74`; normas `‖Q‖≈0,8246`, `‖A‖≈0,9055`; división `0,74/(0,8246×0,9055) ≈ 0,991`. Igual con bolsas B=(0,1;0,9) da 0,348 y cartón C=(0,5;0,5) da 0,857 — orden con sentido de negocio. Validado con NumPy (`np.dot(a,b)/(norm(a)*norm(b))`, mismos resultados). Acá 0,85 "es lo mismo" y 0,35 "no tiene que ver", pero esa escala no se traslada tal cual a embeddings reales (ver C.2).

**A.3 — `base_conocimiento.json`.** El corpus contiene 22 registros de entrada, con 20 documentos después de la purga. El contrato canónico usa `id`, `descripcion_semantica` y `metadatos`; los campos filtrables (`categoria`, `activo`, `tags_regionales`, SKU y unidad de venta) viven en metadatos, según la Regla del Arquitecto. Dos inconsistencias estructurales y una colisión de ID se conservan deliberadamente como fixtures para B.5.

**A.4 — Índice FAISS.** Repartido en `similitud_coseno.py` (embeddings locales), `construir_indice_faiss.py` (arma y persiste con `write_index()`) y `pipeline_vectorial.py` (recarga con `read_index()`, busca con umbral). Log fijo de 3 consultas de prueba con score y distancia coseno en `docs-resultados/resultados_a4.md`, generado por `reporte_a4.py`.

**A.5 — Prueba de volatilidad.** Evidencia real (no solo narrativa) en `docs-resultados/resultados_a5_volatilidad.md`, generada por `prueba_volatilidad.py`: sin `write_index()`, el índice vive solo en RAM y al simular el reinicio del proceso el archivo no existe (`faiss.read_index()` falla), así que hay que regenerar los embeddings de cero. Con `write_index()`, el mismo escenario recarga el índice desde disco con idéntico `ntotal` (20) y dimensión (384), sin volver a llamar `generar_embeddings()`. Incluye además la reflexión pedida sobre qué pasa si el servidor se reinicia y qué pasa si hay dos servidores (FAISS no resuelve la concurrencia por sí solo; ChromaDB con `PersistentClient` sí, ver B.2).

---

## Parte B — ChromaDB, Filtrado Híbrido y ETL

**B.1 — Migración.** `vector_db.py`: `PersistentClient` sobre `chroma/`, `hnsw:space: cosine`, ingesta con `upsert`.

**B.2 — Los tres límites de FAISS que ChromaDB resuelve.**

| Límite de FAISS | Cómo se manifiesta en EcoLogix | Cómo lo resuelve ChromaDB |
|---|---|---|
| Sin persistencia transaccional / atomicidad | El índice FAISS en memoria se pierde al reiniciar si no se ejecuta `write_index()`. Además, el índice y el archivo de documentos deben mantenerse sincronizados manualmente. | `PersistentClient` guarda la colección en disco y permite reabrirla desde otro proceso. `upsert` actualiza documentos por ID y evita duplicarlos al reejecutar la ingesta. |
| Sin filtrado híbrido nativo | FAISS rankea por similitud vectorial, pero no descarta antes de calcular el ranking los productos discontinuados o de otra categoría. No puede combinar por sí mismo una consulta semántica con reglas como `categoria=sorbetes` y `activo=true`. | ChromaDB aplica filtros nativos mediante `where`, usando operadores como `$and` y `$eq`, antes de devolver los resultados vectoriales. |
| CRUD ineficiente / sin concurrencia | Dar de baja o reemplazar un SKU exige coordinar el índice, los documentos asociados y la persistencia. Las actualizaciones incrementales no forman parte del flujo básico de FAISS. | ChromaDB permite `upsert` y `delete` por ID sobre una colección persistente, lo que facilita altas, modificaciones y bajas puntuales del catálogo. |

La tabla refleja el uso real del proyecto: FAISS resuelve la similitud semántica, mientras que ChromaDB agrega persistencia administrada, metadatos filtrables y operaciones incrementales sobre el conocimiento del dominio.

**B.3 — Evento en caliente.** Discontinuamos sorbetes de papel (`doc-004`, de `0,4617` a fuera del top-5), alta del reemplazo de bagazo (`doc-019`), con `upsert` puntual y verificación con `coleccion.get()` reabriendo un cliente nuevo. Antes: el discontinuado lidera (`0,4617`). Después sin filtro: cae del ranking y el reemplazo entra cuarto (`0,4277`). Con el filtro nativo `where={"categoria": {"$eq": "sorbetes"}, "activo": {"$eq": true}}`: gana el reemplazo solo. `upsert` y no `add`/`update` porque necesitamos alta y modificación juntas en la misma corrida.

**B.4 — Búsqueda híbrida.** `BaseVectorial.buscar_ecologix(query_semantica, filtro_x, solo_activos, n_resultados)` es la CLI con la firma que pide la consigna. `construir_where()` combina `filtro_x`, `solo_activos` y cualquier `where` previo en un único filtro duro que viaja **adentro de la query** de ChromaDB (`$and`, `$eq`): el ranking se calcula sobre documentos que ya cumplen el filtro. **No hay post-filtering en Python** — se eliminaron el descarte por `categoria` posterior a la query y el portero `consulta_es_relevante` que exigía vocabulario del dominio. Todo lo que se descarta después de la query es exclusivamente el umbral de aceptación de C.2, que es una regla de confianza y no un filtro de negocio.

El portero se quitó porque se midió su comportamiento y no resolvía lo que decía resolver: tapaba la killer query 3 y, sobre 8 consultas legítimas de EcoLogix, rechazaba 7 — incluida "hay algo para servir café para llevar?" (0,5328 contra `doc-002`), rechazada solo porque el acento de "café" no coincide con "cafe" en el diccionario. A cambio frenaba 2 de 6 consultas fuera de catálogo, que ahora quedan como falsos positivos conocidos del umbral ("venden notebooks y laptops", 0,4319; "busco contratos de alquiler", 0,4132). El balance —7 consultas válidas tapadas por 2 falsos positivos frenados— es el argumento del cambio.

**B.5 — ETL y purga semántica.** `etl_purga.py` normaliza el contrato canónico, convierte `activo` a booleano, mueve los campos filtrables a `metadatos`, resuelve la colisión de IDs y vectoriza los documentos para comparar distancia coseno. Con umbral `0.15`, elimina los casi-duplicados documentados en `docs-resultados/resultados_etl.md` y explica por qué `SELECT DISTINCT` no los habría detectado.

**B.6 — Killer Queries.** Corridas en `killer_queries.py` y documentadas en `docs-resultados/resultados_killer_queries.md`. La tercera consulta no se marca como aprobada: el falso positivo supera el umbral y queda registrado como limitación real del corpus, tal como exige la consigna.

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
|---:|---|---|---|---|---|
| 1 | "Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje" | Poder semántico: jerga sin palabras exactas del documento | `doc-005` — Envases de cartón para alimentos en el primer puesto y por encima de `0.35`. | `doc-005` primero, similitud `0.585`. | Sí |
| 2 | "Necesito sorbetes para mi kiosco, que esten disponibles en stock" | El metadato salva el día: la semántica cruda trae resultados de otras categorías y el filtro los bloquea. | Sin filtro, `doc-019` queda mezclado o superado; con `where` `categoria=sorbetes` y `activo=true`, queda primero. | Sin filtro, `doc-019` queda cuarto con `0.4277`; con filtro nativo, queda primero con `0.4277`. | Sí |
| 3 | "Venden celulares o accesorios de telefonia?" | Prueba de estrés fuera del catálogo: el sistema debería responder "no tengo eso". | Ningún resultado relevante debería superar el umbral `0.35`. | Con el umbral `0.35` el sistema devuelve `doc-013` — "Bolsas de papel kraft para comercio" — con `0.4874`, y `similitud_ancla` `0.3345`. Falso positivo semántico, no de filtrado. | No: hallazgo |

La tabla muestra por qué el umbral no debe usarse para forzar siempre el resultado más cercano: la consulta 3 supera `0.35` pese a estar fuera del dominio. Con el portero de palabras ya no se tapa: el sistema devuelve el producto más cercano y la evidencia lo registra. Cada resultado expone además `similitud_ancla` —la cercanía de la consulta al centroide del corpus— como diagnóstico: para la consulta 3 da `0.3345`, la más baja entre las consultas reales del dominio medidas, lo que confirma el diagnóstico sin tapar el veredicto. El sistema debe combinar similitud con reglas de dominio y, cuando no puede validar la intención o categoría, responder que no tiene esa información.

---

## Parte C — Coherencia e Informe

**C.1 — Enganche con la Entrega 1**

| Entrega 1 | Entrega 2 |
|---|---|
| PEAS, "Base de Conocimiento" (*hoy nada, a futuro índice vectorial recuperable por RAG*) | La colección ChromaDB con los 18 documentos |
| Matriz de Intenciones, campos de filtrado (*el filtro final por stock/activo sigue siendo SQL*) | Los `metadatos` usados como `where` |
| Lo que el LLM extraía del `texto_libre` | Alimenta la consulta semántica, se resuelve en el `where` |

La regla de oro sigue igual: el LLM no decide stock ni precio. La base vectorial da contexto, no autoridad.

**C.2 — El umbral de aceptación.** Oficial: **0,35** de similitud coseno, justificado en `docs-resultados/resultados_killer_queries.md` con datos reales (relevantes ≥0,39, fuera de dominio <0,30 la mayoría). La regla es una sola y es semántica: el mejor resultado debe superar el umbral, y si no queda ninguna coincidencia por encima, la salida es vacía para que el sistema responda `no tengo esa información`. **No hay una segunda validación por palabras clave**: el filtro de dominio que se usó hasta ahora en `vector_db.py` se eliminó (ver B.4) porque, medido, rechazaba 7 de 8 consultas legítimas y solo frenaba 2 de 6 consultas fuera de catálogo. La verificación ejecutada con la consulta relevante ("Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje") devolvió `doc-005` con `0,585`. Con la consulta fuera de dominio ("Venden celulares o accesorios de telefonia?") el sistema devuelve `doc-013` con `0,4874` y `similitud_ancla` `0,3345`: el umbral solo no alcanza para separar esa consulta, y se deja constancia en lugar de esconderlo detrás de un filtro de palabras. `pipeline_vectorial.py`/FAISS sigue usando `umbral=0.25`, un valor distinto porque se recalibró para ese índice específico y no para la recuperación híbrida del dominio.

**C.3 — Qué falta para cerrar el círculo.** `buscar()` devuelve un dict de Python, no una respuesta para el cliente. Falta el orquestador: algo que tome ese contexto + la consulta + el System Prompt de la Entrega 1, se lo pase al LLM para redactar la respuesta, y decida cuándo derivar a un humano. Eso es RAG con un framework tipo LangChain — Unidad 4, no esta entrega.
