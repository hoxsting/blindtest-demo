import secrets
import socket
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .lobby import lobby
from .models import JoinRequest, JoinResponse, LoadPlaylistRequest, Track
from .youtube import YouTubeError, fetch_playlist_tracks

HOST_TOKEN = secrets.token_urlsafe(8)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Blind Test")


def _all_local_ips() -> list[tuple[str, str]]:
    """Return [(interface, ip), ...] for non-loopback IPv4 interfaces."""
    results: list[tuple[str, str]] = []
    try:
        out = subprocess.check_output(["ip", "-4", "-o", "addr"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "inet":
                iface = parts[1]
                ip = parts[3].split("/")[0]
                if ip != "127.0.0.1":
                    results.append((iface, ip))
    except (FileNotFoundError, subprocess.CalledProcessError):
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip != "127.0.0.1":
                results.append(("?", ip))
        except OSError:
            pass
    return results


@app.on_event("startup")
async def _print_urls() -> None:
    ips = _all_local_ips()
    port = 8000
    print()
    print("=" * 70)
    print("🎵  Blind Test server running")
    print()
    if not ips:
        print("   ⚠️  Aucune IP locale détectée — utilise http://127.0.0.1:8000/")
    else:
        print("   Interfaces réseau détectées :")
        for iface, ip in ips:
            print(f"     • {iface:<10} → http://{ip}:{port}/")
        print()
        primary = ips[0][1]
        print(f"   Host link (pour toi)     : http://{primary}:{port}/?host={HOST_TOKEN}")
        print(f"   Player link (à partager) : http://{primary}:{port}/")
        print()
        print("   👉 Si l'invité ne voit pas le salon, essaie une AUTRE IP de la liste")
        print("      ci-dessus (en général celle de ton Wi-Fi, type 192.168.x.x).")
    print("=" * 70)
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


@app.post("/api/playlist")
async def load_playlist(req: LoadPlaylistRequest) -> JSONResponse:
    if not lobby.is_host_token(req.token):
        raise HTTPException(status_code=403, detail="Seul l'hôte peut charger une playlist")
    try:
        raw_tracks = fetch_playlist_tracks(req.playlist_url)
    except YouTubeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    tracks = [Track(**t) for t in raw_tracks]
    if not tracks:
        raise HTTPException(
            status_code=400,
            detail="Aucune piste jouable trouvée dans cette playlist YouTube",
        )
    await lobby.set_playlist(req.playlist_url, tracks)
    return JSONResponse({"loaded": len(tracks)})


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
