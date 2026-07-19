"""Game Loop — o app Textual que orquestra tudo.

O "loop" aqui é o event loop assíncrono do Textual. Nós apenas plugamos:
  * compose()           -> monta os 3 painéis (UI Manager)
  * timers (set_interval)-> logs em tempo real + avanço do Trace
  * on_input_submitted  -> Command Parser -> dispatcher
  * workers             -> teletype (no NarrativeView) e timer de combate

Nada disso bloqueia: enquanto o teletype digita e os logs pulsam, o input
segue aceitando comandos.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.suggester import Suggester
from textual.widgets import Input, RichLog, Static

from . import parser
from . import (
    economy,
    hardware,
    i18n,
    puzzle,
    savegame,
    settings as settings_mod,
    theme,
    tutorial,
)
from .cipher import CipherResult, CipherSession, make_session as make_cipher
from .combat import CombatResult, CombatSession, effective_depth, make_boss, make_ice
from .hardware import CATALOG
from .lockdown import LockdownSession
from .procgen.filesystem import default_cwd
from .screens import BootScreen, DeskScreen, PauseScreen, ShopScreen
from .state import FSNode
from .ui import NarrativeView, random_syslog, render_map, render_rig, render_status
from .world import (
    PUZZLE_TRACE_RELIEF,
    VILLAIN_LINES,
    new_game,
    next_run,
    puzzle_reward,
    sector_payout,
)

# O minigame de cifra (ver cipher.py) é limitado por setor: joga-se no máximo
# MAX_CIPHER_PER_SECTOR vezes por incursão, não importa quantos hosts visite.
MAX_CIPHER_PER_SECTOR = 3
CIPHER_TRACE_RELIEF = 18.0


def _boot_sequence() -> list[tuple[str, str, float]]:
    """Boot sequence messages, translated at runtime."""
    return [
        (i18n.t("app_boot_1"), "green3", 0.008),
        (i18n.t("app_boot_2"), "green3", 0.008),
        (i18n.t("app_boot_3"), "green3", 0.008),
        ("", "green3", 0.0),
        (i18n.t("app_boot_5"), "green3", 0.014),
        (i18n.t("app_boot_6"), "green3", 0.014),
        (i18n.t("app_boot_7"), "yellow", 0.02),
        (i18n.t("app_boot_8"), "green3", 0.012),
    ]


# Ajuda: uma linha por comando, alinhada numa coluna só. Fonte única da
# verdade do `help` — some com a lista solta que vivia dentro do do_help.
def _help_sections() -> list[tuple[str, list[tuple[str, str]]]]:
    """Help sections, translated at runtime."""
    return [
        (
            i18n.t("app_help_sec_nav"),
            [
                ("ls", i18n.t("app_help_ls")),
                ("cd <dir>", i18n.t("app_help_cd")),
                ("cat <arq>", i18n.t("app_help_cat")),
                ("pwd", i18n.t("app_help_pwd")),
                ("look [alvo]", i18n.t("app_help_look")),
            ],
        ),
        (
            i18n.t("app_help_sec_net"),
            [
                ("scan", i18n.t("app_help_scan")),
                ("map", i18n.t("app_help_map")),
                ("hack <alvo>", i18n.t("app_help_hack")),
                ("cipher", i18n.t("app_help_cipher")),
                ("modifier", i18n.t("app_help_modifier")),
            ],
        ),
        (
            i18n.t("app_help_sec_sys"),
            [
                ("run <prog>", i18n.t("app_help_run")),
                ("ps", i18n.t("app_help_ps")),
                ("kill <proc>", i18n.t("app_help_kill")),
                ("whoami", i18n.t("app_help_whoami")),
            ],
        ),
        (
            i18n.t("app_help_sec_items"),
            [
                ("inv", i18n.t("app_help_inv")),
                ("take <item>", i18n.t("app_help_take")),
                ("drop <item>", i18n.t("app_help_drop")),
                ("use <item>", i18n.t("app_help_use")),
                ("use <x> on <y>", i18n.t("app_help_use_on")),
                ("store", i18n.t("app_help_store")),
                ("comprar <id>", i18n.t("app_help_buy")),
                ("plant <host>", i18n.t("app_help_plant")),
                ("unplant <host>", i18n.t("app_help_unplant")),
                ("botnet", i18n.t("app_help_botnet")),
            ],
        ),
        (
            i18n.t("app_help_sec_session"),
            [
                ("save", i18n.t("app_help_save")),
                ("desk", i18n.t("app_help_desk")),
                ("reboot", i18n.t("app_help_reboot")),
                ("clear", i18n.t("app_help_clear")),
                ("help", i18n.t("app_help_help")),
                ("exit", i18n.t("app_help_exit")),
            ],
        ),
    ]


class CommandSuggester(Suggester):
    """Fantasma do autocomplete: o resto do comando em cinza depois do cursor.

    O Textual desenha a sugestão apagada e a aceita com → / End. Reaproveita o
    mesmo `compute_completion` do Tab, então fantasma e Tab nunca discordam.
    """

    def __init__(self, app: "ColdBootApp") -> None:
        super().__init__(use_cache=False, case_sensitive=True)
        self._app = app

    async def get_suggestion(self, value: str) -> str | None:
        if not value or value.endswith(" "):
            return None
        guess, _cands = self._app.compute_completion(value)
        if guess is None:
            return None
        guess = guess.rstrip()
        # O Textual só desenha o fantasma se a sugestão estender o valor atual.
        return guess if guess.startswith(value) and guess != value else None


class CommandInput(Input):
    """Input do prompt com autocomplete (Tab + fantasma) e histórico (↑/↓).

    A lógica de candidatos fica no app, que conhece o estado do jogo; aqui fica
    só o teclado.
    """

    BINDINGS = [
        Binding("tab", "autocomplete", "Autocompletar", show=False, priority=True),
        Binding("up", "history_prev", "Comando anterior", show=False, priority=True),
        Binding("down", "history_next", "Próximo comando", show=False, priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.history: list[str] = []
        self._hist_idx = 0  # == len(history) => digitando uma linha nova
        self._draft = ""  # o que estava digitado antes de subir no histórico

    def remember(self, raw: str) -> None:
        """Guarda um comando executado. Repetições seguidas não duplicam."""
        if raw.strip() and (not self.history or self.history[-1] != raw):
            self.history.append(raw)
        self._hist_idx = len(self.history)
        self._draft = ""

    def _show(self, value: str) -> None:
        self.value = value
        self.cursor_position = len(value)

    def action_history_prev(self) -> None:
        if self._hist_idx == 0:
            return
        if self._hist_idx == len(self.history):
            self._draft = self.value  # preserva a linha em digitação
        self._hist_idx -= 1
        self._show(self.history[self._hist_idx])

    def action_history_next(self) -> None:
        if self._hist_idx >= len(self.history):
            return
        self._hist_idx += 1
        self._show(
            self.history[self._hist_idx]
            if self._hist_idx < len(self.history)
            else self._draft
        )

    def action_autocomplete(self) -> None:
        new_value, candidates = self.app.compute_completion(self.value)
        if len(candidates) > 1:
            self.app.narrative.echo("  ".join(candidates), "grey58")
        if new_value is not None:
            self._show(new_value)


class ColdBootApp(App):
    CSS_PATH = "game.tcss"
    TITLE = "Project: COLD-BOOT"

    BINDINGS = [
        Binding("escape", "pause", "Pausa/Opções", priority=True),
    ]

    def action_quit(self) -> None:
        """Sobrescreve a ação padrão 'quit' do Textual: sem binding nenhum
        chamando ela (nem ctrl+c), mas se algo ainda chamar (ex.: um binding
        futuro reintroduzido sem querer), cai no mesmo fluxo do Esc em vez de
        fechar direto sem chance de salvar."""
        self.action_pause()

    def __init__(
        self,
        seed: int | None = None,
        boot: bool = True,
        save_path: Path | None = None,
        settings_path: Path | None = None,
        tutorial_on: bool = True,
    ) -> None:
        super().__init__()
        self.state = new_game(seed)
        # explore | combat | lockdown | cipher | dead | tutorial | desk
        self.mode = "explore"
        self.combat: CombatSession | None = None
        self._combat_timer = None
        self.cipher: CipherSession | None = None
        self.lockdown: LockdownSession | None = None
        self._lockdown_timer = None
        self.villain_said: str | None = None
        self._warned_hot = False
        self.paused = False  # menu de pausa aberto: congela os timers
        self._boot = boot
        self._tutorial = tutorial_on
        self._tut_active = False  # roteiro do setor 0 em andamento
        self._tut_step = 0
        self.save_path = save_path or savegame.SAVE_PATH
        self.settings_path = settings_path
        self.settings = settings_mod.load(settings_path)

    # ------------------------------------------------------------------ #
    # UI Manager: layout dos 3 painéis
    # ------------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            with Vertical(id="status-col"):
                yield Static(id="status")
                yield RichLog(id="syslog", wrap=True, markup=False, highlight=False)
            yield Static(id="rig")
            yield Static(id="map")
        yield NarrativeView(id="narrative")
        with Horizontal(id="prompt-row"):
            yield Static("guest@coldboot:~$ ", id="ps1")
            yield CommandInput(
                id="prompt",
                placeholder=i18n.t("app_placeholder_default"),
                suggester=CommandSuggester(self),
            )

    # ------------------------------------------------------------------ #
    # Boot
    # ------------------------------------------------------------------ #
    def on_mount(self) -> None:
        self.query_one("#top").border_title = i18n.t("app_border_status")
        self.query_one("#narrative").border_title = i18n.t("app_border_narrative")
        self.apply_settings()
        self.update_prompt()
        # Timers em tempo real (não bloqueiam o input).
        self.set_interval(3.2, self._syslog_tick)
        self.set_interval(4.0, self._trace_creep)
        self.set_interval(2.0, self._economy_tick)  # mineração / calor
        self._apply_rig()
        if self._boot:
            # O POST do KRYOS/OS cobre a tela; a run só começa quando ele sai.
            self.paused = True
            self.push_screen(BootScreen(self.settings), self._boot_done)
        else:
            self._start_session()

    def _boot_done(self, _result=None) -> None:
        self.paused = False
        self._start_session()

    def _start_session(self) -> None:
        for text, style, speed in _boot_sequence():
            self.narrative.narrate(text, style, speed)
        self.narrative.narrate(
            i18n.t(
                "app_session_sector_seed",
                sector=self.state.sector,
                seed=self.state.seed,
            ),
            "grey58",
            0.0,
        )
        self.query_one("#prompt", Input).focus()
        if self._tutorial and not self.settings.tutorial_done:
            self.start_tutorial()

    # ------------------------------------------------------------------ #
    # Tutorial (setor 0 roteirizado)
    # ------------------------------------------------------------------ #
    def start_tutorial(self) -> None:
        self.mode = "tutorial"
        self._tut_active = True
        self._tut_step = 0
        self.state = tutorial.build_sector_zero()
        self._apply_rig()
        self.update_prompt()
        self.refresh_status()
        self.refresh_rig()
        self.refresh_map()
        self.narrative.narrate(i18n.t("app_tut_intro"), "bold cyan", 0.012)
        self._tut_prompt()

    def _tut_prompt(self) -> None:
        step = tutorial.STEPS[self._tut_step]
        self.narrative.narrate("» " + step.prompt, "bold yellow", 0.008)

    def _tut_advance(self, verb: str) -> None:
        """Chamado depois de cada comando enquanto o tutorial roda."""
        if not self._tut_active or self._tut_step >= len(tutorial.STEPS):
            return
        step = tutorial.STEPS[self._tut_step]
        if verb != step.verb:
            return
        # O `hack` só conta quando o DUELO acaba, não quando o comando é
        # digitado — senão o treino se encerrava com o combate ainda em pé.
        if step.verb == "hack":
            return
        self._tut_step_done(step)

    def _tut_step_done(self, step) -> None:
        self.narrative.narrate("  ✓ " + step.done, "green3", 0.006)
        self._tut_step += 1
        if self._tut_step >= len(tutorial.STEPS):
            self._tut_done()
        else:
            self._tut_prompt()

    def _tut_combat_won(self) -> None:
        """O duelo do último passo caiu: fecha o treino."""
        if not self._tut_active or self._tut_step >= len(tutorial.STEPS):
            return
        step = tutorial.STEPS[self._tut_step]
        if step.verb == "hack":
            self._tut_step_done(step)

    def _tut_done(self) -> None:
        self._tut_active = False
        self.settings.tutorial_done = True
        settings_mod.save(self.settings, self.settings_path)
        self.narrative.narrate(i18n.t("app_tut_done"), "bold cyan", 0.010)
        self.state = new_game(sector=1)
        self.mode = "explore"
        self.go_desk("start")

    def do_pular(self, cmd) -> None:
        if not self._tut_active:
            self.narrative.narrate(i18n.t("app_pular_not_active"), "yellow")
            return
        self.narrative.narrate(i18n.t("app_pular_done"), "grey58", 0.004)
        self._tut_done()

    # ------------------------------------------------------------------ #
    # Atalhos de acesso
    # ------------------------------------------------------------------ #
    @property
    def narrative(self) -> NarrativeView:
        return self.query_one("#narrative", NarrativeView)

    def refresh_status(self) -> None:
        self.query_one("#status", Static).update(
            render_status(self.state, self.settings.high_contrast)
        )

    def refresh_rig(self) -> None:
        self.query_one("#rig", Static).update(
            render_rig(self.state, self.settings.high_contrast)
        )

    def refresh_map(self) -> None:
        self.query_one("#map", Static).update(
            render_map(self.state, self.settings.high_contrast)
        )

    def sys(self, msg: str, style: str = "grey42") -> None:
        self.query_one("#syslog", RichLog).write(
            Text(f"· {msg}", theme.resolve(style, self.settings.high_contrast))
        )

    def update_prompt(self) -> None:
        host = self.state.location.lower()
        self.query_one("#ps1", Static).update(f"guest@{host}:{self.state.cwd_str()}$ ")

    # ------------------------------------------------------------------ #
    # Pausa / opções / save
    # ------------------------------------------------------------------ #
    def action_pause(self) -> None:
        """Esc, de qualquer lugar. O binding do app tem prioridade sobre o das
        telas, então o toggle mora aqui: as telas não veem essa tecla."""
        scr = self.screen
        if isinstance(scr, BootScreen):
            scr.action_skip()
            return
        if isinstance(scr, PauseScreen):
            scr.dismiss(None)
            return
        if self.mode == "dead":
            return
        self.paused = True
        self.push_screen(
            PauseScreen(
                self.settings,
                can_save=(self.mode == "explore"),
                has_save=savegame.has_save(self.save_path),
            ),
            self._pause_closed,
        )

    def _pause_closed(self, result=None) -> None:
        self.paused = False
        settings_mod.save(self.settings, self.settings_path)
        if result == "quit":
            self.exit()
            return
        if result == "load":
            self.load_game()
        self.query_one("#prompt", Input).focus()

    def apply_settings(self) -> None:
        """Reflete as preferências atuais na tela inteira.

        `i18n.set_locale()` é global ao processo, não por-instância — mas como
        só existe um `ColdBootApp` rodando por vez, isso equivale a "o idioma
        atual da sessão". Precisa ser chamado aqui (e não só no boot) para o
        botão de idioma do menu de pausa ter efeito imediato.
        """
        i18n.set_locale(self.settings.locale)
        hc = self.settings.high_contrast
        self.screen.set_class(hc, theme.CSS_CLASS)
        self.narrative.high_contrast = hc
        self.narrative.restyle()
        self.refresh_status()
        self.refresh_rig()
        self.refresh_map()

    # ------------------------------------------------------------------ #
    # A MESA — o hub entre setores
    # ------------------------------------------------------------------ #
    def go_desk(self, reason: str = "clear") -> None:
        """Desconecta e volta para a mesa. Nada te caça enquanto ela está aberta."""
        self.mode = "desk"
        self.paused = True
        self.push_screen(
            DeskScreen(self.settings, self.state, reason), self._desk_closed
        )

    def _desk_closed(self, result=None) -> None:
        self.paused = False
        self.mode = "explore"
        self._apply_rig()
        self.update_prompt()
        self.refresh_status()
        self.refresh_rig()
        self.refresh_map()
        if result == "connect":
            st = self.state
            self.narrative.clear_log()
            self.narrative.narrate(
                i18n.t(
                    "app_desk_connecting",
                    sector=st.sector,
                    hosts=len(st.net),
                    seed=st.seed,
                ),
                "bold cyan",
                0.012,
            )
            self.narrative.narrate(i18n.t("app_desk_inside"), "green3", 0.008)
            if st.modifier_id:
                self.narrative.narrate(
                    i18n.t(
                        "app_sector_modifier",
                        name=i18n.t(f"world_mod_{st.modifier_id}_name"),
                        desc=i18n.t(f"world_mod_{st.modifier_id}_desc"),
                    ),
                    "bold yellow",
                    0.010,
                )
        self.query_one("#prompt", Input).focus()

    def after_purchase(self) -> None:
        """A loja acabou de instalar peças: o rig mudou."""
        self._apply_rig()
        self.refresh_status()
        self.refresh_rig()
        self._hint("first_buy")

    def _hint(self, key: str) -> None:
        """Dica contextual: na primeira vez que a mecânica aparece de verdade."""
        text = tutorial.hint_for(self.state, key)
        if text:
            self.narrative.narrate("[dica] " + text, "bold cyan", 0.006)

    def save_game(self) -> str | None:
        """Grava a partida. Devolve o caminho, ou None se falhar."""
        if self.mode != "explore":
            return None
        try:
            return str(savegame.save(self.state, self.save_path))
        except OSError:
            return None

    def load_game(self) -> bool:
        st = savegame.load(self.save_path)
        if st is None:
            self.narrative.narrate(i18n.t("app_load_no_save"), "red", 0.006)
            return False
        # Um save só existe fora de combate, então derrubar as sessões é seguro.
        if self._combat_timer is not None:
            self._combat_timer.stop()
            self._combat_timer = None
        self._stop_lockdown_timer()
        self.combat = None
        self.cipher = None
        self.lockdown = None
        self.mode = "explore"
        self.state = st
        self.query_one("#prompt", Input).placeholder = i18n.t("app_placeholder_default")
        self._warned_hot = False
        self._apply_rig()
        self.update_prompt()
        self.refresh_status()
        self.refresh_map()
        self.narrative.narrate(
            i18n.t(
                "app_load_restored", seed=st.seed, location=st.location, trace=st.trace
            ),
            "cyan",
            0.006,
        )
        return True

    # ------------------------------------------------------------------ #
    # Autocompletar (Tab)
    # ------------------------------------------------------------------ #
    def compute_completion(self, text: str) -> tuple[str | None, list[str]]:
        """Retorna (novo_valor_ou_None, candidatos_para_listar)."""
        # No treino o autocomplete vale também: é onde ele mais ajuda.
        if self.mode not in ("explore", "tutorial"):
            return (None, [])
        parts = text.split(" ")
        frag = parts[-1]
        if len(parts) == 1:  # completando o verbo
            cands = [v for v in parser.COMPLETION_VERBS if v.startswith(frag.lower())]
        else:  # completando um argumento
            cands = self._arg_candidates(parts[0].lower(), frag)
        if not cands:
            return (None, [])
        if len(cands) == 1:
            parts[-1] = cands[0]
            return (" ".join(parts) + " ", [])
        prefix = os.path.commonprefix(cands)
        if len(prefix) > len(frag):  # estende até o prefixo comum
            parts[-1] = prefix
            return (" ".join(parts), cands)
        return (None, cands)  # nada a estender: só lista

    def _arg_candidates(self, verb: str, frag: str) -> list[str]:
        node = self.state.cwd_node()
        fl = frag.lower()

        def pref(seq):
            return sorted(n for n in seq if n.lower().startswith(fl))

        if verb in ("cd", "ir"):
            return pref(n for n, c in node.children.items() if c.is_dir)
        if verb in ("cat", "ler"):
            return pref(n for n, c in node.children.items() if not c.is_dir)
        if verb == "hack":
            locked = [n for n, c in node.children.items() if c.locked]
            hosts = [
                nd.label for nd in self.state.net.values() if nd.state == "discovered"
            ]
            return pref(locked + hosts)
        if verb in ("buy", "comprar"):
            return pref(CATALOG.keys())
        if verb in ("kill", "matar", "parar", "stop"):
            return pref(self.state.processes)
        if verb in ("take", "pegar"):
            return pref(n for n, c in node.children.items() if c.item)
        if verb in ("drop", "largar"):
            return pref(it["name"] for it in self.state.inventory)
        if verb in ("use", "usar"):
            # o que dá para usar: o que está no bolso + o que está na sala
            return pref(
                [it["name"] for it in self.state.inventory]
                + [n for n, c in node.children.items() if c.item]
            )
        if verb in ("run", "rodar", "executar"):
            return pref(
                list(node.children) + [it["name"] for it in self.state.inventory]
            )
        if verb in ("decrypt", "decifrar", "submit"):
            return []  # o código nunca é sugerido — só existe dentro de arquivos
        if verb in ("plant", "plantar"):
            return pref(
                nd.label for nd in self.state.net.values()
                if nd.state == "compromised" and nd.id not in self.state.botnet
            )
        if verb in ("unplant", "desplantar"):
            return pref(
                nd.label for nd in self.state.net.values() if nd.id in self.state.botnet
            )
        return pref(node.children.keys())

    # ------------------------------------------------------------------ #
    # Timers em tempo real
    # ------------------------------------------------------------------ #
    def _syslog_tick(self) -> None:
        if self.paused:
            return
        self.sys(random_syslog())

    def _trace_creep(self) -> None:
        """Rastreamento ambiente: sobe sozinho, sempre. Ficar parado não ajuda —
        para baixar o Trace de propósito, o jogador usa o minigame de cifra
        (`cipher`) ou um script de disfarce (.bat/.sh, `run`)."""
        if self.paused or self.mode in ("dead", "lockdown", "tutorial"):
            return
        st = self.state
        # Roteador melhor = rota mais limpa = te acham mais devagar.
        st.add_trace(0.4 * economy.creep_mult(st, self.settings.diff()))
        self.refresh_status()
        self._check_trace()

    def _economy_tick(self) -> None:
        if self.paused or self.mode == "dead":
            return
        info = economy.tick_economy(self.state, 1.0)
        if info.overheated and not self._warned_hot:
            self.sys(i18n.t("app_overheat_warning"), "bold red")
            self._warned_hot = True
            self._hint("hot")
        elif not info.overheated and self._warned_hot:
            self.sys(i18n.t("app_overheat_normal"), "green3")
            self._warned_hot = False
        if self.state.ram_tight:
            self._hint("ram_tight")
        if self.state.trace >= 75:
            self._hint("trace_high")
        if self.state.botnet:
            bot = economy.botnet_tick(self.state, rng=self.state.rng, diff=self.settings.diff())
            for host_id in bot.lost:
                label = self.state.net[host_id].label if host_id in self.state.net else host_id
                self.narrative.narrate(
                    i18n.t("app_botnet_lost", host=label), "red", 0.008
                )
        self.refresh_status()
        self.refresh_rig()

    def _apply_rig(self) -> None:
        """Reflete o hardware atual nos sistemas (velocidade do teletype)."""
        self.narrative.speed_mult = economy.tele_speed(self.state)

    def _check_trace(self) -> bool:
        """Se o Trace estourou, dispara o LOCKDOWN (interrompendo o combate)."""
        if self.state.trace < 100 or self.mode in ("lockdown", "dead"):
            return False
        if self._combat_timer is not None:
            self._combat_timer.stop()
            self._combat_timer = None
        self.combat = None
        self.cipher = None
        self._enter_lockdown()
        return True

    # ------------------------------------------------------------------ #
    # Input -> Command Parser -> dispatcher
    # ------------------------------------------------------------------ #
    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value
        event.input.value = ""
        if not raw.strip():
            return
        # Códigos de ICE não entram no histórico: são lixo de uso único e só
        # empurrariam os comandos de verdade para longe do ↑.
        if self.mode == "explore" and isinstance(event.input, CommandInput):
            event.input.remember(raw)
        if self.mode == "combat":
            self._combat_submit(raw)
            return
        if self.mode == "lockdown":
            self._lockdown_submit(raw)
            return
        if self.mode == "cipher":
            self._cipher_submit(raw)
            return
        if self.mode == "dead":
            # A run acabou, mas o jogo não: `reboot` abre a próxima incursão.
            morto = parser.parse(raw)
            if morto is not None and morto.verb in ("reboot", "exit"):
                getattr(self, f"do_{morto.verb}")(morto)
            else:
                self.narrative.echo(i18n.t("app_dead_connection"), "red")
            return

        self.narrative.echo(
            f"guest@{self.state.location.lower()}:{self.state.cwd_str()}$ {raw}",
            "grey58",
        )
        # Superaquecimento pode abortar comandos (throttling térmico).
        if economy.is_overheated(self.state) and random.random() < 0.25:
            self.narrative.narrate(i18n.t("app_thermal_abort"), "red", 0.004)
            return
        cmd = parser.parse(raw)
        if cmd is None:
            return
        handler = getattr(self, f"do_{cmd.verb}", None)
        if handler is None:
            self.do_unknown(cmd)
        else:
            handler(cmd)
        self._tut_advance(cmd.verb)  # o roteiro do treino anda com o comando certo
        self.refresh_status()
        self.refresh_rig()
        self._check_trace()  # comandos (cd trancado, scan...) podem estourar o Trace

    # ------------------------------------------------------------------ #
    # Comandos
    # ------------------------------------------------------------------ #
    def do_help(self, cmd) -> None:
        sections = _help_sections()
        help_pad = max(len(uso) for _t, linhas in sections for uso, _d in linhas) + 3
        for titulo, linhas in sections:
            bloco = [f"  {uso:<{help_pad}}{desc}" for uso, desc in linhas]
            self.narrative.narrate(titulo, "bold cyan", 0.0)
            self.narrative.narrate("\n".join(bloco), "green3", 0.0)
        self.narrative.narrate(
            i18n.t("app_help_natural_lang"),
            "cyan",
            0.004,
        )
        self.narrative.narrate(
            i18n.t("app_help_keys"),
            "cyan",
            0.004,
        )

    def do_ls(self, cmd) -> None:
        node = self.state.cwd_node()
        names = []
        for child in node.children.values():
            tag = "/" if child.is_dir else ""
            lock = i18n.t("app_ls_locked_suffix") if child.locked else ""
            names.append(child.name + tag + lock)
        self.narrative.narrate(
            "  ".join(names) if names else i18n.t("app_ls_empty"), "green3", 0.003
        )

    def do_pwd(self, cmd) -> None:
        self.narrative.narrate(self.state.cwd_str(), "green3", 0.0)

    def do_cd(self, cmd) -> None:
        if not cmd.target:
            self.state.cwd = []
            self.update_prompt()
            return
        parts, node = self.state.resolve(cmd.target)
        if node is None or not node.is_dir:
            self.narrative.narrate(
                i18n.t("app_cd_no_such_dir", target=cmd.target), "red"
            )
            return
        if node.locked and not self._admin_bypass(node):
            self.narrative.narrate(
                i18n.t("app_cd_denied", target=cmd.target, name=node.name), "yellow"
            )
            self.state.add_trace(1.5)
            self._hint("locked")
            return
        self.state.cwd = parts
        self.update_prompt()
        self.narrative.narrate(
            i18n.t("app_cd_moved", path=self.state.cwd_str()), "grey58", 0.0
        )

    def do_cat(self, cmd) -> None:
        if not cmd.target:
            self.narrative.narrate(i18n.t("app_cat_missing_arg"), "red")
            return
        parts, node = self.state.resolve(cmd.target)
        if node is None:
            self.narrative.narrate(
                i18n.t("app_cat_no_such_file", target=cmd.target), "red"
            )
            return
        if node.is_dir:
            self.narrative.narrate(i18n.t("app_cat_is_dir", target=cmd.target), "red")
            return
        if node.locked and not self._admin_bypass(node):
            self.narrative.narrate(
                i18n.t("app_cat_encrypted", target=cmd.target, name=node.name), "yellow"
            )
            return
        self.narrative.narrate(
            node.content or i18n.t("app_cat_empty_file"), "green3", 0.006
        )
        if node.on_read:
            self._fs_event(node.on_read)

    def _admin_bypass(self, node) -> bool:
        """Gasta uma carga de chave de admin para destrancar `node` sem combate.

        Uso suspeito pode inutilizar o login do admin: uma vez `admin_locked`,
        as cargas restantes viram lixo e só resta o `hack`.
        """
        if self.state.adminkey <= 0 or self.state.flags.get("admin_locked"):
            return False
        self.state.adminkey -= 1
        node.locked = False
        self.narrative.narrate(
            i18n.t(
                "app_admin_bypass_used", name=node.name, charges=self.state.adminkey
            ),
            "cyan",
            0.008,
        )
        if random.random() < 0.30:
            self.state.flags["admin_locked"] = True
            self.narrative.narrate(i18n.t("app_admin_bypass_burned"), "red", 0.010)
        self.refresh_status()
        return True

    def do_look(self, cmd) -> None:
        if not cmd.target or cmd.target in ("terminal", "tela", "aqui"):
            self.narrative.narrate(
                i18n.t(
                    "app_look_terminal",
                    location=self.state.location,
                    trace=self.state.trace,
                ),
                "green3",
                0.010,
            )
            return
        parts, node = self.state.resolve(cmd.target)
        if node is None:
            self.narrative.narrate(
                i18n.t("app_look_nothing", target=cmd.target), "yellow"
            )
        elif node.is_dir:
            self.narrative.narrate(i18n.t("app_look_is_dir", name=node.name), "green3")
        else:
            self.narrative.narrate(i18n.t("app_look_is_file", name=node.name), "green3")

    def do_scan(self, cmd) -> None:
        if not self.state.flags.get("scan_unlocked"):
            self.narrative.narrate(i18n.t("app_scan_locked"), "yellow", 0.006)
            self._hint("scan_locked")
            return
        revealed = self.state.reveal_neighbors(self.state.location)
        self.sys(i18n.t("app_scan_active"))
        if revealed:
            self.narrative.narrate(
                i18n.t("app_scan_found", hosts=", ".join(revealed)), "cyan", 0.006
            )
        else:
            self.narrative.narrate(i18n.t("app_scan_none"), "yellow", 0.006)
        self.state.add_trace(2.0)
        self.refresh_map()

    def do_map(self, cmd) -> None:
        self.refresh_map()
        self.narrative.narrate(i18n.t("app_map_updated"), "grey58", 0.0)

    def do_modifier(self, cmd) -> None:
        st = self.state
        if not st.modifier_id:
            self.narrative.narrate(i18n.t("app_modifier_none"), "grey58")
            return
        self.narrative.narrate(
            i18n.t(
                "app_sector_modifier",
                name=i18n.t(f"world_mod_{st.modifier_id}_name"),
                desc=i18n.t(f"world_mod_{st.modifier_id}_desc"),
            ),
            "bold yellow",
        )

    def do_hack(self, cmd) -> None:
        if not cmd.target:
            self.narrative.narrate(i18n.t("app_hack_no_target"), "red")
            return
        kind, obj = self._resolve_hack(cmd.target)
        if kind is None:
            self.narrative.narrate(
                i18n.t("app_hack_not_found", target=cmd.target), "yellow"
            )
            return
        # Profundidade escala a dificuldade (Fase 4): nó da rede usa .depth;
        # diretório trancado usa a profundidade do host atual.
        if kind == "net":
            name, depth = obj.label, obj.depth
        else:
            name = obj.name
            here = self.state.net.get(self.state.location)
            depth = here.depth if here else 0
        # A CPU do rig compra alguns segundos a mais por round; a dificuldade
        # escolhida no menu mexe no tempo e no tamanho/estilo dos códigos.
        bonus = economy.typing_bonus(self.state)
        diff = self.settings.diff()
        st = self.state
        if kind == "net" and obj.id == st.core_id:
            # O CORE do setor é o boss: ICE próprio, mais duro que qualquer nó.
            self._hint("boss")
            sess = make_boss(st.sector, rng=st.rng, time_bonus=bonus, diff=diff,
                             pen_mult=st.mod_ice_penalty)
        else:
            sess = make_ice(
                name, effective_depth(depth, st.sector), rng=st.rng, time_bonus=bonus,
                diff=diff, pen_mult=st.mod_ice_penalty,
            )
        self._start_combat(sess, kind, obj)

    def do_run(self, cmd) -> None:
        prog = cmd.target or ""
        if prog.lower() in ("scan", "nmap"):
            self.do_scan(cmd)
            return
        if prog.lower() in ("", "help"):
            self.narrative.narrate(i18n.t("app_run_usage"), "yellow")
            return
        # O minerador roda estando na pasta ou no buffer — carregar um programa
        # e não poder executá-lo seria um beco sem saída.
        node = self.state.cwd_node().children.get(prog)
        item = node.item if (node and node.item) else self.state.find_item(prog)
        if item and item.get("kind") == "miner":
            st = self.state
            if "miner" in st.processes:
                self.narrative.narrate(i18n.t("app_run_already_running"), "yellow")
                return
            # O minerador tem que caber na memória do host, junto com o buffer.
            kb = hardware.miner_footprint(st.rig)
            if kb > st.ram_free:
                self.narrative.narrate(
                    i18n.t("app_run_no_ram", prog=prog, kb=kb, free=st.ram_free),
                    "red",
                    0.006,
                )
                return
            st.processes.append("miner")
            d = hardware.derived(st.rig)
            self.narrative.narrate(
                i18n.t(
                    "app_run_miner_started",
                    hash=d.hashrate,
                    kb=kb,
                    noise=economy.mining_noise(st),
                ),
                "green3",
                0.006,
            )
            self._apply_rig()
            self.refresh_status()
            return
        if item and item.get("kind") == "spoof":
            self.state.trace = max(0.0, self.state.trace - item["amount"])
            self.state.add_trace(0.0)  # recalcula a conexão
            self.reset_lockdown()
            self.narrative.narrate(
                i18n.t(
                    "app_run_spoof_done", fake_user=item["fake_user"], amount=item["amount"]
                ),
                "bold cyan",
                0.008,
            )
            self._hint("spoof_script")
            if node is not None and node.item is item:
                self.state.cwd_node().children.pop(node.name, None)
            else:
                self.state.inventory.remove(item)
            self.refresh_status()
            return
        self.narrative.narrate(i18n.t("app_run_not_found", prog=prog), "red")

    def do_take(self, cmd) -> None:
        """Carrega um item da pasta para o buffer (custa RAM do host)."""
        alvo = cmd.target or ""
        node = self.state.cwd_node().children.get(alvo)
        if node is None or not node.item:
            self.narrative.narrate(i18n.t("app_take_not_item", target=alvo), "yellow")
            return
        if node.item.get("kind") == "reader":
            self.narrative.narrate(i18n.t("app_take_reader_bolted"), "yellow", 0.006)
            return
        if not self.state.can_hold():
            self.narrative.narrate(
                i18n.t(
                    "app_take_buffer_full",
                    free=self.state.ram_free,
                    item_kb=hardware.ITEM_KB,
                ),
                "red",
                0.006,
            )
            return
        item = dict(node.item)
        item["name"] = node.name
        self.state.inventory.append(item)
        self.state.cwd_node().children.pop(node.name, None)
        self.narrative.narrate(
            i18n.t(
                "app_take_loaded",
                name=node.name,
                item_kb=hardware.ITEM_KB,
                free=self.state.ram_free,
            ),
            "cyan",
            0.006,
        )
        self.refresh_status()

    def do_drop(self, cmd) -> None:
        """Devolve um item do buffer para a pasta atual, liberando RAM."""
        it = self.state.find_item(cmd.target or "")
        if it is None:
            self.narrative.narrate(
                i18n.t("app_drop_not_in_buffer", target=cmd.target), "yellow"
            )
            return
        self.state.inventory.remove(it)
        data = {k: v for k, v in it.items() if k != "name"}
        self.state.cwd_node().add(
            FSNode(
                it["name"],
                False,
                item=data,
                content=i18n.t("app_drop_content", kind=it["kind"]),
            )
        )
        self.narrative.narrate(
            i18n.t("app_drop_done", name=it["name"], free=self.state.ram_free),
            "grey58",
            0.006,
        )
        self.refresh_status()

    def do_use(self, cmd) -> None:
        # `use <item>` ou `use <item> no <alvo>` — o parser já tirou o "no".
        args = cmd.args or []
        nome = args[0] if args else ""
        alvo = args[-1] if len(args) > 1 else None

        # O buffer vem primeiro: item carregado funciona em qualquer lugar.
        carregado = self.state.find_item(nome)
        if carregado is not None:
            self._use_carried(carregado, alvo)
            return
        node = self.state.cwd_node().children.get(nome)
        if node and node.item:
            self._use_item(node)
            return
        self.narrative.narrate(i18n.t("app_use_not_found", name=nome), "yellow")

    def _use_carried(self, item: dict, alvo: str | None) -> None:
        """Usa um item do buffer. Some do buffer se for consumido."""
        if item.get("kind") == "keycard":
            if self._swipe_card(item, alvo):
                self.state.inventory.remove(item)
                self.refresh_status()
            return
        if item.get("kind") == "backdoor":
            if self._use_backdoor(alvo):
                self.state.inventory.remove(item)
                self.refresh_status()
            return
        # Os demais itens funcionam igual, estando na pasta ou no bolso.
        fake = FSNode(item["name"], False, item=item)
        if self._apply_item(fake):
            self.state.inventory.remove(item)
        self.refresh_status()

    def _use_backdoor(self, alvo: str | None) -> bool:
        """Gasta o backdoor.key num alvo hackeável (rede ou pasta trancada),
        resolvendo como se o duelo tivesse sido vencido — sem ICE. Não
        funciona no CORE do setor: o clímax se ganha de verdade."""
        if not alvo:
            self.narrative.narrate(i18n.t("app_backdoor_missing_target"), "red")
            return False
        kind, obj = self._resolve_hack(alvo)
        if kind is None:
            self.narrative.narrate(i18n.t("app_backdoor_not_found", target=alvo), "yellow")
            return False
        if kind == "net" and obj.id == self.state.core_id:
            self.narrative.narrate(i18n.t("app_backdoor_no_boss"), "yellow")
            return False
        if kind == "net":
            obj.state = "compromised"
            self.state.location = obj.id
            self.state.cwd = default_cwd(obj.fs) if obj.fs else []
            self.refresh_map()
            self.narrative.narrate(
                i18n.t("app_backdoor_net_done", label=obj.label), "bold cyan", 0.010
            )
        else:  # "fs"
            obj.locked = False
            self.narrative.narrate(
                i18n.t("app_backdoor_fs_done", name=obj.name), "bold cyan", 0.008
            )
        self.update_prompt()
        self._tut_combat_won()
        return True

    def _swipe_card(self, item: dict, alvo: str | None) -> bool:
        """Passa o cartão no leitor da sala. Devolve True se gastou o cartão."""
        aqui = self.state.cwd_node()
        leitores = [
            c
            for c in aqui.children.values()
            if c.item and c.item.get("kind") == "reader"
        ]
        if alvo:
            leitores = [c for c in leitores if c.name == alvo] or leitores
        if not leitores:
            self.narrative.narrate(i18n.t("app_swipe_no_reader"), "yellow", 0.006)
            return False
        leitor = leitores[0]
        cofre = aqui.children.get(leitor.item.get("opens", ""))
        if cofre is None or not cofre.locked:
            self.narrative.narrate(i18n.t("app_swipe_nothing_locked"), "yellow", 0.006)
            return False
        cofre.locked = False
        self.narrative.narrate(
            i18n.t("app_swipe_success", code=item.get("code", "?"), name=cofre.name),
            "bold cyan",
            0.010,
        )
        return True

    def _use_item(self, node) -> None:
        parent = self.state.cwd_node()
        if self._apply_item(node):
            parent.children.pop(node.name, None)
        self.refresh_status()

    def _apply_item(self, node) -> bool:
        """Efeito do item. Devolve True se ele foi consumido."""
        it = node.item
        kind = it.get("kind")
        consumed = True

        if kind in ("wallet", "credits"):
            self.state.wallet = round(self.state.wallet + it["amount"], 3)
            self.narrative.narrate(
                i18n.t(
                    "app_item_credited",
                    amount=it["amount"],
                    coin=hardware.COIN,
                    balance=self.state.wallet,
                ),
                "bold yellow",
                0.008,
            )
        elif kind == "adminkey":
            self.state.adminkey += it["charges"]
            self.narrative.narrate(
                i18n.t("app_item_adminkey", charges=it["charges"]), "cyan", 0.008
            )
        elif kind == "coolant":
            self.state.heat = max(hardware.AMBIENT, self.state.heat - it["amount"])
            self.narrative.narrate(
                i18n.t("app_item_coolant", amount=it["amount"]), "green3", 0.006
            )
        elif kind == "scrambler":
            self.state.trace = max(0.0, self.state.trace - it["amount"])
            self.state.add_trace(0.0)
            self.reset_lockdown()
            self.narrative.narrate(
                i18n.t("app_item_scrambler", amount=it["amount"]), "cyan", 0.008
            )
        elif kind == "miner":
            self.narrative.narrate(
                i18n.t("app_item_is_miner", name=node.name), "yellow", 0.006
            )
            consumed = False
        elif kind == "spoof":
            self.narrative.narrate(
                i18n.t("app_item_is_spoof", name=node.name), "yellow", 0.006
            )
            consumed = False
        elif kind == "reader":
            self.narrative.narrate(i18n.t("app_item_reader_idle"), "yellow", 0.006)
            consumed = False
        elif kind == "keycard":
            self.narrative.narrate(
                i18n.t("app_item_keycard_needs_take", name=node.name), "yellow", 0.006
            )
            consumed = False
        elif kind == "backdoor":
            self.narrative.narrate(
                i18n.t("app_item_backdoor_needs_take", name=node.name), "yellow", 0.006
            )
            consumed = False
        else:
            self.narrative.narrate(i18n.t("app_item_nothing"), "yellow")
            consumed = False

        return consumed

    def do_inv(self, cmd) -> None:
        st = self.state
        bits = [f"{hardware.COIN} {st.wallet:.2f}"]
        if st.adminkey:
            bits.append(i18n.t("app_inv_adminkey", charges=st.adminkey))
        self.narrative.narrate(
            i18n.t("app_inv_label") + " · ".join(bits), "cyan", 0.004
        )
        if st.inventory:
            linhas = [
                f"  {it['name']:<24} {it.get('kind', '?')}" for it in st.inventory
            ]
            self.narrative.narrate("\n".join(linhas), "green3", 0.0)
        else:
            self.narrative.narrate(i18n.t("app_inv_empty"), "grey58", 0.0)
        suffix = i18n.t("app_inv_tight_badge") if st.ram_tight else ""
        self.narrative.narrate(
            i18n.t(
                "app_inv_summary",
                count=len(st.inventory),
                used=st.ram_used(),
                total=st.ram_total,
                free=st.ram_free,
            )
            + suffix,
            "bold red" if st.ram_tight else "grey58",
            0.0,
        )

    def do_whoami(self, cmd) -> None:
        self.narrative.narrate(i18n.t("app_whoami"), "green3", 0.008)

    def do_ps(self, cmd) -> None:
        st = self.state
        lines = [
            i18n.t("app_ps_header"),
            i18n.t("app_ps_init"),
            i18n.t("app_ps_coldboot"),
            i18n.t("app_ps_getty"),
        ]
        if "miner" in st.processes:
            d = hardware.derived(st.rig)
            kb = hardware.miner_footprint(st.rig)
            miner_line = i18n.t(
                "app_ps_miner", kb=kb, hash=d.hashrate, watts=d.power_load
            )
            if economy.is_overheated(st):
                miner_line += i18n.t("app_ps_throttle_badge")
            lines.append(miner_line)
        if st.inventory:
            lines.append(
                i18n.t(
                    "app_ps_buffer",
                    kb=len(st.inventory) * hardware.ITEM_KB,
                    count=len(st.inventory),
                )
            )
        lives = i18n.t("app_ps_free", free=st.ram_free, total=st.ram_total)
        if st.ram_tight:
            lives += i18n.t("app_ps_watching")
        lines.append(lives)
        self.narrative.narrate("\n".join(lines), "green3", 0.004)

    def do_kill(self, cmd) -> None:
        proc = (cmd.target or "").lower()
        if not proc:
            self.narrative.narrate(i18n.t("app_kill_missing_arg"), "red")
            return
        if proc not in self.state.processes:
            self.narrative.narrate(i18n.t("app_kill_not_found", proc=proc), "red")
            return
        self.state.processes.remove(proc)
        self.narrative.narrate(i18n.t("app_kill_done", proc=proc), "green3", 0.006)
        self._apply_rig()
        self.refresh_status()

    def _resolve_compromised(self, target: str):
        """Acha um host COMPROMETIDO pelo id/label (case-insensitive)."""
        t = target.lower().strip("/")
        for n in self.state.net.values():
            if n.state == "compromised" and t in (n.id.lower(), n.label.lower()):
                return n
        return None

    def do_plant(self, cmd) -> None:
        """Planta um script minerador remoto num host já comprometido."""
        st = self.state
        target = (cmd.target or "").strip()
        if not target:
            self.narrative.narrate(i18n.t("app_plant_missing_arg"), "red")
            return
        host = self._resolve_compromised(target)
        if host is None:
            self.narrative.narrate(i18n.t("app_plant_not_found", target=target), "red")
            return
        if host.id in st.botnet:
            self.narrative.narrate(i18n.t("app_plant_already", label=host.label), "yellow")
            return
        cap = economy.botnet_capacity(st.rig)
        if len(st.botnet) >= cap:
            self.narrative.narrate(
                i18n.t("app_plant_no_capacity", used=len(st.botnet), cap=cap), "yellow"
            )
            return
        st.botnet[host.id] = 0
        rate = economy.botnet_income_rate(st.sector)
        self.narrative.narrate(
            i18n.t(
                "app_plant_done", label=host.label, rate=rate, coin=hardware.COIN,
                used=len(st.botnet), cap=cap,
            ),
            "bold cyan",
            0.008,
        )

    def do_unplant(self, cmd) -> None:
        """Puxa um script de volta antes que ele seja descoberto — sem multa,
        mas também sem mais renda dali."""
        st = self.state
        target = (cmd.target or "").strip()
        host = self._resolve_compromised(target) if target else None
        host_id = host.id if host else None
        if host_id is None or host_id not in st.botnet:
            self.narrative.narrate(i18n.t("app_unplant_not_planted", target=target), "yellow")
            return
        del st.botnet[host_id]
        self.narrative.narrate(i18n.t("app_unplant_done", label=host.label), "cyan", 0.006)

    def do_botnet(self, cmd) -> None:
        st = self.state
        if not st.botnet:
            self.narrative.narrate(i18n.t("app_botnet_empty"), "grey58")
            return
        rate = economy.botnet_income_rate(st.sector)
        mult = economy.botnet_risk_mult(st, self.settings.diff())
        lines = []
        for host_id, age in st.botnet.items():
            label = st.net[host_id].label if host_id in st.net else host_id
            risk = economy.botnet_risk(age, mult)
            if risk > 0:
                lines.append(
                    i18n.t(
                        "app_botnet_line_hot", label=label, age=age, rate=rate,
                        coin=hardware.COIN, risk=risk * 100,
                    )
                )
            else:
                lines.append(
                    i18n.t("app_botnet_line", label=label, age=age, rate=rate, coin=hardware.COIN)
                )
        cap = economy.botnet_capacity(st.rig)
        self.narrative.narrate(
            i18n.t("app_botnet_header", used=len(st.botnet), cap=cap), "cyan", 0.0
        )
        self.narrative.narrate("\n".join(lines), "green3", 0.0)

    def do_buy(self, cmd) -> None:
        part_id = (cmd.target or "").strip().lower()
        if not part_id:
            self.narrative.narrate(i18n.t("app_buy_missing_arg"), "red")
            return
        ok, msg, warnings = economy.buy(self.state, part_id)
        prefix = i18n.t("app_buy_prefix_ok") if ok else i18n.t("app_buy_prefix_fail")
        self.narrative.narrate(prefix + msg, "bold green3" if ok else "yellow", 0.006)
        for w in warnings:
            self.narrative.narrate("    [!] " + w, "yellow", 0.006)
        if ok:
            self._apply_rig()
            self.refresh_status()

    def do_decrypt(self, cmd) -> None:
        """Submete o código do puzzle de setor (3 fragmentos espalhados pela
        rede). Recompensa alta, uma vez por setor — não é o objetivo do jogo,
        é um bônus para quem lê tudo que encontra."""
        st = self.state
        guess = (cmd.target or "").strip()
        if not guess:
            self.narrative.narrate(i18n.t("app_decrypt_missing_arg"), "red")
            return
        if st.flags.get("puzzle_solved"):
            self.narrative.narrate(i18n.t("app_decrypt_already_solved"), "yellow")
            return
        if not puzzle.check(st, guess):
            self.narrative.narrate(i18n.t("app_decrypt_wrong"), "red", 0.006)
            return
        st.flags["puzzle_solved"] = True
        reward = puzzle_reward(st.sector)
        st.wallet = round(st.wallet + reward, 2)
        st.trace = max(0.0, st.trace - PUZZLE_TRACE_RELIEF)
        st.add_trace(0.0)  # recalcula a conexão
        self.reset_lockdown()
        self.narrative.narrate(
            i18n.t(
                "app_decrypt_success",
                amount=reward,
                coin=hardware.COIN,
                balance=st.wallet,
                relief=PUZZLE_TRACE_RELIEF,
            ),
            "bold cyan",
            0.010,
        )
        self.refresh_status()

    def do_cipher(self, cmd) -> None:
        """Abre o minigame de cifra: quebrar um código por dedução (sem
        relógio, só tentativas limitadas). Reduz o Trace ao vencer. Limitado
        a MAX_CIPHER_PER_SECTOR vezes por incursão."""
        if self.mode != "explore":
            self.narrative.narrate(i18n.t("app_cipher_busy"), "yellow")
            return
        st = self.state
        if st.cipher_uses >= MAX_CIPHER_PER_SECTOR:
            self.narrative.narrate(
                i18n.t("app_cipher_no_uses_left", used=st.cipher_uses, cap=MAX_CIPHER_PER_SECTOR),
                "yellow",
            )
            return
        st.cipher_uses += 1
        self.cipher = make_cipher(st.sector, rng=st.rng)
        self.mode = "cipher"
        self._hint("cipher_intro")
        self.narrative.narrate(
            i18n.t(
                "app_cipher_start",
                length=self.cipher.length,
                alphabet=self.cipher.alphabet,
                guesses=self.cipher.max_guesses,
                used=st.cipher_uses,
                cap=MAX_CIPHER_PER_SECTOR,
            ),
            "bold cyan",
            0.008,
        )
        self.query_one("#prompt", Input).placeholder = i18n.t("app_placeholder_cipher")

    def _cipher_submit(self, raw: str) -> None:
        c = self.cipher
        if c is None:
            self.mode = "explore"
            return
        res: CipherResult = c.submit(raw)
        if res.kind == "invalid":
            self.narrative.narrate(
                i18n.t("app_cipher_invalid", length=c.length, alphabet=c.alphabet), "red"
            )
            return
        if res.kind == "win":
            st = self.state
            st.trace = max(0.0, st.trace - CIPHER_TRACE_RELIEF)
            st.add_trace(0.0)  # recalcula a conexão
            self.reset_lockdown()
            self.narrative.narrate(
                i18n.t("app_cipher_win", relief=CIPHER_TRACE_RELIEF), "bold green3", 0.010
            )
            self._end_cipher()
            return
        if res.kind == "lose":
            self.narrative.narrate(i18n.t("app_cipher_lose", code=c.secret), "red", 0.010)
            self._end_cipher()
            return
        # progresso: mostra o feedback e continua na mesma sessão
        self.narrative.narrate(
            i18n.t(
                "app_cipher_feedback",
                exact=res.exact,
                partial=res.partial,
                left=res.guesses_left,
            ),
            "cyan",
        )

    def _end_cipher(self) -> None:
        self.cipher = None
        self.mode = "explore"
        self.query_one("#prompt", Input).placeholder = i18n.t("app_placeholder_default")
        self.refresh_status()
        self._check_trace()

    def do_reboot(self, cmd) -> None:
        """Volta para a mesa. Depois de morrer, recomeça no setor 1."""
        if self.mode not in ("dead", "explore"):
            self.narrative.narrate(i18n.t("app_reboot_busy"), "yellow")
            return
        if self.mode == "dead":
            # Morrer joga de volta ao setor 1: o rig é o único ratchet.
            self.state = next_run(self.state, won=False)
            self.combat = None
            self.cipher = None
            self.lockdown = None
            self.villain_said = None
            self._warned_hot = False
            self.reset_lockdown()
            self.query_one("#prompt", Input).placeholder = i18n.t(
                "app_placeholder_default"
            )
            self.go_desk("dead")
            return
        self.go_desk("start")

    def do_desk(self, cmd) -> None:
        """Desconecta no meio do setor e volta para a mesa.

        Sair pelo meio custa o setor: você reconecta numa rede nova, do mesmo
        número — não dá para usar a mesa como pausa infinita para fugir do Trace.
        """
        st = self.state
        self.state = new_game(sector=st.sector)
        self.state.rig = st.rig.copy()
        self.state.wallet = st.wallet
        self.state.run_number = st.run_number + 1
        self.state.runs_won = st.runs_won
        self.state.best_sector = st.best_sector
        for k, v in st.flags.items():
            if k.startswith("hint_"):
                self.state.flags[k] = v
        self.narrative.narrate(i18n.t("app_desk_disconnect"), "yellow", 0.010)
        self.go_desk("start")

    def do_store(self, cmd) -> None:
        """Abre a loja (pop-up) — de dentro do setor ou da mesa."""
        self.paused = True
        self.push_screen(ShopScreen(self.settings, self.state), self._shop_closed)

    def _shop_closed(self, _result=None) -> None:
        self.paused = False
        self.after_purchase()
        self.query_one("#prompt", Input).focus()

    def do_save(self, cmd) -> None:
        path = self.save_game()
        if path:
            self.narrative.narrate(i18n.t("app_save_ok", path=path), "bold cyan", 0.006)
        else:
            self.narrative.narrate(i18n.t("app_save_busy"), "yellow", 0.006)

    def do_clear(self, cmd) -> None:
        self.narrative.clear_log()

    def do_exit(self, cmd) -> None:
        # Sugestão de save só faz sentido em pleno jogo (mesma regra do botão
        # Salvar no menu de pausa: desabilitado fora de "explore").
        if self.mode == "explore":
            self.narrative.narrate(i18n.t("app_exit_save_hint"), "cyan", 0.006)
        self.narrative.narrate(i18n.t("app_exit_message"), "yellow", 0.01)
        self.set_timer(1.2, self.exit)

    def do_unknown(self, cmd) -> None:
        self.narrative.narrate(i18n.t("app_unknown_command", raw=cmd.raw), "red", 0.004)

    # ------------------------------------------------------------------ #
    # Eventos de leitura de arquivo
    # ------------------------------------------------------------------ #
    def _fs_event(self, event: str) -> None:
        if event == "read_auth":
            self.state.flags["read_auth"] = True
            self.narrative.narrate(i18n.t("app_fs_read_auth"), "cyan", 0.008)
        elif event == "got_keycard":
            self.state.inventory.add("keycard")
            self.narrative.narrate(i18n.t("app_fs_got_keycard"), "cyan", 0.008)
        elif event == "poke_daemon":
            self.state.add_trace(12.0)
            self.narrative.narrate(i18n.t("app_fs_poke_daemon"), "red", 0.012)
        elif event == "unlock_scan":
            if not self.state.flags.get("scan_unlocked"):
                self.state.flags["scan_unlocked"] = True
                self.narrative.narrate(i18n.t("app_fs_unlock_scan"), "bold cyan", 0.010)

    # ------------------------------------------------------------------ #
    # Combate Rítmico de Digitação
    # ------------------------------------------------------------------ #
    def _resolve_hack(self, target: str):
        t = target.lower().strip("/")
        for n in self.state.net.values():
            if t in (n.id.lower(), (n.hack_id or "").lower(), n.label.lower()):
                if n.state != "compromised":
                    return ("net", n)
        cwd = self.state.cwd_node()
        node = cwd.children.get(target)
        if node and node.locked:
            return ("fs", node)
        return (None, None)

    def _start_combat(self, session: CombatSession, kind: str, obj) -> None:
        self.mode = "combat"
        self.combat = session
        self._combat_ctx = (kind, obj)
        session.start()
        self.narrative.narrate(
            i18n.t(
                "app_combat_ice_active",
                ice_type=session.ice_type,
                name=session.name,
                rounds=session.total_rounds,
            ),
            "red",
            0.010,
        )
        # Cada tipo joga de um jeito: avisar é justo, e a surpresa só irritaria.
        if session.behavior == "memory":
            self.narrative.narrate(
                i18n.t("app_combat_hint_memory"), "bold yellow", 0.008
            )
        elif session.behavior == "hunt":
            self.narrative.narrate(i18n.t("app_combat_hint_hunt"), "bold yellow", 0.008)
        elif session.behavior == "phantom":
            self.narrative.narrate(i18n.t("app_combat_hint_phantom"), "bold yellow", 0.008)
        self.query_one("#prompt", Input).placeholder = i18n.t("app_placeholder_code")
        self._combat_timer = self.set_interval(0.1, self._combat_tick)
        self._render_combat()

    def _render_combat(self) -> None:
        c = self.combat
        if not c:
            return
        hc = self.settings.high_contrast

        def s(style: str) -> str:
            return theme.resolve(style, hc)

        # O código escondido (Guardião) e o que escapou (Caçador) precisam ser
        # legíveis como estado, não como um código qualquer piscando na tela.
        if c.behavior in ("memory", "phantom") and not c.code_visible:
            code_style = "bold yellow on grey15"
        elif c.behavior == "hunt" and c.mutated:
            code_style = "bold red on grey15"
        else:
            code_style = "bold green3 on grey15"
        self.query_one("#ps1", Static).update(
            Text.assemble(
                (
                    f"⧗ {c.time_left:4.1f}s ",
                    s("bold red" if c.time_left < 2 else "yellow"),
                ),
                (f"[{c.round + 1}/{c.total_rounds}] » ", s("grey58")),
                (c.display_code(), s(code_style)),
            )
        )

    def _combat_tick(self) -> None:
        c = self.combat
        # `is_running`: sair no meio de um duelo derruba os widgets, mas o timer
        # de 0.1s ainda pode disparar uma vez e tentar desenhar num prompt morto.
        if not c or self.paused or not self.is_running:
            return
        res = c.tick(0.1)
        if res is not None:
            self._apply_combat(res)
        else:
            self._render_combat()

    def _combat_submit(self, raw: str) -> None:
        c = self.combat
        if not c:
            return
        self._apply_combat(c.submit(raw))

    def _apply_combat(self, res: CombatResult) -> None:
        if res.trace_delta:
            self.state.add_trace(res.trace_delta)
            self.refresh_status()
        if res.kind == "won":
            self._end_combat(True, res.message)
        elif res.kind == "lost":
            self._end_combat(False, res.message)
        else:  # hit | miss -> continua
            style = "green3" if res.kind == "hit" else "red"
            self.narrative.narrate(res.message, style, 0.006)
            if self._check_trace():  # Trace estourou -> vira LOCKDOWN
                return
            self._render_combat()

    def _end_combat(self, success: bool, message: str) -> None:
        if self._combat_timer is not None:
            self._combat_timer.stop()
            self._combat_timer = None
        kind, obj = getattr(self, "_combat_ctx", (None, None))
        self.mode = "explore"
        self.query_one("#prompt", Input).placeholder = i18n.t("app_placeholder_default")
        self.narrative.narrate(message, "green3" if success else "red", 0.012)

        if success and kind == "net":
            obj.state = "compromised"
            self.state.location = obj.id
            # pivota para o host invadido: monta o filesystem dele
            self.state.cwd = default_cwd(obj.fs) if obj.fs else []
            # NÃO revela os vizinhos de graça — isso encadeava hack->hack sem
            # nunca precisar de `scan`. Ver /home/admin ou /etc/hosts.
            self.refresh_map()
            self.narrative.narrate(
                i18n.t("app_combat_connected", label=obj.label), "cyan", 0.010
            )
            if obj.id == self.state.core_id:
                self._win()
        elif success and kind == "fs":
            obj.locked = False
            self.narrative.narrate(
                i18n.t("app_combat_fs_unlocked", name=obj.name), "cyan", 0.008
            )
        self.update_prompt()
        self.combat = None
        if success:
            self._tut_combat_won()  # o último passo do treino é vencer um duelo
        self._check_trace()

    # ------------------------------------------------------------------ #
    # LOCKDOWN — minigame de Trace 100% + falas do vilão
    # ------------------------------------------------------------------ #
    def _enter_lockdown(self) -> None:
        self.mode = "lockdown"
        self.lockdown = LockdownSession(
            self.state.lockdown_level,
            economy.typing_bonus(self.state),
            diff=self.settings.diff(),
            rng=self.state.rng,
        )
        self.state.connection = "critical"
        self.refresh_status()
        self.narrative.narrate(i18n.t("app_lockdown_enter"), "bold red", 0.014)
        self.query_one("#prompt", Input).placeholder = i18n.t(
            "app_placeholder_lockdown"
        )
        self._lockdown_timer = self.set_interval(0.1, self._lockdown_tick)
        self._render_lockdown()

    def _render_lockdown(self) -> None:
        ld = self.lockdown
        if not ld:
            return
        self.query_one("#ps1", Static).update(
            Text.assemble(
                (f"⧗ {ld.time_left:4.1f}s ", "bold red"),
                (f"[{ld.round + 1}/{ld.total}] REBATER » ", "bold red"),
                (ld.code, "bold yellow on grey15"),
            )
        )

    def _lockdown_tick(self) -> None:
        ld = self.lockdown
        if not ld or self.paused or not self.is_running:
            return
        if ld.tick(0.1) == "fail":
            self._lockdown_fail()
        else:
            self._render_lockdown()

    def _lockdown_submit(self, raw: str) -> None:
        ld = self.lockdown
        if not ld:
            return
        res = ld.submit(raw)
        if res == "win":
            self._lockdown_win()
        elif res == "fail":
            self._lockdown_fail()
        else:
            self.narrative.narrate(i18n.t("app_lockdown_countered"), "green3", 0.004)
            self._render_lockdown()

    def _stop_lockdown_timer(self) -> None:
        if self._lockdown_timer is not None:
            self._lockdown_timer.stop()
            self._lockdown_timer = None

    def _lockdown_win(self) -> None:
        self._stop_lockdown_timer()
        self.lockdown = None
        self.state.lockdown_level += 1
        self.state.trace = 55.0
        self.state.add_trace(0.0)  # recalcula a conexão
        self.mode = "explore"
        self.query_one("#prompt", Input).placeholder = i18n.t("app_placeholder_default")
        self.update_prompt()
        self.refresh_status()
        self.narrative.narrate(
            i18n.t("app_lockdown_won", level=self.state.lockdown_level),
            "bold green3",
            0.012,
        )

    def _lockdown_fail(self) -> None:
        self._stop_lockdown_timer()
        self.lockdown = None
        self.villain_said = random.choice(VILLAIN_LINES)
        self.mode = "dead"
        self.state.connection = "lost"
        self.refresh_status()
        self.narrative.narrate(i18n.t("app_lockdown_captured"), "bold red", 0.02)
        self.narrative.narrate(
            i18n.t("app_lockdown_villain_says", line=self.villain_said),
            "bold yellow",
            0.03,
        )
        self.narrative.narrate(i18n.t("app_lockdown_static"), "red", 0.02)
        perdido = self.state.wallet
        setor = self.state.sector
        self.narrative.narrate(
            i18n.t(
                "app_lockdown_frozen", amount=perdido, coin=hardware.COIN, sector=setor
            ),
            "red",
            0.014,
        )
        self.narrative.narrate(i18n.t("app_lockdown_reboot_hint"), "yellow", 0.010)

    def reset_lockdown(self) -> None:
        """Zera o escalonamento do cerco.

        Chamado pelo scrambler (o item que embaralha o sinal) e por
        `_new_incursion` — o cerco é da run, não seu.
        """
        self.state.lockdown_level = 0

    # ------------------------------------------------------------------ #
    # Fim de jogo
    # ------------------------------------------------------------------ #
    def _win(self) -> None:
        """Setor limpo. Não é o fim do jogo — é o fim de UM setor."""
        st = self.state
        premio = round(sector_payout(st.sector) * st.mod_payout * self.settings.diff().payout_mult, 2)
        st.wallet = round(st.wallet + premio, 2)
        boss_name = make_boss(st.sector).name.split(" —")[0]
        self.narrative.narrate(
            i18n.t("app_win_core", boss_name=boss_name), "bold green3", 0.016
        )
        self.narrative.narrate(
            i18n.t(
                "app_win_cleared",
                sector=st.sector,
                amount=premio,
                coin=hardware.COIN,
                balance=st.wallet,
            ),
            "bold yellow",
            0.012,
        )
        # Avança o setor e volta para a mesa: gastar, montar, decidir descer.
        self.state = next_run(st, won=True)
        self.reset_lockdown()
        self.combat = None
        self.cipher = None
        self.go_desk("clear")


def run() -> None:
    ColdBootApp().run()
