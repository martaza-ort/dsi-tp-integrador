# Hoja de ruta — Entrega 2

Este trabajo práctico grupal es el segundo paso del Proyecto Integrador del cuatrimestre. La idea es pasar del prompt con contexto estático de la Entrega 1 a una base de conocimiento vectorial real: indexar el dominio propio con FAISS y migrarlo a una base de datos vectorial persistente con ChromaDB.

La entrega mantiene la misma arquitectura híbrida que definimos en la primera entrega:
- la IA interpreta el lenguaje natural,
- el backend determinista valida y resuelve,
- la base de conocimiento vectorial aporta contexto relevante,
- la autoridad del dominio sigue estando en datos y reglas, no en el modelo.

---

## 1. Principios de la Entrega 2

1. No se puede seguir usando contexto estático como fuente de verdad.
2. La base de conocimiento debe poder indexarse, persistirse y consultarse por similitud.
3. El sistema debe seguir respetando el PEAS y la Matriz de Intenciones de la Entrega 1.
4. La búsqueda vectorial debe combinar relevancia semántica con filtros de negocio.
5. Los archivos binarios generados deben recrearse desde `base_conocimiento.json`; no se commitean índices ni bases persistentes.
6. Todo cambio debe quedar en commits cortos por funcionalidad, con evidencia verificable.
7. El repositorio se mantiene público y no se commitea `.env`, claves ni bases derivadas.

---

## 2. Catálogo de esfuerzo

- Major: tarea central, de alto riesgo y con muchas dependencias.
- Medium: tarea importante, modular y ejecutable en paralelo.
- Low: tarea de apoyo, validación, documentación o cierre.

---

## 3. Tareas de la Entrega 2 por dominio funcional

### A.1 — Autopsia del contexto estático
**Esfuerzo:** Medium
**Objetivo:** demostrar con datos del dominio por qué no escala incluir toda la base en cada prompt.
**Incluye:**
- desangre de tokens y costo de enviar todo el corpus
- riesgo de `Lost in the Middle`
- inconsistencia de estado concurrente en stock, catálogo o entregas
- explicación de por qué `SELECT ... WHERE descripcion LIKE '%...%'` tampoco resuelve el problema
**Entregable:** sección A.1 de `informe_entrega2.md`.
**Dependencias:** Entrega 1.
**Commit sugerido:** `docs: documenta limites del contexto estatico`

### A.3 — Construcción del corpus base y `base_conocimiento.json`
**Esfuerzo:** Major
**Objetivo:** crear el dataset del dominio EcoLogix con documentos ricos en texto y metadatos.
**Incluye:**
- respetar la estructura exacta de la consigna: `id`, `descripcion_semantica` y `metadatos`
- incluir al menos 15 documentos del dominio
- agregar párrafos semánticos, campos categóricos, booleanos de estado y `tags_regionales`
- preparar el corpus para FAISS y ChromaDB
**Entregable:** `base_conocimiento.json` con dataset listo para indexación.
**Dependencias:** PEAS y Matriz de Intenciones de la Entrega 1.
**Commit sugerido:** `feat: agrega base_conocimiento inicial del dominio`

### B.5 — ETL de purga, normalización y casi-duplicados
**Esfuerzo:** Major
**Objetivo:** limpiar el corpus para que luego pueda indexarse y consultarse sin ruido semántico.
**Incluye:**
- `etl_purga.py`
- agregar al dataset 2-3 casi-duplicados y 2 inconsistencias estructurales controladas
- normalización de tipos y claves
- resolución y reporte de colisiones de IDs
- limpieza de textos inconsistentes
- vectorización y eliminación de casi-duplicados por distancia coseno con umbral justificado
- reporte de documentos eliminados y explicación de por qué `SELECT DISTINCT` no alcanza
- preparación del dataset para FAISS/Chroma
**Entregable:** dataset limpio y consistente más `resultados_etl.md`.
**Dependencias:** A.3.
**Commit sugerido:** `feat: implementa ETL de purga y normalización`

### A.2 — Similitud coseno y validación matemática
**Esfuerzo:** Major
**Objetivo:** validar la base matemática del enfoque vectorial.
**Incluye:**
- cálculo a mano de similitud coseno con NumPy
- vectorización del corpus
- validación de la forma del embedding
- comparación de documentos relevantes por similitud
**Entregable:** evidencia matemática de similitud y justificación del enfoque.
**Dependencias:** A.3.
**Commit sugerido:** `feat: valida similitud coseno con NumPy`

### A.4 — Índice FAISS y búsqueda semántica
**Esfuerzo:** Major
**Objetivo:** crear el índice vectorial persistente y probar su reconstrucción.
**Incluye:**
- construcción del índice FAISS
- `write_index()`
- prueba de volatilidad con y sin persistencia
- verificación de que el índice puede reconstruirse desde el corpus
 - ejecutar tres consultas de prueba y reportar resultados y distancias
**Entregable:** índice FAISS persistido y búsqueda top-K reproducible.
**Dependencias:** A.2 y A.3.
**Commit sugerido:** `feat: crea indice FAISS persistido en disco`

### A.5 — Prueba destructiva de volatilidad de FAISS
**Esfuerzo:** Major
**Objetivo:** demostrar con evidencia experimental qué ocurre con el índice en memoria RAM y con el índice persistido en disco.
**Incluye:**
- construir un índice en memoria sin `write_index()` y verificar que se pierde al reiniciar el proceso o el entorno
- construir un segundo índice con `write_index()` y recargarlo con `read_index()` sin regenerar embeddings
- comparar resultados top-K, reproducibilidad y consistencia entre la versión volátil y la persistida
- documentar el impacto de un reinicio de proceso, un reinicio del host y la coexistencia de múltiples servidores o instancias sobre el mismo corpus
- dejar evidencia concreta de que la persistencia permite reconstruir el índice sin volver a calcularlo desde cero
**Entregable:** evidencia de volatilidad y persistencia documentada en `informe_entrega2.md`.
**Dependencias:** A.4.
**Commit sugerido:** `test: demuestra volatilidad y persistencia de FAISS`

### B.1 — Migración a ChromaDB
**Esfuerzo:** Major
**Objetivo:** cargar la misma base de A.3 en una colección ChromaDB persistente.
**Incluye:**
- `vector_db.py`
- `PersistentClient` y `upsert`
- persistencia local de la base vectorial
 - colección con `metadata={"hnsw:space": "cosine"}`
 - reejecución sin duplicar documentos
**Entregable:** colección ChromaDB persistente.
**Dependencias:** A.3 y B.5.
**Commit sugerido:** `feat: migra el corpus a ChromaDB persistente`

### B.2 — Límites de FAISS que resuelve ChromaDB
**Esfuerzo:** Medium
**Objetivo:** comparar FAISS con ChromaDB en persistencia, filtrado híbrido y operaciones CRUD.
**Incluye:**
- explicar los tres límites aplicados al dominio EcoLogix
- documentar la solución concreta que aporta ChromaDB en cada caso
- completar la tabla comparativa en `informe_entrega2.md`
**Entregable:** tabla de límites de FAISS y resolución con ChromaDB.
**Dependencias:** A.4, A.5 y B.1.
**Commit sugerido:** `docs: compara limites de FAISS y ChromaDB`

### B.3 — Simulación de evento de negocio en caliente
**Esfuerzo:** Medium
**Objetivo:** validar cómo la recuperación vectorial reacciona ante un cambio real del estado del negocio.
**Incluye:**
- evento de negocio con cambios en stock, demanda o política
- actualización de documentos relevantes
- comprobación de reindexado o reconsultas en ChromaDB
- documentación del efecto del estado dinámico sobre la búsqueda
**Entregable:** evidencia del caso de negocio en caliente.
**Dependencias:** B.1.
**Commit sugerido:** `feat: simula evento de negocio en caliente`

### B.4 — CLI de búsqueda híbrida
**Esfuerzo:** Major
**Objetivo:** combinar relevancia semántica con filtros de negocio sin post-filtering manual.
**Incluye:**
- función de búsqueda del dominio con `consulta`, `filtro`, `solo_activos` y `cantidad`
- uso de embeddings + `where` dentro de ChromaDB, sin aplicar filtros en Python después del query
- operadores nativos como `$and`, `$eq` y validación de estados del negocio (`activo`, `categoria`, etc.)
- soporte explícito para `solo_activos` como atajo de `{"activo": {"$eq": True}}`
- mantener la API determinista y reutilizable para el resto del pipeline
**Entregable:** búsqueda híbrida operativa en `vector_db.py`.
**Dependencias:** B.1.
**Commit sugerido:** `feat: agrega busqueda hibrida con filtros nativos`

### B.6 — Killer queries y validación de recuperación
**Esfuerzo:** Major
**Objetivo:** medir la calidad real del sistema con tres consultas críticas del dominio y fijar un umbral de aceptación defendible.
**Incluye:**
- definir 3 “Killer Queries” basadas en intenciones reales del negocio
- ejecutar consultas sobre FAISS/ChromaDB y comparar resultados semánticos con filtros reales
- evaluar relevancia, precisión y utilidad del contexto recuperado
- documentar resultados en `resultados_killer_queries.md`
- justificar un umbral de aceptación y una respuesta de “no tengo esa información” cuando no hay coincidencias suficientes
**Entregable:** validación de recuperación con evidencia numérica y cualitativa.
**Dependencias:** B.3 y B.4.
**Commit sugerido:** `feat: ejecuta y documenta killer queries`

### C.1 — Cadena de coherencia con la Entrega 1
**Esfuerzo:** Medium
**Objetivo:** conectar la colección y sus metadatos con el PEAS y la Matriz de Intenciones.
**Incluye:**
- columna Base de Conocimiento del PEAS -> documentos de ChromaDB
- campos de filtrado -> metadatos
- parámetros extraídos por el LLM -> filtros de la query
**Entregable:** sección C.1 de `informe_entrega2.md`.
**Dependencias:** B.1 y B.4.
**Commit sugerido:** `docs: conecta entrega 2 con PEAS y matriz`

### C.2 — Umbral de aceptación
**Esfuerzo:** Medium
**Objetivo:** justificar el threshold y la respuesta cuando no hay coincidencias suficientes.
**Incluye:**
- definir el threshold con evidencia de las Killer Queries
- responder `no tengo esa información` cuando ningún resultado lo supera
- evitar forzar el resultado más cercano
**Entregable:** sección C.2 de `informe_entrega2.md`.
**Dependencias:** B.6.
**Commit sugerido:** `docs: justifica umbral de aceptación`

### C.3 — Cierre: conexión con el orquestador
**Esfuerzo:** Low
**Objetivo:** explicar qué componente falta para convertir la recuperación en una respuesta al usuario.
**Incluye:**
- aclarar que la búsqueda híbrida devuelve un `dict` de Python
- identificar el orquestador RAG como siguiente capa
- ubicar LangChain/orquestación en la entrega posterior
**Entregable:** sección C.3 de `informe_entrega2.md`.
**Dependencias:** C.1 y C.2.
**Commit sugerido:** `docs: documenta conexion con orquestador RAG`

### Cierre transversal de la entrega
**Esfuerzo:** Low
**Objetivo:** verificar los archivos y restricciones de entrega sin inventar un nuevo ID de la consigna.
**Incluye:** `README.md`, `.env.example`, `.gitignore`, `requirements.txt`, informe y evidencias; ningún secreto, índice o base binaria versionada.
**Dependencias:** A.1–A.5, B.1–B.6 y C.1–C.3.
**Commit sugerido:** `chore: deja repositorio listo para entrega 2`

---

## 4. Distribución por integrante (6 personas)

### Integrante 1 — Dataset y limpieza del conocimiento
**Tareas:**
- A.3 — Construcción del corpus base y `base_conocimiento.json`
- B.5 — ETL de purga y normalización
**Esfuerzo total:** Major + Major
**Rol:** provee el material base que alimenta todo el resto.

### Integrante 2 — Embeddings y FAISS
**Tareas:**
- A.2 — Similitud coseno y validación matemática
- A.4 — Índice FAISS y búsqueda semántica
- A.5 — Prueba destructiva de volatilidad de FAISS
**Esfuerzo total:** Major + Major + Major
**Rol:** responsable de la base vectorial semántica, su persistencia y su evidencia experimental.

### Integrante 3 — ChromaDB y recuperación filtrada
**Tareas:**
- B.1 — Migración a ChromaDB
- B.3 — Simulación de evento de negocio en caliente
**Esfuerzo total:** Major + Medium
**Rol:** responsable de la base persistente y la búsqueda con filtros reales.

### Integrante 4 — Pipeline vectorial y uso del dominio
**Tareas:**
- B.4 — CLI de búsqueda híbrida
- apoyo a B.3 para conectar el caso de negocio con la consulta real:
    Validar que el pipeline vectorial recupera contexto correcto cuando cambia el estado del negocio (stock, discontinuación o reemplazo de productos), comprobando la evolución del ranking antes y después del evento y confirmando que el filtro nativo de ChromaDB excluye documentos no activos
**Esfuerzo total:** Major + Medium
**Rol:** conecta la recuperación vectorial con el uso práctico del sistema de EcoLogix.
    Asegurando que la búsqueda semántica responda de manera útil y consistente a cambios reales del dominio.

### Integrante 5 — Validación y métricas de calidad
**Tareas:**
- B.6 — Killer queries y validación de recuperación
- C.2 — Umbral de aceptación
**Esfuerzo total:** Major + Medium
**Rol:** responsable de la calidad, el umbral y la sustentación experimental de la entrega.

### Integrante 6 — Informe y cierre del repositorio
**Tareas:**
- A.1 — Autopsia del contexto estático
- C.1 — Cadena de coherencia con la Entrega 1
- C.3 — Cierre: conexión con el orquestador
- cierre transversal de archivos y requisitos
**Esfuerzo total:** Medium + Medium + Low + Low
**Rol:** garantiza la coherencia documental y la preparación final del repo.

### Trabajo transversal
**Tareas:**
- apoyo de Integrante 4 a B.3 para verificar el cambio de ranking antes y después del evento
- apoyo de Integrante 5 a C.1 para trasladar la evidencia de B.6 al informe
**Esfuerzo total:** Major + Medium
**Rol:** mantiene conectadas las pruebas técnicas con la evidencia del informe.

---

## 5. Orden recomendado de ejecución

1. A.1 — autopsia del contexto estático
2. A.2 — similitud coseno a mano
3. A.3 — corpus base
4. A.4 — índice FAISS
5. A.5 — prueba de volatilidad
6. B.1 — migración a ChromaDB
7. B.2 — límites de FAISS
8. B.3 — evento de negocio en caliente
9. B.4 — CLI de búsqueda híbrida
10. B.5 — ETL y purga semántica
11. B.6 — Killer Queries
12. C.1 — coherencia con la Entrega 1
13. C.2 — umbral de aceptación
14. C.3 — conexión con el orquestador
15. cierre transversal del repositorio

Este orden mantiene una lógica de dependencia real: primero hay que construir y limpiar el conocimiento; después indexarlo, consultarlo, validarlo y finalmente cerrar la documentación.

---

## 6. Criterio de cierre de la Entrega 2

La entrega se considera cerrada cuando se cumplen estas condiciones:

- existe `base_conocimiento.json` con al menos 15 documentos del dominio y metadatos claros,
- la base se limpió con ETL y casi-duplicados,
- FAISS está persistido en disco, se validó la similitud coseno y se hizo la prueba de volatilidad,
- ChromaDB está operando con persistencia y filtros nativos `where`,
- están documentados los tres límites de FAISS y su resolución con ChromaDB,
- la CLI combina consulta semántica y filtros nativos sin post-filtering,
- se ejecutaron 3 Killer Queries con evidencia documentada,
- se generaron `informe_entrega2.md`, `resultados_killer_queries.md` y el reporte del ETL,
- no hay claves, `.index` ni bases vectoriales en el repositorio.

---


