"""A.1 — Costo medido del contexto estático frente a la recuperación top-k.

Compara cuántos tokens de entrada viajan por consulta si se mete el
catálogo entero en el prompt (crudo o limpio) contra mandar solo los k
documentos más similares. Además mide el largo del corpus (A.3) contra la
ventana del modelo de embeddings, que trunca lo que sobra.

Genera docs-resultados/resultados_a1_tokens.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import tiktoken

from similitud_coseno import generar_embeddings, modelo, preparar_texto


ROOT = Path(__file__).resolve().parent
RUTA_CRUDO = ROOT / "base_conocimiento.json"
RUTA_LIMPIO = ROOT / "base_conocimiento_limpia.json"
RUTA_RESULTADOS = ROOT / "docs-resultados" / "resultados_a1_tokens.md"

# Mismos supuestos que la Entrega 1 (informes/informe.md, A.4):
# tokenizador de gpt-4o / gpt-4o-mini, precio de entrada y volumen diario.
CODIFICADOR = tiktoken.encoding_for_model("gpt-4o-mini")
PRECIO_ENTRADA_USD_POR_MILLON = 0.150
CONSULTAS_POR_DIA = 10_000
CANTIDAD_TOP_K = 3

CONSULTAS_PRUEBA = [
    "Tenés vasos biodegradables para una cafetería",
    "Quiero encargar dos cajas de bolsas compostables para mi súper",
    "Se rompieron varios envases de cartón en la entrega, quiero reclamar",
    "¿Hacen envíos a mi zona o tengo que retirar por el depósito?",
    "¿Cuál es el mínimo de compra para un pedido chico?",
]


def contar_tokens(texto: str) -> int:
    return len(CODIFICADOR.encode(texto))


def costo_usd(tokens: float) -> float:
    return tokens * PRECIO_ENTRADA_USD_POR_MILLON / 1_000_000


def cargar_documentos(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as archivo:
        return json.load(archivo)["documentos"]


def recuperar_top_k(
    consulta: str,
    documentos: list[dict],
    embeddings_docs: np.ndarray,
) -> list[dict]:
    """Top-k por similitud coseno, igual que el índice FAISS de A.4."""

    embedding_consulta = generar_embeddings([consulta])[0]
    normas = np.linalg.norm(embeddings_docs, axis=1) * np.linalg.norm(
        embedding_consulta
    )
    similitudes = embeddings_docs @ embedding_consulta / normas
    mejores = np.argsort(-similitudes)[:CANTIDAD_TOP_K]
    return [documentos[i] for i in mejores]


def medir_escenarios() -> tuple[list[dict], list[dict]]:
    crudos = cargar_documentos(RUTA_CRUDO)
    limpios = cargar_documentos(RUTA_LIMPIO)

    # El catálogo completo se pega tal cual en el prompt (JSON).
    tokens_crudo = contar_tokens(json.dumps(crudos, ensure_ascii=False))
    tokens_limpio = contar_tokens(json.dumps(limpios, ensure_ascii=False))

    # Con recuperación solo viajan los k textos preparados para el modelo.
    textos_limpios = [preparar_texto(documento) for documento in limpios]
    embeddings_docs = generar_embeddings(textos_limpios)

    por_consulta = []
    for consulta in CONSULTAS_PRUEBA:
        recuperados = recuperar_top_k(consulta, limpios, embeddings_docs)
        contexto = "\n\n".join(preparar_texto(d) for d in recuperados)
        por_consulta.append(
            {
                "consulta": consulta,
                "ids": [d["id"] for d in recuperados],
                "tokens": contar_tokens(contexto),
            }
        )

    promedio_top_k = sum(c["tokens"] for c in por_consulta) / len(por_consulta)

    escenarios = [
        {
            "nombre": f"Catálogo crudo completo ({len(crudos)} registros)",
            "tokens": tokens_crudo,
        },
        {
            "nombre": f"Catálogo limpio completo ({len(limpios)} documentos)",
            "tokens": tokens_limpio,
        },
        {
            "nombre": f"Top-{CANTIDAD_TOP_K} recuperados (promedio de "
            f"{len(por_consulta)} consultas)",
            "tokens": promedio_top_k,
        },
    ]
    return escenarios, por_consulta


def medir_corpus() -> list[dict]:
    """Largo de cada documento limpio frente a la ventana del embedder."""

    filas = []
    for documento in cargar_documentos(RUTA_LIMPIO):
        texto = preparar_texto(documento)
        filas.append(
            {
                "id": documento["id"],
                "caracteres": len(documento["descripcion_semantica"]),
                "tokens_embedder": len(modelo.tokenizer.encode(texto)),
            }
        )
    return filas


def escribir_reporte(
    escenarios: list[dict],
    por_consulta: list[dict],
    corpus: list[dict],
) -> None:
    base = escenarios[0]["tokens"]
    filas_escenarios = "\n".join(
        f"| {e['nombre']} | {e['tokens']:,.0f} | "
        f"{costo_usd(e['tokens']):.6f} | "
        f"{costo_usd(e['tokens']) * CONSULTAS_POR_DIA:.2f} | "
        f"{costo_usd(e['tokens']) * CONSULTAS_POR_DIA * 30:.2f} | "
        f"{(1 - e['tokens'] / base) * 100:.0f} % |"
        for e in escenarios
    )
    filas_consultas = "\n".join(
        f"| {c['consulta']} | {', '.join(c['ids'])} | {c['tokens']} |"
        for c in por_consulta
    )

    limite = modelo.max_seq_length
    caracteres = [fila["caracteres"] for fila in corpus]
    truncados = [fila for fila in corpus if fila["tokens_embedder"] > limite]
    filas_corpus = "\n".join(
        f"| {fila['id']} | {fila['caracteres']} | {fila['tokens_embedder']} | "
        f"{'sí' if fila['tokens_embedder'] > limite else 'no'} |"
        for fila in corpus
    )

    contenido = f"""# A.1 — Costo del contexto estático vs. recuperación top-k

Generado por `medir_tokens_a1.py`. Solo cuenta el **contexto de
conocimiento** que se agrega a cada llamada (el System Prompt y el mensaje
del cliente son iguales en los tres escenarios y se miden en la Entrega 1).

- Tokenizador: `{CODIFICADOR.name}` (`tiktoken.encoding_for_model("gpt-4o-mini")`).
- Precio de entrada: USD {PRECIO_ENTRADA_USD_POR_MILLON:.3f} por millón de
  tokens (gpt-4o-mini, mismo valor que la Entrega 1).
- Volumen supuesto: {CONSULTAS_POR_DIA:,} consultas por día (mismo supuesto
  que la Entrega 1); mes = 30 días.

## Tokens y costo por escenario

| Escenario | Tokens de contexto por consulta | USD por consulta | USD por día | USD por mes | Ahorro vs. crudo |
|---|---:|---:|---:|---:|---:|
{filas_escenarios}

## Detalle top-{CANTIDAD_TOP_K} por consulta

| Consulta | Documentos recuperados | Tokens |
|---|---|---:|
{filas_consultas}

## Largo del corpus limpio (A.3)

- Documentos: {len(corpus)}.
- Caracteres de `descripcion_semantica`: mínimo {min(caracteres)},
  promedio {sum(caracteres) / len(caracteres):.0f}, máximo {max(caracteres)}.
- Ventana del modelo de embeddings (`max_seq_length`): {limite} tokens.
  Documentos que la superan (se trunca el final al vectorizar): {len(truncados)}.

| Id | Caracteres | Tokens del embedder (título + categoría + descripción + tags) | ¿Supera {limite}? |
|---|---:|---:|---|
{filas_corpus}

## Reactivación

```powershell
.venv\\Scripts\\python.exe medir_tokens_a1.py
```
"""

    RUTA_RESULTADOS.write_text(contenido, encoding="utf-8")
    print("Reporte escrito en:", RUTA_RESULTADOS)


def main() -> None:
    escenarios, por_consulta = medir_escenarios()
    corpus = medir_corpus()

    for escenario in escenarios:
        print(
            f"{escenario['nombre']:<55} {escenario['tokens']:>8,.0f} tokens  "
            f"USD/día {costo_usd(escenario['tokens']) * CONSULTAS_POR_DIA:.2f}"
        )

    escribir_reporte(escenarios, por_consulta, corpus)


if __name__ == "__main__":
    main()
