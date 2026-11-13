from __future__ import annotations

import argparse
from pathlib import Path

from memoria import MemoriaConversacional


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Purga una vez los hilos vencidos del checkpointer SQLite."
    )
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="Ruta a la base SQLite dedicada a checkpoints.",
    )
    argumentos = parser.parse_args()
    if not argumentos.db.is_file():
        parser.error(f"No existe la base SQLite indicada: {argumentos.db}")

    with MemoriaConversacional(argumentos.db) as memoria:
        cantidad = memoria.purgar_hilos_vencidos()
    print(f"Hilos vencidos purgados: {cantidad}")


if __name__ == "__main__":
    main()
