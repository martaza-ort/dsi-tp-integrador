# TP Integrador — Entrega 2: Del Prompt Saturado a la Base de Conocimiento Vectorial

**Dominio:** EcoLogix Systems (el mismo de la Entrega 1).

- Marta Artaza (`martaza-ort`) — `base_conocimiento.json`, `etl_purga.py`
- Lucía López Guerrero (`LuciaLG1988`) — similitud coseno, índice FAISS, `pipeline_vectorial.py`
- Facundo Folgueira (`Folguee`) — ChromaDB, filtros nativos, evento en caliente
- Agustina Salatino (`agustinasalatino`) — `killer_queries.py`, `docs-resultados/resultados_killer_queries.md`
- Gisella Aramayo (`giaramayo`) — este informe, cierre del repo

---

## Parte A — Embeddings y Búsqueda Semántica

**A.1 — Los tres problemas.** *Costo*: medido con `tiktoken` (`o200k_base`, el tokenizador de gpt-4o-mini) en `medir_tokens_a1.py`, con el mismo precio (USD 0,150 por millón de tokens de entrada) y volumen (10.000 consultas/día) que la Entrega 1:

| Contexto que viaja en cada consulta | Tokens | USD/consulta | USD/día | USD/mes |
|---|---:|---:|---:|---:|
| Catálogo crudo completo (22 registros) | 5.497 | 0,000825 | 8,25 | 247,37 |
| Catálogo limpio completo (20 documentos) | 5.030 | 0,000754 | 7,54 | 226,35 |
| Top-3 recuperados por similitud (promedio de 5 consultas) | 525 | 0,000079 | 0,79 | 23,62 |

Recuperar solo los 3 más relevantes manda **~90 % menos tokens** que pegar el catálogo, y el costo del catálogo completo crece con cada producto nuevo, mientras que el del top-3 queda fijo. Evidencia en `docs-resultados/resultados_a1_tokens.md`.

*Lost in the Middle*: pegar los 20 documentos arma un bloque de ~5.000 tokens en el que cada dato queda en una posición fija. Si el cliente pregunta cuándo se reserva la mercadería, la respuesta está en `doc-010` (*Reserva de stock al confirmar pedido*), el documento 10 de 20: en el medio exacto del bloque, rodeado de `doc-009` (stock por depósito) y `doc-011` (retiro vs. entrega), que hablan de temas parecidos. Es la zona donde el modelo presta menos atención, y el riesgo es que mezcle las reglas de esos tres documentos o responda con la de otro. Con top-3 el contexto son ~525 tokens y `doc-010` viaja al principio, sin competir con 17 documentos que no vienen al caso.

*Estado concurrente*: lo que cambia mientras el cliente está en la sesión es el stock por depósito (`doc-009`), las reservas que otro cliente confirma (`doc-010`) y el estado de cada SKU: el sorbete de papel puede discontinuarse y reemplazarse por el de bagazo (el evento de B.3). Un System Prompt con el catálogo pegado queda desactualizado en cuanto eso ocurre y habría que regenerarlo en cada llamada; con la base vectorial alcanza con un `upsert` puntual y la próxima consulta ya ve el cambio.

Un `SELECT ... WHERE descripcion LIKE '%...%'` tampoco lo resuelve: solo matchea texto literal, así que "pajitas" o "popotes" no encuentran el *sorbete de papel* (`doc-004`) aunque sean la misma cosa, y no rankea por relevancia ni por significado.

**A.2 — Similitud coseno a mano.** Dos ejes: X=afinidad con bebidas, Y=afinidad con empaque seco. Consulta "vaso para café caliente" → Q=(0,8; 0,2); vasos de bagazo A=(0,9; 0,1). Paso a paso: producto punto `0,8×0,9 + 0,2×0,1 = 0,74`; normas `‖Q‖≈0,8246`, `‖A‖≈0,9055`; división `0,74/(0,8246×0,9055) ≈ 0,991`. Igual con bolsas B=(0,1;0,9) da 0,348 y cartón C=(0,5;0,5) da 0,857 — orden con sentido de negocio. Validado con NumPy (`np.dot(a,b)/(norm(a)*norm(b))`, mismos resultados): `similitud_manual.py` repite los tres pasos por documento, compara contra NumPy con un `assert` y se corre con `python similitud_manual.py`. Acá 0,85 "es lo mismo" y 0,35 "no tiene que ver", pero esa escala no se traslada tal cual a embeddings reales (ver C.2).

**A.3 — `base_conocimiento.json`.** El corpus contiene 22 registros de entrada, con 20 documentos después de la purga. El contrato canónico usa `id`, `descripcion_semantica` y `metadatos`; los campos filtrables (`categoria`, `activo`, `tags_regionales`, SKU y unidad de venta) viven en metadatos, según la Regla del Arquitecto. Dos inconsistencias estructurales y una colisión de ID se conservan deliberadamente como fixtures para B.5. Cada `descripcion_semantica` es un párrafo de 450 a 710 caracteres (promedio 649 en la base limpia): qué es el producto o la regla, para quién, material y unidad de venta, cómo lo nombran los clientes ("pajitas", "vasitos", "cajitas para delivery") y sus límites de uso. Las descripciones nunca incluyen precios ni stock (invariante 4 de la Entrega 1). **Límite medido:** el modelo de embeddings trunca a 128 tokens y los 20 documentos lo superan (149–212 tokens), así que solo se vectoriza el comienzo de cada párrafo; por eso lo que distingue a cada documento va en la primera oración. Es la motivación directa del *chunking* de la Entrega 3.

**Regla del Arquitecto aplicada al esquema.** Todo lo sobre lo que el sistema tiene que aplicar un filtro duro va como metadato; lo narrativo queda en el texto vectorizado:

| Campo | Dónde vive | Por qué |
|---|---|---|
| `activo` (booleano de estado) | metadato | Filtro duro: un producto discontinuado nunca puede recomendarse (`where activo=true`). Es lo que cambia en el evento de B.3. |
| `categoria`, `tipo` (categóricos) | metadato | Filtros de la Matriz de Intenciones de la Entrega 1 (`categoria=sorbetes`, `tipo=producto`); no se pueden dejar a la similitud semántica. |
| `sku`, `unidad_venta`, `unidades_por_bulto`, `material`, `uso_principal` | metadato | Datos exactos y comparables: se cruzan con `schema.sql` y `UnidadVenta` de la Entrega 1, y el pedido necesita el valor, no una paráfrasis. |
| `titulo` | metadato | Se muestra al usuario y se reporta en los resultados; no aporta significado extra al embedding. |
| `tags_regionales` | metadato y texto | Es jerga ("pajitas", "popotes", "vasitos"): sirve como etiqueta, y `preparar_texto()` la suma al texto para que el embedding capture sinónimos. |
| Usos, matices, contexto comercial, límites ("no conviene almacenarlas al sol"), cómo lo piden los clientes | texto (`descripcion_semantica`) | Es lo narrativo que se busca por significado. Convertirlo en metadato obligaría a conocer de antemano todas las preguntas posibles. |

Lo que *no* se hace es el caso inverso (meter un filtro duro como `activo` solo en el texto, o un matiz como "aguanta bebidas calientes" como metadato), que es justo lo que la regla prohíbe.

**A.4 — Índice FAISS.** Repartido en `similitud_coseno.py` (embeddings locales), `construir_indice_faiss.py` (arma y persiste con `write_index()`) y `pipeline_vectorial.py` (construye el índice si no existe, lo recarga con `read_index()` si existe, y corre las 3 consultas de prueba con score y distancia; `--interactivo` permite una consulta propia). Log fijo de 3 consultas de prueba con score y distancia coseno en `docs-resultados/resultados_a4.md`, generado por `reporte_a4.py`.

**A.5 — Prueba de volatilidad.** Evidencia real (no solo narrativa) en `docs-resultados/resultados_a5_volatilidad.md`, generada por `prueba_volatilidad.py`: sin `write_index()`, el índice vive solo en RAM y al simular el reinicio del proceso el archivo no existe (`faiss.read_index()` falla), así que hay que regenerar los embeddings de cero. Con `write_index()`, el mismo escenario recarga el índice desde disco con idéntico `ntotal` (20) y dimensión (384), sin volver a llamar `generar_embeddings()`. Incluye además la reflexión pedida sobre qué pasa si el servidor se reinicia y qué pasa si hay dos servidores (FAISS no resuelve la concurrencia por sí solo; ChromaDB con `PersistentClient` sí, ver B.2).

---

## Parte B — ChromaDB, Filtrado Híbrido y ETL

**B.1 — Migración.** `vector_db.py`: `PersistentClient` sobre `chroma/`, `hnsw:space: cosine`, ingesta con `upsert`.

**B.2 — Los tres límites de FAISS que ChromaDB resuelve.**

| Límite de FAISS | Cómo se manifiesta en EcoLogix | Cómo lo resuelve ChromaDB |
|---|---|---|
| Sin persistencia transaccional / atomicidad | El índice FAISS en memoria se pierde al reiniciar si no se ejecuta `write_index()`. Además, el índice y el archivo de documentos deben mantenerse sincronizados manualmente. | `PersistentClient` guarda la colección en disco y permite reabrirla desde otro proceso. `upsert` actualiza documentos por ID y evita duplicarlos al reejecutar la ingesta. |
| Sin filtrado híbrido nativo | FAISS rankea por similitud vectorial, pero no descarta antes de calcular el ranking los productos discontinuados o de otra categoría. No puede combinar por sí mismo una consulta semántica con reglas como `categoria=sorbetes` y `activo=true`. | ChromaDB aplica filtros nativos mediante `where`, usando operadores como `$and` y `$eq`, antes de devolver los resultados vectoriales. |
| CRUD ineficiente / sin concurrencia | Dar de baja o reemplazar un SKU exige coordinar el índice, los documentos asociados y la persistencia. Las actualizaciones incrementales no forman parte del flujo básico de FAISS. | ChromaDB permite `upsert` y `delete` por ID sobre una colección persistente, lo que facilita altas, modificaciones y bajas puntuales del catálogo. |

La tabla refleja el uso real del proyecto: FAISS resuelve la similitud semántica, mientras que ChromaDB agrega persistencia administrada, metadatos filtrables y operaciones incrementales sobre el conocimiento del dominio.

**B.3 — Evento en caliente.** Discontinuamos sorbetes de papel (`doc-004`), alta del reemplazo de bagazo (`doc-022`), con `upsert` puntual y verificación con `coleccion.get()` reabriendo un cliente nuevo. Antes: el sorbete de papel lidera (`0,4631`). Después sin filtro: sale del top 5, porque su texto ahora describe un producto fuera de catálogo, y el reemplazo entra tercero (`0,4277`), detrás de vasos y bolsas kraft. Con el filtro nativo `where={"categoria": {"$eq": "sorbetes"}, "activo": {"$eq": true}}`: gana el reemplazo solo. Evidencia en `docs-resultados/resultados_evento_caliente.md`. La verificación con `coleccion.get(ids=["doc-004", "doc-022"])` sobre un cliente nuevo queda en la evidencia (`doc-004` con `activo=False`, `doc-022` con `activo=True`). **Por qué `upsert` y no `add` ni `update`:** `add` no modifica un id que ya existe (lo ignora o falla según la versión), así que `doc-004` no quedaría discontinuado ni se podría re-ejecutar el evento; `update` falla con un id inexistente y `doc-022` es un alta. `upsert` hace las dos cosas en una sola llamada y es idempotente: el script se puede correr varias veces sin duplicar.

**B.4 — Búsqueda híbrida.** `BaseVectorial.buscar_ecologix(query_semantica, filtro_x, solo_activos, n_resultados)` es la CLI con la firma que pide la consigna. `construir_where()` combina `filtro_x`, `solo_activos` y cualquier `where` previo en un único filtro duro que viaja **adentro de la query** de ChromaDB (`$and`, `$eq`): el ranking se calcula sobre documentos que ya cumplen el filtro. **No hay post-filtering en Python** — se eliminaron el descarte por `categoria` posterior a la query y el portero `consulta_es_relevante` que exigía vocabulario del dominio. Todo lo que se descarta después de la query es exclusivamente el umbral de aceptación de C.2, que es una regla de confianza y no un filtro de negocio.

El portero se quitó porque se midió su comportamiento y no resolvía lo que decía resolver: tapaba la killer query 3 y, en la medición previa a quitarlo (8 consultas legítimas de EcoLogix y 6 fuera de catálogo; el portero ya no está en el código, por lo que no se puede re-correr) rechazaba 7 de las 8 — incluida "hay algo para servir café para llevar?" (hoy `0,4759` contra `doc-002`), rechazada solo porque el acento de "café" no coincide con "cafe" en el diccionario. A cambio frenaba 2 de 6 consultas fuera de catálogo; sin portero, con el corpus actual y el umbral de `0,40` de C.2, "venden notebooks y laptops" (`0,3839`) y "busco contratos de alquiler" (`0,3475`) quedan por debajo del umbral. El balance —7 consultas válidas tapadas contra 2 fuera de catálogo frenadas— es el argumento del cambio.

**B.5 — ETL y purga semántica.** `etl_purga.py` normaliza el contrato canónico, convierte `activo` a booleano, mueve los campos filtrables a `metadatos`, resuelve la colisión de IDs y vectoriza los documentos para comparar distancia coseno. El umbral inicial `0.15` equivale a similitud coseno `>= 0.85`: captura los dos pares controlados del mismo producto (`doc-020` a `0.0896` y `doc-021` a `0.1173` de `doc-019`), con `0.0327` de margen sobre el más distante. Del otro lado, el par de documentos *distintos* más cercano de todo el corpus (`doc-008` zonas de entrega vs. `doc-011` retiro o envío) está a `0.163`, así que el corte cae en el hueco entre ambos grupos y no elimina documentos legítimos. Aun así no se presenta como óptimo: ese par es una sola observación, no un conjunto de pares negativos etiquetados, así que todavía no se puede medir la tasa de falsos positivos; esa limitación y el plan de calibración quedan documentados en `docs-resultados/resultados_etl.md`. También explica por qué `SELECT DISTINCT` no habría detectado estos casi-duplicados.

**B.6 — Killer Queries.** Corridas en `killer_queries.py` y documentadas en `docs-resultados/resultados_killer_queries.md`.

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
|---:|---|---|---|---|---|
| 1 | "Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje" | Poder semántico: jerga sin palabras exactas del documento | `doc-005` — Envases de cartón para alimentos en el primer puesto y por encima de `0.40`. | `doc-005` primero, similitud `0.620`. | Sí |
| 2 | "Necesito sorbetes para mi kiosco, que esten disponibles en stock" | El metadato salva el día: la semántica cruda trae resultados de otras categorías y el filtro los bloquea. | Sin filtro, `doc-022` queda mezclado o superado; con `where` `categoria=sorbetes` y `activo=true`, queda primero. | Sin filtro, `doc-022` queda tercero con `0.4277`, detrás de vasos y bolsas kraft; con filtro nativo, queda primero. | Sí |
| 3 | "Venden celulares o accesorios de telefonia?" | Prueba de estrés fuera del catálogo: el sistema debería responder "no tengo eso". | Ningún resultado debería superar el umbral `0.40`. | El mejor resultado es `doc-017` — "Jerga comercial del dominio" — con `0.3735`, por debajo de `0.40`: el sistema no devuelve nada y responde "no tengo esa información" (`similitud_ancla` `0.2852`). Con el umbral anterior de `0.35` era un falso positivo. | Sí |

La consulta 3 es la que obligó a calibrar el umbral. Con `0,35` pasaba `doc-017` (`0,3735`), un documento *sobre* el lenguaje del negocio (enumera "productos", "descartables", "clientes", "caja", "bulto") que atrae cualquier consulta comercial genérica. Antes no aparecía porque un descarte por `categoria` posterior a la query lo eliminaba en silencio, que es justamente el post-filtering que se quitó en B.4. Con el corpus enriquecido de A.3, `doc-013` (el falso positivo que se veía antes) bajó de `0.4874` a `0.335`. Medir 18 consultas válidas y 8 fuera de catálogo (`calibrar_umbral.py`, `docs-resultados/resultados_umbral.md`) mostró que el umbral correcto es `0,40` (ver C.2): deja `doc-017` afuera sin rechazar consultas válidas adicionales. `similitud_ancla` da `0.2852` para esta consulta, pero 3 de 5 consultas legítimas medidas quedan más abajo, así que el ancla queda solo como diagnóstico y no decide. Queda como límite conocido que algunas consultas *vecinas* del dominio ("¿venden servilletas?", "¿cuánto cuesta la caja de vasos?") superan cualquier umbral razonable; para esas la mitigación es un filtro de negocio **dentro** del `where` (por ejemplo `tipo=producto` según la intención) y, en la Entrega 3, las reglas del prompt con la frase de escape.

---

## Parte C — Coherencia e Informe

**C.1 — Enganche con la Entrega 1**

| Entrega 1 | Entrega 2 |
|---|---|
| PEAS, "Base de Conocimiento" (*hoy nada, a futuro índice vectorial recuperable por RAG*) | La colección ChromaDB con los 20 documentos limpios (22 registros de entrada menos 2 casi-duplicados purgados en B.5) |
| Matriz de Intenciones, campos de filtrado (*el filtro final por stock/activo sigue siendo SQL*) | Los `metadatos` usados como `where` |
| Lo que el LLM extraía del `texto_libre` | Alimenta la consulta semántica, se resuelve en el `where` |

La regla de oro sigue igual: el LLM no decide stock ni precio. La base vectorial da contexto, no autoridad.

**C.2 — El umbral de aceptación.** Oficial: **0,40** de similitud coseno (`UMBRAL_ACEPTACION` en `vector_db.py`), calibrado con `calibrar_umbral.py` y documentado en `docs-resultados/resultados_umbral.md`. Se midió el mejor puntaje de 18 consultas que EcoLogix sí puede responder y de 8 que no: las válidas dan `0,4095` o más, salvo una informal ("me devuelven la plata", `0,3317`); las fuera de catálogo que no se parecen a un producto dan `0,3839` como máximo. El punto medio de ese hueco es `0,40`. Con ese corte, las tres Killer Queries pasan y no se rechaza ninguna consulta válida más que con el `0,35` anterior (rechaza solo la informal). El margen del lado de las consultas válidas es de unos `0,01`, así que es un valor ajustado a este corpus, modelo y conjunto de consultas, y hay que repetir la calibración si cambia alguno. La regla es una sola y es semántica: el mejor resultado debe superar el umbral, y si no queda ninguna coincidencia por encima, la salida es vacía para que el sistema responda `no tengo esa información`; forzar el resultado más cercano sería alucinar. **No hay una segunda validación por palabras clave**: el filtro de dominio que se usó en `vector_db.py` se eliminó (ver B.4) porque, en la medición previa a quitarlo, rechazaba 7 de 8 consultas legítimas y solo frenaba 2 de 6 consultas fuera de catálogo. Verificado: la consulta relevante de la KQ1 devuelve `doc-005` con `0,620` y la consulta fuera de dominio de la KQ3 ("Venden celulares o accesorios de telefonia?") no devuelve nada (mejor puntaje `0,3735`, `similitud_ancla` `0,2852`). **Límite conocido:** consultas vecinas del dominio como "¿venden servilletas de papel reciclado?" (`0,54`) o "¿cuánto cuesta una caja de vasos?" (`0,61`) superan cualquier umbral razonable, porque la similitud mide cercanía de tema y no si el dato existe; esas las cubren el filtro de negocio dentro del `where` y, en la Entrega 3, el prompt con la frase de escape. `pipeline_vectorial.py`/FAISS sigue usando `umbral=0.25`, un valor distinto porque se calibró para ese índice específico y no para la recuperación híbrida del dominio.

**C.3 — Qué falta para cerrar el círculo.** `buscar()` devuelve un dict de Python, no una respuesta para el cliente. Falta el orquestador: algo que tome ese contexto + la consulta + el System Prompt de la Entrega 1, se lo pase al LLM para redactar la respuesta, y decida cuándo derivar a un humano. Eso es RAG con un framework tipo LangChain — Unidad 4, no esta entrega.
