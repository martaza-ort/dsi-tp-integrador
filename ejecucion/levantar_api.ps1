# Levanta la API del agente EcoLogix (Windows PowerShell).
# Uso (desde la raíz del repositorio):
#       .\ejecucion\levantar_api.ps1            (puerto 8000)
#       .\ejecucion\levantar_api.ps1 -Puerto 8080
# Si PowerShell bloquea el script:
#       powershell -ExecutionPolicy Bypass -File .\ejecucion\levantar_api.ps1
param(
    [int]$Puerto = 8000
)

$ErrorActionPreference = "Stop"
# El script vive en ejecucion/; el trabajo se hace desde la raíz del repo.
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location -Path $raiz

function Fallar($mensaje) {
    Write-Host "ERROR: $mensaje" -ForegroundColor Red
    exit 1
}

# 1. Entorno virtual (se crea e instala solo la primera vez)
$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creando entorno virtual e instalando dependencias..." -ForegroundColor Cyan
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fallar "No se pudo crear el entorno virtual (¿está instalado Python 3?)." }
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Fallar "Falló la instalación de dependencias." }
}

# 2. .env con las variables obligatorias
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Fallar "Se creó .env a partir de .env.example. Completalo (GEMINI_API_KEY, API_CLIENTES, HILOS_SECRETO) y volvé a ejecutar."
}
$contenidoEnv = Get-Content ".env" -Raw
foreach ($variable in @("GEMINI_API_KEY", "API_CLIENTES", "HILOS_SECRETO")) {
    if ($contenidoEnv -notmatch "(?m)^\s*$variable\s*=\s*\S+") {
        Fallar "Falta completar $variable en .env."
    }
}

# 3. Índice RAG (solo si no existe)
if (-not (Test-Path "chroma")) {
    Write-Host "Construyendo el índice RAG (puede tardar unos minutos)..." -ForegroundColor Cyan
    & $python vector_db.py
    if ($LASTEXITCODE -ne 0) { Fallar "Falló vector_db.py." }
    & $python -m entrega_3.indexar_chunks
    if ($LASTEXITCODE -ne 0) { Fallar "Falló entrega_3.indexar_chunks." }
}

# 4. Base de negocio de demo (solo si no existe, para no pisar datos)
if (-not (Test-Path "runtime\ecologix.db")) {
    Write-Host "Creando la base de negocio de demo..." -ForegroundColor Cyan
    & $python inicializar_base_demo.py
    if ($LASTEXITCODE -ne 0) { Fallar "Falló inicializar_base_demo.py." }
}

# 5. API (un solo proceso: la memoria SQLite no admite varios workers)
Write-Host "API en http://127.0.0.1:$Puerto  (docs: /docs). Ctrl+C para detener." -ForegroundColor Green
& $python -m uvicorn api:app --host 127.0.0.1 --port $Puerto
