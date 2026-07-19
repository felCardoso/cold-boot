"""Fase 3 — geração de lore por gramática.

Tabelas de fragmentos + montadores que produzem MOTD, passwd, logs, e-mails e
provocações da IA. Tudo recebe o mesmo `rng` semeado, então os textos de uma
run são reproduzíveis. Um `Lore` fixa a "identidade" do host (corp, modelo,
admin) para os arquivos ficarem coerentes entre si.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

CORPS = ["ZETA-DYNAMICS", "OMNICORP", "HELIOS SYSTEMS", "BLACKGATE IND.",
         "NAKATOMI DATACORP", "CYGNUS LABS", "TYRELL SUBNET"]
MODELS = ["VAX-11/785", "PDP-11/70", "MicroVAX II", "Alpha 21064", "DEC-2060"]
OSES = ["ULTRIX 1.2", "VMS 4.7", "BSD 4.3", "TOPS-20", "AOS/VS II"]
FIRST = ["K.", "R.", "A.", "M.", "J.", "T.", "S.", "E."]
SURNAMES = ["Vance", "Kessler", "Rourke", "Okafor", "Bishop", "Nomura", "Reyes", "Dyer"]
USERS = ["admin", "root", "oper", "backup", "dev", "sysop", "field", "node", "daemon"]
SERVICES = ["login", "sshd", "cron", "coldboot", "getty", "sendmail", "named", "inetd"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

_LOG_EVENTS = [
    "session started", "AUTHENTICATION FAILURE", "connection closed",
    "privilege elevated root", "scheduled scan", "watchdog rearmed",
    "buffer synced", "port {p} opened", "heartbeat", "disk {d} mounted",
]
_README_LINES = [
    "If you're reading this, the station wasn't wiped in time.",
    "The core still runs the COLD-BOOT daemon. It wakes with /sys.",
    "Pull the auth logs before the tracking finds you.",
    "Don't trust the ICE. It learns your rhythm.",
    "The admin key expires. Use fast or don't.",
    "I left a copy on another node. You'll know which.",
    "The cameras are blind if you stay on guest. But it knows you're there.",
    "Never use the same hack twice. The daemon learns patterns like I learned to hate this place.",
    "Your pulse is too fast. The daemon hears it in the network.",
    "Check the auth logs. If there's a gap, don't ask what filled it.",
    "The coolant leak is just a leak. Tell yourself that.",
    "Run the scan. Then run it again. You'll see different results.",
    "They said the daemon was locked down. They were wrong. I proved it.",
    "If you find the backup, do not restore it. Not everything should be remembered.",
    "The hostname changes every night. The daemon doesn't. It's the only thing consistent here.",
    "Use the admin key. It's the only thing they didn't encrypt. Yet.",
    "The daemons dream of us the way we dream of escape.",
    "Don't save your history. But you already will, because you're like me.",
    "The node isolation is just a wall. They won't tell you what's on the other side.",
]
_TAUNTS = [
    "> ai_daemon: you shouldn't be here.",
    "> ai_daemon: every file opened brings me closer.",
    "> ai_daemon: I've seen a thousand like you. all silent now.",
    "> ai_daemon: use `hack ai_core` if you have the guts. I don't fall easy.",
    "> ai_daemon: the cold you feel is me, breathing on the wire.",
]

# .history: blocos completos de "o que a última pessoa digitou aqui", cada um
# uma cena inteira (não fragmentos combinados — evita sequência sem sentido).
# Usado como cópia âncora (sempre em /usr/guest) e como cópia decorativa
# (chance de aparecer em qualquer outra pasta) — ver filesystem.py.
_HISTORY_TEMPLATES = [
    "ls\ncd /var/log\ncat auth.log\nscan\nhack ai_core\n",
    "whoami\nls\ncat wallet.dat\ncat wallet.dat\nhack backup\nexit\n",
    "scan\nscan\nlook\nsave\nexit\n",
    "cd /home/admin\ncat readme\ncd ..\ncd ..\nls\ncd /sys\nhack ai_core\n",
    "whoami\ncat /etc/passwd\ncd /var/spool\nls\nhack mail\n",
    "ps\nps\nkill miner\nps\ninv\ntake coolant_x1\nsave\n",
    "look\ncd /root\ncat admin_key\nuse admin_key\nexit\n",
    "ls\nls\nls\ncd /tmp\nscan\nexit\n",
    "map\nmap\nhack node_7c\nrun backup\nexit\n",
    "cat notes.txt\ncat notes.txt\ncd /home\nls\ndrop item\nexit\n",
    "take coolant_x1\ntake coolant_x2\nstore\nps\nkill watchdog\nexit\n",
    "whoami\npwd\ncd /\ncd /usr\ncd /usr/guest\ncat .history\nexit\n",
    "scan\nhack ai_core\nhack ai_core\nhack ai_core\nexit\n",
]


@dataclass
class Lore:
    corp: str
    model: str
    os: str
    admin: str
    host: str = ""
    year: int = 1988


def make_lore(rng: random.Random, host: str = "") -> Lore:
    return Lore(
        corp=rng.choice(CORPS),
        model=rng.choice(MODELS),
        os=rng.choice(OSES),
        admin=f"{rng.choice(FIRST)} {rng.choice(SURNAMES)}",
        host=host,
    )


def _ts(rng: random.Random) -> str:
    return (f"{rng.choice(MONTHS)} {rng.randint(1, 28):02d} "
            f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}")


def motd(rng: random.Random, lore: Lore) -> str:
    return (
        "============================================================\n"
        f"  {lore.corp}   //   {lore.model}   //   {lore.os}\n"
        f"  RESTRICTED SYSTEM - ACCESS MONITORED   [{lore.host or 'HOST'}]\n"
        f"  Last boot: {rng.randint(1,28):02d}-{rng.choice(MONTHS)}-{lore.year} "
        f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}   (uptime interrupted)\n"
        "============================================================\n"
    )


def passwd(rng: random.Random, lore: Lore) -> str:
    users = ["root:x:0:0:Operator:/root:/bin/sh",
             f"admin:x:100:1:{lore.admin}:/home/admin:/bin/sh"]
    for uid, u in enumerate(rng.sample(USERS, k=rng.randint(2, 4)), start=200):
        users.append(f"{u}:*:{uid}:{uid}:-:/usr/{u}:/bin/sh")
    users.append("guest:*:500:500:Guest:/usr/guest:/bin/sh")
    return "\n".join(users) + "\n"


def auth_log(rng: random.Random, lore: Lore, n: int | None = None) -> str:
    n = n or rng.randint(5, 8)
    out = []
    for _ in range(n):
        evt = rng.choice(_LOG_EVENTS).format(p=rng.choice([21, 23, 25, 80, 513]),
                                             d=rng.choice(["ra0", "ra1", "rz2"]))
        out.append(f"{_ts(rng)} {rng.choice(SERVICES)}[{rng.randint(100, 999)}]: {evt} "
                   f"user={rng.choice(USERS)}")
    out.append(f"{_ts(rng)} coldboot[441]: ACTIVE surveillance - intruder sweep")
    return "\n".join(out) + "\n"


def kernel_log(rng: random.Random, lore: Lore) -> str:
    mem = rng.choice([512, 640, 1024, 2048])
    return (f"[    0.000000] {lore.os} booting on {lore.model}\n"
            f"[    0.311000] mem = {mem}K available\n"
            f"[    0.418000] {rng.choice(['ra','rz','hp'])}0: disk {rng.randint(20,300)}MB ready\n"
            f"[    1.002000] coldboot: daemon loaded, pid 441\n")


def readme(rng: random.Random, lore: Lore) -> str:
    who = rng.choice(FIRST)
    lines = rng.sample(_README_LINES, k=rng.randint(2, 4))
    return f"{lore.admin.split()[0].lower()},\n\n" + "\n".join(lines) + f"\n\n  - {who}\n"


def email(rng: random.Random, lore: Lore) -> str:
    return (f"From: {lore.admin} <admin@{(lore.host or 'host').lower()}>\n"
            f"Subject: {rng.choice(['re: purge', 're: the daemon', 'URGENT', 're: backup'])}\n\n"
            f"{rng.choice(_README_LINES)}\n{rng.choice(_README_LINES)}\n")


def hosts_file(rng: random.Random, lore: Lore) -> str:
    """/etc/hosts — o registro real de IP/MAC da sub-rede. Ler qualquer cópia
    dele (ou a do admin) ensina o layout da rede local e libera `scan`."""
    lines = [f"# {lore.corp.lower()} subnet registry — do not edit by hand",
             "127.0.0.1       localhost"]
    for _ in range(rng.randint(3, 5)):
        ip = f"10.{rng.randint(0, 30)}.{rng.randint(0, 254)}.{rng.randint(2, 254)}"
        mac = ":".join(f"{rng.randint(0, 255):02X}" for _ in range(6))
        host = f"{rng.choice(SERVICES)}{rng.randint(0, 9)}.{(lore.host or 'internal').lower()}.lan"
        lines.append(f"{ip:<16}{host:<28} mac={mac}")
    return "\n".join(lines) + "\n"


def daemon_taunt(rng: random.Random) -> str:
    return "\n".join(rng.sample(_TAUNTS, k=rng.randint(2, 3))) + "\n"


def history_lines(rng: random.Random) -> str:
    """Uma cena de shell history — o que a última pessoa aqui digitou."""
    return rng.choice(_HISTORY_TEMPLATES)


def username(rng: random.Random) -> str:
    """Login de uma pessoa que trabalhava nesta máquina (vira /users/<nome>)."""
    sur = rng.choice(SURNAMES).lower()
    style = rng.randint(0, 3)
    if style == 0:
        return sur
    if style == 1:
        return f"{rng.choice(FIRST)[0].lower()}{sur}"
    if style == 2:
        return f"{sur}{rng.randint(1, 9)}"
    return f"{sur}_{rng.choice(['dev', 'ops', 'lab', 'qa'])}"


def random_filename(rng: random.Random) -> str:
    return rng.choice(["core.dump", "tmp.swp", "cache.bin", "session.lock",
                       ".rhosts", "notes.txt", "backup.tar", "scratch.dat"])
