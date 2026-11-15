# TP Final Integrador — Agente Inteligente en Producción

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

El tracing se mantiene desactivado por defecto y puede habilitarse mediante
variables de entorno. Si se activa, la aplicación exige:

```dotenv
LANGSMITH_HIDE_INPUTS=true
LANGSMITH_HIDE_OUTPUTS=true
LANGSMITH_HIDE_METADATA=true