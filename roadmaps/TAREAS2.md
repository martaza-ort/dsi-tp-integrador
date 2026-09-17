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

### A.1 — Construcción del corpus base y `base_conocimiento.json`
**Esfuerzo:** Major
**Objetivo:** crear el dataset del dominio EcoLogix con documentos ricos en texto y metadatos.
**Incluye:**
- definir el esquema de `base_conocimiento.json`
- incluir al menos 15 documentos del dominio
- agregar texto, categorías, metadatos y claves de negocio
- preparar el corpus para FAISS y ChromaDB
**Entregable:** `base_conocimiento.json` con dataset listo para indexación.
**Dependencias:** PEAS y Matriz de Intenciones de la Entrega 1.
**Commit sugerido:** `feat: agrega base_conocimiento inicial del dominio`

### A.2 — ETL de purga, normalización y casi-duplicados
**Esfuerzo:** Major
**Objetivo:** limpiar el corpus para que luego pueda indexarse y consultarse sin ruido semántico.
**Incluye:**
- `etl_purga.py`
- normalización de tipos y claves
- limpieza de textos inconsistentes
- eliminación de casi-duplicados por umbral semántico
- preparación del dataset para FAISS/Chroma
**Entregable:** dataset limpio y consistente.
**Dependencias:** A.1.
**Commit sugerido:** `feat: implementa ETL de purga y normalización`

### B.1 — Similitud coseno y validación matemática
**Esfuerzo:** Major
**Objetivo:** validar la base matemática del enfoque vectorial.
**Incluye:**
- cálculo a mano de similitud coseno con NumPy
- vectorización del corpus
- validación de la forma del embedding
- comparación de documentos relevantes por similitud
**Entregable:** evidencia matemática de similitud y justificación del enfoque.
**Dependencias:** A.1.
**Commit sugerido:** `feat: valida similitud coseno con NumPy`

### B.2 — FAISS y persistencia en disco
**Esfuerzo:** Major
**Objetivo:** crear el índice vectorial persistente y probar su reconstrucción.
**Incluye:**
- construcción del índice FAISS
- `write_index()`
- prueba de volatilidad con y sin persistencia
- verificación de que el índice puede reconstruirse desde el corpus
**Entregable:** índice FAISS persistido y prueba de consistencia.
**Dependencias:** A.1 y B.1.
**Commit sugerido:** `feat: crea indice FAISS persistido en disco`

### B.3 — Pipeline vectorial con FAISS
**Esfuerzo:** Major
**Objetivo:** encapsular la recuperación vectorial en una capa reutilizable.
**Incluye:**
- `pipeline_vectorial.py`
- carga del dataset y embeddings
- consulta semántica con FAISS
- recuperación de contexto relevante por intención de negocio
- preparación de la respuesta para usarla en el pipeline real
**Entregable:** pipeline vectorial funcional.
**Dependencias:** A.1, B.1 y B.2.
**Commit sugerido:** `feat: implementa pipeline vectorial de consulta`

### C.1 — Migración a ChromaDB y filtros nativos
**Esfuerzo:** Major
**Objetivo:** migrar el corpus a ChromaDB persistente y utilizar filtrado híbrido con `where`.
**Incluye:**
- `vector_db.py`
- `PersistentClient` y `upsert`
- persistencia local de la base vectorial
- uso de filtros nativos `where` (sin post-filtering manual)
- validación del flujo de inserción y consulta
**Entregable:** base ChromaDB funcionando con búsqueda filtrada.
**Dependencias:** A.1, A.2 y B.3.
**Commit sugerido:** `feat: migra el corpus a ChromaDB persistente`

### C.2 — Simulación de evento de negocio en caliente
**Esfuerzo:** Medium
**Objetivo:** validar cómo la recuperación vectorial reacciona ante un cambio real del estado del negocio.
**Incluye:**
- evento de negocio con cambios en stock, demanda o política
- actualización de documentos relevantes
- comprobación de reindexado o reconsultas en ChromaDB
- documentación del efecto del estado dinámico sobre la búsqueda
**Entregable:** evidencia del caso de negocio en caliente.
**Dependencias:** C.1.
**Commit sugerido:** `feat: simula evento de negocio en caliente`

### C.3 — Killer queries y validación de recuperación
**Esfuerzo:** Major
**Objetivo:** medir la calidad del sistema con tres consultas críticas del negocio.
**Incluye:**
- definir 3 “Killer Queries” basadas en intentos reales del dominio
- ejecutar consultas sobre FAISS/ChromaDB
- evaluar relevancia, precisión y utilidad del contexto recuperado
- documentar resultados en `resultados_killer_queries.md`
- decidir umbral de aceptación justificado
**Entregable:** validación de recuperación con evidencia numérica y cualitativa.
**Dependencias:** B.3, C.1 y C.2.
**Commit sugerido:** `feat: ejecuta y documenta killer queries`

### C.4 — Informe final y coherencia con la Entrega 1
**Esfuerzo:** Medium
**Objetivo:** cerrar la entrega conectando explícitamente con PEAS, Matriz de Intenciones y decisión de arquitectura.
**Incluye:**
- `informe_entrega2.md`
- explicar el problema del contexto estático
- enganche con el PEAS y la Matriz de Intenciones
- justificar el umbral de aceptación
- documentar la decisión de pasar a conocimiento vectorial
**Entregable:** informe final de la Entrega 2.
**Dependencias:** todas las tareas anteriores.
**Commit sugerido:** `docs: escribe informe final de entrega 2`

### C.5 — Cierre del repositorio y requisitos de entrega
**Esfuerzo:** Low
**Objetivo:** dejar el repositorio listo para entrega según la consigna.
**Incluye:**
- `base_conocimiento.json`
- `pipeline_vectorial.py`
- `vector_db.py`
- `etl_purga.py`
- `informe_entrega2.md`
- `resultados_killer_queries.md`
- `requirements.txt` actualizado
- `.env` no commitado
- no incluir ChromaDB ni `.index` generados
**Entregable:** repo listo y consistente con la entrega.
**Dependencias:** todas las tareas anteriores.
**Commit sugerido:** `chore: deja repositorio listo para entrega 2`

---

## 4. Distribución por integrante (6 personas)

### Integrante 1 — Dataset y limpieza del conocimiento
**Tareas:**
- A.1 — Construcción del corpus base y `base_conocimiento.json`
- A.2 — ETL de purga y normalización
**Esfuerzo total:** Major + Major
**Rol:** provee el material base que alimenta todo el resto.

### Integrante 2 — Embeddings y FAISS
**Tareas:**
- B.1 — Similitud coseno y validación matemática
- B.2 — FAISS y persistencia en disco
**Esfuerzo total:** Major + Major
**Rol:** responsable de la base vectorial semántica y la prueba técnica del índice.

### Integrante 3 — ChromaDB y recuperación filtrada
**Tareas:**
- C.1 — Migración a ChromaDB y filtros nativos
- C.2 — Simulación de evento de negocio en caliente
**Esfuerzo total:** Major + Medium
**Rol:** responsable de la base persistente y la búsqueda con filtros reales.

### Integrante 4 — Pipeline vectorial y uso del dominio
**Tareas:**
- B.3 — Pipeline vectorial con FAISS
- apoyo a C.2 para conectar el caso de negocio con la consulta real
**Esfuerzo total:** Major + Medium
**Rol:** conecta la recuperación vectorial con el uso práctico del sistema de EcoLogix.

### Integrante 5 — Validación y métricas de calidad
**Tareas:**
- C.3 — Killer queries y validación de recuperación
- apoyo a C.4 para la parte de evidencia y conclusiones
**Esfuerzo total:** Major + Medium
**Rol:** responsable de la calidad y de la sustentación experimental de la entrega.

### Integrante 6 — Informe y cierre del repositorio
**Tareas:**
- C.4 — Informe final y coherencia con la Entrega 1
- C.5 — Cierre del repositorio y requisitos de entrega
**Esfuerzo total:** Medium + Low
**Rol:** garantiza la coherencia documental y la preparación final del repo.

---

## 5. Orden recomendado de ejecución

1. A.1 — dataset base
2. A.2 — ETL y limpieza
3. B.1 — similitud coseno
4. B.2 — FAISS persistido
5. B.3 — pipeline vectorial
6. C.1 — ChromaDB persistente y filtros
7. C.2 — evento de negocio en caliente
8. C.3 — killer queries
9. C.4 — informe final
10. C.5 — cierre del repo y requisitos final

Este orden mantiene una lógica de dependencia real: primero hay que construir y limpiar el conocimiento; después indexarlo, consultarlo, validarlo y finalmente cerrar la documentación.

---

## 6. Criterio de cierre de la Entrega 2

La entrega se considera cerrada cuando se cumplen estas condiciones:

- existe `base_conocimiento.json` con al menos 15 documentos del dominio y metadatos claros,
- la base se limpió con ETL y casi-duplicados,
- FAISS está persistido en disco y se validó la similitud coseno,
- ChromaDB está operando con persistencia y filtros nativos `where`,
- el pipeline vectorial consulta documentos relevantes y funciona en casos reales,
- se ejecutaron 3 Killer Queries con evidencia documentada,
- se generó `informe_entrega2.md` y `resultados_killer_queries.md`,
- no hay claves, `.index` ni bases vectoriales en el repositorio.

---


