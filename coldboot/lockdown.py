"""LOCKDOWN — o minigame de vida-ou-morte quando o Trace chega a 100%.

Diferente do combate normal (onde errar só custa Trace), aqui é do-or-die:
uma sequência de códigos, timer apertado, e QUALQUER erro/estouro derruba a
conexão. Vencer "rebate" o sinal (reseta o Trace) e sobe o nível — o próximo
LOCKDOWN vem mais rápido e mais longo.
"""

from __future__ import annotations

import random

from .combat import _make_code


class LockdownSession:
    def __init__(self, level: int, time_bonus: float = 0.0, diff=None,
                 rng: random.Random | None = None):
        self.rng = rng  # None = random global (runtime); seedado = reproduzível
        self.level = level
        self.total = 3 + level                      # códigos a digitar
        self.time_limit = max(1.8, 4.0 - level * 0.5)
        self.time_bonus = time_bonus                # segundos extras da CPU do rig
        self.code_len = 6 + level
        self.words = bool(diff and diff.words)
        if diff is not None:
            self.time_limit *= diff.time_mult
            self.code_len = max(2, self.code_len + diff.code_delta)
        self.round = 0
        self.code = ""
        self.time_left = 0.0
        self._next()

    def _next(self) -> None:
        self.code = _make_code(self.code_len, self.words, self.rng)
        self.time_left = self.time_limit + self.time_bonus

    def tick(self, dt: float) -> str | None:
        """Retorna 'fail' se o tempo estourar."""
        self.time_left -= dt
        return "fail" if self.time_left <= 0 else None

    def submit(self, text: str) -> str:
        """'win' | 'advance' | 'fail'. Qualquer erro = 'fail' (morte)."""
        if text.strip() != self.code:
            return "fail"
        self.round += 1
        if self.round >= self.total:
            return "win"
        self._next()
        return "advance"
