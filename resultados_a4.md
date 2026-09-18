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
| 1 | doc-019 | Vasos compostables para cafe | 0.6957 | 0.3043 |
| 2 | doc-014 | Cubiertos y utensilios de bioplástico | 0.5775 | 0.4225 |
| 3 | doc-001 | Bolsas compostables 40x50 cm | 0.4998 | 0.5002 |
### CREAR_PEDIDO

> Quiero encargar dos cajas de bolsas compostables para mi súper

| Puesto | Id | Documento | Score | Distancia |
|--------|----|-----------|-------|-----------|
| 1 | doc-001 | Bolsas compostables 40x50 cm | 0.7775 | 0.2225 |
| 2 | doc-019 | Vasos compostables para cafe | 0.5999 | 0.4001 |
| 3 | doc-006 | Limpieza ecológica concentrada | 0.5689 | 0.4311 |
### RECLAMO_ENTREGA

> Se rompieron varios envases de cartón en la entrega, quiero reclamar

| Puesto | Id | Documento | Score | Distancia |
|--------|----|-----------|-------|-----------|
| 1 | doc-012 | Reclamos por productos rotos o faltantes | 0.6942 | 0.3058 |
| 2 | doc-016 | Pedidos multitema y confirmación previa | 0.4669 | 0.5331 |
| 3 | doc-005 | Envases de cartón para alimentos | 0.4393 | 0.5607 |

## Reactivación

```powershell
venv\Scripts\python.exe construir_indice_faiss.py
venv\Scripts\python.exe reporte_a4.py
```
