# Contexto del proyecto para Claude Code

Este repo es el **TP Integrador** de "Desarrollo de Sistemas de IA" (IADS 3, ORT), trabajo grupal,
que evoluciona por entregas: la **1** (asistente con LLM, Pydantic y SQL), la **2** (base de
conocimiento vectorial con FAISS y ChromaDB) y la **3** (pipeline RAG con LangChain y RAGAS).
Los enunciados están en el Project de claude.ai; lo esencial está resumido acá y en
`README.md` y `roadmaps/TAREAS*.md`.

## Qué es esto

Sistema de stock y pedidos para **EcoLogix Systems** (distribuidora de productos ecológicos).
Patrón híbrido de la cátedra: el LLM es el "mozo" (normaliza lenguaje natural → JSON),
el backend determinista es el "chef" (valida con Pydantic y resuelve contra SQL).
**La IA es el intérprete, la base de datos es la autoridad.**

## Archivos y a qué parte del TP responden

- `informes/informe.md` — Partes A (diagnóstico, PEAS, tiktoken) y B (matriz de intenciones, decisión reglas/LLM,
  JSON + SQL + System Prompt, flujo, hipótesis) + narrativa C.4/C.5. Cerrado para la Entrega 1.
- `schemas.py` — C.1. Contrato Pydantic V2. `IntencionEcoLogix` es un `Literal` de 5 valores.
- `app.py` — C.2. Pipeline: `.env` → OpenAI con `response_format` json_schema estricto → Pydantic → enrutador.
- `lote.py` — C.3. 6 inputs fijos → `docs-resultados/resultados_lote.md`. `--tecnica zero|few` para el experimento de C.4.
- `schema.sql` — B.5b. SQLite, probado. Incluye la tabla `interacciones`.
- `test_schemas.py` — tests del contrato sin API.
- Entrega 2: `base_conocimiento.json` (fuente de verdad) → `etl_purga.py` → `base_conocimiento_limpia.json`;
  `vector_db.py` (ChromaDB, `buscar_ecologix`, `UMBRAL_ACEPTACION`), `pipeline_vectorial.py` y
  `construir_indice_faiss.py` (FAISS), `killer_queries.py`, `calibrar_umbral.py`, `informes/informe_entrega2.md`.
- Entrega 3: `entrega_3/rag_pipeline.py` (RAG básico y avanzado), `entrega_3/evaluacion_ragas.py`,
  `entrega_3/golden_dataset.json`. Pasos y estado en `roadmaps/TAREAS3.md`.
- Dependencias: `requirements.txt` (Entregas 1 y 2) y `requirements-entrega3.txt` (suma LangChain y RAGAS).

## Invariantes que NO se pueden romper (criterio 9 de la rúbrica: coherencia transversal)

1. `Literal` de `schemas.py` == filas de la Matriz B.3 en `informes/informe.md` == valores en `docs-resultados/resultados_lote.md`
   == intenciones nombradas en el System Prompt de `app.py`. Si se agrega/quita una intención, tocar los 4.
2. `UnidadVenta` de `schemas.py` == valores de `productos.unidad_venta` en `schema.sql`.
3. El JSON de salida de ejemplo en informes/informe.md B.5 debe validar contra `MensajeClasificado`.
4. El LLM nunca ve precios, stock ni decide escrituras. Toda regla de negocio va en código o SQL.
5. Todo filtro de negocio (`activo`, `categoria`, `tipo`) va dentro del `where` de ChromaDB, nunca como
   `if` de Python después de la query. El umbral de aceptación vive solo en `vector_db.py`.

## Reglas de seguridad (penalizaciones del TP)

- `.env` NUNCA se commitea (ya está en `.gitignore`). Solo `.env.example` sin valores. Una key en el
  historial cuesta −15 puntos y hay que rotarla.
- Commits incrementales y con autor real (se evalúa "quién hizo qué"). Nada de un único commit final.

## Convenciones

- Código y comentarios en español rioplatense, nombres de variables en español (como la cátedra).
- Proveedor: OpenAI, modelo `gpt-4o-mini` (configurable en `.env`). Si se cambia de proveedor,
  adaptar `llamar_modelo()` y los `except` de `procesar_mensaje()` en `app.py`.
- No agregar restricciones (`ge`, `pattern`, `min_length`) en `Field(...)`: el modo `strict` de
  Structured Outputs puede rechazarlas. Las reglas van en `@field_validator`.
- Antes de commitear: `python -m pytest -q test_schemas.py`.

## Pendientes (estado al 2026-10-19)

Las Entregas 1 y 2 están cerradas. De la Entrega 3 el código está hecho y verificado sin API;
faltan las corridas con API, la traza de LangSmith y el informe (ver `roadmaps/TAREAS3.md`).

- [ ] Confirmar que el docente esté agregado como colaborador del repo.
- [ ] Publicar las ramas y abrir los PR en orden: Entrega 2, después Entrega 3.
