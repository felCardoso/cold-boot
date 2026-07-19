"""Gerador procedural do grafo da rede (o mini-mapa ASCII).

Algoritmo (o mesmo, já testado, do gerador de masmorra):
  1. GATE nasce no canto do grid e a rede cresce por "random walk" em passos
     ortogonais (garante que tudo fica conectado e grid-adjacente, então o
     renderizador de mapa desenha conexões retas).
  2. Algumas ligações extras entre nós vizinhos criam loops.
  3. BFS a partir de GATE mede a profundidade; o nó mais distante vira o
     objetivo (CORE / daemon COLD-BOOT).

Fica dentro de um bounding box pequeno para caber no painel do mapa.
"""

from __future__ import annotations

import collections
import random

from ..state import NetNode

# Rótulos de host de 4 chars (estilo DEC). CORE/GATE são reservados.
_LABELS = [
    "MAIL",
    "FILE",
    "AUTH",
    "ARCH",
    "DNS0",
    "SQL1",
    "VPN0",
    "LOG3",
    "BAK2",
    "NFS1",
    "WEB0",
    "SSH2",
    "DEV0",
    "FTP1",
    "IRC0",
    "GPU2",
]
_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

# Limites do grid para o mapa caber no painel superior.
MAXCOL, MAXROW = 4, 2
MAX_NODES = (MAXCOL + 1) * (MAXROW + 1)


def size_for_sector(rng: random.Random, sector: int) -> int:
    """Quantos hosts o setor tem. Cresce com o setor até bater no teto do grid.

    O mapa ASCII tem largura fixa, então a rede satura em MAX_NODES — daí a
    dificuldade infinita vir do número do setor, não do tamanho da rede.
    """
    base = 5 + sector
    return max(3, min(MAX_NODES, base + rng.randint(0, 2)))


def generate_network(
    rng: random.Random, size: int | None = None
) -> tuple[dict[str, NetNode], str]:
    """Retorna (net, core_id). GATE começa comprometido; o resto na névoa."""
    if size is None:
        size = rng.randint(6, 10)
    size = max(2, min(size, MAX_NODES))

    labels = _LABELS[:]
    rng.shuffle(labels)
    used_ids = {"GATE"}

    def next_label() -> str:
        # O id do nó É o rótulo, e os dicts da rede são indexados por ele: um
        # id repetido faria o dict engolir um nó silenciosamente e deixaria
        # links apontando para o nó errado. Unicidade aqui é obrigatória, não
        # cosmética — inclusive no fallback H##, que pode sortear repetido.
        while labels:
            lab = labels.pop()
            if lab not in used_ids:
                used_ids.add(lab)
                return lab
        while True:
            lab = f"H{rng.randint(10, 99)}"
            if lab not in used_ids:
                used_ids.add(lab)
                return lab

    cells: dict[tuple[int, int], NetNode] = {}
    order: list[NetNode] = []

    def add(col: int, row: int, nid: str) -> NetNode:
        node = NetNode(id=nid, label=nid, col=col, row=row)
        cells[(col, row)] = node
        order.append(node)
        return node

    gate = add(0, 0, "GATE")
    gate.state = "compromised"

    # 1) random walk
    attempts = 0
    while len(order) < size and attempts < size * 400:
        attempts += 1
        base = rng.choice(order)
        dc, dr = rng.choice(_DIRS)
        nc, nr = base.col + dc, base.row + dr
        if not (0 <= nc <= MAXCOL and 0 <= nr <= MAXROW):
            continue
        if (nc, nr) in cells:
            continue
        node = add(nc, nr, next_label())
        base.links.append(node.id)
        node.links.append(base.id)

    # O CORE é "o nó mais fundo", então precisa existir um nó além do GATE —
    # senão o objetivo cairia no próprio GATE e a run nasceria vencida. O
    # random walk não falha na prática, mas isto é garantia estrutural, não
    # probabilística: se por absurdo ele não produziu nada, força um vizinho.
    if len(order) < 2:
        node = add(1, 0, next_label())
        gate.links.append(node.id)
        node.links.append(gate.id)

    # 2) ligações extras (loops)
    for node in order:
        for dc, dr in _DIRS:
            nb = cells.get((node.col + dc, node.row + dr))
            if (
                nb
                and nb.id != node.id
                and nb.id not in node.links
                and rng.random() < 0.18
            ):
                node.links.append(nb.id)
                nb.links.append(node.id)

    # 3) BFS de profundidade a partir de GATE
    idmap = {n.id: n for n in order}
    depth = {"GATE": 0}
    q = collections.deque(["GATE"])
    while q:
        cid = q.popleft()
        for lid in idmap[cid].links:
            if lid not in depth:
                depth[lid] = depth[cid] + 1
                q.append(lid)
    for n in order:
        n.depth = depth.get(n.id, 0)

    # objetivo = nó mais distante da entrada
    objective = max(order, key=lambda n: n.depth)
    objective.label = "CORE"
    objective.hack_id = "ai_core"
    core_id = objective.id

    for n in order:
        if n.id != "GATE" and n is not objective:
            n.hack_id = n.id.lower()

    net = {n.id: n for n in order}
    return net, core_id
