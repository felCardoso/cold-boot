"""RNG determinístico. Uma seed reproduz a run inteira (mapa, e no futuro
filesystem/lore/missão), o que também permite "seed do dia" compartilhável.
"""

from __future__ import annotations

import random


def resolve_seed(seed: int | None = None) -> int:
    """Devolve uma seed concreta. Se None, gera uma (e guardável) aleatória."""
    if seed is None:
        return random.randrange(1, 2**31 - 1)
    return int(seed) & 0x7FFFFFFF


def make_rng(seed: int) -> random.Random:
    return random.Random(seed)
