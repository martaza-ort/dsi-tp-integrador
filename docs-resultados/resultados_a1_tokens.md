# A.1 — Costo del contexto estático vs. recuperación top-k

Generado por `medir_tokens_a1.py`. Solo cuenta el **contexto de
conocimiento** que se agrega a cada llamada (el System Prompt y el mensaje
del cliente son iguales en los tres escenarios y se miden en la Entrega 1).

- Tokenizador: `o200k_base` (`tiktoken.encoding_for_model("gpt-4o-mini")`).
- Precio de entrada: USD 0.150 por millón de
  tokens (gpt-4o-mini, mismo valor que la Entrega 1).
- Volumen supuesto: 10,000 consultas por día (mismo supuesto
  que la Entrega 1); mes = 30 días.

## Tokens y costo por escenario

| Escenario | Tokens de contexto por consulta | USD por consulta | USD por día | USD por mes | Ahorro vs. crudo |
|---|---:|---:|---:|---:|---:|
| Catálogo crudo completo (22 registros) | 3,879 | 0.000582 | 5.82 | 174.56 | 0 % |
| Catálogo limpio completo (20 documentos) | 3,471 | 0.000521 | 5.21 | 156.19 | 11 % |
| Top-3 recuperados (promedio de 5 consultas) | 293 | 0.000044 | 0.44 | 13.19 | 92 % |

## Detalle top-3 por consulta

| Consulta | Documentos recuperados | Tokens |
|---|---|---:|
| Tenés vasos biodegradables para una cafetería | doc-019, doc-014, doc-004 | 297 |
| Quiero encargar dos cajas de bolsas compostables para mi súper | doc-001, doc-019, doc-006 | 301 |
| Se rompieron varios envases de cartón en la entrega, quiero reclamar | doc-012, doc-013, doc-005 | 290 |
| ¿Hacen envíos a mi zona o tengo que retirar por el depósito? | doc-011, doc-008, doc-012 | 260 |
| ¿Cuál es el mínimo de compra para un pedido chico? | doc-007, doc-002, doc-016 | 317 |

## Largo del corpus limpio (A.3)

- Documentos: 20.
- Caracteres de `descripcion_semantica`: mínimo 308,
  promedio 347, máximo 439.
- Ventana del modelo de embeddings (`max_seq_length`): 128 tokens.
  Documentos que la superan (se trunca el final al vectorizar): 0.

| Id | Caracteres | Tokens del embedder (título + categoría + descripción + tags) | ¿Supera 128? |
|---|---:|---:|---|
| doc-001 | 334 | 110 | no |
| doc-002 | 327 | 119 | no |
| doc-003 | 317 | 102 | no |
| doc-004 | 308 | 110 | no |
| doc-005 | 314 | 112 | no |
| doc-006 | 357 | 105 | no |
| doc-007 | 351 | 103 | no |
| doc-008 | 322 | 91 | no |
| doc-009 | 373 | 98 | no |
| doc-010 | 332 | 99 | no |
| doc-011 | 318 | 91 | no |
| doc-012 | 333 | 101 | no |
| doc-013 | 382 | 114 | no |
| doc-014 | 311 | 108 | no |
| doc-015 | 353 | 114 | no |
| doc-016 | 389 | 126 | no |
| doc-017 | 346 | 106 | no |
| doc-018 | 383 | 109 | no |
| doc-019 | 358 | 122 | no |
| doc-018-dup-2 | 439 | 117 | no |

## Reactivación

```powershell
.venv\Scripts\python.exe medir_tokens_a1.py
```
