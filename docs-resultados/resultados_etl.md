# Reporte de ETL y purga semántica

## Resumen

- Documentos originales: 22
- Documentos limpios: 20
- Umbral de distancia coseno: `0.15`
- Regla: se conserva el primer documento válido y se elimina el posterior
  cuando la distancia coseno es menor o igual al umbral.

## Justificación y alcance del umbral

La distancia coseno se calcula como `1 - similitud`; por eso, el umbral `0.15` equivale a exigir similitud coseno >= `0.85`. Los casos positivos controlados corresponden a variantes del mismo producto: `doc-020` vs. `doc-019` (`0.0767`), `doc-021` vs. `doc-019` (`0.1298`). El duplicado con mayor distancia quedó en `0.1298`. El par diferente más cercano quedó en `0.2630`. La separación observada entre el duplicado más distante y el documento diferente más cercano es de `0.1332`. Por lo tanto, el umbral `0.15` conserva los documentos distintos medidos y elimina los casi duplicados sembrados. El valor sigue siendo específico de este corpus, del modelo de embeddings y del formato utilizado; deberá recalibrarse si cambia alguno de esos elementos.

## Correcciones estructurales

- doc-019: activo string -> booleano

## Colisiones de IDs resueltas

- doc-018 -> doc-018-dup-2

## Documentos eliminados

| Eliminado | Conservado | Distancia coseno | Motivo |
|---|---|---:|---|
| doc-020 | doc-019 | 0.0767 | casi-duplicado semántico |
| doc-021 | doc-019 | 0.1298 | casi-duplicado semántico |
## Pares diferentes más cercanos

Los siguientes documentos sobrevivieron a la purga. Se muestran los
pares con menor distancia para utilizarlos como ejemplos negativos y
comprobar que el umbral no elimina documentos diferentes pero
semánticamente relacionados.

| Documento A | Título A | Documento B | Título B | Distancia coseno |
|---|---|---|---|---:|
| doc-009 | Stock por depósito central | doc-010 | Reserva de stock al confirmar pedido | 0.2630 |
| doc-005 | Envases de cartón para alimentos | doc-013 | Bolsas de papel kraft para comercio | 0.2712 |
| doc-003 | Platos y bowls de bagazo | doc-005 | Envases de cartón para alimentos | 0.2717 |

## Por qué `SELECT DISTINCT` no alcanza

`SELECT DISTINCT` solo detectaría filas idénticas en todas sus columnas.
Los casi-duplicados tienen IDs, títulos, textos o tags diferentes, aunque
representen el mismo concepto del negocio. La distancia coseno compara el
significado de los embeddings y permite detectar esa equivalencia semántica.
