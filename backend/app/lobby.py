from __future__ import annotations

import asyncio
import secrets
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket

from .models import LobbyState, Player, Track


@dataclass
class _PlayerRecord:
    player: Player
    token: str


class Lobby:
    def __init__(self) -> None:
        self._players: dict[str, _PlayerRecord] = {}
        self._tokens: dict[str, str] = {}
        self._connections: dict[str, WebSocket] = {}
        self._host_id: str | None = None
        self._playlist: list[Track] = []
        self._playlist_url: str | None = None
        self._lock = asyncio.Lock()

    @property
    def host_id(self) -> str | None:
        return self._host_id

    def state(self) -> LobbyState:
        return LobbyState(
            players=[record.player for record in self._players.values()],
            host_id=self._host_id,
            playlist=list(self._playlist),
            playlist_url=self._playlist_url,
        )

    def is_host_token(self, token: str) -> bool:
        player = self.player_from_token(token)
        return player is not None and player.is_host

    async def set_playlist(self, url: str, tracks: list[Track]) -> None:
        async with self._lock:
            self._playlist = tracks
            self._playlist_url = url
        await self.broadcast({"type": "state", **self.state().model_dump()})

    def username_taken(self, username: str) -> bool:
        lowered = username.strip().lower()
        return any(
            record.player.username.lower() == lowered for record in self._players.values()
        )

    async def add_player(self, username: str, is_host: bool) -> tuple[Player, str]:
        async with self._lock:
            if self.username_taken(username):
                raise ValueError("username already taken")
            player_id = uuid.uuid4().hex
            token = secrets.token_urlsafe(16)
            player = Player(id=player_id, username=username.strip(), is_host=is_host)
            self._players[player_id] = _PlayerRecord(player=player, token=token)
            self._tokens[token] = player_id
            if is_host and self._host_id is None:
                self._host_id = player_id
        await self.broadcast({"type": "state", **self.state().model_dump()})
        return player, token

    def player_from_token(self, token: str) -> Player | None:
        player_id = self._tokens.get(token)
        if player_id is None:
            return None
        record = self._players.get(player_id)
        return record.player if record else None

    async def register_connection(self, token: str, websocket: WebSocket) -> Player | None:
        player_id = self._tokens.get(token)
        if player_id is None:
            return None
        self._connections[player_id] = websocket
        record = self._players[player_id]
        return record.player

    async def remove_connection(self, token: str) -> None:
        player_id = self._tokens.get(token)
        if player_id is None:
            return
        self._connections.pop(player_id, None)
        async with self._lock:
            self._players.pop(player_id, None)
            self._tokens.pop(token, None)
            if self._host_id == player_id:
                self._host_id = None
        await self.broadcast({"type": "state", **self.state().model_dump()})

    async def broadcast(self, message: dict) -> None:
        dead: list[str] = []
        for player_id, ws in list(self._connections.items()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(player_id)
        for player_id in dead:
            self._connections.pop(player_id, None)


lobby = Lobby()
