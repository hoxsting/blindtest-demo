import { useState } from "react";
import { loadPlaylist } from "../api";

type Props = {
  token: string;
  currentUrl: string | null;
};

export function PlaylistLoader({ token, currentUrl }: Props) {
  const [url, setUrl] = useState(currentUrl ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const res = await loadPlaylist(token, url.trim());
      setInfo(`${res.loaded} piste(s) chargée(s)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="card playlist-loader" onSubmit={submit}>
      <label htmlFor="playlist-url">URL de playlist Spotify</label>
      <input
        id="playlist-url"
        type="url"
        value={url}
        placeholder="https://open.spotify.com/playlist/…"
        onChange={(e) => setUrl(e.target.value)}
        disabled={loading}
      />
      {error && <p className="error">{error}</p>}
      {info && <p className="info">{info}</p>}
      <button type="submit" disabled={loading || !url.trim()}>
        {loading ? "Chargement…" : currentUrl ? "Recharger" : "Charger"}
      </button>
    </form>
  );
}
