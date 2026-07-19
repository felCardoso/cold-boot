"""Economia — mineração, calor/throttling e compra de hardware.

Lógica pura sobre o GameState (sem UI). O app chama `tick_economy` num timer.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import hardware, i18n
from .hardware import CATALOG, TMAX, MINE_RATE
from .settings import Difficulty
from .state import GameState


# Barulho da mineração: você está queimando CPU numa máquina alheia, e isso
# aparece no `ps` deles. Sublinear no hashrate — dobrar o rig não dobra o
# risco, mas rig grande continua sendo rig barulhento.
NOISE_K = 0.08            # trace por tick por sqrt(hashrate)
NOISE_TIGHT_MULT = 2.0    # host com a memória no talo repara MUITO mais

# --------------------------------------------------------------------------- #
# Botnet — mineradores remotos plantados em hosts comprometidos.
#
# Versão enxuta de propósito: sem "rig minerador dedicado" na loja (isso
# tornaria o dinheiro efetivamente infinito). O único freio é o risco: depois
# de BOTNET_GRACE_TICKS, cada tick tem uma chance CRESCENTE de o script ser
# achado e apagado — perde o script e leva um susto de trace. A capacidade
# (quantos scripts de uma vez) escala com os núcleos da CPU, então evoluir o
# rig também evolui a botnet, sem precisar de uma categoria de loja nova.
# --------------------------------------------------------------------------- #
BOTNET_GRACE_TICKS = 15       # ticks (~2s cada) antes do risco de descoberta começar
BOTNET_RISK_PER_TICK = 0.015  # cresce por tick após a graça
BOTNET_RISK_CAP = 0.35        # nunca passa disso por tick
BOTNET_LOSS_TRACE = 8.0       # trace ao perder um script
_BOTNET_INCOME_BASE = 0.4
_BOTNET_INCOME_PER_SECTOR = 0.12


def botnet_income_rate(sector: int) -> float:
    """CRN por tick que CADA script plantado rende — modesto, é dinheiro
    "esquecido rodando", não substitui minerar de verdade."""
    return round(_BOTNET_INCOME_BASE + _BOTNET_INCOME_PER_SECTOR * sector, 3)


def botnet_capacity(rig: hardware.Rig) -> int:
    """Quantos scripts cabem ao mesmo tempo — escala com núcleos da CPU."""
    return hardware.derived(rig).cores // 3


@dataclass
class BotnetTick:
    income: float = 0.0
    lost: list[str] = field(default_factory=list)


def botnet_risk(age: int, mult: float = 1.0) -> float:
    """Risco de descoberta NESTE tick, para um script com esta idade — 0
    dentro da graça, crescente (até o teto) depois dela. Usado tanto pelo
    tick de verdade quanto pelo `botnet` (mostrar o risco não muda o risco).
    `mult` é o modificador de setor (state.mod_botnet_risk — ver world.py)."""
    if age <= BOTNET_GRACE_TICKS:
        return 0.0
    return min(BOTNET_RISK_CAP, (age - BOTNET_GRACE_TICKS) * BOTNET_RISK_PER_TICK * mult)


def botnet_risk_mult(state: GameState, diff: Difficulty | None = None) -> float:
    """Risco combinado: modificador de setor (state.mod_botnet_risk) vezes a
    dificuldade escolhida (diff.botnet_risk_mult) — mesmo padrão de
    `creep_mult`, para o risco mostrado em `botnet` bater com o risco real."""
    return state.mod_botnet_risk * (diff.botnet_risk_mult if diff is not None else 1.0)


def botnet_tick(
    state: GameState, rng: random.Random | None = None, diff: Difficulty | None = None
) -> BotnetTick:
    """Avança um tick da botnet: rende, envelhece, arrisca."""
    r = rng or random
    rate = botnet_income_rate(state.sector)
    mult = botnet_risk_mult(state, diff)
    income = 0.0
    lost: list[str] = []
    for host_id in list(state.botnet.keys()):
        state.botnet[host_id] += 1
        age = state.botnet[host_id]
        income += rate
        if r.random() < botnet_risk(age, mult):
            del state.botnet[host_id]
            lost.append(host_id)
    if income:
        state.wallet = round(state.wallet + income, 3)
    if lost:
        state.add_trace(BOTNET_LOSS_TRACE * len(lost))
    return BotnetTick(round(income, 3), lost)


@dataclass
class TickInfo:
    mined: float
    power: int
    temp: float
    overheated: bool
    mining: bool
    noise: float = 0.0        # trace somado neste tick pela mineração


def mining_on(state: GameState) -> bool:
    return "miner" in state.processes


def tick_economy(state: GameState, dt_ticks: float = 1.0) -> TickInfo:
    """Avança a economia um tick: calor -> mineração."""
    d = hardware.derived(state.rig)
    mining = mining_on(state)

    # Calor com inércia térmica.
    target = hardware.heat_equilibrium(state.rig, mining)
    state.heat += (target - state.heat) * 0.15
    overheated = state.heat > TMAX

    # Mineração (para se superaquecer).
    mined = 0.0
    noise = 0.0
    if mining and not overheated:
        mined = d.hashrate * MINE_RATE * dt_ticks
        state.wallet += mined
        # Minerar não é de graça: o host sente a CPU sumindo.
        noise = mining_noise(state) * dt_ticks
        state.add_trace(noise)

    power = d.power_load if mining else d.power_idle

    return TickInfo(round(mined, 3), power,
                    round(state.heat, 1), overheated, mining, round(noise, 3))


def mining_noise(state: GameState) -> float:
    """Trace por tick que o minerador gera (0 se ele não está rodando)."""
    if not mining_on(state):
        return 0.0
    d = hardware.derived(state.rig)
    noise = NOISE_K * math.sqrt(max(0.0, d.hashrate))
    if state.ram_tight:
        noise *= NOISE_TIGHT_MULT
    return noise


def is_overheated(state: GameState) -> bool:
    return state.heat > TMAX


# Rota limpa esconde melhor: o roteador multiplica o rastreamento passivo.
# Sinal 1 (modem da operadora) = 1.4x; sinal 5 (Husky X-Band) = 0.6x.
_CREEP_BY_SIGNAL = {1: 1.4, 2: 1.2, 3: 1.0, 4: 0.8, 5: 0.6}


def creep_mult(state: GameState, diff: Difficulty | None = None) -> float:
    """Quanto o Trace passivo corre, dado o roteador do rig, o modificador do
    setor (state.mod_creep — ver world.py) E a dificuldade escolhida (fácil
    aperta menos, difícil aperta mais)."""
    mult = _CREEP_BY_SIGNAL.get(hardware.derived(state.rig).signal, 1.0) * state.mod_creep
    if diff is not None:
        mult *= diff.creep_mult
    return mult


def typing_bonus(state: GameState) -> float:
    """Segundos extras nos minigames (0 se superaquecido)."""
    if is_overheated(state):
        return 0.0
    return hardware.derived(state.rig).typing_bonus


def tele_speed(state: GameState) -> float:
    """Multiplicador de velocidade do teletype (CPU melhor = texto mais rápido)."""
    mult = hardware.derived(state.rig).tele_mult
    return mult * (0.6 if is_overheated(state) else 1.0)


# --------------------------------------------------------------------------- #
# Carrinho da loja
# --------------------------------------------------------------------------- #
@dataclass
class CartLine:
    part_id: str
    ok: bool
    reason: str          # por que não dá para instalar, se for o caso


@dataclass
class CartPreview:
    lines: list[CartLine]
    total: float
    affordable: bool
    ok: bool             # tudo instalável E dentro do saldo


def preview_cart(state: GameState, cart: list[str]) -> CartPreview:
    """Valida o carrinho inteiro ANTES de cobrar.

    A ordem importa: comprar uma placa-mãe nova e depois a RAM dela só funciona
    nessa ordem. Por isso a checagem simula as peças em cima de uma CÓPIA do
    rig, uma a uma — assim o carrinho conta a verdade em vez de aprovar coisas
    que o checkout depois recusaria.
    """
    rig = state.rig.copy()
    lines: list[CartLine] = []
    total = 0.0
    for pid in cart:
        part = CATALOG.get(pid)
        if part is None:
            lines.append(CartLine(pid, False, i18n.t("eco_item_not_found")))
            continue
        ok, reason = hardware.can_install(rig, part)
        if ok:
            hardware.install(rig, part)
            total += part.price
        lines.append(CartLine(pid, ok, "" if ok else reason))
    total = round(total, 2)
    affordable = state.wallet >= total
    return CartPreview(lines, total, affordable,
                       affordable and all(l.ok for l in lines))


def checkout(state: GameState, cart: list[str]) -> tuple[bool, list[str]]:
    """Cobra e instala o carrinho inteiro. Ou vai tudo, ou não vai nada."""
    pv = preview_cart(state, cart)
    if not cart:
        return False, [i18n.t("eco_cart_empty")]
    if not pv.affordable:
        return False, [i18n.t("eco_cart_insufficient_funds", total=pv.total, coin=hardware.COIN, balance=state.wallet)]
    ruins = [l for l in pv.lines if not l.ok]
    if ruins:
        return False, [i18n.t("eco_cart_line_error", name=CATALOG[l.part_id].name if l.part_id in CATALOG else l.part_id, reason=l.reason) for l in ruins]
    msgs: list[str] = []
    for pid in cart:
        part = CATALOG[pid]
        state.wallet = round(state.wallet - part.price, 3)
        for w in hardware.install(state.rig, part):
            msgs.append(w)
        msgs.append(i18n.t("eco_buy_installed", name=part.name, price=part.price, coin=hardware.COIN))
    return True, msgs


def buy(state: GameState, part_id: str) -> tuple[bool, str, list[str]]:
    """Compra e instala uma peça. Retorna (ok, mensagem, avisos)."""
    part = CATALOG.get(part_id)
    if not part:
        return False, i18n.t("eco_buy_not_found", part_id=part_id), []
    if hardware.is_installed(state.rig, part):
        return False, i18n.t("eco_buy_already_installed", name=part.name), []
    if state.wallet < part.price:
        return False, i18n.t("eco_buy_insufficient_funds", name=part.name, price=part.price, coin=hardware.COIN, balance=state.wallet), []
    ok, reason = hardware.can_install(state.rig, part)
    if not ok:
        return False, i18n.t("eco_buy_cannot_install", name=part.name, reason=reason), []
    state.wallet = round(state.wallet - part.price, 3)
    warnings = hardware.install(state.rig, part)
    return True, i18n.t("eco_buy_installed", name=part.name, price=part.price, coin=hardware.COIN), warnings
