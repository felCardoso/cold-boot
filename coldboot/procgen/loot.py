"""Itens de loot procedurais espalhados pelo filesystem.

Cada item segue um modelo (kind) mas com nome semi-aleatório e valores que
escalam com a profundidade. A chance de aparecer é moderada — a maioria das
pastas fica vazia.
"""

from __future__ import annotations

import random
import string

from ..state import FSNode
from . import grammar

_B58 = string.ascii_uppercase + string.ascii_lowercase + string.digits

# Modelos de item: kind + peso (raridade) + nomes semi-aleatórios possíveis.
_TEMPLATES = [
    ("miner", 3, ["cryptominer_{s}.py", "xmrig_{s}.conf", "hashd_{s}.sh", "btc_miner_{s}.py"]),
    ("wallet", 3, ["wallet_{s}.dat", "keystore_{s}.json", "btx_{s}.wallet"]),
    ("credits", 3, ["voucher_{s}.txt", "payout_{s}.log", "dust_{s}.dat"]),
    ("adminkey", 2, ["admin_{s}.key", "root_token_{s}.gpg", "su_{s}.pem"]),
    ("coolant", 2, ["coolant_{s}.sh", "thermald_{s}.cfg"]),
    ("scrambler", 1, ["scrambler_{s}.bin", "proxychain_{s}.cfg"]),
    ("keycard", 2, ["keycard_{s}.bin", "badge_{s}.dat", "cartao_{s}.id"]),
    ("spoof", 1, ["masquerade_{s}.bat", "impersonate_{s}.sh", "ghostuser_{s}.bat"]),
    ("backdoor", 1, ["backdoor_{s}.key", "rootshell_{s}.pem", "sudoer_{s}.tok"]),
]

_CARD_SERIES = ["ORION", "VESPER", "HALCON", "MERIDIAN", "TALOS"]


def _sfx(rng: random.Random) -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return f"{rng.randint(0, 0xffff):04x}"
    if style == 1:
        return str(rng.randint(2, 99))
    return f"{rng.randint(0, 255):02x}{rng.randint(0, 255):02x}"


def _addr(rng: random.Random) -> str:
    return "crn1" + "".join(rng.choice(_B58) for _ in range(rng.randint(24, 30)))


def _content(rng: random.Random, kind: str, data: dict) -> str:
    if kind == "miner":
        return (f"# {kind}: memory-hard miner (randomx algorithm)\n"
                f"pool = stratum+tcp://pool.crn.onion:3333\n"
                f"wallet = {_addr(rng)}\n"
                f"threads = auto   # uses CPU + RAM\n"
                f"# `run <file>` to start; `ps` to view; `kill miner` to stop.\n")
    if kind == "wallet":
        return f"address: {_addr(rng)}\nrecoverable balance: {data['amount']:.3f} CRN\n"
    if kind == "credits":
        return f"payout proof: {data['amount']:.3f} CRN credited to bearer.\n"
    if kind == "adminkey":
        return (f"----- PRIVILEGED ACCESS KEY -----\n"
                f"charges: {data['charges']}   (bypasses one locked resource)\n"
                f"WARNING: suspicious use may disable the admin login.\n")
    if kind == "coolant":
        return f"#!/bin/sh\n# injects coolant into loop: -{data['amount']} C\n"
    if kind == "scrambler":
        return f"# signal scrambler: -{data['amount']}% trace reduction and resets siege\n"
    if kind == "spoof":
        return (f"# masquerade script: hijacks a logged-in session for a moment\n"
                f"impersonates: {data['fake_user']}\n"
                f"# `run <file>` to triangulate the signal as someone else: -{data['amount']} trace\n")
    if kind == "backdoor":
        return ("----- ONE-SHOT BACKDOOR CREDENTIAL -----\n"
                 "grants silent access to ONE locked resource or network node —\n"
                 "no ICE, no duel. does not work on a sector's CORE.\n"
                 "`take` to carry; `use <file> on <target>` to spend it.\n")
    if kind == "keycard":
        return (f"----- PHYSICAL ACCESS CARD -----\n"
                f"series: {data['code']}\n"
                f"opens card readers (leitor.dev) on the zeta-dynamics network.\n"
                f"`take` to carry; `use <card> on leitor.dev` in the vault room.\n")
    return "(data)\n"


def generate_item(rng: random.Random, depth: int, kind: str | None = None) -> FSNode:
    """Um item procedural. `kind` força o tipo (o resto sorteia por peso)."""
    if kind is None:
        kind = rng.choices([t[0] for t in _TEMPLATES],
                           weights=[t[1] for t in _TEMPLATES])[0]
    names = next(t[2] for t in _TEMPLATES if t[0] == kind)
    name = rng.choice(names).format(s=_sfx(rng))

    data: dict = {"kind": kind}
    if kind == "keycard":
        data["code"] = f"{rng.randint(0, 255):02X}-{rng.choice(_CARD_SERIES)}-" \
                       f"{rng.randint(0, 255):02X}"
    elif kind == "wallet":
        data["amount"] = round(rng.uniform(2, 8) + depth * 1.5, 3)
    elif kind == "credits":
        data["amount"] = round(rng.uniform(1, 5) + depth, 3)
    elif kind == "adminkey":
        data["charges"] = rng.randint(1, 2)
    elif kind == "coolant":
        data["amount"] = rng.randint(15, 30)
    elif kind == "scrambler":
        data["amount"] = rng.randint(20, 40)
    elif kind == "spoof":
        data["amount"] = rng.randint(25, 45)
        data["fake_user"] = grammar.username(rng)

    return FSNode(name, False, content=_content(rng, kind, data), item=data)


def place_item(rng: random.Random, folder: FSNode, node: FSNode) -> FSNode:
    """Adiciona o nó à pasta, GARANTIDO. Nome já usado ganha um prefixo novo em
    vez de o item ser descartado em silêncio — descartar quebrava garantias do
    mundo (cofre "de 2 itens" nascendo com 1, keycard garantida sumindo)."""
    base = node.name
    tries = 0
    while node.name in folder.children:
        tries += 1
        # sufixo aleatório primeiro (mantém a estética); contador depois de 8
        # tentativas, porque contador SEMPRE termina — garantia estrutural.
        node.name = f"{_sfx(rng)}_{base}" if tries <= 8 else f"{tries}_{base}"
    folder.add(node)
    return node


def sprinkle(rng: random.Random, folder: FSNode, depth: int, chance: float) -> None:
    """Com probabilidade `chance`, adiciona um item procedural à pasta."""
    if rng.random() < chance:
        place_item(rng, folder, generate_item(rng, depth))


# --------------------------------------------------------------------------- #
# Leitor de cartão + cofre
# --------------------------------------------------------------------------- #
VAULT_NAME = "cofre"
READER_NAME = "leitor.dev"


def add_card_reader(rng: random.Random, folder: FSNode, depth: int) -> None:
    """Installs a card reader and the vault it opens.

    The vault also yields to `hack`, but with expensive ICE — the card is the
    silent shortcut for anyone who found one. High reward precisely because of it.
    """
    reader = FSNode(READER_NAME, False,
                    content=("magnetic card reader — model ZD-114\n"
                             "state: ARMED. awaiting access card.\n"
                             f"locks resource: ./{VAULT_NAME}\n"),
                    item={"kind": "reader", "opens": VAULT_NAME})
    vault = FSNode(VAULT_NAME, True, locked=True, hack_id="card_reader")
    for _ in range(2):
        place_item(rng, vault, generate_item(rng, depth + 2))
    folder.add(reader)
    folder.add(vault)


def find_kind(node: FSNode, kind: str) -> FSNode | None:
    """Procura (em profundidade) o primeiro item de um dado kind."""
    if node.item and node.item.get("kind") == kind:
        return node
    for child in node.children.values():
        found = find_kind(child, kind)
        if found is not None:
            return found
    return None
