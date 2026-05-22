export type Player = {
  id: string;
  username: string;
  is_host: boolean;
};

export type Track = {
  id: string;
  name: string;
  artists: string;
  year: string;
  video_id: string;
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

export type SessionPhase = "idle" | "playing" | "final";

export type Song = { artist: string; title: string; year: number | null };

export type PodiumEntry = { player_id: string; score: number; rank: number };

export type SessionState = {
  phase: SessionPhase;
  roundIndex: number | null;
  totalRounds: number;
  timeLeftMs: number;
  hints: { kind: string; value: string }[];
  scores: Record<string, number>;
  reveal: Song | null;
  podium: PodiumEntry[] | null;
  restartDeadlineMs: number | null;
  currentVideoId: string | null;
  lastFeedback:
    | {
        playerId: string;
        correct: boolean;
        kind: "artist" | "title" | "both" | "none";
        isFirstFull: boolean;
        seq: number;
      }
    | null;
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

async function command(path: string, token: string, body?: object): Promise<void> {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Player-Token": token,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => b.detail)
      .catch(() => res.statusText);
    throw new Error(typeof detail === "string" ? detail : `${path} failed`);
  }
}

export const startSession = (token: string) =>
  command("/api/session/start", token);

export const submitAnswer = (token: string, guess: string) =>
  command("/api/session/answer", token, { guess });

export const restartSession = (token: string) =>
  command("/api/session/restart", token);
