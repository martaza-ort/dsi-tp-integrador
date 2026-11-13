# TP Final Integrador — Agente Inteligente en Producción
Asignatura: Desarrollo de Sistemas de Inteligencia Artificial (IADS 3) · Modalidad: grupal, mismo repositorio · Entrega y defensa: 16 de noviembre

## De qué se trata

El TP Final integra la unidad 5 y 6 en un único sistema. Tomen el RAG de la Entrega 3 y conviértanlo en un agente con LangGraph que decide solo qué herramientas usar, recuerda la conversación y queda expuesto como una API REST observable y protegida con guardrails. El trabajo cierra con una ficha técnica y una defensa en vivo.

## Qué tienen que construir

| Parte | Qué se pide |
|---|---|
|A. Agente|	≥3 herramientas (el retriever de la E3, un sensor y un actuador del dominio) con docstrings completos; grafo ReAct con límite de iteraciones; memoria SQLite persistente por thread_id; matriz de validación con 4 escenarios.|
|B. API REST|	FastAPI con GET /health, POST /consultar, GET /estado/{thread_id} y DELETE /estado/{thread_id}; memoria demostrada vía HTTP, incluso después de reiniciar; el sistema debe levantar en otra máquina siguiendo solo el README.|
|C. Observabilidad|Logs JSON, endpoint GET /metricas (consultas, errores, latencia promedio y p95, herramientas, bloqueos) y trazas en LangSmith con análisis de costos.|
|D. Seguridad|	≥2 validators de input (prompt injection y longitud) y ≥1 de output (enmascarado de datos personales), integrados en /consultar; suite automática de ≥4 tests|
|E. Cierre|Ficha técnica del sistema y defensa en vivo de 15 minutos (presentación, demo y preguntas).|

## Qué se entrega

El link al repositorio público a la rama main o master: código del agente y de la API, security_tests.py, requirements.txt, .env.example, README.md, .gitignore, informe.md y ficha_tecnica.md

---

## Solución Propuesta

Se realiza una propuesta general de alto nivel como base para medir el esfuerzo de cada tarea a implementar y tener un aproximado de tiempos de entrega.

### A. Agente

1. **Integrar el RAG existente como herramienta del agente.**
   - Mantener la configuración actual del pipeline avanzado: recuperar 8 candidatos y seleccionar 4 mediante reranking.
   - Reutilizar la colección `ecologix_chunks_500_100`, el almacenamiento persistente `chroma` y los componentes existentes en `entrega_3/` y `vector_db.py`.
   - No regenerar embeddings durante las consultas. Documentar cómo preparar la colección para una instalación limpia, reutilizando los indexadores existentes y agregando o ajustando pasos solo si fuera necesario.
   - Escribir un docstring completo que describa propósito, argumentos, resultado y límites del retriever.
2. **Implementar las herramientas del dominio EcoLogix**, simuladas localmente y con docstrings completos:
   - **Retriever:** consulta conocimiento comercial en la base RAG.
   - **Sensor — consultar estado de envío:** obtiene el estado de un pedido solo si el backend verifica que pertenece al cliente autenticado.
   - **Actuador — registrar reclamo:** registra un reclamo para el cliente autenticado y, si corresponde, un pedido propio. No aprueba notas de crédito ni compensaciones.
3. **Implementar el grafo ReAct** con un nodo agente y un nodo de herramientas; enrutar los resultados de vuelta al agente hasta la respuesta final. Limitar cada consulta a cinco ciclos de herramientas y permitir una sola herramienta por decisión. Si el agente pide varias en paralelo, no ejecutar ninguna y terminar con una respuesta segura. Si pide otra herramienta después de cinco ciclos, no ejecutarla y terminar sin afirmar que la operación pendiente se realizó. Propagar explícitamente los errores de herramientas, sin presentarlos como éxitos. La memoria persistente se implementa en A.4.
4. **Agregar memoria persistente SQLite por `thread_id`** con `langgraph-checkpoint-sqlite` y comprobar que el historial correspondiente se recupera al reiniciar. Aplicar una retención activa inicial de 30 días corridos desde la última interacción del hilo. Mantener una marca de última actividad sin contenido conversacional en una tabla auxiliar de la base dedicada, actualizarla antes de cada invocación y purgar al iniciar el gestor y luego cada 24 horas. Eliminar el hilo completo mediante `delete_thread` del checkpointer y borrar su metadato auxiliar, sin depender de SQL sobre tablas internas. Usar deserialización restringida de checkpoints. Pasar `cliente_id` por el contexto confiable de ejecución de LangGraph, fuera del estado y los checkpoints. El despliegue inicial usa un solo proceso con una instancia compartida de memoria; múltiples workers requieren coordinación adicional para la purga y el acceso concurrente. Guardar la base fuera del control de versiones y restringir su acceso con permisos/ACL del sistema operativo (`chmod 600` en Unix y ACL equivalentes en Windows). Considerar los archivos WAL/SHM y las copias de seguridad: la purga lógica no garantiza la sobrescritura física ni elimina copias previas.
   - La memoria conversacional y los registros formales de negocio tienen ciclos de vida distintos: el TTL de memoria no debe borrar pedidos ni reclamos. Antes de implementar, resolver la relación existente entre interacciones y reclamos para evitar conservar texto personal innecesario o romper la trazabilidad; cualquier retención de datos de negocio queda sujeta a una definición comercial y revisión legal, no se presume cumplimiento normativo automático.
5. **Preparar una matriz de integración automatizada** en `test_matriz_agente.py`, con modelo falso y SQLite temporal, que compruebe el uso de evidencia RAG, el acceso autorizado a un envío propio, la respuesta neutra para un pedido ajeno o inexistente, el registro de un reclamo asociado a un pedido propio y el rechazo de un reclamo asociado a un pedido ajeno sin escritura. No hacer llamadas a proveedores externos ni modificar datos reales; cada escenario debe verificar tanto el resultado como los efectos observables en las herramientas o la base temporal.

### B. API REST

1. Implementar `GET /health`, `POST /consultar`, `GET /estado/{thread_id}` y `DELETE /estado/{thread_id}` con FastAPI, conectados al agente y a su memoria. El borrado debe autorizar al operador o cliente autenticado y verificar que puede administrar ese hilo; `thread_id` no es una credencial. El endpoint debe borrar el hilo completo mediante la API del checkpointer y sus metadatos auxiliares, y reportar errores de borrado explícitamente.
2. Comprobar la persistencia de conversación mediante HTTP, incluyendo una prueba después de reiniciar el servicio.
3. Documentar en `README.md` la configuración, dependencias, variables de entorno, preparación del índice RAG y ejecución en otra máquina siguiendo únicamente esas instrucciones.
4. Probar los endpoints y mantener respuestas de error que no expongan datos personales, entradas completas ni detalles internos.
5. **Advertencia sobre identidad y autorización:** la API todavía debe definir cómo autentica o identifica de forma confiable al cliente. Debe pasar el `cliente_id` autenticado al contexto confiable de ejecución para que las tools operativas lo reciban por inyección, sin persistirlo en el estado/checkpoint; nunca debe aceptar ese identificador desde el mensaje ni desde argumentos generados por el LLM. La misma autorización debe proteger la lectura y el borrado de hilos. La prueba local con identidad fija sirve solo para tests/demo y no constituye autenticación de producción.

### C. Observabilidad

1. Emitir logs JSON para eventos operativos y de seguridad sin registrar texto completo de consultas, datos personales ni credenciales; para correlación, usar metadatos mínimos y un identificador que no revele ni permita derivar la identidad del cliente o el `thread_id`.
2. Implementar `GET /metricas` con consultas, errores, latencia promedio y p95, uso de herramientas y bloqueos.
3. Instrumentar trazas en LangSmith y analizar costos. Configurar el tracing para no enviar texto de entrada/salida ni datos personales del runtime, incluidas las entradas bloqueadas; si se registra un evento de bloqueo, usar únicamente metadatos sanitizados. Las evaluaciones que necesiten contenido deben usar datos sintéticos.
4. Implementar las métricas según la propuesta base de la subsección "Métricas" de esta parte. Estos criterios podrán ajustarse durante la implementación si las pruebas o la integración revelan necesidades, manteniendo documentados los cambios.

#### Métricas — propuesta base

Propuesta inicial basada en el enfoque de la Clase 12. Se podrá revisar durante la implementación según los resultados de las pruebas, el comportamiento de la API y las restricciones del despliegue; cualquier cambio deberá quedar reflejado en la documentación y en las pruebas.

- **Alcance de conteo:** contar cada solicitud con formato válido que llega al manejador de `POST /consultar`. Registrar por separado consultas exitosas, fallidas, bloqueadas y total de consultas. Una solicitud bloqueada por prompt injection o por exceder el límite de longitud cuenta como consulta y bloqueo, pero no como error técnico. Las solicitudes que FastAPI rechaza antes de ejecutar el manejador (por ejemplo, un cuerpo mal formado) no se incluyen en estos contadores.
- **Éxito y falla:** una consulta es exitosa cuando el flujo del agente termina y devuelve una respuesta procesada; es fallida cuando ocurre un error técnico o no se puede completar el flujo. Los bloqueos de guardrails son una categoría separada y no incrementan el contador de fallas.
- **Latencia:** medir en milisegundos el tiempo total de cada solicitud contabilizada a `POST /consultar`, desde que comienza su procesamiento en el manejador hasta que se obtiene el resultado. Incluir solicitudes bloqueadas dentro del manejador; excluir las rechazadas antes de entrar al manejador.
- **Herramientas:** contar cada invocación efectivamente ejecutada por nombre, no una selección o intento que no llegó a ejecutarse. Registrar por separado los errores técnicos de herramientas como parte del resultado fallido de la consulta.
- **Ventana y reinicio:** mantener contadores y latencias acumulados desde el inicio del proceso, en memoria y con acceso thread-safe. Reiniciarlos al reiniciar la API. Esta propuesta no consolida métricas entre múltiples procesos o instancias.
- **Promedio y p95:** calcularlos sobre las latencias contabilizadas desde el inicio del proceso. Si no hay datos o no se alcanzó la muestra mínima pendiente, devolver p95 como `null` y no evaluar la alerta; el promedio también será `null` si no hay latencias.
- **Alerta de latencia:** usar inicialmente el umbral p95 de **5.0 segundos**. En `GET /metricas`, incluir `alerta_latencia: true` cuando el p95 calculado supere el umbral. Registrar un log `WARNING` cuando la condición pase de inactiva a activa, evitando repetirlo en cada lectura del endpoint. Cuando se normalice, desactivar el flag; el registro de recuperación queda como evento opcional.
- **p99:** no incluirlo en la primera versión porque no es un requisito de la consigna. Podrá agregarse si la implementación o la evaluación lo justifican.

#### Decisión de métrica pendiente

- **Muestra mínima para p95:** definir cuántas consultas completadas se requieren antes de publicar p95 y evaluar la alerta de latencia. Hasta alcanzar ese mínimo, devolver p95 como `null` y no activar la alerta.

### D. Seguridad y pruebas

1. Integrar en `POST /consultar`, antes del modelo y las herramientas:
   - un límite de longitud de entrada de 1000 caracteres, inclusive;
   - un filtro heurístico de prompt injection con patrones claros, sin presentarlo como garantía completa ni como único control. No depender de un segundo LLM como única barrera.
2. Considerar señales de inyección los intentos de cambiar las reglas o el rol del agente, extraer instrucciones internas o credenciales, evadir validaciones, manipular herramientas o acceder a pedidos e información de otro cliente. Una consulta legítima sobre catálogo, stock, pedidos propios, entregas o reclamos no es una inyección por sí misma. Evitar reglas que bloqueen por palabras aisladas y probar los patrones con ejemplos benignos del dominio para reducir falsos positivos.
3. Ante una detección clara de prompt injection, interrumpir el flujo antes del modelo y las herramientas, no actualizar la memoria, no ejecutar escrituras y responder con mensaje neutro y `exito: false`, indicando que no se usaron herramientas. Se propone `HTTP 200` para ese resultado conversacional; no revelar el patrón detectado ni detalles internos.
4. Registrar el bloqueo en logs JSON con nivel `WARNING` y metadatos mínimos, como categoría, resultado, timestamp e identificador de correlación no identificable; no registrar texto original, datos personales, credenciales ni detalle del patrón. No enviar el contenido bloqueado a LangSmith ni a otros servicios externos de trazas.
5. Aplicar autorización y validación determinista dentro de cada herramienta: el filtro no reemplaza la comprobación de propiedad del pedido ni los permisos de escritura del reclamo. Las herramientas deben validar argumentos y permisos inmediatamente antes de consultar o modificar datos, usar solo los datos necesarios y no delegar decisiones de autorización al LLM.
6. Incorporar el enmascarado de CUIT/CUIL, DNI, correo electrónico y teléfono antes de devolver respuestas, con las etiquetas y precauciones especificadas en la subsección "Parámetros definidos" de esta parte.
7. Crear `security_tests.py` con al menos cinco pruebas: bloqueo antes de invocar modelo/herramientas; no bloqueo de consultas legítimas del dominio; rechazo del acceso a pedidos de otro cliente; ausencia de escrituras de reclamos no autorizadas; y ausencia de texto sensible en logs o trazas.

#### Parámetros definidos

- **Límite de longitud de consulta:** máximo de 1000 caracteres, inclusive. Las consultas de más de 1000 caracteres se rechazan con `400 Bad Request` antes de invocar el modelo, el agente, la memoria o cualquier herramienta. La respuesta indica el límite, sin incluir el texto recibido ni su longitud. Este control limita el tamaño de la consulta, pero no sustituye límites del cuerpo HTTP ni otros controles contra abuso.
- **Formato estándar de enmascarado de datos personales:** reemplazar los datos detectados por etiquetas semánticas en mayúsculas y entre corchetes:
  - CUIT o CUIL: `[CUIT_CUIL_ENMASCARADO]`
  - DNI: `[DNI_ENMASCARADO]`
  - Correo electrónico: `[EMAIL_ENMASCARADO]`
  - Teléfono: `[TELEFONO_ENMASCARADO]`
- El enmascarado se aplica a la respuesta final antes de enviarla al cliente y mantiene el `HTTP 200` de una respuesta procesada. Los patrones deben reconocer formatos habituales sin enmascarar números de pedido, SKUs, cantidades u otros datos comerciales. Para DNI y teléfono, no se deben enmascarar secuencias numéricas aisladas sin suficiente contexto, ya que pueden producir falsos positivos. CUIT y CUIL comparten formato, por eso se usa una etiqueta común.
- La sanitización de la respuesta no reemplaza la minimización de datos que recibe el agente ni el cuidado de datos personales en logs y trazas.

### E. Cierre y entrega

1. Preparar `informe.md` y `ficha_tecnica.md` con el diseño, herramientas, memoria, API, guardrails, observabilidad, validación y limitaciones.
2. Preparar la defensa de 15 minutos con presentación, demostración del flujo y respuestas a preguntas.
3. Verificar los archivos de entrega indicados en la consigna, incluyendo código del agente y API, `security_tests.py`, `requirements.txt`, `.env.example`, `README.md`, `.gitignore`, `informe.md` y `ficha_tecnica.md`.
4. Verificar que la entrega esté publicada en un repositorio público en `main` o `master`.
