# Ficha técnica — Agente EcoLogix (TP Final Integrador)

IADS 3, ORT · Grupo 1 · Entrega y defensa: 16 de noviembre de 2026

## 1. Qué es

Agente conversacional para EcoLogix Systems (distribuidora de productos
ecológicos). Responde consultas comerciales con RAG, consulta envíos propios y
registra reclamos. Decide solo qué herramienta usar, recuerda la conversación
y se expone por API REST con guardrails y observabilidad.

## 2. Stack

| Capa | Tecnología |
|---|---|
| Agente | LangGraph (ReAct), LangChain |
| Modelo | Configurable por `RAG_PROVIDER` (Gemini u OpenAI); medido con `gemini-3.5-flash-lite` |
| RAG | ChromaDB persistente (`ecologix_chunks_500_100`), embeddings locales `sentence-transformers`, reranking |
| Memoria | SQLite con `langgraph-checkpoint-sqlite` |
| Negocio | SQLite (`schema.sql`), datos ficticios |
| API | FastAPI + Uvicorn (un proceso) |
| Observabilidad | Logs JSON, `/metricas`, LangSmith |

## 3. Herramientas

| Nombre | Tipo | Resumen |
|---|---|---|
| `buscar_conocimiento_ecologix` | Retriever | RAG: 8 candidatos → 4 por reranking. Sin stock ni precios en vivo. |
| `consultar_estado_envio` | Sensor | Estado de envío solo de pedidos del cliente autenticado. |
| `registrar_reclamo` | Actuador | Alta de reclamo `ABIERTO`; sin notas de crédito ni compensaciones. |

## 4. Parámetros clave

| Parámetro | Valor |
|---|---|
| Ciclos de herramientas por consulta | 5 máx.; 1 herramienta por decisión |
| Retención de memoria | 30 días desde la última actividad; purga al iniciar y cada 24 h |
| Longitud de consulta | 1000 caracteres inclusive (`400` si se excede) |
| Muestra mínima para p95 | 20 consultas |
| Umbral de alerta de latencia | p95 > 5000 ms |

## 5. API

| Endpoint | Auth | Función |
|---|---|---|
| `GET /health` | No | Estado |
| `POST /consultar` | Bearer | Consulta al agente |
| `GET /estado/{thread_id}` | Bearer | Historial propio |
| `DELETE /estado/{thread_id}` | Bearer | Borrado propio |
| `GET /metricas` | No | Consultas, errores, latencia (promedio y p95), herramientas, bloqueos |

## 6. Seguridad

- `cliente_id` por contexto confiable de LangGraph; nunca desde el mensaje ni el LLM; no se persiste.
- Autorización de pedido y escritura dentro de cada herramienta.
- `thread_id` aislado por cliente con HMAC; no es una credencial.
- Entrada: límite de longitud y filtro heurístico de prompt injection (antes del modelo, la memoria y las herramientas).
- Salida: enmascarado de CUIT/CUIL, DNI, email y teléfono.
- Logs JSON y LangSmith sin texto de consultas, datos personales ni identificadores del cliente; el tracing se rehúsa a iniciar sin `HIDE_INPUTS/OUTPUTS/METADATA`.

## 7. Validación

88 tests automáticos aprobados (15/11/2026) con modelo falso y bases temporales,
sin claves de proveedor: `test_agente`, `test_memoria`, `test_matriz_agente`,
`test_herramientas_*`, `test_api`, `test_observabilidad`, `security_tests`,
`test_schemas`. Flujo real con RAG y LangSmith verificado manualmente.

## 8. Costos (muestra de 2 solicitudes E2E)

| Concepto | Valor |
|---|---|
| Tokens (entrada / salida) | 7368 / 262 |
| Equivalente a tarifa paga | USD 0.0028654 (≈ USD 0.0014 por solicitud) |
| Cargo real | USD 0 (nivel gratuito) |

No es una proyección de producción.

## 9. Cómo ejecutarlo

Ver `README.md`: instalación, `.env` (`API_CLIENTES`, `HILOS_SECRETO`, proveedor),
índice RAG (`python vector_db.py`, `python -m entrega_3.indexar_chunks`), base
demo (`python inicializar_base_demo.py`) y
`uvicorn api:app --host 127.0.0.1 --port 8000`.

## 10. Limitaciones

- Autenticación de demo con tokens fijos; no apta para producción.
- `/metricas` sin autenticación.
- Un solo proceso (memoria, purga y métricas en memoria).
- Injection heurístico y enmascarado por patrones: sin garantía completa.
- Purga lógica: no sobrescribe físicamente ni toca backups; retención de datos de negocio pendiente de definición legal.
- Herramientas operativas simuladas; el RAG no informa stock ni precios en vivo.
- Costos medidos sobre 2 solicitudes; el nivel gratuito puede usar el contenido para mejorar productos del proveedor.
