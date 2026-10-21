# Reporte de ETL y purga semántica

## Resumen

- Documentos originales: 22
- Documentos limpios: 20
- Umbral de distancia coseno: `0.15`
- Regla: se conserva el primer documento válido y se elimina el posterior
  cuando la distancia coseno es menor o igual al umbral.

## Justificación y alcance del umbral

La distancia coseno se calcula como `1 - similitud`; por eso, el umbral `0.15` equivale a exigir similitud coseno >= `0.85`. En este corpus, los dos casos controlados corresponden a variantes del mismo producto (vasos de bagazo de 12 oz): `doc-020` vs. `doc-019` (`0.0767`), `doc-021` vs. `doc-019` (`0.1298`). El mayor valor observado es `0.1298`; el corte queda `0.0202` por encima y captura ambos. Este margen describe el ajuste a los ejemplos sembrados, no una frontera universal de duplicidad. Como todavía no hay pares negativos etiquetados, no se puede estimar la tasa de falsos positivos ni afirmar que el valor sea óptimo. Se considera un umbral inicial para este corpus, modelo y formato de texto; antes de ampliarlo conviene evaluarlo con pares positivos y negativos revisados, medir falsos positivos y falsos negativos, y recalibrarlo.

## Correcciones estructurales

- doc-019: activo string -> booleano

## Colisiones de IDs resueltas

- doc-018 -> doc-018-dup-2

## Documentos eliminados

| Eliminado | Conservado | Distancia coseno | Motivo |
|---|---|---:|---|
| doc-020 | doc-019 | 0.0767 | casi-duplicado semántico |
| doc-021 | doc-019 | 0.1298 | casi-duplicado semántico |

## Por qué `SELECT DISTINCT` no alcanza

`SELECT DISTINCT` solo detectaría filas idénticas en todas sus columnas.
Los casi-duplicados tienen IDs, títulos, textos o tags diferentes, aunque
representen el mismo concepto del negocio. La distancia coseno compara el
significado de los embeddings y permite detectar esa equivalencia semántica.
