# Búsqueda top-K del índice FAISS — A.4

Log de las 3 consultas de prueba sobre el índice persistido.

- Modelo de embeddings: `paraphrase-multilingual-MiniLM-L12-v2` (local).
- Índice: `indice_faiss/ecologix.index`, IndexFlatIP sobre vectores
  L2-normalizados (producto interno = similitud coseno).
- Forma: 20 vectores, dimensión 384. La cantidad de
  vectores surge de ejecutar `python construir_indice_faiss.py`; el
  `score` es la similitud devuelta por `pipeline_vectorial.py` con
  umbral 0,25 y la `distancia` se reporta como `1 - score`
  (distancia coseno).

## Consultas

### CONSULTA_STOCK

> Tenés vasos biodegradables para una cafetería

| Puesto | Id | Documento | Score | Distancia |
|--------|----|-----------|-------|-----------|
| 1 | doc-019 | Vasos compostables para cafe | 0.6717 | 0.3283 |
| 2 | doc-014 | Cubiertos y utensilios de bioplástico | 0.5643 | 0.4357 |
| 3 | doc-004 | Sorbetes de papel | 0.553 | 0.447 |
### CREAR_PEDIDO

> Quiero encargar dos cajas de bolsas compostables para mi súper

| Puesto | Id | Documento | Score | Distancia |
|--------|----|-----------|-------|-----------|
| 1 | doc-001 | Bolsas compostables 40x50 cm | 0.7159 | 0.2841 |
| 2 | doc-019 | Vasos compostables para cafe | 0.6348 | 0.3652 |
| 3 | doc-017 | Jerga comercial del dominio | 0.6161 | 0.3839 |
### RECLAMO_ENTREGA

> Se rompieron varios envases de cartón en la entrega, quiero reclamar

| Puesto | Id | Documento | Score | Distancia |
|--------|----|-----------|-------|-----------|
| 1 | doc-012 | Reclamos por productos rotos o faltantes | 0.7565 | 0.2435 |
| 2 | doc-018 | Derivación a humano cuando no hay certeza | 0.4823 | 0.5177 |
| 3 | doc-016 | Pedidos multitema y confirmación previa | 0.4631 | 0.5369 |

## Reactivación

```powershell
venv\Scripts\python.exe construir_indice_faiss.py
venv\Scripts\python.exe reporte_a4.py
```
