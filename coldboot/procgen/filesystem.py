"""Fase 2 — gera um filesystem UNIX por host da rede.

Cada nó da rede recebe sua própria árvore (esqueleto UNIX padrão), com o
conteúdo dos arquivos vindo da gramática (Fase 3). Determinístico: mesmo rng
+ mesma ordem de hosts => mesmos filesystems.

`generate_filesystem` é só o orquestrador: cada pasta do esqueleto tem seu
próprio construtor `_build_*` abaixo, na MESMA ordem (e mesma ordem de
chamadas de `rng`) que o orquestrador segue — trocar a ordem muda o mundo que
sai de uma seed já compartilhada, então isso é regra dura, não estética.
"""

from __future__ import annotations

import random

from ..state import FSNode
from . import grammar
from . import loot


def _maybe_history(rng: random.Random, folder: FSNode, chance: float) -> None:
    """Cópia decorativa de `.history`: com probabilidade `chance`, mais uma
    pasta guarda o rastro de comandos de alguém. Só a de /usr/guest é garantida."""
    if ".history" not in folder.children and rng.random() < chance:
        folder.add(FSNode(".history", False, content=grammar.history_lines(rng)))


def default_cwd(fs: FSNode) -> list[str]:
    """Diretório onde o jogador 'cai' ao entrar num host."""
    if "usr" in fs.children and "guest" in fs.children["usr"].children:
        return ["usr", "guest"]
    return []


# Pastas que todo host tem, sempre. São o esqueleto que torna o jogo
# aprendível: por mais aleatório que o resto fique, você sempre sabe que
# /etc guarda a identidade da máquina e /var/log guarda o que ela viu.
CORE_DIRS = ("etc", "var", "usr", "home", "sys", "tmp", "users")

# Pastas de sabor, sorteadas por host — variedade sem esconder o essencial.
_EXTRA_DIRS = [
    ("opt", ["license.txt", "patch_notes"]),
    ("mnt", ["backup_tape", "volume.cfg"]),
    ("srv", ["export.cfg", "quota"]),
    ("proc", ["meminfo", "cpuinfo"]),
    ("lib", ["libcold.so", "crt0.o"]),
    ("boot", ["vmunix", "boot.cfg"]),
]


def _build_etc(rng: random.Random, lore: grammar.Lore) -> FSNode:
    etc = FSNode("etc", True)
    etc.add(FSNode("motd", False, content=grammar.motd(rng, lore)))
    etc.add(FSNode("passwd", False, content=grammar.passwd(rng, lore)))
    # A tabela de IP/MAC da sub-rede: um dos dois caminhos (o outro é o admin)
    # que libera `scan`. Não é garantida em todo host — às vezes você tem que
    # procurar noutro lugar.
    if rng.random() < 0.7:
        etc.add(
            FSNode(
                "hosts", False, content=grammar.hosts_file(rng, lore),
                on_read="unlock_scan",
            )
        )
    return etc


def _build_var(rng: random.Random, lore: grammar.Lore) -> tuple[FSNode, FSNode]:
    var = FSNode("var", True)
    log = FSNode("log", True)
    log.add(
        FSNode(
            "auth.log", False, content=grammar.auth_log(rng, lore), on_read="read_auth"
        )
    )
    log.add(FSNode("kernel.log", False, content=grammar.kernel_log(rng, lore)))
    var.add(log)
    return var, log


def _build_usr(rng: random.Random, lore: grammar.Lore) -> tuple[FSNode, FSNode]:
    usr = FSNode("usr", True)
    guest = FSNode("guest", True)
    guest.add(FSNode("readme.txt", False, content=grammar.readme(rng, lore)))
    # Cópia âncora: sempre existe aqui, mas o CONTEÚDO agora varia por seed
    # (era uma string fixa igual em todo host).
    guest.add(FSNode(".history", False, content=grammar.history_lines(rng)))
    usr.add(guest)
    return usr, guest


def _build_home(rng: random.Random, lore: grammar.Lore) -> tuple[FSNode, FSNode]:
    # /home/admin (trancado -> hack). O outro caminho para `scan`: quem chega
    # até aqui (hack ou chave-admin) já provou que sabe se mover pela rede.
    home = FSNode("home", True)
    admin = FSNode("admin", True, locked=True, hack_id="admin_home")
    admin.add(FSNode("mail", False, content=grammar.email(rng, lore)))
    admin.add(
        FSNode(
            "subnet.map", False, content=grammar.hosts_file(rng, lore),
            on_read="unlock_scan",
        )
    )
    _maybe_history(rng, admin, 0.25)
    home.add(admin)
    return home, admin


def _build_sys(rng: random.Random, depth: int, is_core: bool) -> FSNode:
    sys = FSNode("sys", True)
    sys.add(
        FSNode(
            "ai_daemon", False, content=grammar.daemon_taunt(rng), on_read="poke_daemon"
        )
    )
    if is_core:
        sys.add(
            FSNode(
                "core.lock",
                False,
                locked=True,
                hack_id="ai_core",
                content="CORE OFFLINE. COLD-BOOT daemon shut down.",
            )
        )
    # Leitor de cartão + cofre: só fora da borda da rede (a entrada não tem).
    if depth >= 1 and rng.random() < 0.35:
        loot.add_card_reader(rng, sys, depth)
    return sys


def _build_tmp(rng: random.Random) -> FSNode:
    # /tmp with random junk (variety per host)
    tmp = FSNode("tmp", True)
    for _ in range(rng.randint(0, 2)):
        fn = grammar.random_filename(rng)
        if fn not in tmp.children:
            tmp.add(
                FSNode(fn, False, content=f"(binary data: {rng.randint(1,64)}KB)\n")
            )
    _maybe_history(rng, tmp, 0.2)
    return tmp


def _build_users(
    rng: random.Random, host_label: str, lore: grammar.Lore
) -> tuple[FSNode, list[str]]:
    # /users/<nome> — as pessoas que trabalhavam nesta máquina. Uma pasta por
    # login, com nome procedural; é onde mora o lore pessoal e o loot melhor.
    users = FSNode("users", True)
    nomes: list[str] = []
    for _ in range(rng.randint(1, 3)):
        nome = grammar.username(rng)
        if nome in users.children:
            continue
        nomes.append(nome)
        casa = FSNode(nome, True)
        casa.add(FSNode("notes.txt", False, content=grammar.readme(rng, lore)))
        casa.add(
            FSNode(
                ".profile",
                False,
                content=f"export USER={nome}\nexport HOST={host_label}\n"
                f"export TERM=vt220\n",
            )
        )
        if rng.random() < 0.5:
            casa.add(FSNode("mail", False, content=grammar.email(rng, lore)))
        _maybe_history(rng, casa, 0.2)
        users.add(casa)
    return users, nomes


def _build_extra_dirs(
    rng: random.Random, lore: grammar.Lore, depth: int, sector: int
) -> list[FSNode]:
    # Pastas de sabor sorteadas (o "aleatório" por cima do esqueleto fixo). O
    # sprinkle de loot fica DENTRO deste mesmo loop, logo após montar cada
    # pasta — igual ao original — para não mudar a ordem de consumo do rng
    # entre pastas (sprinkle separado em outro loop já quebrou reprodutibilidade).
    extras = []
    for nome, arquivos in rng.sample(_EXTRA_DIRS, k=rng.randint(1, 3)):
        extra = FSNode(nome, True)
        for fn in arquivos:
            extra.add(
                FSNode(
                    fn, False, content=f"({fn}: {rng.randint(1, 512)}KB, {lore.os})\n"
                )
            )
        loot.sprinkle(rng, extra, depth + sector, chance=0.20)
        extras.append(extra)
    return extras


def generate_filesystem(
    rng: random.Random,
    host_label: str,
    depth: int,
    is_core: bool = False,
    sector: int = 1,
) -> FSNode:
    lore = grammar.make_lore(rng, host=host_label)
    root = FSNode("/", True)

    etc = _build_etc(rng, lore)
    root.add(etc)

    var, log = _build_var(rng, lore)
    root.add(var)

    usr, guest = _build_usr(rng, lore)
    root.add(usr)

    home, admin = _build_home(rng, lore)
    root.add(home)

    sys = _build_sys(rng, depth, is_core)
    root.add(sys)

    tmp = _build_tmp(rng)
    root.add(tmp)

    users, nomes = _build_users(rng, host_label, lore)
    root.add(users)

    for extra in _build_extra_dirs(rng, lore, depth, sector):
        root.add(extra)

    # Loot procedural com chances moderadas. Hosts mais fundos (e o admin,
    # trancado) tendem a esconder mais. A maioria das pastas fica vazia.
    # O setor entra como profundidade extra: setor 9 paga melhor que o 1.
    d = depth + (sector - 1)
    loot.sprinkle(rng, tmp, d, chance=0.30)
    loot.sprinkle(rng, guest, d, chance=0.22)
    loot.sprinkle(rng, admin, d + 1, chance=0.55)  # atrás do cadeado: recompensa melhor
    loot.sprinkle(rng, log, d, chance=0.15)
    for nome in nomes:
        loot.sprinkle(rng, users.children[nome], d, chance=0.35)

    return root
