import type { LobbyState } from "../api";

type Props = {
  state: LobbyState;
  connected: boolean;
  me: { playerId: string; isHost: boolean };
};

export function Lobby({ state, connected, me }: Props) {
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

      {me.isHost && (
        <button className="primary" disabled title="Disponible à la prochaine itération">
          Démarrer la partie
        </button>
      )}
      {!me.isHost && (
        <p className="hint">En attente de l'hôte pour démarrer la partie…</p>
      )}
    </div>
  );
}
