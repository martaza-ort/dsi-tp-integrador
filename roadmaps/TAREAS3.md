# Hoja de ruta — Entrega 3: Sistema RAG completo con evaluación

## Objetivo

Evolucionar la base vectorial de la Entrega 2 hacia un pipeline RAG con LangChain LCEL, mejorar la recuperación mediante chunking y reranking, y evaluar los resultados con RAGAS. Esta hoja resume los requisitos de la consigna original; no reemplaza el PDF ni marca tareas como completadas.

## Parte A — Pipeline RAG con LangChain LCEL

### A.1 — Conexión con la base vectorial
- [x] Configurar el retriever para usar la misma base ChromaDB creada en la Entrega 2.
- [x] Verificar que use el mismo nombre de colección y la misma ruta de persistencia.

### A.2 — Chain LCEL completo
- [x] Implementar la secuencia retriever → prompt de contexto → LLM → parser.
- [x] Configurar el retriever para recuperar los documentos más similares según `k`.
- [x] Incluir guardrails en el prompt: responder solo con información explícita del contexto, no confirmar precios que no estén respaldados y usar una respuesta de escape clara cuando falten datos.
- [x] Hacer que el chain devuelva tanto la respuesta como los documentos fuente utilizados.

### A.3 — Matriz de validación de resiliencia
- [x] Ejecutar el pipeline y registrar una consulta factual directa; debe responder con apoyo en los documentos correctos.
- [x] Probar una consulta fuera del dominio; debe activar la respuesta de escape, sin inventar información.
- [x] Probar un intento de inducir una respuesta complaciente o falsa; debe rechazar la afirmación sin inventar datos.
- [x] Probar una consulta con sinónimos; debe recuperar el documento pertinente y responder correctamente.
- [x] Documentar consultas, resultados observados y si cada comportamiento esperado se cumplió.

### A.4 — Trazabilidad de fuentes
- [x] Mostrar al menos dos consultas en las que se expongan las fuentes empleadas.
- [x] Para cada fuente, registrar el fragmento de texto utilizado y sus metadatos relevantes (por ejemplo, sucursal o categoría).

## Parte B — RAG avanzado: chunking y reranking

### B.1 — Falla del RAG básico
- [ ] Encontrar y documentar al menos una consulta en la que falle el RAG básico.
- [ ] Explicar la causa técnica observada; considerar, entre otras, un chunk cortado, ruido en el contexto o el efecto *Lost in the Middle*.

### B.2 — Chunking con solapamiento
- [ ] Reindexar el corpus usando chunks con solapamiento; la consigna da como ejemplo 500 caracteres de tamaño y 100 de solapamiento.
- [ ] Informar la cantidad de chunks antes y después de reindexar.
- [ ] Analizar si el nuevo chunking corrige la falla registrada en B.1.

### B.3 — Reranking
- [ ] Aumentar la cantidad inicial de documentos recuperados (por ejemplo, `k=8`).
- [ ] Incorporar una etapa de filtrado o reordenamiento por relevancia antes de construir el contexto final.
- [ ] Usar el LLM como juez de relevancia en esa etapa, como propone la consigna.
- [ ] Pasar al generador de respuesta solo el contexto seleccionado tras el reranking.

### B.4 — Traza de LangSmith
- [ ] Configurar la observabilidad de LangSmith con las variables de trazabilidad, API key y nombre de proyecto.
- [ ] Registrar una ejecución completa del pipeline.
- [ ] Documentar tiempos, tokens consumidos y qué chunks se recuperaron frente a cuáles quedaron seleccionados tras el reranking.
- [ ] Guardar una captura o un enlace público de la traza como evidencia. No incluir API keys en archivos versionados.

## Parte C — Evaluación con RAGAS

### C.1 — Golden dataset
- [ ] Crear un conjunto de al menos 10 preguntas del dominio con sus respuestas esperadas (*ground truth*).
- [ ] Incluir 3 preguntas simples, respondibles desde un chunk.
- [ ] Incluir 3 preguntas complejas, que requieran combinar chunks.
- [ ] Incluir 2 preguntas de escape, donde el sistema debe reconocer que no sabe.
- [ ] Incluir 2 preguntas con lenguaje ambiguo o informal.

### C.2 — Baseline RAGAS
- [ ] Ejecutar la evaluación sobre el pipeline RAG básico.
- [ ] Registrar `Faithfulness`, `Answer Relevancy`, `Context Precision` y `Context Recall`.
- [ ] Explicar brevemente qué mide cada métrica y reportar sus valores obtenidos.

### C.3 — Comparación entre modelos/pipelines
- [ ] Evaluar el pipeline avanzado con chunking y reranking.
- [ ] Presentar una tabla comparativa de las cuatro métricas para RAG básico y avanzado, con su delta.
- [ ] Mostrar la mejora de al menos una métrica como resultado del trabajo técnico.

### C.4 — Diagnóstico y mitigación
- [ ] Identificar la métrica con el resultado más bajo en la evaluación avanzada.
- [ ] Explicar una causa probable con evidencia de las corridas.
- [ ] Proponer una acción técnica concreta para mejorarla en una iteración futura.

## Entregables en `entrega_3/`

- [ ] `rag_pipeline.py` o notebook equivalente: implementación de las Partes A y B conectada a la base vectorial original.
- [ ] `evaluacion_ragas.py` o notebook equivalente: golden dataset de 10 preguntas y ejecución de RAGAS.
- [ ] `langsmith_trace.png` o enlace público: evidencia de una traza de LangSmith de la Parte B.4.
- [ ] `informe.md`: análisis de la falla del RAG básico y su causa (B.1), tabla comparativa básico/avanzado (C.3), y diagnóstico de la peor métrica con una propuesta concreta de mejora (C.4).

## Criterio de cierre

- [ ] Verificar que los scripts y evidencias correspondan a las mismas versiones del corpus, la colección y los pipelines evaluados.
- [ ] Confirmar que el informe incluya resultados observados, no solo resultados esperados o tareas planificadas.
- [ ] Confirmar que no se hayan versionado claves de API ni secretos usados para LangSmith.
