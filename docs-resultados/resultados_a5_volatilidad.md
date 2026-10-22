# Prueba destructiva de volatilidad — EcoLogix (Entrega 2, A.5)

Esta prueba demuestra con evidencia ejecutable la diferencia entre mantener
un índice FAISS únicamente en memoria y persistirlo en disco.

La prueba de persistencia se realizó mediante procesos independientes.
Primero se construyó y guardó el índice ejecutando el modo `escribir`.
Una vez finalizado completamente ese proceso, se inició una nueva ejecución
con el modo `leer`, que recuperó el índice desde disco sin volver a generar
los embeddings del corpus.

## Comandos de reproducción

```bash
rm -f indice_faiss/prueba_a5.index

python3 prueba_volatilidad.py --modo leer
python3 prueba_volatilidad.py --modo escribir
python3 prueba_volatilidad.py --modo leer
```

Cada ejecución de `python3` corresponde a un proceso independiente.

## Escenario 1 — Intento de lectura sin persistencia previa

Antes de comenzar la prueba se eliminó únicamente el archivo temporal
`indice_faiss/prueba_a5.index`.

Luego se ejecutó:

```bash
python3 prueba_volatilidad.py --modo leer
```

El resultado fue un error esperado:

```text
FileNotFoundError: No existe el índice persistido:
indice_faiss/prueba_a5.index
```

| Medición | Resultado |
|---|---|
| ¿Existía un índice persistido? | No |
| ¿Fue posible recuperarlo desde otro proceso? | No |
| ¿Sería necesario regenerar los embeddings? | Sí |
| Resultado esperado | Prueba superada |

Sin una llamada previa a `faiss.write_index()`, el índice solamente existe
en la memoria RAM del proceso que lo construyó. Cuando ese proceso termina,
el objeto desaparece y un proceso posterior no tiene ningún archivo que
pueda cargar mediante `faiss.read_index()`.

Por lo tanto, para recuperar la funcionalidad sería necesario volver a
procesar todos los documentos, generar nuevamente sus embeddings y
reconstruir el índice.

## Escenario 2 — Escritura del índice

Se ejecutó:

```bash
python3 prueba_volatilidad.py --modo escribir
```

La ejecución construyó los embeddings del corpus, creó el índice FAISS y
lo persistió mediante `faiss.write_index()`.

| Medición | Resultado |
|---|---:|
| Documentos procesados | 20 |
| Vectores guardados | 20 |
| Dimensión de los vectores | 384 |
| Archivo generado | `indice_faiss/prueba_a5.index` |

Al finalizar el comando, el proceso de Python que construyó el índice se
cerró completamente. El índice dejó de existir en la memoria de ese
proceso, pero quedó almacenado en disco.

## Escenario 3 — Lectura desde un proceso nuevo

Después de finalizar el proceso de escritura se ejecutó:

```bash
python3 prueba_volatilidad.py --modo leer
```

Esta ejecución inició un proceso nuevo y cargó directamente el archivo
persistido mediante `faiss.read_index()`.

| Medición | Antes de finalizar el proceso de escritura | Nuevo proceso de lectura |
|---|---:|---:|
| Vectores | 20 | 20 |
| Dimensión | 384 | 384 |
| ¿Se generaron nuevamente los embeddings? | No aplica | No |

El modo `leer` no llama a `cargar_documentos()`, `preparar_texto()` ni
`generar_embeddings()`. Solamente utiliza `faiss.read_index()` para
recuperar el índice almacenado.

**¿Coincide el índice recuperado con el persistido?** Sí.

**¿El índice sobrevivió al cierre del proceso que lo construyó?** Sí.

## Conclusión de la prueba

Los resultados demuestran que el índice que existe únicamente en memoria
se pierde al finalizar el proceso. En cambio, después de ejecutar
`faiss.write_index()`, un proceso independiente puede recuperar la misma
cantidad de vectores y la misma dimensión mediante `faiss.read_index()`,
sin recalcular los embeddings del corpus.

La persistencia evita repetir el costo computacional de vectorizar todos
los documentos cada vez que se reinicia la aplicación.

## Reflexión

### ¿Qué ocurre si el servidor se reinicia?

Sin persistencia, cada reinicio causado por un despliegue, una falla o una
tarea de mantenimiento obliga a reconstruir el índice completo. Durante
esa reconstrucción, la búsqueda vectorial podría no estar disponible y se
repetiría innecesariamente el costo de generar los embeddings.

Con el índice guardado en un volumen persistente, el servidor puede
recuperarlo mediante `faiss.read_index()` al iniciar. Esto disminuye el
tiempo necesario para volver a prestar servicio y evita recalcular los
vectores del corpus cuando los documentos no cambiaron.

### ¿Qué ocurre si existen dos servidores?

FAISS no proporciona control de concurrencia ni sincronización automática
entre distintas instancias. Si cada servidor conserva su propia copia
local del índice, las copias pueden quedar desactualizadas. Por ejemplo,
un servidor podría incorporar un producto nuevo mientras el otro continúa
trabajando con una versión anterior.

Compartir directamente un archivo tampoco garantiza escrituras
concurrentes seguras. Para un entorno con varios servidores sería
necesario centralizar la construcción y distribución del índice, aplicar
versionado y reemplazos atómicos, o utilizar una base vectorial desplegada
como servicio para que todas las instancias consulten una única fuente.

Un `PersistentClient` local de ChromaDB conserva información entre
reinicios de una instancia, pero tampoco convierte automáticamente el
almacenamiento local en una solución distribuida para múltiples
servidores.