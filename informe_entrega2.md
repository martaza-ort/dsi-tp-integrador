# TP Integrador — Entrega 2: Del Prompt Saturado a la Base de Conocimiento Vectorial

**Dominio:** EcoLogix Systems (el mismo de la Entrega 1).

- Marta Artaza (`martaza-ort`) — `base_conocimiento.json`, `etl_purga.py`
- Lucía López Guerrero (`LuciaLG1988`) — similitud coseno, índice FAISS, `pipeline_vectorial.py`
- Facundo Folgueira (`Folguee`) — ChromaDB, filtros nativos, evento en caliente
- Agustina Salatino (`agustinasalatino`) — `killer_queries.py`, `resultados_killer_queries.md`
- Gisella Aramayo (`giaramayo`) — este informe, cierre del repo

---

## Parte A — Embeddings y Búsqueda Semántica

**A.1 — Los tres problemas.** Meter los 22 registros sucios del catálogo en cada prompt cuesta más tokens que el corpus original de 18 documentos; recuperando solo los más relevantes por similitud se evita enviar documentos irrelevantes en cada consulta. *Lost in the Middle*: el modelo presta menos atención a lo que queda en el medio de un bloque largo. *Estado concurrente*: stock, discontinuados y reemplazos cambian en vivo; el evento de B.3 lo demuestra sin modificar ningún prompt. Un `LIKE '%...%'` tampoco alcanza porque matchea texto literal, no significado, y no rankea por relevancia.

**A.2 — Similitud coseno a mano.** Dos ejes: X=afinidad con bebidas, Y=afinidad con empaque seco. Consulta "vaso para café caliente" → Q=(0,8; 0,2); vasos de bagazo A=(0,9; 0,1). Paso a paso: producto punto `0,8×0,9 + 0,2×0,1 = 0,74`; normas `‖Q‖≈0,8246`, `‖A‖≈0,9055`; división `0,74/(0,8246×0,9055) ≈ 0,991`. Igual con bolsas B=(0,1;0,9) da 0,348 y cartón C=(0,5;0,5) da 0,857 — orden con sentido de negocio. Validado con NumPy (`np.dot(a,b)/(norm(a)*norm(b))`, mismos resultados). Acá 0,85 "es lo mismo" y 0,35 "no tiene que ver", pero esa escala no se traslada tal cual a embeddings reales (ver C.2).

**A.3 — `base_conocimiento.json`.** El corpus contiene 22 registros de entrada, con 20 documentos después de la purga. El contrato canónico usa `id`, `descripcion_semantica` y `metadatos`; los campos filtrables (`categoria`, `activo`, `tags_regionales`, SKU y unidad de venta) viven en metadatos, según la Regla del Arquitecto. Dos inconsistencias estructurales y una colisión de ID se conservan deliberadamente como fixtures para B.5.

**A.4 — Índice FAISS.** Repartido en `similitud_coseno.py` (embeddings locales), `construir_indice_faiss.py` (arma y persiste con `write_index()`) y `pipeline_vectorial.py` (recarga con `read_index()`, busca con umbral). Falta un log fijo de 3 consultas de prueba — hoy corre interactivo.

**A.5 — Prueba de volatilidad. No está hecha.** Falta mostrar "sin `write_index()` → se pierde al reiniciar"; solo existe la mitad persistida (`verificar_persistencia()`). Mayor riesgo de la Parte A, la rúbrica la pide explícita.

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

**B.3 — Evento en caliente.** Discontinuamos sorbetes de papel, alta del reemplazo de bagazo, con `upsert` puntual. Antes: el discontinuado lidera (0,46). Después sin filtro: cae al 2°. Con `where={"estado":"activo"}`: gana el reemplazo. `upsert` y no `add`/`update` porque necesitamos alta y modificación juntas en la misma corrida.

**B.4 — Búsqueda híbrida.** `buscar(consulta, cantidad, donde)` manda el filtro directo al `where` — cero post-filtering en Python. El estado se representa como el booleano canónico `activo`, y los operadores `$and` y `$eq` se aplican dentro de ChromaDB.

**B.5 — ETL y purga semántica.** `etl_purga.py` normaliza el contrato canónico, convierte `activo` a booleano, mueve los campos filtrables a `metadatos`, resuelve la colisión de IDs y vectoriza los documentos para comparar distancia coseno. Con umbral `0.15`, elimina los casi-duplicados documentados en `resultados_etl.md` y explica por qué `SELECT DISTINCT` no los habría detectado.

**B.6 — Killer Queries.** Corridas en `killer_queries.py` y documentadas en `resultados_killer_queries.md`. La tercera consulta no se marca como aprobada: el falso positivo supera el umbral y queda registrado como limitación real del corpus, tal como exige la consigna.

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
|---:|---|---|---|---|---|
| 1 | "Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje" | Poder semántico: jerga sin palabras exactas del documento | `doc-005` — Envases de cartón para alimentos en el primer puesto y por encima de `0.35`. | `doc-005` primero, similitud `0.585`. | Sí |
| 2 | "Necesito sorbetes para mi kiosco, que esten disponibles en stock" | El metadato salva el día: la semántica cruda trae resultados de otras categorías y el filtro los bloquea. | Sin filtro, `doc-019` queda mezclado o superado; con `where` `categoria=sorbetes` y `activo=true`, queda primero. | Sin filtro, `doc-019` queda cuarto con `0.4277`; con filtro nativo, queda primero con `0.4277`. | Sí |
| 3 | "Venden celulares o accesorios de telefonia?" | Prueba de estrés fuera del catálogo: el sistema debería responder "no tengo eso". | Ningún resultado relevante debería superar el umbral `0.35`. | `doc-013` queda primero con `0.4874`, aunque es irrelevante. Falso positivo documentado. | No: hallazgo |

La tabla muestra por qué el umbral no debe usarse para forzar siempre el resultado más cercano: la consulta 3 supera `0.35` pese a estar fuera del dominio. El sistema debe combinar similitud con reglas de dominio y, cuando no puede validar la intención o categoría, responder que no tiene esa información.

---

## Parte C — Coherencia e Informe

**C.1 — Enganche con la Entrega 1**

| Entrega 1 | Entrega 2 |
|---|---|
| PEAS, "Base de Conocimiento" (*hoy nada, a futuro índice vectorial recuperable por RAG*) | La colección ChromaDB con los 18 documentos |
| Matriz de Intenciones, campos de filtrado (*el filtro final por stock/activo sigue siendo SQL*) | Los `metadatos` usados como `where` |
| Lo que el LLM extraía del `texto_libre` | Alimenta la consulta semántica, se resuelve en el `where` |

La regla de oro sigue igual: el LLM no decide stock ni precio. La base vectorial da contexto, no autoridad.

**C.2 — El umbral de aceptación.** Oficial: **0,35** de similitud coseno, justificado en `resultados_killer_queries.md` con datos reales (relevantes ≥0,39, fuera de dominio <0,30 la mayoría). Si nada supera el umbral, el sistema debe decir que no tiene esa información, no forzar el resultado más cercano. Hoy ese umbral se evalúa recién al armar el reporte (`killer_queries.py`) — `vector_db.py` no tiene ningún parámetro de umbral, siempre trae los k más cercanos. La killer query 3 lo prueba: un resultado irrelevante (0,487) pasa el 0,35 igual. Aplicarlo dentro de `vector_db.py` queda pendiente. (`pipeline_vectorial.py`/FAISS usa su propio `umbral=0.25`, más bajo porque nunca se recalibró contra este corpus.)

**C.3 — Qué falta para cerrar el círculo.** `buscar()` devuelve un dict de Python, no una respuesta para el cliente. Falta el orquestador: algo que tome ese contexto + la consulta + el System Prompt de la Entrega 1, se lo pase al LLM para redactar la respuesta, y decida cuándo derivar a un humano. Eso es RAG con un framework tipo LangChain — Unidad 4, no esta entrega.
