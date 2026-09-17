# TP Integrador — Entrega 2: Del Prompt Saturado a la Base de Conocimiento Vectorial

**Dominio:** EcoLogix Systems (el mismo de la Entrega 1).

- Marta Artaza (`martaza-ort`) — `base_conocimiento.json`, `etl_purga.py`
- Lucía López Guerrero (`LuciaLG1988`) — similitud coseno, índice FAISS, `pipeline_vectorial.py`
- Facundo Folgueira (`Folguee`) — ChromaDB, filtros nativos, evento en caliente
- Agustina Salatino (`agustinasalatino`) — `killer_queries.py`, `resultados_killer_queries.md`
- Gisella Aramayo (`giaramayo`) — este informe, cierre del repo

Sigue el orden A.1–A.5 / B.1–B.6 / C.1–C.3 de la consigna. Lo hecho, con evidencia real. Lo que falta, señalado con a quién le toca — sin inventar resultados. **Pendiente real:** `base_conocimiento.json` no usa las claves exactas pedidas (A.3), falta la prueba de volatilidad (A.5), y el ETL no hace purga semántica, solo dedup exacto (B.5).

---

## Parte A — Embeddings y Búsqueda Semántica

**A.1 — Los tres problemas.** Meter los 18 documentos del catálogo en cada prompt cuesta 3.444 tokens (`tiktoken`), + 894 del System Prompt de la Entrega 1 = 4.338/consulta; recuperando los 3 más relevantes por similitud baja a 1.539 (−81%), y el catálogo real de EcoLogix tiene más SKUs todavía. *Lost in the Middle*: el modelo presta menos atención a lo que queda en el medio de un bloque largo (Liu et al., 2023) — con 18 documentos ya es un riesgo. *Estado concurrente*: stock, discontinuados y reemplazos cambian en vivo; probado en B.3, donde discontinuamos un producto y el sistema lo reflejó sin tocar ningún prompt. Un `LIKE '%...%'` tampoco alcanza porque matchea texto literal, no significado, y no rankea por relevancia.

**A.2 — Similitud coseno a mano.** Dos ejes: X=afinidad con bebidas, Y=afinidad con empaque seco. Consulta "vaso para café caliente" → Q=(0,8; 0,2); vasos de bagazo A=(0,9; 0,1). Paso a paso: producto punto `0,8×0,9 + 0,2×0,1 = 0,74`; normas `‖Q‖≈0,8246`, `‖A‖≈0,9055`; división `0,74/(0,8246×0,9055) ≈ 0,991`. Igual con bolsas B=(0,1;0,9) da 0,348 y cartón C=(0,5;0,5) da 0,857 — orden con sentido de negocio. Validado con NumPy (`np.dot(a,b)/(norm(a)*norm(b))`, mismos resultados). Acá 0,85 "es lo mismo" y 0,35 "no tiene que ver", pero esa escala no se traslada tal cual a embeddings reales (ver C.2).

**A.3 — `base_conocimiento.json`.** 18 documentos (≥15 ✓), texto en párrafo, metadatos filtrables. No usa los nombres de campo exactos de la consigna: `texto` en vez de `descripcion_semantica`, `estado` es string no booleano, `tags` vive fuera de `metadatos` y no se llama `tags_regionales`. No lo tocamos (es de `@martaza-ort`), pero pega en el criterio 3 de la rúbrica.

**A.4 — Índice FAISS.** Repartido en `similitud_coseno.py` (embeddings locales), `construir_indice_faiss.py` (arma y persiste con `write_index()`) y `pipeline_vectorial.py` (recarga con `read_index()`, busca con umbral). Falta un log fijo de 3 consultas de prueba — hoy corre interactivo.

**A.5 — Prueba de volatilidad. No está hecha.** Falta mostrar "sin `write_index()` → se pierde al reiniciar"; solo existe la mitad persistida (`verificar_persistencia()`). Mayor riesgo de la Parte A, la rúbrica la pide explícita.

---

## Parte B — ChromaDB, Filtrado Híbrido y ETL

**B.1 — Migración.** `vector_db.py`: `PersistentClient` sobre `chroma/`, `hnsw:space: cosine`, ingesta con `upsert`.

**B.2 — Los tres límites de FAISS que ChromaDB resuelve.** Sin persistencia transaccional (FAISS en RAM puede quedar a medias si el proceso muere; ChromaDB escribe a disco por operación) · sin filtrado híbrido nativo (FAISS solo rankea por distancia; ChromaDB filtra con `where` antes de rankear) · CRUD ineficiente (dar de baja un SKU en FAISS exige reconstruir todo; ChromaDB opera por id con `upsert`/`delete`).

**B.3 — Evento en caliente.** Discontinuamos sorbetes de papel, alta del reemplazo de bagazo, con `upsert` puntual. Antes: el discontinuado lidera (0,46). Después sin filtro: cae al 2°. Con `where={"estado":"activo"}`: gana el reemplazo. `upsert` y no `add`/`update` porque necesitamos alta y modificación juntas en la misma corrida.

**B.4 — Búsqueda híbrida.** `buscar(consulta, cantidad, donde)` manda el filtro directo al `where` — cero post-filtering en Python. La consigna pide un `solo_activos` booleano dedicado; acá es un dict genérico (consistente con que `estado` no es booleano, A.3).

**B.5 — ETL y purga semántica.** `etl_purga.py` normaliza texto/tags/claves y saca duplicados exactos. Falta: casi-duplicados sembrados a mano en el dataset, y la purga semántica en sí (comparar embeddings por umbral de distancia) — hoy solo compara strings iguales. La pieza que falta ya existe en `similitud_coseno.py`, solo hay que conectarla.

**B.6 — Killer Queries.** Corridas en `killer_queries.py` (`resultados_killer_queries.md`). Las tres pasan: (1) "packaging para comida caliente a domicilio" trae los envases de cartón sin nombrarlos, 0,585; (2) sin filtro el sorbete discontinuado empata/gana, con `where` gana el reemplazo; (3) "venden celulares?" es el caso interesante — el resultado más parecido (0,487) supera igual el umbral por vocabulario genérico compartido con el corpus chico, documentado como hallazgo real, no tapado.

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
