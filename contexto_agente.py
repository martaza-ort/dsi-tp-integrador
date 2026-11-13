from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextoAgente:
    """Contexto confiable de ejecución que no forma parte del estado persistido."""

    cliente_id: int
