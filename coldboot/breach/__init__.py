"""Breach System — mecânicas de hacking simuladas (nmap/grep/base64/ssh) e o
tutorial interativo do primeiro nível.

Camadas (a mesma separação do jogo principal, num pacote próprio):

    network.py      -> VirtualNetwork   (nós, portas, credenciais, arquivos)
    parser.py        -> CommandParser    (texto cru -> ParsedCommand, valida sintaxe)
    commands.py       -> execução dos comandos (aplica efeitos em GameState)
    game_state.py     -> GameState       (Trace Level, progresso, nó atual)
    tutorial.py        -> run_tutorial()  (fluxo guiado por Ghost_0x)

Independente do jogo Textual em `coldboot/app.py` — pode ser jogado num
terminal puro com `python -m coldboot.breach.tutorial`.
"""

from .commands import execute
from .game_state import GameState
from .network import VirtualHost, VirtualNetwork, build_academic_corp_network
from .parser import CommandParser, CommandSyntaxError, ParsedCommand
from .tutorial import run_tutorial

__all__ = [
    "execute",
    "GameState",
    "VirtualHost",
    "VirtualNetwork",
    "build_academic_corp_network",
    "CommandParser",
    "CommandSyntaxError",
    "ParsedCommand",
    "run_tutorial",
]
