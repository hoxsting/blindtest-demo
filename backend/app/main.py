import secrets
import socket
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .lobby import lobby
from .models import JoinRequest, JoinResponse

HOST_TOKEN = secrets.token_urlsafe(8)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Blind Test")


def _local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


@app.on_event("startup")
async def _print_urls() -> None:
    ip = _local_ip()
    port = 8000
    print()
    print("=" * 60)
    print("🎵  Blind Test server running")
    print(f"   Host link (pour toi)     : http://{ip}:{port}/?host={HOST_TOKEN}")
    print(f"   Player link (à partager) : http://{ip}:{port}/")
    print("=" * 60)
    print()


@app.post("/api/join", response_model=JoinResponse)
async def join(req: JoinRequest) -> JoinResponse:
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username vide")
    if lobby.username_taken(username):
        raise HTTPException(status_code=409, detail="pseudo déjà pris")

    is_host = req.host_token is not None and req.host_token == HOST_TOKEN
    if is_host and lobby.host_id is not None:
        is_host = False

    try:
        player, token = await lobby.add_player(username=username, is_host=is_host)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return JoinResponse(player_id=player.id, token=token, is_host=player.is_host)


@app.get("/api/lobby")
async def get_lobby() -> JSONResponse:
    return JSONResponse(lobby.state().model_dump())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str) -> None:
    player = await lobby.register_connection(token, websocket)
    if player is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    await websocket.send_json({"type": "state", **lobby.state().model_dump()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await lobby.remove_connection(token)


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
