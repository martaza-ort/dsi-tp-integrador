# TP Integrador — Entrega 2: Del Prompt Saturado a la Base de Conocimiento Vectorial

**Dominio:** EcoLogix Systems (el mismo de la Entrega 1).

- Marta Artaza (`martaza-ort`) — `base_conocimiento.json`, `etl_purga.py`
- Lucía López Guerrero (`LuciaLG1988`) — similitud coseno, índice FAISS, `pipeline_vectorial.py`
- Facundo Folgueira (`Folguee`) — ChromaDB, filtros nativos, evento en caliente
- Agustina Salatino (`agustinasalatino`) — `killer_queries.py`, `docs-resultados/resultados_killer_queries.md`
- Gisella Aramayo (`giaramayo`) — este informe, cierre del repo

---

## Parte A — Embeddings y Búsqueda Semántica

**A.1 — Los tres problemas.** *Costo*: medido con `tiktoken` (`o200k_base`, el tokenizador de gpt-4o-mini) en `medir_tokens_a1.py`, con el mismo precio (USD 0,150 por millón de tokens de entrada) y volumen (10.000 consultas/día) que la Entrega 1:

| Contexto que viaja en cada consulta | Tokens | USD/consulta | USD/día | USD/mes |
|---|---:|---:|---:|---:|
| Catálogo crudo completo (22 registros) | 5.497 | 0,000825 | 8,25 | 247,37 |
| Catálogo limpio completo (20 documentos) | 5.030 | 0,000754 | 7,54 | 226,35 |
| Top-3 recuperados por similitud (promedio de 5 consultas) | 525 | 0,000079 | 0,79 | 23,62 |

Recuperar solo los 3 más relevantes manda **~90 % menos tokens** que pegar el catálogo, y el costo del catálogo completo crece con cada producto nuevo, mientras que el del top-3 queda fijo. Evidencia en `docs-resultados/resultados_a1_tokens.md`. *Lost in the Middle*: el modelo presta menos atención a lo que queda en el medio de un bloque largo. *Estado concurrente*: stock, discontinuados y reemplazos cambian en vivo; el evento de B.3 lo demuestra sin modificar ningún prompt. Un `LIKE '%...%'` tampoco alcanza porque matchea texto literal, no significado, y no rankea por relevancia.

**A.2 — Similitud coseno a mano.** Dos ejes: X=afinidad con bebidas, Y=afinidad con empaque seco. Consulta "vaso para café caliente" → Q=(0,8; 0,2); vasos de bagazo A=(0,9; 0,1). Paso a paso: producto punto `0,8×0,9 + 0,2×0,1 = 0,74`; normas `‖Q‖≈0,8246`, `‖A‖≈0,9055`; división `0,74/(0,8246×0,9055) ≈ 0,991`. Igual con bolsas B=(0,1;0,9) da 0,348 y cartón C=(0,5;0,5) da 0,857 — orden con sentido de negocio. Validado con NumPy (`np.dot(a,b)/(norm(a)*norm(b))`, mismos resultados). Acá 0,85 "es lo mismo" y 0,35 "no tiene que ver", pero esa escala no se traslada tal cual a embeddings reales (ver C.2).

**A.3 — `base_conocimiento.json`.** El corpus contiene 22 registros de entrada, con 20 documentos después de la purga. El contrato canónico usa `id`, `descripcion_semantica` y `metadatos`; los campos filtrables (`categoria`, `activo`, `tags_regionales`, SKU y unidad de venta) viven en metadatos, según la Regla del Arquitecto. Dos inconsistencias estructurales y una colisión de ID se conservan deliberadamente como fixtures para B.5. Cada `descripcion_semantica` es un párrafo de 450 a 710 caracteres (promedio 649 en la base limpia): qué es el producto o la regla, para quién, material y unidad de venta, cómo lo nombran los clientes ("pajitas", "vasitos", "cajitas para delivery") y sus límites de uso. Las descripciones nunca incluyen precios ni stock (invariante 4 de la Entrega 1). **Límite medido:** el modelo de embeddings trunca a 128 tokens y los 20 documentos lo superan (149–212 tokens), así que solo se vectoriza el comienzo de cada párrafo; por eso lo que distingue a cada documento va en la primera oración. Es la motivación directa del *chunking* de la Entrega 3.

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

**B.3 — Evento en caliente.** Discontinuamos sorbetes de papel (`doc-004`), alta del reemplazo de bagazo (`doc-022`), con `upsert` puntual. Antes: el sorbete de papel lidera (0,463). Después sin filtro: sale del top 4, porque su texto ahora describe un producto fuera de catálogo. Con `where={"activo": true}`: gana el reemplazo (0,428). Evidencia en `docs-resultados/resultados_evento_caliente.md`. `upsert` y no `add`/`update` porque necesitamos alta y modificación juntas en la misma corrida.

**B.4 — Búsqueda híbrida.** `buscar(consulta, cantidad, donde)` manda el filtro directo al `where` — cero post-filtering en Python. El estado se representa como el booleano canónico `activo`, y los operadores `$and` y `$eq` se aplican dentro de ChromaDB.

**B.5 — ETL y purga semántica.** `etl_purga.py` normaliza el contrato canónico, convierte `activo` a booleano, mueve los campos filtrables a `metadatos`, resuelve la colisión de IDs y vectoriza los documentos para comparar distancia coseno. El umbral inicial `0.15` equivale a similitud coseno `>= 0.85`: captura los dos pares controlados del mismo producto (`doc-020` a `0.0896` y `doc-021` a `0.1173` de `doc-019`), con `0.0327` de margen sobre el más distante. Del otro lado, el par de documentos *distintos* más cercano de todo el corpus (`doc-008` zonas de entrega vs. `doc-011` retiro o envío) está a `0.163`, así que el corte cae en el hueco entre ambos grupos y no elimina documentos legítimos. Aun así no se presenta como óptimo: ese par es una sola observación, no un conjunto de pares negativos etiquetados, así que todavía no se puede medir la tasa de falsos positivos; esa limitación y el plan de calibración quedan documentados en `docs-resultados/resultados_etl.md`. También explica por qué `SELECT DISTINCT` no habría detectado estos casi-duplicados.

**B.6 — Killer Queries.** Corridas en `killer_queries.py` y documentadas en `docs-resultados/resultados_killer_queries.md`.

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
|---:|---|---|---|---|---|
| 1 | "Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje" | Poder semántico: jerga sin palabras exactas del documento | `doc-005` — Envases de cartón para alimentos en el primer puesto y por encima de `0.35`. | `doc-005` primero, similitud `0.620`. | Sí |
| 2 | "Necesito sorbetes para mi kiosco, que esten disponibles en stock" | El metadato salva el día: la semántica cruda trae resultados de otras categorías y el filtro los bloquea. | Sin filtro, `doc-022` queda mezclado o superado; con `where` `categoria=sorbetes` y `activo=true`, queda primero. | Sin filtro, `doc-022` queda tercero con `0.4277`, detrás de vasos y bolsas kraft; con filtro nativo, queda primero. | Sí |
| 3 | "Venden celulares o accesorios de telefonia?" | Prueba de estrés fuera del catálogo: el sistema debería responder "no tengo eso". | Ningún resultado debería superar el umbral `0.35`. | Mejor resultado `doc-013` con `0.335`, corrido **sin** la regla de vocabulario del dominio: lo rechaza la semántica sola. | Sí, con margen chico |

La consulta 3 es la corrección de fondo de esta entrega. Con las descripciones originales (~300 caracteres) daba un falso positivo de `0.4874` y solo la "tapaba" el portero por palabras clave. Con el corpus enriquecido de A.3, la similitud cae por debajo del umbral sin ese portero. El margen es de apenas `0.015`, así que la regla de vocabulario se mantiene como segunda línea de defensa y no como la que resuelve el caso.

---

## Parte C — Coherencia e Informe

**C.1 — Enganche con la Entrega 1**

| Entrega 1 | Entrega 2 |
|---|---|
| PEAS, "Base de Conocimiento" (*hoy nada, a futuro índice vectorial recuperable por RAG*) | La colección ChromaDB con los 20 documentos limpios (22 registros de entrada menos 2 casi-duplicados purgados en B.5) |
| Matriz de Intenciones, campos de filtrado (*el filtro final por stock/activo sigue siendo SQL*) | Los `metadatos` usados como `where` |
| Lo que el LLM extraía del `texto_libre` | Alimenta la consulta semántica, se resuelve en el `where` |

La regla de oro sigue igual: el LLM no decide stock ni precio. La base vectorial da contexto, no autoridad.

**C.2 — El umbral de aceptación.** Oficial: **0,35** de similitud coseno, justificado en `docs-resultados/resultados_killer_queries.md` con datos reales (relevantes ≥0,428, la consulta fuera de dominio de la killer query 3 queda en 0,335). La regla de aceptación queda definida como una doble validación: la consulta debe tener vocabulario del dominio EcoLogix y el mejor resultado debe superar el umbral antes de considerarse respuesta válida. En la práctica, la búsqueda `BaseVectorial.buscar(...)` rechaza automáticamente consultas fuera de dominio y descarta resultados por debajo de `0,35`; si no queda ninguna coincidencia aceptada, la salida es vacía y el sistema responde `no tengo esa información`, sin forzar el resultado más cercano. La validación real ejecutada con la consulta relevante (`"Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje"`) devolvió `doc-005` con `0,620`, mientras que la consulta fuera de dominio (`"Venden celulares o accesorios de telefonia?"`) devolvió `[]` y `LEN 0`, confirmando que la regla C.2 está funcionando. (`pipeline_vectorial.py`/FAISS sigue usando `umbral=0.25`, un valor distinto porque se recalibró para ese índice específico y no para la recuperación híbrida del dominio.)

**C.3 — Qué falta para cerrar el círculo.** `buscar()` devuelve un dict de Python, no una respuesta para el cliente. Falta el orquestador: algo que tome ese contexto + la consulta + el System Prompt de la Entrega 1, se lo pase al LLM para redactar la respuesta, y decida cuándo derivar a un humano. Eso es RAG con un framework tipo LangChain — Unidad 4, no esta entrega.
