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
