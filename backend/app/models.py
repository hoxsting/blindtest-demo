from typing import List, Optional

from pydantic import BaseModel, Field


class Player(BaseModel):
    id: str
    username: str
    is_host: bool = False


class JoinRequest(BaseModel):
    username: str = Field(min_length=1, max_length=24)
    host_token: Optional[str] = None


class JoinResponse(BaseModel):
    player_id: str
    token: str
    is_host: bool


class LobbyState(BaseModel):
    players: List[Player]
    host_id: Optional[str]


class AnswerRequest(BaseModel):
    guess: str = Field(min_length=1, max_length=120)


class CommandResponse(BaseModel):
    ok: bool
