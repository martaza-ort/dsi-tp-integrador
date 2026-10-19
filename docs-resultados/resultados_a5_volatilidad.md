# Prueba destructiva de volatilidad — EcoLogix (Entrega 2, A.5)

Evidencia real de que la persistencia del índice FAISS no es una
afirmación: se construyó el mismo corpus dos veces, una sin
`write_index()` y otra con, simulando en ambos casos el reinicio del
proceso (se borran los objetos de Python en memoria y se intenta
recargar desde el path en disco).

Reproducible con `python prueba_volatilidad.py`.

## Escenario 1 — Sin `write_index()`

| Medición | Resultado |
|---|---|
| Vectores construidos en memoria | 20 |
| ¿Existe el archivo en disco tras "reiniciar"? | False |
| Error al intentar `faiss.read_index()` | `Error in __cdecl faiss::FileIOReader::FileIOReader(const char *) at D:\a\faiss\faiss\faiss\impl\io.cpp:70: Error: 'f' failed: could not open C:\Users\gisel\AppData\Local\Temp\prueba_volatilidad_gst7hi0a\sin_persistencia.index for reading: No such file or directory` |
| ¿Hay que regenerar embeddings (pagar de nuevo)? | **Sí** |

**¿Pasó la prueba (se perdió el índice)?** Sí

Sin `write_index()`, el índice vive únicamente en la RAM del proceso
de Python. Al terminar el proceso ("reiniciar el entorno"), el objeto
`faiss.Index` desaparece con él. No queda ningún archivo para
recargar: `faiss.read_index()` sobre ese path falla, y la única forma
de volver a tener el índice es correr `generar_embeddings()` de nuevo
sobre todo el corpus — es decir, pagar tokens/cómputo otra vez.

## Escenario 2 — Con `write_index()`

| Medición | Antes de "reiniciar" | Después de recargar desde disco |
|---|---|---|
| Vectores | 20 | 20 |
| Dimensión | 384 | 384 |

**¿Coincide el índice recargado con el original?** True

**¿Pasó la prueba (el índice sobrevivió al "reinicio")?** Sí

Con `write_index()`, el índice queda serializado en disco. Tras
borrar los objetos en memoria (simulando que el proceso terminó y
arrancó de nuevo), `faiss.read_index()` reconstruye el mismo índice
— mismo `ntotal`, misma dimensión — sin volver a llamar
`generar_embeddings()` en ningún momento de este segundo escenario.
La diferencia entre los dos escenarios es, literalmente, esa única
línea de código.

## Reflexión

**¿Qué pasa en producción si el servidor se reinicia?** Sin
persistencia en disco, cada reinicio (deploy, crash, escalado)
obliga a reconstruir el índice completo desde cero, con el costo de
cómputo/tokens que eso implica y un período sin búsqueda disponible
mientras se regenera. Con `write_index()`/`read_index()` sobre un
volumen persistente, el servidor vuelve a estar operativo apenas
termina de leer el archivo.

**¿Y si hay dos servidores?** FAISS no tiene control de concurrencia
ni mecanismo de sincronización propio: si cada instancia construye
su índice por separado, pueden terminar desincronizadas (una ve un
producto que la otra no, por ejemplo tras un evento como el de B.3).
Para dos servidores hace falta un paso adicional que FAISS no
resuelve solo: compartir el mismo archivo de índice (disco
compartido, objeto en un bucket, o reconstrucción centralizada que
los demás solo leen) — exactamente el problema que `PersistentClient`
de ChromaDB sí resuelve de fábrica (ver B.2).
