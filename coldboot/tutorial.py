"""Tutorial — o setor 0 roteirizado e as dicas contextuais.

Duas coisas diferentes, e de propósito:

  * **Setor 0**: uma rede FIXA (não procedural) e minúscula, jogada uma vez, que
    conduz pelos verbos básicos. Cada passo espera um comando específico e só
    então libera o próximo. É pulável — quem já conhece não deveria ser refém.
  * **Dicas contextuais**: disparam na primeira vez que uma mecânica aparece de
    verdade (o primeiro cadeado, o primeiro superaquecimento). O jogo tem ~25
    comandos; ensinar tudo de uma vez no começo não gruda, e as mecânicas
    tardias nunca chegariam a ser explicadas.

Módulo puro: descreve os passos e escolhe as dicas. Quem narra é o app.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import i18n
from .state import FSNode, GameState, NetNode


# --------------------------------------------------------------------------- #
# Setor 0 — o roteiro
# --------------------------------------------------------------------------- #
@dataclass
class Step:
    verb: str            # verbo canônico que destrava o passo ("" = qualquer)
    prompt: str          # o que pedimos
    done: str            # o que dizemos quando a pessoa acerta


def _build_steps() -> list[Step]:
    """Constrói a lista de passos do tutorial, com textos resolvidos no locale atual."""
    return [
        Step("ls",
             i18n.t("tut_step_1_prompt"),
             i18n.t("tut_step_1_done")),
        Step("cat",
             i18n.t("tut_step_2_prompt"),
             i18n.t("tut_step_2_done")),
        Step("cd",
             i18n.t("tut_step_3_prompt"),
             i18n.t("tut_step_3_done")),
        Step("take",
             i18n.t("tut_step_4_prompt"),
             i18n.t("tut_step_4_done")),
        Step("use",
             i18n.t("tut_step_5_prompt"),
             i18n.t("tut_step_5_done")),
        Step("scan",
             i18n.t("tut_step_6_prompt"),
             i18n.t("tut_step_6_done")),
        Step("hack",
             i18n.t("tut_step_7_prompt"),
             i18n.t("tut_step_7_done")),
    ]


def build_sector_zero() -> GameState:
    """A rede de treino: dois nós, um filesystem à mão, nada procedural."""
    st = GameState()
    st.seed = 0
    st.sector = 0
    # Nenhum nó é o CORE: tomar o ALVO não pode disparar o "setor limpo" (com
    # pagamento e avanço de setor) no meio do treino.
    st.core_id = "__nenhum__"
    st.trace = 4.0
    # O treino ensina o verbo `scan`, não a caça por /home/admin ou /etc/hosts
    # que libera ele numa run de verdade — aqui já vem destravado.
    st.flags["scan_unlocked"] = True

    root = FSNode("/", True)
    root.add(FSNode("leiame.txt", False, content=(
        "TRAINING MACHINE — isolated network.\n"
        "Nothing here can hurt you. Make mistakes freely.\n"
        "Game objective: reach the CORE of each sector before Trace closes in.\n")))
    cofre = FSNode("cofre_treino", True)
    cofre.add(FSNode("moeda_treino.dat", False,
                     content="training voucher: 5,000 CRN to bearer.\n",
                     item={"kind": "credits", "amount": 5.0}))
    root.add(cofre)

    gate = NetNode(id="GATE", label="GATE", col=0, row=0, links=["ALVO"],
                   state="compromised", depth=0)
    gate.fs = root

    alvo_fs = FSNode("/", True)
    alvo_fs.add(FSNode("premio.txt", False, content=(
        "You took the host. This is exactly what you'll do the whole run, except against real ICE.\n")))
    alvo = NetNode(id="ALVO", label="ALVO", col=1, row=0, links=["GATE"],
                   state="fog", hack_id="alvo", depth=1)
    alvo.fs = alvo_fs

    st.net = {"GATE": gate, "ALVO": alvo}
    st.location = "GATE"
    st.cwd = []
    return st


# --------------------------------------------------------------------------- #
# Dicas contextuais — uma vez cada, na hora em que a mecânica acontece
# --------------------------------------------------------------------------- #
# Chaves conhecidas de dica. O texto de cada uma vive no catálogo i18n
# (`tut_hint_<chave>`), resolvido em `hint_for()` — este set só registra quais
# chaves existem, para `hint_for` recusar uma chave desconhecida.
HINTS: frozenset[str] = frozenset({
    "locked", "hot", "trace_high", "mining", "ram_tight",
    "reader", "vault_open", "boss", "first_buy",
    "scan_locked", "cipher_intro", "spoof_script",
})


def hint_for(state: GameState, key: str) -> str | None:
    """A dica, se ela ainda não foi dada. Marca como vista no próprio estado."""
    flag = f"hint_{key}"
    if state.flags.get(flag) or key not in HINTS:
        return None
    state.flags[flag] = True
    return i18n.t(f"tut_hint_{key}")


def __getattr__(name: str) -> list[Step]:
    """Lazy resolution de STEPS para respeitar mudanças de locale."""
    if name == "STEPS":
        return _build_steps()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
