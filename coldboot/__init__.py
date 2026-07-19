"""Project: COLD-BOOT — RPG de texto/TUI retro-cyberpunk.

Pacote principal. Arquitetura em camadas:

    state.py    -> State Manager  (dados puros do jogo, sem UI)
    world.py    -> conteúdo       (filesystem UNIX falso + grafo da rede)
    parser.py   -> Command Parser (shell + linguagem natural -> intenção)
    combat.py   -> Combate Rítmico de Digitação
    ui.py       -> UI Manager     (widgets Textual: painéis, mapa, teletype)
    app.py      -> Game Loop       (liga tudo; event loop assíncrono do Textual)
"""

__version__ = "0.1.0"
