"""Puzzle de código — junte fragmentos espalhados pela rede, decifre, lucre.

Cada setor esconde um código de 3 fragmentos: o primeiro sempre embutido na
cópia âncora de `.history` (em `/usr/guest`, garantida pelo filesystem), os
outros dois plantados em `/tmp` de dois outros hosts do setor (também
garantido — `tmp` está em `CORE_DIRS`, então toda casa da rede tem um).

Resolver é opcional e não bloqueia nada — é uma recompensa lateral para quem
lê tudo. O código nunca é um nome de arquivo (só aparece dentro de conteúdo de
texto), então nunca aparece no autocompletar de Tab.
"""

from __future__ import annotations

import random
import string

from .procgen import loot
from .state import FSNode, GameState, NetNode

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_GROUP_LEN = 4
_N_FRAGMENTS = 3

FRAGMENT_FILENAMES = [
    "keyfrag_a{s}.log",
    "keyfrag_b{s}.log",
    "keyfrag_c{s}.log",
]


def make_code(rng: random.Random) -> str:
    """Gera o código completo, ex.: 7QXK-M2NP-9RTZ."""
    groups = ["".join(rng.choice(_CODE_ALPHABET) for _ in range(_GROUP_LEN))
             for _ in range(_N_FRAGMENTS)]
    return "-".join(groups)


def _fragment_content(index: int, total: int, fragment: str) -> str:
    return (f"recovered from a dead session — key fragment {index}/{total}:\n"
            f"  {fragment}\n"
            f"piece it together with the others, in order, dashes and all.\n"
            f"`decrypt <code>` once you have all {total}.\n")


def _pick_fragment_hosts(gate: NetNode, net: dict[str, NetNode]) -> tuple[NetNode, NetNode]:
    """Um host raso e um fundo da rede (fora do GATE) para os fragmentos 2 e 3
    — espalhar por profundidade incentiva exploração de verdade, não só ficar
    perto da entrada. Rede minúscula demais (sem outro host): repete o GATE
    em vez de deixar o puzzle sem fragmento."""
    others = sorted(
        (n for n in net.values() if n.id != "GATE" and n.fs is not None),
        key=lambda n: n.depth,
    )
    if not others:
        return gate, gate
    if len(others) == 1:
        return others[0], others[0]
    return others[0], others[-1]


def place(rng: random.Random, state: GameState) -> None:
    """Planta o puzzle inteiro na rede recém-gerada e guarda o código no estado.

    Chamado por `world.new_game()` depois que TODOS os filesystems já
    existem — precisa enxergar a rede inteira, não um host de cada vez.
    """
    code = make_code(rng)
    fragments = code.split("-")
    state.puzzle_code = code

    gate = state.net.get("GATE")
    if gate is None or gate.fs is None:
        return

    # Fragmento 1: embutido na cópia âncora de .history (sempre existe ali).
    guest = gate.fs.children.get("usr", FSNode("usr", True)).children.get("guest")
    history = guest.children.get(".history") if guest else None
    if history is not None:
        history.content = (history.content or "") + "\n" + _fragment_content(
            1, _N_FRAGMENTS, fragments[0]
        )

    # Fragmentos 2 e 3: plantados em /tmp de dois outros hosts (ver
    # _pick_fragment_hosts).
    picks = _pick_fragment_hosts(gate, state.net)
    for i, host in enumerate(picks, start=2):
        # /tmp faz parte do esqueleto fixo de todo host (CORE_DIRS); se um dia
        # deixar de fazer, o fragmento cai na raiz em vez de sumir — um puzzle
        # com fragmento faltando é insolúvel, e insolúvel-silencioso é o pior
        # tipo de bug de geração.
        folder = host.fs.children.get("tmp") or host.fs
        name = FRAGMENT_FILENAMES[i - 1].format(s=rng.randint(10, 99))
        loot.place_item(
            rng, folder,
            FSNode(name, False, content=_fragment_content(i, _N_FRAGMENTS, fragments[i - 1])),
        )


def check(state: GameState, guess: str) -> bool:
    """Compara a tentativa ao código do setor (case/espaço-insensível)."""
    return guess.strip().upper() == state.puzzle_code.strip().upper()
