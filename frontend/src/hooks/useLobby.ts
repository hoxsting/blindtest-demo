import { useEffect, useRef, useState } from "react";
import type { LobbyState, SessionState } from "../api";

const EMPTY_SESSION: SessionState = {
  phase: "idle",
  roundIndex: null,
  totalRounds: 0,
  timeLeftMs: 0,
  hints: [],
  scores: {},
  reveal: null,
  podium: null,
  restartDeadlineMs: null,
  lastFeedback: null,
};

export function useLobby(token: string | null) {
  const [lobby, setLobby] = useState<LobbyState>({ players: [], host_id: null });
  const [session, setSession] = useState<SessionState>(EMPTY_SESSION);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const feedbackSeq = useRef(0);

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    let retry: number | undefined;

    function applyMessage(msg: any) {
      switch (msg.type) {
        case "state":
          setLobby({ players: msg.players, host_id: msg.host_id });
          return;
        case "session_state":
          // Snapshot after reconnect / late join
          setSession((s) => ({
            ...s,
            phase: msg.phase,
            roundIndex: msg.round_index,
            totalRounds: msg.total_rounds,
            scores: msg.scores ?? {},
          }));
          return;
        case "round_started":
          setSession((s) => ({
            ...s,
            phase: "playing",
            roundIndex: msg.round_index,
            totalRounds: msg.total_rounds,
            timeLeftMs: msg.time_left_ms,
            hints: [],
            reveal: null,
          }));
          return;
        case "hint":
          setSession((s) => ({
            ...s,
            hints: [...s.hints, { kind: msg.kind, value: msg.value }],
          }));
          return;
        case "answer_feedback":
          feedbackSeq.current += 1;
          setSession((s) => ({
            ...s,
            scores: msg.scores_total ?? s.scores,
            // Shorten chrono visually when someone gets the full match
            timeLeftMs: msg.is_first_full ? Math.min(s.timeLeftMs, 5000) : s.timeLeftMs,
            lastFeedback: {
              playerId: msg.player_id,
              correct: msg.correct,
              kind: msg.kind,
              isFirstFull: msg.is_first_full,
              seq: feedbackSeq.current,
            },
          }));
          return;
        case "round_ended":
          setSession((s) => ({
            ...s,
            reveal: msg.song,
            scores: msg.scores_total ?? s.scores,
            timeLeftMs: 0,
          }));
          return;
        case "session_ended":
          setSession((s) => ({
            ...s,
            phase: "final",
            podium: msg.podium,
            scores: msg.scores_total ?? s.scores,
          }));
          return;
        case "restart_prompt":
          setSession((s) => ({
            ...s,
            restartDeadlineMs: Date.now() + msg.deadline_ms,
          }));
          return;
        case "session_terminated":
          setSession({ ...EMPTY_SESSION });
          return;
      }
    }

    function open() {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(
        `${proto}://${window.location.host}/ws?token=${encodeURIComponent(token!)}`,
      );
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          applyMessage(JSON.parse(ev.data));
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          retry = window.setTimeout(open, 1500);
        }
      };
      ws.onerror = () => ws.close();
    }

    open();

    return () => {
      cancelled = true;
      if (retry) window.clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [token]);

  return { state: lobby, session, connected };
}
