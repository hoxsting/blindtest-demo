import { useEffect, useRef, useState } from "react";
import type { Track } from "../api";
import {
  FATAL_YT_ERRORS,
  YT_ERROR_DESCRIPTIONS,
  YT_STATE_NAMES,
  loadYouTubeAPI,
  type YTPlayer,
} from "../lib/youtubeApi";

type Props = {
  tracks: Track[];
};

export function Player({ tracks }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [skipped, setSkipped] = useState<Set<number>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const tracksRef = useRef(tracks);
  const indexRef = useRef(index);
  const skippedRef = useRef(skipped);

  const current = tracks[index];

  function findNextPlayable(from: number, blocked: Set<number>): number | null {
    if (!tracks.length) return null;
    for (let step = 1; step <= tracks.length; step++) {
      const candidate = (from + step) % tracks.length;
      if (!blocked.has(candidate)) return candidate;
    }
    return null;
  }

  useEffect(() => {
    tracksRef.current = tracks;
    indexRef.current = index;
    skippedRef.current = skipped;
  }, [tracks, index, skipped]);

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
    setSkipped(new Set());
  }, [tracks]);

  useEffect(() => {
    let cancelled = false;
    loadYouTubeAPI().then((YT) => {
      if (cancelled || !containerRef.current) {
        console.log("[Player] cancelled before YT.Player created");
        return;
      }
      console.log(
        "[Player] creating YT.Player with videoId=",
        tracksRef.current[0]?.video_id,
      );
      playerRef.current = new YT.Player(containerRef.current, {
        height: "180",
        width: "320",
        videoId: tracksRef.current[0]?.video_id ?? "",
        playerVars: {
          autoplay: 0,
          controls: 1,
          disablekb: 1,
          fs: 0,
          modestbranding: 1,
          rel: 0,
          iv_load_policy: 3,
        },
        events: {
          onReady: () => console.log("[Player] YT.Player ready"),
          onError: (e: { data: number }) => {
            const desc = YT_ERROR_DESCRIPTIONS[e.data] ?? "unknown error";
            const t = tracksRef.current[indexRef.current];
            console.warn(
              `[Player] YT error ${e.data}: ${desc} (video=${t?.video_id ?? "?"}, ${t?.artists ?? "?"} — ${t?.name ?? "?"})`,
            );
            if (!FATAL_YT_ERRORS.has(e.data)) return;
            const blockedIdx = indexRef.current;
            const list = tracksRef.current;
            const blocked = new Set(skippedRef.current);
            blocked.add(blockedIdx);
            skippedRef.current = blocked;
            setSkipped(blocked);
            const next = findNextPlayable(blockedIdx, blocked);
            if (next === null || blocked.size >= list.length) {
              console.warn(
                "[Player] no playable video left — all tracks blocked embedding",
              );
              setPlaying(false);
              return;
            }
            console.log(
              `[Player] auto-skip (err ${e.data}) → next index`,
              next,
            );
            setIndex(next);
            setPlaying(true);
          },
          onStateChange: (e: { data: number }) => {
            console.log("[Player] state →", YT_STATE_NAMES[e.data] ?? e.data);
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

      <div className="yt-frame" aria-hidden="true">
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
        {skipped.size > 0 && ` · ${skipped.size} ignorée(s) (embedding bloqué)`}
      </p>
    </div>
  );
}
