"""CommandParser — valida a sintaxe de um comando de hacking antes de executar.

Separado da execução de propósito (mesma ideia do parser do jogo principal em
`coldboot/parser.py`): este módulo só decide "isso é um `ssh` bem formado?" e
devolve uma estrutura tipada ou um erro de sintaxe. Quem decide se as
CREDENCIAIS estão certas, se o HOST existe etc. é `commands.py` — validação de
forma (aqui) é diferente de validação de conteúdo (lá).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_USER_AT_IP_RE = re.compile(r"^([\w.\-]+)@(\d{1,3}(?:\.\d{1,3}){3})$")


class CommandSyntaxError(Exception):
    """Sintaxe inválida. A mensagem já vem pronta para mostrar ao jogador,
    incluindo a forma de uso esperada (`usage`)."""

    def __init__(self, message: str, usage: str) -> None:
        super().__init__(message)
        self.message = message
        self.usage = usage

    def __str__(self) -> str:
        return f"{self.message}\n  uso: {self.usage}"


@dataclass
class ParsedCommand:
    verb: str
    args: list[str] = field(default_factory=list)
    raw: str = ""


class CommandParser:
    """Reconhece `nmap`, `grep`, `base64 -d`, `ssh` e alguns comandos de apoio
    (`cat`, `help`, `clear`, `exit`) e valida a gramática de cada um.
    """

    def parse(self, raw: str) -> ParsedCommand:
        text = raw.strip()
        if not text:
            raise CommandSyntaxError("comando vazio.", "<comando> [args]")

        tokens = text.split()
        verb = tokens[0].lower()
        args = tokens[1:]

        handler = getattr(self, f"_validate_{verb}", None)
        if handler is None:
            raise CommandSyntaxError(
                f"comando desconhecido: '{verb}'.",
                "nmap | grep | base64 -d | ssh | cat | help | clear | exit",
            )
        handler(args)
        return ParsedCommand(verb=verb, args=args, raw=text)

    # ------------------------------------------------------------------ #
    # nmap <ip>
    # ------------------------------------------------------------------ #
    def _validate_nmap(self, args: list[str]) -> None:
        usage = "nmap <ip>"
        if len(args) != 1:
            raise CommandSyntaxError("nmap espera exatamente um IP.", usage)
        if not _IP_RE.match(args[0]):
            raise CommandSyntaxError(f"'{args[0]}' não parece um IP válido.", usage)

    # ------------------------------------------------------------------ #
    # grep <termo> <arquivo>
    # ------------------------------------------------------------------ #
    def _validate_grep(self, args: list[str]) -> None:
        usage = "grep <termo> <arquivo>"
        if len(args) != 2:
            raise CommandSyntaxError("grep espera um termo e um arquivo.", usage)

    # ------------------------------------------------------------------ #
    # base64 -d <arquivo_ou_string>
    # ------------------------------------------------------------------ #
    def _validate_base64(self, args: list[str]) -> None:
        usage = "base64 -d <arquivo_ou_string>"
        if len(args) != 2 or args[0] != "-d":
            raise CommandSyntaxError("base64 só suporta decodificação: '-d <alvo>'.", usage)

    # ------------------------------------------------------------------ #
    # ssh <usuario>@<ip> -p <senha>
    # ------------------------------------------------------------------ #
    def _validate_ssh(self, args: list[str]) -> None:
        usage = "ssh <usuario>@<ip> -p <senha>"
        if len(args) != 3 or args[1] != "-p":
            raise CommandSyntaxError("sintaxe de ssh incompleta.", usage)
        if not _USER_AT_IP_RE.match(args[0]):
            raise CommandSyntaxError(f"'{args[0]}' não é 'usuario@ip' válido.", usage)

    # ------------------------------------------------------------------ #
    # Comandos de apoio, sem exigência de argumentos rígida
    # ------------------------------------------------------------------ #
    def _validate_cat(self, args: list[str]) -> None:
        if len(args) != 1:
            raise CommandSyntaxError("cat espera um arquivo.", "cat <arquivo>")

    def _validate_help(self, args: list[str]) -> None:
        return

    def _validate_clear(self, args: list[str]) -> None:
        return

    def _validate_exit(self, args: list[str]) -> None:
        return


def split_user_at_ip(token: str) -> tuple[str, str]:
    """'admin@192.168.1.100' -> ('admin', '192.168.1.100'). Assume já validado."""
    match = _USER_AT_IP_RE.match(token)
    assert match is not None
    return match.group(1), match.group(2)
