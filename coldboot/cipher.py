"""Minigame de Cifra — quebra de código por dedução, ao estilo Mastermind.

Diferente do Combate Rítmico (combat.py), aqui não tem relógio: o jogador tem
um número limitado de PALPITES para deduzir uma sequência secreta, guiado só
pelo feedback de cada tentativa (quantos dígitos certos na posição certa,
quantos certos na posição errada). É pensar, não digitar rápido.

Módulo puro: quem conta os usos por setor e aplica a recompensa é o app.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

_DIGITS = "123456789"
CODE_LENGTH = 4
MAX_GUESSES = 8


@dataclass
class CipherResult:
    kind: str            # "invalid" | "progress" | "win" | "lose"
    exact: int = 0        # dígitos certos, na posição certa
    partial: int = 0       # dígitos certos, na posição errada
    guesses_left: int = 0


class CipherSession:
    def __init__(self, length: int = CODE_LENGTH, alphabet: str = _DIGITS[:6],
                 max_guesses: int = MAX_GUESSES, rng: random.Random | None = None):
        self.length = length
        self.alphabet = alphabet
        self.max_guesses = max_guesses
        r = rng or random
        self.secret = "".join(r.choice(alphabet) for _ in range(length))
        self.guesses_made = 0
        self.finished = False
        self.won = False

    @property
    def guesses_left(self) -> int:
        return max(0, self.max_guesses - self.guesses_made)

    def _valid(self, guess: str) -> bool:
        return len(guess) == self.length and all(c in self.alphabet for c in guess)

    def submit(self, raw: str) -> CipherResult:
        if self.finished:
            return CipherResult("win" if self.won else "lose", guesses_left=self.guesses_left)
        guess = raw.strip()
        if not self._valid(guess):
            return CipherResult("invalid", guesses_left=self.guesses_left)

        self.guesses_made += 1
        exact = sum(1 for a, b in zip(guess, self.secret) if a == b)
        # "parcial" conta dígitos certos em posição errada: interseção de
        # multiconjuntos (Counter) menos os que já bateram na posição certa.
        common = sum((Counter(guess) & Counter(self.secret)).values())
        partial = common - exact

        if exact == self.length:
            self.finished = True
            self.won = True
            return CipherResult("win", exact, partial, self.guesses_left)
        if self.guesses_left <= 0:
            self.finished = True
            self.won = False
            return CipherResult("lose", exact, partial, 0)
        return CipherResult("progress", exact, partial, self.guesses_left)


def make_session(sector: int, rng: random.Random | None = None) -> CipherSession:
    """Sessão escalada pelo setor: o alfabeto cresce devagar (mais dígitos
    possíveis = dedução mais dura), sem nunca passar de 9 símbolos distintos."""
    alphabet_size = min(9, 6 + sector // 4)
    return CipherSession(alphabet=_DIGITS[:alphabet_size], rng=rng)
