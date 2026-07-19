"""Motor do jogo pro front-end web — mesma lógica de `app.py` (do_hack, do_cd,
do_cat, do_scan, combate, LOCKDOWN, vitória/derrota de setor, itens, minerador
local, loja/hardware), sem NENHUMA dependência de Textual. Onda 1 (ver plano):
rede + filesystem + ICE + LOCKDOWN + vitória/derrota + save + itens
(take/drop/use/run/kill) + mineração local de CRN + loja/hardware (rig sobe
de verdade). Botnet remoto/cifra/puzzle/tutorial/idioma ficam pra depois — a
dificuldade nunca é escolhida (sempre "normal").

`WebSession` é o equivalente do que `ColdBootApp` guarda em `self.mode`/
`self.combat`/`self.lockdown` — só que aqui vira um objeto plano que o
servidor (`web/server.py`) pode manter em memória por conexão e persistir via
`savegame.py` sem tocar em Textual.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import economy, hardware, i18n
from .combat import CombatSession, effective_depth, make_boss, make_ice
from .economy import creep_mult, is_overheated, mining_noise, tick_economy, typing_bonus
from .lockdown import LockdownSession
from .procgen.filesystem import default_cwd
from .state import FSNode, GameState
from .world import ACHIEVEMENTS, VILLAIN_LINES, next_run, sector_payout, unlock_achievements


def _log(msgs: list[dict], text: str, kind: str = "info") -> None:
    msgs.append({"text": text, "kind": kind})


@dataclass
class WebSession:
    state: GameState
    mode: str = "explore"  # explore | combat | lockdown | dead
    combat: CombatSession | None = None
    lockdown: LockdownSession | None = None
    villain_said: str | None = None
    cart: list[str] = field(default_factory=list)
    _combat_kind: str | None = field(default=None, repr=False)
    _combat_obj: object | None = field(default=None, repr=False)
    _creep_acc: float = field(default=0.0, repr=False)
    _economy_acc: float = field(default=0.0, repr=False)
    _warned_hot: bool = field(default=False, repr=False)

    # ------------------------------------------------------------------ #
    # Trace / LOCKDOWN
    # ------------------------------------------------------------------ #
    def _check_trace(self, msgs: list[dict]) -> bool:
        if self.state.trace < 100 or self.mode in ("lockdown", "dead"):
            return False
        self.combat = None
        self._enter_lockdown(msgs)
        return True

    def _enter_lockdown(self, msgs: list[dict]) -> None:
        self.mode = "lockdown"
        self.lockdown = LockdownSession(
            self.state.lockdown_level, typing_bonus(self.state), rng=self.state.rng
        )
        self.state.connection = "critical"
        _log(msgs, i18n.t("app_lockdown_enter"), "danger")

    def _lockdown_win(self, msgs: list[dict]) -> None:
        self.lockdown = None
        self.state.lockdown_level += 1
        self.state.trace = 55.0
        self.state.add_trace(0.0)
        self.mode = "explore"
        _log(msgs, i18n.t("app_lockdown_won", level=self.state.lockdown_level), "win")

    def _lockdown_fail(self, msgs: list[dict]) -> None:
        self.lockdown = None
        self.villain_said = random.choice(VILLAIN_LINES)
        self.mode = "dead"
        self.state.connection = "lost"
        _log(msgs, i18n.t("app_lockdown_captured"), "danger")
        _log(
            msgs,
            i18n.t("app_lockdown_villain_says", line=self.villain_said),
            "danger",
        )

    # ------------------------------------------------------------------ #
    # Combate
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

    def do_hack(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        if not target:
            _log(msgs, i18n.t("app_hack_no_target"), "error")
            return
        kind, obj = self._resolve_hack(target)
        if kind is None:
            _log(msgs, i18n.t("app_hack_not_found", target=target), "warn")
            return
        if kind == "net":
            name, depth = obj.label, obj.depth
        else:
            name = obj.name
            here = self.state.net.get(self.state.location)
            depth = here.depth if here else 0
        bonus = typing_bonus(self.state)
        st = self.state
        if kind == "net" and obj.id == st.core_id:
            sess = make_boss(st.sector, rng=st.rng, time_bonus=bonus, pen_mult=st.mod_ice_penalty)
        else:
            sess = make_ice(
                name, effective_depth(depth, st.sector), rng=st.rng, time_bonus=bonus,
                pen_mult=st.mod_ice_penalty,
            )
        self.mode = "combat"
        self.combat = sess
        self._combat_kind, self._combat_obj = kind, obj
        sess.start()
        _log(
            msgs,
            i18n.t(
                "app_combat_ice_active", ice_type=sess.ice_type, name=sess.name,
                rounds=sess.total_rounds,
            ),
            "danger",
        )
        if sess.behavior == "memory":
            _log(msgs, i18n.t("app_combat_hint_memory"), "warn")
        elif sess.behavior == "hunt":
            _log(msgs, i18n.t("app_combat_hint_hunt"), "warn")
        elif sess.behavior == "phantom":
            _log(msgs, i18n.t("app_combat_hint_phantom"), "warn")

    def combat_submit(self, text: str, msgs: list[dict]) -> None:
        if self.mode != "combat" or self.combat is None:
            return
        self._apply_combat(self.combat.submit(text), msgs)

    def _apply_combat(self, res, msgs: list[dict]) -> None:
        if res.trace_delta:
            self.state.add_trace(res.trace_delta)
        if res.kind in ("won", "lost"):
            self._end_combat(res.kind == "won", res.message, msgs)
        else:
            _log(msgs, res.message, "hit" if res.kind == "hit" else "miss")
            self._check_trace(msgs)

    def _end_combat(self, success: bool, message: str, msgs: list[dict]) -> None:
        kind, obj = self._combat_kind, self._combat_obj
        self.mode = "explore"
        _log(msgs, message, "win" if success else "lose")
        if success and kind == "net":
            obj.state = "compromised"
            self.state.location = obj.id
            self.state.cwd = default_cwd(obj.fs) if obj.fs else []
            _log(msgs, i18n.t("app_combat_connected", label=obj.label), "info")
            if obj.id == self.state.core_id:
                self._win(msgs)
        elif success and kind == "fs":
            obj.locked = False
            _log(msgs, i18n.t("app_combat_fs_unlocked", name=obj.name), "info")
        self.combat = None
        self._combat_kind = self._combat_obj = None
        self._check_trace(msgs)

    def _win(self, msgs: list[dict]) -> None:
        st = self.state
        boss_name = make_boss(st.sector).name.split(" —")[0]
        premio = round(sector_payout(st.sector) * st.mod_payout, 2)
        st.wallet = round(st.wallet + premio, 2)
        _log(msgs, i18n.t("app_win_core", boss_name=boss_name), "win")
        _log(
            msgs,
            i18n.t(
                "app_win_cleared", sector=st.sector, amount=premio, coin="CRN",
                balance=st.wallet,
            ),
            "win",
        )
        self.state = next_run(st, won=True)
        self.state.total_earned = round(self.state.total_earned + premio, 2)
        for aid in unlock_achievements(self.state):
            _log(msgs, i18n.t("app_achievement_unlocked", name=i18n.t(f"ach_{aid}_name")), "win")

    # ------------------------------------------------------------------ #
    # LOCKDOWN — submissão
    # ------------------------------------------------------------------ #
    def lockdown_submit(self, text: str, msgs: list[dict]) -> None:
        if self.mode != "lockdown" or self.lockdown is None:
            return
        res = self.lockdown.submit(text)
        if res == "win":
            self._lockdown_win(msgs)
        elif res == "fail":
            self._lockdown_fail(msgs)
        else:
            _log(msgs, i18n.t("app_lockdown_countered"), "hit")

    # ------------------------------------------------------------------ #
    # Exploração
    # ------------------------------------------------------------------ #
    def do_cd(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        if not target:
            self.state.cwd = []
            return
        parts, node = self.state.resolve(target)
        if node is None or not node.is_dir:
            _log(msgs, i18n.t("app_cd_no_such_dir", target=target), "error")
            return
        if node.locked:
            _log(msgs, i18n.t("app_cd_denied", target=target, name=node.name), "warn")
            self.state.add_trace(1.5)
            self._check_trace(msgs)
            return
        self.state.cwd = parts

    def do_cat(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        if not target:
            _log(msgs, i18n.t("app_cat_missing_arg"), "error")
            return
        parts, node = self.state.resolve(target)
        if node is None:
            _log(msgs, i18n.t("app_cat_no_such_file", target=target), "error")
            return
        if node.is_dir:
            _log(msgs, i18n.t("app_cat_is_dir", target=target), "error")
            return
        if node.locked:
            _log(msgs, i18n.t("app_cat_encrypted", target=target, name=node.name), "warn")
            return
        _log(msgs, node.content or i18n.t("app_cat_empty_file"), "file")
        if node.on_read == "unlock_scan" and not self.state.flags.get("scan_unlocked"):
            self.state.flags["scan_unlocked"] = True
            _log(msgs, i18n.t("app_fs_unlock_scan"), "info")
        elif node.on_read == "poke_daemon":
            self.state.add_trace(12.0)
            _log(msgs, i18n.t("app_fs_poke_daemon"), "danger")
        elif node.on_read == "read_auth":
            self.state.flags["read_auth"] = True
            _log(msgs, i18n.t("app_fs_read_auth"), "info")
        self._check_trace(msgs)

    def do_look(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        if not target:
            _log(
                msgs,
                i18n.t(
                    "app_look_terminal", location=self.state.location,
                    trace=self.state.trace,
                ),
                "info",
            )
            return
        parts, node = self.state.resolve(target)
        if node is None:
            _log(msgs, i18n.t("app_look_nothing", target=target), "warn")
        elif node.is_dir:
            _log(msgs, i18n.t("app_look_is_dir", name=node.name), "info")
        else:
            _log(msgs, i18n.t("app_look_is_file", name=node.name), "info")

    def do_scan(self, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        if not self.state.flags.get("scan_unlocked"):
            _log(msgs, i18n.t("app_scan_locked"), "warn")
            return
        revealed = self.state.reveal_neighbors(self.state.location)
        if revealed:
            _log(msgs, i18n.t("app_scan_found", hosts=", ".join(revealed)), "info")
        else:
            _log(msgs, i18n.t("app_scan_none"), "warn")
        self.state.add_trace(2.0)
        self._check_trace(msgs)

    # ------------------------------------------------------------------ #
    # Itens (take/drop/use) e programas (run/kill) — mesma lógica de
    # app.py:do_take/do_drop/do_use/do_run/do_kill, só trocando
    # `self.narrative.narrate` por `_log(msgs, ...)`.
    # ------------------------------------------------------------------ #
    def do_take(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        alvo = target or ""
        node = self.state.cwd_node().children.get(alvo)
        if node is None or not node.item:
            _log(msgs, i18n.t("app_take_not_item", target=alvo), "warn")
            return
        if node.item.get("kind") == "reader":
            _log(msgs, i18n.t("app_take_reader_bolted"), "warn")
            return
        if not self.state.can_hold():
            _log(
                msgs,
                i18n.t(
                    "app_take_buffer_full", free=self.state.ram_free,
                    item_kb=hardware.ITEM_KB,
                ),
                "error",
            )
            return
        item = dict(node.item)
        item["name"] = node.name
        self.state.inventory.append(item)
        self.state.cwd_node().children.pop(node.name, None)
        _log(
            msgs,
            i18n.t(
                "app_take_loaded", name=node.name, item_kb=hardware.ITEM_KB,
                free=self.state.ram_free,
            ),
            "info",
        )

    def do_drop(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        it = self.state.find_item(target or "")
        if it is None:
            _log(msgs, i18n.t("app_drop_not_in_buffer", target=target), "warn")
            return
        self.state.inventory.remove(it)
        data = {k: v for k, v in it.items() if k != "name"}
        self.state.cwd_node().add(
            FSNode(
                it["name"], False, item=data,
                content=i18n.t("app_drop_content", kind=it["kind"]),
            )
        )
        _log(msgs, i18n.t("app_drop_done", name=it["name"], free=self.state.ram_free), "info")

    def do_use(self, args: list[str], msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        nome = args[0] if args else ""
        alvo = args[-1] if len(args) > 1 else None
        carregado = self.state.find_item(nome)
        if carregado is not None:
            self._use_carried(carregado, alvo, msgs)
            return
        node = self.state.cwd_node().children.get(nome)
        if node and node.item:
            self._use_item(node, msgs)
            return
        _log(msgs, i18n.t("app_use_not_found", name=nome), "warn")

    def _use_carried(self, item: dict, alvo: str | None, msgs: list[dict]) -> None:
        if item.get("kind") == "keycard":
            if self._swipe_card(item, alvo, msgs):
                self.state.inventory.remove(item)
            return
        if item.get("kind") == "backdoor":
            if self._use_backdoor(alvo, msgs):
                self.state.inventory.remove(item)
            return
        fake = FSNode(item["name"], False, item=item)
        if self._apply_item(fake, msgs):
            self.state.inventory.remove(item)

    def _use_backdoor(self, alvo: str | None, msgs: list[dict]) -> bool:
        if not alvo:
            _log(msgs, i18n.t("app_backdoor_missing_target"), "error")
            return False
        kind, obj = self._resolve_hack(alvo)
        if kind is None:
            _log(msgs, i18n.t("app_backdoor_not_found", target=alvo), "warn")
            return False
        if kind == "net" and obj.id == self.state.core_id:
            _log(msgs, i18n.t("app_backdoor_no_boss"), "warn")
            return False
        if kind == "net":
            obj.state = "compromised"
            self.state.location = obj.id
            self.state.cwd = default_cwd(obj.fs) if obj.fs else []
            _log(msgs, i18n.t("app_backdoor_net_done", label=obj.label), "win")
        else:
            obj.locked = False
            _log(msgs, i18n.t("app_backdoor_fs_done", name=obj.name), "win")
        return True

    def _swipe_card(self, item: dict, alvo: str | None, msgs: list[dict]) -> bool:
        aqui = self.state.cwd_node()
        leitores = [
            c for c in aqui.children.values() if c.item and c.item.get("kind") == "reader"
        ]
        if alvo:
            leitores = [c for c in leitores if c.name == alvo] or leitores
        if not leitores:
            _log(msgs, i18n.t("app_swipe_no_reader"), "warn")
            return False
        leitor = leitores[0]
        cofre = aqui.children.get(leitor.item.get("opens", ""))
        if cofre is None or not cofre.locked:
            _log(msgs, i18n.t("app_swipe_nothing_locked"), "warn")
            return False
        cofre.locked = False
        _log(msgs, i18n.t("app_swipe_success", code=item.get("code", "?"), name=cofre.name), "win")
        return True

    def _use_item(self, node: FSNode, msgs: list[dict]) -> None:
        if self._apply_item(node, msgs):
            self.state.cwd_node().children.pop(node.name, None)

    def _apply_item(self, node: FSNode, msgs: list[dict]) -> bool:
        """Efeito do item. Devolve True se ele foi consumido."""
        it = node.item
        kind = it.get("kind")
        consumed = True

        if kind in ("wallet", "credits"):
            self.state.wallet = round(self.state.wallet + it["amount"], 3)
            _log(
                msgs,
                i18n.t("app_item_credited", amount=it["amount"], coin=hardware.COIN, balance=self.state.wallet),
                "win",
            )
        elif kind == "adminkey":
            self.state.adminkey += it["charges"]
            _log(msgs, i18n.t("app_item_adminkey", charges=it["charges"]), "info")
        elif kind == "coolant":
            self.state.heat = max(hardware.AMBIENT, self.state.heat - it["amount"])
            _log(msgs, i18n.t("app_item_coolant", amount=it["amount"]), "info")
        elif kind == "scrambler":
            self.state.trace = max(0.0, self.state.trace - it["amount"])
            self.state.add_trace(0.0)
            _log(msgs, i18n.t("app_item_scrambler", amount=it["amount"]), "info")
        elif kind == "miner":
            _log(msgs, i18n.t("app_item_is_miner", name=node.name), "warn")
            consumed = False
        elif kind == "spoof":
            _log(msgs, i18n.t("app_item_is_spoof", name=node.name), "warn")
            consumed = False
        elif kind == "reader":
            _log(msgs, i18n.t("app_item_reader_idle"), "warn")
            consumed = False
        elif kind == "keycard":
            _log(msgs, i18n.t("app_item_keycard_needs_take", name=node.name), "warn")
            consumed = False
        elif kind == "backdoor":
            _log(msgs, i18n.t("app_item_backdoor_needs_take", name=node.name), "warn")
            consumed = False
        else:
            _log(msgs, i18n.t("app_item_nothing"), "warn")
            consumed = False

        return consumed

    def do_run(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        prog = target or ""
        if prog.lower() in ("scan", "nmap"):
            self.do_scan(msgs)
            return
        node = self.state.cwd_node().children.get(prog)
        item = node.item if (node and node.item) else self.state.find_item(prog)
        st = self.state
        if item and item.get("kind") == "miner":
            if "miner" in st.processes:
                _log(msgs, i18n.t("app_run_already_running"), "warn")
                return
            kb = hardware.miner_footprint(st.rig)
            if kb > st.ram_free:
                _log(msgs, i18n.t("app_run_no_ram", prog=prog, kb=kb, free=st.ram_free), "error")
                return
            st.processes.append("miner")
            d = hardware.derived(st.rig)
            _log(
                msgs,
                i18n.t("app_run_miner_started", hash=d.hashrate, kb=kb, noise=mining_noise(st)),
                "info",
            )
            return
        if item and item.get("kind") == "spoof":
            self.state.trace = max(0.0, self.state.trace - item["amount"])
            self.state.add_trace(0.0)
            _log(
                msgs,
                i18n.t("app_run_spoof_done", fake_user=item["fake_user"], amount=item["amount"]),
                "win",
            )
            if node is not None and node.item is item:
                self.state.cwd_node().children.pop(node.name, None)
            else:
                self.state.inventory.remove(item)
            return
        _log(msgs, i18n.t("app_run_not_found", prog=prog), "error")

    def do_kill(self, target: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        proc = (target or "").lower()
        if not proc:
            _log(msgs, i18n.t("app_kill_missing_arg"), "error")
            return
        if proc not in self.state.processes:
            _log(msgs, i18n.t("app_kill_not_found", proc=proc), "error")
            return
        self.state.processes.remove(proc)
        _log(msgs, i18n.t("app_kill_done", proc=proc), "info")

    # ------------------------------------------------------------------ #
    # Loja / hardware — mesma lógica de economy.py (preview_cart/checkout/buy)
    # e screens.py:ShopScreen, só sem a UI de carrinho do Textual.
    # ------------------------------------------------------------------ #
    def do_buy(self, part_id: str | None, msgs: list[dict]) -> None:
        """Compra direta de uma peça, sem carrinho — `buy <id>` no terminal."""
        if self.mode != "explore":
            return
        ok, message, warnings = economy.buy(self.state, part_id or "")
        _log(msgs, message, "win" if ok else "error")
        for w in warnings:
            _log(msgs, w, "warn")

    def shop_add(self, part_id: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        if not part_id or part_id not in hardware.CATALOG:
            _log(msgs, i18n.t("eco_item_not_found"), "warn")
            return
        self.cart.append(part_id)

    def shop_remove(self, part_id: str | None, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        if part_id and part_id in self.cart:
            self.cart.remove(part_id)
        elif self.cart:
            self.cart.pop()

    def shop_checkout(self, msgs: list[dict]) -> None:
        if self.mode != "explore":
            return
        ok, out = economy.checkout(self.state, self.cart)
        if ok:
            self.cart = []
        for m in out:
            _log(msgs, m, "win" if ok else "error")

    def do_reboot(self, msgs: list[dict]) -> None:
        if self.mode != "dead":
            return
        self.state = next_run(self.state, won=False)
        for aid in unlock_achievements(self.state):
            _log(msgs, i18n.t("app_achievement_unlocked", name=i18n.t(f"ach_{aid}_name")), "win")
        self.state.lockdown_level = 0
        self.combat = None
        self.lockdown = None
        self.villain_said = None
        self.mode = "explore"

    # ------------------------------------------------------------------ #
    # Tick — chamado pelo servidor a cada 0.1s
    # ------------------------------------------------------------------ #
    def tick(self, dt: float) -> list[dict]:
        msgs: list[dict] = []
        if self.mode == "combat" and self.combat is not None:
            res = self.combat.tick(dt)
            if res is not None:
                self._apply_combat(res, msgs)
        elif self.mode == "lockdown" and self.lockdown is not None:
            if self.lockdown.tick(dt) == "fail":
                self._lockdown_fail(msgs)
        elif self.mode == "explore":
            # mesma cadência de app._trace_creep (a cada 4s, fora de combate)
            self._creep_acc += dt
            while self._creep_acc >= 4.0:
                self._creep_acc -= 4.0
                self.state.add_trace(0.4 * creep_mult(self.state))
                if self._check_trace(msgs):
                    break

        # Economia (mineração/calor) roda o tempo todo, igual app._economy_tick
        # (2s de cadência) — inclusive durante combate/LOCKDOWN, porque minerar
        # é um processo de fundo do rig, não do minigame.
        if self.mode != "dead":
            self._economy_acc += dt
            while self._economy_acc >= 2.0:
                self._economy_acc -= 2.0
                info = tick_economy(self.state, 1.0)
                if info.overheated and not self._warned_hot:
                    self._warned_hot = True
                    _log(msgs, i18n.t("app_overheat_warning"), "danger")
                elif not info.overheated and self._warned_hot:
                    self._warned_hot = False
                    _log(msgs, i18n.t("app_overheat_normal"), "win")
        return msgs


# --------------------------------------------------------------------------- #
# Snapshot — o que o front-end recebe a cada atualização
# --------------------------------------------------------------------------- #
def _net_snapshot(session: WebSession) -> list[dict]:
    out = []
    for n in session.state.net.values():
        fog = n.state == "fog"
        out.append({
            "id": n.id,
            "label": None if fog else n.label,
            "col": n.col,
            "row": n.row,
            "links": list(n.links),
            "state": n.state,
            "here": n.id == session.state.location,
        })
    return out


def _fs_listing(session: WebSession) -> list[dict]:
    node = session.state.cwd_node()
    return [
        {
            "name": c.name, "is_dir": c.is_dir, "locked": c.locked,
            "item": c.item.get("kind") if c.item else None,
        }
        for c in node.children.values()
    ]


def _combat_snapshot(session: WebSession) -> dict | None:
    c = session.combat
    if c is None:
        return None
    return {
        "ice_type": c.ice_type,
        "name": c.name,
        "round": c.round,
        "total_rounds": c.total_rounds,
        "time_left": round(c.time_left, 1),
        "round_time": round(c.round_time, 1),
        "code_display": c.display_code(),
        "code_visible": c.code_visible,
    }


def _lockdown_snapshot(session: WebSession) -> dict | None:
    ld = session.lockdown
    if ld is None:
        return None
    return {
        "round": ld.round,
        "total": ld.total,
        "time_left": round(ld.time_left, 1),
        "time_limit": round(ld.time_limit, 1),
        "code": ld.code,
    }


def _shop_snapshot(session: WebSession) -> dict:
    """Vitrine + carrinho, igual a screens.py:ShopScreen — simula o carrinho
    em cima de uma CÓPIA do rig pra mostrar o status real (instalável ou não,
    já contando o que está na cesta), sem tocar no rig de verdade."""
    state = session.state
    preview_rig = state.rig.copy()
    for pid in session.cart:
        part = hardware.CATALOG.get(pid)
        if part and hardware.can_install(preview_rig, part)[0]:
            hardware.install(preview_rig, part)

    parts = []
    for p in hardware.CATALOG.values():
        if hardware.is_installed(preview_rig, p):
            status = "installed"
        else:
            ok, reason = hardware.can_install(preview_rig, p)
            status = "available" if ok else reason
        parts.append({"id": p.id, "kind": p.kind, "name": p.name, "price": p.price, "status": status})

    pv = economy.preview_cart(state, session.cart)
    cart_lines = [
        {
            "part_id": l.part_id,
            "name": hardware.CATALOG[l.part_id].name if l.part_id in hardware.CATALOG else l.part_id,
            "ok": l.ok,
            "reason": l.reason,
        }
        for l in pv.lines
    ]

    d = hardware.derived(state.rig)
    return {
        "parts": parts,
        "cart": cart_lines,
        "cart_total": pv.total,
        "affordable": pv.affordable,
        "rig": {
            "mobo": state.rig.mobo, "cpu": state.rig.cpu, "ram": list(state.rig.ram),
            "gpus": list(state.rig.gpus), "psu": state.rig.psu, "cooler": state.rig.cooler,
            "router": state.rig.router,
        },
        "derived": {
            "hashrate": d.hashrate, "ram_gb": d.ram_gb, "power_load": d.power_load,
            "max_power": d.max_power, "cooling": d.cooling, "typing_bonus": d.typing_bonus,
            "signal": d.signal, "cores": d.cores,
        },
    }


def snapshot(session: WebSession) -> dict:
    st = session.state
    return {
        "mode": session.mode,
        "sector": st.sector,
        "best_sector": st.best_sector,
        "trace": round(st.trace, 1),
        "connection": st.connection,
        "wallet": st.wallet,
        "location": st.location,
        "cwd": st.cwd_str(),
        "listing": _fs_listing(session),
        "net": _net_snapshot(session),
        "combat": _combat_snapshot(session),
        "lockdown": _lockdown_snapshot(session),
        "villain_said": session.villain_said if session.mode == "dead" else None,
        "run_number": st.run_number,
        "runs_won": st.runs_won,
        "total_earned": st.total_earned,
        "deaths": st.deaths,
        "achievements": len(st.achievements),
        "achievements_total": len(ACHIEVEMENTS),
        "inventory": [
            {"name": it["name"], "kind": it.get("kind")} for it in st.inventory
        ],
        "processes": list(st.processes),
        "adminkey": st.adminkey,
        "heat": round(st.heat, 1),
        "overheated": is_overheated(st),
        "ram_free": st.ram_free,
        "ram_total": st.ram_total,
        "shop": _shop_snapshot(session),
        "hashrate": hardware.derived(st.rig).hashrate,
    }
