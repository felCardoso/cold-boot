"""Paleta — traduz os estilos Rich do jogo para o modo de alto contraste.

O jogo inteiro escreve em estilos semânticos literais ("green3", "grey58"...).
Em vez de reescrever cada chamada, tudo passa por `resolve()` num punhado de
pontos de estrangulamento (a narrativa, o syslog e os renderizadores de painel).

O modo normal é verde-fósforo com cinzas — bonito, mas os cinzas sobre fundo
quase preto ficam abaixo do contraste mínimo legível. No alto contraste os
cinzas viram branco, as cores viram suas variantes brilhantes e tudo ganha
`bold`, que no terminal engrossa o glifo além de clarear a cor.
"""

from __future__ import annotations

# Estilo do jogo -> equivalente de alto contraste.
_MAP = {
    "grey30": "white",
    "grey42": "white",
    "grey58": "white",
    "grey15": "black",          # usado como fundo (on grey15)
    "green3": "bright_green",
    "yellow": "bright_yellow",
    "cyan": "bright_cyan",
    "red": "bright_red",
    "white": "bright_white",
}

CSS_CLASS = "high-contrast"


def resolve(style: str, high_contrast: bool) -> str:
    """Reescreve um estilo Rich para o modo de alto contraste.

    Funciona token a token, então estilos compostos ("bold red reverse",
    "bold black on green3") continuam válidos.
    """
    if not high_contrast or not style:
        return style
    tokens = [_MAP.get(tok, tok) for tok in style.split()]
    if "bold" not in tokens:
        tokens.insert(0, "bold")
    return " ".join(tokens)
