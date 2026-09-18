# EcoLogix Systems — TP Integrador (Entrega 1): Del diagnóstico al pipeline validado

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial — IADS 3, ORT
**Grupo: 1**

- Lucas Di Biase — `LDibiase` — Parte C: pipeline, lote y prompting (T-06, T-07)
- Marta Artaza — `martaza-ort` — T-04: riesgo de `SEGUIMIENTO_PEDIDO`
- Facundo Folgueira — `Folguee` — T-02: evidencia A.2, segundo modelo
- Federico Cantero — `Fedoh` — T-01: evidencia A.2, primer modelo
- Agustina Salatino — `agustinasalatino` — T-05: fundamento de los tres umbrales
- Gisella Aramayo — `giaramayo` — T-10: costo en dólares
- Lucía Lopez Guerrero — `LuciaLG1988` — T-03: hipótesis más riesgosa

## Dominio elegido

**EcoLogix Systems** es una distribuidora mediana de productos ecológicos y biodegradables
(bolsas compostables, vajilla de bagazo, sorbetes de papel, envases de cartón, limpieza
ecológica) que vende a comercios y mayoristas. Hoy los pedidos y consultas llegan por
WhatsApp y mail en texto libre y se transcriben a mano a planillas desconectadas
(ventas y almacén): se vende sin stock, se factura mal y nadie sabe dónde está un envío.

El sistema que diseñamos es un **asistente de stock y pedidos**: un normalizador semántico
(LLM) convierte cada mensaje en una intención + parámetros validados con Pydantic, y un
backend determinista (SQL) resuelve contra el stock y los pedidos reales.

Intenciones (árbol cerrado): `CONSULTA_STOCK` · `CREAR_PEDIDO` · `SEGUIMIENTO_PEDIDO` ·
`RECLAMO_ENTREGA` · `OTRO`.

## Estructura del repo

| Archivo | Contenido |
|---|---|
| `TAREAS.md` | Hoja de ruta: setup, reparto de tareas y reglas de trabajo del grupo |
| `informe.md` | Informe completo: Partes A, B y C + decisiones de diseño |
| `schemas.py` | Contrato Pydantic V2 (`Literal`, validadores, modelo anidado) — C.1 |
| `app.py` | Pipeline con API real + Structured Outputs + manejo de errores separado — C.2 |
| `lote.py` | Corre los 6 inputs del dominio y genera `resultados_lote.md` — C.3 |
| `resultados_lote.md` | Tabla de resultados del lote |
| `schema.sql` | Esquema SQL completo (SQLite), incluida la tabla `interacciones` — B.5b |
| `test_schemas.py` | 12 tests del contrato que no consumen API |
| `.env.example` | Variables de entorno sin valores |
| `.gitignore` | Incluye `.env` y `logs/` |
| `CLAUDE.md` | Contexto del proyecto para trabajar con Claude Code |

## Cómo correr

Requiere Python 3.10+.

```bash
# 1. Crear entorno e instalar dependencias
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Credenciales (NUNCA se commitean)
cp .env.example .env
#    editar .env y pegar la key en OPENAI_API_KEY

# 3. Probar el contrato sin gastar créditos
python -m pytest -q test_schemas.py

# 4. Correr un mensaje (usa uno de ejemplo si no se pasa texto)
python app.py
python app.py "Buenas, mandame 20 cajas de vasos de bagazo 12oz para el jueves"
python app.py --tecnica zero "hola como viene el pedido #4521?"

# 5. Correr el lote de 6 inputs y generar la tabla de C.3
python lote.py                                                    # few-shot -> resultados_lote.md
python lote.py --tecnica zero --salida resultados_lote_zero.md    # para comparar en C.4
python lote.py --extra                                            # suma 2 casos opcionales
```

> En macOS/Linux, si `python` no existe en el PATH usar `python3` en los pasos 1 y 3-5.
> Entorno verificado: Python 3.14.6 — `pytest -q test_schemas.py` da **12 passed**,
> `sqlite3 ecologix.db < schema.sql` crea las 9 tablas, y `app.py`/`lote.py` importan
> sin `.env` (toman los defaults). Los pasos 1 a 3 no consumen créditos de API.

Cada corrida se registra en `logs/interacciones.jsonl` (ignorado por Git).

### Variables de entorno (`.env`)

| Variable | Obligatoria | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | sí | API key de OpenAI |
| `OPENAI_MODEL` | no | Modelo a usar (default `gpt-4o-mini`) |
| `OPENAI_TIMEOUT` | no | Timeout en segundos por llamada (default 30) |
| `UMBRAL_CONFIANZA` | no | Confianza mínima para no derivar a humano (default 0.60) |

### Estados posibles del pipeline

`OK` · `VALIDATION_ERROR` (el JSON violó el contrato Pydantic) · `REFUSAL` (el modelo se negó) ·
`ERROR_SALIDA` (truncada/filtrada) · `ERROR_CREDENCIALES` · `ERROR_CUOTA` · `ERROR_RED` ·
`ERROR_PROVEEDOR` · `ERROR_INESPERADO`.

## Seguridad de credenciales

- `.env` está en `.gitignore` desde el primer commit. Solo se sube `.env.example`.
- Si una key se filtró en un commit, **rotarla** (darla de baja y generar una nueva); borrar el
  archivo no alcanza porque queda en el historial.

---

## Entrega 2 — De contexto estático a conocimiento vectorial

Segundo paso del Proyecto Integrador: se indexa el dominio de EcoLogix con FAISS y se migra a una
base vectorial persistente con ChromaDB, con filtrado híbrido (similitud + reglas de negocio vía
`where`). Detalle completo, evidencia y decisiones en [`informe_entrega2.md`](informe_entrega2.md).

| Archivo | Contenido |
|---|---|
| `base_conocimiento.json` | Corpus del dominio: 18 documentos (productos, políticas, operativa) con texto y metadatos. |
| `etl_purga.py` | Normaliza y limpia el corpus → `base_conocimiento_limpia.json`. |
| `similitud_coseno.py` | Similitud coseno calculada a mano con NumPy + generación de embeddings locales (`sentence-transformers`). |
| `construir_indice_faiss.py` | Construye y persiste el índice FAISS (`indice_faiss/`, no se commitea). |
| `pipeline_vectorial.py` | Consulta semántica sobre el índice FAISS, enriquecida por intención de negocio. |
| `vector_db.py` | Migración a ChromaDB persistente (`chroma/`, no se commitea): `upsert`, búsqueda con filtros nativos `where`. |
| `simular_evento_caliente.py` | Simula un cambio real de catálogo (producto discontinuado + reemplazo) y prueba que la recuperación lo refleja. |
| `resultados_evento_caliente.md` | Evidencia real de la simulación anterior. |
| `informe_entrega2.md` | Informe final: autopsia del contexto estático, coherencia con el PEAS y la Matriz de Intenciones de la Entrega 1, umbral de aceptación y pendientes. |
| `killer_queries.py` | Corre las 3 Killer Queries de C.3 contra ChromaDB y regenera `resultados_killer_queries.md`. |
| `resultados_killer_queries.md` | Evidencia real de las 3 Killer Queries (C.3), con el umbral de aceptación justificado con datos. |

### Cómo correr (Entrega 2)

```bash
pip install -r requirements.txt        # suma numpy, faiss-cpu, sentence-transformers, chromadb

python etl_purga.py                    # genera base_conocimiento_limpia.json
python similitud_coseno.py             # similitud coseno a mano, validación con NumPy
python construir_indice_faiss.py       # arma y persiste el índice FAISS en indice_faiss/
python pipeline_vectorial.py           # consulta interactiva sobre el índice FAISS

python vector_db.py                    # migra el corpus a ChromaDB (chroma/) y corre búsquedas con where
python simular_evento_caliente.py      # simula el evento de negocio y regenera resultados_evento_caliente.md
python simular_evento_caliente.py --restaurar   # vuelve la base al corpus original

python killer_queries.py               # corre las 3 killer queries de C.3 y regenera resultados_killer_queries.md
```

> `indice_faiss/` y `chroma/` son binarios derivados: no se commitean (`.gitignore`) y se
> reconstruyen desde `base_conocimiento.json` corriendo los scripts de arriba.
