import { useState } from "react";
import type { LobbyState } from "../api";
import { startSession } from "../api";

type Props = {
  state: LobbyState;
  connected: boolean;
  me: { playerId: string; isHost: boolean; token: string };
};

export function Lobby({ state, connected, me }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setBusy(true);
    setError(null);
    try {
      await startSession(me.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <h1>🎵 Salon</h1>
      <p className="subtitle">
        {connected ? `${state.players.length} joueur(s) connecté(s)` : "Connexion…"}
      </p>

      <div className="player-grid">
        {state.players.map((p) => (
          <div
            key={p.id}
            className={`player-card${p.id === me.playerId ? " me" : ""}`}
          >
            <div className="player-name">{p.username}</div>
            {p.is_host && <div className="badge">Hôte</div>}
          </div>
        ))}
      </div>

      {error && <p className="error">{error}</p>}

      {me.isHost && (
        <button
          className="primary"
          onClick={handleStart}
          disabled={busy || state.players.length === 0}
        >
          {busy ? "Démarrage…" : "Démarrer la partie"}
        </button>
      )}
      {!me.isHost && (
        <p className="hint">En attente de l'hôte pour démarrer la partie…</p>
      )}
    </div>
  );
}
