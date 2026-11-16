# Guía para levantar la API del agente EcoLogix

Guía paso a paso para ejecutar el sistema con el modelo real de Gemini y, si se
quiere, con trazas en LangSmith. Los comandos son de Windows PowerShell y se
ejecutan **desde la raíz del repositorio** (`dsi-tp-integrador`).

Contenido de esta carpeta:

| Archivo              | Para qué sirve                           |
| -------------------- | ----------------------------------------- |
| `GUIA.md`          | Esta guía.                               |
| `levantar_api.ps1` | Script que prepara todo y levanta la API. |

## 1. Requisitos

- Windows con PowerShell y Python 3.10 o superior (`py -3 --version`).
- Una cuenta de Google (para la clave de Gemini).
- Opcional: una cuenta de LangSmith (para las trazas).

## 2. Conseguir las claves (gratis)

### Gemini (Google AI Studio) → `GEMINI_API_KEY`

1. Entrá a [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) con tu cuenta de Google.
2. Tocá **Create API key** (pide elegir o crear un proyecto de Google Cloud).
3. Copiá la clave.

El modelo gratuito tiene límites de cuota por minuto y por día. Si aparece un
error de cuota, esperá un rato o repartí las corridas.

### LangSmith → `LANGSMITH_API_KEY` (opcional)

1. Entrá a [https://smith.langchain.com](https://smith.langchain.com) y creá una cuenta (el plan Developer es gratuito).
2. Andá a **Settings → API Keys** y creá una clave.
3. Elegí el nombre del proyecto en `LANGSMITH_PROJECT`; si no existe, se crea solo.

Si el grupo usa una cuenta o proyecto compartido, acuerden cuál para que las
trazas queden juntas.

> **Seguridad.** Las claves van **solo** en `.env`, que está en `.gitignore`.
> Nunca en el código, el informe ni los commits. Si una clave llega a un commit
> hay que revocarla y generar otra.

## 3. Configurar `.env`

Si todavía no existe, ejecutar el script (paso 4) lo crea desde `.env.example` y
se detiene. También se puede copiar a mano:

```powershell
Copy-Item .env.example .env
```

Generar el secreto de los hilos:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Completar en `.env`:

```text
RAG_PROVIDER=gemini
GEMINI_API_KEY=<tu clave de Google AI Studio>
GEMINI_MODEL=<modelo de Gemini, por ejemplo gemini-3.5-flash-lite>
API_CLIENTES=token-demo-cliente-1:1,token-demo-cliente-2:2
HILOS_SECRETO=<la salida del comando anterior>
```

Para activar las trazas de LangSmith agregar además:

```text
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<tu clave de LangSmith>
LANGSMITH_PROJECT=ecologix-tp-final
LANGSMITH_HIDE_INPUTS=true
LANGSMITH_HIDE_OUTPUTS=true
LANGSMITH_HIDE_METADATA=true
```

La API **se niega a arrancar** con el tracing activo si alguno de los tres
`LANGSMITH_HIDE_*` no está en `true`.

> **Ojo con las variables repetidas.** `.env.example` define
> `LANGSMITH_TRACING` y `LANGSMITH_PROJECT` más de una vez. Si en `.env` quedan
> duplicadas, suele ganar la última: verificá que no quede un
> `LANGSMITH_TRACING=false` más abajo pisando el `true`.

## 4. Levantar la API con el script

```powershell
.\ejecucion\levantar_api.ps1
```

Si PowerShell bloquea la ejecución:

```powershell
powershell -ExecutionPolicy Bypass -File .\ejecucion\levantar_api.ps1
```

Para otro puerto: `.\ejecucion\levantar_api.ps1 -Puerto 8080`.

El script, en orden:

1. Crea `.venv` e instala `requirements.txt` si no existe el entorno.
2. Si no hay `.env`, lo crea desde `.env.example` y se detiene (es normal: completalo y volvé a ejecutar). Verifica que `GEMINI_API_KEY`, `API_CLIENTES` y `HILOS_SECRETO` tengan valor.
3. Construye el índice RAG si falta la carpeta `chroma/` (tarda unos minutos).
4. Crea la base de demo `runtime\ecologix.db` si no existe.
5. Levanta `uvicorn` en un solo proceso (no usar `--workers`: la memoria SQLite no lo admite).

Cuando termina, la API queda en `http://127.0.0.1:8000` y la documentación
interactiva en `http://127.0.0.1:8000/docs`. Se detiene con `Ctrl+C`.

## 5. Comprobar que funciona

En otra terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Debe devolver `estado: ok`, `agente: True` y `memoria: True`.

Una consulta de prueba:

```powershell
$headers = @{ Authorization = "Bearer token-demo-cliente-1" }
$body = @{ mensaje = "¿En qué estado está mi pedido 101?"; thread_id = "demo-1" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/consultar `
  -Headers $headers -ContentType "application/json; charset=utf-8" -Body $body

Invoke-RestMethod http://127.0.0.1:8000/estado/demo-1 -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/metricas
```

El resto de los ejemplos (borrado, bloqueos de seguridad, memoria tras
reiniciar) están en el `README.md`, sección "API del agente", y el guion de la
demo en `roadmaps/GUION-DEFENSA.md`.

## 6. Problemas frecuentes

| Síntoma                                   | Causa probable                          | Qué hacer                                              |
| ------------------------------------------ | --------------------------------------- | ------------------------------------------------------- |
| "Se creó .env a partir de .env.example…" | Primera ejecución sin `.env`.        | Es lo esperado: completar `.env` y volver a ejecutar. |
| "Falta completar X en .env"                | Variable vacía o ausente.              | Completarla.                                            |
| Error por `HILOS_SECRETO`                | Menos de 32 caracteres.                 | Generar uno con `secrets.token_hex(32)`.              |
| La API no arranca con LangSmith            | Falta algún `LANGSMITH_HIDE_*=true`. | Poner los tres en `true`.                             |
| Error de cuota o 429 del modelo            | Límite del plan gratuito.              | Esperar y reintentar.                                   |
| Falla al construir el índice              | `chroma/` quedó a medias.            | Borrar la carpeta `chroma/` y volver a ejecutar.      |
| Acentos rotos en la consola                | Codificación de la consola.            | Probar en Windows Terminal o `chcp 65001`.            |
| El script no se puede ejecutar             | Política de ejecución de PowerShell.  | Usar el comando con `-ExecutionPolicy Bypass`.        |
