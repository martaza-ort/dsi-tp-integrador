# Evento de negocio en caliente — EcoLogix

## Evento simulado

Cambio de politica comercial y de oferta de EcoLogix:

1. **Revalidacion del catalogo**: todos los productos pasan a tener
    metadata `activo: true` (mantenimiento del stock).
2. Los **sorbetes de papel** (`doc-004`) se **discontinuan** por la
   nueva politica ambiental: su texto pasa a indicar que el producto
   queda fuera de catalogo y su metadata se marca
    `activo: false`.
3. Entra en catalogo el reemplazo activo, los **sorbetes compostables
   de bagazo** (`doc-022`, SKU `ECO-SOR-BAGAZO`), con
    `activo: true`.

Los cambios se aplican en caliente con `upsert` de ChromaDB, solo
sobre los documentos afectados, sin reconstruir toda la base.

## Consulta utilizada

> Necesito sorbetes para mi kiosco, que esten disponibles en stock

## Resultados antes del evento (corpus original)

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-004 | Sorbetes de papel | 0.4631 |
| 2 | doc-019 | Vasos compostables para cafe | 0.4599 |
| 3 | doc-013 | Bolsas de papel kraft para comercio | 0.4309 |
| 4 | doc-017 | Jerga comercial del dominio | 0.4106 |

## Resultados despues del evento (sin filtro)

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-019 | Vasos compostables para cafe | 0.4599 |
| 2 | doc-013 | Bolsas de papel kraft para comercio | 0.4309 |
| 3 | doc-022 | Sorbetes compostables de bagazo | 0.4277 |
| 4 | doc-017 | Jerga comercial del dominio | 0.4106 |

## Resultados despues del evento (filtro nativo `activo=true`)

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-022 | Sorbetes compostables de bagazo | 0.4277 |

## Verificacion con `coleccion.get()`

Con un cliente ChromaDB nuevo, `coleccion.get(ids=["doc-004", "doc-022"])`
devuelve el estado que quedo guardado en disco tras el `upsert`:

| Id | Titulo | Categoria | SKU | activo |
|----|--------|-----------|-----|--------|
| doc-004 | Sorbetes de papel | sorbetes | ECO-SOR-PAP | False |
| doc-022 | Sorbetes compostables de bagazo | sorbetes | ECO-SOR-BAGAZO | True |

`doc-004` quedo con `activo=False` y `doc-022` existe con `activo=True`.

## Por que `upsert` y no `add` ni `update`

`add` no sirve para re-ejecutar el evento: con un id que ya existe no
lo modifica (lo ignora o falla segun la version), asi que `doc-004` no
quedaria discontinuado. `update` falla con un id que no existe, y
`doc-022` es un alta. `upsert` hace las dos cosas en la misma llamada
(modifica `doc-004` y crea `doc-022`) y es idempotente, asi que el
script se puede correr mas de una vez sin duplicar ni romper nada.

## Persistencia del nuevo estado

Con un cliente ChromaDB nuevo se reconsulto la misma consulta con el
filtro `activo=true` y el ranking se mantuvo identico:

| Puesto | Id | Documento | Similitud |
|--------|----|-----------|-----------|
| 1 | doc-022 | Sorbetes compostables de bagazo | 0.4277 |

## Analisis

El estado dinamico del negocio impacta de dos maneras sobre la
recuperacion vectorial:

- **Semantica**: tras el evento, `doc-004` (discontinuado) cae del
  primer puesto del ranking aunque no exista filtro, porque su
  contenido ahora describe un producto fuera de catalogo. El
  reemplazo activo `doc-022` entra en el top de resultados.
- **Reglas de negocio via filtros nativos**: con el filtro
    `where={"activo": true}` aplicado en la base (sin
  post-filtering), el producto discontinuado queda garantizado fuera
  de toda recomendacion, y para la consulta de sorbetes el resultado
  correcto (`doc-022`) lidera la recuperacion.
- El cambio de estado (stock/politica) se propaga a la busqueda
  reindexando solo los documentos afectados con `upsert`, sin
  reindexar el corpus completo.

## Regeneracion

La base persistente se reconstruye desde `base_conocimiento.json`
con `vector_db.py`. Para volver al estado original de este
experimento: `python simular_evento_caliente.py --restaurar`.
