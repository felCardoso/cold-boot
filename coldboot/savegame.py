"""Save/load da partida em JSON.

A run inteira nasce de uma seed, então seria tentador salvar só a seed e
regerar o mundo. Não dá: a partida acumula mutações que não voltam da seed —
itens consumidos somem do filesystem, pastas destrancadas, nós comprometidos,
o rig remontado. Por isso serializamos o estado de verdade.

Módulo puro: recebe/devolve GameState e um caminho, sem tocar na UI.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .hardware import Rig
from .procgen.rng import make_rng
from .settings import GAME_DIR
from .state import FSNode, GameState, NetNode

SAVE_PATH = GAME_DIR / "save.json"
# v2: inventário virou lista de itens (era set de nomes), ram_free virou
#     derivado e entraram os contadores de incursão.
# v3: rig.gpu (uma) virou rig.gpus (lista, uma por slot PCIe), entrou o
#     roteador e o jogo passou a ter setores.
# v4: entrou meta-progressão lifetime (total_earned/deaths/achievements),
#     sobrevive a mortes igual run_number/best_sector.
SAVE_VERSION = 4


# --------------------------------------------------------------------------- #
# Serialização
# --------------------------------------------------------------------------- #
def _fs_to_dict(node: FSNode) -> dict:
    return {
        "name": node.name,
        "is_dir": node.is_dir,
        "content": node.content,
        "locked": node.locked,
        "hack_id": node.hack_id,
        "on_read": node.on_read,
        "item": node.item,
        # dict preserva a ordem de inserção, então o `ls` sai igual ao salvo
        "children": [_fs_to_dict(c) for c in node.children.values()],
    }


def _fs_from_dict(d: dict) -> FSNode:
    node = FSNode(
        name=d["name"],
        is_dir=d["is_dir"],
        content=d.get("content"),
        locked=d.get("locked", False),
        hack_id=d.get("hack_id"),
        on_read=d.get("on_read"),
        item=d.get("item"),
    )
    for child in d.get("children", []):
        node.add(_fs_from_dict(child))
    return node


def _net_to_dict(n: NetNode) -> dict:
    return {
        "id": n.id,
        "label": n.label,
        "col": n.col,
        "row": n.row,
        "links": list(n.links),
        "state": n.state,
        "hack_id": n.hack_id,
        "depth": n.depth,
        "fs": _fs_to_dict(n.fs) if n.fs else None,
    }


def _net_from_dict(d: dict) -> NetNode:
    return NetNode(
        id=d["id"],
        label=d["label"],
        col=d["col"],
        row=d["row"],
        links=list(d.get("links", [])),
        state=d.get("state", "fog"),
        hack_id=d.get("hack_id"),
        depth=d.get("depth", 0),
        fs=_fs_from_dict(d["fs"]) if d.get("fs") else None,
    )


def state_to_dict(state: GameState) -> dict:
    return {
        "version": SAVE_VERSION,
        "seed": state.seed,
        "core_id": state.core_id,
        "trace": state.trace,
        "ram_total": state.ram_total,  # ram_free é derivado; não se salva
        "connection": state.connection,
        "root": _fs_to_dict(state.root) if state.root else None,
        "cwd": list(state.cwd),
        "net": [_net_to_dict(n) for n in state.net.values()],
        "location": state.location,
        "inventory": [dict(it) for it in state.inventory],
        "flags": dict(state.flags),
        "lockdown_level": state.lockdown_level,
        "run_number": state.run_number,
        "runs_won": state.runs_won,
        "sector": state.sector,
        "best_sector": state.best_sector,
        "wallet": state.wallet,
        "rig": asdict(state.rig),
        "heat": state.heat,
        "processes": list(state.processes),
        "adminkey": state.adminkey,
        "puzzle_code": state.puzzle_code,
        "botnet": dict(state.botnet),
        "cipher_uses": state.cipher_uses,
        "modifier_id": state.modifier_id,
        "mod_creep": state.mod_creep,
        "mod_ice_penalty": state.mod_ice_penalty,
        "mod_botnet_risk": state.mod_botnet_risk,
        "mod_payout": state.mod_payout,
        "total_earned": state.total_earned,
        "deaths": state.deaths,
        "achievements": sorted(state.achievements),
    }


def state_from_dict(d: dict) -> GameState:
    st = GameState()
    st.seed = d["seed"]
    st.rng = make_rng(st.seed)
    st.core_id = d["core_id"]
    st.trace = d["trace"]
    st.add_trace(0.0)  # recomputa `connection` a partir do trace (não se salva)
    st.ram_total = d.get("ram_total", 640)
    st.root = _fs_from_dict(d["root"]) if d.get("root") else None
    st.cwd = list(d.get("cwd", []))
    st.net = {n["id"]: _net_from_dict(n) for n in d.get("net", [])}
    st.location = d.get("location", "GATE")
    st.inventory = [dict(it) for it in d.get("inventory", [])]
    st.flags = dict(d.get("flags", {}))
    st.lockdown_level = d.get("lockdown_level", 0)
    st.wallet = d.get("wallet", 0.0)
    st.run_number = d.get("run_number", 1)
    st.runs_won = d.get("runs_won", 0)
    st.sector = d.get("sector", 1)
    st.best_sector = d.get("best_sector", st.sector)
    rig = d.get("rig", {})
    st.rig = Rig(
        mobo=rig.get("mobo", "mb_a1"),
        cpu=rig.get("cpu", "cpu_s1"),
        ram=list(rig.get("ram", ["ram_d3_4"])),
        gpus=list(rig.get("gpus", [])),
        psu=rig.get("psu", "psu_300"),
        cooler=rig.get("cooler", "cool_stock"),
        router=rig.get("router", "net_dsl"),
    )
    st.heat = d.get("heat", 32.0)
    st.processes = list(d.get("processes", []))
    st.adminkey = d.get("adminkey", 0)
    st.puzzle_code = d.get("puzzle_code", "")
    st.botnet = dict(d.get("botnet", {}))
    st.cipher_uses = d.get("cipher_uses", 0)
    st.modifier_id = d.get("modifier_id", "")
    st.mod_creep = d.get("mod_creep", 1.0)
    st.mod_ice_penalty = d.get("mod_ice_penalty", 1.0)
    st.mod_botnet_risk = d.get("mod_botnet_risk", 1.0)
    st.mod_payout = d.get("mod_payout", 1.0)
    st.total_earned = d.get("total_earned", 0.0)
    st.deaths = d.get("deaths", 0)
    st.achievements = set(d.get("achievements", []))
    return st


# --------------------------------------------------------------------------- #
# Migração entre versões de save
# --------------------------------------------------------------------------- #
def migrate(d: dict) -> dict | None:
    """Traz um save antigo para o formato atual. None = não dá para ler.

    Saves na versão anterior existem em disco de gente que já estava jogando —
    recusá-los seria jogar a partida dessas pessoas fora por uma mudança de
    formato nossa.
    """
    version = d.get("version")
    if version is None or version > SAVE_VERSION:
        return None  # versão futura: melhor não chutar
    if version == 1:
        # v1 -> v2:
        #   * inventory era uma lista de nomes; agora carrega os dados do item
        #   * ram_free era salvo; agora é derivado (processos + buffer)
        #   * não existiam contadores de incursão
        d["inventory"] = [{"name": n, "kind": n} for n in d.get("inventory", [])]
        d.pop("ram_free", None)
        d.setdefault("run_number", 1)
        d.setdefault("runs_won", 0)
        version = 2
    if version == 2:
        # v2 -> v3:
        #   * rig.gpu (uma só) virou rig.gpus (lista, uma por slot PCIe)
        #   * entrou o roteador (quem não tinha fica com o modem da operadora)
        #   * o jogo passou a ter setores
        rig = d.get("rig", {})
        gpu = rig.pop("gpu", None)
        rig.setdefault("gpus", [gpu] if gpu else [])
        rig.setdefault("router", "net_dsl")
        d["rig"] = rig
        d.setdefault("sector", 1)
        d.setdefault("best_sector", 1)
        version = 3
    if version == 3:
        # v3 -> v4: meta-progressão lifetime nova, quem já jogava começa zerado.
        d.setdefault("total_earned", 0.0)
        d.setdefault("deaths", 0)
        d.setdefault("achievements", [])
        version = 4
    d["version"] = SAVE_VERSION
    return d if version == SAVE_VERSION else None


# --------------------------------------------------------------------------- #
# Disco
# --------------------------------------------------------------------------- #
def save(state: GameState, path: Path | None = None) -> Path:
    p = path or SAVE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state_to_dict(state)), encoding="utf-8")
    return p


def load(path: Path | None = None) -> GameState | None:
    """Devolve o estado salvo, ou None se não houver save legível."""
    p = path or SAVE_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    data = migrate(data)
    if data is None:  # versão futura/desconhecida: melhor não chutar
        return None
    try:
        return state_from_dict(data)
    except (KeyError, TypeError):
        return None


def has_save(path: Path | None = None) -> bool:
    return (path or SAVE_PATH).exists()
