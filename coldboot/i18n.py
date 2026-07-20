"""i18n — catálogo de strings da interface, en/pt.

Só a UI muda de idioma: HUD, menus, mensagens de comando, tutorial. O MUNDO
(lore procedural — MOTD, logs, e-mails, provocações da IA, nomes de host/
usuário/corp, nomes de ICE e de boss) fica sempre em inglês, fixo, sem
alternância: é "a língua da corporação", não a do jogador. Essa linha é o que
mantém este catálogo do tamanho de "a UI do jogo" em vez de "o jogo inteiro"
(ver procgen/grammar.py, procgen/loot.py, combat.py).

Uso: `i18n.t("cd_locked", target=cmd.target, name=node.name)`. Sempre chamado
com o módulo qualificado (`i18n.t(...)`, nunca `from .i18n import t`) porque
o resto do código usa `t` como nome de variável local para buffers de Rich
Text — importar a função desqualificada colidiria por toda parte.

Chave ausente do catálogo devolve a própria chave: um `[chave_esquecida]`
aparecendo na tela é um sinal óbvio de bug, nunca um traceback. Locale ausente
numa entrada cai para EN (o padrão do jogo).
"""

from __future__ import annotations

LOCALES = ("en", "pt")
DEFAULT_LOCALE = "en"

_locale = DEFAULT_LOCALE


def set_locale(locale: str) -> None:
    """Chamado pelo app no boot, ao trocar no menu de pausa e ao carregar um save."""
    global _locale
    _locale = locale if locale in LOCALES else DEFAULT_LOCALE


def get_locale() -> str:
    return _locale


def t(key: str, **kwargs) -> str:
    """Resolve uma chave do catálogo no locale atual, com interpolação opcional."""
    entry = _CATALOG.get(key)
    if entry is None:
        return f"[{key}]"
    text = entry.get(_locale) or entry.get(DEFAULT_LOCALE) or key
    return text.format(**kwargs) if kwargs else text


# --------------------------------------------------------------------------- #
# Catálogo — chaves prefixadas por módulo/tela para nunca colidir.
# --------------------------------------------------------------------------- #
_CATALOG: dict[str, dict[str, str]] = {
    # app.py — chaves REUTILIZADAS em vários comandos (não duplicar!). Sempre
    # que uma dessas literais aparecer de novo em outro do_*, use a chave já
    # existente aqui em vez de criar uma nova.
    "app_placeholder_default": {
        "en": "type a command...",
        "pt": "digite um comando...",
    },
    "app_placeholder_code": {"en": "type the CODE...", "pt": "digite o CÓDIGO..."},
    "app_placeholder_lockdown": {
        "en": "COUNTER the code...",
        "pt": "REBATA o código...",
    },
    "app_placeholder_cipher": {
        "en": "type the code...",
        "pt": "digite o código...",
    },
    "app_hint_prefix": {"en": "[hint] ", "pt": "[dica] "},
    "app_border_status": {
        "en": "STATUS // NETWORK  ·  RIG  ·  MAP",
        "pt": "STATUS // REDE  ·  RIG  ·  MAPA",
    },
    "app_border_narrative": {"en": "// TRANSMISSION", "pt": "// TRANSMISSÃO"},
    # Hardware (can_install, install)
    "hw_ram_wrong_gen": {
        "en": "board only accepts {board_ddr} (part is {part_ddr})",
        "pt": "placa só aceita {board_ddr} (peça é {part_ddr})",
    },
    "hw_ram_no_slots": {
        "en": "no free RAM slots ({slots} occupied)",
        "pt": "sem slots de RAM livres ({slots} ocupados)",
    },
    "hw_cpu_wrong_socket": {
        "en": "incompatible socket (board {board_socket}, CPU {cpu_socket})",
        "pt": "socket incompatível (placa {board_socket}, CPU {cpu_socket})",
    },
    "hw_gpu_no_pcie": {
        "en": "board has no PCIe slots for GPU",
        "pt": "a placa não tem slot PCIe para GPU",
    },
    "hw_gpu_no_slots": {
        "en": "no free PCIe slots ({slots} occupied)",
        "pt": "sem slots PCIe livres ({slots} ocupados)",
    },
    "hw_psu_insufficient": {
        "en": "insufficient power supply: needs >{needed}W (has {available}W)",
        "pt": "fonte insuficiente: precisa >{needed}W (tem {available}W)",
    },
    "hw_power_exceeds_board": {
        "en": "exceeds board power limit",
        "pt": "excede o teto de potência da placa-mãe",
    },
    "hw_warn_ram_discarded": {
        "en": "incompatible RAM discarded with new board",
        "pt": "RAM incompatível com a nova placa foi descartada.",
    },
    "hw_warn_gpu_discarded": {
        "en": "GPU removed: no PCIe slot in new board",
        "pt": "GPU sem slot PCIe na nova placa foi removida.",
    },
    "hw_warn_cpu_discarded": {
        "en": "CPU removed: incompatible with new socket",
        "pt": "CPU incompatível com o novo socket foi removida.",
    },
    # Economy (preview_cart, checkout, buy)
    "eco_item_not_found": {
        "en": "part not found",
        "pt": "peça inexistente",
    },
    "eco_cart_empty": {
        "en": "cart is empty",
        "pt": "carrinho vazio.",
    },
    "eco_cart_insufficient_funds": {
        "en": "insufficient balance: total {total:.0f} {coin}, you have {balance:.2f}",
        "pt": "saldo insuficiente: total {total:.0f} {coin}, você tem {balance:.2f}.",
    },
    "eco_cart_line_error": {
        "en": "{name}: {reason}",
        "pt": "{name}: {reason}",
    },
    "eco_buy_not_found": {
        "en": "part '{part_id}' not found in shop",
        "pt": "peça '{part_id}' não existe na loja.",
    },
    "eco_buy_already_installed": {
        "en": "{name} is already installed in the rig",
        "pt": "{name} já está instalado no rig.",
    },
    "eco_buy_insufficient_funds": {
        "en": "insufficient balance: {name} costs {price:.0f} {coin} (you have {balance:.2f})",
        "pt": "saldo insuficiente: {name} custa {price:.0f} {coin} (você tem {balance:.2f}).",
    },
    "eco_buy_cannot_install": {
        "en": "cannot install {name}: {reason}",
        "pt": "não dá para instalar {name}: {reason}.",
    },
    "eco_buy_installed": {
        "en": "installed: {name} (-{price:.0f} {coin})",
        "pt": "instalado: {name} (-{price:.0f} {coin}).",
    },
    # Combat (combat.py)
    "combat_timeout": {
        "en": "TIME'S UP — ICE counter-attacks.",
        "pt": "TEMPO ESGOTADO — o ICE contra-ataca.",
    },
    "combat_barrier_broken": {
        "en": "BARRIER BROKEN — {name} fell.",
        "pt": "BARREIRA ROMPIDA — {name} caiu.",
    },
    "combat_hit": {
        "en": "HIT — layer breached.",
        "pt": "ACERTO — camada perfurada.",
    },
    "combat_invalid_string": {
        "en": "INVALID STRING — ICE marks you.",
        "pt": "STRING INVÁLIDA — o ICE te marca.",
    },
    # HUD (UI status panel labels)
    "hud_trace": {
        "en": "TRACE  ",
        "pt": "TRACE  ",
    },
    "hud_cpu": {
        "en": "CPU    ",
        "pt": "CPU    ",
    },
    "hud_ram": {
        "en": "   RAM {used:.1f}/{total}GB\n",
        "pt": "   RAM {used:.1f}/{total}GB\n",
    },
    "hud_gpu": {
        "en": "GPU {index}  ",
        "pt": "GPU {index}  ",
    },
    "hud_gpu_none": {
        "en": "GPU    ",
        "pt": "GPU    ",
    },
    "hud_gpu_none_msg": {
        "en": "(none installed)\n",
        "pt": "(nenhuma instalada)\n",
    },
    "hud_psu": {
        "en": "PSU    ",
        "pt": "PSU    ",
    },
    "hud_signal": {
        "en": "SIGNAL ",
        "pt": "SINAL  ",
    },
    "hud_host": {
        "en": "HOST   ",
        "pt": "HOST   ",
    },
    "hud_sector": {
        "en": "SECTOR {sector}  ",
        "pt": "SETOR {sector}  ",
    },
    "hud_conn_stable": {
        "en": "STABLE",
        "pt": "ESTÁVEL",
    },
    "hud_conn_unstable": {
        "en": "UNSTABLE",
        "pt": "INSTÁVEL",
    },
    "hud_conn_critical": {
        "en": "CRITICAL",
        "pt": "CRÍTICA",
    },
    "hud_conn_lost": {
        "en": "LOST",
        "pt": "PERDIDA",
    },
    "hud_ram_slots_free": {
        "en": "  ({free} free RAM slot(s))\n",
        "pt": "  ({free} slot(s) de RAM livre)\n",
    },
    "hud_pcie_none": {
        "en": "  (board has no PCIe)\n",
        "pt": "  (placa sem PCIe)\n",
    },
    "hud_pcie_slots_free": {
        "en": "  ({free} free PCIe slot(s))\n",
        "pt": "  ({free} slot(s) PCIe livre)\n",
    },
    "hud_temp": {
        "en": "TEMP ",
        "pt": "TEMP ",
    },
    "hud_throttle": {
        "en": "THROTTLE!",
        "pt": "THROTTLE!",
    },
    "hud_net_unmapped": {
        "en": "(network unmapped)",
        "pt": "(rede não mapeada)",
    },
    # Difficulty settings (settings.py)
    "diff_facil_label": {
        "en": "Easy",
        "pt": "Fácil",
    },
    "diff_normal_label": {
        "en": "Normal",
        "pt": "Normal",
    },
    "diff_dificil_label": {
        "en": "Hard",
        "pt": "Difícil",
    },
    "diff_facil_hint": {
        "en": "more time, and codes with readable words",
        "pt": "mais tempo e códigos com palavras legíveis",
    },
    "diff_normal_hint": {
        "en": "the original balance",
        "pt": "o equilíbrio original",
    },
    "diff_dificil_hint": {
        "en": "less time, longer codes",
        "pt": "menos tempo e códigos mais longos",
    },
    # BootScreen (screens.py)
    "boot_post_1": {
        "en": "Memory test ..... 640K OK",
        "pt": "Teste de memória ..... 640K OK",
    },
    "boot_post_2": {
        "en": "UNIBUS ..... OK",
        "pt": "Barramento UNIBUS ..... OK",
    },
    "boot_post_3": {
        "en": "RA81 drive ..... spin-up",
        "pt": "Unidade RA81 ..... spin-up",
    },
    "boot_post_4": {
        "en": "System clock ..... 03:14 17-JUL-1988",
        "pt": "Relógio de sistema ..... 03:14 17-JUL-1988",
    },
    "boot_post_5": {
        "en": "DEC LAT interface ..... ONLINE",
        "pt": "Interface DEC LAT ..... ONLINE",
    },
    "boot_post_6": {
        "en": "mounting /  ...",
        "pt": "montando /  ...",
    },
    "boot_post_7": {
        "en": "mounting /usr  ...",
        "pt": "montando /usr  ...",
    },
    "boot_post_8": {
        "en": "starting daemons: init syslogd getty coldboot",
        "pt": "iniciando daemons: init syslogd getty coldboot",
    },
    "boot_login_1": {
        "en": "login: guest",
        "pt": "login: guest",
    },
    "boot_login_2": {
        "en": "password: ",
        "pt": "password: ",
    },
    "boot_login_3": {
        "en": "password: ********",
        "pt": "password: ********",
    },
    "boot_login_4": {
        "en": "Last login: 12-NOV-1987 23:58 from console",
        "pt": "Último acesso: 12-NOV-1987 23:58 de console",
    },
    "boot_login_5": {
        "en": "ACCESS GRANTED — welcome, guest.",
        "pt": "ACESSO CONCEDIDO — bem-vindo, guest.",
    },
    "boot_hint_skip": {
        "en": "press any key to skip",
        "pt": "qualquer tecla pula",
    },
    "boot_loading_kernel": {
        "en": "loading kernel  ",
        "pt": "carregando kernel  ",
    },
    # PauseScreen (screens.py)
    "pause_title": {
        "en": "╪╪  SESSION PAUSED  ╪╪",
        "pt": "╪╪  SESSÃO PAUSADA  ╪╪",
    },
    "pause_subtitle": {
        "en": "Tracing is frozen.",
        "pt": "O rastreamento está congelado.",
    },
    "pause_btn_resume": {
        "en": "Resume",
        "pt": "Continuar",
    },
    "pause_btn_save": {
        "en": "Save game",
        "pt": "Salvar jogo",
    },
    "pause_btn_save_disabled": {
        "en": "Save game (not during ICE)",
        "pt": "Salvar jogo (não durante o ICE)",
    },
    "pause_btn_load": {
        "en": "Load saved game",
        "pt": "Carregar jogo salvo",
    },
    "pause_contrast_on": {
        "en": "on",
        "pt": "ligado",
    },
    "pause_contrast_off": {
        "en": "off",
        "pt": "desligado",
    },
    "pause_contrast_label": {
        "en": "High contrast: {state}",
        "pt": "Alto contraste: {state}",
    },
    "pause_diff_label": {
        "en": "Difficulty: {label}",
        "pt": "Dificuldade: {label}",
    },
    "pause_locale_label": {
        "en": "Language: {name}",
        "pt": "Idioma: {name}",
    },
    "pause_locale_en": {
        "en": "English",
        "pt": "Inglês",
    },
    "pause_locale_pt": {
        "en": "Portuguese",
        "pt": "Português",
    },
    "pause_btn_quit": {
        "en": "Quit game",
        "pt": "Sair do jogo",
    },
    "pause_saved_at": {
        "en": "Game saved to {path}.",
        "pt": "Jogo salvo em {path}.",
    },
    "pause_save_failed": {
        "en": "Save failed.",
        "pt": "Falha ao salvar.",
    },
    # DeskScreen (screens.py)
    "desk_title_dead": {
        "en": "╪╪  TRACED  ╪╪",
        "pt": "╪╪  RASTREADO  ╪╪",
    },
    "desk_sub_dead": {
        "en": "They froze your wallet and you crashed to sector 1. Rig left behind — record: sector {best}.",
        "pt": "Congelaram sua carteira e você caiu para o setor 1. O rig ficou — recorde: setor {best}.",
    },
    "desk_title_clear": {
        "en": "╪╪  SECTOR {sector} CLEAR  ╪╪",
        "pt": "╪╪  SETOR {sector} LIMPO  ╪╪",
    },
    "desk_sub_clear": {
        "en": "You cashed out and disconnected. Next run: sector {sector} (record: {best}).",
        "pt": "Você sacou o que ganhou e desconectou. Próxima descida: setor {sector} (recorde: {best}).",
    },
    "desk_title_idle": {
        "en": "╪╪  THE DESK  ╪╪",
        "pt": "╪╪  A MESA  ╪╪",
    },
    "desk_sub_idle": {
        "en": "Rig built, coffee cold. Sector {sector} waiting.",
        "pt": "Rig montado, café frio. Setor {sector} esperando.",
    },
    "desk_btn_shop": {
        "en": "Open shop",
        "pt": "Abrir a loja",
    },
    "desk_btn_connect": {
        "en": "Connect to sector {sector}",
        "pt": "Conectar ao setor {sector}",
    },
    "desk_btn_save": {
        "en": "Save",
        "pt": "Salvar",
    },
    "desk_wallet_label": {
        "en": "wallet: ",
        "pt": "carteira: ",
    },
    # ShopScreen (screens.py)
    "shop_cat_cpu": {
        "en": "CPU",
        "pt": "CPU",
    },
    "shop_cat_mobo": {
        "en": "Motherboard",
        "pt": "Placa-mãe",
    },
    "shop_cat_ram": {
        "en": "RAM",
        "pt": "RAM",
    },
    "shop_cat_gpu": {
        "en": "GPU",
        "pt": "GPU",
    },
    "shop_cat_psu": {
        "en": "Power supply",
        "pt": "Fonte",
    },
    "shop_cat_cooler": {
        "en": "Cooler",
        "pt": "Cooler",
    },
    "shop_cat_router": {
        "en": "Network",
        "pt": "Rede",
    },
    "shop_title": {
        "en": "GREY MARKET — anonymous delivery in the rack",
        "pt": "MERCADO CINZENTO — entrega anônima no rack",
    },
    "shop_col_part": {
        "en": "part",
        "pt": "peça",
    },
    "shop_col_price": {
        "en": "price",
        "pt": "preço",
    },
    "shop_col_status": {
        "en": "status",
        "pt": "situação",
    },
    "shop_status_installed": {
        "en": "installed",
        "pt": "instalado",
    },
    "shop_status_available": {
        "en": "available",
        "pt": "disponível",
    },
    "shop_cart_title": {
        "en": "CART",
        "pt": "CARRINHO",
    },
    "shop_cart_empty": {
        "en": "  (empty)",
        "pt": "  (vazio)",
    },
    "shop_cart_total_label": {
        "en": "total ",
        "pt": "total ",
    },
    "shop_cart_balance_label": {
        "en": "\nbalance ",
        "pt": "\nsaldo ",
    },
    "shop_btn_add": {
        "en": "Add",
        "pt": "Adicionar",
    },
    "shop_btn_remove": {
        "en": "Remove",
        "pt": "Remover",
    },
    "shop_btn_checkout": {
        "en": "Check out",
        "pt": "Finalizar compra",
    },
    "shop_btn_close": {
        "en": "Close",
        "pt": "Fechar",
    },
    "shop_msg_cart_wont_install": {
        "en": "in cart, but won't install: {reason}",
        "pt": "no carrinho, mas não instala: {reason}",
    },
    "shop_msg_added_to_cart": {
        "en": "{name} in cart.",
        "pt": "{name} no carrinho.",
    },
    "shop_msg_removed": {
        "en": "{name} removed.",
        "pt": "{name} removido.",
    },
    # Tutorial (tutorial.py)
    "tut_step_1_prompt": {
        "en": "You're inside a training machine. Start by looking around: type `ls`.",
        "pt": "Você está dentro de uma máquina de treino. Comece olhando o que tem aqui: digite `ls`.",
    },
    "tut_step_1_done": {
        "en": "That's a folder. A slash at the end means it's a directory.",
        "pt": "Isto é uma pasta. Barra no fim quer dizer que é um diretório.",
    },
    "tut_step_2_prompt": {
        "en": "Files are read with `cat`. Try `cat leiame.txt`.",
        "pt": "Arquivos se leem com `cat`. Tente `cat leiame.txt`.",
    },
    "tut_step_2_done": {
        "en": "That's how you read everything in this game: logs, emails, keys.",
        "pt": "É assim que se lê tudo neste jogo: logs, e-mails, chaves.",
    },
    "tut_step_3_prompt": {
        "en": "To enter a folder, use `cd <name>`. Try `cd cofre_treino`. (`cd ..` goes back.)",
        "pt": "Para entrar numa pasta, `cd <nome>`. Tente `cd cofre_treino`. (`cd ..` volta.)",
    },
    "tut_step_3_done": {
        "en": "The prompt at the bottom always shows where you are.",
        "pt": "O prompt lá embaixo sempre mostra onde você está.",
    },
    "tut_step_4_prompt": {
        "en": "There's an item here. `take moeda_treino.dat` loads it into your buffer — items use host memory, and occupied memory draws attention.",
        "pt": "Aqui tem um item. `take moeda_treino.dat` carrega ele no seu buffer — itens ocupam memória do host, e memória ocupada chama atenção.",
    },
    "tut_step_4_done": {
        "en": "Loaded. `inv` shows your buffer and how much memory is left.",
        "pt": "Carregado. `inv` mostra o buffer e quanta memória sobrou.",
    },
    "tut_step_5_prompt": {
        "en": "Items in your buffer work anywhere. Use with `use moeda_treino.dat`.",
        "pt": "Itens do buffer funcionam em qualquer lugar. Use com `use moeda_treino.dat`.",
    },
    "tut_step_5_done": {
        "en": "Credits in your wallet. That's how you buy hardware.",
        "pt": "Créditos na carteira. É assim que se paga o hardware.",
    },
    "tut_step_6_prompt": {
        "en": "Now the network. `scan` sweeps the subnet and reveals neighbors on the map — but it makes noise: watch the Trace climb.",
        "pt": "Agora a rede. `scan` varre a sub-rede e revela vizinhos no mapa — mas faz barulho: repare no Trace subindo.",
    },
    "tut_step_6_done": {
        "en": "Everything you do costs Trace. At 100% they close in.",
        "pt": "Cada coisa que você faz custa Trace. Em 100% o cerco fecha.",
    },
    "tut_step_7_prompt": {
        "en": "There's a host revealed on the map. Invade with `hack alvo` — it's a typing duel: copy the CODES before time runs out.",
        "pt": "Há um host revelado no mapa. Invada com `hack alvo` — vai começar um duelo de digitação: copie os CÓDIGOS antes que o tempo acabe.",
    },
    "tut_step_7_done": {
        "en": "That's how you take each host — and the CORE of each sector.",
        "pt": "É assim que se toma cada host — e o CORE de cada setor.",
    },
    "tut_hint_locked": {
        "en": "Locked folder. `hack <name>` faces down the ICE — or an admin key/keycard skips the fight if you have one.",
        "pt": "Pasta trancada. `hack <nome>` encara o ICE dela — ou uma chave de admin/cartão pula a briga, se você tiver.",
    },
    "tut_hint_hot": {
        "en": "Rig is over 82C: thermal throttle shuts down mining, text slows, and commands can abort. A cooler fixes it.",
        "pt": "O rig passou dos 82C: em throttle a mineração para, o texto desacelera e comandos podem abortar. Um refrigerante resolve.",
    },
    "tut_hint_trace_high": {
        "en": "Trace above 75%. At 100% it triggers LOCKDOWN: one mistake and the connection drops. A scrambler bounces the signal.",
        "pt": "Trace acima de 75%. Em 100% dispara o LOCKDOWN: um erro só e a conexão cai. Um scrambler rebate o sinal.",
    },
    "tut_hint_mining": {
        "en": "The miner is running: it generates CRN, but Trace climbs on its own while it's active. `kill miner` when it gets dangerous.",
        "pt": "O minerador está rodando: ele gera CRN, mas o Trace sobe sozinho enquanto ele estiver de pé. `kill miner` quando ficar perigoso.",
    },
    "tut_hint_ram_tight": {
        "en": "The host's memory is maxed out — and a memory-starved host notices you much more: mining noise doubles. `drop` something.",
        "pt": "A memória do host está no talo — e host sem memória repara muito mais em você: o ruído da mineração dobra. `drop` algo.",
    },
    "tut_hint_reader": {
        "en": "This is a keycard reader. Find a `keycard` on the network and use it with `use <card> on leitor.dev` to open the vault without a fight.",
        "pt": "Isto é um leitor de cartão. Ache um `keycard` na rede e passe com `use <cartao> no leitor.dev` para abrir o cofre sem briga.",
    },
    "tut_hint_vault_open": {
        "en": "Vault open, no alarm. A keycard always beats force.",
        "pt": "Cofre aberto sem alarme. Cartão sempre vale mais que força.",
    },
    "tut_hint_boss": {
        "en": "This is the sector's core: its ICE is the hardest here and doesn't play fair. Winning clears the sector and sends you back to the desk.",
        "pt": "Este é o núcleo do setor: o ICE dele é o mais duro daqui e não joga limpo. Vencer fecha o setor e te leva de volta à mesa.",
    },
    "tut_hint_first_buy": {
        "en": "Part installed. Your rig is the only thing that survives a wipe — it's your real progress.",
        "pt": "Peça instalada. O rig é a única coisa que atravessa a morte — ele é o seu progresso de verdade.",
    },
    "tut_hint_scan_locked": {
        "en": "`scan` needs intel first: get into /home/admin, or find and read a file with the subnet's IP/MAC table somewhere on this host.",
        "pt": "`scan` precisa de informação primeiro: entre em /home/admin, ou ache e leia um arquivo com a tabela de IP/MAC da sub-rede em algum lugar deste host.",
    },
    "tut_hint_cipher_intro": {
        "en": "Type a guess using the available alphabet. Feedback shows exact matches (right digit, right place) and partial matches (right digit, wrong place). Attempts are limited per sector.",
        "pt": "Digite um palpite usando o alfabeto disponível. Feedback mostra exatos (dígito certo, lugar certo) e parciais (dígito certo, lugar errado). Tentativas são limitadas por setor.",
    },
    "tut_hint_spoof_script": {
        "en": "Spoof scripts instantly reduce trace when executed, but are consumed in use. Find more by exploring deeper into the network.",
        "pt": "Scripts de disfarce reduzem o trace instantaneamente ao rodar, mas são consumidos no uso. Ache mais explorando mais fundo a rede.",
    },
    # app.py — BOOT_SEQUENCE
    "app_boot_1": {
        "en": "> connecting to zeta-dynamics.corp :23 ...",
        "pt": "> conectando a zeta-dynamics.corp :23 ...",
    },
    "app_boot_2": {
        "en": "> DEC LAT handshake ... OK",
        "pt": "> handshake DEC LAT ... OK",
    },
    "app_boot_3": {
        "en": "> authenticating as guest ... ACCESS GRANTED",
        "pt": "> autenticando como guest ... ACESSO CONCEDIDO",
    },
    "app_boot_5": {
        "en": "You're in. The terminal spits out a greenish cursor.",
        "pt": "Você está dentro. O terminal cospe um cursor esverdecido.",
    },
    "app_boot_6": {
        "en": "This is a VAX-11/785 running ULTRIX, forgotten since 1988.",
        "pt": "Isto é uma VAX-11/785 rodando ULTRIX, esquecida desde 1988.",
    },
    "app_boot_7": {
        "en": "Somewhere, the COLD-BOOT daemon still breathes.",
        "pt": "Em algum lugar, o daemon COLD-BOOT ainda respira.",
    },
    "app_boot_8": {
        "en": 'Type "help" for commands. Good luck.',
        "pt": 'Digite "ajuda" (ou "help") para os comandos. Boa sorte.',
    },
    # app.py — HELP_SECTIONS section titles
    "app_help_sec_nav": {
        "en": "NAVIGATION",
        "pt": "NAVEGAÇÃO",
    },
    "app_help_sec_net": {
        "en": "NETWORK",
        "pt": "REDE",
    },
    "app_help_sec_sys": {
        "en": "SYSTEM",
        "pt": "SISTEMA",
    },
    "app_help_sec_items": {
        "en": "ITEMS & RIG",
        "pt": "ITENS E RIG",
    },
    "app_help_sec_session": {
        "en": "SESSION",
        "pt": "SESSÃO",
    },
    # app.py — HELP_SECTIONS descriptions
    "app_help_ls": {
        "en": "list contents of current folder",
        "pt": "lista o conteúdo da pasta atual",
    },
    "app_help_cd": {
        "en": "enter a folder (`cd ..` back, `cd` to root)",
        "pt": "entra numa pasta (`cd ..` volta, `cd` vai à raiz)",
    },
    "app_help_cat": {
        "en": "read a file",
        "pt": "lê um arquivo",
    },
    "app_help_pwd": {
        "en": "show current path",
        "pt": "mostra o caminho atual",
    },
    "app_help_look": {
        "en": "examine the terminal or an item up close",
        "pt": "examina o terminal ou um item de perto",
    },
    "app_help_scan": {
        "en": "sweep subnet and lift map fog (needs /home/admin or /etc/hosts first)",
        "pt": "varre a sub-rede e dissipa a névoa (precisa de /home/admin ou /etc/hosts antes)",
    },
    "app_help_map": {
        "en": "redraw the network map on the panel",
        "pt": "redesenha o mapa da rede no painel",
    },
    "app_help_hack": {
        "en": "invade a host or unlock a file (typing duel)",
        "pt": "invade um host ou destranca um arquivo (duelo de digitação)",
    },
    "app_help_cipher": {
        "en": "break an intercepted code by deduction to reduce trace",
        "pt": "quebra um código por dedução para reduzir o trace",
    },
    "app_help_run": {
        "en": "execute a binary — including the CRN miner",
        "pt": "executa um binário — inclusive o minerador de CRN",
    },
    "app_help_ps": {
        "en": "list processes, including the miner",
        "pt": "lista os processos, incluindo o minerador",
    },
    "app_help_kill": {
        "en": "end a process (e.g., `kill miner`)",
        "pt": "encerra um processo (ex.: `kill miner`)",
    },
    "app_help_whoami": {
        "en": "show who you are on this machine",
        "pt": "mostra quem você é nesta máquina",
    },
    "app_help_inv": {
        "en": "wallet, keys, and what's in your buffer",
        "pt": "carteira, chaves e o que está no buffer",
    },
    "app_help_take": {
        "en": "load an item into buffer (uses host RAM)",
        "pt": "carrega um item no buffer (ocupa RAM do host)",
    },
    "app_help_drop": {
        "en": "drop an item here and free the RAM",
        "pt": "larga um item aqui e libera a RAM",
    },
    "app_help_use": {
        "en": "use an item from buffer or current folder",
        "pt": "usa um item do buffer ou da pasta atual",
    },
    "app_help_use_on": {
        "en": "use an item on something (e.g., a card on `leitor.dev`)",
        "pt": "usa um item em algo (ex.: um cartão no `leitor.dev`)",
    },
    "app_help_store": {
        "en": "hardware catalog and what you can install now",
        "pt": "catálogo de hardware e o que dá para instalar agora",
    },
    "app_help_buy": {
        "en": "buy and install a part (e.g., `comprar cool_fans`)",
        "pt": "compra e instala uma peça (ex.: `comprar cool_fans`)",
    },
    "app_help_plant": {
        "en": "plant a remote miner on a host you've compromised (risks getting caught)",
        "pt": "planta um minerador remoto num host que você comprometeu (risco de ser pego)",
    },
    "app_help_unplant": {
        "en": "pull a planted script back before it's found",
        "pt": "retira um script plantado antes que ele seja achado",
    },
    "app_help_botnet": {
        "en": "list your remote scripts and how old they are",
        "pt": "lista seus scripts remotos e a idade de cada um",
    },
    "app_help_modifier": {
        "en": "show the sector's active modifier effect",
        "pt": "mostra o efeito do modificador ativo do setor",
    },
    "app_help_achievements": {
        "en": "show meta-progression achievements, unlocked and locked",
        "pt": "mostra as conquistas de meta-progressão, desbloqueadas e travadas",
    },
    # app.py — do_decrypt (não listado no `help` de propósito — é achado lendo
    # os fragmentos, não escaneando comandos)
    "app_decrypt_missing_arg": {
        "en": "decrypt: give me the assembled code.",
        "pt": "decrypt: me dê o código montado.",
    },
    "app_decrypt_already_solved": {
        "en": "This sector's code is already spent. Nothing left to decrypt here.",
        "pt": "O código deste setor já foi gasto. Não há mais nada para decifrar aqui.",
    },
    "app_decrypt_wrong": {
        "en": "decrypt: rejected. Wrong code, or you're missing a fragment.",
        "pt": "decrypt: rejeitado. Código errado, ou falta um fragmento.",
    },
    "app_decrypt_success": {
        "en": "[decrypt] Key accepted. +{amount:.2f} {coin} (balance {balance:.2f}), "
              "and the signal goes quiet: -{relief:.0f} trace.",
        "pt": "[decrypt] Chave aceita. +{amount:.2f} {coin} (saldo {balance:.2f}), "
              "e o sinal fica quieto: -{relief:.0f} de trace.",
    },
    "app_help_save": {
        "en": "save the game (also via pause menu Esc)",
        "pt": "grava a partida (também dá para salvar pelo menu do Esc)",
    },
    "app_help_desk": {
        "en": "disconnect and return to the desk (costs the sector)",
        "pt": "desconecta e volta para a mesa (custa o setor atual)",
    },
    "app_help_reboot": {
        "en": "after being traced: back to desk, sector 1",
        "pt": "depois de ser rastreado: volta à mesa, no setor 1",
    },
    "app_help_clear": {
        "en": "clear the screen",
        "pt": "limpa a tela",
    },
    "app_help_help": {
        "en": "this list",
        "pt": "esta lista",
    },
    "app_help_exit": {
        "en": "end the session",
        "pt": "encerra a sessão",
    },
    "app_help_natural_lang": {
        "en": 'Also understands natural actions: "look at terminal", "read readme.txt", "go to /var/log", "use keycard on reader".',
        "pt": 'Também entende ações naturais: "olhar terminal", "ler readme.txt", "ir para /var/log", "usar keycard no leitor".',
    },
    "app_help_keys": {
        "en": "KEYS: Tab completes · → accept faded suggestion · ↑/↓ recall commands · Esc opens pause menu.",
        "pt": "TECLAS: Tab completa · → aceita a sugestão apagada · ↑/↓ repete comandos · Esc abre o menu de pausa.",
    },
    # app.py — do_ls
    "app_ls_empty": {
        "en": "(empty)",
        "pt": "(vazio)",
    },
    "app_ls_locked_suffix": {
        "en": " (locked)",
        "pt": " (trancado)",
    },
    # app.py — do_cd
    "app_cd_no_such_dir": {
        "en": "cd: {target}: no such directory",
        "pt": "cd: {target}: diretório inexistente",
    },
    "app_cd_denied": {
        "en": "cd: {target}: ACCESS DENIED. Try `hack {name}`.",
        "pt": "cd: {target}: ACESSO NEGADO. Tente `hack {name}`.",
    },
    "app_cd_moved": {
        "en": "→ {path}",
        "pt": "→ {path}",
    },
    # app.py — do_cat
    "app_cat_missing_arg": {
        "en": "cat: missing a file",
        "pt": "cat: falta um arquivo",
    },
    "app_cat_no_such_file": {
        "en": "cat: {target}: no such file",
        "pt": "cat: {target}: arquivo inexistente",
    },
    "app_cat_is_dir": {
        "en": "cat: {target}: is a directory",
        "pt": "cat: {target}: é um diretório",
    },
    "app_cat_encrypted": {
        "en": "cat: {target}: encrypted. `hack {name}` first.",
        "pt": "cat: {target}: criptografado. `hack {name}` primeiro.",
    },
    "app_cat_empty_file": {
        "en": "(empty file)",
        "pt": "(arquivo vazio)",
    },
    # app.py — _admin_bypass
    "app_admin_bypass_used": {
        "en": "[admin-key] su -c: '{name}' unlocked without alarm ({charges} charge(s) left).",
        "pt": "[chave-admin] su -c: '{name}' destrancado sem alarme ({charges} carga(s) restante(s)).",
    },
    "app_admin_bypass_burned": {
        "en": "[!] Key use raised suspicion: admin login invalidated. Remaining charges are worthless.",
        "pt": "[!] O uso da chave levantou suspeita: o login do admin foi invalidado. As cargas restantes não servem mais para nada.",
    },
    # app.py — do_look
    "app_look_terminal": {
        "en": "The amber terminal hums. Ancient fans spin in the dark of the rack. You're jacked into node {location}. Trace at {trace:.0f}%.",
        "pt": "O terminal âmbar zumbe. Ventoinhas antigas giram no escuro do rack. Você está jackeado no nó {location}. Trace em {trace:.0f}%.",
    },
    "app_look_nothing": {
        "en": "There's nothing called '{target}' around here.",
        "pt": "Não há nada chamado '{target}' por aqui.",
    },
    "app_look_is_dir": {
        "en": "'{name}' is a directory. Use `cd {name}`.",
        "pt": "'{name}' é um diretório. Use `cd {name}`.",
    },
    "app_look_is_file": {
        "en": "'{name}' is a file. Use `cat {name}`.",
        "pt": "'{name}' é um arquivo. Use `cat {name}`.",
    },
    # app.py — do_scan
    "app_scan_locked": {
        "en": "scan: unknown subnet layout. Get into /home/admin, or find a "
              "file with the IP/MAC table somewhere on this host.",
        "pt": "scan: layout da sub-rede desconhecido. Entre em /home/admin, "
              "ou ache um arquivo com a tabela de IP/MAC em algum lugar deste host.",
    },
    "app_cipher_busy": {
        "en": "cipher: occupied — can't decrypt now.",
        "pt": "cipher: ocupado — não dá para decifrar agora.",
    },
    "app_cipher_no_uses_left": {
        "en": "cipher: no attempts left for this sector ({used}/{cap}). Refresh on next descent.",
        "pt": "cipher: sem tentativas restantes neste setor ({used}/{cap}). Atualize na próxima descida.",
    },
    "app_cipher_start": {
        "en": "[cipher] Intercepted signal — {length}-digit code, alphabet: {alphabet}. {guesses} guesses (attempt {used}/{cap}). Crack it.",
        "pt": "[cipher] Sinal interceptado — código de {length} dígitos, alfabeto: {alphabet}. {guesses} tentativas (tentativa {used}/{cap}). Quebre o código.",
    },
    "app_cipher_invalid": {
        "en": "cipher: invalid input. Enter exactly {length} digits from {alphabet}.",
        "pt": "cipher: entrada inválida. Digite exatamente {length} dígitos do alfabeto {alphabet}.",
    },
    "app_cipher_win": {
        "en": "[cipher] Code cracked. Signal decrypted. -{relief:.0f} trace.",
        "pt": "[cipher] Código quebrado. Sinal decriptado. -{relief:.0f} de trace.",
    },
    "app_cipher_lose": {
        "en": "[cipher] Out of guesses. Code was {code}. No trace reduction.",
        "pt": "[cipher] Tentativas esgotadas. Código era {code}. Sem redução de trace.",
    },
    "app_cipher_feedback": {
        "en": "[feedback] {exact} exact · {partial} partial · {left} guesses remain.",
        "pt": "[feedback] {exact} exato(s) · {partial} parcial(is) · {left} tentativas restam.",
    },
    "app_scan_active": {
        "en": "active scan — sweeping subnet...",
        "pt": "scan ativo — varrendo sub-rede...",
    },
    "app_scan_found": {
        "en": "SCAN: new hosts in the fog → {hosts}",
        "pt": "SCAN: novos hosts na névoa → {hosts}",
    },
    "app_scan_none": {
        "en": "SCAN: no new hosts within reach of this node.",
        "pt": "SCAN: nenhum host novo ao alcance deste nó.",
    },
    # app.py — do_map
    "app_map_updated": {
        "en": "Network map updated on the top panel.",
        "pt": "Mapa da rede atualizado no painel superior.",
    },
    # app.py — do_whoami
    "app_whoami": {
        "en": "guest (uid=500) — no privileges. Yet.",
        "pt": "guest (uid=500) — sem privilégios. Por enquanto.",
    },
    # app.py — do_ps
    "app_ps_header": {
        "en": "  PID  MEM  CMD",
        "pt": "  PID  MEM  CMD",
    },
    "app_ps_init": {
        "en": "    1   12K  /etc/init",
        "pt": "    1   12K  /etc/init",
    },
    "app_ps_coldboot": {
        "en": "  441   64K  coldboot -daemon -watch",
        "pt": "  441   64K  coldboot -daemon -watch",
    },
    "app_ps_getty": {
        "en": "  512    8K  getty ttS0",
        "pt": "  512    8K  getty ttS0",
    },
    "app_ps_miner": {
        "en": "  920  {kb:3d}K  miner --randomx ({hash:.0f}H, {watts}W)",
        "pt": "  920  {kb:3d}K  miner --randomx ({hash:.0f}H, {watts}W)",
    },
    "app_ps_throttle_badge": {
        "en": "  [THROTTLE]",
        "pt": "  [THROTTLE]",
    },
    "app_ps_buffer": {
        "en": "  977  {kb:3d}K  buffer ({count} item/ns)",
        "pt": "  977  {kb:3d}K  buffer ({count} item/ns)",
    },
    "app_ps_free": {
        "en": "  free: {free}K of {total}K",
        "pt": "  livre: {free}K de {total}K",
    },
    "app_ps_watching": {
        "en": "   << the host is watching you",
        "pt": "   << o host está reparando em você",
    },
    # app.py — do_kill
    "app_kill_missing_arg": {
        "en": "kill: specify a process (see `ps`).",
        "pt": "kill: informe um processo (veja `ps`).",
    },
    "app_kill_not_found": {
        "en": "kill: '{proc}': nonexistent or system-protected process.",
        "pt": "kill: '{proc}': processo inexistente ou protegido pelo sistema.",
    },
    "app_kill_done": {
        "en": "[kill] {proc} ended. The rig begins to cool.",
        "pt": "[kill] {proc} encerrado. O rig começa a esfriar.",
    },
    # app.py — _fs_event
    "app_fs_read_auth": {
        "en": "[!] Partial credentials extracted from auth logs.",
        "pt": "[!] Credenciais parciais extraídas dos logs de auth.",
    },
    "app_fs_got_keycard": {
        "en": "[+] keycard 7F-ORION-2A added to inventory.",
        "pt": "[+] keycard 7F-ORION-2A adicionado ao inventário.",
    },
    "app_fs_poke_daemon": {
        "en": "[!] The COLD-BOOT daemon felt you. Trace spiked.",
        "pt": "[!] O daemon COLD-BOOT sentiu você. Trace disparou.",
    },
    "app_fs_unlock_scan": {
        "en": "[+] Subnet layout acquired. `scan` is unlocked for this sector.",
        "pt": "[+] Layout da sub-rede adquirido. `scan` está desbloqueado para este setor.",
    },
    # app.py — do_unknown
    "app_unknown_command": {
        "en": "unknown command: '{raw}'. Try `help`.",
        "pt": "comando desconhecido: '{raw}'. Tente `help`.",
    },
    # app.py — do_hack
    "app_hack_no_target": {
        "en": "hack: specify a target (network node or locked file).",
        "pt": "hack: informe um alvo (nó da rede ou arquivo trancado).",
    },
    "app_hack_not_found": {
        "en": "hack: target '{target}' not found or already open.",
        "pt": "hack: alvo '{target}' não encontrado ou já aberto.",
    },
    # app.py — do_run
    "app_run_usage": {
        "en": "run: specify a program. Ex.: run scan or run <miner>.py",
        "pt": "run: informe um programa. Ex.: run scan ou run <miner>.py",
    },
    "app_run_already_running": {
        "en": "the miner is already running (see `ps`).",
        "pt": "o minerador já está rodando (veja `ps`).",
    },
    "app_run_no_ram": {
        "en": "run: {prog}: insufficient host memory — your rig's miner needs {kb}K but only {free}K is free. Drop items (`drop`) to make space.",
        "pt": "run: {prog}: sem memória no host — o minerador do seu rig pede {kb}K e só há {free}K livres. Largue itens (`drop`) para abrir espaço.",
    },
    "app_run_miner_started": {
        "en": "miner started in background ({hash:.0f}H, {kb}K on host). It generates CRN, heats the rig, and MAKES NOISE: Trace climbs +{noise:.2f} per tick. `kill miner` to stop.",
        "pt": "minerador iniciado em segundo plano ({hash:.0f}H, {kb}K no host). Ele gera CRN, esquenta o rig e FAZ BARULHO: o trace sobe +{noise:.2f} por tick. `kill miner` para parar.",
    },
    "app_run_spoof_done": {
        "en": "signal triangulated as {fake_user} — trace reduced -{amount:.0f}%. Script consumed.",
        "pt": "sinal triangulado como {fake_user} — trace reduzido -{amount:.0f}%. Script consumido.",
    },
    "app_run_not_found": {
        "en": "run: '{prog}': binary not found or not executable.",
        "pt": "run: '{prog}': binário não encontrado ou não executável.",
    },
    # app.py — do_take
    "app_take_not_item": {
        "en": "take: '{target}': not an item you can carry.",
        "pt": "take: '{target}': não é um item que dê para carregar.",
    },
    "app_take_reader_bolted": {
        "en": "take: the reader is bolted to the rack. No go.",
        "pt": "take: o leitor está parafusado no rack. Não vai.",
    },
    "app_take_buffer_full": {
        "en": "take: buffer full — only {free}K free on host (each item takes {item_kb}K). Drop something or kill the miner.",
        "pt": "take: buffer cheio — só {free}K livres no host (cada item ocupa {item_kb}K). Largue algo ou pare o minerador.",
    },
    "app_take_loaded": {
        "en": "[+] {name} loaded into buffer ({item_kb}K · {free}K free).",
        "pt": "[+] {name} carregado no buffer ({item_kb}K · {free}K livres).",
    },
    # app.py — do_drop
    "app_drop_not_in_buffer": {
        "en": "drop: '{target}': not in buffer. (`inv` to see)",
        "pt": "drop: '{target}': não está no buffer. (`inv` para ver)",
    },
    "app_drop_done": {
        "en": "[-] {name} dropped here ({free}K free).",
        "pt": "[-] {name} largado aqui ({free}K livres).",
    },
    "app_drop_content": {
        "en": "(dropped item: {kind})\n",
        "pt": "(item largado: {kind})\n",
    },
    # app.py — do_use
    "app_use_not_found": {
        "en": "No item called '{name}' here or in buffer. (`ls` / `inv`)",
        "pt": "Não há um item '{name}' aqui nem no buffer. (`ls` / `inv`)",
    },
    # app.py — _swipe_card
    "app_swipe_no_reader": {
        "en": "No card reader in this room. Look for a `leitor.dev`.",
        "pt": "Não há leitor de cartão nesta sala. Procure um `leitor.dev`.",
    },
    "app_swipe_nothing_locked": {
        "en": "The reader blinks green, but there's nothing locked to it.",
        "pt": "O leitor pisca verde, mas não há nada trancado nele.",
    },
    "app_swipe_success": {
        "en": "[card {code}] the reader swallows the stripe, thinks, and unlocks '{name}' without raising ONE alarm. `ls` to see.",
        "pt": "[cartão {code}] o leitor engole a tarja, pensa, e destrava '{name}' sem levantar UM alarme. `ls` para ver.",
    },
    # app.py — _apply_item
    "app_item_credited": {
        "en": "[+] {amount:.3f} {coin} credited to wallet (balance {balance:.2f}).",
        "pt": "[+] {amount:.3f} {coin} creditados na carteira (saldo {balance:.2f}).",
    },
    "app_item_adminkey": {
        "en": "[+] admin key extracted (+{charges} charge/s). It bypasses a locked resource — but suspicious use can invalidate the admin.",
        "pt": "[+] chave de admin extraída (+{charges} carga(s)). Ela burla um recurso trancado — mas uso suspeito pode inutilizar o admin.",
    },
    "app_item_coolant": {
        "en": "[+] coolant injected: -{amount}C.",
        "pt": "[+] refrigerante injetado: -{amount}C.",
    },
    "app_item_scrambler": {
        "en": "[+] signal scrambled: -{amount}% trace and siege reset.",
        "pt": "[+] sinal embaralhado: -{amount}% de trace e cerco resetado.",
    },
    "app_item_is_miner": {
        "en": "this is a miner. Start it with `run {name}`.",
        "pt": "isto é um minerador. Inicie com `run {name}`.",
    },
    "app_item_is_spoof": {
        "en": "this is a spoof script. Run it with `run {name}`.",
        "pt": "isto é um script de disfarce. Rode com `run {name}`.",
    },
    "app_item_reader_idle": {
        "en": "the reader blinks, idle. It wants a card: `use <card> on leitor.dev`.",
        "pt": "o leitor pisca, ocioso. Ele quer um cartão: `use <cartao> no leitor.dev`.",
    },
    "app_item_keycard_needs_take": {
        "en": "the card must be on you to pass the reader. `take {name}` first.",
        "pt": "o cartão precisa estar com você para passar no leitor. `take {name}` primeiro.",
    },
    "app_item_backdoor_needs_take": {
        "en": "the credential must be on you to spend it. `take {name}` first.",
        "pt": "a credencial precisa estar com você para ser gasta. `take {name}` primeiro.",
    },
    "app_backdoor_missing_target": {
        "en": "usage: use <backdoor file> on <target>",
        "pt": "uso: use <arquivo do backdoor> em <alvo>",
    },
    "app_backdoor_not_found": {
        "en": "'{target}' isn't a hackable node or locked resource here.",
        "pt": "'{target}' não é um nó hackeável nem um recurso trancado aqui.",
    },
    "app_backdoor_no_boss": {
        "en": "the backdoor won't touch the sector's CORE — that fight is yours to win.",
        "pt": "o backdoor não funciona no CORE do setor — essa luta é para vencer de verdade.",
    },
    "app_backdoor_net_done": {
        "en": "[backdoor] silent access granted to {label}. No ICE, no alarm. Credential spent.",
        "pt": "[backdoor] acesso silencioso concedido a {label}. Sem ICE, sem alarme. Credencial gasta.",
    },
    "app_backdoor_fs_done": {
        "en": "[backdoor] '{name}' unlocked without a fight. Credential spent.",
        "pt": "[backdoor] '{name}' destrancado sem luta. Credencial gasta.",
    },
    "app_item_nothing": {
        "en": "nothing happens.",
        "pt": "nada acontece.",
    },
    # app.py — do_inv
    "app_inv_label": {
        "en": "INVENTORY: ",
        "pt": "INVENTÁRIO: ",
    },
    "app_inv_adminkey": {
        "en": "admin-key x{charges}",
        "pt": "chave-admin x{charges}",
    },
    "app_inv_empty": {
        "en": "  (buffer empty — `take <item>` to load)",
        "pt": "  (buffer vazio — `take <item>` para carregar)",
    },
    "app_inv_summary": {
        "en": "  buffer: {count} item(s) · {used}K/{total}K of host in use · {free}K free",
        "pt": "  buffer: {count} item(ns) · {used}K/{total}K do host em uso · {free}K livres",
    },
    "app_inv_tight_badge": {
        "en": "  [MEMORY MAXED]",
        "pt": "  [MEMÓRIA NO TALO]",
    },
    # app.py — do_buy
    "app_buy_missing_arg": {
        "en": "buy: specify the part id (see `store`).",
        "pt": "comprar: informe o id da peça (veja `store`).",
    },
    "app_buy_prefix_ok": {
        "en": "[+] ",
        "pt": "[+] ",
    },
    "app_buy_prefix_fail": {
        "en": "purchase refused: ",
        "pt": "compra recusada: ",
    },
    # app.py — do_plant / do_unplant / do_botnet
    "app_plant_missing_arg": {
        "en": "plant: give me a compromised host.",
        "pt": "plant: me dê um host comprometido.",
    },
    "app_plant_not_found": {
        "en": "plant: '{target}': not a host you've compromised.",
        "pt": "plant: '{target}': não é um host que você comprometeu.",
    },
    "app_plant_already": {
        "en": "There's already a script running on {label}.",
        "pt": "Já tem um script rodando em {label}.",
    },
    "app_plant_no_capacity": {
        "en": "No free botnet slots ({used}/{cap} in use) — a stronger CPU opens more.",
        "pt": "Sem slots de botnet livres ({used}/{cap} em uso) — uma CPU melhor abre mais.",
    },
    "app_plant_done": {
        "en": "[+] Script planted on {label}: +{rate:.2f} {coin}/tick ({used}/{cap} slots). "
              "It'll run until someone finds it — check `botnet`.",
        "pt": "[+] Script plantado em {label}: +{rate:.2f} {coin}/tick ({used}/{cap} slots). "
              "Vai rodar até alguém achar — confira com `botnet`.",
    },
    "app_unplant_not_planted": {
        "en": "unplant: no script running there.",
        "pt": "unplant: não há script rodando ali.",
    },
    "app_unplant_done": {
        "en": "[-] Pulled the script from {label} before anyone noticed.",
        "pt": "[-] Script retirado de {label} antes que alguém percebesse.",
    },
    "app_botnet_empty": {
        "en": "No scripts running remotely. `plant <host>` on a compromised host to start one.",
        "pt": "Nenhum script rodando remotamente. `plant <host>` num host comprometido para começar.",
    },
    "app_botnet_header": {
        "en": "BOTNET ({used}/{cap} slots):",
        "pt": "BOTNET ({used}/{cap} slots):",
    },
    "app_botnet_line": {
        "en": "  {label:<8} {age:3d} ticks old · +{rate:.2f} {coin}/tick",
        "pt": "  {label:<8} {age:3d} ticks · +{rate:.2f} {coin}/tick",
    },
    "app_botnet_line_hot": {
        "en": "  {label:<8} {age:3d} ticks old · +{rate:.2f} {coin}/tick · [!] HOT, {risk:.0f}%/tick discovery risk",
        "pt": "  {label:<8} {age:3d} ticks · +{rate:.2f} {coin}/tick · [!] QUENTE, {risk:.0f}%/tick de risco de descoberta",
    },
    "app_botnet_lost": {
        "en": "[!] The script on {host} got caught and wiped. Trace ticked up.",
        "pt": "[!] O script em {host} foi pego e apagado. O trace subiu.",
    },
    # app.py — _start_combat
    "app_combat_ice_active": {
        "en": "⚠ ICE ACTIVE [{ice_type}] — {name} raised a barrier of {rounds} layers. Type the CODES before the signal drops!",
        "pt": "⚠ ICE ATIVO [{ice_type}] — {name} ergueu uma barreira de {rounds} camadas. Digite os CÓDIGOS antes que o sinal caia!",
    },
    "app_combat_hint_memory": {
        "en": "This ICE erases the code after a moment — memorize and type from memory.",
        "pt": "Este ICE apaga o código depois de um instante — memorize e digite de cabeça.",
    },
    "app_combat_hint_hunt": {
        "en": "This ICE won't stay still: mid-round the code escapes and becomes another. Eyes sharp.",
        "pt": "Este ICE não fica quieto: no meio do round o código escapa e vira outro. Olho vivo.",
    },
    "app_combat_hint_phantom": {
        "en": "This ICE erases the code early AND swaps it while hidden — what you memorized may already be a lie.",
        "pt": "Este ICE apaga o código cedo E o troca enquanto está escondido — o que você memorizou já pode ser mentira.",
    },
    # app.py — _end_combat
    "app_combat_connected": {
        "en": "Connected to {label}. New file system mounted — `ls` to look.",
        "pt": "Conectado a {label}. Novo sistema de arquivos montado — `ls` para olhar.",
    },
    "app_combat_fs_unlocked": {
        "en": "[+] '{name}' unlocked.",
        "pt": "[+] '{name}' destrancado.",
    },
    # app.py — _enter_lockdown
    "app_lockdown_enter": {
        "en": "╪╪ TRACE 100% — LOCKDOWN ╪╪  The system closed in. Counter the signal: type ALL the codes, without ONE mistake, or the connection drops.",
        "pt": "╪╪ TRACE 100% — LOCKDOWN ╪╪  O sistema fechou o cerco. Rebata o sinal: digite TODOS os códigos, sem UM erro, ou a conexão cai.",
    },
    # app.py — _lockdown_submit
    "app_lockdown_countered": {
        "en": "COUNTERED — layer spoofed.",
        "pt": "REBATIDO — camada despistada.",
    },
    # app.py — _lockdown_win
    "app_lockdown_won": {
        "en": "SIGNAL COUNTERED — tracing spoofed to 55%. Lockdown level {level}: next siege will come faster.",
        "pt": "SINAL REBATIDO — rastreamento despistado para 55%. Nível de lockdown {level}: o próximo cerco virá mais rápido.",
    },
    # app.py — _lockdown_fail
    "app_lockdown_captured": {
        "en": "[ SIGNAL CAPTURED ]",
        "pt": "[ SINAL CAPTURADO ]",
    },
    "app_lockdown_villain_says": {
        "en": 'COLD-BOOT: "{line}"',
        "pt": 'COLD-BOOT: "{line}"',
    },
    "app_lockdown_static": {
        "en": "The screen saturates with static and dies. CONNECTION LOST.",
        "pt": "A tela satura de estática e some. FIM DA CONEXÃO.",
    },
    "app_lockdown_frozen": {
        "en": "They traced your wallet and froze {amount:.2f} {coin}. You fell from sector {sector} back to 1. The rig is out of reach — it's on your desk, hot, waiting.",
        "pt": "Rastrearam a carteira e congelaram {amount:.2f} {coin}. Você caiu do setor {sector} de volta ao 1. O rig ficou fora do alcance deles — está na sua mesa, quente, esperando.",
    },
    "app_lockdown_reboot_hint": {
        "en": "Type `reboot` to return to the desk.",
        "pt": "Digite `reboot` para voltar à mesa.",
    },
    # app.py — _win
    "app_win_core": {
        "en": "CORE COMPROMISED. The {boss_name} chokes and shuts down. Rack lights blink out one by one.",
        "pt": "NÚCLEO COMPROMETIDO. O {boss_name} engasga e desliga. As luzes do rack apagam uma a uma.",
    },
    "app_win_cleared": {
        "en": "Sector {sector} cleared: +{amount:.2f} {coin} cashed out (balance {balance:.2f}). Disconnecting before they notice.",
        "pt": "Setor {sector} limpo: +{amount:.2f} {coin} sacados (saldo {balance:.2f}). Desconectando antes que percebam.",
    },
    # world.py — sector modifiers
    "world_mod_signal_clean_name": {
        "en": "Clean Signal",
        "pt": "Sinal Limpo",
    },
    "world_mod_signal_clean_desc": {
        "en": "trace rises 30% slower, but payout reduced 10%",
        "pt": "trace sobe 30% mais lento, mas o pagamento cai 10%",
    },
    "world_mod_high_alert_name": {
        "en": "High Alert",
        "pt": "Alerta Máximo",
    },
    "world_mod_high_alert_desc": {
        "en": "ICE punishes 30% harder per mistake, but payout raised 30%",
        "pt": "o ICE pune 30% mais forte por erro, mas o pagamento sobe 30%",
    },
    "world_mod_ghost_net_name": {
        "en": "Ghost Net",
        "pt": "Rede Fantasma",
    },
    "world_mod_ghost_net_desc": {
        "en": "planted scripts half as risky to discovery, but payout reduced 10%",
        "pt": "scripts plantados com metade do risco de descoberta, mas o pagamento cai 10%",
    },
    "world_mod_soft_ice_name": {
        "en": "Soft ICE",
        "pt": "ICE Amaciado",
    },
    "world_mod_soft_ice_desc": {
        "en": "ICE punishes 25% softer per mistake, but payout reduced 15%",
        "pt": "o ICE pune 25% mais fraco por erro, mas o pagamento cai 15%",
    },
    "world_mod_noisy_signal_name": {
        "en": "Noisy Signal",
        "pt": "Sinal Ruidoso",
    },
    "world_mod_noisy_signal_desc": {
        "en": "ambient trace rises 30% faster, but payout raised 15%",
        "pt": "o trace ambiente sobe 30% mais rápido, mas o pagamento sobe 15%",
    },
    "world_mod_loud_botnet_name": {
        "en": "Loud Botnet",
        "pt": "Botnet Barulhenta",
    },
    "world_mod_loud_botnet_desc": {
        "en": "planted scripts 50% more likely to be discovered, but payout raised 15%",
        "pt": "scripts plantados com 50% mais chance de serem descobertos, mas o pagamento sobe 15%",
    },
    # app.py — _start_session
    "app_session_sector_seed": {
        "en": "// sector {sector} — seed: {seed}",
        "pt": "// setor {sector} — seed: {seed}",
    },
    # app.py — start_tutorial
    "app_tut_intro": {
        "en": "╪╪  SECTOR 0 — TRAINING  ╪╪  Isolated network, no real ICE. Type `skip` anytime to jump straight to the game.",
        "pt": "╪╪  SETOR 0 — TREINO  ╪╪  Rede isolada, sem ICE de verdade. Digite `pular` a qualquer momento para ir direto ao jogo.",
    },
    # app.py — _tut_done
    "app_tut_done": {
        "en": "Training complete. The rest of the game is this with real ICE, Trace running, and a core at the end of each sector.",
        "pt": "Treino encerrado. O resto do jogo é isto com ICE de verdade, Trace correndo e um núcleo no fim de cada setor.",
    },
    # app.py — do_pular
    "app_pular_not_active": {
        "en": "skip: no training running.",
        "pt": "pular: não há tutorial rodando.",
    },
    "app_pular_done": {
        "en": "Training skipped.",
        "pt": "Tutorial pulado.",
    },
    # app.py — _desk_closed
    "app_desk_connecting": {
        "en": "╪╪  SECTOR {sector}  ╪╪  connecting... {hosts} hosts in initial sweep. seed {seed}.",
        "pt": "╪╪  SETOR {sector}  ╪╪  conectando... {hosts} hosts na varredura inicial. seed {seed}.",
    },
    "app_desk_inside": {
        "en": "You're in. Trace started running.",
        "pt": "Você está dentro. O Trace voltou a correr.",
    },
    "app_sector_modifier": {
        "en": "[sector modifier] {name} — {desc}",
        "pt": "[modificador do setor] {name} — {desc}",
    },
    "app_modifier_none": {
        "en": "no active modifier",
        "pt": "nenhum modificador ativo",
    },
    # app.py — do_achievements / _announce_achievements
    "app_achievement_unlocked": {
        "en": "[achievement unlocked] {name}",
        "pt": "[conquista desbloqueada] {name}",
    },
    "app_achievement_locked": {
        "en": "locked",
        "pt": "travada",
    },
    "app_achievements_header": {
        "en": "== ACHIEVEMENTS ({n}/{total}) ==",
        "pt": "== CONQUISTAS ({n}/{total}) ==",
    },
    "ach_first_core_name": {
        "en": "First Core",
        "pt": "Primeiro Núcleo",
    },
    "ach_first_core_desc": {
        "en": "compromise a sector's CORE for the first time",
        "pt": "comprometa o CORE de um setor pela primeira vez",
    },
    "ach_deep_5_name": {
        "en": "Descent",
        "pt": "Descida",
    },
    "ach_deep_5_desc": {
        "en": "reach sector 5",
        "pt": "chegue ao setor 5",
    },
    "ach_deep_10_name": {
        "en": "Free Fall",
        "pt": "Queda Livre",
    },
    "ach_deep_10_desc": {
        "en": "reach sector 10",
        "pt": "chegue ao setor 10",
    },
    "ach_payout_1k_name": {
        "en": "First Grand",
        "pt": "Primeiro Milhar",
    },
    "ach_payout_1k_desc": {
        "en": "earn 1000 CRN total from cleared COREs",
        "pt": "acumule 1000 CRN sacados de CORE limpo",
    },
    "ach_payout_5k_name": {
        "en": "Crypto Baron",
        "pt": "Barão da Cripto",
    },
    "ach_payout_5k_desc": {
        "en": "earn 5000 CRN total from cleared COREs",
        "pt": "acumule 5000 CRN sacados de CORE limpo",
    },
    "ach_resilient_name": {
        "en": "Reboot and Try Again",
        "pt": "Reinicia e Tenta de Novo",
    },
    "ach_resilient_desc": {
        "en": "get caught by LOCKDOWN 3 times and keep coming back",
        "pt": "seja pego pelo LOCKDOWN 3 vezes e continue voltando",
    },
    "ach_veteran_name": {
        "en": "Veteran",
        "pt": "Veterano",
    },
    "ach_veteran_desc": {
        "en": "clear 10 sector COREs total",
        "pt": "limpe 10 COREs de setor no total",
    },
    # app.py — load_game
    "app_load_no_save": {
        "en": "load: no readable save found.",
        "pt": "load: nenhum save legível encontrado.",
    },
    "app_load_restored": {
        "en": "[save] game restored — seed {seed}, node {location}, trace {trace:.0f}%.",
        "pt": "[save] partida restaurada — seed {seed}, nó {location}, trace {trace:.0f}%.",
    },
    # app.py — do_reboot
    "app_reboot_busy": {
        "en": "reboot: finish the duel first.",
        "pt": "reboot: termine o duelo primeiro.",
    },
    # app.py — do_desk
    "app_desk_disconnect": {
        "en": "You pull the plug. The sector closes behind you — reconnecting will drop you in a new network.",
        "pt": "Você puxa o cabo. O setor se fecha atrás de você — reconectar vai cair numa rede nova.",
    },
    # app.py — do_save
    "app_save_ok": {
        "en": "[save] game saved to {path}. Load from the pause menu (Esc).",
        "pt": "[save] partida gravada em {path}. Carregue pelo menu (Esc).",
    },
    "app_save_busy": {
        "en": "save: can't save now — finish the duel first.",
        "pt": "save: não dá para salvar agora — termine o duelo primeiro.",
    },
    # app.py — do_exit
    "app_exit_save_hint": {
        "en": "> tip: type `save` first if you want to keep this run.",
        "pt": "> dica: digite `save` antes se quiser guardar esta run.",
    },
    "app_exit_message": {
        "en": "> ending session... good escape, guest.",
        "pt": "> encerrando sessão... boa fuga, guest.",
    },
    # app.py — _economy_tick
    "app_overheat_warning": {
        "en": "!! OVERHEAT — throttle: mining and speed slow down",
        "pt": "!! SUPERAQUECIMENTO — throttle: mineração e velocidade caem",
    },
    "app_overheat_normal": {
        "en": "temperature normalized",
        "pt": "temperatura normalizada",
    },
    # app.py — on_input_submitted
    "app_dead_connection": {
        "en": "The connection is dead. `reboot` for a new incursion · `exit` to quit.",
        "pt": "A conexão está morta. `reboot` para uma nova incursão · `exit` para sair.",
    },
    "app_thermal_abort": {
        "en": "SEGFAULT: thermal — command aborted (overheating).",
        "pt": "SEGFAULT: thermal — comando abortado (superaquecimento).",
    },
}
