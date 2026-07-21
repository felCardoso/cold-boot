"""Execução dos comandos de hacking — a ponte entre ParsedCommand, VirtualNetwork
e GameState.

Cada `cmd_*` recebe um `ParsedCommand` já validado sinticamente pelo
`CommandParser`, confere o CONTEÚDO contra a `VirtualNetwork` (host existe?
porta aberta? credencial bate?) e devolve um `CommandResult`. É aqui — e só
aqui — que o Trace Level sobe: `GameState` expõe as regras (`register_error`,
`register_wrong_credentials`), mas quem decide QUANDO chamá-las é este
módulo, porque só ele sabe se o comando "deu errado" no sentido do jogo.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

from .game_state import GameState
from .network import VirtualHost, VirtualNetwork
from .parser import CommandParser, CommandSyntaxError, ParsedCommand, split_user_at_ip


@dataclass
class CommandResult:
    output: str
    success: bool   # a "intenção" do comando deu certo (achou a porta, decodificou, logou...)


def execute(raw: str, parser: CommandParser, net: VirtualNetwork, state: GameState) -> CommandResult:
    """Ponto de entrada único: parseia, despacha, aplica Trace em caso de erro."""
    try:
        cmd = parser.parse(raw)
    except CommandSyntaxError as exc:
        state.register_error()
        return CommandResult(output=str(exc), success=False)

    handler = _HANDLERS.get(cmd.verb)
    if handler is None:
        state.register_error()
        return CommandResult(output=f"comando não implementado: {cmd.verb}", success=False)
    return handler(cmd, net, state)


# --------------------------------------------------------------------------- #
# nmap <ip>
# --------------------------------------------------------------------------- #
def cmd_nmap(cmd: ParsedCommand, net: VirtualNetwork, state: GameState) -> CommandResult:
    ip = cmd.args[0]
    host = net.get_host(ip)
    if host is None:
        state.register_error()
        return CommandResult(
            output=f"nmap: não foi possível conectar a {ip} (host inalcançável).",
            success=False,
        )

    lines = [f"Starting Nmap scan on {ip} ({host.hostname})", "PORT      SERVICE   STATE"]
    for port, service, is_open in host.port_table():
        status = "open" if is_open else "closed"
        lines.append(f"{port}/tcp".ljust(10) + f"{service}".ljust(10) + status)
    return CommandResult(output="\n".join(lines), success=True)


# --------------------------------------------------------------------------- #
# cat <arquivo> — apoio para inspecionar logs sem filtrar
# --------------------------------------------------------------------------- #
def cmd_cat(cmd: ParsedCommand, net: VirtualNetwork, state: GameState) -> CommandResult:
    path = cmd.args[0]
    host = net.get_host(state.current_node) if state.current_node != "127.0.0.1" else None
    # Antes de logar no alvo, "cat" só enxerga arquivos do próprio alvo já
    # escaneado — no tutorial isso é sempre 192.168.1.100.
    host = host or _only_known_target(net)
    content = host.read_file(path) if host else None
    if content is None:
        state.register_error()
        return CommandResult(output=f"cat: {path}: arquivo não encontrado.", success=False)
    return CommandResult(output=content.rstrip("\n"), success=True)


# --------------------------------------------------------------------------- #
# grep <termo> <arquivo>
# --------------------------------------------------------------------------- #
def cmd_grep(cmd: ParsedCommand, net: VirtualNetwork, state: GameState) -> CommandResult:
    term, path = cmd.args
    host = net.get_host(state.current_node) if state.current_node != "127.0.0.1" else None
    host = host or _only_known_target(net)
    content = host.read_file(path) if host else None
    if content is None:
        state.register_error()
        return CommandResult(output=f"grep: {path}: arquivo não encontrado.", success=False)

    matches = [line for line in content.splitlines() if term.lower() in line.lower()]
    if not matches:
        return CommandResult(output=f"grep: nenhuma ocorrência de '{term}' em {path}.", success=False)
    return CommandResult(output="\n".join(matches), success=True)


# --------------------------------------------------------------------------- #
# base64 -d <arquivo_ou_string>
# --------------------------------------------------------------------------- #
def cmd_base64(cmd: ParsedCommand, net: VirtualNetwork, state: GameState) -> CommandResult:
    target = cmd.args[1]
    # Aceita tanto uma string base64 direta quanto o caminho de um arquivo que
    # contenha só o hash (conveniência: o jogador pode copiar do grep OU
    # apontar pro arquivo).
    host = _only_known_target(net)
    raw_value = target
    if host is not None:
        file_content = host.read_file(target)
        if file_content is not None:
            raw_value = file_content.strip()

    try:
        decoded = base64.b64decode(raw_value, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        state.register_error()
        return CommandResult(output=f"base64: '{raw_value}' não é base64 válido.", success=False)
    return CommandResult(output=decoded, success=True)


# --------------------------------------------------------------------------- #
# ssh <usuario>@<ip> -p <senha>
# --------------------------------------------------------------------------- #
def cmd_ssh(cmd: ParsedCommand, net: VirtualNetwork, state: GameState) -> CommandResult:
    user_at_ip, _flag, password = cmd.args
    username, ip = split_user_at_ip(user_at_ip)

    host = net.get_host(ip)
    if host is None:
        state.register_error()
        return CommandResult(output=f"ssh: {ip}: host inalcançável.", success=False)

    if not host.check_credentials(username, password):
        state.register_wrong_credentials()
        return CommandResult(
            output=f"ssh: Permission denied for {username}@{ip} (senha incorreta). "
                   f"Trace Level +{15:.0f}%.",
            success=False,
        )

    state.mark_hacked(ip)
    return CommandResult(
        output=f"Última autenticação em {ip} via senha.\n"
               f"guest@127.0.0.1 -> {username}@{ip}: acesso concedido.",
        success=True,
    )


def _only_known_target(net: VirtualNetwork) -> VirtualHost | None:
    """Tutorial só tem um alvo cadastrado; cat/grep/base64 operam nele por
    padrão quando o jogador ainda não "está dentro" de nenhum host (não fez
    `ssh`). Fora do tutorial, uma sessão real resolveria isso pelo nó atual —
    aqui simplificamos porque a rede do tutorial tem exatamente um host."""
    for ip in ("192.168.1.100",):
        host = net.get_host(ip)
        if host is not None:
            return host
    return None


_HANDLERS = {
    "nmap": cmd_nmap,
    "cat": cmd_cat,
    "grep": cmd_grep,
    "base64": cmd_base64,
    "ssh": cmd_ssh,
}
