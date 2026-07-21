"""Verificação automatizada (headless) do Breach System (coldboot/breach/).

Cobre CommandParser (sintaxe), VirtualNetwork (conteúdo), commands.execute
(efeitos em GameState) e o fluxo completo de run_tutorial() via input/print
injetados (sem terminal de verdade).
Rode a partir da pasta cold-boot:   python test_breach_system.py
"""

from __future__ import annotations

from coldboot.breach import commands
from coldboot.breach.game_state import GameState, TRACE_ON_ERROR, TRACE_ON_WRONG_CREDENTIALS
from coldboot.breach.network import build_academic_corp_network
from coldboot.breach.parser import CommandParser, CommandSyntaxError
from coldboot.breach.tutorial import TARGET_IP, run_tutorial


def ok(cond, label):
    print(("PASS" if cond else "FALHA") + " . " + label)
    if not cond:
        raise SystemExit(f"Falhou: {label}")


def test_parser():
    p = CommandParser()

    cmd = p.parse(f"nmap {TARGET_IP}")
    ok(cmd.verb == "nmap" and cmd.args == [TARGET_IP], "parser: nmap válido")

    try:
        p.parse("nmap")
        ok(False, "parser: nmap sem args deveria falhar")
    except CommandSyntaxError:
        ok(True, "parser: nmap sem args rejeitado")

    try:
        p.parse("nmap not-an-ip")
        ok(False, "parser: nmap com IP inválido deveria falhar")
    except CommandSyntaxError:
        ok(True, "parser: nmap com IP inválido rejeitado")

    cmd = p.parse("grep hash ftp_public/log.txt")
    ok(cmd.verb == "grep" and len(cmd.args) == 2, "parser: grep válido")
    try:
        p.parse("grep sotermo")
        ok(False, "parser: grep com 1 arg deveria falhar")
    except CommandSyntaxError:
        ok(True, "parser: grep com args insuficientes rejeitado")

    cmd = p.parse("base64 -d Q3liZXIyMDI2IQ==")
    ok(cmd.verb == "base64" and cmd.args[0] == "-d", "parser: base64 -d válido")
    try:
        p.parse("base64 Q3liZXIyMDI2IQ==")
        ok(False, "parser: base64 sem -d deveria falhar")
    except CommandSyntaxError:
        ok(True, "parser: base64 sem -d rejeitado")

    cmd = p.parse(f"ssh admin@{TARGET_IP} -p Cyber2026!")
    ok(cmd.verb == "ssh" and len(cmd.args) == 3, "parser: ssh válido")
    try:
        p.parse(f"ssh admin{TARGET_IP} -p x")
        ok(False, "parser: ssh sem usuario@ip deveria falhar")
    except CommandSyntaxError:
        ok(True, "parser: ssh com token usuario@ip malformado rejeitado")

    try:
        p.parse("voar para lua")
        ok(False, "parser: verbo desconhecido deveria falhar")
    except CommandSyntaxError:
        ok(True, "parser: verbo desconhecido rejeitado")


def test_network():
    net = build_academic_corp_network()
    ok(net.host_exists(TARGET_IP), "network: alvo do tutorial existe")
    ok(not net.host_exists("10.0.0.1"), "network: IP não cadastrado não existe")

    host = net.get_host(TARGET_IP)
    table = dict((port, is_open) for port, _service, is_open in host.port_table())
    ok(table[21] is True, "network: porta 21/FTP aberta")
    ok(table[22] is True, "network: porta 22/SSH aberta")
    ok(table[80] is False, "network: porta 80/HTTP fechada")

    ok(host.check_credentials("admin", "Cyber2026!"), "network: credencial correta bate")
    ok(not host.check_credentials("admin", "senha_errada"), "network: credencial errada não bate")


def test_commands_and_trace():
    net = build_academic_corp_network()
    state = GameState()
    parser = CommandParser()

    r = commands.execute(f"nmap {TARGET_IP}", parser, net, state)
    ok(r.success and "21/tcp" in r.output, "commands: nmap lista a porta 21")
    ok(state.trace_level == 0.0, "commands: nmap bem-sucedido não sobe Trace")

    r = commands.execute("nmap 10.0.0.1", parser, net, state)
    ok(not r.success, "commands: nmap em host inexistente falha")
    ok(state.trace_level == TRACE_ON_ERROR, "commands: erro de host sobe Trace em TRACE_ON_ERROR")

    r = commands.execute("grep hash ftp_public/log.txt", parser, net, state)
    ok(r.success and "Q3liZXIyMDI2IQ==" in r.output, "commands: grep acha o hash no log")

    r = commands.execute("base64 -d Q3liZXIyMDI2IQ==", parser, net, state)
    ok(r.success and r.output == "Cyber2026!", "commands: base64 -d decodifica a senha certa")

    trace_before = state.trace_level
    r = commands.execute(f"ssh admin@{TARGET_IP} -p senha_errada", parser, net, state)
    ok(not r.success, "commands: ssh com senha errada falha")
    ok(state.trace_level == trace_before + TRACE_ON_WRONG_CREDENTIALS,
       "commands: ssh incorreto soma +15% de Trace")
    ok(not state.is_hacked(TARGET_IP), "commands: ssh incorreto não marca host como invadido")

    r = commands.execute(f"ssh admin@{TARGET_IP} -p Cyber2026!", parser, net, state)
    ok(r.success, "commands: ssh com credenciais certas autentica")
    ok(state.is_hacked(TARGET_IP), "commands: ssh correto marca is_hacked")
    ok(state.current_node == TARGET_IP, "commands: ssh correto pivota a sessão para o alvo")


def test_trace_level_caps_at_100():
    state = GameState()
    ok(state.session_active, "game_state: sessão começa ativa")
    state.add_trace(150.0)
    ok(state.trace_level == 100.0, "game_state: Trace trava em 100")
    ok(state.is_traced, "game_state: is_traced fica True em 100")
    ok(not state.session_active, "game_state: sessão encerra ao bater 100% de Trace")

    state2 = GameState()
    state2.add_trace(-50.0)
    ok(state2.trace_level == 0.0, "game_state: Trace não fica negativo")


def test_run_tutorial_happy_path():
    scripted_inputs = iter([
        f"nmap {TARGET_IP}",              # etapa 1
        "cat ftp_public/log.txt",         # etapa 2 (acha o hash)
        "base64 -d Q3liZXIyMDI2IQ==",     # etapa 3 (decodifica a senha)
        f"ssh admin@{TARGET_IP} -p Cyber2026!",  # etapa 4
    ])
    output_lines: list[str] = []

    def fake_input(_prompt):
        return next(scripted_inputs)

    def fake_print(msg=""):
        output_lines.append(str(msg))

    state = run_tutorial(input_fn=fake_input, print_fn=fake_print)

    ok(state.session_active, "tutorial: sessão feliz não cai por Trace")
    ok(state.is_hacked(TARGET_IP), "tutorial: alvo comprometido ao final do fluxo feliz")
    ok(state.tutorial_step > 4, "tutorial: progride pelas 4 etapas")
    ok(any("Missão cumprida" in line for line in output_lines),
       "tutorial: mensagem final de sucesso é impressa")


def test_run_tutorial_blocks_out_of_order_commands():
    scripted_inputs = iter([
        f"ssh admin@{TARGET_IP} -p Cyber2026!",  # fora de ordem: ainda na etapa 1
        f"nmap {TARGET_IP}",                       # comando certo da etapa 1
        "exit",                                     # sai antes de terminar
    ])
    output_lines: list[str] = []

    def fake_input(_prompt):
        return next(scripted_inputs)

    def fake_print(msg=""):
        output_lines.append(str(msg))

    state = run_tutorial(input_fn=fake_input, print_fn=fake_print)

    ok(state.tutorial_step == 2, "tutorial: comando fora de ordem não avança etapa, mas o certo sim")
    ok(not state.is_hacked(TARGET_IP), "tutorial: ssh fora de ordem nunca chega a executar")
    ok(any("Ainda não" in line for line in output_lines),
       "tutorial: guia lembra o jogador do passo certo")


def main():
    test_parser()
    test_network()
    test_commands_and_trace()
    test_trace_level_caps_at_100()
    test_run_tutorial_happy_path()
    test_run_tutorial_blocks_out_of_order_commands()
    print("\nTODOS OS TESTES DO BREACH SYSTEM PASSARAM [OK]")


if __name__ == "__main__":
    main()
