from pydantic import BaseModel, Field


class Player(BaseModel):
    id: str
    username: str
    is_host: bool = False


class JoinRequest(BaseModel):
    username: str = Field(min_length=1, max_length=24)
    host_token: str | None = None


class JoinResponse(BaseModel):
    player_id: str
    token: str
    is_host: bool


class LobbyState(BaseModel):
    players: list[Player]
    host_id: str | None
