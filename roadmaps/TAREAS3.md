# Hoja de ruta — Entrega 3

Pasamos de la base vectorial de la Entrega 2 a un sistema RAG completo: pipeline con
LangChain LCEL, chunking con solapamiento y reranking, y evaluación con RAGAS.

La arquitectura híbrida no cambia: el LLM redacta con el contexto recuperado, pero
**nunca** confirma precios, stock ni beneficios que no estén escritos (invariante 4 de la
Entrega 1). Eso lo garantiza el prompt con guardrails y se mide con Faithfulness.

**Entregables** (carpeta `entrega_3/`, link a `main`): `rag_pipeline.py`,
`evaluacion_ragas.py`, `informe.md` y `langsmith_trace.png` (o link público a la traza).

---

## 1. Antes de empezar

1. Estado de las ramas: `main` local ya tiene mergeadas la Entrega 2
   (`fix/entrega2-correcciones`) y esta (`feat/entrega3-rag`). Las correcciones de la
   rúbrica de la Entrega 2 están en `fix/entrega2-rubrica` y los ajustes de esta entrega en
   `fix/entrega3-ajustes`. Falta publicar y abrir los PR en ese orden: **primero la
   Entrega 2, después esta**.
2. Instalar dependencias con `requirements-entrega3.txt` (suma LangChain y RAGAS a
   `requirements.txt`): ver "Cómo correr — Entrega 3" en el `README.md` (en Python 3.14
   `ragas` se instala aparte).
3. Copiar `.env.example` a `.env` y completar `OPENAI_API_KEY` y `LANGCHAIN_API_KEY`.
   **Las keys van solo en `.env`, nunca en `.env.example`** (se commitea y el repo es público).
   `LANGCHAIN_TRACING_V2` viene en `false`: ponerlo en `true` recién para la captura de B.4.
4. Regenerar la base local: `python etl_purga.py`, `python vector_db.py` y
   `python entrega_3/rag_pipeline.py indexar`.

---

## 2. Estado por parte

| Parte | Qué pide la consigna | Estado |
|---|---|---|
| A.1 | Retriever sobre la misma colección y ruta de la Entrega 2 | ✅ Hecho y verificado (mismos scores que `vector_db.py`); filtra `activo=true` dentro del `where` |
| A.2 | Chain LCEL retriever → prompt con guardrails → LLM → parser, con fuentes | ✅ Código hecho (`construir_rag_basico`) |
| A.3 | Matriz de resiliencia: factual, fuera de dominio, complacencia, sinónimos | 🟡 Preguntas definidas; falta correr `matriz` con la API |
| A.4 | Trazabilidad en 2 consultas con fragmento y metadatos | 🟡 Definida; sale en la misma corrida de `matriz` |
| B.1 | Una falla real del RAG básico con su causa técnica | 🟡 Detectada en el retriever; falta la respuesta del LLM (`fallas`) |
| B.2 | Reindexar con solapamiento y comparar cantidad de chunks | ✅ 500/100: de 20 vectores a 40 chunks (6 de 40 superan los 128 tokens del embedder, máx. 145) |
| B.3 | k=8 + reranking con LLM como juez | ✅ Código hecho (juez 0-10, top 3, posicionamiento contra Lost in the Middle) |
| B.4 | Traza de LangSmith con tiempos, tokens y recuperados vs. seleccionados | ❌ Falta: correr con tracing y sacar la captura |
| C.1 | Golden dataset de 10 preguntas (3/3/2/2) | ✅ `entrega_3/golden_dataset.json` |
| C.2 | Baseline RAGAS con las 4 métricas | ❌ Falta correr `evaluacion_ragas.py` |
| C.3 | Tabla básico vs. avanzado con delta | ❌ Sale de la misma corrida |
| C.4 | Peor métrica, causa y acción concreta | ❌ Falta escribirlo con los números |
| — | `entrega_3/informe.md` | ❌ Falta |

---

## 3. Lo que ya sabemos (para el informe)

**B.1 — Falla del RAG básico.** Consulta: *"¿Los envases del desengrasante se pueden
devolver para recargar?"*. El modelo de embeddings (`paraphrase-multilingual-MiniLM-L12-v2`)
trunca a 128 tokens y los 20 documentos los superan (149–212). "Desengrasante" y "pueden
devolverse para recarga" están al final de `doc-006`, fuera del embedding: el retriever
básico (k=4) no trae `doc-006` (trae vasos, bolsas kraft, reclamos). Es un caso de **chunk
cortado**: la información existe pero quedó en la parte que no se vectorizó.
Con chunks de 500/100, `doc-006#2` (la segunda mitad) tiene su propio vector y sube al
2° puesto. Otras consultas del mismo tipo: *"¿Dónde tengo que guardar las cajitas para
delivery?"* (`doc-005` 3° en el básico, 1° con chunks) y *"¿Las bandejas de caña se pueden
meter al horno?"* (gana `doc-019` en el básico, `doc-003#2` con chunks).

**Falla que el chunking NO resuelve (candidata para C.4).** *"¿Puedo devolver los bidones
vacíos para que me los rellenen?"*: ni el básico ni los chunks traen `doc-006`, porque
"bidón" y "rellenar" no aparecen en el corpus. Es un problema de vocabulario, no de corte;
se resolvería con sinónimos en el corpus o con *query expansion*.

**Por qué embeddings locales y no `OpenAIEmbeddings` como en la clase.** La consigna pide
conectarse a la base de la Entrega 2 sin crear una nueva, y esa base está indexada con el
modelo local. Cambiar de modelo obliga a reindexar todo.

**Verificado sin API (2026-10-19).** Con el corpus y el modelo locales se comprobó:
- `rag_pipeline.py` y `evaluacion_ragas.py` importan; los nombres de columna de RAGAS 0.4.3
  (`faithfulness`, `answer_relevancy`, `llm_context_precision_with_reference`,
  `context_recall`) coinciden con `METRICAS`.
- `indexar` genera 40 chunks. El embedder corta a 128 tokens y solo 6 chunks lo superan
  (`doc-002#1`: 145, `doc-005#1` y `doc-003#1`: 141, `doc-014#1`: 135, `doc-017#1`: 133,
  `doc-004#1`: 129). El corte es de a lo sumo 17 tokens, así que el chunking resuelve la
  falla de B.1 casi por completo; decirlo así en el informe (B.2).
- Los retrievers reproducen lo de esta sección: sin `doc-006` en el básico, `doc-006#2` 2°
  con chunks; `doc-005` 3° en el básico y 1° (`doc-005#2`) con chunks; `doc-019` primero en
  el básico y `doc-003#2` primero con chunks; el caso de "bidones" no trae `doc-006` en
  ninguno.
- El filtro `activo=true` no cambia nada en el estado normal, y tras el evento de
  `doc-004` lo deja afuera del contexto.

**Límites que conviene nombrar en el informe.** (1) El RAG no aplica el umbral de
aceptación de la Entrega 2 (0,40, calibrado sobre documentos enteros, no sobre chunks):
las preguntas fuera de dominio llegan con k documentos al LLM y las ataja el prompt con la
frase de escape. (2) `simular_evento_caliente.py` solo toca la colección `ecologix`: después
de un evento hay que correr `indexar` para que `ecologix_chunks` refleje el estado.

---

## 4. Tareas pendientes

### T1 — Correr A.3, A.4 y B.1–B.3 (Low, necesita API)
```bash
python entrega_3/rag_pipeline.py matriz   # -> entrega_3/resultados_matriz.md
python entrega_3/rag_pipeline.py fallas   # -> entrega_3/resultados_fallas.md
```
Revisar que: la factual cite `doc-001`; fuera de dominio use la frase de escape exacta;
complacencia **no** confirme el descuento; sinónimos ("popotes") encuentre `doc-004`.
Si alguna falla, documentarla tal cual (no ajustar el prompt para que "pase" sin decirlo).

### T2 — Traza de LangSmith (Low, necesita API + LangSmith)
Con `LANGCHAIN_TRACING_V2=true` en `.env`:
```bash
python entrega_3/rag_pipeline.py preguntar "¿Los envases del desengrasante se pueden devolver para recargar?" --modo avanzado
```
En smith.langchain.com → proyecto `ecologix-entrega3` → abrir la corrida `rag_avanzado`.
La captura tiene que mostrar: el retriever con los **8 chunks**, las 8 llamadas
`juez_relevancia`, el paso `reranking_llm_juez` con los **3 seleccionados**, la llamada final
al LLM, y los **tiempos y tokens**. Guardar como `entrega_3/langsmith_trace.png` (o compartir
la traza con link público y pegarlo en el informe).

### T3 — Evaluación RAGAS (Medium, necesita API)
```bash
python entrega_3/evaluacion_ragas.py   # -> resultados_ragas.md, ragas_basico.csv, ragas_avanzado.csv
```
La consigna pide mejora (delta) en **al menos una** métrica del avanzado. Si ninguna mejora,
no tocar los resultados: probar `PUNTAJE_MINIMO` o `TOP_RERANKING` en `rag_pipeline.py`,
volver a correr y documentar ambas corridas.

Ojo al interpretar: en las 2 preguntas de escape la respuesta correcta es la frase de
escape, y RAGAS puede dar Answer Relevancy baja o Faithfulness NaN aunque el sistema haya
hecho lo correcto. Documentarlo en C.4 en lugar de esconderlo.

### T4 — `entrega_3/informe.md` (Medium)
Obligatorio: **B.1** (falla y causa técnica, sección 3 de este archivo), **C.3** (tabla
básico vs. avanzado con delta, de `resultados_ragas.md`) y **C.4** (peor métrica del
avanzado, causa probable y una acción técnica concreta). Sumar A.3, A.4, B.2, B.3 y B.4
con links a los `resultados_*.md` y a la captura.

### T5 — Cierre (Low)
Commitear resultados, informe y captura; PR de `feat/entrega3-rag` a `main` (después del
de la Entrega 2); entregar el link de `main`. Verificar que `.env` no esté en el commit.

---

## 5. Reglas de la entrega

- Commits cortos por tarea y con autor real (se evalúa quién hizo qué).
- Ninguna key en el repo: una key real en un commit se penaliza y obliga a rotarla.
- El golden dataset se reutiliza en las Entregas 4 y 5: no cambiar preguntas ni ids sin
  avisar al grupo.
- `chroma/` es local: después de cambiar el corpus, volver a correr `vector_db.py` e
  `indexar`.
