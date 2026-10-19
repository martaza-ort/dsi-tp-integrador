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
| Catálogo crudo completo (22 registros) | 5,497 | 0.000825 | 8.25 | 247.37 | 0 % |
| Catálogo limpio completo (20 documentos) | 5,030 | 0.000754 | 7.54 | 226.35 | 8 % |
| Top-3 recuperados (promedio de 5 consultas) | 525 | 0.000079 | 0.79 | 23.62 | 90 % |

## Detalle top-3 por consulta

| Consulta | Documentos recuperados | Tokens |
|---|---|---:|
| Tenés vasos biodegradables para una cafetería | doc-019, doc-004, doc-002 | 511 |
| Quiero encargar dos cajas de bolsas compostables para mi súper | doc-001, doc-019, doc-003 | 524 |
| Se rompieron varios envases de cartón en la entrega, quiero reclamar | doc-012, doc-013, doc-002 | 560 |
| ¿Hacen envíos a mi zona o tengo que retirar por el depósito? | doc-011, doc-012, doc-008 | 522 |
| ¿Cuál es el mínimo de compra para un pedido chico? | doc-007, doc-016, doc-010 | 508 |

## Largo del corpus limpio (A.3)

- Documentos: 20.
- Caracteres de `descripcion_semantica`: mínimo 503,
  promedio 649, máximo 708.
- Ventana del modelo de embeddings (`max_seq_length`): 128 tokens.
  Documentos que la superan (se trunca el final al vectorizar): 20.

| Id | Caracteres | Tokens del embedder (título + categoría + descripción + tags) | ¿Supera 128? |
|---|---:|---:|---|
| doc-001 | 708 | 212 | sí |
| doc-002 | 631 | 207 | sí |
| doc-003 | 651 | 200 | sí |
| doc-004 | 581 | 186 | sí |
| doc-005 | 647 | 205 | sí |
| doc-006 | 647 | 189 | sí |
| doc-007 | 672 | 169 | sí |
| doc-008 | 629 | 171 | sí |
| doc-009 | 660 | 173 | sí |
| doc-010 | 657 | 179 | sí |
| doc-011 | 649 | 188 | sí |
| doc-012 | 685 | 200 | sí |
| doc-013 | 684 | 194 | sí |
| doc-014 | 672 | 203 | sí |
| doc-015 | 669 | 189 | sí |
| doc-016 | 661 | 193 | sí |
| doc-017 | 653 | 200 | sí |
| doc-018 | 653 | 174 | sí |
| doc-019 | 503 | 157 | sí |
| doc-018-dup-2 | 675 | 176 | sí |

## Reactivación

```powershell
.venv\Scripts\python.exe medir_tokens_a1.py
```
