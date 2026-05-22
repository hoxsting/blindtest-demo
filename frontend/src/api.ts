export type Player = {
  id: string;
  username: string;
  is_host: boolean;
};

export type Track = {
  id: string;
  name: string;
  artists: string;
  album: string;
  year: string;
  preview_url: string;
  duration_ms: number;
};

export type LobbyState = {
  players: Player[];
  host_id: string | null;
  playlist: Track[];
  playlist_url: string | null;
};

export type JoinResponse = {
  player_id: string;
  token: string;
  is_host: boolean;
};

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => b.detail)
      .catch(() => res.statusText);
    throw new Error(typeof detail === "string" ? detail : `${url} failed`);
  }
  return res.json() as Promise<T>;
}

export function joinLobby(
  username: string,
  hostToken: string | null,
): Promise<JoinResponse> {
  return postJson("/api/join", { username, host_token: hostToken });
}

export function loadPlaylist(
  token: string,
  playlistUrl: string,
): Promise<{ loaded: number }> {
  return postJson("/api/playlist", { token, playlist_url: playlistUrl });
}
