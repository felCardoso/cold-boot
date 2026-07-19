"""Combate Rítmico de Digitação.

Quando o ICE (o sistema de segurança / IA) te detecta, começa um duelo em
turnos: um CÓDIGO aparece na tela e você tem poucos segundos para digitá-lo
exatamente antes que o SINAL caia. Acertos derrubam a barreira; erros e
estouros de tempo aumentam o Trace.

Esta classe é só a *máquina de estados* — quem conta o tempo e desenha é o
app (via timer assíncrono do Textual), o que mantém a lógica testável.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

from . import i18n

_ALPHABET = string.ascii_uppercase + string.digits
_PREFIXES = ["SYS", "ICE", "0x", "KRN", "NET", "VAX", "DEC"]

# Modo fácil: palavras curtas e legíveis batem muito mais rápido que
# alfanumérico aleatório — a mão memoriza a palavra, não caça o caractere.
_WORDS = [
    "kernel", "daemon", "socket", "packet", "cipher", "vetor", "matriz",
    "proxy", "buffer", "cache", "token", "shell", "modem", "relay", "node",
    "core", "gate", "trace", "frost", "null", "zero", "echo", "drift", "ghost",
]


def _make_code(length: int, words: bool = False,
               rng: random.Random | None = None) -> str:
    r = rng or random
    if words:
        # ~4 caracteres por palavra: o tamanho pedido vira nº de palavras
        n = max(1, round(length / 4))
        body = "-".join(r.choice(_WORDS) for _ in range(n))
    else:
        body = "".join(r.choice(_ALPHABET) for _ in range(length))
    return f"{r.choice(_PREFIXES)}::{body}"


@dataclass
class CombatResult:
    kind: str            # "hit", "miss", "won", "lost"
    message: str
    trace_delta: float = 0.0


class CombatSession:
    def __init__(self, name: str, hack_id: str, rounds: int = 3,
                 base_time: float = 5.0, trace_penalty: float = 9.0,
                 code_len: int = 4, ice_type: str = "Firewall",
                 time_bonus: float = 0.0, words: bool = False,
                 behavior: str = "plain", reveal: float = 1.6,
                 mutate_at: float = 0.5, rng: random.Random | None = None):
        # RNG próprio da sessão: com ele, mesma seed = mesmos códigos, na
        # ordem — o que torna um duelo reproduzível em teste. Sem ele (None),
        # cai no `random` global: variedade de runtime, como sempre foi.
        self.rng = rng
        self.name = name              # rótulo do ICE, para narrativa
        self.hack_id = hack_id
        self.total_rounds = rounds
        self.round = 0                # rounds vencidos
        self.base_time = base_time
        self.trace_penalty = trace_penalty
        self.code_len = code_len      # tamanho-base do código (varia por tipo)
        self.ice_type = ice_type
        self.time_bonus = time_bonus  # segundos extras vindos da CPU do rig
        self.words = words            # dificuldade fácil: códigos com palavras
        # Como este ICE se comporta, além dos números:
        #   plain   -> o código fica na tela o round todo
        #   memory  -> some depois de `reveal` s: digite de cabeça (Guardião)
        #   hunt    -> escapa e vira outro código na metade do round (Caçador)
        #   phantom -> some cedo E troca de código ENQUANTO escondido (Fantasma):
        #              o que você memorizou pode já não valer mais nada
        self.behavior = behavior
        self.reveal = reveal
        self.mutate_at = mutate_at    # fração do tempo em que o código escapa
        self.mutated = False          # o Caçador só escapa uma vez por round
        self.code = ""
        self.round_time = 0.0         # tempo cheio deste round (base do relógio)
        self.time_left = 0.0
        self.finished = False
        self.won = False

    # ---- ciclo de vida ------------------------------------------------ #
    def start(self) -> str:
        self.round = 0
        self._next_challenge()
        return self.code

    def _next_challenge(self) -> None:
        # códigos ficam maiores e o tempo menor a cada round vencido
        length = max(2, self.code_len + self.round * 2)
        self.code = _make_code(length, self.words, self.rng)
        self.round_time = max(2.0, self.base_time - self.round * 0.8) + self.time_bonus
        self.time_left = self.round_time
        self.mutated = False

    # ---- o que o jogador vê -------------------------------------------- #
    @property
    def elapsed(self) -> float:
        return self.round_time - self.time_left

    @property
    def code_visible(self) -> bool:
        """Guardião e Fantasma mostram o código e o escondem: o resto do
        round é memória (o Fantasma, além disso, pode trocar o que memorizou)."""
        if self.behavior not in ("memory", "phantom"):
            return True
        return self.elapsed < self.reveal

    def display_code(self) -> str:
        """O código como ele aparece no prompt (mascarado se já sumiu)."""
        if self.code_visible:
            return self.code
        return "".join("·" if c not in ":-" else c for c in self.code)

    def tick(self, dt: float) -> CombatResult | None:
        """Avança o relógio. Retorna um resultado se o tempo estourar."""
        if self.finished:
            return None
        self.time_left -= dt
        # O Caçador (e o Fantasma) não deixam o código quieto: na metade do
        # round ele escapa e vira outro. Uma vez só — a ideia é assustar, não
        # ser impossível. No Fantasma isso acontece ESCONDIDO (reveal curto),
        # então quem memorizou o código antigo só descobre a troca ao errar.
        if (self.behavior in ("hunt", "phantom") and not self.mutated
                and self.time_left <= self.round_time * self.mutate_at):
            self.mutated = True
            self.code = _make_code(max(2, self.code_len + self.round * 2),
                                   self.words, self.rng)
        if self.time_left <= 0:
            return self._fail(i18n.t("combat_timeout"))
        return None

    def submit(self, text: str) -> CombatResult:
        """Avalia a string digitada pelo jogador."""
        if self.finished:
            return CombatResult("won" if self.won else "lost", "")
        if text.strip() == self.code:
            self.round += 1
            if self.round >= self.total_rounds:
                self.finished = True
                self.won = True
                return CombatResult("won", i18n.t("combat_barrier_broken", name=self.name))
            self._next_challenge()
            return CombatResult("hit", i18n.t("combat_hit"))
        return self._fail(i18n.t("combat_invalid_string"))

    def _fail(self, msg: str) -> CombatResult:
        # errar não encerra o duelo, mas custa Trace e gera novo código
        self._next_challenge()
        return CombatResult("miss", msg, trace_delta=self.trace_penalty)


# --------------------------------------------------------------------------- #
# Fase 4 — tipos de ICE e escalonamento por profundidade
# --------------------------------------------------------------------------- #
# Cada tipo tem um perfil de números E um verbo próprio: o que muda entre eles
# não é só quanto tempo você tem, mas o que exatamente você precisa fazer.
_ICE_TYPES = [
    # nome         rounds  tempo  penal  code_len  behavior
    ("Sentinel",   2,      5.5,   6.0,   3,        "plain"),   # poucos códigos, curtos
    ("Firewall",   3,      5.0,   9.0,   5,        "plain"),   # códigos longos
    ("Hunter",     3,      4.6,   11.0,  4,        "hunt"),    # o código escapa no meio
    ("Guardian",   4,      5.0,   12.0,  4,        "memory"),  # o código some: de cabeça
    ("Phantom",    3,      4.6,   13.5,  4,        "phantom"), # some cedo E troca escondido
]

# O Fantasma só aparece bem fundo — é o pior dos dois mundos (Guardião +
# Caçador), reservado para quem já está avançado o suficiente para merecer.
_PHANTOM_MIN_DEPTH = 8


# --------------------------------------------------------------------------- #
# Bosses — o CORE de cada setor
# --------------------------------------------------------------------------- #
# O daemon COLD-BOOT muda de máscara a cada setor. O nome é cosmético; o que
# escala de verdade é o setor, que entra como profundidade efetiva.
BOSS_TITLES = [
    "COLD CORE", "MOTHER SENTINEL", "THE ARCHIVIST", "IVORY TOWER",
    "IRON CURTAIN", "THE COLLECTOR", "LAST WINTER", "LIDLESS EYE",
]

# Tetos de duração: um duelo mais longo que isto vira tédio, não desafio.
MAX_ROUNDS = 8
BOSS_MAX_ROUNDS = 10


def boss_name(sector: int) -> str:
    """Persona do boss deste setor (cicla, com o número para não repetir)."""
    title = BOSS_TITLES[(sector - 1) % len(BOSS_TITLES)]
    ciclo = (sector - 1) // len(BOSS_TITLES)
    return f"{title}-{ciclo + 1}" if ciclo else title


def effective_depth(depth: int, sector: int) -> int:
    """A dificuldade que o ICE enxerga.

    A rede satura em 15 hosts (profundidade ~6), então `depth` sozinho para de
    crescer. O setor é o que continua subindo para sempre.
    """
    return depth + (sector - 1) * 2


def make_boss(sector: int, rng=None, time_bonus: float = 0.0,
              diff=None, pen_mult: float = 1.0) -> CombatSession:
    """O ICE do CORE: mais rounds que qualquer nó, e ele NÃO joga limpo.

    Alterna entre esconder o código (memória) e deixá-lo escapar (caça) —
    conforme o setor —, para o clímax do setor nunca ser só "um Firewall
    grande".
    """
    behavior = "memory" if sector % 2 else "hunt"
    # O boss é medido na MESMA régua dos nós comuns, só que um degrau mais
    # fundo que qualquer um deles — senão, em setor alto, um Guardião de canto
    # acabava punindo mais que o clímax do setor.
    eff = effective_depth(5, sector)
    rounds = min(BOSS_MAX_ROUNDS, 5 + eff // 3)
    base_time = max(2.4, 5.0 - eff * 0.18)
    pen = (14.0 + eff * 1.2) * pen_mult
    code_len = 5 + eff // 4
    reveal = 2.0

    if diff is not None:
        base_time *= diff.time_mult
        code_len = max(2, code_len + diff.code_delta)
        reveal *= diff.time_mult
        pen *= diff.ice_penalty_mult

    return CombatSession(
        name=f"{boss_name(sector)} — core of sector {sector}",
        hack_id="ai_core",
        rounds=rounds,
        base_time=base_time,
        trace_penalty=pen,
        code_len=code_len,
        ice_type="BOSS",
        time_bonus=time_bonus,
        words=bool(diff and diff.words),
        behavior=behavior,
        reveal=reveal,
        rng=rng,
    )


def make_ice(label: str, depth: int, rng=None, time_bonus: float = 0.0,
             diff=None, pen_mult: float = 1.0) -> CombatSession:
    """Cria uma sessão de ICE escalada pela profundidade do alvo.

    Quanto mais fundo na rede, mais rounds, menos tempo e mais penalidade —
    ICEs mais duros também ficam mais prováveis. `time_bonus` são os segundos
    extras que a CPU do rig concede em cada round; `diff` é a Difficulty
    escolhida no menu de pausa (None = Normal); `pen_mult` é o modificador de
    setor (state.mod_ice_penalty — ver world.py).
    """
    r = rng or random
    # Nota: `rng` (quando passado) também vira o RNG da sessão — o sorteio do
    # tipo E os códigos do duelo saem todos da mesma fonte, reproduzíveis.
    # tipos disponíveis crescem com a profundidade (Sentinela sempre; Guardiao
    # só fundo). O Fantasma é um degrau à parte, ainda mais fundo — não altera
    # quando os outros quatro tipos aparecem.
    n_tipos = 2 + min(2, depth // 2)
    if depth >= _PHANTOM_MIN_DEPTH:
        n_tipos += 1
    disponiveis = _ICE_TYPES[:n_tipos]
    name, rounds, base_time, pen, code_len, behavior = r.choice(disponiveis)

    # Rounds têm teto: num jogo infinito, `rounds + depth//3` cresceria sem
    # limite e o setor 20 viraria um duelo de 15 códigos — longo, não difícil.
    # Passado o teto, quem continua apertando é o tempo, a penalidade e o
    # tamanho do código.
    rounds = min(MAX_ROUNDS, rounds + depth // 3)
    base_time = max(2.4, base_time - depth * 0.22)
    pen = (pen + depth * 0.8) * pen_mult
    code_len = code_len + depth // 4
    # O Fantasma esconde bem mais cedo que o Guardião: memorizar o de cabeça
    # não basta, porque o código pode trocar ENQUANTO está escondido.
    reveal = 1.4 if behavior == "phantom" else 1.8

    if diff is not None:
        base_time *= diff.time_mult
        code_len = max(2, code_len + diff.code_delta)
        reveal *= diff.time_mult      # no fácil, mostra por mais tempo
        pen *= diff.ice_penalty_mult

    return CombatSession(
        name=f"{name} of {label}",
        hack_id=label,
        rounds=rounds,
        base_time=base_time,
        trace_penalty=pen,
        code_len=code_len,
        ice_type=name,
        time_bonus=time_bonus,
        words=bool(diff and diff.words),
        behavior=behavior,
        reveal=reveal,
        rng=rng,
    )
