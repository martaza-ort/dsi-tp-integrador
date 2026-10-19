"""Similitud coseno a mano sobre dos ejes de EcoLogix — Entrega 2, A.2.

Ejes: X = afinidad con bebidas, Y = afinidad con empaque seco.
Muestra los tres pasos (producto punto, normas, división) y los valida
con NumPy.

Uso:
    python similitud_manual.py
"""

from __future__ import annotations

import math

import numpy as np

CONSULTA = ("vaso para café caliente", (0.8, 0.2))
DOCUMENTOS = [
    ("Vasos de bagazo", (0.9, 0.1)),
    ("Bolsas compostables", (0.1, 0.9)),
    ("Envases de cartón", (0.5, 0.5)),
]


def similitud_coseno(a, b) -> float:
    """Validación con NumPy, igual a la fórmula de la consigna."""

    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def coseno_a_mano(a: tuple[float, float], b: tuple[float, float]) -> dict:
    producto_punto = a[0] * b[0] + a[1] * b[1]
    norma_a = math.sqrt(a[0] ** 2 + a[1] ** 2)
    norma_b = math.sqrt(b[0] ** 2 + b[1] ** 2)
    return {
        "producto_punto": producto_punto,
        "norma_a": norma_a,
        "norma_b": norma_b,
        "similitud": producto_punto / (norma_a * norma_b),
    }


def main() -> None:
    texto, q = CONSULTA
    print(f'Consulta: "{texto}"  Q = {q}\n')

    for nombre, vector in DOCUMENTOS:
        pasos = coseno_a_mano(q, vector)
        con_numpy = similitud_coseno(np.array(q), np.array(vector))
        assert math.isclose(pasos["similitud"], con_numpy, rel_tol=1e-9)

        print(f"{nombre}  D = {vector}")
        print(f"  1) A·B   = {q[0]}×{vector[0]} + {q[1]}×{vector[1]} = {pasos['producto_punto']:.2f}")
        print(f"  2) ‖A‖   = {pasos['norma_a']:.4f}   ‖B‖ = {pasos['norma_b']:.4f}")
        print(
            f"  3) cos   = {pasos['producto_punto']:.2f} / "
            f"({pasos['norma_a']:.4f} × {pasos['norma_b']:.4f}) = {pasos['similitud']:.3f}"
        )
        print(f"  NumPy    = {con_numpy:.3f}  -> coincide con el cálculo a mano\n")


if __name__ == "__main__":
    main()
