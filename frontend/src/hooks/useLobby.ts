import { useEffect, useRef, useState } from "react";
import type { LobbyState } from "../api";

export function useLobby(token: string | null) {
  const [state, setState] = useState<LobbyState>({
    players: [],
    host_id: null,
    playlist: [],
    playlist_url: null,
  });
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    let retry: number | undefined;

    function open() {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(
        `${proto}://${window.location.host}/ws?token=${encodeURIComponent(token!)}`,
      );
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "state") {
            setState({
              players: msg.players,
              host_id: msg.host_id,
              playlist: msg.playlist ?? [],
              playlist_url: msg.playlist_url ?? null,
            });
          }
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

  return { state, connected };
}
