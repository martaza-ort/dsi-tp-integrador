# TP Final Integrador — Agente Inteligente en Producción

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial — IADS 3, ORT · **Grupo 1**
**Entrega y defensa:** 16 de noviembre de 2026

Este informe documenta el sistema final: un agente LangGraph para EcoLogix
Systems que reutiliza el RAG de la Entrega 3, recuerda la conversación en
SQLite, se expone como API REST y está protegido con guardrails y observabilidad.
La versión resumida para consulta rápida está en [`ficha_tecnica.md`](../ficha_tecnica.md).

## Resumen del sistema

```text
Cliente ──Bearer──▶ FastAPI ──▶ guardrails de entrada (longitud, injection)
                       │                      │ bloqueo: 200/400, sin agente ni memoria
                       ▼
              grafo ReAct (LangGraph) ◀──▶ memoria SQLite por hilo
                │  agente ⇄ herramientas (máx. 5 ciclos, 1 tool por decisión)
                ├─ buscar_conocimiento_ecologix  (RAG: 8 candidatos → 4 reranking)
                ├─ consultar_estado_envio        (sensor, solo pedidos propios)
                └─ registrar_reclamo             (actuador, solo cliente propio)
                       ▼
              enmascarado de datos personales ──▶ respuesta
Transversal: logs JSON · GET /metricas · trazas LangSmith sin contenido
```

## A. Agente

### A.1 — Herramientas

| Herramienta | Rol | Qué hace | Límites |
|---|---|---|---|
| `buscar_conocimiento_ecologix` | Retriever | Consulta la colección persistida `ecologix_chunks_500_100`: recupera 8 candidatos y selecciona 4 por reranking. Devuelve fragmentos con título de fuente. | No consulta stock en vivo ni precios, no crea pedidos y no regenera embeddings por consulta. Su contenido es evidencia, no instrucciones. |
| `consultar_estado_envio` | Sensor | Devuelve el estado y las fechas del envío de un pedido. | Solo si el pedido pertenece al cliente autenticado; pedido ajeno, inexistente o sin envío dan la misma respuesta neutra. |
| `registrar_reclamo` | Actuador | Inserta un reclamo (con pedido propio opcional) en estado `ABIERTO`. | Verifica titularidad del pedido antes de escribir; no aprueba notas de crédito ni compensaciones. |

Las tres tienen docstring completo (propósito, argumentos, resultado, límites).
Las operativas son simuladas localmente sobre SQLite (`schema.sql`).

**Identidad.** `cliente_id` llega por el contexto confiable de ejecución de
LangGraph (`ContextoAgente`), queda fuera del esquema que ve el modelo y no se
persiste en el estado ni en los checkpoints. El LLM no puede elegir ni falsear
el cliente. La autorización se aplica dentro de cada herramienta, no en el prompt.

### A.2 — Grafo ReAct

Un nodo `agente` y un nodo `herramientas`, con el resultado de cada herramienta
devuelto al agente hasta la respuesta final. Reglas de seguridad del grafo:

- máximo **5 ciclos** de herramientas por consulta; si el agente pide otra, no
  se ejecuta y se responde sin afirmar que la operación pendiente se realizó;
- **una sola herramienta por decisión**: si pide varias en paralelo no se
  ejecuta ninguna y se responde con un mensaje seguro;
- los errores de herramientas se propagan, no se presentan como éxito.

### A.3 — Memoria persistente

`langgraph-checkpoint-sqlite`, un hilo por `thread_id`, con deserialización
restringida de MsgPack. Retención de **30 días** desde la última interacción,
con una tabla auxiliar que guarda solo la marca de actividad (sin contenido).
La purga corre al iniciar y cada 24 horas, y borra el hilo completo con
`delete_thread` del checkpointer. La base vive en `runtime/` (fuera de Git) con
permisos restringidos (`chmod 600` en Unix; en Windows se requieren ACL
equivalentes configuradas por quien despliega).

### A.4 — Matriz de validación

`test_matriz_agente.py` usa un modelo falso y SQLite temporal (sin proveedores
externos ni datos reales) y verifica resultado y efecto observable:

| Escenario | Resultado verificado |
|---|---|
| Uso de evidencia RAG | La respuesta se apoya en el fragmento recuperado. |
| Envío propio | Devuelve el estado autorizado. |
| Pedido ajeno o inexistente | Respuesta neutra idéntica; sin filtrar existencia. |
| Reclamo sobre pedido propio | Se inserta una fila con cliente y pedido correctos. |
| Reclamo sobre pedido ajeno | Se rechaza y no hay escritura en la base. |

## B. API REST

| Endpoint | Auth | Función |
|---|---|---|
| `GET /health` | No | Estado de servicio, agente y memoria. |
| `POST /consultar` | Sí | Consulta al agente; devuelve `thread_id`, `respuesta`, `exito`, `herramientas_utilizadas`. |
| `GET /estado/{thread_id}` | Sí | Historial de un hilo propio (con datos personales enmascarados). |
| `DELETE /estado/{thread_id}` | Sí | Borra checkpoints y metadato auxiliar del hilo propio. |
| `GET /metricas` | No | Métricas de la parte C. |

**Identidad.** `Authorization: Bearer <token>`; el backend resuelve el token a
`cliente_id` con `API_CLIENTES`. Es una identidad fija para demo y tests, **no**
autenticación de producción.

**Aislamiento de hilos.** El `thread_id` no es una credencial: internamente se
usa `HMAC(HILOS_SECRETO, cliente_id:thread_id)`. Otro cliente que conozca el
`thread_id` recibe 404 y el identificador guardado no revela al cliente.

**Persistencia tras reinicio.** Verificada por el test
`test_memoria_persiste_via_http_despues_de_reiniciar` y por la demo manual del
README (consulta, `Ctrl+C`, nuevo arranque, `GET /estado`).

**Errores.** Respuestas neutras (401, 404, 422, 500) que no incluyen la entrada,
datos personales ni detalles internos de excepciones.

**Otra máquina.** El README documenta entorno virtual, `.env`, preparación del
índice RAG (`vector_db.py` y `entrega_3.indexar_chunks`), base demo
(`inicializar_base_demo.py`) y `uvicorn api:app`.

## C. Observabilidad

### C.1 — Diseño

La API EcoLogix incorpora una capa de observabilidad compuesta por:

- logs operativos y de seguridad en formato JSON;
- métricas thread-safe acumuladas en memoria;
- endpoint `GET /metricas`;
- alerta de latencia basada en p95;
- tracing opcional mediante LangSmith con controles de privacidad.

La instrumentación se implementó en `observabilidad.py` y se integró en
`POST /consultar` sin modificar el contrato público de las respuestas.

### C.2 — Métricas implementadas

| Métrica | Criterio |
|---|---|
| Consultas totales | Solicitudes con formato válido que ingresan al manejador de `/consultar`. |
| Exitosas | El agente finaliza y devuelve una respuesta procesada sin errores de herramientas. |
| Fallidas | Ocurre un error técnico o el flujo no puede completarse correctamente. |
| Bloqueadas | Un guardrail interrumpe la consulta antes del modelo y las herramientas. |
| Latencia promedio | Promedio acumulado del tiempo total de procesamiento en milisegundos. |
| Latencia p95 | Percentil 95 calculado mediante rango más próximo desde las 20 muestras. |
| Herramientas | Invocaciones efectivamente ejecutadas, agrupadas por nombre. |
| Errores de herramientas | Resultados técnicos fallidos producidos durante las invocaciones. |

Las solicitudes bloqueadas cuentan como consultas y bloqueos, pero no como
errores técnicos. Las solicitudes rechazadas por FastAPI antes de ingresar al
manejador no forman parte de estos contadores.

Las métricas se acumulan desde el inicio del proceso y se reinician al reiniciar
la API. La primera versión utiliza memoria local y está diseñada para un único
proceso; no consolida resultados entre múltiples workers o instancias.

### C.3 — Latencia y alerta

El promedio se informa desde la primera muestra. Para evitar presentar un
percentil poco representativo, se definió una muestra mínima de 20 consultas
antes de publicar el p95. Hasta alcanzar ese valor, el endpoint devuelve
`p95: null` y no evalúa la alerta.

El umbral inicial es de 5000 ms. Cuando el p95 pasa de un estado normal a uno
superior al umbral, se activa `alerta_latencia` y se genera un único evento
`WARNING`. No se repite la advertencia en cada lectura de `/metricas`.

Esta decisión debe revisarse con tráfico representativo, ya que 20 solicitudes
constituyen una muestra inicial y no una calibración definitiva de producción.

### C.4 — Logs estructurados y privacidad

Los logs propios de EcoLogix se serializan como objetos JSON. Contienen
timestamp, nivel, logger, categoría, resultado e identificador aleatorio de
correlación.

No se registran:

- textos completos de consultas o respuestas;
- credenciales;
- identificadores de clientes;
- `thread_id` públicos o internos;
- mensajes completos de excepciones;
- datos personales.

Los errores se registran mediante categorías y eventos neutrales, sin incluir
el contenido recibido ni detalles que puedan exponer información interna.

### C.5 — Endpoint `GET /metricas`

El endpoint devuelve una fotografía consistente de los contadores, latencias,
herramientas y estado de alerta. No expone mensajes, conversaciones,
credenciales ni identificadores de clientes.

La respuesta incluye:

- momento de inicio de la ventana;
- consultas totales, exitosas, fallidas y bloqueadas;
- promedio, p95, cantidad de muestras y muestra mínima;
- invocaciones por herramienta y errores;
- estado y umbral de la alerta de latencia.

### C.6 — Trazabilidad con LangSmith

El tracing está desactivado por defecto. Para habilitarlo en las ejecuciones
que se quieran observar, configurar las siguientes variables de entorno. La
aplicación rechaza iniciar el tracing si alguno de los tres controles de
privacidad no está activo:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_HIDE_INPUTS=true
LANGSMITH_HIDE_OUTPUTS=true
LANGSMITH_HIDE_METADATA=true
```

El 15 de noviembre de 2026 se hicieron pruebas para verificar la privacidad
del tracing y el flujo real con el índice RAG persistido. Este cuadro resume
los grupos antes de detallar sus resultados:

| Prueba | Sección | Ejecución | Objetivo | Resultado principal |
|---|---|---|---|---|
| **Privacidad del tracing con canario** | **C.6.1** | 18:09 | Comprobar que inputs y outputs queden ocultos en una llamada identificable por marcador | HTTP 200; traza localizada por ID raíz; inputs/outputs vacíos en el dashboard |
| **Integración E2E y medición con RAG persistido** | **C.6.2** | 16:49 y 16:51 | Comprobar el flujo con Chroma, embeddings, reranking y herramienta RAG; obtener tokens y revisar jerarquía | Dos respuestas HTTP 200; la traza queda documentada en C.6.2 y los costos en C.7 |

Los distintos sets de pruebas se ejecutaron con un objetivo específico,
aunque la prueba de privacidad también recorrió el índice RAG.

#### C.6.1 — Privacidad del tracing: consulta con canario (18:09)

Para verificar la privacidad de la traza, se envió el siguiente mensaje a
`POST /consultar`:

```text
Que zonas cubre EcoLogix para las entregas? Para esta prueba de privacidad, codigo de control: ECOLG-PRIV-20261115-1809-M3P8. No repitas el codigo en la respuesta.
```

El marcador buscable es `ECOLG-PRIV-20261115-1809-M3P8`. La solicitud se
ejecutó el 15 de noviembre de 2026 entre las **18:09:11 y las 18:09:15
(UTC−3)**. La llamada respondió HTTP 200, invocó una vez la herramienta RAG y
`GET /metricas` registró una consulta exitosa. Se habilitó `LANGSMITH_TRACING`
y los tres controles `LANGSMITH_HIDE_INPUTS`, `LANGSMITH_HIDE_OUTPUTS` y
`LANGSMITH_HIDE_METADATA`.

El ID raíz capturado localmente es
`01a1e10a-ea90-70d6-86c9-2756ab83816c`. En el dashboard de observabilidad de
LangSmith, ese ID lleva a un único run raíz `LangGraph` iniciado a las 18:09,
con los runs descendientes de la llamada. En el detalle del run raíz, `Input`
y `Output` aparecen como `No inputs` y `No outputs`; en los listados de runs
las columnas de entrada y salida también aparecen vacías. La traza conserva
metadatos técnicos como `ls_run_depth` y tags de pasos, pero no se observan
valores de usuario.

Esta inspección confirma que el dashboard recibió la traza y que sus campos de
entrada/salida no muestran el mensaje ni el marcador. No se buscó el canario
dentro del payload recuperado: los controles de privacidad lo mantienen
oculto. El propósito del canario es identificar el contenido que se quería
proteger y dejar localizable la ejecución por ID y horario.

**Figura C.6.1 — Run raíz de privacidad.** Un solo run `LangGraph` aparece en
el horario de la prueba.

![Run raíz de la prueba de privacidad](../evidencias/langsmith/07-privacidad-runs-raiz.png)

**Figura C.6.2 — Runs descendientes de la herramienta RAG.** Se muestran runs
anidados de la consulta, con inputs y outputs vacíos en el listado.

![Runs descendientes de la herramienta RAG](../evidencias/langsmith/08-privacidad-runs-rag.png)

**Figura C.6.3 — Runs de los nodos del grafo.** Los pasos `agente` y
`herramientas` aparecen asociados a la ejecución.

![Runs de nodos del grafo](../evidencias/langsmith/09-privacidad-runs-grafo.png)

**Figura C.6.4 — Árbol de trazabilidad y detalle del run raíz.** Se ve la
jerarquía y los campos `Input`/`Output` vacíos.

![Árbol de privacidad con inputs y outputs ocultos](../evidencias/langsmith/10-privacidad-traza-detalle.png)

#### C.6.2 — Integración E2E y trazabilidad con RAG persistido (16:49 y 16:51)

Las dos ejecuciones enviaron una consulta de prueba por `POST /consultar` a la
aplicación real, con tracing habilitado para LangSmith, y usaron la
colección Chroma persistida `ecologix_chunks_500_100`, los embeddings locales y
el reranking del modelo configurado. La base de negocio y la memoria
conversacional fueron archivos SQLite temporales; no se usaron datos de
clientes ni se escribieron las bases persistentes. La ejecución de las 16:49
confirmó HTTP 200 y el uso de la herramienta RAG. Se repitió a las 16:51 para
medir tokens de forma fiable e inspeccionar la traza completa.

En la ejecución de las 16:51, `GET /metricas` informó una consulta exitosa y una
invocación de `buscar_conocimiento_ecologix`. La solicitud consumió 3656 tokens
de entrada y 146 de salida, agregados mediante callback. El dashboard de
observabilidad de LangSmith mostró un run raíz `LangGraph`, ID
`01a1e0c3-69c2-75b3-9125-dbe115b3129b`, iniciado a las 4:51:05 p. m. (UTC−3).
El indicador `20` junto al run raíz corresponde a sus descendientes: los 21
runs visibles son pasos anidados de una sola traza, no 21 consultas. El árbol
incluye los nodos `agente`, `decidir_siguiente_nodo` y `herramientas`, además
de spans internos del RAG para recuperación, prompts, reranking y parseo. En
el detalle del run raíz, `Input` y `Output` aparecen como `No inputs` y
`No outputs`.

**Figura C.6.5 — Run raíz de la prueba E2E con RAG de las 16:51.** El dashboard
identifica el run `LangGraph`, con hora y duración.

![Run raíz de LangGraph de la prueba con RAG](../evidencias/langsmith/04-e2e-rag-run-raiz.png)

**Figura C.6.6 — Jerarquía y privacidad de la traza RAG de las 16:51.** Un run
raíz con 20 descendientes; su detalle no muestra inputs ni outputs.

![Jerarquía de la traza RAG con inputs y outputs ocultos](../evidencias/langsmith/05-e2e-rag-traza-jerarquia.png)

**Figura C.6.7 — Spans internos del RAG de las 16:51.** La expansión muestra
pasos anidados de recuperación, reranking y generación, no ejecuciones
independientes.

![Detalle expandido de los spans internos del RAG](../evidencias/langsmith/06-e2e-rag-traza-detalle.png)

### C.7 — Medición E2E y análisis de costos

#### Medición principal: E2E con índice RAG persistido

La medición principal corresponde a la ejecución del 15 de noviembre de 2026
a las 16:51 (UTC−3), detallada en C.6.2. Se envió una consulta de prueba por
`POST /consultar` y se recorrió la aplicación real con el modelo configurado,
`gemini-3.5-flash-lite`, la colección Chroma persistida
`ecologix_chunks_500_100`, los embeddings
locales, el reranking y la herramienta RAG. Para aislar los efectos operativos,
la base de negocio y la memoria se crearon en SQLite temporal; no se utilizaron
datos de clientes ni se modificaron las bases persistentes.

La solicitud respondió HTTP 200, invocó una vez `buscar_conocimiento_ecologix`
y registró una consulta exitosa en `GET /metricas`. El callback de uso del
modelo reportó **3656 tokens de entrada y 146 de salida** para las generaciones
de esa solicitud. Esta ejecución fue una observación del flujo integrado; no
es una estimación de tráfico promedio ni de producción.

La nueva prueba de privacidad de las 18:09, también con el índice RAG
persistido, registró **3712 tokens de entrada y 116 de salida**. Se informan
ambas ejecuciones para transparentar la variación entre consultas; la
ejecución de las 16:49 se excluye porque no se obtuvo un conteo fiable de
tokens.

| Ejecución | Tokens de entrada | Tokens de salida | Equivalente a tarifa paga |
|---|---:|---:|---:|
| 16:51, E2E RAG | 3656 | 146 | USD 0.0014618 |
| 18:09, E2E RAG con canario | 3712 | 116 | USD 0.0014036 |
| **Total (2 solicitudes)** | **7368** | **262** | **USD 0.0028654** |

El equivalente medio de esta muestra es USD 0.0014327 por solicitud. Son dos
observaciones de prueba, no una proyección representativa de producción.

#### Estimación económica

Como la cuenta utilizada está en el nivel gratuito, el cargo esperado por estas
pruebas es **USD 0**, sujeto a los límites y condiciones del plan. El dashboard
de observabilidad de LangSmith también muestra `$0.000`; este valor está
redondeado y no se toma como costo facturado. Para comparar con tarifa paga,
se calculó el equivalente usando USD 0.30 por millón de tokens de entrada y USD
2.50 por millón de tokens de salida:

```text
(3656 × 0.30 + 146 × 2.50) / 1 000 000 = USD 0.0014618
(3712 × 0.30 + 116 × 2.50) / 1 000 000 = USD 0.0014036
```

Los equivalentes calculados describen únicamente el consumo de modelo observado
en estas solicitudes. No incluyen otros servicios potencialmente facturables,
impuestos, descuentos ni diferencias de precio por nivel de cuenta. La
facturación efectiva depende de las condiciones vigentes del proveedor.

#### Alcance y fuente tarifaria

La medición representa una consulta E2E con el índice RAG del proyecto y
almacenamiento temporal para las operaciones de negocio. Es una muestra de dos
solicitudes, no una estimación del costo promedio de producción.

La fuente tarifaria consultada fue la
[página oficial de precios de Gemini API](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite)
(15 de noviembre de 2026). Los valores pueden cambiar y deben verificarse
nuevamente al actualizar el modelo o repetir el análisis. En el nivel gratuito,
Google indica que el contenido puede usarse para mejorar sus productos.

## D. Seguridad y pruebas

### D.1 — Guardrails en `POST /consultar`

Implementados en `guardrails.py`, deterministas y sin segundo LLM.

| Control | Momento | Comportamiento |
|---|---|---|
| Longitud | Entrada | Más de 1000 caracteres (1000 inclusive es válido): `400`, antes de modelo, memoria y herramientas. El mensaje indica el límite, no el texto ni su longitud. |
| Prompt injection | Entrada | Patrones por categoría (cambio de reglas, cambio de rol, extracción de instrucciones o credenciales, evasión de validaciones, acceso a otro cliente). Los patrones combinan verbo y objeto, no palabras aisladas. Ante detección: `HTTP 200`, `exito: false`, sin herramientas, sin escritura en memoria. |
| Enmascarado | Salida | CUIT/CUIL, DNI, correo y teléfono pasan a `[CUIT_CUIL_ENMASCARADO]`, `[DNI_ENMASCARADO]`, `[EMAIL_ENMASCARADO]`, `[TELEFONO_ENMASCARADO]`. No toca números de pedido, SKU ni montos. También se aplica al historial de `GET /estado`. |

Los bloqueos se cuentan como consulta y bloqueo en `/metricas`, con su latencia,
y no como error técnico. El log `WARNING` solo lleva categoría, resultado y un
identificador de correlación aleatorio.

El filtro de inyección es heurístico: **no es una garantía completa** ni el
único control. La autorización real vive en cada herramienta.

### D.2 — Suite `security_tests.py`

25 casos (varios parametrizados) que cubren: bloqueo antes del modelo y de la
memoria, rechazo por longitud con `400`, contadores de `/metricas` tras
bloqueos, consultas legítimas del dominio no bloqueadas (falsos positivos),
rechazo de envío y de reclamo sobre pedido ajeno sin escritura, reclamo propio
sí registrado, ausencia de texto de la consulta y de datos personales en los
logs, obligación de ocultar entradas, salidas y metadatos con LangSmith activo,
y enmascarado correcto sin tocar datos comerciales.

## E. Cierre

### E.1 — Validación

Corrida del 15 de noviembre de 2026, en un entorno virtual limpio con las
dependencias de `requirements.txt` (sin `.env`, sin claves: los tests usan
modelo falso y bases temporales):

| Archivo | Casos | Qué valida |
|---|---:|---|
| `test_agente.py` | 7 | Flujo ReAct, límite de ciclos, llamadas paralelas, errores de herramientas |
| `test_memoria.py` | 5 | Persistencia, aislamiento, ausencia de `cliente_id` en estado, purga por TTL |
| `test_matriz_agente.py` | 6 | Matriz de integración A.4 |
| `test_herramientas_operativas.py` | 8 | Autorización y escrituras de las tools |
| `test_herramientas_rag.py` | 4 | Contrato del retriever 8→4 |
| `test_api.py` | 11 | Endpoints, autenticación, aislamiento, persistencia tras reinicio |
| `test_observabilidad.py` | 10 | Métricas, p95, alerta, logs |
| `security_tests.py` | 25 | Guardrails y privacidad |
| `test_schemas.py` | 12 | Contrato de la Entrega 1 |
| **Total** | **88** | **88 aprobados, 0 fallos** |

Además se validó de forma manual el flujo real con el índice RAG persistido y
trazas de LangSmith (ver C.6 y C.7). Esa parte depende de claves y cuota del
proveedor y no corre en la suite automática.

### E.2 — Limitaciones conocidas

- **Autenticación de demo.** Tokens fijos en `API_CLIENTES`. Producción exige
  autenticación real (por ejemplo OAuth/JWT) y gestión de secretos.
- **`GET /metricas` sin autenticación.** No expone contenido ni identidades,
  pero en producción conviene protegerlo o limitarlo a la red interna.
- **Un solo proceso.** La memoria SQLite, la purga y las métricas en memoria
  asumen una instancia. Varios workers requieren coordinación y métricas
  consolidadas.
- **Filtro de injection heurístico.** Puede tener falsos negativos con
  reformulaciones o idiomas no cubiertos, y falsos positivos en frases raras.
- **Enmascarado por patrones.** Reconoce formatos habituales; DNI y teléfono
  exigen contexto o formato inequívoco, por lo que algunos casos pueden pasar.
- **Retención.** La purga lógica a los 30 días no sobrescribe físicamente
  páginas SQLite ni elimina copias de seguridad previas; WAL/SHM y backups
  necesitan su propia política. La retención de reclamos y pedidos queda
  sujeta a definición comercial y revisión legal.
- **Alcance del RAG.** No informa stock ni precios en vivo; las herramientas
  operativas son simuladas sobre una base local de demo.
- **Costos.** El análisis se basa en dos solicitudes; no es proyección de
  producción. El cargo real fue USD 0 por el nivel gratuito, cuyo contenido
  Google puede usar para mejorar sus productos: no cargar datos reales.
- **Muestra mínima de p95.** 20 consultas es un valor inicial por calibrar con
  tráfico real.
- **Sin límite de tasa ni de tamaño de cuerpo HTTP.** El límite de 1000
  caracteres no sustituye controles contra abuso.

### E.3 — Defensa

Guion de 15 minutos, demo y preguntas probables en
[`roadmaps/GUION-DEFENSA.md`](../roadmaps/GUION-DEFENSA.md).

### E.4 — Archivos de entrega

Código del agente (`agente.py`, `memoria.py`, `herramientas_*.py`,
`contexto_agente.py`) y de la API (`api.py`, `guardrails.py`,
`observabilidad.py`), `security_tests.py`, `requirements.txt`, `.env.example`,
`README.md`, `.gitignore`, `informes/informe-entrega-04.md` y
`ficha_tecnica.md`. La publicación en el repositorio público (`main`) se
confirma antes de la defensa con el checklist del guion.