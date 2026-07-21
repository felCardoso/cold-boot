"""GameState — sessão do jogador: Trace Level, nó atual e progresso do tutorial.

Puro (sem I/O, sem print): só guarda números e flags e expõe as regras de
como eles mudam. Quem imprime mensagens é `tutorial.py`; quem decide OS
VALORES de incremento é este módulo, para as duas mecânicas (Trace por erro,
Trace por senha errada) ficarem num lugar só.
"""

from __future__ import annotations

# Incrementos de Trace Level, em pontos percentuais (0-100).
TRACE_ON_ERROR = 5.0            # comando com erro genérico (sintaxe, host/arquivo inexistente...)
TRACE_ON_WRONG_CREDENTIALS = 15.0  # `ssh` com usuário/senha incorretos


class GameState:
    """Estado de uma sessão de invasão."""

    def __init__(self) -> None:
        self.trace_level: float = 0.0
        self.current_node: str = "127.0.0.1"   # onde o "shell" do jogador está agora
        self.compromised: set[str] = set()      # IPs com sessão SSH aberta (is_hacked)
        self.tutorial_step: int = 1             # 1..4, ver tutorial.STEPS
        self.session_active: bool = True        # False quando o Trace estoura ou a run acaba

    # ------------------------------------------------------------------ #
    # Trace Level
    # ------------------------------------------------------------------ #
    def add_trace(self, amount: float) -> None:
        """Soma pontos de Trace, sempre travado em [0, 100].

        Ao atingir 100, a conexão cai: `session_active` vira False e nenhum
        comando novo deveria mais ser processado (quem consome isso é o loop
        de `run_tutorial`).
        """
        self.trace_level = max(0.0, min(100.0, self.trace_level + amount))
        if self.trace_level >= 100.0:
            self.session_active = False

    def register_error(self) -> None:
        self.add_trace(TRACE_ON_ERROR)

    def register_wrong_credentials(self) -> None:
        self.add_trace(TRACE_ON_WRONG_CREDENTIALS)

    @property
    def is_traced(self) -> bool:
        return self.trace_level >= 100.0

    # ------------------------------------------------------------------ #
    # Sessão / nós comprometidos
    # ------------------------------------------------------------------ #
    def is_hacked(self, ip: str) -> bool:
        return ip in self.compromised

    def mark_hacked(self, ip: str) -> None:
        """SSH bem-sucedido: a sessão "pivota" para o novo nó."""
        self.compromised.add(ip)
        self.current_node = ip

    # ------------------------------------------------------------------ #
    # Progresso do tutorial
    # ------------------------------------------------------------------ #
    def advance_tutorial(self) -> None:
        self.tutorial_step += 1
