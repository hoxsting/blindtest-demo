import type { LobbyState } from "../api";
import { PlaylistLoader } from "./PlaylistLoader";
import { Player } from "./Player";

type Props = {
  state: LobbyState;
  connected: boolean;
  me: { playerId: string; isHost: boolean; token: string };
};

export function Lobby({ state, connected, me }: Props) {
  const hasPlaylist = state.playlist.length > 0;

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
        <section className="section">
          <h2>Playlist Spotify</h2>
          <PlaylistLoader token={me.token} currentUrl={state.playlist_url} />
          {hasPlaylist && <Player tracks={state.playlist} />}
        </section>
      )}

      {!me.isHost && (
        <p className="hint">
          {hasPlaylist
            ? `Playlist chargée — ${state.playlist.length} piste(s). En attente du démarrage…`
            : "En attente de l'hôte pour configurer la playlist…"}
        </p>
      )}

      {me.isHost && (
        <button
          className="primary"
          disabled
          title="Disponible à la prochaine itération"
        >
          Démarrer la partie
        </button>
      )}
    </div>
  );
}
