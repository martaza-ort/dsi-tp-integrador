"""Crea la base SQLite de negocio con datos ficticios para la demo de la API.

Uso:
    python inicializar_base_demo.py                 # crea runtime/ecologix.db
    python inicializar_base_demo.py --db otra.db
    python inicializar_base_demo.py --forzar        # la recrea desde cero

Todos los datos son sintéticos. No usar datos reales de clientes.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
RUTA_DEFAULT = RAIZ / "runtime" / "ecologix.db"

CLIENTES = [
    (1, "Almacén Verde SRL"),
    (2, "Distribuidora Sur SA"),
]
PEDIDOS = [
    # (id, cliente_id, estado, dirección)
    (101, 1, "DESPACHADO", "Av. Siempreviva 742, CABA"),
    (102, 1, "ENTREGADO", "Av. Siempreviva 742, CABA"),
    (202, 2, "DESPACHADO", "Calle Falsa 123, Córdoba"),
]
ENVIOS = [
    # (pedido_id, transportista, estado, despachado_en, entregado_en)
    (101, "Logística Andina", "EN_CAMINO", "2026-11-12 10:00:00", None),
    (102, "Logística Andina", "ENTREGADO", "2026-11-05 09:00:00", "2026-11-06 15:30:00"),
    (202, "Transporte Norte", "EN_CAMINO", "2026-11-11 08:00:00", None),
]


def crear_base(ruta: Path, forzar: bool = False) -> None:
    if ruta.exists():
        if not forzar:
            raise SystemExit(f"La base ya existe en {ruta}. Usá --forzar para recrearla.")
        ruta.unlink()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript((RAIZ / "schema.sql").read_text(encoding="utf-8"))
        conexion.executemany(
            "INSERT INTO clientes (id, razon_social) VALUES (?, ?)", CLIENTES
        )
        conexion.executemany(
            "INSERT INTO pedidos (id, cliente_id, estado, direccion_entrega) VALUES (?, ?, ?, ?)",
            PEDIDOS,
        )
        conexion.executemany(
            """
            INSERT INTO envios (pedido_id, transportista, estado, despachado_en, entregado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            ENVIOS,
        )
    print(f"Base de demo creada en {ruta}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=RUTA_DEFAULT)
    parser.add_argument("--forzar", action="store_true")
    argumentos = parser.parse_args()
    crear_base(argumentos.db, argumentos.forzar)


if __name__ == "__main__":
    main()
