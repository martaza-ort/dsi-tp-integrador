# Reporte de ETL y purga semántica

## Resumen

- Documentos originales: 22
- Documentos limpios: 20
- Umbral de distancia coseno: `0.15`
- Regla: se conserva el primer documento válido y se elimina el posterior
  cuando la distancia coseno es menor o igual al umbral.

## Correcciones estructurales

- doc-019: activo string -> booleano

## Colisiones de IDs resueltas

- doc-018 -> doc-018-dup-2

## Documentos eliminados

| Eliminado | Conservado | Distancia coseno | Motivo |
|---|---|---:|---|
| doc-020 | doc-019 | 0.144 | casi-duplicado semántico |
| doc-021 | doc-019 | 0.1177 | casi-duplicado semántico |

## Por qué `SELECT DISTINCT` no alcanza

`SELECT DISTINCT` solo detectaría filas idénticas en todas sus columnas.
Los casi-duplicados tienen IDs, títulos, textos o tags diferentes, aunque
representen el mismo concepto del negocio. La distancia coseno compara el
significado de los embeddings y permite detectar esa equivalencia semántica.
