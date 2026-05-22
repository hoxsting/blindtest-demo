import { useEffect, useRef, useState } from "react";
import type { Track } from "../api";

type Props = {
  tracks: Track[];
};

export function Player({ tracks }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  const current = tracks[index];

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [tracks]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !current) return;
    audio.src = current.preview_url;
    if (playing) {
      audio.play().catch(() => setPlaying(false));
    }
  }, [index, current, tracks]);

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    } else {
      audio.pause();
      setPlaying(false);
    }
  }

  function go(delta: number) {
    if (!tracks.length) return;
    const next = (index + delta + tracks.length) % tracks.length;
    setIndex(next);
    setPlaying(true);
  }

  if (!current) {
    return <p className="hint">Aucune piste jouable.</p>;
  }

  return (
    <div className="card player">
      <div className="player-now">
        <div className="player-track">{current.name || "—"}</div>
        <div className="player-artists">{current.artists || "—"}</div>
        <div className="player-meta">
          {[current.album, current.year].filter(Boolean).join(" · ")}
        </div>
      </div>

      <audio
        ref={audioRef}
        onEnded={() => go(1)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        controls
        preload="none"
      />

      <div className="player-controls">
        <button type="button" onClick={() => go(-1)} aria-label="Précédent">
          ⏮
        </button>
        <button
          type="button"
          onClick={togglePlay}
          aria-label={playing ? "Pause" : "Lecture"}
          className="primary"
        >
          {playing ? "⏸" : "▶"}
        </button>
        <button type="button" onClick={() => go(1)} aria-label="Suivant">
          ⏭
        </button>
      </div>

      <p className="player-counter">
        {index + 1} / {tracks.length}
      </p>
    </div>
  );
}
