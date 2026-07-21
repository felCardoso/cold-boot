"""run_tutorial() — o primeiro nível guiado do Breach System.

Nó de partida `127.0.0.1` -> alvo `192.168.1.100` ("Corporação Acadêmica").
O NPC guia (Ghost_0x) fala antes de cada etapa e trava o jogo na etapa atual:
comandos que não avançam a etapa corrente voltam com o lembrete do guia em vez
de serem descartados em silêncio — o jogador sempre sabe o que fazer a
seguir. `help`/`clear`/`exit` funcionam em qualquer etapa.

As quatro etapas (Step) descrevem o que cada uma exige e ensina:
  1. Reconhecimento — `nmap 192.168.1.100` revela a porta 21/FTP aberta.
  2. Investigação   — `cat`/`grep` no log do FTP acham o hash em base64.
  3. Decodificação  — `base64 -d` transforma o hash na senha em texto puro.
  4. Acesso         — `ssh admin@192.168.1.100 -p <senha>` fecha o tutorial.
"""

from __future__ import annotations

from dataclasses import dataclass

from .commands import execute
from .game_state import GameState
from .network import build_academic_corp_network
from .parser import CommandParser

GUIDE = "Ghost_0x"
TARGET_IP = "192.168.1.100"
_META_VERBS = {"help", "clear", "exit"}


@dataclass
class Step:
    allowed_verbs: frozenset[str]   # verbos que este passo aceita executar
    intro: str                      # o que Ghost_0x diz ao entrar no passo
    reminder: str                   # o que Ghost_0x repete se o jogador tentar outra coisa
    done: str                       # o que Ghost_0x diz quando o passo é cumprido


STEPS: dict[int, Step] = {
    1: Step(
        allowed_verbs=frozenset({"nmap"}),
        intro=(
            f"[{GUIDE}] Precisamos acessar o servidor central da Corporação Acadêmica.\n"
            f"[{GUIDE}] Primeiro, rode um 'nmap {TARGET_IP}' para identificar as portas abertas."
        ),
        reminder=f"[{GUIDE}] Ainda não. Rode 'nmap {TARGET_IP}' primeiro.",
        done=f"[{GUIDE}] Boa — porta 21 (FTP) está aberta. É por aí que entramos.",
    ),
    2: Step(
        allowed_verbs=frozenset({"cat", "grep"}),
        intro=(
            f"[{GUIDE}] O FTP costuma vazar coisa nos logs. Leia 'ftp_public/log.txt'\n"
            f"[{GUIDE}] com 'cat ftp_public/log.txt' ou filtre com "
            f"'grep hash ftp_public/log.txt'."
        ),
        reminder=f"[{GUIDE}] Olha o log do FTP: cat ou grep em ftp_public/log.txt.",
        done=f"[{GUIDE}] Achou — um hash em base64. Isso não é a senha ainda, é só como ela viaja.",
    ),
    3: Step(
        allowed_verbs=frozenset({"base64"}),
        intro=(
            f"[{GUIDE}] Esse texto é base64, não criptografia de verdade — dá pra reverter.\n"
            f"[{GUIDE}] Rode 'base64 -d Q3liZXIyMDI2IQ==' (ou aponte pro arquivo) para decodificar."
        ),
        reminder=f"[{GUIDE}] Decodifique o hash: base64 -d <hash_ou_arquivo>.",
        done=f"[{GUIDE}] Senha em texto puro. Agora é só usar.",
    ),
    4: Step(
        allowed_verbs=frozenset({"ssh"}),
        intro=(
            f"[{GUIDE}] Você tem usuário e senha. Entre com "
            f"'ssh admin@{TARGET_IP} -p <senha>'."
        ),
        reminder=f"[{GUIDE}] Use o ssh: ssh admin@{TARGET_IP} -p <senha>.",
        done=f"[{GUIDE}] Dentro. A Corporação Acadêmica é sua. Tutorial completo.",
    ),
}


def run_tutorial(input_fn=input, print_fn=print) -> GameState:
    """Loop interativo do tutorial. `input_fn`/`print_fn` são injetáveis para
    testes automatizados (sem precisar de um terminal de verdade)."""
    net = build_academic_corp_network()
    state = GameState()
    parser = CommandParser()

    print_fn("=== BREACH SYSTEM — TUTORIAL ===")
    print_fn(f"Nó local: 127.0.0.1  |  Alvo: {TARGET_IP} (Corporação Acadêmica)\n")
    print_fn(STEPS[1].intro)

    while state.session_active and state.tutorial_step in STEPS:
        step = STEPS[state.tutorial_step]
        try:
            raw = input_fn(f"guest@{state.current_node}:~$ ")
        except EOFError:
            break
        text = raw.strip()
        if not text:
            continue

        verb = text.split()[0].lower()

        if verb == "exit":
            print_fn(f"[{GUIDE}] Saindo. Volte quando quiser tentar de novo.")
            break
        if verb == "help":
            print_fn(step.intro)
            continue
        if verb == "clear":
            print_fn("\n" * 40)
            continue

        if verb not in step.allowed_verbs:
            print_fn(step.reminder)
            continue

        result = execute(text, parser, net, state)
        print_fn(result.output)

        if not state.session_active:
            break

        if result.success:
            print_fn(step.done)
            state.advance_tutorial()
            next_step = STEPS.get(state.tutorial_step)
            if next_step is not None:
                print_fn("")
                print_fn(next_step.intro)

    if state.is_traced:
        print_fn(f"\n[SISTEMA] Trace Level atingiu 100%. Conexão derrubada. Missão falhou.")
    elif state.tutorial_step not in STEPS:
        print_fn(f"\n[{GUIDE}] Missão cumprida. Bem-vindo ao Breach System.")

    return state


if __name__ == "__main__":
    run_tutorial()
