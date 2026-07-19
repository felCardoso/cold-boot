"""Telas de tela cheia: o boot do OS e o menu de pausa.

Ambas são Screens do Textual empilhadas por cima do jogo. O menu de pausa é
modal: enquanto está no topo, o app segura os timers (Trace, economia, combate),
então pausar realmente congela o cerco em vez de só esconder a tela.
"""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Static

from . import economy, hardware, i18n, theme
from .settings import Settings

# O OS fictício desta VAX. "kryos" (κρύος) = frio, gelado — o mesmo frio do
# daemon COLD-BOOT que dorme na rede.
OS_NAME = "KRYOS/OS"
OS_VERSION = "v4.2"

_LOGO = """
 ██╗  ██╗██████╗ ██╗   ██╗ ██████╗ ███████╗
 ██║ ██╔╝██╔══██╗╚██╗ ██╔╝██╔═══██╗██╔════╝
 █████╔╝ ██████╔╝ ╚████╔╝ ██║   ██║███████╗
 ██╔═██╗ ██╔══██╗  ╚██╔╝  ██║   ██║╚════██║
 ██║  ██╗██║  ██║   ██║   ╚██████╔╝███████║
 ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚══════╝
"""

# (chave_i18n ou "", segundos até a próxima linha). O POST de uma máquina de 1988:
# devagar, barulhento e orgulhoso de si mesmo. Chaves vazias ("") mantêm linhas em branco.
_POST = [
    (f"{OS_NAME} {OS_VERSION}  ·  (c) 1988 Zeta Dynamics Corp.", 0.35),
    ("", 0.05),
    ("VAX-11/785  ·  microcode rev 7.1", 0.30),
    ("boot_post_1", 0.45),
    ("boot_post_2", 0.25),
    ("boot_post_3", 0.55),
    ("boot_post_4", 0.30),
    ("boot_post_5", 0.35),
    ("", 0.10),
    ("boot_post_6", 0.30),
    ("boot_post_7", 0.25),
    ("boot_post_8", 0.60),
    ("", 0.15),
]

_LOGIN = [
    ("boot_login_1", 0.55),
    ("boot_login_2", 0.10),
    ("boot_login_3", 0.70),
    ("", 0.10),
    ("boot_login_4", 0.40),
    ("boot_login_5", 0.60),
]


class BootScreen(Screen):
    """Sequência de boot do KRYOS/OS. Qualquer tecla pula.

    Esc não é tratado aqui: o binding do app tem prioridade e chama `skip`.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self._done = False

    def compose(self) -> ComposeResult:
        with Vertical(id="boot-box"):
            yield Static(id="boot-logo")
            yield Static(id="boot-post")
            yield Static(id="boot-bar")
            yield Static(f"[{i18n.t('boot_hint_skip')}]", id="boot-hint")

    def on_mount(self) -> None:
        if self.settings.high_contrast:
            self.add_class(theme.CSS_CLASS)
        self.query_one("#boot-logo", Static).update(
            Text(_LOGO, style=theme.resolve("bold cyan", self.settings.high_contrast))
        )
        self.run_worker(self._play(), name="boot")

    # -- animação -------------------------------------------------------- #
    async def _play(self) -> None:
        hc = self.settings.high_contrast
        post = self.query_one("#boot-post", Static)
        bar = self.query_one("#boot-bar", Static)
        lines: list[str] = []

        for key, wait in _POST:
            text = i18n.t(key) if key else ""
            lines.append(text)
            post.update(Text("\n".join(lines), style=theme.resolve("green3", hc)))
            await asyncio.sleep(wait)

        # Barra de carga: o disco RA81 acordando.
        width = 34
        for i in range(width + 1):
            filled = "█" * i + "░" * (width - i)
            pct = int(i / width * 100)
            bar.update(
                Text.assemble(
                    (i18n.t("boot_loading_kernel"), theme.resolve("grey58", hc)),
                    (filled, theme.resolve("green3", hc)),
                    (f"  {pct:3d}%", theme.resolve("yellow", hc)),
                )
            )
            await asyncio.sleep(0.045)

        for key, wait in _LOGIN:
            text = i18n.t(key) if key else ""
            lines.append(text)
            post.update(Text("\n".join(lines), style=theme.resolve("green3", hc)))
            await asyncio.sleep(wait)

        self._finish()

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        self.dismiss(None)

    def action_skip(self) -> None:
        self._finish()

    def on_key(self, event) -> None:
        event.stop()
        self._finish()

    def on_click(self) -> None:
        self._finish()


class PauseScreen(ModalScreen):
    """Menu de pausa (Esc). Enquanto está aberto, o jogo inteiro congela.

    Fechar com Esc é responsabilidade do app (o binding dele tem prioridade).
    """

    def __init__(self, settings: Settings, can_save: bool, has_save: bool) -> None:
        super().__init__()
        self.settings = settings
        self.can_save = can_save  # falso durante combate/lockdown
        self._has_save = has_save

    def compose(self) -> ComposeResult:
        with Vertical(id="pause-box"):
            yield Static(i18n.t("pause_title"), id="pause-title")
            yield Static(i18n.t("pause_subtitle"), id="pause-sub")
            yield Button(i18n.t("pause_btn_resume"), id="btn-resume", variant="success")
            yield Button(self._save_label(), id="btn-save")
            yield Button(i18n.t("pause_btn_load"), id="btn-load")
            yield Button(self._contrast_label(), id="btn-contrast")
            yield Button(self._diff_label(), id="btn-diff")
            yield Button(self._locale_label(), id="btn-locale")
            yield Static("", id="pause-hint")
            yield Button(i18n.t("pause_btn_quit"), id="btn-quit", variant="error")

    def on_mount(self) -> None:
        if self.settings.high_contrast:
            self.add_class(theme.CSS_CLASS)
        self.query_one("#btn-load", Button).disabled = not self._has_save
        self.query_one("#btn-save", Button).disabled = not self.can_save
        self._refresh_hint()
        self.query_one("#btn-resume", Button).focus()

    # -- rótulos --------------------------------------------------------- #
    def _save_label(self) -> str:
        if self.can_save:
            return i18n.t("pause_btn_save")
        else:
            return i18n.t("pause_btn_save_disabled")

    def _contrast_label(self) -> str:
        state = i18n.t(
            "pause_contrast_on" if self.settings.high_contrast else "pause_contrast_off"
        )
        return i18n.t("pause_contrast_label", state=state)

    def _diff_label(self) -> str:
        label = i18n.t(f"diff_{self.settings.diff().id}_label")
        return i18n.t("pause_diff_label", label=label)

    def _locale_label(self) -> str:
        locale_key = f"pause_locale_{self.settings.locale}"
        name = i18n.t(locale_key)
        return i18n.t("pause_locale_label", name=name)

    def _refresh_hint(self) -> None:
        hint = i18n.t(f"diff_{self.settings.diff().id}_hint")
        self.query_one("#pause-hint", Static).update(
            Text(hint, style=theme.resolve("grey58", self.settings.high_contrast))
        )

    def _notify_saved(self, msg: str, style: str = "green3") -> None:
        self.query_one("#pause-sub", Static).update(
            Text(msg, style=theme.resolve(style, self.settings.high_contrast))
        )

    # -- ações ----------------------------------------------------------- #
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-resume":
            self.dismiss(None)
        elif bid == "btn-save":
            path = self.app.save_game()
            msg = (
                i18n.t("pause_saved_at", path=path)
                if path
                else i18n.t("pause_save_failed")
            )
            self._notify_saved(msg, "green3" if path else "red")
            self.query_one("#btn-load", Button).disabled = False
        elif bid == "btn-load":
            self.dismiss("load")
        elif bid == "btn-contrast":
            self.settings.toggle_contrast()
            self.set_class(self.settings.high_contrast, theme.CSS_CLASS)
            event.button.label = self._contrast_label()
            self._refresh_hint()
            self.app.apply_settings()
        elif bid == "btn-diff":
            self.settings.cycle_difficulty()
            event.button.label = self._diff_label()
            self._refresh_hint()
            self.app.apply_settings()
        elif bid == "btn-locale":
            self.settings.cycle_locale()
            event.button.label = self._locale_label()
            self._refresh_hint()
            i18n.set_locale(self.settings.locale)
            self.app.apply_settings()
        elif bid == "btn-quit":
            self.dismiss("quit")


# --------------------------------------------------------------------------- #
# A MESA — o hub entre setores
# --------------------------------------------------------------------------- #
class DeskScreen(Screen):
    """Sua mesa: desconectado, sem Trace correndo, com o rig na sua frente.

    É o respiro do laço: aqui você vê o balanço do setor, gasta o que ganhou e
    decide quando descer de novo. Nada te caça enquanto esta tela está aberta.
    """

    def __init__(self, settings: Settings, state, reason: str = "clear") -> None:
        super().__init__()
        self.settings = settings
        self.state = state
        self.reason = reason  # clear | dead | start

    def compose(self) -> ComposeResult:
        with Vertical(id="desk-box"):
            yield Static(id="desk-title")
            yield Static(id="desk-sub")
            yield Static(id="desk-rig")
            yield Button(i18n.t("desk_btn_shop"), id="btn-shop", variant="warning")
            yield Button("Connect", id="btn-connect", variant="success")
            yield Button(i18n.t("desk_btn_save"), id="btn-desk-save")
            yield Static("", id="desk-msg")

    def on_mount(self) -> None:
        if self.settings.high_contrast:
            self.add_class(theme.CSS_CLASS)
        self.refresh_desk()
        self.query_one("#btn-connect", Button).focus()

    def refresh_desk(self) -> None:
        hc = self.settings.high_contrast
        st = self.state

        def s(style):
            return theme.resolve(style, hc)

        if self.reason == "dead":
            titulo = i18n.t("desk_title_dead")
            cor = "bold red"
            sub = i18n.t("desk_sub_dead", best=st.best_sector)
        elif self.reason == "clear":
            titulo = i18n.t("desk_title_clear", sector=st.sector - 1)
            cor = "bold green3"
            sub = i18n.t("desk_sub_clear", sector=st.sector, best=st.best_sector)
        else:
            titulo = i18n.t("desk_title_idle")
            cor = "bold cyan"
            sub = i18n.t("desk_sub_idle", sector=st.sector)

        self.query_one("#desk-title", Static).update(Text(titulo, s(cor)))
        self.query_one("#desk-sub", Static).update(Text(sub, s("green3")))

        d = hardware.derived(st.rig)
        C = hardware.CATALOG
        linhas = [
            f"  {C[st.rig.cpu].name}",
            f"  {d.ram_gb}GB {d.ddr} em {d.slots_used}/{d.slots_total} slots",
            f"  {len(st.rig.gpus)} GPU(s) · {d.hashrate:.0f}H",
            f"  {C[st.rig.router].name} (sinal {d.signal}/5)",
            f"  {C[st.rig.psu].name} · {C[st.rig.cooler].name}",
            "",
            f"  {i18n.t('desk_wallet_label')}{st.wallet:.2f} {hardware.COIN}",
        ]
        self.query_one("#desk-rig", Static).update(Text("\n".join(linhas), s("green3")))
        self.query_one("#btn-connect", Button).label = i18n.t(
            "desk_btn_connect", sector=st.sector
        )

    def msg(self, text: str, style: str = "green3") -> None:
        self.query_one("#desk-msg", Static).update(
            Text(text, theme.resolve(style, self.settings.high_contrast))
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-shop":
            self.app.push_screen(ShopScreen(self.settings, self.state), self._shopped)
        elif bid == "btn-connect":
            self.dismiss("connect")
        elif bid == "btn-desk-save":
            path = self.app.save_game()
            msg = (
                i18n.t("pause_saved_at", path=path)
                if path
                else i18n.t("pause_save_failed")
            )
            self.msg(msg, "green3" if path else "red")

    def _shopped(self, _result=None) -> None:
        self.refresh_desk()
        self.app.refresh_status()
        self.app.refresh_rig()


# --------------------------------------------------------------------------- #
# A LOJA — pop-up com carrinho e checkout
# --------------------------------------------------------------------------- #
def _categorias() -> list[tuple[str, str]]:
    """Constrói a lista de categorias com rótulos traduzidos."""
    return [
        ("cpu", i18n.t("shop_cat_cpu")),
        ("mobo", i18n.t("shop_cat_mobo")),
        ("ram", i18n.t("shop_cat_ram")),
        ("gpu", i18n.t("shop_cat_gpu")),
        ("psu", i18n.t("shop_cat_psu")),
        ("cooler", i18n.t("shop_cat_cooler")),
        ("router", i18n.t("shop_cat_router")),
    ]


class ShopScreen(ModalScreen):
    """Vitrine + carrinho + checkout, como uma loja online de 1988.

    O carrinho é validado como um todo antes de cobrar: comprar a placa nova e
    a RAM dela na mesma cesta tem que funcionar, e a ordem importa.
    """

    def __init__(self, settings: Settings, state) -> None:
        super().__init__()
        self.settings = settings
        self.state = state
        self.cat = "cpu"
        self.cart: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="shop-box"):
            yield Static(id="shop-title")
            with Horizontal(id="shop-cats"):
                for cid, label in _categorias():
                    yield Button(label, id=f"cat-{cid}", classes="cat-btn")
            with Horizontal(id="shop-body"):
                yield DataTable(id="shop-table", cursor_type="row")
                with Vertical(id="shop-cart"):
                    yield Static(i18n.t("shop_cart_title"), id="cart-title")
                    yield Static("", id="cart-list")
                    yield Static("", id="cart-total")
            with Horizontal(id="shop-actions"):
                yield Button(i18n.t("shop_btn_add"), id="btn-add", variant="success")
                yield Button(i18n.t("shop_btn_remove"), id="btn-remove")
                yield Button(
                    i18n.t("shop_btn_checkout"), id="btn-checkout", variant="warning"
                )
                yield Button(i18n.t("shop_btn_close"), id="btn-close", variant="error")
            yield Static("", id="shop-msg")

    def on_mount(self) -> None:
        if self.settings.high_contrast:
            self.add_class(theme.CSS_CLASS)
        table = self.query_one("#shop-table", DataTable)
        table.add_columns(
            "id",
            i18n.t("shop_col_part"),
            i18n.t("shop_col_price"),
            i18n.t("shop_col_status"),
        )
        self._fill_table()
        self._refresh_cart()
        self.query_one("#shop-title", Static).update(
            Text(
                i18n.t("shop_title"),
                theme.resolve("bold cyan", self.settings.high_contrast),
            )
        )
        table.focus()

    # -- vitrine --------------------------------------------------------- #
    def _fill_table(self) -> None:
        """A vitrine mostra a situação de cada peça *já contando o carrinho*."""
        table = self.query_one("#shop-table", DataTable)
        table.clear()
        pv_rig = self.state.rig.copy()
        for pid in self.cart:
            part = hardware.CATALOG.get(pid)
            if part and hardware.can_install(pv_rig, part)[0]:
                hardware.install(pv_rig, part)
        for p in hardware.parts_of(self.cat):
            if hardware.is_installed(pv_rig, p):
                nota = i18n.t("shop_status_installed")
            else:
                ok, reason = hardware.can_install(pv_rig, p)
                nota = i18n.t("shop_status_available") if ok else reason
            table.add_row(p.id, p.name, f"{p.price:.0f}", nota, key=p.id)

    def _selected(self) -> str | None:
        table = self.query_one("#shop-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        except Exception:
            return None
        return row.value

    def _refresh_cart(self) -> None:
        hc = self.settings.high_contrast
        pv = economy.preview_cart(self.state, self.cart)
        if not self.cart:
            self.query_one("#cart-list", Static).update(
                Text(i18n.t("shop_cart_empty"), theme.resolve("grey58", hc))
            )
        else:
            linhas = []
            for line in pv.lines:
                part = hardware.CATALOG.get(line.part_id)
                nome = part.name if part else line.part_id
                marca = " " if line.ok else "!"
                linhas.append(
                    f" {marca} {nome[:26]:<26} {part.price if part else 0:>4.0f}"
                )
            self.query_one("#cart-list", Static).update(
                Text("\n".join(linhas), theme.resolve("green3", hc))
            )
        estilo = "bold yellow" if pv.affordable else "bold red"
        self.query_one("#cart-total", Static).update(
            Text.assemble(
                (i18n.t("shop_cart_total_label"), theme.resolve("grey58", hc)),
                (f"{pv.total:.0f} {hardware.COIN}", theme.resolve(estilo, hc)),
                (
                    i18n.t("shop_cart_balance_label") + f"{self.state.wallet:.2f}",
                    theme.resolve("grey58", hc),
                ),
            )
        )

    def msg(self, text: str, style: str = "green3") -> None:
        self.query_one("#shop-msg", Static).update(
            Text(text, theme.resolve(style, self.settings.high_contrast))
        )

    # -- ações ----------------------------------------------------------- #
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("cat-"):
            self.cat = bid[4:]
            self._fill_table()
            self.msg("")
            return
        if bid == "btn-add":
            self._add()
        elif bid == "btn-remove":
            self._remove()
        elif bid == "btn-checkout":
            self._checkout()
        elif bid == "btn-close":
            self.dismiss(None)

    def _add(self) -> None:
        pid = self._selected()
        if pid is None:
            return
        self.cart.append(pid)
        pv = economy.preview_cart(self.state, self.cart)
        ruim = next((l for l in pv.lines if l.part_id == pid and not l.ok), None)
        if ruim is not None:
            self.msg(i18n.t("shop_msg_cart_wont_install", reason=ruim.reason), "yellow")
        else:
            self.msg(
                i18n.t("shop_msg_added_to_cart", name=hardware.CATALOG[pid].name),
                "green3",
            )
        self._fill_table()
        self._refresh_cart()

    def _remove(self) -> None:
        pid = self._selected()
        if pid is not None and pid in self.cart:
            self.cart.remove(pid)
            self.msg(
                i18n.t("shop_msg_removed", name=hardware.CATALOG[pid].name), "grey58"
            )
        elif self.cart:
            removido = self.cart.pop()
            self.msg(
                i18n.t("shop_msg_removed", name=hardware.CATALOG[removido].name),
                "grey58",
            )
        self._fill_table()
        self._refresh_cart()

    def _checkout(self) -> None:
        ok, msgs = economy.checkout(self.state, self.cart)
        if not ok:
            self.msg(msgs[0], "red")
            return
        self.cart.clear()
        self.app.after_purchase()
        self.msg(" · ".join(msgs)[:90], "bold green3")
        self._fill_table()
        self._refresh_cart()
