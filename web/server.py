"""FastAPI + WebSocket — a versão web do COLD-BOOT (onda 1: núcleo jogável).

Roda com: `uvicorn web.server:app --reload` (a partir da raiz do repo).

Um WebSocket por jogador. O cookie de sessão (token aleatório opaco) escolhe
qual `WebSession` (coldboot/webengine.py) essa conexão fala — cada jogador só
enxerga o próprio estado. Uma tarefa assíncrona por conexão avança os
minigames (ICE/LOCKDOWN) a 10Hz e empurra o snapshot puro-JSON de volta.

NOTA de produção: o cookie aqui não é assinado — suficiente pra um protótipo
onde a única coisa em jogo é o progresso da própria run, mas atrás de HTTPS
e, se algum dia importar impedir sequestro de sessão, trocar por um token
assinado (ex.: `itsdangerous`).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from coldboot.webengine import WebSession, snapshot
from coldboot.world import new_game
from web.session import COOKIE_NAME, manager

STATIC_DIR = Path(__file__).parent / "static"
TICK_SECONDS = 0.1

app = FastAPI(title="COLD-BOOT web")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index(request: Request):
    resp = FileResponse(STATIC_DIR / "index.html")
    if not request.cookies.get(COOKIE_NAME):
        sid = manager.new_id()
        resp.set_cookie(
            COOKIE_NAME, sid, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax"
        )
    return resp


async def _send(ws: WebSocket, lock: asyncio.Lock, payload: dict) -> None:
    async with lock:
        await ws.send_json(payload)


async def _tick_loop(ws: WebSocket, lock: asyncio.Lock, sid: str) -> None:
    """Avança combate/LOCKDOWN/creep de Trace/economia a 10Hz.

    Só EMPURRA snapshot pro cliente quando há algo em tempo real pra animar
    (duelo/LOCKDOWN ativo, com o relógio correndo), quando o minerador está
    rodando (carteira/calor sobem em silêncio, sem gerar log — o jogador
    precisa ver os números andando) ou quando o tick produziu um evento de
    verdade (ex.: creep de Trace estourou o LOCKDOWN). Fora disso (modo
    "explore" parado, nada rodando) não manda nada — evita reconstruir a tela
    inteira 10x/s à toa, o que no celular fica pior que só flicker: interrompe
    o toque no meio do gesto porque o elemento embaixo do dedo já foi trocado.
    """
    while True:
        await asyncio.sleep(TICK_SECONDS)
        _, web = manager.get_or_create(sid)
        log = web.tick(TICK_SECONDS)
        mining = "miner" in web.state.processes
        if web.mode in ("combat", "lockdown") or mining or log:
            await _send(ws, lock, {"type": "state", "snapshot": snapshot(web), "log": log})


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    sid = websocket.cookies.get(COOKIE_NAME) or manager.new_id()
    _, web = manager.get_or_create(sid)
    lock = asyncio.Lock()

    await _send(websocket, lock, {
        "type": "state", "snapshot": snapshot(web), "log": [], "session_id": sid,
    })

    ticker = asyncio.create_task(_tick_loop(websocket, lock, sid))
    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")
            target = msg.get("target")
            text = msg.get("text", "")
            log: list[dict] = []
            _, web = manager.get_or_create(sid)

            if action == "cd":
                web.do_cd(target, log)
            elif action == "cat":
                web.do_cat(target, log)
            elif action == "look":
                web.do_look(target, log)
            elif action == "scan":
                web.do_scan(log)
            elif action == "hack":
                web.do_hack(target, log)
            elif action == "combat_submit":
                web.combat_submit(text, log)
            elif action == "lockdown_submit":
                web.lockdown_submit(text, log)
            elif action == "reboot":
                web.do_reboot(log)
            elif action == "take":
                web.do_take(target, log)
            elif action == "drop":
                web.do_drop(target, log)
            elif action == "use":
                # args: [nome] ou [nome, alvo] — mesma convenção de app.py:do_use
                web.do_use(msg.get("args") or ([target] if target else []), log)
            elif action == "run":
                web.do_run(target, log)
            elif action == "kill":
                web.do_kill(target, log)
            elif action == "save":
                ok = manager.save(sid)
                log.append({
                    "text": "run salva." if ok else "não dá pra salvar agora.",
                    "kind": "info" if ok else "warn",
                })
            elif action == "new_run":
                # abandona a run atual e começa de novo — usado pelo botão
                # "novo jogo" (não existe save automático de meio de setor).
                web = WebSession(state=new_game())
                manager._live[sid] = web

            await _send(websocket, lock, {
                "type": "state", "snapshot": snapshot(web), "log": log,
            })
    except WebSocketDisconnect:
        pass
    finally:
        ticker.cancel()
        manager.save(sid)  # rede de segurança: salva se estava em modo explorável
