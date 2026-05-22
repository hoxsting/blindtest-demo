import { useEffect, useRef, useState } from "react";
import type { Track } from "../api";

declare global {
  interface Window {
    YT?: { Player: new (el: Element, opts: unknown) => YTPlayer };
    onYouTubeIframeAPIReady?: () => void;
  }
}

type YTPlayer = {
  destroy?: () => void;
  loadVideoById: (id: string) => void;
  cueVideoById: (id: string) => void;
  playVideo: () => void;
  pauseVideo: () => void;
};

let apiPromise: Promise<NonNullable<Window["YT"]>> | null = null;
function loadYouTubeAPI(): Promise<NonNullable<Window["YT"]>> {
  if (apiPromise) return apiPromise;
  apiPromise = new Promise((resolve) => {
    if (window.YT?.Player) {
      resolve(window.YT);
      return;
    }
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      if (window.YT) resolve(window.YT);
    };
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  });
  return apiPromise;
}

type Props = {
  tracks: Track[];
};

export function Player({ tracks }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const tracksRef = useRef(tracks);
  const indexRef = useRef(index);

  const current = tracks[index];

  useEffect(() => {
    tracksRef.current = tracks;
    indexRef.current = index;
  }, [tracks, index]);

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [tracks]);

  useEffect(() => {
    let cancelled = false;
    loadYouTubeAPI().then((YT) => {
      if (cancelled || !containerRef.current) return;
      playerRef.current = new YT.Player(containerRef.current, {
        height: "200",
        width: "200",
        videoId: tracksRef.current[0]?.video_id ?? "",
        playerVars: {
          autoplay: 0,
          controls: 0,
          disablekb: 1,
          fs: 0,
          modestbranding: 1,
          rel: 0,
          iv_load_policy: 3,
        },
        events: {
          onStateChange: (e: { data: number }) => {
            if (e.data === 1) setPlaying(true);
            else if (e.data === 2) setPlaying(false);
            else if (e.data === 0) {
              const list = tracksRef.current;
              if (!list.length) return;
              const next = (indexRef.current + 1) % list.length;
              setIndex(next);
              setPlaying(true);
            }
          },
        },
      }) as YTPlayer;
    });
    return () => {
      cancelled = true;
      try {
        playerRef.current?.destroy?.();
      } catch {
        /* ignore */
      }
      playerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const player = playerRef.current;
    if (!player || !current) return;
    if (playing) player.loadVideoById(current.video_id);
    else player.cueVideoById(current.video_id);
  }, [index, current?.video_id]);

  function togglePlay() {
    const player = playerRef.current;
    if (!player) return;
    if (playing) player.pauseVideo();
    else player.playVideo();
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
        <div className="player-meta">{current.year || ""}</div>
      </div>

      <div className="yt-hidden" aria-hidden="true">
        <div ref={containerRef} />
      </div>

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
