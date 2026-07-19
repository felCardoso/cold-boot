"""Verificação automatizada (headless) do protótipo COLD-BOOT.

Cobre parser, State/mundo, geração PROCEDURAL de rede (determinismo +
invariantes), e o app dirigido via Pilot (comandos, combate, teletype).
Rode a partir da pasta cold-boot:   python smoke_test.py
"""

import asyncio
import collections
import random
import tempfile
from pathlib import Path

from coldboot import (
    economy,
    hardware,
    i18n,
    parser,
    puzzle,
    savegame,
    settings as settings_mod,
    theme,
)
from coldboot.app import ColdBootApp
from coldboot.combat import CombatSession, make_ice
from coldboot.lockdown import LockdownSession
from coldboot.procgen import filesystem as fsmod, loot
from coldboot.ui import render_map, render_rig, render_status
from coldboot.world import new_game, next_run, sector_payout


def ok(cond, label):
    print(("PASS" if cond else "FALHA") + " . " + label)
    if not cond:
        raise SystemExit(f"Falhou: {label}")


def net_signature(state):
    return tuple(
        (n.id, n.col, n.row, tuple(sorted(n.links)))
        for n in sorted(state.net.values(), key=lambda x: x.id)
    )


def reachable_from_gate(state):
    seen = {"GATE"}
    q = collections.deque(["GATE"])
    while q:
        cur = q.popleft()
        for lid in state.net[cur].links:
            if lid not in seen:
                seen.add(lid)
                q.append(lid)
    return seen


def test_units():
    # Parser
    ok(parser.parse("ls").verb == "ls", "parser: ls")
    ok(parser.parse("cd /var/log").target == "/var/log", "parser: cd alvo")
    c = parser.parse("ler readme.txt")
    ok(c.verb == "cat" and c.target == "readme.txt", "parser: natural 'ler' -> cat")
    c = parser.parse("usar cartao no leitor")
    ok(c.verb == "use" and "no" not in c.args, "parser: 'usar x no y' remove stopword")
    ok(parser.parse("xyz").verb == "unknown", "parser: desconhecido")

    # Estado / filesystem (ainda fixo)
    st = new_game(1234)
    ok(st.seed == 1234, "seed: armazenada no estado")
    ok(st.cwd == ["usr", "guest"], "world: cwd inicial")
    parts, node = st.resolve("/var/log")
    ok(node is not None and node.is_dir, "state: resolve caminho absoluto")

    # Rede PROCEDURAL — invariantes
    ok("GATE" in st.net and st.net["GATE"].state == "compromised", "rede: GATE é a entrada")
    ok(st.core_id in st.net, "rede: core_id existe no grafo")
    ok(st.net[st.core_id].label == "CORE", "rede: objetivo rotulado CORE")
    ok(6 <= len(st.net) <= 10, "rede: tamanho no intervalo esperado")
    ok(reachable_from_gate(st) == set(st.net), "rede: todos os nós alcançáveis de GATE")
    # links simétricos
    sym = all(a in st.net[b].links for a in st.net for b in st.net[a].links)
    ok(sym, "rede: links simétricos")
    # névoa: vizinhos de GATE revelados, mas o CORE (mais distante) fica oculto
    disc = [n for n in st.net.values() if n.state == "discovered"]
    ok(len(disc) >= 1, "névoa: ao menos um vizinho revelado no boot")
    ok(st.net[st.core_id].state == "fog", "névoa: CORE começa oculto")

    # Determinismo: mesma seed -> mesma rede; seeds diferentes -> redes diferentes
    ok(net_signature(new_game(777)) == net_signature(new_game(777)), "determinismo: seed igual = rede igual")
    ok(net_signature(new_game(1)) != net_signature(new_game(2)), "determinismo: seeds diferentes = redes diferentes")

    # Fase 2/3: filesystem procedural por host
    ok(all(n.fs is not None for n in st.net.values()), "fs: cada host tem filesystem próprio")
    motds = {n.id: n.fs.children["etc"].children["motd"].content for n in st.net.values()}
    ok(len(set(motds.values())) > 1, "fs: hosts têm MOTD diferentes (Fase 3)")
    a, b = new_game(999), new_game(999)
    pa = a.net["GATE"].fs.children["etc"].children["passwd"].content
    pb = b.net["GATE"].fs.children["etc"].children["passwd"].content
    ok(pa == pb, "fs: conteúdo determinístico por seed")

    # Fase 4: ICE escala com a profundidade (ranges garantem a ordem)
    shallow = make_ice("MAIL", 0)
    deep = make_ice("CORE", 8)
    ok(deep.total_rounds > shallow.total_rounds, "fase 4: mais fundo = mais rounds")
    ok(deep.base_time < shallow.base_time, "fase 4: mais fundo = menos tempo")

    # Renderizadores puros não quebram
    ok(render_status(st).plain != "", "ui: render_status")
    ok("GATE" in render_map(st).plain, "ui: render_map mostra GATE")
    print("--- unidades OK ---")


def test_hardware():
    from coldboot.hardware import Rig

    base = hardware.starting_rig()
    ok(hardware.derived(base).hashrate > 0, "hw: rig inicial tem hashrate")

    # Compatibilidade: a placa básica é DDR3 e não tem PCIe.
    ddr4 = hardware.CATALOG["ram_d4_8"]
    ok(not hardware.can_install(base, ddr4)[0], "hw: RAM de geração errada é rejeitada")
    ok(not hardware.can_install(base, hardware.CATALOG["gpu_a"])[0],
       "hw: GPU sem slot PCIe é rejeitada")
    ok(not hardware.can_install(base, hardware.CATALOG["cpu_s3"])[0],
       "hw: CPU de socket errado é rejeitada")

    # Slots: a placa básica tem 2; o segundo pente entra, o terceiro não.
    dois = Rig(ram=["ram_d3_4", "ram_d3_4"])
    ok(not hardware.can_install(dois, hardware.CATALOG["ram_d3_4"])[0],
       "hw: sem slots livres a RAM é rejeitada")

    # Mineração memory-hard: mais RAM = mais hashrate.
    ok(hardware.derived(dois).hashrate > hardware.derived(base).hashrate,
       "hw: mais RAM = mais hashrate (memory-hard)")

    # Fonte insuficiente barra a peça.
    forte = Rig(mobo="mb_c3", cpu="cpu_s3", ram=["ram_d5_32"], psu="psu_300")
    ok(not hardware.can_install(forte, hardware.CATALOG["gpu_b"])[0],
       "hw: fonte insuficiente barra a GPU")

    # Trocar a placa-mãe descarta RAM/CPU incompatíveis.
    trocar = hardware.starting_rig()
    avisos = hardware.install(trocar, hardware.CATALOG["mb_b2"])
    ok(trocar.ram == [], "hw: troca de placa descarta RAM incompatível")
    ok(hardware.CATALOG[trocar.cpu].specs["socket"] == "S2", "hw: troca de placa ajusta a CPU")
    ok(len(avisos) == 2, "hw: troca de placa avisa o que foi removido")

    # Calor: minerando esquenta mais que ocioso; cooler melhor esfria.
    ok(hardware.heat_equilibrium(base, True) > hardware.heat_equilibrium(base, False),
       "hw: minerar esquenta mais que ocioso")
    gelado = Rig(cooler="cool_liquid")
    ok(hardware.heat_equilibrium(gelado, True) < hardware.heat_equilibrium(base, True),
       "hw: cooler melhor = menos calor")
    print("--- hardware OK ---")


def test_economy():
    st = new_game(7)
    st.processes.append("miner")
    info = economy.tick_economy(st, 1.0)
    ok(info.mining and info.mined > 0 and st.wallet > 0, "eco: minerador gera CRN")

    # Ocioso: não minera, mas ainda consome (menos).
    st2 = new_game(7)
    carga = economy.tick_economy(st2, 1.0)
    ok(carga.mined == 0 and st2.wallet == 0, "eco: sem minerador não gera CRN")
    ok(carga.power < info.power, "eco: ocioso consome menos que sob carga")

    # Superaquecimento: throttle para a mineração e zera o bônus da CPU.
    quente = new_game(7)
    quente.processes.append("miner")
    quente.heat = 200.0
    quente.rig.cpu = "cpu_s3"
    quente.rig.mobo = "mb_c3"
    hot = economy.tick_economy(quente, 1.0)
    ok(hot.overheated and hot.mined == 0, "eco: superaquecido não minera")
    ok(economy.typing_bonus(quente) == 0.0, "eco: superaquecido zera o bônus da CPU")
    ok(economy.tele_speed(quente) < economy.tele_speed(new_game(7)),
       "eco: superaquecido deixa o texto mais lento")

    # Loja: preço, saldo e compatibilidade.
    loja = new_game(7)
    ok(not economy.buy(loja, "nao_existe")[0], "eco: peça inexistente não compra")
    ok(not economy.buy(loja, "cool_fans")[0], "eco: saldo insuficiente recusa a compra")
    loja.wallet = 500.0
    comprou, _msg, _av = economy.buy(loja, "cool_fans")
    ok(comprou and loja.rig.cooler == "cool_fans", "eco: compra instala a peça")
    ok(abs(loja.wallet - (500.0 - hardware.CATALOG["cool_fans"].price)) < 0.01,
       "eco: compra debita o preço")
    ok(not economy.buy(loja, "gpu_a")[0], "eco: peça incompatível não compra")
    saldo = loja.wallet
    ok(not economy.buy(loja, "cool_fans")[0], "eco: peça já instalada não recompra")
    ok(loja.wallet == saldo, "eco: compra recusada não debita nada")
    # RAM é exceção: pentes iguais empilham nos slots livres.
    ok(not hardware.is_installed(loja.rig, hardware.CATALOG["ram_d3_4"]),
       "eco: RAM nunca conta como 'já instalada'")
    print("--- economia OK ---")


def test_loot():
    # Determinismo por seed (mesma regra do resto da procgen).
    a = loot.generate_item(random.Random(3), 2)
    b = loot.generate_item(random.Random(3), 2)
    ok(a.name == b.name and a.item == b.item, "loot: item determinístico por seed")

    ok(not a.is_dir and a.item and a.item.get("kind"), "loot: item é arquivo e tem kind")
    ok(a.content, "loot: item tem conteúdo para o `cat`")

    # sprinkle respeita a chance (a maioria das pastas fica vazia).
    from coldboot.state import FSNode
    vazia = FSNode("dir", True)
    loot.sprinkle(random.Random(1), vazia, 0, chance=0.0)
    ok(vazia.children == {}, "loot: chance 0 não gera item")
    cheia = FSNode("dir", True)
    loot.sprinkle(random.Random(1), cheia, 0, chance=1.0)
    ok(len(cheia.children) == 1, "loot: chance 1 gera exatamente um item")

    # Nomes semi-aleatórios: a mesma pasta não repete o mesmo nome sempre.
    nomes = {loot.generate_item(random.Random(s), 1).name for s in range(30)}
    ok(len(nomes) > 10, "loot: nomes semi-aleatórios variam")

    # Profundidade paga melhor.
    raso = [loot.generate_item(random.Random(s), 0) for s in range(60)]
    fundo = [loot.generate_item(random.Random(s), 6) for s in range(60)]
    def media(itens):
        vals = [i.item["amount"] for i in itens if "amount" in i.item]
        return sum(vals) / max(1, len(vals))
    ok(media(fundo) > media(raso), "loot: mais fundo = recompensa maior")

    # Todo kind gerado é conhecido pelo jogo.
    kinds = {loot.generate_item(random.Random(s), 3).item["kind"] for s in range(200)}
    ok(kinds <= {"miner", "wallet", "credits", "adminkey", "coolant", "scrambler",
                 "keycard", "spoof", "backdoor"},
       "loot: só gera kinds conhecidos")
    # Hardware nunca é loot de pasta — só se compra na loja.
    ok("ramcrate" not in kinds, "loot: nenhum kind de hardware aparece como loot")
    # `kind` força o tipo (usado para plantar o cartão que o cofre exige).
    forcado = [loot.generate_item(random.Random(s), 1, kind="keycard") for s in range(5)]
    ok(all(i.item["kind"] == "keycard" and i.item["code"] for i in forcado),
       "loot: kind forçado gera o item pedido, com série")
    print("--- loot OK ---")


def test_timebonus():
    # A CPU compra segundos nos minigames (combate e lockdown).
    sem = make_ice("MAIL", 2, rng=random.Random(5), time_bonus=0.0)
    com = make_ice("MAIL", 2, rng=random.Random(5), time_bonus=2.5)
    sem.start()
    com.start()
    ok(abs((com.time_left - sem.time_left) - 2.5) < 1e-6, "cpu: bônus soma tempo no combate")
    ok(LockdownSession(1, 2.5).time_left - LockdownSession(1, 0.0).time_left == 2.5,
       "cpu: bônus soma tempo no lockdown")
    # E o bônus persiste nos rounds seguintes, não só no primeiro.
    com.submit("errado")
    ok(com.time_left > sem.time_left, "cpu: bônus vale em todos os rounds")
    print("--- bônus de CPU OK ---")


def test_settings(tmp):
    p = tmp / "cfg.json"
    s = settings_mod.load(p)
    ok(s.difficulty == "normal" and not s.high_contrast, "cfg: sem arquivo = padrões")

    # Dificuldade cicla e persiste no disco.
    ok(s.cycle_difficulty().id == "dificil", "cfg: dificuldade cicla normal -> difícil")
    ok(s.toggle_contrast() is True, "cfg: alto contraste alterna")
    settings_mod.save(s, p)
    ok(settings_mod.load(p).difficulty == "dificil", "cfg: dificuldade persiste")
    ok(settings_mod.load(p).high_contrast is True, "cfg: contraste persiste")

    # Arquivo corrompido ou valor inválido cai nos padrões em vez de quebrar.
    p.write_text("{lixo!!", encoding="utf-8")
    ok(settings_mod.load(p).difficulty == "normal", "cfg: arquivo corrompido = padrões")
    p.write_text('{"difficulty": "impossivel"}', encoding="utf-8")
    ok(settings_mod.load(p).difficulty == "normal", "cfg: dificuldade inválida = normal")

    # A dificuldade realmente mexe nos minigames.
    facil = settings_mod.DIFFICULTIES["facil"]
    dificil = settings_mod.DIFFICULTIES["dificil"]
    f = make_ice("MAIL", 1, rng=random.Random(4), diff=facil)
    n = make_ice("MAIL", 1, rng=random.Random(4), diff=None)
    d = make_ice("MAIL", 1, rng=random.Random(4), diff=dificil)
    f.start(); n.start(); d.start()
    ok(f.time_left > n.time_left > d.time_left, "cfg: dificuldade escalona o tempo do ICE")
    ok(len(d.code) > len(n.code), "cfg: difícil = código mais longo")
    ok("-" in f.code or f.code.split("::")[1].islower(),
       "cfg: fácil = código com palavras legíveis")
    ok(all(c.isalpha() or c in "-" for c in f.code.split("::")[1]),
       "cfg: fácil não mistura dígitos no código")

    lf = LockdownSession(1, diff=facil)
    ln = LockdownSession(1, diff=None)
    ok(lf.time_left > ln.time_left, "cfg: fácil dá mais tempo no lockdown")
    ok(lf.words and not ln.words, "cfg: fácil usa palavras no lockdown")
    print("--- configurações OK ---")


def test_savegame(tmp):
    p = tmp / "save.json"
    ok(savegame.load(p) is None, "save: sem arquivo = None")
    ok(not savegame.has_save(p), "save: has_save falso sem arquivo")

    st = new_game(4242)
    # Suja o estado com tudo que a seed sozinha NÃO reconstrói.
    st.trace = 61.5
    st.add_trace(0.0)   # recomputa `connection` (o load também recomputa; sem
                        # isso o objeto original ficaria com um valor "stale")
    st.wallet = 12.5
    st.adminkey = 2
    st.heat = 70.0
    st.lockdown_level = 2
    st.processes.append("miner")
    st.inventory.append({"name": "keycard_1f.bin", "kind": "keycard", "code": "7F-ORION-2A"})
    st.flags["read_auth"] = True
    st.rig.cooler = "cool_fans"
    st.rig.ram.append("ram_d3_4")
    st.cwd = ["var", "log"]
    alvo = st.net["GATE"].fs.children["home"].children["admin"]
    alvo.locked = False                                  # destrancado na partida
    st.net["GATE"].fs.children["tmp"].children.clear()   # item consumido
    outro = next(n for n in st.net.values() if n.id != "GATE")
    outro.state = "compromised"

    savegame.save(st, p)
    ok(savegame.has_save(p), "save: grava o arquivo")
    r = savegame.load(p)
    ok(r is not None, "save: carrega de volta")

    ok((r.seed, r.trace, r.wallet, r.adminkey) == (4242, 61.5, 12.5, 2),
       "save: escalares voltam")
    ok(r.heat == 70.0 and r.lockdown_level == 2,
       "save: economia e lockdown voltam")
    ok(r.processes == ["miner"], "save: minerador segue rodando ao carregar")
    ok(r.inventory == st.inventory and r.flags["read_auth"] is True,
       "save: inventário (com os dados dos itens) e flags voltam")
    ok(r.find_item("keycard") is not None and r.find_item("keycard_1f.bin") is not None,
       "save: item carregado volta achável por kind e por nome")
    ok((r.run_number, r.runs_won) == (st.run_number, st.runs_won),
       "save: contadores de incursão voltam")
    ok(r.ram_free == st.ram_free, "save: RAM do host é derivada, não salva torta")
    ok(r.rig.cooler == "cool_fans" and r.rig.ram == ["ram_d3_4", "ram_d3_4"],
       "save: o rig montado volta peça por peça")
    ok(r.cwd == ["var", "log"] and r.location == "GATE", "save: posição volta")

    # As mutações do mundo — o motivo de não salvar só a seed.
    ok(not r.net["GATE"].fs.children["home"].children["admin"].locked,
       "save: pasta destrancada continua destrancada")
    ok(r.net["GATE"].fs.children["tmp"].children == {},
       "save: item consumido não ressuscita")
    ok(r.net[outro.id].state == "compromised", "save: nó comprometido volta")
    ok(set(r.net) == set(st.net), "save: rede inteira volta")
    ok(all(n.fs is not None for n in r.net.values()), "save: todo host mantém seu FS")

    # A ordem do `ls` é parte do save (dict preserva inserção).
    ok(list(r.net["GATE"].fs.children) == list(st.net["GATE"].fs.children),
       "save: ordem do filesystem preservada")

    # Round-trip é estável: salvar o carregado dá o mesmo JSON.
    ok(savegame.state_to_dict(r) == savegame.state_to_dict(st), "save: round-trip estável")

    # --- Migração v1 -> v2 ---
    # Um save v1 de verdade: inventory era lista de NOMES, ram_free era salvo e
    # não existiam contadores de incursão. Quem já estava jogando tem um destes
    # no disco; recusá-lo jogaria a partida da pessoa fora.
    import json
    v1 = json.loads(p.read_text(encoding="utf-8"))
    v1["version"] = 1
    v1["inventory"] = ["keycard"]
    v1["ram_free"] = 640
    v1.pop("run_number", None)
    v1.pop("runs_won", None)
    p.write_text(json.dumps(v1), encoding="utf-8")
    velho = savegame.load(p)
    ok(velho is not None, "migração: save v1 continua carregando")
    ok(velho.inventory == [{"name": "keycard", "kind": "keycard"}],
       "migração: inventário v1 (nomes) vira item do formato novo")
    ok(velho.find_item("keycard") is not None, "migração: o item migrado é achável")
    ok((velho.run_number, velho.runs_won) == (1, 0),
       "migração: v1 entra como primeira incursão")
    # O v1 gravava ram_free=640 mesmo com minerador e item; agora é derivado.
    ok(velho.ram_free == velho.ram_total - velho.ram_used(),
       "migração: ram_free vira derivado")
    ok(velho.ram_free != 640, "migração: o ram_free obsoleto do arquivo é ignorado")
    ok(velho.seed == st.seed and velho.trace == st.trace,
       "migração: o resto do save v1 chega intacto")
    # Migrar e regravar deixa o arquivo no formato novo.
    savegame.save(velho, p)
    ok(json.loads(p.read_text(encoding="utf-8"))["version"] == savegame.SAVE_VERSION,
       "migração: regravar sobe o save para a versão atual")

    # Save de versão futura é recusado em vez de carregar torto.
    d = json.loads(p.read_text(encoding="utf-8"))
    d["version"] = 999
    p.write_text(json.dumps(d), encoding="utf-8")
    ok(savegame.load(p) is None, "save: versão desconhecida é recusada")
    p.write_text("{nao é json", encoding="utf-8")
    ok(savegame.load(p) is None, "save: arquivo corrompido não quebra")
    print("--- savegame OK ---")


def test_help():
    from coldboot.app import _help_sections

    # _help_sections() é uma função (não mais uma lista fixa de módulo) desde
    # que o help virou traduzível: o texto precisa ser resolvido no locale
    # atual a cada chamada, não "congelado" na hora em que o módulo foi importado.
    sections = _help_sections()
    help_pad = max(len(uso) for _t, ls in sections for uso, _d in ls) + 3

    linhas = [(uso, desc) for _t, ls in sections for uso, desc in ls]
    ok(len(linhas) >= 15, "help: uma linha por comando")
    ok(all(desc and desc[0].islower() for _u, desc in linhas),
       "help: toda linha tem explicação")

    # Espaçamento padronizado: a explicação começa na MESMA coluna em todas.
    render = [f"  {uso:<{help_pad}}{desc}" for uso, desc in linhas]
    colunas = {l.index(d) for l, (_u, d) in zip(render, linhas)}
    ok(len(colunas) == 1, "help: explicações todas na mesma coluna")
    ok(all(l[:2] == "  " for l in render), "help: comandos indentados")
    # A coluna cabe na sintaxe mais longa sem colar nela.
    maior = max(len(uso) for uso, _d in linhas)
    ok(help_pad > maior, "help: a coluna não encosta no comando mais longo")

    # O help cobre o que o parser aceita: nada documentado que não exista.
    usos = {uso.split()[0] for uso, _d in linhas}
    ok(usos <= set(parser._SHELL), "help: não documenta comando inexistente")
    # E os comandos novos estão documentados.
    ok({"save", "store", "comprar", "kill"} <= usos, "help: documenta os comandos novos")
    print("--- help OK ---")


def test_host_ram():
    from coldboot.hardware import Rig

    st = new_game(11)
    ok(st.ram_free == st.ram_total == 640, "ram: host começa com os 640K livres")

    # Itens no buffer ocupam memória do host.
    st.inventory.append({"name": "a.bin", "kind": "coolant", "amount": 20})
    ok(st.ram_free == 640 - hardware.ITEM_KB, "ram: item no buffer ocupa KB")

    # O minerador ocupa muito mais — e cresce com a RAM do RIG (memory-hard).
    st.processes.append("miner")
    pequeno = st.ram_used()
    st.rig = Rig(mobo="mb_x9", cpu="cpu_s4", ram=["ram_d6_64"] * 4, psu="psu_1200")
    ok(st.ram_used() > pequeno, "ram: rig maior = minerador com pegada maior")

    # Mesmo o rig de topo cabe nos 640K (senão a economia morria no late game).
    topo = hardware.miner_footprint(st.rig)
    ok(topo < 640, "ram: até o rig de topo cabe no host")
    ok(topo > hardware.miner_footprint(Rig()), "ram: rig de topo ocupa mais que o inicial")
    # ...mas sobra pouco: minerar passa a competir com carregar itens.
    ok((640 - topo) // hardware.ITEM_KB <= 3, "ram: rig de topo quase não deixa espaço para itens")

    # Memória no talo = host desconfiado.
    st.inventory.clear()
    ok(not st.ram_tight, "ram: com folga o host não estranha")
    while st.can_hold():
        st.inventory.append({"name": "x", "kind": "coolant", "amount": 1})
    ok(st.ram_tight, "ram: buffer no limite deixa o host no talo")
    ok(not st.can_hold(), "ram: sem espaço o buffer recusa mais itens")
    ok(st.ram_free >= 0, "ram: livre nunca fica negativo")
    print("--- RAM do host OK ---")


def test_mining_noise():
    from coldboot.hardware import Rig

    # Parado não faz barulho.
    st = new_game(11)
    ok(economy.mining_noise(st) == 0.0, "ruído: sem minerador não há barulho")
    t0 = st.trace
    economy.tick_economy(st, 1.0)
    ok(st.trace == t0, "ruído: sem minerador o tick não sobe o trace")

    # Minerar sobe o trace — o custo que faltava na economia.
    st.processes.append("miner")
    info = economy.tick_economy(st, 1.0)
    ok(info.noise > 0 and st.trace > t0, "ruído: minerar sobe o trace")

    # Rig maior = mais barulho (sublinear, mas monotônico).
    fraco = new_game(11); fraco.processes.append("miner")
    forte = new_game(11); forte.processes.append("miner")
    forte.rig = Rig(mobo="mb_x9", cpu="cpu_s4", ram=["ram_d6_64"] * 2, psu="psu_1200")
    ok(economy.mining_noise(forte) > economy.mining_noise(fraco),
       "ruído: rig maior minera mais alto")
    # Sublinear: dobrar o hashrate não dobra o risco.
    razao_hash = (hardware.derived(forte.rig).hashrate
                  / hardware.derived(fraco.rig).hashrate)
    razao_ruido = economy.mining_noise(forte) / economy.mining_noise(fraco)
    ok(razao_ruido < razao_hash, "ruído: cresce sublinear no hashrate")

    # Host no talo = o dobro de barulho.
    calmo = economy.mining_noise(forte)
    while forte.can_hold():
        forte.inventory.append({"name": "x", "kind": "coolant", "amount": 1})
    ok(forte.ram_tight and economy.mining_noise(forte) > calmo,
       "ruído: host sem memória repara muito mais")

    # Superaquecido não minera, então não faz barulho de mineração.
    quente = new_game(11); quente.processes.append("miner"); quente.heat = 200.0
    hot = economy.tick_economy(quente, 1.0)
    ok(hot.noise == 0.0, "ruído: em throttle não minera nem faz barulho")
    print("--- ruído da mineração OK ---")


def test_ice_behaviors():
    # Cada tipo de ICE tem um verbo próprio, não só números diferentes.
    # Depth 8 já libera o Fantasma (_PHANTOM_MIN_DEPTH), então os cinco tipos
    # devem aparecer numa amostra grande.
    tipos = {}
    for s in range(200):
        ice = make_ice("CORE", 8, rng=random.Random(s))
        tipos[ice.ice_type] = ice.behavior
    ok(set(tipos) == {"Sentinel", "Firewall", "Hunter", "Guardian", "Phantom"},
       "ice: os cinco tipos aparecem no fundo da rede")
    ok(tipos["Sentinel"] == "plain" and tipos["Firewall"] == "plain",
       "ice: Sentinel e Firewall jogam limpo")
    ok(tipos["Hunter"] == "hunt", "ice: Hunter é do tipo que escapa")
    ok(tipos["Guardian"] == "memory", "ice: Guardian é o de memória")
    ok(tipos["Phantom"] == "phantom", "ice: Phantom é o tipo que esconde E troca")

    # Antes do degrau (_PHANTOM_MIN_DEPTH), o Fantasma nunca aparece.
    tipos_rasos = {make_ice("CORE", 5, rng=random.Random(s)).ice_type for s in range(200)}
    ok("Phantom" not in tipos_rasos, "ice: Fantasma não aparece antes da profundidade mínima")

    # Guardião: mostra o código e some com ele.
    g = CombatSession("g", "g", behavior="memory", reveal=1.0, base_time=6.0)
    g.start()
    ok(g.code_visible and g.display_code() == g.code, "ice: memória mostra o código no início")
    g.tick(1.2)
    ok(not g.code_visible, "ice: memória esconde o código depois do reveal")
    mascarado = g.display_code()
    ok(mascarado != g.code and len(mascarado) == len(g.code),
       "ice: escondido vira máscara do mesmo tamanho")
    ok("::" in mascarado, "ice: a máscara preserva a forma do código")
    ok(g.submit(g.code).kind in ("hit", "won"),
       "ice: acertar de memória vale, mesmo com o código escondido")

    # Caçador: o código escapa no meio do round — uma vez só.
    h = CombatSession("h", "h", behavior="hunt", base_time=4.0, mutate_at=0.5)
    h.start()
    antes = h.code
    h.tick(0.5)
    ok(h.code == antes and not h.mutated, "ice: caça não muda no começo do round")
    h.tick(1.8)
    ok(h.code != antes and h.mutated, "ice: caça troca o código na metade")
    escapou = h.code
    h.tick(0.5)
    ok(h.code == escapou, "ice: caça escapa uma vez por round, não sempre")
    # E o código velho não vale mais.
    ok(h.submit(antes).kind == "miss", "ice: o código que escapou não vale mais")

    # Tipo limpo nunca esconde nem muda.
    p = CombatSession("p", "p", behavior="plain", base_time=4.0)
    p.start()
    c0 = p.code
    p.tick(3.0)
    ok(p.code == c0 and p.code_visible, "ice: tipo limpo não mexe no código")

    # Fantasma: esconde cedo (memória) E troca escondido (caça) — o pior
    # dos dois. Quem memorizou o código antigo não sabe que ele já mudou.
    f = CombatSession("f", "f", behavior="phantom", base_time=6.0,
                      reveal=1.0, mutate_at=0.5)
    f.start()
    memorizado = f.code
    ok(f.code_visible, "fantasma: mostra o código no início, como o Guardião")
    f.tick(1.2)
    ok(not f.code_visible, "fantasma: esconde cedo, antes da metade do round")
    ok(f.code == memorizado and not f.mutated,
       "fantasma: escondido, mas ainda não trocou logo depois do reveal")
    f.tick(1.8)  # passa de metade do round_time (6.0*0.5=3.0), ainda escondido
    ok(f.mutated and f.code != memorizado,
       "fantasma: troca de código enquanto está escondido")
    ok(not f.code_visible, "fantasma: continua escondido depois de trocar")
    ok(f.submit(memorizado).kind == "miss",
       "fantasma: o código memorizado antes da troca não vale mais nada")

    # No fácil o Guardião mostra o código por mais tempo.
    facil = settings_mod.DIFFICULTIES["facil"]
    gf = make_ice("X", 8, rng=random.Random(3), diff=facil)
    gn = make_ice("X", 8, rng=random.Random(3), diff=None)
    ok(gf.reveal > gn.reveal, "ice: fácil revela o código por mais tempo")
    print("--- comportamentos de ICE OK ---")


def test_meta_loop():
    from coldboot.hardware import Rig

    prev = new_game(5)
    prev.rig = Rig(mobo="mb_b2", cpu="cpu_s2", ram=["ram_d4_8"], psu="psu_550",
                   cooler="cool_fans")
    prev.wallet = 88.0
    prev.adminkey = 3
    prev.inventory.append({"name": "x.bin", "kind": "scrambler", "amount": 30})
    prev.trace = 90.0
    prev.lockdown_level = 4
    prev.processes.append("miner")

    # Vitória: leva o rig E a carteira.
    won = next_run(prev, won=True)
    ok(won.seed != prev.seed, "meta: incursão nova sorteia outra rede")
    ok(won.rig.cpu == "cpu_s2" and won.rig.cooler == "cool_fans", "meta: o rig vem junto")
    ok(won.wallet == 88.0, "meta: vencer preserva a carteira")
    ok(won.run_number == 2 and won.runs_won == 1, "meta: placar sobe ao vencer")

    # Derrota: mantém o rig, perde a carteira (congelada).
    lost = next_run(prev, won=False)
    ok(lost.rig.cpu == "cpu_s2", "meta: perder não tira o hardware")
    ok(lost.wallet == 0.0, "meta: perder congela a carteira")
    ok(lost.run_number == 2 and lost.runs_won == 0, "meta: derrota não pontua")

    # O que ficou lá dentro, fica lá dentro.
    ok(lost.inventory == [] and lost.adminkey == 0, "meta: buffer e chaves ficam na rede")
    ok(lost.processes == [], "meta: nenhum processo sobrevive")
    ok(lost.trace < 90.0 and lost.lockdown_level == 0, "meta: trace e cerco zeram")

    # O rig é uma cópia: mexer na run nova não mexe na antiga.
    won.rig.ram.append("ram_d4_8")
    ok(prev.rig.ram == ["ram_d4_8"], "meta: o rig é copiado, não compartilhado")
    print("--- loop de incursões OK ---")


def test_keycard_world():
    # Invariante: se a rede tem cofre, tem cartão em algum lugar.
    from coldboot.procgen import loot as lootmod
    com_cofre = 0
    for seed in range(40):
        st = new_game(seed)
        hosts = [n for n in st.net.values() if n.fs]
        cofre = any(lootmod.find_kind(n.fs, "reader") for n in hosts)
        if not cofre:
            continue
        com_cofre += 1
        card = any(lootmod.find_kind(n.fs, "keycard") for n in hosts)
        ok(card, f"keycard: seed {seed} tem cofre e tem cartão")
    ok(com_cofre > 0, f"keycard: cofres aparecem nas runs ({com_cofre}/40 seeds)")

    # O leitor guarda um cofre trancado, e o cofre tem loot.
    st = next(new_game(s) for s in range(40)
              if any(lootmod.find_kind(n.fs, "reader") for n in new_game(s).net.values() if n.fs))
    host = next(n for n in st.net.values() if n.fs and lootmod.find_kind(n.fs, "reader"))
    sysdir = host.fs.children["sys"]
    ok(lootmod.READER_NAME in sysdir.children, "keycard: o leitor fica em /sys")
    cofre = sysdir.children[lootmod.VAULT_NAME]
    ok(cofre.locked and cofre.is_dir, "keycard: o cofre nasce trancado")
    ok(cofre.hack_id == "card_reader", "keycard: o cofre também cede ao hack")
    ok(len(cofre.children) > 0, "keycard: o cofre tem recompensa dentro")
    # O leitor não aparece na entrada da rede (depth 0).
    ok(lootmod.find_kind(st.net["GATE"].fs, "reader") is None,
       "keycard: a entrada da rede não tem cofre")
    print("--- keycard/cofre OK ---")


def test_sectors():
    from coldboot.combat import boss_name, effective_depth, make_boss
    from coldboot.procgen.network import MAX_NODES, size_for_sector

    # A rede NÃO pode crescer para sempre: o mapa ASCII trava em MAX_NODES.
    tamanhos = [size_for_sector(random.Random(s), s) for s in range(1, 40)]
    ok(all(t <= MAX_NODES for t in tamanhos), "setor: a rede nunca passa do teto do mapa")
    ok(size_for_sector(random.Random(1), 9) > size_for_sector(random.Random(1), 1),
       "setor: setor mais alto = rede maior (até saturar)")
    ok(size_for_sector(random.Random(1), 99) == MAX_NODES, "setor: satura no teto")

    # Como a rede satura, quem escala para sempre é o setor.
    ok(effective_depth(3, 1) == 3, "setor: setor 1 não altera a profundidade")
    ok(effective_depth(3, 10) > effective_depth(3, 2) > effective_depth(3, 1),
       "setor: o setor vira profundidade efetiva e cresce sem teto")

    # ICE escala com o setor mesmo com a rede saturada.
    raso = make_ice("X", effective_depth(2, 1), rng=random.Random(2))
    fundo = make_ice("X", effective_depth(2, 12), rng=random.Random(2))
    ok(fundo.total_rounds > raso.total_rounds, "setor: ICE fica mais duro por setor")
    ok(fundo.trace_penalty > raso.trace_penalty, "setor: penalidade cresce por setor")

    # Pagamento cresce mais que linear: vale descer.
    p1, p2, p10 = (sector_payout(1), sector_payout(2), sector_payout(10))
    ok(p10 > p2 > p1, "setor: setor mais fundo paga mais")
    ok(p10 > p1 * 10 / 2, "setor: o pagamento cresce mais que linear")

    # Boss: um por setor, com persona e sem jogar limpo.
    b1, b2 = make_boss(1), make_boss(2)
    ok(b1.ice_type == "BOSS" and b2.ice_type == "BOSS", "boss: é um ICE próprio")
    ok(b1.behavior == "memory" and b2.behavior == "hunt",
       "boss: alterna o verbo entre setores")
    ok(make_boss(9).total_rounds > b1.total_rounds, "boss: escala com o setor")
    ok(make_boss(9).base_time < b1.base_time, "boss: mais fundo = menos tempo")
    ok(boss_name(1) != boss_name(2), "boss: cada setor tem sua persona")
    ok(boss_name(1) in b1.name and "sector 1" in b1.name, "boss: o nome entra na narrativa")
    # Persona cicla, mas não repete o nome exato.
    n = len(__import__("coldboot.combat", fromlist=["x"]).BOSS_TITLES)
    ok(boss_name(1) != boss_name(1 + n), "boss: ao dar a volta, a persona ganha ciclo")
    # O boss é o clímax: tem que ser mais duro que QUALQUER nó do setor, em
    # qualquer setor. Sem isso, um Guardião de canto de setor alto punia mais
    # que o próprio núcleo.
    for setor in (1, 3, 8, 15, 30):
        b = make_boss(setor)
        piores_pen, piores_rounds = 0.0, 0
        for s in range(40):
            for prof in range(0, 7):     # toda profundidade possível na rede
                c = make_ice("X", effective_depth(prof, setor), rng=random.Random(s))
                piores_pen = max(piores_pen, c.trace_penalty)
                piores_rounds = max(piores_rounds, c.total_rounds)
        ok(b.trace_penalty > piores_pen, f"boss: setor {setor} pune mais que qualquer nó")
        ok(b.total_rounds >= piores_rounds, f"boss: setor {setor} não é mais curto que um nó")

    # Duelo infinito não pode virar duelo eterno: os rounds têm teto.
    from coldboot.combat import BOSS_MAX_ROUNDS, MAX_ROUNDS
    ok(make_ice("X", effective_depth(6, 99), rng=random.Random(1)).total_rounds <= MAX_ROUNDS,
       "ice: os rounds têm teto mesmo em setor absurdo")
    ok(make_boss(99).total_rounds <= BOSS_MAX_ROUNDS, "boss: os rounds têm teto")
    # ...mas o resto continua apertando depois do teto.
    ok(make_boss(99).trace_penalty > make_boss(20).trace_penalty,
       "boss: passado o teto de rounds, a penalidade segue subindo")

    # O mundo monta o setor pedido.
    st = new_game(3, sector=7)
    ok(st.sector == 7 and st.best_sector == 7, "setor: new_game monta o setor pedido")
    ok(len(st.net) <= MAX_NODES, "setor: a rede montada respeita o teto")
    print("--- setores/bosses OK ---")


def test_sector_modifiers():
    from coldboot.combat import make_boss
    from coldboot.world import SECTOR_MODIFIERS

    # Todo new_game sorteia um modificador conhecido.
    st = new_game(5, sector=2)
    ok(st.modifier_id in SECTOR_MODIFIERS, "modificador: new_game sempre sorteia um conhecido")
    ok(new_game(5, sector=2).modifier_id == st.modifier_id,
       "modificador: determinístico pela seed/setor")

    # Os multiplicadores resolvidos no estado batem com a tabela.
    mod = SECTOR_MODIFIERS[st.modifier_id]
    ok(st.mod_creep == mod.creep_mult, "modificador: mod_creep bate com a tabela")
    ok(st.mod_ice_penalty == mod.ice_penalty_mult, "modificador: mod_ice_penalty bate com a tabela")
    ok(st.mod_botnet_risk == mod.botnet_risk_mult, "modificador: mod_botnet_risk bate com a tabela")
    ok(st.mod_payout == mod.payout_mult, "modificador: mod_payout bate com a tabela")

    # Nenhum modificador é de graça: sempre mexe o payout junto.
    ok(all(m.payout_mult != 1.0 for m in SECTOR_MODIFIERS.values()),
       "modificador: todos trocam algo pelo payout do setor")

    # GameState "cru" (sem passar por new_game) fica neutro — nunca quebra.
    from coldboot.state import GameState
    cru = GameState()
    ok(cru.modifier_id == "" and cru.mod_creep == cru.mod_ice_penalty ==
       cru.mod_botnet_risk == cru.mod_payout == 1.0,
       "modificador: estado cru (sem new_game) é neutro por padrão")

    # creep_mult aplica o modificador em cima do roteador.
    base = economy.creep_mult(cru)
    cru.mod_creep = 0.5
    ok(economy.creep_mult(cru) == base * 0.5, "modificador: creep_mult aplica mod_creep")

    # botnet_risk aplica o multiplicador sem estourar o teto original.
    idade = economy.BOTNET_GRACE_TICKS + 10
    risco_normal = economy.botnet_risk(idade, 1.0)
    risco_reduzido = economy.botnet_risk(idade, 0.5)
    ok(risco_reduzido < risco_normal, "modificador: mod_botnet_risk reduz o risco de fato")
    ok(economy.botnet_risk(idade + 10000, 1.0) == economy.BOTNET_RISK_CAP,
       "modificador: o teto de risco continua valendo com multiplicador neutro")

    # make_ice/make_boss aplicam pen_mult na penalidade de trace.
    normal = make_ice("X", 3, rng=random.Random(1))
    punitivo = make_ice("X", 3, rng=random.Random(1), pen_mult=1.3)
    brando = make_ice("X", 3, rng=random.Random(1), pen_mult=0.75)
    ok(punitivo.trace_penalty > normal.trace_penalty > brando.trace_penalty,
       "modificador: pen_mult sobe/desce a penalidade do ICE")
    boss_normal = make_boss(4)
    boss_punitivo = make_boss(4, pen_mult=1.3)
    ok(boss_punitivo.trace_penalty > boss_normal.trace_penalty,
       "modificador: pen_mult também vale para o boss")
    print("--- modificadores de setor OK ---")


def test_folders():
    # O esqueleto é garantido em TODO host: é o que torna o jogo aprendível.
    for seed in range(12):
        st = new_game(seed, sector=(seed % 5) + 1)
        for host in st.net.values():
            faltando = [d for d in fsmod.CORE_DIRS if d not in host.fs.children]
            ok(not faltando, f"pastas: seed {seed} host {host.label} tem o esqueleto fixo")

    st = new_game(4, sector=3)
    host = st.net["GATE"]
    users = host.fs.children["users"]
    ok(users.is_dir and len(users.children) >= 1, "pastas: /users tem ao menos um login")
    for nome, casa in users.children.items():
        ok(casa.is_dir, f"pastas: /users/{nome} é uma pasta")
        ok("notes.txt" in casa.children and ".profile" in casa.children,
           f"pastas: /users/{nome} tem o conteúdo pessoal")
        ok(nome == nome.lower() and " " not in nome, f"pastas: login '{nome}' é um login")

    # Os nomes de usuário variam entre hosts (procedural, não fixo).
    nomes = set()
    for h in st.net.values():
        nomes |= set(h.fs.children["users"].children)
    ok(len(nomes) > 1, "pastas: logins variam pela rede")

    # Pastas de sabor: aleatórias, mas só de um conjunto conhecido.
    extras = set()
    for seed in range(15):
        for h in new_game(seed).net.values():
            extras |= set(h.fs.children) - set(fsmod.CORE_DIRS)
    conhecidas = {n for n, _f in fsmod._EXTRA_DIRS}
    ok(extras and extras <= conhecidas, "pastas: as aleatórias saem do conjunto previsto")
    ok(len(extras) > 1, "pastas: mais de uma pasta de sabor aparece pela rede")

    # Determinismo continua valendo com as pastas novas.
    a, b = new_game(55, sector=2), new_game(55, sector=2)
    ok(list(a.net["GATE"].fs.children) == list(b.net["GATE"].fs.children),
       "pastas: mesma seed = mesmas pastas")
    print("--- pastas OK ---")


def test_router_and_telemetry():
    from coldboot.hardware import Rig

    # O sinal do roteador tem que FAZER algo: ele mexe no trace passivo.
    ruim = new_game(1); ruim.rig = Rig(router="net_dsl")
    bom = new_game(1); bom.rig = Rig(router="net_husky_x")
    ok(economy.creep_mult(ruim) > economy.creep_mult(bom),
       "rede: roteador melhor deixa o trace correr mais devagar")
    ok(hardware.derived(bom.rig).signal > hardware.derived(ruim.rig).signal,
       "rede: roteador melhor = mais sinal")

    # Telemetria: pura, previsível, e reflete o que o jogo está fazendo.
    rig = Rig(mobo="mb_c3", cpu="cpu_s3", ram=["ram_d5_32"], gpus=["gpu_a"],
              psu="psu_850", cooler="cool_fans", router="net_husky")
    parado = hardware.telemetry(rig, mining=False)
    minerando = hardware.telemetry(rig, mining=True)
    ok(minerando.cpu_pct > parado.cpu_pct, "hud: minerar acende a CPU")
    ok(minerando.gpu_pct[0] > parado.gpu_pct[0], "hud: minerar acende a GPU")
    ok(len(minerando.gpu_pct) == 1, "hud: uma leitura por GPU instalada")
    ok(minerando.ram_used_gb > parado.ram_used_gb, "hud: minerar come a RAM do rig")
    ok(minerando.ram_used_gb <= minerando.ram_total_gb, "hud: RAM usada nunca passa da total")
    ok(minerando.watts > parado.watts and minerando.psu_pct > parado.psu_pct,
       "hud: minerar puxa mais da fonte")
    ok(0 <= minerando.psu_pct <= 100, "hud: a fonte fica em 0..100%")
    ok(minerando.signal == 3, "hud: o sinal vem do roteador")

    # Throttle aparece na telemetria.
    quente = hardware.telemetry(rig, mining=True, throttled=True)
    ok(quente.cpu_pct < minerando.cpu_pct, "hud: em throttle a CPU cai")
    ok(quente.gpu_pct[0] < minerando.gpu_pct[0], "hud: em throttle a GPU cai")

    # Sem GPU, sem leitura de GPU.
    ok(hardware.telemetry(Rig(), mining=True).gpu_pct == [], "hud: rig sem GPU não lista GPU")

    # Duas GPUs: a placa X9 tem 3 slots PCIe.
    duas = Rig(mobo="mb_x9", cpu="cpu_s4", ram=["ram_d6_64"], gpus=["gpu_a", "gpu_b"],
               psu="psu_1200", cooler="cool_liquid")
    ok(len(hardware.telemetry(duas, mining=True).gpu_pct) == 2, "hud: lista as duas GPUs")
    ok(hardware.derived(duas).hashrate > hardware.derived(rig).hashrate,
       "hw: duas GPUs somam hashrate")
    ok(hardware.derived(duas).pcie_used == 2, "hw: conta os slots PCIe usados")

    # Slots PCIe são finitos: a placa B2 só tem um.
    uma = Rig(mobo="mb_b2", cpu="cpu_s2", ram=["ram_d4_8"], gpus=["gpu_a"], psu="psu_850")
    ok(not hardware.can_install(uma, hardware.CATALOG["gpu_a"])[0],
       "hw: sem slot PCIe livre a segunda GPU é rejeitada")

    # Trocar para uma placa com menos PCIe descarta a GPU sobrando.
    volta = Rig(mobo="mb_x9", cpu="cpu_s4", ram=[], gpus=["gpu_a", "gpu_b"], psu="psu_1200")
    avisos = hardware.install(volta, hardware.CATALOG["mb_b2"])
    ok(len(volta.gpus) == 1, "hw: placa com menos PCIe descarta a GPU sobrando")
    ok(any("PCIe" in a for a in avisos), "hw: e avisa que descartou")

    # O HUD do rig mostra as peças por nome.
    st = new_game(1); st.rig = duas
    painel = render_rig(st).plain
    ok(hardware.CATALOG["cpu_s4"].name in painel, "hud: o painel RIG nomeia a CPU")
    ok(hardware.CATALOG["gpu_b"].name in painel, "hud: o painel RIG nomeia cada GPU")
    ok(hardware.CATALOG["net_dsl"].name in painel or "Husky" in painel,
       "hud: o painel RIG nomeia o roteador")
    ok("TEMP" in painel, "hud: a temperatura fica no painel do RIG")

    # E o painel de status mostra os medidores.
    st.processes.append("miner")
    med = render_status(st).plain
    for rotulo in ("TRACE", "CPU", "RAM", "GPU 0", "GPU 1", "PSU", "SIGNAL", "HOST", "SECTOR"):
        ok(rotulo in med, f"hud: o painel de status mostra {rotulo}")
    print("--- roteador/telemetria OK ---")


def test_cart():
    st = new_game(2)
    st.wallet = 2000.0

    # Carrinho vazio.
    ok(economy.preview_cart(st, []).total == 0, "carrinho: vazio custa zero")
    ok(not economy.checkout(st, [])[0], "carrinho: não dá para fechar vazio")

    # A ORDEM importa: placa nova primeiro, depois a RAM dela.
    certo = economy.preview_cart(st, ["mb_b2", "ram_d4_8"])
    ok(certo.ok, "carrinho: placa + RAM da geração nova passa na ordem certa")
    errado = economy.preview_cart(st, ["ram_d4_8", "mb_b2"])
    ok(not errado.ok, "carrinho: a RAM antes da placa não passa")
    ok(not errado.lines[0].ok and "DDR" in errado.lines[0].reason,
       "carrinho: e diz exatamente qual peça não entra")

    # Soma e saldo.
    ok(certo.total == hardware.CATALOG["mb_b2"].price + hardware.CATALOG["ram_d4_8"].price,
       "carrinho: soma os preços")
    pobre = new_game(2); pobre.wallet = 10.0
    ok(not economy.preview_cart(pobre, ["mb_b2"]).affordable,
       "carrinho: sem saldo não fecha")

    # Checkout aplica tudo de uma vez.
    ok(economy.checkout(st, ["mb_b2", "ram_d4_8"])[0], "carrinho: checkout aceita o válido")
    ok(st.rig.mobo == "mb_b2" and "ram_d4_8" in st.rig.ram,
       "carrinho: checkout instala o carrinho inteiro")
    ok(abs(st.wallet - (2000.0 - certo.total)) < 0.01, "carrinho: checkout cobra o total")

    # Ou vai tudo, ou não vai nada.
    antes = (st.rig.mobo, list(st.rig.ram), st.wallet)
    ok(not economy.checkout(st, ["cool_fans", "gpu_b"])[0],
       "carrinho: um item ruim recusa o carrinho inteiro")
    ok((st.rig.mobo, st.rig.ram, st.wallet) == antes,
       "carrinho: recusado, nada é cobrado nem instalado")

    # Duas GPUs no mesmo carrinho, numa placa que só tem um slot.
    st2 = new_game(2); st2.wallet = 5000.0
    economy.checkout(st2, ["mb_b2", "psu_850"])
    duas = economy.preview_cart(st2, ["gpu_a", "gpu_a"])
    ok(duas.lines[0].ok and not duas.lines[1].ok,
       "carrinho: a segunda GPU não cabe e o carrinho sabe disso")
    print("--- carrinho OK ---")


def test_tutorial_unit():
    from coldboot import tutorial as tut

    st = tut.build_sector_zero()
    ok(st.sector == 0, "tutorial: é o setor 0")
    ok(set(st.net) == {"GATE", "ALVO"}, "tutorial: rede mínima e fixa")
    ok(st.net["GATE"].fs.children["leiame.txt"], "tutorial: tem o que a 1ª tarefa pede")
    ok("moeda_treino.dat" in st.net["GATE"].fs.children["cofre_treino"].children,
       "tutorial: tem o item que a tarefa do take pede")
    # Duas montagens são iguais: nada procedural no treino.
    ok(list(tut.build_sector_zero().net) == list(st.net), "tutorial: não é procedural")

    # O roteiro cobre os verbos que ele promete, e todos existem no parser.
    verbos = [s.verb for s in tut.STEPS]
    ok(verbos == ["ls", "cat", "cd", "take", "use", "scan", "hack"],
       "tutorial: ensina os verbos na ordem de dificuldade")
    ok(all(v in parser._SHELL for v in verbos), "tutorial: só ensina comando que existe")
    ok(all(s.prompt and s.done for s in tut.STEPS), "tutorial: todo passo pede e confirma")

    # Dicas: uma vez cada, e só as conhecidas.
    st2 = new_game(1)
    ok(tut.hint_for(st2, "hot") is not None, "dica: sai na primeira vez")
    ok(tut.hint_for(st2, "hot") is None, "dica: não se repete")
    ok(tut.hint_for(st2, "nao_existe") is None, "dica: chave desconhecida não quebra")
    ok(st2.flags.get("hint_hot"), "dica: fica marcada no estado")
    # As dicas atravessam o setor (não se repetem a cada incursão).
    prox = next_run(st2, won=True)
    ok(prox.flags.get("hint_hot"), "dica: já vista não volta no setor seguinte")
    print("--- tutorial (unidade) OK ---")


def test_cipher():
    from coldboot.cipher import CipherSession, make_session

    # Sessão determinística por seed.
    s1 = CipherSession(rng=random.Random(7))
    s2 = CipherSession(rng=random.Random(7))
    ok(s1.secret == s2.secret, "cipher: mesma seed = mesmo código secreto")

    sess = CipherSession(length=4, alphabet="123456", max_guesses=3, rng=random.Random(1))
    ok(len(sess.secret) == 4 and all(c in "123456" for c in sess.secret),
       "cipher: código secreto respeita tamanho e alfabeto")

    # Entrada inválida não consome tentativa.
    res = sess.submit("abcd")
    ok(res.kind == "invalid", "cipher: fora do alfabeto é inválido")
    ok(sess.guesses_left == 3, "cipher: palpite inválido não consome tentativa")
    res = sess.submit("12")
    ok(res.kind == "invalid", "cipher: tamanho errado é inválido")

    # Acerto exato de tudo vence na hora.
    win_sess = CipherSession(length=4, alphabet="123456", max_guesses=3, rng=random.Random(1))
    secret = win_sess.secret
    res = win_sess.submit(secret)
    ok(res.kind == "win" and res.exact == 4, "cipher: acertar o código secreto vence")
    ok(win_sess.finished and win_sess.won, "cipher: sessão termina vencida")

    # Feedback exato/parcial é coerente (mastermind clássico).
    fb_sess = CipherSession(length=4, alphabet="123456", max_guesses=5, rng=random.Random(1))
    fb_sess.secret = "1234"
    res = fb_sess.submit("1243")
    ok(res.exact == 2 and res.partial == 2, "cipher: feedback conta exatos e parciais certo")

    # Esgotar tentativas sem acertar perde, sem prêmio.
    lose_sess = CipherSession(length=4, alphabet="123456", max_guesses=2, rng=random.Random(2))
    lose_sess.secret = "1111"
    r1 = lose_sess.submit("2222")
    ok(r1.kind == "progress", "cipher: primeira tentativa errada continua")
    r2 = lose_sess.submit("3333")
    ok(r2.kind == "lose", "cipher: tentativas esgotadas sem acertar perde")
    ok(not lose_sess.won, "cipher: sessão perdida não fica marcada como vencida")

    # Depois de terminada, submissões seguintes só ecoam o resultado final.
    r3 = lose_sess.submit("1111")
    ok(r3.kind == "lose", "cipher: sessão encerrada não aceita mais palpites")

    # make_session escala o alfabeto com o setor, sem nunca passar de 9 dígitos.
    ok(len(make_session(1, random.Random(1)).alphabet) == 6,
       "cipher: setor 1 usa alfabeto base de 6 dígitos")
    ok(len(make_session(40, random.Random(1)).alphabet) == 9,
       "cipher: setor alto tampa em 9 dígitos")
    print("--- minigame de cifra OK ---")


def test_puzzle():
    st = new_game(11, sector=3)
    code = st.puzzle_code
    ok(code.count("-") == 2 and len(code) == 14, "puzzle: código tem 3 grupos de 4")
    parts = code.split("-")
    ok(all(len(p) == 4 for p in parts), "puzzle: cada fragmento tem 4 caracteres")

    # Determinismo: mesma seed/setor = mesmo código.
    ok(new_game(11, sector=3).puzzle_code == code, "puzzle: código determinístico por seed")
    ok(new_game(12, sector=3).puzzle_code != code, "puzzle: seed diferente = código diferente")

    # O fragmento 1 está embutido na âncora de .history do GATE.
    history = st.net["GATE"].fs.children["usr"].children["guest"].children[".history"]
    ok(parts[0] in history.content, "puzzle: fragmento 1 está no .history do GATE")

    # Os fragmentos 2 e 3 estão em /tmp de outros hosts.
    achados = []
    for n in st.net.values():
        tmp = n.fs.children.get("tmp")
        if not tmp:
            continue
        for child in tmp.children.values():
            if child.content and "fragment" in child.content:
                achados.append(child.content)
    ok(len(achados) >= 2, "puzzle: fragmentos 2 e 3 plantados em /tmp de outros hosts")
    ok(any(parts[1] in c for c in achados), "puzzle: fragmento 2 existe em algum /tmp")
    ok(any(parts[2] in c for c in achados), "puzzle: fragmento 3 existe em algum /tmp")

    # check() é case/espaço-insensível.
    ok(puzzle.check(st, code), "puzzle: código certo é aceito")
    ok(puzzle.check(st, code.lower()), "puzzle: aceita minúsculo")
    ok(puzzle.check(st, f"  {code}  "), "puzzle: ignora espaços nas pontas")
    ok(not puzzle.check(st, "NADA-A-VER"), "puzzle: código errado é rejeitado")

    # Rede minúscula (fallback sem outros hosts) não quebra a geração.
    from coldboot.state import GameState, NetNode
    from coldboot.procgen.filesystem import generate_filesystem
    diminuta = GameState()
    diminuta.seed = 1
    gate = NetNode(id="GATE", label="GATE", col=0, row=0, links=[], state="compromised", depth=0)
    gate.fs = generate_filesystem(random.Random(1), "GATE", 0, is_core=True)
    diminuta.net = {"GATE": gate}
    puzzle.place(random.Random(1), diminuta)
    ok(diminuta.puzzle_code, "puzzle: rede de 1 host só ainda gera um código")
    print("--- puzzle de código OK ---")


def test_botnet():
    from coldboot.hardware import Rig

    # Capacidade escala com núcleos da CPU (cores // 3).
    ok(economy.botnet_capacity(Rig()) == 0, "botnet: CPU inicial não tem slot nenhum")
    ok(economy.botnet_capacity(Rig(cpu="cpu_s2")) == 2, "botnet: CPU média dá 2 slots")
    ok(economy.botnet_capacity(Rig(cpu="cpu_s4")) == 8, "botnet: CPU de topo dá 8 slots")

    # Renda escala com o setor, mas é modesta (não substitui minerar de verdade).
    ok(economy.botnet_income_rate(5) > economy.botnet_income_rate(1),
       "botnet: setor mais fundo rende mais por script")
    ok(economy.botnet_income_rate(1) < 1.0, "botnet: renda por script é modesta")

    # Um tick sem nenhum script plantado não faz nada.
    st = new_game(1)
    bt = economy.botnet_tick(st)
    ok(bt.income == 0.0 and bt.lost == [], "botnet: sem scripts, tick não faz nada")

    # Plantar rende a cada tick e envelhece.
    st.botnet["GATE"] = 0
    wallet0 = st.wallet
    bt = economy.botnet_tick(st)
    ok(bt.income > 0 and st.wallet > wallet0, "botnet: script plantado rende por tick")
    ok(st.botnet["GATE"] == 1, "botnet: a idade do script sobe a cada tick")

    # Dentro da graça, o risco de descoberta é zero.
    st2 = new_game(1)
    st2.botnet["GATE"] = 0
    achou_perda = False
    for _ in range(economy.BOTNET_GRACE_TICKS):
        bt = economy.botnet_tick(st2, rng=random.Random(0))
        if bt.lost:
            achou_perda = True
    ok(not achou_perda, "botnet: dentro da graça, nunca é descoberto")

    # Passada a graça, com uma seed que force o pior caso, acaba sendo achado.
    st3 = new_game(1)
    st3.botnet["GATE"] = 0
    rng = random.Random(2)
    trace0 = st3.trace
    perdido = False
    for _ in range(200):
        bt = economy.botnet_tick(st3, rng=rng)
        if bt.lost:
            perdido = True
            break
    ok(perdido, "botnet: passada a graça, acaba sendo descoberto (probabilisticamente)")
    ok("GATE" not in st3.botnet, "botnet: script descoberto some da lista")
    ok(st3.trace > trace0, "botnet: perder um script custa trace")

    # O risco por tick nunca passa do teto.
    idade_enorme = economy.BOTNET_GRACE_TICKS + 1000
    ok(economy.botnet_risk(idade_enorme) == economy.BOTNET_RISK_CAP,
       "botnet: risco satura no teto, não cresce sem limite")

    # botnet_risk: zero dentro da graça, positivo e crescente depois dela.
    ok(economy.botnet_risk(economy.BOTNET_GRACE_TICKS) == 0.0,
       "botnet: risco ainda zero no limite exato da graça")
    ok(economy.botnet_risk(economy.BOTNET_GRACE_TICKS + 1) > 0.0,
       "botnet: risco aparece um tick depois da graça")
    ok(economy.botnet_risk(economy.BOTNET_GRACE_TICKS + 5) >
       economy.botnet_risk(economy.BOTNET_GRACE_TICKS + 1),
       "botnet: risco cresce com a idade, passada a graça")
    print("--- botnet (unidade) OK ---")


def test_spoof_script():
    item = loot.generate_item(random.Random(3), depth=2, kind="spoof")
    ok(item.item["kind"] == "spoof", "spoof: kind forçado gera o item pedido")
    ok(25 <= item.item["amount"] <= 45, "spoof: alívio de trace no intervalo esperado")
    ok(bool(item.item["fake_user"]), "spoof: vem com um nome de usuário para se passar por")
    ok(item.item["fake_user"] in item.content, "spoof: o conteúdo do arquivo cita o usuário fingido")
    ok(item.name.endswith(".bat") or item.name.endswith(".sh"),
       "spoof: nome de arquivo é um script (.bat ou .sh)")
    print("--- script de disfarce (loot) OK ---")


def test_backdoor_key():
    item = loot.generate_item(random.Random(4), depth=2, kind="backdoor")
    ok(item.item["kind"] == "backdoor", "backdoor: kind forçado gera o item pedido")
    ok("CORE" in item.content, "backdoor: conteúdo avisa que não funciona no CORE")
    print("--- backdoor.key (loot) OK ---")


def test_theme():
    ok(theme.resolve("grey58", False) == "grey58", "tema: sem alto contraste não mexe")
    ok(theme.resolve("grey58", True) != "grey58", "tema: cinza vira legível no contraste")
    ok("bold" in theme.resolve("green3", True), "tema: alto contraste engrossa o texto")
    # Estilos compostos continuam válidos (fundo e reverse sobrevivem).
    ok(theme.resolve("bold black on green3", True) == "bold black on bright_green",
       "tema: estilo composto preserva a estrutura")
    ok(theme.resolve("bold red reverse", True).endswith("reverse"),
       "tema: modificadores não viram cor")
    ok(theme.resolve("", True) == "", "tema: estilo vazio não quebra")
    # Nenhum cinza sobra na paleta de alto contraste.
    ok(not any("grey" in theme.resolve(s, True)
               for s in ("grey30", "grey42", "grey58", "bold grey58")),
       "tema: alto contraste elimina os cinzas")
    print("--- tema OK ---")


def static_text(node, selector):
    """O rich.Text que um Static recebeu — o Textual não reexpõe o original."""
    return getattr(node.query_one(selector), "_Static__content")


async def submit(pilot, app, text):
    app.query_one("#prompt").value = text
    await pilot.press("enter")
    await pilot.pause()


async def test_app(tmp: Path):
    # seed fixa => run determinística. boot=False pula a animação do KRYOS/OS
    # (ela tem teste próprio); os caminhos vão para uma pasta temporária para
    # o teste nunca tocar no ~/.coldboot de quem roda.
    app = ColdBootApp(seed=42, boot=False, tutorial_on=False,
                      save_path=tmp / "save.json", settings_path=tmp / "settings.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        ok(app.query_one("#status") is not None, "app: painel status")
        ok(app.query_one("#map") is not None, "app: painel mapa")
        ok(app.query_one("#narrative") is not None, "app: painel narrativa")
        ok(app.query_one("#prompt") is not None, "app: prompt")

        # --- Autocompletar com Tab ---
        inp = app.query_one("#prompt")
        inp.value = "ca"
        await pilot.press("tab")
        await pilot.pause()
        ok(inp.value == "cat ", "tab: completa verbo único (ca -> cat)")
        inp.value = "cat re"
        await pilot.press("tab")
        await pilot.pause()
        ok(inp.value.startswith("cat readme.txt"), "tab: completa arquivo do cwd")
        inp.value = "c"
        await pilot.press("tab")
        await pilot.pause()
        ok(inp.value == "c", "tab: múltiplos candidatos não força escolha")
        inp.value = ""

        # --- Fantasma do autocomplete (texto apagado após o cursor) ---
        sug = await inp.suggester.get_suggestion("ca")
        ok(sug == "cat", "fantasma: sugere o verbo completo")
        ok(await inp.suggester.get_suggestion("cat re") == "cat readme.txt",
           "fantasma: sugere o arquivo do cwd")
        ok(await inp.suggester.get_suggestion("xyzzy") is None,
           "fantasma: sem candidato não sugere nada")
        ok(await inp.suggester.get_suggestion("cat ") is None,
           "fantasma: não sugere com o argumento vazio")
        # A seta → aceita o fantasma (comportamento nativo do Input).
        inp.value = ""
        await pilot.press("c", "a")
        await pilot.pause()
        ok(inp._suggestion == "cat", "fantasma: aparece enquanto digita")
        await pilot.press("right")
        await pilot.pause()
        ok(inp.value == "cat", "fantasma: seta direita aceita a sugestão")
        inp.value = ""

        # --- Historico com as setas up/down ---
        await submit(pilot, app, "pwd")
        await submit(pilot, app, "whoami")
        await pilot.press("up")
        await pilot.pause()
        ok(inp.value == "whoami", "historico: seta-cima traz o ultimo comando")
        await pilot.press("up")
        await pilot.pause()
        ok(inp.value == "pwd", "historico: seta-cima de novo volta mais um")
        await pilot.press("down")
        await pilot.pause()
        ok(inp.value == "whoami", "historico: seta-baixo anda para frente")
        await pilot.press("down")
        await pilot.pause()
        ok(inp.value == "", "historico: seta-baixo no fim volta para a linha nova")
        # Um rascunho em digitação não se perde ao passear pelo histórico.
        inp.value = "rascunho"
        await pilot.press("up")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        ok(inp.value == "rascunho", "historico: o rascunho volta intacto")
        inp.value = ""
        # Repetição seguida não duplica.
        n0 = len(inp.history)
        await submit(pilot, app, "pwd")
        await submit(pilot, app, "pwd")
        ok(len(inp.history) == n0 + 1, "historico: comando repetido nao duplica")

        # --- help sai na tela (o alinhamento tem teste próprio, puro) ---
        app.narrative.speed_mult = 500.0      # atropela o teletype pendente
        await pilot.pause(0.6)
        app.narrative.clear_log()
        await submit(pilot, app, "help")
        await pilot.pause(0.6)
        txt = "\n".join(t for t, _s in app.narrative._printed)
        ok("cd <dir>" in txt and "kill <proc>" in txt, "help: lista os comandos na tela")
        ok("Esc" in txt, "help: ensina as teclas novas")

        # Filesystem (fixo) segue funcionando
        await submit(pilot, app, "cd /var/log")
        ok(app.state.cwd == ["var", "log"], "cmd: cd muda cwd")
        await submit(pilot, app, "cat auth.log")
        ok(app.state.flags.get("read_auth") is True, "cmd: cat dispara evento")
        tr0 = app.state.trace
        await submit(pilot, app, "cd /home/admin")
        ok(app.state.cwd == ["var", "log"], "cmd: cd trancado não move")
        ok(app.state.trace > tr0, "cmd: cd trancado sobe trace")

        # scan é trancado até achar /home/admin ou /etc/hosts — sem isso, não sobe trace.
        tr1 = app.state.trace
        await submit(pilot, app, "scan")
        ok(app.state.trace == tr1, "cmd: scan trancado não sobe trace nem revela nada")

        # Desbloqueado (aqui, direto no estado — o achado tem teste próprio), roda de fato.
        app.state.flags["scan_unlocked"] = True
        await submit(pilot, app, "scan")
        ok(app.state.trace > tr1, "cmd: scan desbloqueado sobe trace")
        ok(any(n.state == "fog" for n in app.state.net.values()), "névoa: ainda há nós ocultos")

        # hack de um vizinho revelado (evita o CORE p/ não vencer no teste)
        alvo = next(n for n in app.state.net.values()
                    if n.state == "discovered" and n.id != app.state.core_id)
        await submit(pilot, app, f"hack {alvo.id.lower()}")
        ok(app.mode == "combat" and app.combat is not None, "combate: inicia com hack")
        for _ in range(app.combat.total_rounds):
            await submit(pilot, app, app.combat.code)
        ok(app.mode == "explore", "combate: volta a explorar após vencer")
        ok(app.state.net[alvo.id].state == "compromised", "combate: nó comprometido")
        ok(app.state.location == alvo.id, "combate: pivota para o nó invadido")
        ok(app.state.current_fs() is app.state.net[alvo.id].fs, "fs: pivô troca o filesystem ativo")

        # --- Compra pelo terminal (a loja em pop-up tem teste próprio) ---
        await submit(pilot, app, "comprar cool_fans")
        ok(app.state.rig.cooler == "cool_stock", "loja: sem saldo não compra")
        app.state.wallet = 400.0
        await submit(pilot, app, "comprar cool_fans")
        ok(app.state.rig.cooler == "cool_fans", "loja: com saldo compra e instala")
        ok(app.state.wallet < 400.0, "loja: compra debita a carteira")
        await submit(pilot, app, "comprar gpu_a")
        ok(app.state.rig.gpus == [], "loja: GPU sem slot PCIe não instala")
        await submit(pilot, app, "comprar mb_b2")
        ok(app.state.rig.mobo == "mb_b2", "loja: troca de placa-mãe aplicada")
        ok(app.narrative.speed_mult == economy.tele_speed(app.state),
           "loja: upgrade reflete na velocidade do teletype")

        # kill / ps com o minerador
        app.state.processes.append("miner")
        await submit(pilot, app, "kill sshd")
        ok(app.state.processes == ["miner"], "kill: processo inexistente não mexe na lista")
        await submit(pilot, app, "kill miner")
        ok(app.state.processes == [], "kill: para o minerador")

        # Tab completa ids de peça e processos
        inp.value = "comprar cool_f"
        await pilot.press("tab")
        await pilot.pause()
        ok(inp.value.startswith("comprar cool_fans"), "tab: completa id de peça na loja")
        inp.value = ""

        # --- Chave de admin: burla o lock, gasta carga, pode inutilizar ---
        chave = ColdBootApp(seed=42, boot=False, tutorial_on=False,
                            save_path=tmp / "s2.json", settings_path=tmp / "cfg2.json")
        async with chave.run_test(size=(120, 40)) as p2:
            await p2.pause()
            alvo_fs = chave.state.net["GATE"].fs.children["home"].children["admin"]
            ok(alvo_fs.locked, "chave: alvo começa trancado")
            await submit(p2, chave, "cd /home/admin")
            ok(chave.state.cwd != ["home", "admin"], "chave: sem carga o lock segura")

            chave.state.adminkey = 2
            chave.state.flags.pop("admin_locked", None)
            random.seed(1)                       # controla o risco de inutilizar
            await submit(p2, chave, "cd /home/admin")
            ok(chave.state.cwd == ["home", "admin"], "chave: com carga o cd passa")
            ok(not alvo_fs.locked, "chave: alvo fica destrancado")
            ok(chave.state.adminkey == 1, "chave: uso gasta uma carga")

            # Com o admin invalidado, as cargas restantes não servem mais.
            chave.state.flags["admin_locked"] = True
            outro = next((c for c in chave.state.cwd_node().children.values() if c.locked), None)
            if outro is None:
                outro = chave.state.net["GATE"].fs.children["home"].children["admin"]
                outro.locked = True
            await submit(p2, chave, f"cat {outro.name}")
            ok(outro.locked and chave.state.adminkey == 1,
               "chave: admin invalidado não gasta nem destranca")

        # --- take / drop / use do buffer ---
        from coldboot.state import FSNode
        aqui = app.state.cwd_node()
        aqui.add(FSNode("scrambler_t1.bin", False, content="x",
                        item={"kind": "scrambler", "amount": 25}))
        await submit(pilot, app, "take scrambler_t1.bin")
        ok(len(app.state.inventory) == 1, "take: item vai para o buffer")
        ok("scrambler_t1.bin" not in app.state.cwd_node().children,
           "take: item sai da pasta")
        ok(app.state.ram_free == app.state.ram_total - hardware.ITEM_KB,
           "take: item carregado ocupa RAM do host")

        # O ponto do take: usar o item longe de onde ele foi achado.
        await submit(pilot, app, "cd /etc")
        app.state.trace = 60.0
        app.state.lockdown_level = 3
        t0 = app.state.trace
        await submit(pilot, app, "use scrambler_t1.bin")
        # Delta, não valor absoluto: o trace passivo corre em tempo real e uma
        # igualdade exata aqui é uma corrida contra o timer.
        ok(t0 - app.state.trace >= 24.0, "use: item do buffer funciona em outra pasta")
        ok(app.state.lockdown_level == 0, "use: scrambler reseta o cerco (reset_lockdown)")
        ok(app.state.inventory == [], "use: item consumido sai do buffer")
        ok(app.state.ram_free == app.state.ram_total, "use: consumir devolve a RAM")

        # drop devolve o item para a pasta e libera RAM.
        app.state.inventory.append({"name": "coolant_z.sh", "kind": "coolant", "amount": 20})
        await submit(pilot, app, "drop coolant_z.sh")
        ok(app.state.inventory == [], "drop: sai do buffer")
        ok("coolant_z.sh" in app.state.cwd_node().children, "drop: item cai na pasta atual")
        ok(app.state.cwd_node().children["coolant_z.sh"].item["kind"] == "coolant",
           "drop: o item largado continua sendo o mesmo item")
        await submit(pilot, app, "take coolant_z.sh")
        ok(len(app.state.inventory) == 1, "take: dá para pegar de volta o que largou")

        # Buffer cheio recusa (e o minerador come o espaço).
        app.state.inventory.clear()
        while app.state.can_hold():
            app.state.inventory.append({"name": "f.bin", "kind": "coolant", "amount": 1})
        n_cheio = len(app.state.inventory)
        aqui = app.state.cwd_node()
        aqui.add(FSNode("extra.bin", False, item={"kind": "coolant", "amount": 5}))
        await submit(pilot, app, "take extra.bin")
        ok(len(app.state.inventory) == n_cheio, "take: buffer cheio recusa o item")
        ok("extra.bin" in app.state.cwd_node().children, "take: recusado, o item fica na pasta")
        app.state.inventory.clear()

        # O minerador precisa caber no host.
        aqui.add(FSNode("miner_t.py", False, item={"kind": "miner"}))
        while app.state.can_hold():
            app.state.inventory.append({"name": "f.bin", "kind": "coolant", "amount": 1})
        await submit(pilot, app, "run miner_t.py")
        ok("miner" not in app.state.processes, "run: minerador não roda sem RAM no host")
        app.state.inventory.clear()
        await submit(pilot, app, "run miner_t.py")
        ok("miner" in app.state.processes, "run: com espaço, o minerador sobe")
        ok(app.state.ram_free < app.state.ram_total, "run: o minerador ocupa o host")

        # Minerador carregado no buffer também roda (senão o take viraria armadilha).
        await submit(pilot, app, "kill miner")
        await submit(pilot, app, "take miner_t.py")
        ok(app.state.find_item("miner_t.py") is not None, "take: dá para carregar o minerador")
        await submit(pilot, app, "run miner_t.py")
        ok("miner" in app.state.processes, "run: minerador do buffer também executa")
        # Segue rodando: o teste de ruído logo abaixo precisa dele vivo.

        # Minerando, o trace sobe sozinho (o custo novo da economia).
        t_ruido = app.state.trace
        app._economy_tick()
        ok(app.state.trace > t_ruido, "eco: o minerador rodando sobe o trace no tick do app")
        await submit(pilot, app, "kill miner")

        # --- Cartão + leitor ---
        from coldboot.procgen import loot as lootmod
        sala = app.state.cwd_node()
        lootmod.add_card_reader(random.Random(1), sala, 1)
        cofre = sala.children[lootmod.VAULT_NAME]
        ok(cofre.locked, "cofre: nasce trancado")
        # Sem cartão no bolso, o leitor não faz nada.
        await submit(pilot, app, f"use {lootmod.READER_NAME}")
        ok(cofre.locked, "cofre: o leitor sozinho não abre nada")
        # Cartão na pasta não serve: tem que estar com você.
        sala.add(FSNode("cartao_x.id", False, item={"kind": "keycard", "code": "7F-ORION-2A"}))
        await submit(pilot, app, "use cartao_x.id")
        ok(cofre.locked, "cofre: cartão no chão não abre o leitor")
        # Com o cartão no bolso: abre, e gasta o cartão.
        await submit(pilot, app, "take cartao_x.id")
        await submit(pilot, app, f"use cartao_x.id no {lootmod.READER_NAME}")
        ok(not cofre.locked, "cofre: cartão no leitor destranca (sem combate)")
        ok(app.state.find_item("cartao_x.id") is None, "cofre: o cartão é consumido")
        ok(app.mode == "explore", "cofre: abrir com cartão não dispara ICE")
        await submit(pilot, app, f"cd {lootmod.VAULT_NAME}")
        ok(app.state.cwd[-1] == lootmod.VAULT_NAME, "cofre: destrancado, dá para entrar")
        await submit(pilot, app, "cd /etc")

        # --- LOCKDOWN (Trace 100%) ---
        # vitória: rebate o Trace e sobe o nível de escalonamento
        app.state.trace = 100.0
        app._check_trace()
        await pilot.pause()
        ok(app.mode == "lockdown" and app.lockdown is not None, "lockdown: dispara em Trace 100%")
        lvl0 = app.state.lockdown_level
        for _ in range(app.lockdown.total):
            await submit(pilot, app, app.lockdown.code)
        ok(app.mode == "explore", "lockdown: vencer volta a explorar")
        ok(app.state.lockdown_level == lvl0 + 1, "lockdown: sobe o escalonamento")
        ok(app.state.trace < 100, "lockdown: rebate o Trace")

        # derrota: erro dispara a fala do vilão e o fim de jogo
        app.state.trace = 100.0
        app._check_trace()
        await pilot.pause()
        ok(app.mode == "lockdown", "lockdown: dispara de novo")
        await submit(pilot, app, "CODIGO_ERRADO")
        ok(app.mode == "dead", "lockdown: erro = fim de jogo")
        from coldboot.world import VILLAIN_LINES
        ok(app.villain_said in VILLAIN_LINES, "lockdown: vilão solta uma fala impactante")

        # --- Morrer não é o fim: `reboot` leva de volta à mesa, no setor 1 ---
        from textual.widgets import Button
        from coldboot.screens import DeskScreen
        app.state.wallet = 50.0
        app.state.rig.cooler = "cool_fans"
        app.state.sector = 6          # morreu fundo
        app.state.best_sector = 6
        seed_velha = app.state.seed
        await submit(pilot, app, "ls")
        ok(app.mode == "dead", "morto: comando comum não revive a sessão")
        await submit(pilot, app, "reboot")
        await pilot.pause()
        ok(isinstance(app.screen, DeskScreen), "reboot: morrer leva de volta à mesa")
        ok(app.paused, "mesa: nada corre enquanto ela está aberta")
        ok(app.state.sector == 1, "reboot: morrer derruba você para o setor 1")
        ok(app.state.best_sector == 6, "reboot: o recorde de setor fica registrado")
        ok(app.state.seed != seed_velha, "reboot: rede nova")
        ok(app.state.rig.cooler == "cool_fans", "reboot: o rig atravessa a morte")
        ok(app.state.wallet == 0.0, "reboot: morrer congelou a carteira")
        ok(app.state.runs_won == 0, "reboot: morte não pontua")
        ok(app.lockdown is None and app.combat is None, "reboot: sem sessão pendente")

        # Conectar pela mesa devolve o jogo.
        app.screen.query_one("#btn-connect", Button).press()
        await pilot.pause()
        ok(not isinstance(app.screen, DeskScreen), "mesa: conectar fecha a mesa")
        ok(app.mode == "explore" and not app.paused, "mesa: conectar volta a explorar")
        ok(app.query_one("#prompt").placeholder == i18n.t("app_placeholder_default"),
           "mesa: o prompt volta ao normal")
        await submit(pilot, app, "pwd")
        ok(app.mode == "explore", "mesa: aceita comandos de novo")

        # teletype: narra uma linha conhecida e espera a fila assíncrona drenar.
        # (O fluxo mesa→conectar limpa o log, então não dá para assumir que
        # sobrou algo de antes — testamos o mecanismo de entrega diretamente.)
        from textual.widgets import RichLog
        app.narrative.speed_mult = 500.0
        app.narrative.narrate("PROVA DE TELETYPE", "green3", 0.0)
        log = app.query_one("#narrative-log", RichLog)
        for _ in range(40):
            await pilot.pause(0.05)
            if any("PROVA DE TELETYPE" in "".join(seg.text for seg in ln._segments)
                   for ln in log.lines):
                break
        ok(any("PROVA DE TELETYPE" in "".join(seg.text for seg in ln._segments)
               for ln in log.lines), "teletype: a fila assíncrona entrega a linha")

    print("--- app OK ---")


async def test_boot_and_pause(tmp):
    from textual.widgets import Button, DataTable
    from coldboot.screens import BootScreen, DeskScreen, PauseScreen

    # --- Animação de boot do KRYOS/OS ---
    app = ColdBootApp(seed=7, boot=True, tutorial_on=False, save_path=tmp / "b.json",
                      settings_path=tmp / "bcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        ok(isinstance(app.screen, BootScreen), "boot: começa na tela do OS")
        ok(app.paused, "boot: o trace não corre durante o boot")
        tr = app.state.trace
        app._trace_creep()
        ok(app.state.trace == tr, "boot: trace congelado de verdade")
        await pilot.pause(1.0)     # o POST leva ~0.7s até a linha da memória
        texto = static_text(app.screen, "#boot-post").plain
        ok("KRYOS/OS" in texto, "boot: mostra o nome do OS fictício")
        ok("640K" in texto, "boot: roda o teste de memória")
        # Qualquer tecla pula a animação e cai no jogo.
        await pilot.press("space")
        await pilot.pause(0.3)
        ok(not isinstance(app.screen, BootScreen), "boot: tecla pula a animação")
        ok(not app.paused, "boot: sair do boot destrava o jogo")
        await pilot.pause(0.2)
        ok(app.query_one("#prompt").has_focus, "boot: o prompt recebe o foco depois")

    # --- Menu de pausa ---
    app = ColdBootApp(seed=7, boot=False, tutorial_on=False, save_path=tmp / "p.json",
                      settings_path=tmp / "pcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        ok(isinstance(app.screen, PauseScreen), "pausa: Esc abre o menu")
        ok(app.paused, "pausa: o jogo congela")

        # O tracer para de verdade — inclusive o creep e a economia.
        tr = app.state.trace
        app._trace_creep()
        app._economy_tick()
        ok(app.state.trace == tr, "pausa: o tracer congela")

        # Alto contraste liga pelo menu e repinta a tela do jogo.
        app.screen.query_one("#btn-contrast", Button).press()
        await pilot.pause()
        ok(app.settings.high_contrast, "pausa: alto contraste liga")
        ok(app.narrative.high_contrast, "pausa: a narrativa adota a paleta")
        ok(static_text(app, "#status").spans[0].style.startswith("bold"),
           "pausa: o painel de status repinta na hora")

        # Dificuldade cicla pelo menu.
        d0 = app.settings.difficulty
        app.screen.query_one("#btn-diff", Button).press()
        await pilot.pause()
        ok(app.settings.difficulty != d0, "pausa: dificuldade muda pelo menu")

        # Salvar pelo menu grava o arquivo e habilita o Carregar.
        ok(app.screen.query_one("#btn-load", Button).disabled, "pausa: sem save não dá pra carregar")
        app.screen.query_one("#btn-save", Button).press()
        await pilot.pause()
        ok((tmp / "p.json").exists(), "pausa: salvar pelo menu grava o arquivo")
        ok(not app.screen.query_one("#btn-load", Button).disabled,
           "pausa: carregar libera depois de salvar")

        # Esc fecha, destrava e persiste as preferências.
        await pilot.press("escape")
        await pilot.pause()
        ok(not isinstance(app.screen, PauseScreen), "pausa: Esc fecha o menu")
        ok(not app.paused, "pausa: fechar destrava o jogo")
        ok(settings_mod.load(tmp / "pcfg.json").high_contrast,
           "pausa: preferências persistem ao fechar")

        # --- Carregar restaura o estado salvo ---
        app.state.trace = 3.0
        app.state.wallet = 999.0
        await submit(pilot, app, "cd /var/log")
        await pilot.press("escape")
        await pilot.pause()
        app.screen.query_one("#btn-load", Button).press()
        await pilot.pause(0.3)
        ok(not isinstance(app.screen, PauseScreen), "carregar: fecha o menu")
        ok(app.state.wallet != 999.0, "carregar: restaura o estado salvo")
        ok(app.mode == "explore", "carregar: volta a explorar")

    # --- Salvar pelo terminal ---
    app = ColdBootApp(seed=7, boot=False, tutorial_on=False, save_path=tmp / "t.json",
                      settings_path=tmp / "tcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await submit(pilot, app, "save")
        ok((tmp / "t.json").exists(), "cmd: `save` grava pelo terminal")
        ok(savegame.load(tmp / "t.json").seed == 7, "cmd: o save do terminal é legível")

        # Não dá para salvar no meio do duelo (o combate não é serializado).
        alvo = next(n for n in app.state.net.values() if n.state == "discovered")
        await submit(pilot, app, f"hack {alvo.id.lower()}")
        ok(app.mode == "combat", "cmd: duelo começou")
        ok(app.save_game() is None, "save: recusa salvar durante o ICE")

        # Mas dá para pausar no meio do duelo — e o ICE congela junto.
        await pilot.press("escape")
        await pilot.pause()
        ok(isinstance(app.screen, PauseScreen), "pausa: Esc funciona durante o duelo")
        t0 = app.combat.time_left
        app._combat_tick()
        ok(app.combat.time_left == t0, "pausa: o relógio do ICE congela")
        ok(app.screen.query_one("#btn-save", Button).disabled,
           "pausa: o botão salvar fica travado no duelo")
        await pilot.press("escape")
        await pilot.pause()

    # --- Vencer: leva a carteira e pontua ---
    app = ColdBootApp(seed=7, boot=False, tutorial_on=False, save_path=tmp / "w.json",
                      settings_path=tmp / "wcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        from textual.widgets import Button
        from coldboot.world import sector_payout
        await pilot.pause()
        app.state.wallet = 120.0
        app.state.sector = 3
        premio = round(sector_payout(3) * app.state.mod_payout, 2)
        app._win()
        await pilot.pause()
        ok(isinstance(app.screen, DeskScreen), "vitória: setor limpo leva à mesa")
        ok(app.state.sector == 4, "vitória: avança um setor")
        ok(app.state.best_sector == 4, "vitória: o recorde acompanha")
        ok(abs(app.state.wallet - (120.0 + premio)) < 0.01,
           "vitória: o setor paga e você saca a carteira")
        ok(app.state.runs_won == 1, "vitória: o placar sobe")
        ok(app.paused, "vitória: na mesa nada corre")
        # Da mesa, conectar desce para o setor seguinte.
        app.screen.query_one("#btn-connect", Button).press()
        await pilot.pause()
        ok(app.mode == "explore" and app.state.sector == 4,
           "vitória: conectar desce para o setor novo")

    # --- A loja em pop-up: vitrine, carrinho, checkout ---
    app = ColdBootApp(seed=7, boot=False, tutorial_on=False, save_path=tmp / "sh.json",
                      settings_path=tmp / "shcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        from coldboot.screens import ShopScreen
        await pilot.pause()
        app.state.wallet = 2000.0
        await submit(pilot, app, "store")
        await pilot.pause()
        shop = app.screen
        ok(isinstance(shop, ShopScreen), "loja: `store` abre o pop-up")
        ok(app.paused, "loja: o jogo congela com a loja aberta")

        tabela = shop.query_one("#shop-table", DataTable)
        ok(tabela.row_count == len(hardware.parts_of("cpu")), "loja: a vitrine abre em CPU")
        shop.query_one("#cat-gpu", Button).press()
        await pilot.pause()
        ok(tabela.row_count == len(hardware.parts_of("gpu")), "loja: trocar de categoria troca a vitrine")

        # Adicionar ao carrinho não cobra nada.
        shop.query_one("#cat-cooler", Button).press()
        await pilot.pause()
        shop.cart.append("cool_fans")
        shop._refresh_cart()
        ok(app.state.wallet == 2000.0, "loja: pôr no carrinho não cobra")
        ok(app.state.rig.cooler == "cool_stock", "loja: nem instala")

        # Checkout cobra e instala.
        shop.query_one("#btn-checkout", Button).press()
        await pilot.pause()
        ok(app.state.rig.cooler == "cool_fans", "loja: checkout instala")
        ok(app.state.wallet < 2000.0, "loja: checkout cobra")
        ok(shop.cart == [], "loja: o carrinho esvazia depois do checkout")

        # Carrinho com dependência: placa + RAM da geração nova, na mesma cesta.
        shop.cart.extend(["mb_b2", "ram_d4_8"])
        shop.query_one("#btn-checkout", Button).press()
        await pilot.pause()
        ok(app.state.rig.mobo == "mb_b2" and "ram_d4_8" in app.state.rig.ram,
           "loja: cesta com placa + RAM nova passa de uma vez")

        # Carrinho inválido não cobra nada.
        saldo = app.state.wallet
        shop.cart.append("ram_d5_32")          # DDR5 numa placa DDR4
        shop.query_one("#btn-checkout", Button).press()
        await pilot.pause()
        ok(app.state.wallet == saldo, "loja: cesta inválida não cobra")
        ok(shop.cart == ["ram_d5_32"], "loja: e o carrinho fica como estava")
        shop.cart.clear()

        # Fechar devolve o jogo.
        shop.query_one("#btn-close", Button).press()
        await pilot.pause()
        ok(not isinstance(app.screen, ShopScreen), "loja: fechar sai do pop-up")
        ok(not app.paused, "loja: fechar destrava o jogo")
        ok(app.narrative.speed_mult == economy.tele_speed(app.state),
           "loja: o rig novo reflete no jogo na hora")

    # --- Tutorial: setor 0 roteirizado ---
    app = ColdBootApp(seed=7, boot=False, tutorial_on=True, save_path=tmp / "tu.json",
                      settings_path=tmp / "tucfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        ok(app.mode == "tutorial", "tutorial: primeira vez cai no treino")
        ok(app.state.sector == 0, "tutorial: é o setor 0")
        ok(app._tut_step == 0, "tutorial: começa no primeiro passo")

        # O roteiro só anda com o comando certo.
        await submit(pilot, app, "pwd")
        ok(app._tut_step == 0, "tutorial: comando errado não avança o roteiro")
        await submit(pilot, app, "ls")
        ok(app._tut_step == 1, "tutorial: o comando certo avança")

        # O trace não corre no treino: ninguém morre aprendendo.
        tr = app.state.trace
        app._trace_creep()
        ok(app.state.trace == tr, "tutorial: o trace não corre no treino")

        await submit(pilot, app, "cat leiame.txt")
        ok(app._tut_step == 2, "tutorial: cat avança")
        await submit(pilot, app, "cd cofre_treino")
        ok(app._tut_step == 3, "tutorial: cd avança")
        await submit(pilot, app, "take moeda_treino.dat")
        ok(app._tut_step == 4 and len(app.state.inventory) == 1, "tutorial: take avança e funciona")
        await submit(pilot, app, "use moeda_treino.dat")
        ok(app._tut_step == 5 and app.state.wallet > 0, "tutorial: use avança e credita")
        await submit(pilot, app, "scan")
        ok(app._tut_step == 6, "tutorial: scan avança")

        # O último passo é o hack — e termina o treino levando à mesa.
        await submit(pilot, app, "hack alvo")
        ok(app.mode == "combat", "tutorial: o hack abre um duelo de verdade")
        for _ in range(app.combat.total_rounds):
            await submit(pilot, app, app.combat.code)
        await pilot.pause(0.3)
        ok(app.settings.tutorial_done, "tutorial: concluir marca como visto")
        ok(settings_mod.load(tmp / "tucfg.json").tutorial_done,
           "tutorial: e persiste (é uma vez na vida, não por partida)")
        ok(isinstance(app.screen, DeskScreen), "tutorial: termina levando à mesa")
        ok(app.state.sector == 1, "tutorial: e o jogo de verdade começa no setor 1")

    # --- Tutorial: pulável, e não volta depois de visto ---
    app = ColdBootApp(seed=7, boot=False, tutorial_on=True, save_path=tmp / "tu2.json",
                      settings_path=tmp / "tu2cfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        ok(app.mode == "tutorial", "tutorial: aparece de novo para quem nunca viu")
        await submit(pilot, app, "pular")
        await pilot.pause(0.2)
        ok(app.settings.tutorial_done, "tutorial: pular também marca como visto")
        ok(isinstance(app.screen, DeskScreen), "tutorial: pular cai direto na mesa")

    app = ColdBootApp(seed=7, boot=False, tutorial_on=True, save_path=tmp / "tu3.json",
                      settings_path=tmp / "tu2cfg.json")     # settings de quem já viu
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        ok(app.mode == "explore", "tutorial: quem já viu não vê de novo")

    print("--- boot/pausa OK ---")


async def test_gameplay_additions(tmp: Path):
    """Os sistemas novos jogados de verdade: trace, scan gate, puzzle, botnet,
    cifra e script de disfarce."""
    from coldboot.app import CIPHER_TRACE_RELIEF, MAX_CIPHER_PER_SECTOR
    from coldboot.state import FSNode

    # --- Trace: sobe sozinho, sempre — ficar parado não reduz mais nada ---
    app = ColdBootApp(seed=21, boot=False, tutorial_on=False,
                      save_path=tmp / "qd.json", settings_path=tmp / "qdcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        st = app.state
        st.trace = 50.0
        for _ in range(10):
            antes = st.trace
            app._trace_creep()
            ok(st.trace >= antes, "gameplay: parado, o trace nunca cai sozinho")
        ok(st.trace > 50.0, "gameplay: parado, o trace ainda sobe com o tempo")

    # --- Comando `modifier`: consulta o modificador ativo do setor ---
    app = ColdBootApp(seed=21, boot=False, tutorial_on=False,
                      save_path=tmp / "mod.json", settings_path=tmp / "modcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.narrative.speed_mult = 500.0
        st = app.state
        ok(bool(st.modifier_id), "gameplay: new_game sempre atribui um modificador")
        await submit(pilot, app, "modifier")
        ok(app.mode == "explore", "gameplay: consultar o modificador não muda de modo")

    # --- Cifra: minigame de dedução, 3x por setor, reduz trace ao vencer ---
    app = ColdBootApp(seed=21, boot=False, tutorial_on=False,
                      save_path=tmp / "cph.json", settings_path=tmp / "cphcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.narrative.speed_mult = 500.0
        st = app.state
        st.trace = 60.0
        await submit(pilot, app, "cipher")
        ok(app.mode == "cipher", "gameplay: cipher abre o minigame")
        ok(st.cipher_uses == 1, "gameplay: abrir a cifra consome um uso do setor")
        await submit(pilot, app, "XYZ")  # fora do alfabeto: inválido, não conta tentativa
        ok(app.mode == "cipher", "gameplay: palpite inválido não sai do minigame")
        secret = app.cipher.secret
        tr0 = st.trace
        await submit(pilot, app, secret)
        ok(app.mode == "explore", "gameplay: acertar o código fecha o minigame")
        ok(st.trace <= tr0 - CIPHER_TRACE_RELIEF + 1.0, "gameplay: acertar a cifra reduz o trace")

        # Esgota os usos restantes do setor e confirma o bloqueio.
        for _ in range(MAX_CIPHER_PER_SECTOR - 1):
            await submit(pilot, app, "cipher")
            await submit(pilot, app, app.cipher.secret)
        ok(st.cipher_uses == MAX_CIPHER_PER_SECTOR, "gameplay: usos batem o teto do setor")
        await submit(pilot, app, "cipher")
        ok(app.mode == "explore", "gameplay: sem usos restantes, cipher recusa abrir")

    # --- Script de disfarge: `run` reduz trace e consome o item; `use` recusa ---
    app = ColdBootApp(seed=21, boot=False, tutorial_on=False,
                      save_path=tmp / "sp.json", settings_path=tmp / "spcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.narrative.speed_mult = 500.0
        st = app.state
        st.trace = 60.0
        st.inventory.append({"name": "masquerade_x9.bat", "kind": "spoof",
                              "amount": 30, "fake_user": "kvance"})
        await submit(pilot, app, "use masquerade_x9.bat")
        ok(any(it["name"] == "masquerade_x9.bat" for it in st.inventory),
           "gameplay: `use` num script de disfarce não o consome")
        ok(st.trace == 60.0, "gameplay: `use` num script de disfarce não reduz trace")
        await submit(pilot, app, "run masquerade_x9.bat")
        ok(st.trace <= 31.0, "gameplay: `run` no script de disfarce reduz o trace")
        ok(not any(it["name"] == "masquerade_x9.bat" for it in st.inventory),
           "gameplay: `run` consome o script de disfarce")

    # --- backdoor.key: pula o duelo (rede e pasta), recusa o CORE ---
    app = ColdBootApp(seed=17, boot=False, tutorial_on=False,
                      save_path=tmp / "bk.json", settings_path=tmp / "bkcfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.narrative.speed_mult = 500.0
        st = app.state

        # Sem estar no bolso, `use` recusa (mesmo padrão do keycard).
        folder_node = st.cwd_node()
        folder_node.add(FSNode("bk_x1.key", False, item={"kind": "backdoor"}))
        await submit(pilot, app, "use bk_x1.key")
        ok("bk_x1.key" in folder_node.children, "gameplay: backdoor sem take não se gasta")

        alvo = next(n for n in st.net.values() if n.state == "discovered")
        st.inventory.append({"name": "bk_net.key", "kind": "backdoor"})
        await submit(pilot, app, f"use bk_net.key on {alvo.id.lower()}")
        ok(alvo.state == "compromised", "gameplay: backdoor compromete o alvo de rede sem duelo")
        ok(app.combat is None, "gameplay: backdoor não abre nenhum duelo")
        ok(not any(it["name"] == "bk_net.key" for it in st.inventory),
           "gameplay: backdoor é consumido ao funcionar")

        # Não funciona no CORE do setor.
        st.inventory.append({"name": "bk_core.key", "kind": "backdoor"})
        core = st.net[st.core_id]
        core.state = "discovered"
        await submit(pilot, app, f"use bk_core.key on {core.id.lower()}")
        ok(core.state != "compromised", "gameplay: backdoor recusa o CORE do setor")
        ok(any(it["name"] == "bk_core.key" for it in st.inventory),
           "gameplay: recusado no CORE, o backdoor não se gasta")

        # Pasta trancada: mesmo item, mesmo comando, alvo diferente.
        locked = FSNode("vault_room", True, locked=True)
        st.cwd_node().add(locked)
        await submit(pilot, app, "use bk_core.key on vault_room")
        ok(not locked.locked, "gameplay: backdoor também destranca pasta, sem duelo")

    # --- Scan trancado; sem auto-revelação ao hackear; dois caminhos de desbloqueio ---
    app = ColdBootApp(seed=5, boot=False, tutorial_on=False,
                      save_path=tmp / "sc.json", settings_path=tmp / "sccfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.narrative.speed_mult = 500.0
        st = app.state
        ok(not st.flags.get("scan_unlocked"), "gameplay: scan começa trancado")
        tr0 = st.trace
        await submit(pilot, app, "scan")
        ok(st.trace == tr0, "gameplay: scan trancado não sobe trace nem revela nada")

        # Hackear um vizinho não revela os vizinhos DELE de graça.
        alvo = next(n for n in st.net.values() if n.state == "discovered")
        antes_dos_estados = {n.id: n.state for n in st.net.values()}
        await submit(pilot, app, f"hack {alvo.id.lower()}")
        for _ in range(app.combat.total_rounds):
            await submit(pilot, app, app.combat.code)
        depois = {n.id: n.state for n in st.net.values()}
        mudaram = {nid for nid in depois if depois[nid] != antes_dos_estados[nid]}
        ok(mudaram == {alvo.id}, "gameplay: comprometer um host não revela mais ninguém de graça")

        # Desbloqueia via /etc/hosts, se existir no GATE; senão via admin.
        gate_fs = st.net["GATE"].fs
        if "hosts" in gate_fs.children["etc"].children:
            await submit(pilot, app, "cd /etc")
            await submit(pilot, app, "cat hosts")
        else:
            await submit(pilot, app, "cd /home")
            await submit(pilot, app, "hack admin")
            for _ in range(app.combat.total_rounds if app.combat else 0):
                await submit(pilot, app, app.combat.code)
            await submit(pilot, app, "cd admin")
            await submit(pilot, app, "cat subnet.map")
        ok(st.flags.get("scan_unlocked"), "gameplay: um dos dois caminhos desbloqueia scan")
        await submit(pilot, app, "cd /")
        tr1 = st.trace
        await submit(pilot, app, "scan")
        ok(st.trace > tr1, "gameplay: desbloqueado, scan funciona de verdade")

    # --- decrypt: código errado, resolvido uma vez, recusa repetir ---
    app = ColdBootApp(seed=9, boot=False, tutorial_on=False,
                      save_path=tmp / "dc.json", settings_path=tmp / "dccfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.narrative.speed_mult = 500.0
        st = app.state
        code = st.puzzle_code
        st.trace = 70.0
        wallet0 = st.wallet
        await submit(pilot, app, "decrypt NADA-A-VER-0000")
        ok(not st.flags.get("puzzle_solved"), "gameplay: código errado não resolve")
        ok(st.wallet == wallet0, "gameplay: código errado não paga nada")
        await submit(pilot, app, f"decrypt {code}")
        ok(st.flags.get("puzzle_solved"), "gameplay: código certo resolve")
        ok(st.wallet > wallet0, "gameplay: resolver paga CRN")
        ok(st.trace < 70.0, "gameplay: resolver reduz o trace")
        wallet1 = st.wallet
        await submit(pilot, app, f"decrypt {code}")
        ok(st.wallet == wallet1, "gameplay: resolver de novo não paga de novo")

    # --- plant / unplant / botnet, pelo dispatcher de comandos de verdade ---
    app = ColdBootApp(seed=13, boot=False, tutorial_on=False,
                      save_path=tmp / "bn.json", settings_path=tmp / "bncfg.json")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.narrative.speed_mult = 500.0
        st = app.state
        await submit(pilot, app, "plant GATE")
        ok("GATE" not in st.botnet, "gameplay: sem capacidade (CPU fraca), plant recusa")

        st.wallet = 2000.0
        await submit(pilot, app, "comprar mb_c3")
        await submit(pilot, app, "comprar cpu_s3")
        await submit(pilot, app, "plant GATE")
        ok("GATE" in st.botnet, "gameplay: com capacidade, plant funciona")
        await submit(pilot, app, "botnet")

        wallet_antes = st.wallet
        for _ in range(5):
            app._economy_tick()
        ok(st.wallet > wallet_antes, "gameplay: botnet rende passivamente nos ticks")

        await submit(pilot, app, "unplant GATE")
        ok("GATE" not in st.botnet, "gameplay: unplant retira o script")
        await submit(pilot, app, "unplant GATE")  # idempotente, não deveria quebrar
        ok("GATE" not in st.botnet, "gameplay: unplant duas vezes não quebra")

    print("--- sistemas novos (trace/scan/puzzle/botnet/cifra/spoof) OK ---")


def main():
    test_units()
    test_hardware()
    test_economy()
    test_loot()
    test_timebonus()
    test_host_ram()
    test_mining_noise()
    test_ice_behaviors()
    test_meta_loop()
    test_keycard_world()
    test_sectors()
    test_sector_modifiers()
    test_folders()
    test_router_and_telemetry()
    test_cart()
    test_tutorial_unit()
    test_cipher()
    test_puzzle()
    test_botnet()
    test_spoof_script()
    test_backdoor_key()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_settings(tmp)
        test_savegame(tmp)
        test_theme()
        test_help()
        asyncio.run(test_app(tmp))
        asyncio.run(test_boot_and_pause(tmp))
        asyncio.run(test_gameplay_additions(tmp))
    print("\nTODOS OS TESTES PASSARAM [OK]")


if __name__ == "__main__":
    main()
