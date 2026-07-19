"""Validador de invariantes do mundo gerado.

O gerador procedural faz PROMESSAS ao jogo: todo host tem o esqueleto de
pastas, o CORE existe e não é o GATE, `scan` sempre tem um caminho de
desbloqueio, o puzzle tem os 3 fragmentos, cofre implica cartão. Quando uma
promessa quebra, o bug aparece longe da causa — uma run insolúvel no setor 12
por um item que sumiu na geração. Este módulo confere todas de uma vez, logo
depois de gerar, onde o stack trace ainda aponta para o culpado.

`validate_state` devolve a lista de violações (vazia = mundo íntegro);
`world.new_game` chama e estoura WorldGenError se houver qualquer uma.
"""

from __future__ import annotations

import collections

from ..state import FSNode, GameState
from .filesystem import CORE_DIRS
from .network import MAX_NODES
from . import loot


class WorldGenError(RuntimeError):
    """O mundo gerado violou uma invariante. A mensagem lista todas."""


def _walk(node: FSNode):
    yield node
    for child in node.children.values():
        yield from _walk(child)


def _contents(fs: FSNode) -> str:
    return "\n".join(n.content for n in _walk(fs) if n.content)


def validate_state(state: GameState) -> list[str]:
    """Confere as invariantes do mundo recém-gerado. [] = tudo certo."""
    v: list[str] = []
    net = state.net

    # ---- grafo da rede ------------------------------------------------- #
    gate = net.get("GATE")
    if gate is None:
        return ["rede: GATE não existe"]  # sem entrada, nada mais é conferível
    if gate.state != "compromised":
        v.append("rede: GATE não começa comprometido")
    if len(net) > MAX_NODES:
        v.append(f"rede: {len(net)} nós passa do teto do mapa ({MAX_NODES})")

    core = net.get(state.core_id)
    if core is None:
        v.append(f"rede: core_id '{state.core_id}' não está no grafo")
    else:
        if core.id == "GATE":
            v.append("rede: o CORE caiu no próprio GATE (run nasceria vencida)")
        if core.label != "CORE":
            v.append(f"rede: o nó objetivo não está rotulado CORE ({core.label})")

    posicoes = collections.Counter((n.col, n.row) for n in net.values())
    for pos, quantos in posicoes.items():
        if quantos > 1:
            v.append(f"rede: {quantos} nós na mesma célula {pos}")

    for n in net.values():
        for lid in n.links:
            outro = net.get(lid)
            if outro is None:
                v.append(f"rede: {n.id} tem link para '{lid}', que não existe")
                continue
            if lid == n.id:
                v.append(f"rede: {n.id} tem link para si mesmo")
            if n.id not in outro.links:
                v.append(f"rede: link {n.id}->{lid} não é simétrico")
            if abs(n.col - outro.col) + abs(n.row - outro.row) != 1:
                # o renderizador do mapa desenha conexões retas entre células
                # vizinhas; um link diagonal/longe sairia invisível na tela
                v.append(f"rede: link {n.id}->{lid} não é adjacente no grid")

    vistos = {"GATE"}
    fila = collections.deque(["GATE"])
    while fila:
        for lid in net[fila.popleft()].links:
            if lid in net and lid not in vistos:
                vistos.add(lid)
                fila.append(lid)
    for n in net.values():
        if n.id not in vistos:
            v.append(f"rede: {n.id} é inalcançável a partir do GATE")

    # ---- filesystem de cada host --------------------------------------- #
    for n in net.values():
        if n.fs is None:
            v.append(f"fs: host {n.id} não tem filesystem")
            continue
        for d in CORE_DIRS:
            pasta = n.fs.children.get(d)
            if pasta is None or not pasta.is_dir:
                v.append(f"fs: host {n.id} sem a pasta obrigatória /{d}")
        # caminho de `scan` garantido: /home/admin sempre tem o subnet.map
        admin = n.fs.children.get("home", FSNode("home", True)).children.get("admin")
        if admin is None:
            v.append(f"fs: host {n.id} sem /home/admin")
        else:
            mapa = admin.children.get("subnet.map")
            if mapa is None or mapa.on_read != "unlock_scan":
                v.append(f"fs: host {n.id} sem subnet.map destravando scan")
        # âncora do puzzle e cwd inicial
        guest = n.fs.children.get("usr", FSNode("usr", True)).children.get("guest")
        if guest is None:
            v.append(f"fs: host {n.id} sem /usr/guest")
        elif n.id == "GATE" and ".history" not in guest.children:
            v.append("fs: GATE sem a âncora .history do puzzle")

    if core is not None and core.fs is not None:
        sys_dir = core.fs.children.get("sys", FSNode("sys", True))
        lock = sys_dir.children.get("core.lock")
        if lock is None or lock.hack_id != "ai_core":
            v.append("fs: o host CORE não tem o core.lock hackeável")

    # ---- promessas do mundo -------------------------------------------- #
    fss = [n.fs for n in net.values() if n.fs is not None]

    # cofre <-> leitor <-> cartão: fechadura sem chave é decoração quebrada
    tem_leitor = any(loot.find_kind(fs, "reader") for fs in fss)
    tem_cartao = any(loot.find_kind(fs, "keycard") for fs in fss)
    if tem_leitor and not tem_cartao:
        v.append("loot: existe leitor de cartão mas nenhuma keycard na rede")
    for n in net.values():
        if n.fs is None:
            continue
        for node in _walk(n.fs):
            if node.item and node.item.get("kind") == "reader":
                abre = node.item.get("opens", "")
                if abre not in {c.name for c in _walk(n.fs) if c.is_dir}:
                    v.append(f"loot: leitor em {n.id} abre '{abre}', que não existe")

    # puzzle: código bem-formado e os 3 fragmentos de fato plantados
    code = state.puzzle_code
    partes = code.split("-") if code else []
    if len(partes) != 3 or any(len(p) != 4 for p in partes):
        v.append(f"puzzle: código malformado ('{code}')")
    else:
        tudo = "\n".join(_contents(fs) for fs in fss)
        for i, frag in enumerate(partes, start=1):
            if frag not in tudo:
                v.append(f"puzzle: fragmento {i} ('{frag}') não está em arquivo nenhum")

    # modificador de setor: sorteado e resolvido em multiplicadores sãos
    if not state.modifier_id:
        v.append("modificador: new_game não sorteou modificador")
    for campo in ("mod_creep", "mod_ice_penalty", "mod_botnet_risk", "mod_payout"):
        if getattr(state, campo) <= 0:
            v.append(f"modificador: {campo} não-positivo ({getattr(state, campo)})")

    return v
