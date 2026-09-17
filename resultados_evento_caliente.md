# Evento de negocio en caliente — EcoLogix

## Evento simulado

Cambio de politica comercial y de oferta de EcoLogix:

1. **Revalidacion del catalogo**: todos los productos pasan a tener
   metadata de estado `estado: "activo"` (mantenimiento del stock).
2. Los **sorbetes de papel** (`doc-004`) se **discontinuan** por la
   nueva politica ambiental: su texto pasa a indicar que el producto
   queda fuera de catalogo y su metadata se marca
   `estado: "discontinuado"`.
3. Entra en catalogo el reemplazo activo, los **sorbetes compostables
   de bagazo** (`doc-019`, SKU `ECO-SOR-BAGAZO`), con
   `estado: "activo"`.

Los cambios se aplican en caliente con `upsert` de ChromaDB, solo
sobre los documentos afectados, sin reconstruir toda la base.

## Consulta utilizada

> Necesito sorbetes para mi kiosco, que esten disponibles en stock

## Resultados antes del evento (corpus original)

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-004 | Sorbetes de papel | 0.4616 |
| 2 | doc-001 | Bolsas compostables 40x50 cm | 0.432 |
| 3 | doc-002 | Vasos de bagazo 12 oz | 0.4297 |
| 4 | doc-013 | Bolsas de papel kraft para comercio | 0.4278 |
| 5 | doc-005 | Envases de cartón para alimentos | 0.4003 |

## Resultados despues del evento (sin filtro)

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-001 | Bolsas compostables 40x50 cm | 0.432 |
| 2 | doc-002 | Vasos de bagazo 12 oz | 0.4297 |
| 3 | doc-013 | Bolsas de papel kraft para comercio | 0.4278 |
| 4 | doc-019 | Sorbetes compostables de bagazo | 0.4277 |
| 5 | doc-005 | Envases de cartón para alimentos | 0.4003 |

## Resultados despues del evento (filtro nativo `categoria=sorbetes` + `estado=activo`)

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-019 | Sorbetes compostables de bagazo | 0.4277 |

## Persistencia del nuevo estado

Con un cliente ChromaDB nuevo se reconsulto la misma consulta con el
filtro `categoria=sorbetes` + `estado=activo` y el ranking se mantuvo
identico:

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-019 | Sorbetes compostables de bagazo | 0.4277 |

## Analisis

El estado dinamico del negocio impacta de dos maneras sobre la
recuperacion vectorial:

- **Semantica**: tras el evento, `doc-004` (discontinuado) cae del
  primer puesto del ranking aunque no exista filtro, porque su
  contenido ahora describe un producto fuera de catalogo. El
  reemplazo activo `doc-019` entra en el top de resultados.
- **Reglas de negocio via filtros nativos**: con el filtro nativo
  `where={"categoria": "sorbetes", "estado": "activo"}` aplicado en
  la base (sin post-filtering), el producto discontinuado queda
  garantizado fuera de toda recomendacion, y para la consulta de
  sorbetes el resultado correcto (`doc-019`) lidera la recuperacion.
- El cambio de estado (stock/politica) se propaga a la busqueda
  reindexando solo los documentos afectados con `upsert`, sin
  reindexar el corpus completo.

## Regeneracion

La base persistente se reconstruye desde `base_conocimiento.json`
con `vector_db.py`. Para volver al estado original de este
experimento: `python simular_evento_caliente.py --restaurar`.
