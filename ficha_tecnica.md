# Ficha técnica — Agente EcoLogix en producción

**Asignatura:** Desarrollo de Sistemas de IA — IADS 3, ORT · **Grupo:** 1
**Dominio:** EcoLogix Systems, distribuidora mayorista de productos ecológicos y biodegradables.

## Qué hace

Asistente para clientes mayoristas que responde consultas comerciales con evidencia de la base de
conocimiento (RAG), informa el estado de envíos de pedidos propios y registra reclamos. Está expuesto
como API REST observable y protegida con guardrails.

## Arquitectura

```text
Cliente HTTP ── Bearer token ──▶ FastAPI (api.py)
                                   │ 1. Autenticación → cliente_id (backend)
                                   │ 2. Guardrails de entrada (longitud, prompt injection)
                                   ▼
                          Grafo ReAct LangGraph (agente.py)
                          agente ⇄ herramientas (máx. 5 ciclos, 1 tool por turno)
                                   │
         ┌─────────────────────────┼──────────────────────────────┐
         ▼                         ▼                              ▼
 buscar_conocimiento_ecologix  consultar_estado_envio        registrar_reclamo
 (sensor de conocimiento:      (sensor: lee SQLite,          (actuador: escribe SQLite,
  ChromaDB 8→4 con reranking)   valida titularidad)           valida titularidad)
                                   │
                    Memoria SQLite por hilo (memoria.py, TTL 30 días)
                                   │
                    3. Guardrail de salida (enmascarado de datos personales)
                    4. Logs JSON + /metricas + trazas LangSmith (sin texto)
```

## Componentes

| Componente | Tecnología | Archivo |
|---|---|---|
| Modelo de lenguaje | OpenAI `gpt-4o-mini` o Gemini, según `RAG_PROVIDER` | `entrega_3/rag_pipeline.py` |
| Orquestación | LangGraph `StateGraph`, patrón ReAct | `agente.py` |
| Conocimiento | ChromaDB `ecologix_chunks_500_100`, 8 candidatos → 4 con reranking | `herramientas_rag.py` |
| Datos de negocio | SQLite (`schema.sql`) | `herramientas_operativas.py` |
| Memoria | `langgraph-checkpoint-sqlite`, un hilo por conversación | `memoria.py` |
| API | FastAPI + Uvicorn | `api.py` |
| Guardrails | Reglas deterministas (regex) | `guardrails.py` |
| Observabilidad | Logs JSON, métricas en memoria, LangSmith | `observabilidad.py` |

## Herramientas del agente

| Herramienta | Tipo | Efecto | Control |
|---|---|---|---|
| `buscar_conocimiento_ecologix` | Sensor (RAG) | Solo lectura | El contenido recuperado es evidencia, no instrucciones. |
| `consultar_estado_envio` | Sensor | Solo lectura | Solo pedidos del cliente autenticado; respuesta neutra si no es propio. |
| `registrar_reclamo` | Actuador | Escribe un reclamo | Valida titularidad del pedido; no aprueba notas de crédito. |

`cliente_id` llega a las herramientas por el contexto confiable de LangGraph, nunca por argumentos del LLM
ni por el estado persistido.

## Endpoints

| Método y ruta | Respuesta |
|---|---|
| `GET /health` | `{"estado": "ok", "agente": true, "memoria": true}` |
| `POST /consultar` | `{"thread_id", "respuesta", "exito", "herramientas_utilizadas"}` |
| `GET /estado/{thread_id}` | Historial enmascarado de una conversación propia; 404 si no existe o es ajena. |
| `DELETE /estado/{thread_id}` | `{"thread_id", "eliminado": true}`; 404 si no existe o es ajena. |
| `GET /metricas` | Consultas, errores, latencia promedio y p95, alerta, herramientas, bloqueos y costos. |

## Seguridad

| Control | Dónde | Comportamiento |
|---|---|---|
| Autenticación por token | `api.py` | 401 sin token válido. Identidad fija de demo. |
| Aislamiento de hilos | `api.py` | `HMAC(secreto, cliente_id:thread_id)`; un hilo ajeno devuelve 404. |
| Límite de longitud | `guardrails.py` | Más de 1000 caracteres → 400, antes del modelo. |
| Prompt injection | `guardrails.py` | 5 categorías heurísticas → 200 con `exito: false`, sin tools ni memoria. |
| Enmascarado de salida | `guardrails.py` | CUIT/CUIL, DNI, email y teléfono → etiquetas `[..._ENMASCARADO]`. |
| Autorización por herramienta | `herramientas_operativas.py` | Titularidad del pedido validada en código. |
| Límite de ciclos | `agente.py` | Máximo 5 ciclos y 1 herramienta por decisión. |
| Logs y trazas | `observabilidad.py` | Sin texto de consulta, PII, tokens ni `thread_id`; LangSmith oculta entradas y salidas. |

## Observabilidad

- **Métricas:** acumuladas desde el inicio del proceso, thread-safe. p95 por rango más cercano con muestra
  mínima de 20 consultas; alerta si p95 > 5 s.
- **Costos:** tokens de entrada y salida por consulta; costo estimado con precios configurables.
- **Trazas:** LangSmith, una traza `consulta_agente_ecologix` por consulta, con `correlacion_id`.

## Validación

| Suite | Qué cubre | Tests |
|---|---|---|
| `test_agente.py`, `test_matriz_agente.py` | Flujo ReAct, límites y matriz de 4 escenarios (A.5) | Parte A |
| `test_memoria.py` | Persistencia, aislamiento y purga | Parte A |
| `test_api.py` | Endpoints, autenticación, aislamiento, persistencia tras reinicio, métricas | Parte B y C |
| `security_tests.py` | Inyección, longitud, pedidos ajenos, escrituras no autorizadas, logs y trazas, enmascarado | Parte D |

Todas las suites usan un modelo falso y bases temporales: no consumen APIs externas.

## Limitaciones conocidas

- Un solo proceso: memoria SQLite y métricas no se comparten entre workers ni instancias.
- La identidad por tokens fijos sirve para demo; producción requiere un proveedor de identidad real.
- El filtro de prompt injection es heurístico y no detecta todos los ataques; por eso la autorización sigue
  en el backend.
- El enmascarado por regex puede tener falsos negativos con formatos poco comunes.
- Los precios para estimar costos son configurables y deben verificarse con el proveedor.
- La purga lógica de la memoria no elimina copias de seguridad ni garantiza sobrescritura física.
