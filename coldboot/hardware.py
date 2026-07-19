"""Hardware — catálogo de peças, a montagem (Rig) e as stats derivadas.

Módulo puro (não importa o State), então dá para testar toda a compatibilidade
e a matemática sem UI. Sem marcas reais; tudo por tiers.

Realismo modelado:
  * Placa-mãe define geração de RAM (DDR3..DDR6), nº de slots, socket de CPU,
    slots PCIe (GPU) e teto de watts.
  * RAM: mineração é memory-hard (estilo RandomX), então capacidade+velocidade
    de RAM aumentam o hashrate de verdade.
  * CPU: hashrate + velocidade do texto (teletype) + tempo extra nos minigames.
  * PSU: a soma dos TDPs sob carga precisa caber (com folga) ou não instala.
  * Cooler/fans dissipam calor; sob carga o rig esquenta e pode dar throttle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import i18n

COIN = "CRN"  # moeda fictícia (bitcoin-like) da carteira (Chronium)
AMBIENT = 32.0  # temperatura ambiente (°C)
TMAX = 82.0  # acima disso: throttling
HEAT_K = 26.0  # ganho térmico (W -> °C)
MINE_RATE = 0.22  # CRN por unidade de hashrate por tick

# --------------------------------------------------------------------------- #
# Memória do HOST (não a do seu rig): os 640K da VAX em que você está jackeado.
# Tudo que você deixa rodando lá dentro ocupa espaço — e espaço ocupado numa
# máquina alheia é exatamente o que faz o ICE olhar para o seu lado.
# --------------------------------------------------------------------------- #
HOST_RAM_KB = 640  # "640K ought to be enough for anybody"
ITEM_KB = 40  # cada item carregado no seu buffer
RAM_TIGHT_KB = 96  # abaixo disso o host começa a estranhar


def miner_footprint(rig: "Rig") -> int:
    """KB que o minerador ocupa no host.

    Mineração memory-hard: quanto mais RAM o seu rig tem, maior a tabela que
    ele precisa manter viva do outro lado — rig forte é rig barulhento.

    Cresce com a raiz, não linear: um rig de topo (256GB) tem que caber nos
    640K da VAX, senão a economia inteira morre no late game. No teto ele ocupa
    ~536K e sobra espaço para uns dois itens — é aí que minerar passa a
    competir com carregar coisas.
    """
    return 120 + round(26 * math.sqrt(max(0, derived(rig).ram_gb)))


@dataclass(frozen=True)
class Part:
    id: str
    kind: str  # mobo | ram | cpu | gpu | psu | cooler
    name: str
    price: float
    tdp: int = 0
    specs: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Catálogo (id -> Part)
# --------------------------------------------------------------------------- #
# Marcas fictícias, para o rig ter cara de catálogo de loja sem citar ninguém
# real: FIC (CPU), NTX (GPU), Husky (roteadores), PNU (fontes), Kestrel (placas).
_PARTS: list[Part] = [
    # Placas-mãe: slots, geração DDR, socket, slots PCIe, teto de watts
    Part(
        "mb_a1",
        "mobo",
        "Kestrel A1 (OEM)",
        0,
        15,
        {"slots": 2, "ddr": "DDR3", "socket": "S1", "pcie": 0, "max_power": 300},
    ),
    Part(
        "mb_b2",
        "mobo",
        "Kestrel B2 Plus",
        180,
        18,
        {"slots": 4, "ddr": "DDR4", "socket": "S2", "pcie": 1, "max_power": 550},
    ),
    Part(
        "mb_c3",
        "mobo",
        "Kestrel C3 Gamer",
        420,
        22,
        {"slots": 4, "ddr": "DDR5", "socket": "S3", "pcie": 2, "max_power": 850},
    ),
    Part(
        "mb_x9",
        "mobo",
        "Kestrel X9 Workstation",
        900,
        26,
        {"slots": 4, "ddr": "DDR6", "socket": "S4", "pcie": 3, "max_power": 1200},
    ),
    # RAM: geração, tamanho (GB), clock (MHz) e fator de velocidade
    Part(
        "ram_d3_4",
        "ram",
        "4GB DDR3 100 MHz",
        40,
        4,
        {"ddr": "DDR3", "size": 4, "mhz": 100, "speed": 1.0},
    ),
    Part(
        "ram_d3_8",
        "ram",
        "8GB DDR3 120 MHz",
        70,
        5,
        {"ddr": "DDR3", "size": 8, "mhz": 120, "speed": 1.1},
    ),
    Part(
        "ram_d4_8",
        "ram",
        "8GB DDR4 240 MHz",
        90,
        5,
        {"ddr": "DDR4", "size": 8, "mhz": 240, "speed": 1.4},
    ),
    Part(
        "ram_d4_16",
        "ram",
        "16GB DDR4 320 MHz",
        150,
        6,
        {"ddr": "DDR4", "size": 16, "mhz": 320, "speed": 1.6},
    ),
    Part(
        "ram_d5_32",
        "ram",
        "32GB DDR5 480 MHz",
        300,
        8,
        {"ddr": "DDR5", "size": 32, "mhz": 480, "speed": 2.2},
    ),
    Part(
        "ram_d6_64",
        "ram",
        "64GB DDR6 720 MHz",
        620,
        10,
        {"ddr": "DDR6", "size": 64, "mhz": 720, "speed": 3.0},
    ),
    # CPUs: socket, hashrate base, bônus de tempo (s) nos minigames, mult. teletype
    Part(
        "cpu_s1",
        "cpu",
        "FIC Core 2 (OEM)",
        0,
        35,
        {"socket": "S1", "hash": 5, "typing": 0.0, "tele": 1.0, "cores": 2},
    ),
    Part(
        "cpu_s2",
        "cpu",
        "FIC Ultra 5",
        220,
        65,
        {"socket": "S2", "hash": 20, "typing": 0.8, "tele": 1.3, "cores": 6},
    ),
    Part(
        "cpu_s3",
        "cpu",
        "FIC Ultra 7",
        480,
        95,
        {"socket": "S3", "hash": 45, "typing": 1.5, "tele": 1.6, "cores": 12},
    ),
    Part(
        "cpu_s4",
        "cpu",
        "FIC Ultra 9 XE",
        850,
        130,
        {"socket": "S4", "hash": 80, "typing": 2.5, "tele": 2.0, "cores": 24},
    ),
    # GPUs: cada uma ocupa 1 slot PCIe, dão hashrate extra
    Part("gpu_a", "gpu", "NTX 1660sz 6GB", 300, 120, {"hash": 30, "vram": 6}),
    Part("gpu_b", "gpu", "NTX 3080sz 12GB", 620, 200, {"hash": 70, "vram": 12}),
    # Fontes: teto de watts
    Part("psu_300", "psu", "PNU Bronze 300W", 0, 0, {"watts": 300}),
    Part("psu_550", "psu", "PNU Silver 550W", 80, 0, {"watts": 550}),
    Part("psu_850", "psu", "PNU Gold Series 850W", 160, 0, {"watts": 850}),
    Part("psu_1200", "psu", "PNU Platinum 1200W", 300, 0, {"watts": 1200}),
    # Cooler/fans: capacidade de dissipação
    Part("cool_stock", "cooler", "Cooler stock", 0, 2, {"cooling": 40}),
    Part("cool_fans", "cooler", "Husky AirFlow (fans)", 60, 6, {"cooling": 95}),
    Part("cool_liquid", "cooler", "Husky Hydro 240", 160, 10, {"cooling": 170}),
    # Roteadores: qualidade do sinal (1..5). Sinal melhor = rota mais limpa,
    # e o rastreamento passivo demora mais para te achar.
    Part("net_dsl", "router", "Carrier DSL Modem", 0, 8, {"signal": 1}),
    Part("net_husky", "router", "Router Husky Pro", 120, 12, {"signal": 3}),
    Part("net_husky_x", "router", "Router Husky X-Band", 340, 18, {"signal": 5}),
]

CATALOG: dict[str, Part] = {p.id: p for p in _PARTS}


def parts_of(kind: str) -> list[Part]:
    return [p for p in _PARTS if p.kind == kind]


# --------------------------------------------------------------------------- #
# A montagem
# --------------------------------------------------------------------------- #
@dataclass
class Rig:
    mobo: str = "mb_a1"
    cpu: str = "cpu_s1"
    ram: list[str] = field(default_factory=lambda: ["ram_d3_4"])
    gpus: list[str] = field(default_factory=list)  # uma por slot PCIe
    psu: str = "psu_300"
    cooler: str = "cool_stock"
    router: str = "net_dsl"

    def copy(self) -> "Rig":
        return Rig(
            self.mobo,
            self.cpu,
            list(self.ram),
            list(self.gpus),
            self.psu,
            self.cooler,
            self.router,
        )


def starting_rig() -> Rig:
    return Rig()


@dataclass
class Derived:
    hashrate: float
    ram_gb: int
    ddr: str
    slots_used: int
    slots_total: int
    pcie_used: int
    pcie_total: int
    power_idle: int
    power_load: int
    max_power: int
    cooling: int
    typing_bonus: float
    tele_mult: float
    signal: int
    cores: int


def derived(rig: Rig) -> Derived:
    mobo = CATALOG[rig.mobo]
    cpu = CATALOG[rig.cpu]
    cooler = CATALOG[rig.cooler]
    router = CATALOG[rig.router]
    gpus = [CATALOG[g] for g in rig.gpus]
    sticks = [CATALOG[s] for s in rig.ram]

    ram_gb = sum(s.specs["size"] for s in sticks)
    avg_speed = (sum(s.specs["speed"] for s in sticks) / len(sticks)) if sticks else 1.0
    # mineração memory-hard: RAM (capacidade x velocidade) escala o hashrate
    ram_bonus = min(2.5, (ram_gb / 16.0) * avg_speed * 0.6)
    hashrate = cpu.specs["hash"] * (1 + ram_bonus) + sum(g.specs["hash"] for g in gpus)

    power_load = (
        mobo.tdp
        + cpu.tdp
        + cooler.tdp
        + router.tdp
        + sum(s.tdp for s in sticks)
        + sum(g.tdp for g in gpus)
    )
    power_idle = round(power_load * 0.35)

    return Derived(
        hashrate=round(hashrate, 1),
        ram_gb=ram_gb,
        ddr=mobo.specs["ddr"],
        slots_used=len(sticks),
        slots_total=mobo.specs["slots"],
        pcie_used=len(gpus),
        pcie_total=mobo.specs["pcie"],
        power_idle=power_idle,
        power_load=power_load,
        max_power=mobo.specs["max_power"],
        cooling=cooler.specs["cooling"],
        typing_bonus=cpu.specs["typing"],
        tele_mult=cpu.specs["tele"],
        signal=router.specs["signal"],
        cores=cpu.specs["cores"],
    )


# --------------------------------------------------------------------------- #
# Telemetria do rig — o que o HUD mostra como "uso agora"
# --------------------------------------------------------------------------- #
SIGNAL_MAX = 5
_IDLE_CPU = 6  # o OS sempre mastiga alguma coisa


@dataclass
class Telemetry:
    cpu_pct: int
    gpu_pct: list[int]  # uma leitura por GPU instalada
    ram_used_gb: float
    ram_total_gb: int
    watts: int
    watts_max: int
    psu_pct: int
    signal: int
    signal_max: int


def telemetry(rig: Rig, mining: bool, throttled: bool = False) -> Telemetry:
    """Leitura instantânea do rig. Função pura do estado: o HUD não inventa
    número nenhum, e o teste consegue prever tudo."""
    d = derived(rig)
    if mining:
        cpu = 45 if throttled else 97
        gpu = [40 if throttled else 96 for _ in rig.gpus]
        # memory-hard: minerando, a tabela ocupa quase toda a RAM do rig
        ram_used = d.ram_gb * (0.5 if throttled else 0.86)
    else:
        cpu = _IDLE_CPU
        gpu = [0 for _ in rig.gpus]
        ram_used = min(d.ram_gb, 1.2)
    watts = d.power_load if mining else d.power_idle
    watts_max = CATALOG[rig.psu].specs["watts"]
    return Telemetry(
        cpu_pct=cpu,
        gpu_pct=gpu,
        ram_used_gb=round(ram_used, 1),
        ram_total_gb=d.ram_gb,
        watts=watts,
        watts_max=watts_max,
        psu_pct=min(100, round(watts / max(1, watts_max) * 100)),
        signal=d.signal,
        signal_max=SIGNAL_MAX,
    )


def heat_equilibrium(rig: Rig, mining: bool) -> float:
    d = derived(rig)
    watts = d.power_load if mining else d.power_idle
    return AMBIENT + (watts / max(1, d.cooling)) * HEAT_K


# --------------------------------------------------------------------------- #
# Compatibilidade / instalação
# --------------------------------------------------------------------------- #
_STACKABLE = ("ram", "gpu")  # dá para ter várias; o resto é peça única


def is_installed(rig: Rig, part: Part) -> bool:
    """RAM e GPU nunca contam como 'instaladas': várias iguais são válidas."""
    if part.kind in _STACKABLE:
        return False
    return getattr(rig, part.kind) == part.id


def can_install(rig: Rig, part: Part) -> tuple[bool, str]:
    mobo = CATALOG[rig.mobo]
    if part.kind == "ram":
        if part.specs["ddr"] != mobo.specs["ddr"]:
            return False, i18n.t(
                "hw_ram_wrong_gen",
                board_ddr=mobo.specs["ddr"],
                part_ddr=part.specs["ddr"],
            )
        if len(rig.ram) >= mobo.specs["slots"]:
            return False, i18n.t("hw_ram_no_slots", slots=mobo.specs["slots"])
    elif part.kind == "cpu":
        if part.specs["socket"] != mobo.specs["socket"]:
            return False, i18n.t(
                "hw_cpu_wrong_socket",
                board_socket=mobo.specs["socket"],
                cpu_socket=part.specs["socket"],
            )
    elif part.kind == "gpu":
        if mobo.specs["pcie"] < 1:
            return False, i18n.t("hw_gpu_no_pcie")
        if len(rig.gpus) >= mobo.specs["pcie"]:
            return False, i18n.t("hw_gpu_no_slots", slots=mobo.specs["pcie"])
    # checagem de fonte após a hipotética instalação
    hypothetical = _with(rig, part)
    d = derived(hypothetical)
    watts = CATALOG[hypothetical.psu].specs["watts"]
    if part.kind != "psu" and d.power_load > watts * 0.9:
        return False, i18n.t(
            "hw_psu_insufficient", needed=int(d.power_load / 0.9), available=watts
        )
    if d.power_load > d.max_power:
        return False, i18n.t("hw_power_exceeds_board")
    return True, "ok"


def _with(rig: Rig, part: Part) -> Rig:
    """Cópia do rig com a peça aplicada (sem validar)."""
    new = rig.copy()
    if part.kind == "ram":
        new.ram = list(rig.ram) + [part.id]
    elif part.kind == "gpu":
        new.gpus = list(rig.gpus) + [part.id]
    else:
        setattr(new, part.kind, part.id)
    return new


def install(rig: Rig, part: Part) -> list[str]:
    """Instala a peça no rig. Ao trocar de placa-mãe, remove RAM/CPU/GPU que
    não couberem no novo socket/DDR/PCIe. Retorna avisos."""
    warnings: list[str] = []
    if part.kind == "ram":
        rig.ram.append(part.id)
    elif part.kind == "gpu":
        rig.gpus.append(part.id)
    elif part.kind == "mobo":
        rig.mobo = part.id
        # RAM incompatível some
        kept = [s for s in rig.ram if CATALOG[s].specs["ddr"] == part.specs["ddr"]]
        if len(kept) != len(rig.ram):
            warnings.append(i18n.t("hw_warn_ram_discarded"))
        rig.ram = kept[: part.specs["slots"]]
        # GPUs além dos slots PCIe da nova placa também
        if len(rig.gpus) > part.specs["pcie"]:
            warnings.append(i18n.t("hw_warn_gpu_discarded"))
            rig.gpus = rig.gpus[: part.specs["pcie"]]
        # CPU incompatível volta pra básica compatível, se houver
        if CATALOG[rig.cpu].specs["socket"] != part.specs["socket"]:
            warnings.append(i18n.t("hw_warn_cpu_discarded"))
            rig.cpu = next(
                (
                    c.id
                    for c in parts_of("cpu")
                    if c.specs["socket"] == part.specs["socket"]
                ),
                rig.cpu,
            )
    else:
        setattr(rig, part.kind, part.id)
    return warnings
