"""Configurações do jogador — acessibilidade e dificuldade.

Persistem entre runs e ficam FORA do save do jogo: são preferências da pessoa,
não estado da partida. Módulo puro (sem UI), então dá para testar o ciclo
carregar/alterar/salvar sem terminal.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

GAME_DIR = Path.home() / ".coldboot"
SETTINGS_PATH = GAME_DIR / "settings.json"


@dataclass(frozen=True)
class Difficulty:
    id: str
    time_mult: float     # multiplica o tempo de cada round dos minigames
    code_delta: int      # soma ao tamanho do código (negativo = mais curto)
    words: bool          # códigos com palavras legíveis em vez de alfanumérico
    # Mesma forma dos modificadores de setor (world.SectorModifier): a
    # dificuldade não mexe só no relógio do minigame, ela também pesa (ou
    # alivia) a economia da run inteira — senão "difícil" só deixava a
    # digitação mais apertada, sem a run ficar mais arriscada de verdade.
    creep_mult: float = 1.0         # multiplica economy.creep_mult (Trace ambiente)
    ice_penalty_mult: float = 1.0   # multiplica a penalidade de Trace do ICE
    botnet_risk_mult: float = 1.0   # multiplica o risco de descoberta da botnet
    payout_mult: float = 1.0        # multiplica o pagamento do CORE do setor
    # label/hint não moram aqui: são texto de UI, resolvido via
    # i18n.t(f"diff_{id}_label") / i18n.t(f"diff_{id}_hint") em screens.py.


DIFFICULTIES: dict[str, Difficulty] = {
    "facil": Difficulty(
        "facil", time_mult=1.8, code_delta=-2, words=True,
        creep_mult=0.75, ice_penalty_mult=0.8, botnet_risk_mult=0.8, payout_mult=0.85,
    ),
    "normal": Difficulty("normal", time_mult=1.0, code_delta=0, words=False),
    "dificil": Difficulty(
        "dificil", time_mult=0.7, code_delta=2, words=False,
        creep_mult=1.25, ice_penalty_mult=1.25, botnet_risk_mult=1.3, payout_mult=1.25,
    ),
}

ORDER = ["facil", "normal", "dificil"]


@dataclass
class Settings:
    high_contrast: bool = False
    difficulty: str = "normal"
    # O tutorial é uma vez na vida, não uma vez por partida — por isso mora
    # aqui, com as preferências, e não no save.
    tutorial_done: bool = False
    # Idioma da UI ("en" | "pt"). O mundo (lore procedural) não muda com isto —
    # ver coldboot/i18n.py. Padrão inglês: é a língua "de fábrica" do jogo.
    locale: str = "en"

    def cycle_locale(self) -> str:
        from . import i18n
        i = i18n.LOCALES.index(self.locale) if self.locale in i18n.LOCALES else 0
        self.locale = i18n.LOCALES[(i + 1) % len(i18n.LOCALES)]
        return self.locale

    def diff(self) -> Difficulty:
        return DIFFICULTIES.get(self.difficulty, DIFFICULTIES["normal"])

    def cycle_difficulty(self) -> Difficulty:
        i = ORDER.index(self.difficulty) if self.difficulty in ORDER else 1
        self.difficulty = ORDER[(i + 1) % len(ORDER)]
        return self.diff()

    def toggle_contrast(self) -> bool:
        self.high_contrast = not self.high_contrast
        return self.high_contrast


def load(path: Path | None = None) -> Settings:
    """Lê as preferências do disco. Arquivo ausente/corrompido = padrões."""
    p = path or SETTINGS_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        from . import i18n
        return Settings(
            high_contrast=bool(data.get("high_contrast", False)),
            difficulty=(data.get("difficulty") if data.get("difficulty") in DIFFICULTIES
                        else "normal"),
            tutorial_done=bool(data.get("tutorial_done", False)),
            locale=(data.get("locale") if data.get("locale") in i18n.LOCALES
                    else i18n.DEFAULT_LOCALE),
        )
    except (OSError, ValueError, TypeError):
        return Settings()


def save(settings: Settings, path: Path | None = None) -> Path:
    p = path or SETTINGS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return p
