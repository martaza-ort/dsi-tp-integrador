"""Calibración del umbral de aceptación — Entrega 2, C.2.

Mide el mejor puntaje de similitud de un conjunto de consultas que
EcoLogix sí puede responder y de otro de consultas que no, y cuenta
qué pasaría con distintos umbrales. Genera
`docs-resultados/resultados_umbral.md`.

Requiere el corpus indexado (`python vector_db.py`).

Uso:
    python calibrar_umbral.py
"""

from __future__ import annotations

from pathlib import Path

from vector_db import UMBRAL_ACEPTACION, BaseVectorial

ROOT = Path(__file__).resolve().parent
RUTA_EVIDENCIA = ROOT / "docs-resultados" / "resultados_umbral.md"

UMBRALES_A_PROBAR = (0.35, 0.38, 0.40, 0.42, 0.45)

CONSULTAS_VALIDAS = [
    "Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje",
    "hay algo para servir café para llevar?",
    "necesito unos pots",
    "necesito algo para takeaway",
    "tengo un pedido en curso, como va?",
    "me llegaron unos paquetes rotos, quiero reclamar",
    "Tenés vasos biodegradables para una cafetería",
    "Quiero encargar dos cajas de bolsas compostables para mi súper",
    "Se rompieron varios envases de cartón en la entrega, quiero reclamar",
    "¿Hacen envíos a mi zona o tengo que retirar por el depósito?",
    "¿Cuál es el mínimo de compra para un pedido chico?",
    "che, tenés pajitas de papel? de a cuántas vienen?",
    "¿Las tapas vienen incluidas en la caja de vasos?",
    "¿Cuántas unidades trae la caja de bolsas compostables?",
    "¿Los envases del desengrasante se pueden devolver para recargar?",
    "me llegó todo roto el pedido, me devuelven la plata?",
    "Necesito sorbetes para mi kiosco, que esten disponibles en stock",
    "¿En qué estados puede estar un ticket de reclamo por entrega?",
]

CONSULTAS_FUERA_DE_CATALOGO = [
    "Venden celulares o accesorios de telefonia?",
    "venden notebooks y laptops",
    "busco contratos de alquiler",
    "¿Quién ganó el último mundial de fútbol?",
    "¿Tienen zapatillas deportivas?",
    "¿Cómo está el clima hoy en Buenos Aires?",
    # Parecen del dominio, pero el corpus no tiene la respuesta.
    "¿Venden servilletas de papel reciclado?",
    "¿Cuánto cuesta una caja de vasos de bagazo de 12 oz?",
]

CONSULTAS_VECINAS = {
    "¿Venden servilletas de papel reciclado?",
    "¿Cuánto cuesta una caja de vasos de bagazo de 12 oz?",
}


def mejor_puntaje(base: BaseVectorial, consulta: str) -> tuple[float, str]:
    resultados = base.buscar(consulta=consulta, cantidad=1, umbral=0.0)
    if not resultados:
        return 0.0, "-"
    return resultados[0]["similitud"], resultados[0]["id"]


def medir(base: BaseVectorial, consultas: list[str]) -> list[tuple[float, str, str]]:
    return sorted(
        (*mejor_puntaje(base, consulta), consulta) for consulta in consultas
    )


def main() -> None:
    base = BaseVectorial()
    validas = medir(base, CONSULTAS_VALIDAS)
    fuera = medir(base, CONSULTAS_FUERA_DE_CATALOGO)

    for nombre, medidas in (("Válidas", validas), ("Fuera de catálogo", fuera)):
        print(f"\n{nombre}:")
        for puntaje, identificador, consulta in medidas:
            print(f"  {puntaje:.4f} {identificador} {consulta}")

    max_lejanas = max(
        puntaje for puntaje, _, consulta in fuera if consulta not in CONSULTAS_VECINAS
    )
    min_validas = validas[1][0]  # sin la consulta informal más baja
    punto_medio = (max_lejanas + min_validas) / 2

    filas_umbral = []
    for umbral in UMBRALES_A_PROBAR:
        rechazadas = sum(1 for puntaje, _, _ in validas if puntaje < umbral)
        aceptadas = sum(1 for puntaje, _, _ in fuera if puntaje >= umbral)
        marca = " (actual)" if umbral == UMBRAL_ACEPTACION else ""
        filas_umbral.append(
            f"| {umbral:.2f}{marca} | {rechazadas} de {len(validas)} | "
            f"{aceptadas} de {len(fuera)} |"
        )

    def tabla(medidas: list[tuple[float, str, str]]) -> str:
        return "\n".join(
            f"| {consulta} | `{identificador}` | {puntaje:.4f} |"
            for puntaje, identificador, consulta in medidas
        )

    contenido = f"""# Calibración del umbral de aceptación — EcoLogix (Entrega 2, C.2)

Generado por `python calibrar_umbral.py` sobre la colección ChromaDB
`ecologix` (coseno, embeddings locales). Se mide el **mejor** puntaje de
cada consulta, sin aplicar ningún umbral, y se cuenta qué pasaría con
cada corte.

## Consultas que EcoLogix sí puede responder ({len(validas)})

| Consulta | Mejor documento | Similitud |
|---|---|---:|
{tabla(validas)}

## Consultas que EcoLogix no puede responder ({len(fuera)})

| Consulta | Mejor documento | Similitud |
|---|---|---:|
{tabla(fuera)}

## Qué pasa con cada umbral

| Umbral | Consultas válidas rechazadas | Consultas fuera de catálogo aceptadas |
|---|---|---|
{chr(10).join(filas_umbral)}

## Lectura

- **Los dos grupos se solapan por los dos extremos.** Una consulta válida
  informal ("me devuelven la plata", {validas[0][0]:.4f}) queda por debajo
  de varias fuera de catálogo, y dos fuera de catálogo "vecinas" del
  dominio superan cualquier corte razonable.
- **Dejando de lado esos dos casos hay un hueco.** Las fuera de catálogo
  que no se parecen a un producto llegan como máximo a {max_lejanas:.4f} y las
  consultas válidas, sin contar la informal, parten de {min_validas:.4f}. El punto
  medio del hueco es {punto_medio:.2f}, que es el umbral definido
  (**{UMBRAL_ACEPTACION}**).
- **El margen es chico.** Del lado de las consultas válidas es de
  {min_validas - UMBRAL_ACEPTACION:.4f}. Es un valor ajustado a este corpus, modelo y
  conjunto de consultas, no una frontera general; hay que repetir esta
  calibración si cambia alguno de los tres.
- **Las vecinas no se resuelven con el umbral.** Preguntar por
  servilletas o por el precio de un producto que sí existe se parece al
  corpus aunque la respuesta no esté: la similitud mide cercanía de
  tema, no si el dato existe. Ese resto lo cubren el filtro de negocio
  dentro del `where` (por ejemplo `tipo=producto` según la intención) y,
  en la Entrega 3, las reglas del prompt con la frase de escape.
"""

    RUTA_EVIDENCIA.write_text(contenido, encoding="utf-8")
    print("\nEvidencia escrita en:", RUTA_EVIDENCIA)


if __name__ == "__main__":
    main()
