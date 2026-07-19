"""UI Manager — renderização dos painéis e o widget de narrativa com teletype.

As funções `render_status` / `render_map` são puras (State -> renderável Rich),
então o app só precisa chamá-las de novo quando o estado muda. O `NarrativeView`
encapsula o efeito teletype assíncrono via uma fila + worker, garantindo que a
digitação de caracteres nunca bloqueie o input nem os logs.
"""

from __future__ import annotations

import asyncio
import random

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import RichLog, Static

from . import economy, hardware, i18n, theme
from .state import GameState


# --------------------------------------------------------------------------- #
# Painel de status (Trace / RAM / Conexão)
# --------------------------------------------------------------------------- #
def _bar(pct: float, width: int = 18) -> tuple[str, str]:
    filled = int(round(pct / 100 * width))
    bar = "█" * filled + "░" * (width - filled)
    if pct >= 75:
        style = "bold red"
    elif pct >= 40:
        style = "bold yellow"
    else:
        style = "bold green3"
    return bar, style


def _heatbar(temp: float, width: int = 14) -> tuple[str, str]:
    frac = max(0.0, min(1.0, (temp - hardware.AMBIENT) / (hardware.TMAX + 20 - hardware.AMBIENT)))
    filled = int(round(frac * width))
    bar = "█" * filled + "░" * (width - filled)
    if temp >= hardware.TMAX:
        style = "bold red reverse"
    elif temp >= hardware.TMAX - 20:
        style = "bold yellow"
    else:
        style = "green3"
    return bar, style


def _meter(frac: float, width: int, style: str) -> tuple[str, str]:
    """Barra genérica 0..1. Um só lugar decide como uma barra é desenhada."""
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled), style


def _load_style(pct: int) -> str:
    if pct >= 90:
        return "bold red"
    if pct >= 60:
        return "bold yellow"
    return "green3"


def render_status(state: GameState, hc: bool = False) -> Text:
    """Painel STATUS / REDE — só medidores ao vivo. O que você *tem* fica no
    painel do RIG; aqui fica o que está *acontecendo*."""
    def s(style: str) -> str:
        return theme.resolve(style, hc)

    mining = "miner" in state.processes
    over = state.heat >= hardware.TMAX
    tel = hardware.telemetry(state.rig, mining, throttled=over)
    t = Text()

    # Trace: o medidor que mata.
    bar, style = _bar(state.trace, 18)
    t.append(i18n.t("hud_trace"), s("bold green3"))
    t.append(bar, s(style))
    t.append(f" {state.trace:5.1f}%", s(style))
    if mining:
        t.append(f"  +{economy.mining_noise(state):.2f}/t", s("bold red"))
    t.append("\n")

    # CPU / RAM do rig
    cbar, _ = _meter(tel.cpu_pct / 100, 10, "")
    t.append(i18n.t("hud_cpu"), s("bold green3"))
    t.append(cbar, s(_load_style(tel.cpu_pct)))
    t.append(f" {tel.cpu_pct:3d}%", s(_load_style(tel.cpu_pct)))
    t.append(i18n.t("hud_ram", used=tel.ram_used_gb, total=tel.ram_total_gb), s("green3"))

    # Uma linha por GPU instalada (a placa-mãe define quantas cabem).
    if tel.gpu_pct:
        for i, pct in enumerate(tel.gpu_pct):
            gbar, _ = _meter(pct / 100, 10, "")
            t.append(i18n.t("hud_gpu", index=i), s("bold green3"))
            t.append(gbar, s(_load_style(pct)))
            t.append(f" {pct:3d}%\n", s(_load_style(pct)))
    else:
        t.append(i18n.t("hud_gpu_none"), s("bold green3"))
        t.append(i18n.t("hud_gpu_none_msg"), s("grey58"))

    # PSU e sinal de internet
    pbar, _ = _meter(tel.psu_pct / 100, 8, "")
    t.append(i18n.t("hud_psu"), s("bold green3"))
    t.append(pbar, s(_load_style(tel.psu_pct)))
    t.append(f" {tel.watts}/{tel.watts_max}W\n", s(_load_style(tel.psu_pct)))

    sig_style = "green3" if tel.signal >= 4 else ("yellow" if tel.signal >= 2 else "bold red")
    t.append(i18n.t("hud_signal"), s("bold green3"))
    t.append("▮" * tel.signal + "▯" * (tel.signal_max - tel.signal), s(sig_style))
    t.append(f" {tel.signal}/{tel.signal_max}\n", s(sig_style))

    # Memória do HOST invadido: o que você deixa rodando lá é o que te entrega.
    frac = state.ram_free / max(1, state.ram_total)
    hbar, _ = _meter(frac, 10, "")
    ram_style = "bold red reverse" if state.ram_tight else ("yellow" if frac < 0.4 else "green3")
    t.append(i18n.t("hud_host"), s("bold green3"))
    t.append(hbar, s(ram_style))
    t.append(f" {state.ram_free}K/{state.ram_total}K\n", s(ram_style))

    conn_style = {
        "stable": "green3", "unstable": "yellow",
        "critical": "bold red", "lost": "bold red reverse",
    }.get(state.connection, "green3")
    t.append(i18n.t("hud_sector", sector=state.sector), s("bold yellow"))
    t.append(i18n.t(f"hud_conn_{state.connection}"), s(conn_style))
    t.append(f"  {state.location}  ", s("green3"))
    t.append(state.cwd_str(), s("yellow"))
    return t


def render_rig(state: GameState, hc: bool = False) -> Text:
    """Painel RIG — o que está montado na sua mesa, peça por peça."""
    def s(style: str) -> str:
        return theme.resolve(style, hc)

    rig = state.rig
    d = hardware.derived(rig)
    mining = "miner" in state.processes
    t = Text()

    t.append(hardware.CATALOG[rig.cpu].name + "\n", s("bold green3"))
    for stick in rig.ram:
        t.append("  " + hardware.CATALOG[stick].name + "\n", s("green3"))
    if d.slots_used < d.slots_total:
        t.append(i18n.t("hud_ram_slots_free", free=d.slots_total - d.slots_used), s("grey58"))
    for gid in rig.gpus:
        t.append("  " + hardware.CATALOG[gid].name + "\n", s("green3"))
    if d.pcie_total == 0:
        t.append(i18n.t("hud_pcie_none"), s("grey58"))
    elif d.pcie_used < d.pcie_total:
        t.append(i18n.t("hud_pcie_slots_free", free=d.pcie_total - d.pcie_used), s("grey58"))

    t.append(hardware.CATALOG[rig.router].name + "\n", s("green3"))
    t.append(hardware.CATALOG[rig.psu].name + "\n", s("green3"))
    t.append(hardware.CATALOG[rig.cooler].name + "\n", s("green3"))

    hb, hs = _heatbar(state.heat, 14)
    over = state.heat >= hardware.TMAX
    t.append(i18n.t("hud_temp"), s("bold green3"))
    t.append(hb, s(hs))
    throttle_msg = f"  {i18n.t('hud_throttle')}" if over else ""
    t.append(f" {state.heat:3.0f}C{throttle_msg}\n", s(hs))

    t.append(f"{d.hashrate:.0f}H", s("bold yellow" if mining else "grey58"))
    t.append(f"  {hardware.COIN} {state.wallet:.2f}", s("bold yellow"))
    return t


# --------------------------------------------------------------------------- #
# Mini-mapa ASCII da rede, com névoa de guerra
# --------------------------------------------------------------------------- #
_CW = 7   # largura de célula (cabe até col 4 no painel do mapa)
_CH = 2   # altura de célula


def render_map(state: GameState, hc: bool = False) -> Text:
    def s(style: str) -> str:
        return theme.resolve(style, hc)

    net = state.net
    if not net:
        return Text(i18n.t("hud_net_unmapped"), s("grey58"))

    cols = [n.col for n in net.values()]
    rows = [n.row for n in net.values()]
    width = max(cols) * _CW + 6
    height = max(rows) * _CH + 1
    chars = [[" "] * width for _ in range(height)]
    styles: list[list[str | None]] = [[None] * width for _ in range(height)]

    def put(x: int, y: int, s: str, style: str) -> None:
        for i, ch in enumerate(s):
            if 0 <= y < height and 0 <= x + i < width:
                chars[y][x + i] = ch
                styles[y][x + i] = style

    # Conexões primeiro (as caixas escrevem por cima).
    seen: set[tuple[str, str]] = set()
    for n in net.values():
        for lid in n.links:
            m = net.get(lid)
            if not m:
                continue
            key = tuple(sorted((n.id, m.id)))
            if key in seen:
                continue
            seen.add(key)
            known = n.state != "fog" and m.state != "fog"
            cstyle = s("green3" if known else "grey30")
            if n.row == m.row:
                y = n.row * _CH
                x1 = min(n.col, m.col) * _CW + 6
                x2 = max(n.col, m.col) * _CW
                for x in range(x1, x2):
                    put(x, y, "─", cstyle)
            elif n.col == m.col:
                x = n.col * _CW + 3
                y1 = min(n.row, m.row) * _CH + 1
                y2 = max(n.row, m.row) * _CH
                for y in range(y1, y2):
                    put(x, y, "│", cstyle)

    # Caixas dos nós.
    for n in net.values():
        if n.state == "fog":
            label, style = "????", "grey30"
        elif n.state == "compromised":
            label, style = n.label[:4].center(4), "bold green3"
        else:  # discovered
            label, style = n.label[:4].center(4), "bold yellow"
        if n.id == state.location:
            style = "bold black on green3"
        put(n.col * _CW, n.row * _CH, f"[{label}]", s(style))

    out = Text()
    for y in range(height):
        for x in range(width):
            out.append(chars[y][x], style=styles[y][x] or "")
        if y < height - 1:
            out.append("\n")
    return out


# System noise for real-time logging (does not interrupt input).
SYSLOG_NOISE = [
    "noise detected on port 80",
    "WEAK SIGNAL — recalibrating gain",
    "ICMP packet dropped from 10.0.0.1",
    "coldboot[441]: heartbeat",
    "teletype buffer released",
    "passive scan: 3 silent hosts detected",
    "DEC VT220 terminal echo ok",
    "sector checksum recalculated",
    "daemon watchdog restarted",
]


def random_syslog() -> str:
    return random.choice(SYSLOG_NOISE)


# --------------------------------------------------------------------------- #
# Painel central de narrativa com efeito TELETYPE assíncrono
# --------------------------------------------------------------------------- #
class NarrativeView(Vertical):
    """Log de narrativa + uma linha "em digitação" com efeito teletype.

    As mensagens entram numa fila e um único worker as digita uma a uma, então
    a ordem é preservada e nada bloqueia o event loop (input e logs seguem
    vivos enquanto os caracteres aparecem).
    """

    def compose(self):
        yield RichLog(id="narrative-log", wrap=True, markup=False, highlight=False)
        yield Static("", id="narrative-current")

    speed_mult: float = 1.0       # CPU melhor => texto mais rápido (setado pelo app)
    high_contrast: bool = False   # acessibilidade (setado pelo app)

    def on_mount(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        # Texto cru + estilo semântico do que já foi impresso. Guardado para
        # poder repintar a tela inteira quando o alto contraste liga/desliga:
        # trocar a paleta só do texto futuro deixaria o histórico ilegível.
        self._printed: list[tuple[str, str]] = []
        self.run_worker(self._consume(), name="teletype", group="teletype")

    # API pública ------------------------------------------------------- #
    def narrate(self, text: str, style: str = "green3", speed: float = 0.010) -> None:
        """Enfileira texto para aparecer com efeito teletype."""
        self._queue.put_nowait((text, style, speed))

    def echo(self, text: str, style: str = "grey58") -> None:
        """Escreve na hora (sem teletype) — usado para eco de comandos."""
        self._queue.put_nowait((text, style, 0.0))

    def clear_log(self) -> None:
        self._printed.clear()
        self.query_one("#narrative-log", RichLog).clear()
        self.query_one("#narrative-current", Static).update("")

    def restyle(self) -> None:
        """Repinta o que já está na tela com a paleta atual."""
        log = self.query_one("#narrative-log", RichLog)
        log.clear()
        for text, style in self._printed:
            log.write(Text(text, style=theme.resolve(style, self.high_contrast)))

    # Worker ------------------------------------------------------------ #
    async def _consume(self) -> None:
        log = self.query_one("#narrative-log", RichLog)
        cur = self.query_one("#narrative-current", Static)
        while True:
            text, style, speed = await self._queue.get()
            painted = theme.resolve(style, self.high_contrast)
            if speed > 0:
                eff = speed / max(0.3, self.speed_mult)   # CPU acelera o teletype
                buff = Text()
                for ch in text:
                    buff.append(ch, style=painted)
                    cur.update(buff)
                    await asyncio.sleep(eff)
                cur.update("")
            self._printed.append((text, style))
            log.write(Text(text, style=painted))
