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


class Track(BaseModel):
    id: str
    name: str
    artists: str
    year: str
    video_id: str
    duration_ms: int


class LobbyState(BaseModel):
    players: list[Player]
    host_id: str | None
    playlist: list[Track] = []
    playlist_url: str | None = None


class LoadPlaylistRequest(BaseModel):
    token: str = Field(min_length=1)
    playlist_url: str = Field(min_length=1)
