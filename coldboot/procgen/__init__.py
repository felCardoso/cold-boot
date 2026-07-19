"""Geração procedural. Cada submódulo espelha uma camada do jogo e consome
um único RNG semeado, então a run inteira é reproduzível a partir da seed.

    rng.py       -> seed determinística
    network.py   -> grafo da rede (mapa ASCII)  [Fase 1]
    (filesystem, grammar, mission virão nas próximas fases)
"""
