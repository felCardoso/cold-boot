"""VirtualNetwork — o "mundo" do Breach System: nós, portas, credenciais e arquivos.

Não sabe nada sobre parsing de comando nem sobre Trace Level; só responde
perguntas sobre o estado da rede simulada ("essa porta está aberta?", "esse
arquivo existe?", "essa senha bate?"). Quem interpreta o comando do jogador é
o `CommandParser`; quem aplica as consequências (Trace, progresso) é o
`GameState`. Este módulo é a fonte de verdade dos dados, nada mais.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Portas conhecidas exibidas por `nmap`, mesmo quando fechadas — é isso que
# torna a tabela informativa: ver "21/FTP: aberta" tem menos valor sem ver
# "23/TELNET: fechada" ao lado.
KNOWN_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "TELNET",
    80: "HTTP",
    443: "HTTPS",
    3306: "MYSQL",
}


@dataclass
class VirtualHost:
    """Um nó da rede simulada: um IP com portas, credenciais e um mini-filesystem."""

    ip: str
    hostname: str
    open_ports: set[int] = field(default_factory=set)
    credentials: dict[str, str] = field(default_factory=dict)   # usuario -> senha
    files: dict[str, str] = field(default_factory=dict)         # caminho -> conteúdo

    def port_table(self) -> list[tuple[int, str, bool]]:
        """(porta, serviço, aberta?) para cada porta conhecida, ordenado."""
        return [(port, service, port in self.open_ports)
                for port, service in sorted(KNOWN_PORTS.items())]

    def check_credentials(self, username: str, password: str) -> bool:
        return self.credentials.get(username) == password

    def read_file(self, path: str) -> str | None:
        return self.files.get(path)


class VirtualNetwork:
    """Registro de todos os hosts simulados. Uma instância por partida/tutorial."""

    def __init__(self) -> None:
        self._hosts: dict[str, VirtualHost] = {}

    def add_host(self, host: VirtualHost) -> None:
        self._hosts[host.ip] = host

    def get_host(self, ip: str) -> VirtualHost | None:
        return self._hosts.get(ip)

    def host_exists(self, ip: str) -> bool:
        return ip in self._hosts


def build_academic_corp_network() -> VirtualNetwork:
    """A rede fixa do tutorial: 192.168.1.100, "Corporação Acadêmica".

    Estrutura equivalente ao JSON de exemplo do design doc — hospedada em
    código para reaproveitar `VirtualHost`/`KNOWN_PORTS` em vez de duplicar
    o parsing de um JSON solto.
    """
    net = VirtualNetwork()
    net.add_host(VirtualHost(
        ip="192.168.1.100",
        hostname="ACAD-CORP-01 (Corporação Acadêmica)",
        open_ports={21, 22},
        credentials={"admin": "Cyber2026!"},
        files={
            "ftp_public/log.txt": (
                "220 ProFTPD Server ready.\n"
                "DEBUG: failed login attempt for user 'guest'\n"
                "DEBUG: User admin hash: Q3liZXIyMDI2IQ==\n"
                "DEBUG: connection closed.\n"
            ),
        },
    ))
    return net
