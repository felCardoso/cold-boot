"""Montagem de uma nova run.

Todo o conteúdo agora é procedural: a rede vem de `procgen.network` e cada host
ganha seu próprio filesystem de `procgen.filesystem` (com lore de
`procgen.grammar`). Tudo derivado da mesma seed.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from . import puzzle
from .state import GameState
from .procgen import loot
from .procgen.filesystem import default_cwd, generate_filesystem
from .procgen.network import generate_network, size_for_sector
from .procgen.rng import make_rng, resolve_seed


# --------------------------------------------------------------------------- #
# Modificadores de setor — cada incursão sorteia um, trocando o tom da run.
# Cada um mexe em UM sistema existente e sempre paga (ou cobra) no payout do
# setor, para nenhum ser estritamente melhor que o outro — só diferente.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SectorModifier:
    id: str
    creep_mult: float = 1.0        # multiplica economy.creep_mult (Trace ambiente)
    ice_penalty_mult: float = 1.0  # multiplica a penalidade de Trace do ICE
    botnet_risk_mult: float = 1.0  # multiplica economy.botnet_risk
    payout_mult: float = 1.0       # multiplica sector_payout


SECTOR_MODIFIERS: dict[str, SectorModifier] = {
    "signal_clean": SectorModifier("signal_clean", creep_mult=0.7, payout_mult=0.9),
    "high_alert": SectorModifier("high_alert", ice_penalty_mult=1.3, payout_mult=1.3),
    "ghost_net": SectorModifier("ghost_net", botnet_risk_mult=0.5, payout_mult=0.9),
    "soft_ice": SectorModifier("soft_ice", ice_penalty_mult=0.75, payout_mult=0.85),
    # Os dois de baixo são o espelho dos dois de cima: mesma dobradiça
    # (ambiente ambiente / botnet), só que cobrando o preço no risco em vez de
    # no payout — cada eixo agora tem as duas direções representadas.
    "noisy_signal": SectorModifier("noisy_signal", creep_mult=1.3, payout_mult=1.15),
    "loud_botnet": SectorModifier("loud_botnet", botnet_risk_mult=1.5, payout_mult=1.15),
}


def _roll_modifier(rng: random.Random, state: GameState) -> None:
    mod = SECTOR_MODIFIERS[rng.choice(list(SECTOR_MODIFIERS))]
    state.modifier_id = mod.id
    state.mod_creep = mod.creep_mult
    state.mod_ice_penalty = mod.ice_penalty_mult
    state.mod_botnet_risk = mod.botnet_risk_mult
    state.mod_payout = mod.payout_mult


# Falas do vilão (a IA corporativa) para quando o LOCKDOWN captura o sinal.
# Lore fixo em inglês (ver i18n.py) — não muda com o idioma da UI.
VILLAIN_LINES = [
    "Every signal is a confession. Yours echoed too long.",
    "You call yourselves ghosts. Ghosts leave a chill in the air too.",
    "I didn't hunt you. I just waited for you to get tired.",
    "Every keystroke was a crumb. You led me right to your door.",
    "Freedom is just latency that hasn't resolved yet.",
    "There's no way out of the system. There's only the illusion that you got in.",
    "I'll keep your typing rhythm. It's more unique than your fingerprint.",
]


def new_game(seed: int | None = None, sector: int = 1) -> GameState:
    """Novo setor reproduzível. Rede + um filesystem por host, tudo da seed."""
    seed = resolve_seed(seed)
    rng = make_rng(seed)

    state = GameState()
    state.seed = seed
    state.rng = rng
    state.sector = sector
    state.best_sector = sector

    net, core_id = generate_network(rng, size=size_for_sector(rng, sector))
    state.net = net
    state.core_id = core_id
    state.location = "GATE"

    # Um filesystem por host (ordem estável => determinístico).
    for node in net.values():
        node.fs = generate_filesystem(
            rng, node.label, node.depth, is_core=(node.id == core_id), sector=sector
        )

    state.cwd = default_cwd(net["GATE"].fs)
    state.reveal_neighbors("GATE")
    _ensure_keycard(rng, state)
    puzzle.place(rng, state)
    _roll_modifier(rng, state)
    return state


def _ensure_keycard(rng: random.Random, state: GameState) -> None:
    """Se a rede sorteou um cofre, garante que exista cartão para ele.

    Sem isso, o leitor de cartão vira decoração numa fração das runs: a chance
    do cofre e a do cartão são sorteadas separadamente, então dava para gerar
    a fechadura sem nunca gerar a chave.
    """
    hosts = [n for n in sorted(state.net.values(), key=lambda x: (x.depth, x.id))
             if n.fs is not None]
    if not any(loot.find_kind(n.fs, "reader") for n in hosts):
        return
    if any(loot.find_kind(n.fs, "keycard") for n in hosts):
        return
    # Planta um cartão no host mais raso que tiver /tmp — perto da entrada, para
    # o jogador achar antes do cofre. place_item garante a inserção: esta
    # keycard é uma PROMESSA do mundo, não pode sumir por colisão de nome.
    for host in hosts:
        tmp = host.fs.children.get("tmp")
        if tmp is not None:
            loot.place_item(rng, tmp, loot.generate_item(rng, host.depth, kind="keycard"))
            return


def sector_payout(sector: int) -> float:
    """CRN que o setor limpo deposita na sua conta. Cresce mais que linear —
    é o que faz valer descer mais fundo em vez de moer o setor 1."""
    return round(20 + sector * 12 + (sector ** 1.6), 2)


def puzzle_reward(sector: int) -> float:
    """CRN do puzzle de código — bem mais que loot comum, mas menos que
    limpar o setor inteiro (é um bônus lateral, não o objetivo)."""
    return round(60 + sector * 15, 2)


PUZZLE_TRACE_RELIEF = 35.0   # alívio de trace ao decifrar — comparável ao scrambler


def next_run(prev: GameState, won: bool, seed: int | None = None) -> GameState:
    """O próximo setor: rede nova, hardware antigo.

    O rig é seu, físico, na sua casa — a corporação não alcança. O que se perde
    é tudo que estava do lado de dentro: mapa, itens no buffer, chaves.

    Vencer avança um setor e você saca o que ganhou. Perder te joga de volta ao
    setor 1 com a carteira congelada: o hardware é o único ratchet, e é ele que
    faz os setores iniciais passarem voando na próxima descida.
    """
    sector = prev.sector + 1 if won else 1
    st = new_game(seed, sector=sector)
    st.rig = prev.rig.copy()
    st.wallet = prev.wallet if won else 0.0
    st.run_number = prev.run_number + 1
    st.runs_won = prev.runs_won + (1 if won else 0)
    st.best_sector = max(prev.best_sector, sector)
    # Meta lifetime: sobrevive à morte também (ao contrário de wallet).
    st.total_earned = prev.total_earned
    st.deaths = prev.deaths + (0 if won else 1)
    st.achievements = set(prev.achievements)
    # O tutorial e as dicas já vistas não se repetem a cada setor.
    for k, v in prev.flags.items():
        if k.startswith("hint_") or k == "tutorial_done":
            st.flags[k] = v
    return st


# --------------------------------------------------------------------------- #
# Conquistas — meta-progressão além de best_sector. Cada uma é só um limiar
# sobre estado que já sobrevive a mortes/setores (ver acima); nenhuma precisa
# de contador novo dedicado.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Achievement:
    id: str
    check: Callable[[GameState], bool]


ACHIEVEMENTS: list[Achievement] = [
    Achievement("first_core", lambda st: st.runs_won >= 1),
    Achievement("deep_5", lambda st: st.best_sector >= 5),
    Achievement("deep_10", lambda st: st.best_sector >= 10),
    Achievement("payout_1k", lambda st: st.total_earned >= 1000),
    Achievement("payout_5k", lambda st: st.total_earned >= 5000),
    Achievement("resilient", lambda st: st.deaths >= 3),
    Achievement("veteran", lambda st: st.runs_won >= 10),
]


def unlock_achievements(state: GameState) -> list[str]:
    """Confere o catálogo contra o estado atual e desbloqueia o que bater.

    Devolve só os ids RECÉM desbloqueados nesta chamada (para narrar) — ids já
    em `state.achievements` não voltam, então é seguro chamar de novo sem que
    nada tenha mudado (idempotente)."""
    newly: list[str] = []
    for ach in ACHIEVEMENTS:
        if ach.id not in state.achievements and ach.check(state):
            state.achievements.add(ach.id)
            newly.append(ach.id)
    return newly
