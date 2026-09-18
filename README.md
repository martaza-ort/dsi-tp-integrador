# EcoLogix Systems — TP Integrador: del diagnóstico al conocimiento vectorial

**Asignatura:** Desarrollo de Sistemas de Inteligencia Artificial — IADS 3, ORT
**Grupo: 1**

## Integrantes — IADS 3, ORT — Grupo 1

| Integrante | ID de GitHub |
|---|---|
| Lucas Di Biase | `LDibiase` |
| Marta Artaza | `martaza-ort`, `martaza` |
| Facundo Folgueira | `Folguee` |
| Federico Cantero | `Fedoh` |
| Agustina Salatino | `agustinasalatino` |
| Gisella Aramayo | `giaramayo` |
| Lucía Lopez Guerrero | `LuciaLG1988` |

Las asignaciones de tareas y la distribución por integrante se encuentran en las hojas de ruta de la carpeta [`roadmaps/`](roadmaps/): [`TAREAS.md`](roadmaps/TAREAS.md) y [`TAREAS2.md`](roadmaps/TAREAS2.md).

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

## Descripción del repositorio

Este repositorio contiene el Proyecto Integrador de EcoLogix Systems para IADS 3, ORT.
El proyecto evoluciona por entregas: la Entrega 1 implementa un asistente híbrido de stock
y pedidos con LLM, Pydantic y SQL; la Entrega 2 agrega una base de conocimiento vectorial
con embeddings, FAISS, ChromaDB, filtros híbridos y purga semántica.

Esta sección y la tabla siguiente se actualizarán en cada nueva entrega o avance relevante
del proyecto.

## Árbol actual del repositorio

```text
.
├── .env.example
├── .gitignore
├── README.md
├── CLAUDE.md
├── requirements.txt
├── app.py
├── lote.py
├── schemas.py
├── schema.sql
├── test_schemas.py
├── base_conocimiento.json
├── base_conocimiento_limpia.json
├── etl_purga.py
├── similitud_coseno.py
├── construir_indice_faiss.py
├── pipeline_vectorial.py
├── vector_db.py
├── simular_evento_caliente.py
├── killer_queries.py
├── docs-resultados/
│   ├── resultados_a4.md
│   ├── resultados_etl.md
│   ├── resultados_evento_caliente.md
│   ├── resultados_killer_queries.md
│   ├── resultados_lote.md
│   └── resultados_lote_zero.md
├── informes/
│   ├── informe.md
│   └── informe_entrega2.md
├── roadmaps/
│   ├── TAREAS.md
│   └── TAREAS2.md
├── logs/                 # generado localmente, ignorado por Git
├── indice_faiss/         # generado localmente, ignorado por Git
└── chroma/               # generado localmente, ignorado por Git
```

## Estructura del repositorio

| Archivo o carpeta | Contenido | Entrega |
|---|---|---|
| `README.md` | Descripción, instalación, ejecución y estructura actual del proyecto. | General |
| `requirements.txt` | Dependencias de Entrega 1 y Entrega 2. | General |
| `.env.example` | Plantilla de variables de entorno sin secretos. | General |
| `.gitignore` | Exclusión de credenciales, logs y artefactos binarios. | General |
| `CLAUDE.md` | Contexto, invariantes y convenciones del proyecto. | General |
| `roadmaps/TAREAS.md` | Hoja de ruta y asignaciones de la Entrega 1. | Entrega 1 |
| `roadmaps/TAREAS2.md` | Hoja de ruta y asignaciones de la Entrega 2. | Entrega 2 |
| `app.py` | Pipeline con OpenAI, Structured Outputs, Pydantic y enrutamiento. | Entrega 1 |
| `schemas.py` | Contrato Pydantic V2 e intenciones cerradas. | Entrega 1 |
| `lote.py` | Lote de mensajes para evaluar el pipeline y prompting. | Entrega 1 |
| `schema.sql` | Esquema SQLite de clientes, productos, stock, pedidos y operaciones. | Entrega 1 |
| `test_schemas.py` | Tests del contrato Pydantic sin consumo de API. | Entrega 1 |
| `informes/informe.md` | Informe de diagnóstico, PEAS, intenciones y decisiones de la Entrega 1. | Entrega 1 |
| `docs-resultados/resultados_lote.md` | Evidencia del lote few-shot. | Entrega 1 |
| `docs-resultados/resultados_lote_zero.md` | Evidencia del lote zero-shot. | Entrega 1 |
| `base_conocimiento.json` | Corpus fuente del dominio y casos de prueba estructurales. | Entrega 2 |
| `base_conocimiento_limpia.json` | Corpus normalizado y purgado para indexación. | Entrega 2 |
| `etl_purga.py` | Normalización, resolución de IDs y purga semántica. | Entrega 2 |
| `docs-resultados/resultados_etl.md` | Reporte de correcciones y casi-duplicados eliminados. | Entrega 2 |
| `similitud_coseno.py` | Similitud coseno y generación de embeddings locales. | Entrega 2 |
| `construir_indice_faiss.py` | Construcción y persistencia del índice FAISS. | Entrega 2 |
| `pipeline_vectorial.py` | Consulta semántica reutilizable sobre FAISS. | Entrega 2 |
| `vector_db.py` | Colección ChromaDB persistente, `upsert` y filtros `where`. | Entrega 2 |
| `simular_evento_caliente.py` | Simulación de discontinuación y reemplazo de producto. | Entrega 2 |
| `docs-resultados/resultados_evento_caliente.md` | Evidencia del evento de negocio en caliente. | Entrega 2 |
| `killer_queries.py` | Ejecución de las tres consultas trampa. | Entrega 2 |
| `docs-resultados/resultados_killer_queries.md` | Evidencia y análisis de las Killer Queries. | Entrega 2 |
| `informes/informe_entrega2.md` | Informe, tablas B.2/B.6 y coherencia con la Entrega 1. | Entrega 2 |
| `logs/` | Registro local de interacciones; no se versiona. | General |
| `indice_faiss/` | Índice FAISS derivado; se reconstruye y no se versiona. | Entrega 2 |
| `chroma/` | Base persistente ChromaDB derivada; se reconstruye y no se versiona. | Entrega 2 |

## Instalación general

Requiere Python 3.10 o superior.

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Windows — PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación, puede ejecutarse el intérprete directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Consideraciones generales

### Variables de entorno (`.env`)

Copiar `.env.example` como `.env` y completar los valores localmente. El archivo `.env`
nunca debe commitearse.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | Sí para Entrega 1 con API | API key de OpenAI. |
| `OPENAI_MODEL` | No | Modelo usado por defecto: `gpt-4o-mini`. |
| `OPENAI_TIMEOUT` | No | Timeout por llamada; por defecto 30 segundos. |
| `UMBRAL_CONFIANZA` | No | Confianza mínima para no derivar a una persona; por defecto 0.60. |

La Entrega 2 usa embeddings locales con `sentence-transformers` y no necesita una API key
para generar el índice vectorial.

### Estados posibles del pipeline

`OK` · `VALIDATION_ERROR` · `REFUSAL` · `ERROR_SALIDA` · `ERROR_CREDENCIALES` ·
`ERROR_CUOTA` · `ERROR_RED` · `ERROR_PROVEEDOR` · `ERROR_INESPERADO`.

### Seguridad de credenciales

- `.env` está incluido en `.gitignore`; solo se versiona `.env.example` sin valores.
- No pegar claves en código, notebooks, informes, logs ni commits.
- Si una clave aparece en el historial, revocarla y generar una nueva; borrar el archivo no
  la elimina del historial de Git.
- `logs/`, `chroma/`, `indice_faiss/` y los archivos `.index` son artefactos locales ignorados.

## Instrucciones de ejecución por entrega

### Cómo correr — Entrega 1

Activar el entorno virtual y ejecutar:

```bash
# Validar el contrato sin consumir créditos
python -m pytest -q test_schemas.py

# Crear la base SQLite si se necesita probar el esquema
sqlite3 ecologix.db < schema.sql

# Ejecutar un mensaje
python app.py
python app.py "Buenas, mandame 20 cajas de vasos de bagazo 12oz para el jueves"
python app.py --tecnica zero "hola como viene el pedido #4521?"

# Ejecutar el lote few-shot y zero-shot
python lote.py
python lote.py --tecnica zero --salida docs-resultados/resultados_lote_zero.md
python lote.py --extra
```

En Windows, si `sqlite3` no está instalado, puede ejecutarse el script desde otra instalación
de SQLite o utilizarse el cliente SQLite disponible en el entorno local.

### Cómo correr — Entrega 2

Ejecutar en el entorno virtual:

```bash
# A.3/B.5: limpiar y purgar el corpus
python etl_purga.py

# A.2: validar similitud y embeddings
python similitud_coseno.py

# A.4/A.5: construir y persistir FAISS
python construir_indice_faiss.py
python pipeline_vectorial.py

# B.1/B.4: reconstruir ChromaDB y probar filtros nativos
python vector_db.py

# B.3: simular evento caliente y regenerar evidencia
python simular_evento_caliente.py
python simular_evento_caliente.py --restaurar

# B.6: ejecutar las tres Killer Queries y regenerar evidencia
python killer_queries.py
```

Los directorios `indice_faiss/` y `chroma/` son derivados. Se reconstruyen desde
`base_conocimiento.json` y no se incluyen en el repositorio.
