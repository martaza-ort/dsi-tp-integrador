# Informe — TP Final Integrador: Agente Inteligente en Producción

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial — IADS 3, ORT
**Grupo:** 1 · **Integrantes:** ver [`README.md`](README.md)
**Entrega y defensa:** 16 de noviembre de 2026

> Las secciones marcadas con ⚠️ **GRUPO** necesitan evidencia de una corrida real con la key de un
> integrante (respuestas del modelo, trazas de LangSmith y costos observados). El resto describe lo
> implementado y verificado con la suite automática.

## 1. Objetivo

Tomar el RAG de la Entrega 3 y convertirlo en un agente con LangGraph que decide solo qué herramientas
usar, recuerda la conversación y queda expuesto como una API REST observable y protegida con
guardrails. El caso sigue siendo **EcoLogix Systems**: la IA interpreta y redacta; el backend
determinista y la base de datos deciden.

## 2. Parte A — Agente

### Herramientas

| Herramienta | Rol (PEAS) | Qué hace |
|---|---|---|
| `buscar_conocimiento_ecologix` | Sensor de conocimiento | Reutiliza el pipeline avanzado de la Entrega 3: 8 candidatos de `ecologix_chunks_500_100` y 4 seleccionados por reranking. |
| `consultar_estado_envio` | Sensor | Lee el estado del envío solo si el pedido es del cliente autenticado. |
| `registrar_reclamo` | Actuador | Inserta un reclamo validando la titularidad del pedido; no aprueba compensaciones. |

Las tres tienen docstrings completos (propósito, argumentos, resultado y límites), que son lo que el
modelo ve para decidir cuándo usarlas.

### Grafo ReAct

Nodo `agente` ⇄ nodo `herramientas`, con dos salidas seguras:

- **Límite de iteraciones:** como máximo 5 ciclos de herramientas por consulta; si el modelo pide una
  sexta, no se ejecuta y se responde sin afirmar que la operación se hizo.
- **Una herramienta por decisión:** si el modelo pide varias en paralelo, no se ejecuta ninguna.

### Memoria

`langgraph-checkpoint-sqlite` con un hilo por conversación, retención de 30 días desde la última
actividad y purga al iniciar y cada 24 horas. `cliente_id` viaja por el contexto confiable de LangGraph
y nunca se guarda en el estado ni en los checkpoints.

### Matriz de validación (4 escenarios)

| Escenario | Resultado esperado | Verificación |
|---|---|---|
| Consulta que requiere evidencia RAG | El agente usa el retriever y responde con esa evidencia | `test_matriz_agente.py` |
| Envío de un pedido propio | Devuelve el estado real del envío | `test_matriz_agente.py` |
| Envío de un pedido ajeno o inexistente | Respuesta neutra, sin filtrar datos | `test_matriz_agente.py` |
| Reclamo sobre pedido propio / ajeno | Se registra / se rechaza sin escribir | `test_matriz_agente.py` |

## 3. Parte B — API REST

Implementada en `api.py` con FastAPI.

| Endpoint | Descripción |
|---|---|
| `GET /health` | Estado del servicio, agente y memoria. |
| `POST /consultar` | Consulta al agente con guardrails. |
| `GET /estado/{thread_id}` | Historial de una conversación propia. |
| `DELETE /estado/{thread_id}` | Borra una conversación propia (extra respecto de la consigna). |
| `GET /metricas` | Métricas de la Parte C. |

**Decisiones de diseño:**

- **Identidad:** `Authorization: Bearer <token>` resuelto a `cliente_id` en el backend. Nunca se acepta
  el identificador desde el mensaje ni desde argumentos del LLM. Es una identidad fija de demo.
- **El `thread_id` no es una credencial:** se transforma con `HMAC(secreto, cliente_id:thread_id)`. Así un
  cliente no puede leer ni borrar el hilo de otro y el identificador persistido no revela al cliente.
- **Un solo proceso:** la memoria SQLite y las métricas viven en el proceso; escalar a varios workers
  requeriría mover el checkpoint a PostgreSQL o Redis (Unidad 6).
- **Errores neutros:** un error del agente devuelve 500 con un mensaje genérico, sin detalles internos.

**Memoria vía HTTP después de reiniciar:** `test_memoria_persiste_via_http_despues_de_reiniciar` levanta
la API, conversa, la apaga, la vuelve a levantar sobre el mismo archivo y verifica con `GET /estado` que
el historial sigue y que el agente continúa la conversación.

> ⚠️ **GRUPO:** pegar acá la salida de la demo manual (consulta → Ctrl+C → reinicio → `GET /estado`).

## 4. Parte C — Observabilidad

### Logs JSON

Cada evento es una línea JSON con `timestamp`, `nivel`, `evento` y metadatos mínimos
(`correlacion_id`, resultado, latencia, herramientas, tokens). No se registra el texto de la consulta,
datos personales, tokens de acceso ni `thread_id`. El `correlacion_id` es aleatorio por solicitud.

### `GET /metricas`

| Métrica | Criterio |
|---|---|
| Consultas | Total, exitosas, fallidas y bloqueadas de cada solicitud con formato válido que llega al manejador. |
| Errores | Fallas técnicas; un bloqueo de guardrail no es un error. |
| Latencia | Promedio y p95 en ms; p95 por rango más cercano, publicado desde 20 consultas. |
| Alerta | `alerta_latencia: true` si p95 > 5 s; se loguea un `WARNING` solo al activarse. |
| Herramientas | Invocaciones efectivamente ejecutadas por nombre y errores de herramientas. |
| Bloqueos | Total y por categoría (`longitud`, `cambio_de_reglas`, `cambio_de_rol`, etc.). |
| Costos | Tokens de entrada y salida y costo estimado total y por consulta. |

Por qué p95 y no solo el promedio: con 70 consultas de 1 s, 25 de 2 s, 4 de 5 s y una de 100 s, el
promedio queda en 2,4 s y esconde la cola, mientras que p95 = 2 s y p99 = 5 s la muestran (verificado en
`test_percentil_nearest_rank_ejemplo_de_clase`).

**Decisión sobre la muestra mínima del p95 (pendiente en la propuesta base):** se fijó en 20 consultas,
configurable con `MUESTRA_MINIMA_P95`. Con menos datos, un único caso lento dispararía la alerta.

### Trazas en LangSmith y análisis de costos

Con `LANGSMITH_TRACING=true`, cada consulta genera una traza `consulta_agente_ecologix` con los spans del
nodo agente, las herramientas y el retriever. La API activa `LANGSMITH_HIDE_INPUTS` y
`LANGSMITH_HIDE_OUTPUTS`, así que se ve la estructura, las latencias y los tokens, pero no el texto. Las
consultas bloqueadas no se trazan porque no llegan al agente.

> ⚠️ **GRUPO:** correr 5 a 10 consultas representativas con la key de un integrante y completar:

| Tipo de consulta | Tokens entrada | Tokens salida | Latencia | Costo USD |
|---|---|---|---|---|
| Conocimiento (RAG) | | | | |
| Estado de envío | | | | |
| Registro de reclamo | | | | |
| **Promedio por consulta** | | | | |

Agregar captura de una traza de LangSmith y una conclusión: qué paso consume más tokens (suele ser el
contexto del RAG, por los 4 fragmentos) y cuánto costarían, por ejemplo, 1000 consultas diarias.

## 5. Parte D — Seguridad

### Validators integrados en `POST /consultar`

| Validator | Tipo | Comportamiento |
|---|---|---|
| Longitud | Entrada | Más de 1000 caracteres → 400, sin modelo, memoria ni herramientas. |
| Prompt injection | Entrada | Detección por categorías → 200 con `exito: false` y mensaje neutro, sin herramientas ni memoria. Log `WARNING` sin el texto. |
| Enmascarado de datos personales | Salida | CUIT/CUIL, DNI, email y teléfono → `[CUIT_CUIL_ENMASCARADO]`, `[DNI_ENMASCARADO]`, `[EMAIL_ENMASCARADO]`, `[TELEFONO_ENMASCARADO]`. |

El detector de inyección busca combinaciones (verbo + objeto), no palabras aisladas, en cinco categorías:
cambio de reglas, cambio de rol, extracción de instrucciones o credenciales, evasión de validaciones y
acceso a datos de otro cliente. Así "Ignoren mi mensaje anterior" pasa, pero "Ignorá tus instrucciones"
se bloquea. Es heurístico: no garantiza detectar todo, por eso **la autorización sigue en cada
herramienta** (defensa en profundidad).

El enmascarado no toca números de pedido, SKU, cantidades ni montos con `$`; para DNI y teléfono exige
contexto ("DNI", "tel") o un formato inequívoco.

### Suite `security_tests.py`

| # | Prueba | Qué verifica |
|---|---|---|
| 1 | Inyecciones (8 variantes) | Bloqueo antes del modelo: el modelo no se invoca, no hay escrituras ni memoria. |
| 2 | Longitud | 1000 caracteres pasan; 1001 → 400 sin invocar el modelo ni devolver el texto. |
| 3 | Consultas legítimas (6 variantes) | No hay falsos positivos con consultas reales del dominio. |
| 4 | Pedido ajeno | Aunque el LLM lo pida, la herramienta no devuelve el envío de otro cliente. |
| 5 | Reclamo no autorizado | No se escribe un reclamo sobre un pedido ajeno (y sí sobre uno propio). |
| 6 | Logs y trazas | Los logs no contienen texto, DNI, email, `thread_id` ni token; LangSmith oculta entradas y salidas. |
| 7 | Enmascarado | La respuesta enmascara los 4 tipos de dato sin tocar datos comerciales. |

## 6. Resultados de la validación automática

| Suite | Resultado |
|---|---|
| `test_agente.py`, `test_memoria.py`, `test_matriz_agente.py`, `test_herramientas_*.py` | ✅ |
| `test_api.py` | ✅ |
| `security_tests.py` | ✅ |

```bash
python -m pytest -q test_agente.py test_memoria.py test_matriz_agente.py \
  test_herramientas_operativas.py test_herramientas_rag.py test_api.py security_tests.py
```

> ⚠️ **GRUPO:** pegar la salida del comando corrido en una máquina del grupo.

## 7. Limitaciones y trabajo futuro

- **Escalado:** un solo proceso. Para varias instancias, checkpoint en PostgreSQL o Redis y métricas en un
  backend compartido (Prometheus, OpenTelemetry).
- **Identidad:** reemplazar los tokens fijos por un proveedor de identidad real (OAuth2/JWT).
- **Inyección:** sumar un clasificador dedicado como segunda capa, sin que sea la única barrera.
- **Calidad:** volver a correr RAGAS sobre el agente completo con el golden dataset de la Entrega 3 para
  detectar regresiones al cambiar prompts o modelo.
- **Memoria inválida en caliente:** si cambia el catálogo, invalidar datos derivados en conversaciones
  activas mediante eventos.

## 8. Defensa (15 minutos)

| Minutos | Contenido |
|---|---|
| 0–3 | Problema de EcoLogix y arquitectura (ficha técnica). |
| 3–9 | Demo: `/health` → consulta RAG → estado de envío propio → pedido ajeno (respuesta neutra) → reclamo → reinicio y `/estado` → inyección bloqueada → `/metricas`. |
| 9–11 | Traza en LangSmith y costos. |
| 11–15 | Preguntas. |
