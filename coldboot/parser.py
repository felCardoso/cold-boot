"""Command Parser — transforma texto cru numa intenção estruturada.

Aceita dois estilos, como pedido:
  * comandos de shell:      ls, cd <dir>, cat <arq>, hack <alvo>, run <prog>...
  * aventura de texto (PT): "olhar terminal", "usar cartao no leitor",
                            "ler readme", "ir para etc"

Não executa nada — apenas classifica. Quem age é o dispatcher em app.py.
Isso mantém o parser testável isoladamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Command:
    verb: str  # verbo canônico (ex.: "cd", "look", "hack")
    args: list[str] = field(default_factory=list)
    target: str | None = None  # alvo principal (args juntos), conveniência
    raw: str = ""


# Verbos de shell -> canônico
_SHELL = {
    "ls": "ls",
    "dir": "ls",
    "l": "ls",
    "cd": "cd",
    "chdir": "cd",
    "cat": "cat",
    "type": "cat",
    "more": "cat",
    "less": "cat",
    "hack": "hack",
    "crack": "hack",
    "breach": "hack",
    "run": "run",
    "exec": "run",
    "./": "run",
    "scan": "scan",
    "nmap": "scan",
    "map": "map",
    "mapa": "map",
    "help": "help",
    "ajuda": "help",
    "?": "help",
    "man": "help",
    "clear": "clear",
    "cls": "clear",
    "whoami": "whoami",
    "ps": "ps",
    "pwd": "pwd",
    "exit": "exit",
    "quit": "exit",
    "logout": "exit",
    "disconnect": "exit",
    "look": "look",
    "olhar": "look",
    "ver": "look",
    "examinar": "look",
    "use": "use",
    "usar": "use",
    "inventory": "inv",
    "inv": "inv",
    "inventario": "inv",
    "store": "store",
    "loja": "store",
    "shop": "store",
    "buy": "buy",
    "comprar": "buy",
    "kill": "kill",
    "matar": "kill",
    "stop": "kill",
    "parar": "kill",
    "save": "save",
    "salvar": "save",
    "savegame": "save",
    "take": "take",
    "pegar": "take",
    "get": "take",
    "pick": "take",
    "drop": "drop",
    "largar": "drop",
    "soltar": "drop",
    "reboot": "reboot",
    "reiniciar": "reboot",
    "nova": "reboot",
    "desk": "desk",
    "mesa": "desk",
    "desconectar": "desk",
    "pular": "pular",
    "skip": "pular",
    "decrypt": "decrypt",
    "decifrar": "decrypt",
    "submit": "decrypt",
    "plant": "plant",
    "plantar": "plant",
    "unplant": "unplant",
    "desplantar": "unplant",
    "botnet": "botnet",
    "cipher": "cipher",
    "cifrar": "cipher",
    "modifier": "modifier",
    "modificador": "modifier",
    "mod": "modifier",
}

# Verbos de linguagem natural (PT) -> canônico + eventual normalização de args
_NATURAL = {
    "ler": "cat",
    "ir": "cd",  # "ir para <x>"  /  "ir <x>"
    "entrar": "cd",
    "abrir": "cat",
    "olhar": "look",
    "examinar": "look",
    "usar": "use",
    "invadir": "hack",
    "rodar": "run",
    "executar": "run",
    "pegar": "take",
    "largar": "drop",
    "passar": "use",  # "passar cartao no leitor"
}

# Palavras de ligação removidas dos argumentos ("ir PARA etc", "usar x NO y")
_STOPWORDS = {
    "para",
    "pra",
    "o",
    "a",
    "os",
    "as",
    "no",
    "na",
    "em",
    "de",
    "do",
    "da",
    "the",
}

# Verbos oferecidos ao autocompletar (Tab). Um por ação, evitando ruído.
COMPLETION_VERBS = [
    "ls",
    "cd",
    "cat",
    "pwd",
    "scan",
    "map",
    "hack",
    "run",
    "whoami",
    "ps",
    "inv",
    "look",
    "use",
    "take",
    "drop",
    "store",
    "comprar",
    "kill",
    "save",
    "reboot",
    "clear",
    "exit",
    "help",
    "olhar",
    "ler",
    "usar",
    "pegar",
    "ir",
    "plant",
    "unplant",
    "botnet",
    "cipher",
    "cifrar",
    "modifier",
]


def parse(raw: str) -> Command | None:
    text = raw.strip()
    if not text:
        return None
    tokens = text.split()
    head = tokens[0].lower()
    rest = tokens[1:]

    # 1) shell direto
    if head in _SHELL:
        verb = _SHELL[head]
        args = [t for t in rest if t.lower() not in _STOPWORDS]
        return Command(verb=verb, args=args, target=" ".join(args) or None, raw=text)

    # 2) linguagem natural
    if head in _NATURAL:
        verb = _NATURAL[head]
        args = [t for t in rest if t.lower() not in _STOPWORDS]
        return Command(verb=verb, args=args, target=" ".join(args) or None, raw=text)

    # 3) desconhecido — devolve como 'unknown' para o dispatcher responder
    return Command(verb="unknown", args=tokens, target=text, raw=text)
