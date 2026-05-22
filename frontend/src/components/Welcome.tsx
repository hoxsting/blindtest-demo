import { useState } from "react";
import { joinLobby } from "../api";

type Props = {
  hostToken: string | null;
  onJoined: (token: string, playerId: string, isHost: boolean) => void;
};

export function Welcome({ hostToken, onJoined }: Props) {
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await joinLobby(username.trim(), hostToken);
      onJoined(res.token, res.player_id, res.is_host);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="screen">
      <h1>🎵 Blind Test</h1>
      <p className="subtitle">
        {hostToken ? "Tu es l'hôte — choisis ton pseudo" : "Rejoins le salon"}
      </p>
      <form className="card" onSubmit={submit}>
        <label htmlFor="username">Pseudo</label>
        <input
          id="username"
          type="text"
          value={username}
          autoFocus
          maxLength={24}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Ton pseudo"
          disabled={loading}
        />
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading || !username.trim()}>
          {loading ? "Connexion…" : "Rejoindre"}
        </button>
      </form>
    </div>
  );
}
