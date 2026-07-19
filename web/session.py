"""SessionManager — uma run isolada por jogador.

Cada visitante recebe um cookie de sessão (id aleatório). O `WebSession`
(estado do jogo + modo + combate/lockdown ativos) fica em memória, indexado
por esse id; persiste em disco só quando o jogador pede `save` (ou ao
desconectar, como rede de segurança), reaproveitando `savegame.state_to_dict`/
`state_from_dict` — só troca o path fixo (`SAVE_PATH`) por um por sessão.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from coldboot import savegame
from coldboot.webengine import WebSession
from coldboot.world import new_game

SESSIONS_DIR = Path(__file__).parent / "sessions"
COOKIE_NAME = "coldboot_session"


class SessionManager:
    def __init__(self) -> None:
        self._live: dict[str, WebSession] = {}
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return SESSIONS_DIR / f"{session_id}.json"

    def new_id(self) -> str:
        while True:
            sid = secrets.token_urlsafe(24)
            if sid not in self._live and not self._path(sid).exists():
                return sid

    def get_or_create(self, session_id: str | None) -> tuple[str, WebSession]:
        """Devolve (id, sessão). Cria id novo se `session_id` for None/desconhecido
        e não houver save em disco para reabrir."""
        if session_id and session_id in self._live:
            return session_id, self._live[session_id]
        if session_id:
            loaded = self._load_from_disk(session_id)
            if loaded is not None:
                self._live[session_id] = loaded
                return session_id, loaded
        # sessão nova: run do zero
        sid = session_id or self.new_id()
        web = WebSession(state=new_game())
        self._live[sid] = web
        return sid, web

    def _load_from_disk(self, session_id: str) -> WebSession | None:
        p = self._path(session_id)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        data = savegame.migrate(data)
        if data is None:
            return None
        try:
            state = savegame.state_from_dict(data)
        except (KeyError, TypeError):
            return None
        return WebSession(state=state)

    def save(self, session_id: str) -> bool:
        web = self._live.get(session_id)
        if web is None or web.mode != "explore":
            return False
        try:
            savegame.save(web.state, self._path(session_id))
        except OSError:
            return False
        return True

    def drop(self, session_id: str) -> None:
        """Chamado ao desconectar: tira da memória (mantém o save em disco,
        se houver — só encerra a sessão viva, não apaga progresso salvo)."""
        self._live.pop(session_id, None)


manager = SessionManager()
