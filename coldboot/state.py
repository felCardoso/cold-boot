"""State Manager — todo o estado do jogo, sem nenhuma dependência de UI.

Mantido puro de propósito: pode ser testado sem terminal e serializado para
save/load no futuro. A UI (app.py) apenas lê este estado e o re-renderiza.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .hardware import (HOST_RAM_KB, ITEM_KB, RAM_TIGHT_KB, Rig, miner_footprint,
                       starting_rig)


# --------------------------------------------------------------------------- #
# Sistema de arquivos falso (a máquina UNIX de 1988 que você invadiu)
# --------------------------------------------------------------------------- #
@dataclass
class FSNode:
    name: str
    is_dir: bool
    content: str | None = None          # texto de arquivos (para `cat`)
    children: dict[str, "FSNode"] = field(default_factory=dict)
    locked: bool = False                # exige `hack` para abrir
    hack_id: str | None = None          # identifica o desafio de combate
    on_read: str | None = None          # evento disparado ao ler (flag)
    item: dict | None = None            # loot procedural (Fase de itens)

    def add(self, node: "FSNode") -> "FSNode":
        self.children[node.name] = node
        return self


# --------------------------------------------------------------------------- #
# Grafo da rede (o mini-mapa ASCII com névoa de guerra)
# --------------------------------------------------------------------------- #
# Estados de um nó da rede:
#   "fog"         -> desconhecido (névoa)
#   "discovered"  -> visível, porém trancado
#   "compromised" -> invadido (verde)
@dataclass
class NetNode:
    id: str
    label: str          # até 5 chars, cabe no box do mapa
    col: int            # posição no grid do mapa ASCII
    row: int
    links: list[str] = field(default_factory=list)
    state: str = "fog"
    hack_id: str | None = None
    depth: int = 0      # distância (em saltos) da entrada; escala dificuldade
    fs: "FSNode | None" = None   # filesystem próprio deste host (Fase 2)


@dataclass
class GameState:
    seed: int = 0               # seed que gerou esta run (reproduzível)
    core_id: str = "CORE"       # id do nó objetivo (daemon COLD-BOOT)

    # RNG da run (semeado por `seed`), reusado por combat.py/lockdown.py para
    # que ICE e LOCKDOWN também saiam reproduzíveis, não só a geração do mundo.
    # Não é salvo — savegame.py reconstrói via make_rng(seed) no load.
    rng: random.Random | None = field(default=None, repr=False, compare=False)

    # Recursos exibidos no painel de status
    trace: float = 8.0          # nível de rastreamento 0..100 (game over em 100)
    ram_total: int = HOST_RAM_KB   # KB do HOST invadido (ram_free é derivado)
    connection: str = "stable"    # stable | unstable | critical | lost (interno, ver add_trace)

    # Filesystem: o FS ativo é o do host atual (state.net[location].fs).
    # `root` é só um fallback vazio para um estado recém-criado sem rede.
    root: FSNode | None = None
    cwd: list[str] = field(default_factory=list)   # ex.: ["usr", "guest"]

    # Rede / mapa
    net: dict[str, NetNode] = field(default_factory=dict)
    location: str = "GATE"      # nó da rede em que você está "jackeado"

    # Progresso
    # Itens carregados no buffer: dicts do loot + "name". Ocupam RAM do host.
    inventory: list[dict] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    lockdown_level: int = 0     # escalonamento do minigame de Trace 100%

    # Puzzle de código do setor (ver puzzle.py). O "resolvido" mora em
    # flags["puzzle_solved"] — não precisa de campo próprio.
    puzzle_code: str = ""

    # Minigame de cifra (ver cipher.py): quantas vezes já foi jogado NESTE
    # setor. Reseta sozinho a cada setor/morte, porque GameState nasce de novo
    # a cada `new_game()`.
    cipher_uses: int = 0

    # Botnet: host_id -> ticks desde que o script foi plantado lá. Só existe
    # em hosts comprometidos NESTE setor — reseta ao trocar de setor/morrer,
    # como tudo mais do lado de dentro.
    botnet: dict[str, int] = field(default_factory=dict)

    # Meta (roguelike): sobrevive entre incursões
    run_number: int = 1
    runs_won: int = 0
    # Setor atual: o eixo infinito do jogo. A rede não pode crescer (o mapa
    # ASCII trava em 15 hosts), então quem escala para sempre é este número —
    # ele multiplica ICE, loot e pagamento.
    sector: int = 1
    best_sector: int = 1

    # Modificador do setor (ver world.SECTOR_MODIFIERS): sorteado uma vez em
    # new_game() e guardado já resolvido em multiplicadores — quem consome
    # (economy.py, combat.py) só lê um float, sem precisar importar world.py.
    # modifier_id é só para exibição (`i18n.t(f"world_mod_{modifier_id}_name")`).
    modifier_id: str = ""
    mod_creep: float = 1.0
    mod_ice_penalty: float = 1.0
    mod_botnet_risk: float = 1.0
    mod_payout: float = 1.0

    # Economia / hardware
    wallet: float = 0.0                       # saldo de cripto (CRN)
    rig: Rig = field(default_factory=starting_rig)
    heat: float = 32.0                        # temperatura atual (°C)
    processes: list[str] = field(default_factory=list)  # ex.: ["miner"]
    adminkey: int = 0                         # cargas de chave de admin

    # ------------------------------------------------------------------ #
    # Memória do host: processos + itens no buffer disputam os 640K
    # ------------------------------------------------------------------ #
    def ram_used(self) -> int:
        kb = len(self.inventory) * ITEM_KB
        if "miner" in self.processes:
            kb += miner_footprint(self.rig)
        return kb

    @property
    def ram_free(self) -> int:
        return max(0, self.ram_total - self.ram_used())

    @property
    def ram_tight(self) -> bool:
        """Host com pouca memória livre = host desconfiado."""
        return self.ram_free < RAM_TIGHT_KB

    def can_hold(self, n: int = 1) -> bool:
        return self.ram_free >= ITEM_KB * n

    # ------------------------------------------------------------------ #
    # Inventário (itens carregados, não só nomes)
    # ------------------------------------------------------------------ #
    def find_item(self, name: str) -> dict | None:
        """Item do buffer por nome exato ou por kind ('use keycard')."""
        n = name.lower()
        for it in self.inventory:
            if it.get("name", "").lower() == n:
                return it
        for it in self.inventory:
            if it.get("kind", "").lower() == n:
                return it
        return None

    # ------------------------------------------------------------------ #
    # Filesystem helpers (operam sobre o FS do host atual)
    # ------------------------------------------------------------------ #
    def current_fs(self) -> FSNode:
        node = self.net.get(self.location)
        if node is not None and node.fs is not None:
            return node.fs
        if self.root is None:
            self.root = FSNode("/", True)
        return self.root

    def node_at(self, parts: list[str]) -> FSNode | None:
        node = self.current_fs()
        for p in parts:
            if not node.is_dir or p not in node.children:
                return None
            node = node.children[p]
        return node

    def cwd_node(self) -> FSNode:
        return self.node_at(self.cwd) or self.current_fs()

    def cwd_str(self) -> str:
        return "/" + "/".join(self.cwd)

    def resolve(self, path: str) -> tuple[list[str] | None, FSNode | None]:
        """Resolve um caminho relativo/absoluto -> (parts, node)."""
        if path in ("/", ""):
            parts: list[str] = []
        elif path.startswith("/"):
            parts = [p for p in path.split("/") if p]
        else:
            parts = list(self.cwd)
            for token in path.split("/"):
                if token in ("", "."):
                    continue
                if token == "..":
                    if parts:
                        parts.pop()
                else:
                    parts.append(token)
        return parts, self.node_at(parts)

    # ------------------------------------------------------------------ #
    # Rede / mapa helpers
    # ------------------------------------------------------------------ #
    def reveal_neighbors(self, node_id: str) -> list[str]:
        """Dissipa a névoa em volta de um nó. Retorna os ids recém-revelados."""
        revealed: list[str] = []
        node = self.net.get(node_id)
        if not node:
            return revealed
        for nid in node.links:
            n = self.net.get(nid)
            if n and n.state == "fog":
                n.state = "discovered"
                revealed.append(nid)
        return revealed

    def add_trace(self, amount: float) -> None:
        # Códigos internos em inglês, fixos — não é texto de exibição (isso é
        # i18n.t(f"conn_{connection}") em ui.py). Guardar o rótulo traduzido
        # aqui acoplaria o estado do jogo ao idioma da UI.
        self.trace = max(0.0, min(100.0, self.trace + amount))
        if self.trace >= 100:
            self.connection = "lost"
        elif self.trace >= 75:
            self.connection = "critical"
        elif self.trace >= 40:
            self.connection = "unstable"
        else:
            self.connection = "stable"

    @property
    def is_traced(self) -> bool:
        return self.trace >= 100
