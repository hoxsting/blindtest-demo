export type Player = {
  id: string;
  username: string;
  is_host: boolean;
};

export type LobbyState = {
  players: Player[];
  host_id: string | null;
};

export type JoinResponse = {
  player_id: string;
  token: string;
  is_host: boolean;
};

export async function joinLobby(
  username: string,
  hostToken: string | null,
): Promise<JoinResponse> {
  const res = await fetch("/api/join", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, host_token: hostToken }),
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => b.detail)
      .catch(() => res.statusText);
    throw new Error(typeof detail === "string" ? detail : "join failed");
  }
  return res.json();
}
