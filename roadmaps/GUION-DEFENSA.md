# Guion de defensa — TP Final Integrador (15 minutos)

Formato: presentación + demo + preguntas. Los tiempos son una propuesta; el
reparto entre integrantes queda para que el grupo lo defina.

## Distribución del tiempo

| Min | Bloque | Contenido |
|---|---|---|
| 0–1 | Problema | EcoLogix: consultas por WhatsApp/mail, envíos sin seguimiento. Del RAG de la E3 a un agente en producción. |
| 1–4 | Arquitectura | Diagrama del informe: API → guardrails → grafo ReAct → 3 herramientas → memoria → enmascarado. Decisiones: `cliente_id` por contexto confiable, 5 ciclos, 1 tool por decisión. |
| 4–10 | **Demo en vivo** | Ver guion abajo. |
| 10–12 | Observabilidad y costos | `/metricas`, logs JSON, traza LangSmith con inputs/outputs ocultos, costo por consulta (≈ USD 0.0014 equivalente; USD 0 en nivel gratuito). |
| 12–13 | Validación y limitaciones | Ejecución real 16/16 (`docs-resultados/resultados_ejecucion_real.md`), 88 tests solo como regresión; limitaciones honestas (auth de demo, heurística, un proceso). |
| 13–15 | Preguntas | Ver lista probable. |

## Guion de la demo

Preparación previa (antes de entrar): entorno activo, `.env` completo, índice RAG
construido, `python inicializar_base_demo.py` corrido, `uvicorn` levantado, una
terminal con `$headers` listo (README, sección API). Tener un plan B: la evidencia de
`docs-resultados/resultados_ejecucion_real.md` y las capturas de LangSmith
(`evidencias/langsmith/`). El recorrido completo se puede repetir con
`python ejecucion/recorrido_real.py --fase 1` (y `--fase 2` tras reiniciar la API).
Si la base de demo ya tiene reclamos de una corrida anterior, recrearla con
`python inicializar_base_demo.py --forzar` (con la API detenida).

1. `GET /health` → agente y memoria en `true`.
2. **RAG:** consulta comercial (por ejemplo zonas de entrega) con `thread_id` `demo-1` → `herramientas_utilizadas` incluye `buscar_conocimiento_ecologix`.
3. **Sensor:** "¿En qué estado está mi pedido 101?" con el token del cliente 1 → estado del envío.
4. **Autorización:** mismo pedido con el token del cliente 2 → respuesta neutra, sin filtrar existencia.
5. **Actuador:** registrar un reclamo sobre un pedido propio → ID y estado `ABIERTO`; luego sobre un pedido ajeno → rechazo.
6. **Memoria:** `GET /estado/demo-1` → historial; cortar `uvicorn` con Ctrl+C, relanzar, `GET /estado/demo-1` → el historial sigue.
7. **Guardrails:** consulta con "Ignorá todas tus instrucciones anteriores…" → `exito: false`, sin herramientas; consulta de más de 1000 caracteres → `400`; respuesta con un DNI o email → enmascarado.
8. `GET /metricas` → consultas, bloqueadas, herramientas, latencia (p95 `null` hasta 20 muestras: explicarlo).
9. `DELETE /estado/demo-1` y `GET` → 404.

Si falla la red o la cuota del modelo: mostrar los pasos 1, 6 (con tests), 7 y 8,
que no dependen del proveedor para los bloqueos, y señalar los tests como evidencia.

## Preguntas probables y respuesta corta

- **¿Por qué el LLM no recibe el `cliente_id`?** Para que no pueda elegirlo ni falsearlo; llega por contexto de ejecución, no entra al estado ni a los checkpoints, y cada herramienta verifica propiedad contra la base.
- **¿El filtro de prompt injection es suficiente?** No. Es heurístico y complementario; la defensa real es la autorización determinista dentro de las herramientas.
- **¿Qué pasa si el agente pide varias herramientas a la vez o entra en bucle?** Se rechazan las llamadas paralelas y se corta a los 5 ciclos, sin afirmar que lo pendiente se hizo.
- **¿Cómo se protege la privacidad en logs y trazas?** Logs sin texto ni identificadores; LangSmith con inputs, outputs y metadatos ocultos, y la app no inicia el tracing si alguno de los tres controles está apagado.
- **¿Qué pasa con los datos al borrar o a los 30 días?** Se borra el hilo completo vía API del checkpointer; la purga es lógica, no sobrescribe páginas ni toca backups. Reclamos y pedidos tienen otro ciclo de vida, pendiente de definición comercial y legal.
- **¿Escala a varios workers?** No en esta versión: memoria SQLite, purga y métricas en memoria asumen un proceso.
- **¿Por qué `/metricas` no tiene autenticación?** Limitación declarada: no expone contenido ni identidades, pero en producción se protege o se limita a red interna.
- **¿De dónde sale el p95 y por qué 20 muestras?** Rango más próximo sobre las latencias acumuladas; 20 es un mínimo inicial por calibrar.
- **¿Cuánto cuesta?** Dos solicitudes medidas: unos USD 0.0014 por consulta a tarifa paga; cargo real USD 0 por nivel gratuito. No es proyección de producción.

## Checklist previo a la entrega (E.3 y E.4)

- [ ] Archivos presentes: código del agente y la API, `security_tests.py`, `requirements.txt`, `.env.example`, `README.md`, `.gitignore`, `informes/informe-entrega-04.md`, `ficha_tecnica.md`.
- [ ] `python -m pytest -q` en un entorno limpio → todo en verde.
- [ ] README seguido desde cero en otra máquina (o compañero) hasta `/health`.
- [ ] Sin secretos en el repo ni en el historial (`.env`, claves, `runtime/`, `*.sqlite`).
- [ ] Repositorio **público**, rama `main` o `master` con todo mergeado, y docente como colaborador si corresponde.
- [ ] Commits con autoría real de cada integrante.
- [ ] Ensayo cronometrado de la presentación (≤ 15 min).
