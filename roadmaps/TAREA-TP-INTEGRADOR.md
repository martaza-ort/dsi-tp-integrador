# TP Final Integrador — Agente Inteligente en Producción
Asignatura: Desarrollo de Sistemas de Inteligencia Artificial (IADS 3) · Modalidad: grupal, mismo repositorio · Entrega y defensa: 16 de noviembre

## De qué se trata

El TP Final integra la unidad 5 y 6 en un único sistema. Tomen el RAG de la Entrega 3 y conviértanlo en un agente con LangGraph que decide solo qué herramientas usar, recuerda la conversación y queda expuesto como una API REST observable y protegida con guardrails. El trabajo cierra con una ficha técnica y una defensa en vivo.

## Qué tienen que construir

| Parte | Qué se pide |
|---|---|
|A. Agente|	≥3 herramientas (el retriever de la E3, un sensor y un actuador del dominio) con docstrings completos; grafo ReAct con límite de iteraciones; memoria SQLite persistente por thread_id; matriz de validación con 4 escenarios.|
|B. API REST|	FastAPI con GET /health, POST /consultar y GET /estado/{thread_id}; memoria demostrada vía HTTP, incluso después de reiniciar; el sistema debe levantar en otra máquina siguiendo solo el README.|
|C. Observabilidad|Logs JSON, endpoint GET /metricas (consultas, errores, latencia promedio y p95, herramientas, bloqueos) y trazas en LangSmith con análisis de costos.|
|D. Seguridad|	≥2 validators de input (prompt injection y longitud) y ≥1 de output (enmascarado de datos personales), integrados en /consultar; suite automática de ≥4 tests|
|E. Cierre|Ficha técnica del sistema y defensa en vivo de 15 minutos (presentación, demo y preguntas).|

## Qué se entrega

El link al repositorio público a la rama main o master: código del agente y de la API, security_tests.py, requirements.txt, .env.example, README.md, .gitignore, informe.md y ficha_tecnica.md

