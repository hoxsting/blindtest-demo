import { useEffect, useRef } from "react";
import { skipRound } from "../api";
import {
  FATAL_YT_ERRORS,
  YT_ERROR_DESCRIPTIONS,
  YT_STATE_NAMES,
  loadYouTubeAPI,
  type YTPlayer,
} from "../lib/youtubeApi";

type Props = {
  videoId: string | null;
  hostToken: string | null;
};

// How long we wait, after loading a video, before deciding it's unplayable
// and asking the backend to move on. Region-restricted / age-restricted /
// "unavailable" videos often pass the oEmbed pre-check but then never reach
// the "playing" state in the iframe — that's exactly what this catches.
const WATCHDOG_MS = 8000;

// YouTube iframe driven entirely by the session's `videoId`. When videoId
// changes, we load + autoplay it. When it becomes null (round ended), we
// stop. If the video errors or never starts playing within WATCHDOG_MS,
// the host's client asks the backend to skip to the next round.
export function SessionPlayer({ videoId, hostToken }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const readyRef = useRef(false);
  const pendingVideoRef = useRef<string | null>(videoId);
  const watchdogRef = useRef<number | null>(null);
  const watchedVideoRef = useRef<string | null>(null);

  function clearWatchdog() {
    if (watchdogRef.current !== null) {
      window.clearTimeout(watchdogRef.current);
      watchdogRef.current = null;
    }
  }

  function armWatchdog(forVideoId: string) {
    clearWatchdog();
    watchedVideoRef.current = forVideoId;
    watchdogRef.current = window.setTimeout(() => {
      // Only fire if we're still on the same video; otherwise stale.
      if (watchedVideoRef.current !== forVideoId) return;
      console.warn(
        `[SessionPlayer] watchdog: ${forVideoId} never reached "playing" within ${WATCHDOG_MS}ms — asking backend to skip`,
      );
      requestSkip("watchdog timeout");
    }, WATCHDOG_MS);
  }

  function requestSkip(reason: string) {
    if (!hostToken) {
      console.log(`[SessionPlayer] skip requested (${reason}) — not host, ignored`);
      return;
    }
    console.log(`[SessionPlayer] requesting skip (rights): ${reason}`);
    skipRound(hostToken, "rights").catch((err) =>
      console.warn("[SessionPlayer] skip request failed:", err),
    );
  }

  useEffect(() => {
    let cancelled = false;
    loadYouTubeAPI().then((YT) => {
      if (cancelled || !containerRef.current) return;
      console.log("[SessionPlayer] creating YT.Player");
      playerRef.current = new YT.Player(containerRef.current, {
        height: "180",
        width: "320",
        videoId: pendingVideoRef.current ?? "",
        playerVars: {
          autoplay: 1,
          controls: 1,
          disablekb: 1,
          fs: 0,
          modestbranding: 1,
          rel: 0,
          iv_load_policy: 3,
        },
        events: {
          onReady: () => {
            readyRef.current = true;
            console.log("[SessionPlayer] ready");
            const pending = pendingVideoRef.current;
            if (pending) {
              playerRef.current?.loadVideoById(pending);
              armWatchdog(pending);
            }
          },
          onError: (e: { data: number }) => {
            const desc = YT_ERROR_DESCRIPTIONS[e.data] ?? "unknown error";
            console.warn(
              `[SessionPlayer] YT error ${e.data}: ${desc} (video=${watchedVideoRef.current ?? "?"})`,
            );
            if (FATAL_YT_ERRORS.has(e.data)) {
              clearWatchdog();
              requestSkip(`YT error ${e.data}`);
            }
          },
          onStateChange: (e: { data: number }) => {
            const name = YT_STATE_NAMES[e.data] ?? String(e.data);
            console.log(
              `[SessionPlayer] state → ${name} (video=${watchedVideoRef.current ?? "?"})`,
            );
            // Cleared once the video is actually playing — proves the embed
            // is working.
            if (e.data === 1) clearWatchdog();
          },
        },
      }) as YTPlayer;
    });
    return () => {
      cancelled = true;
      clearWatchdog();
      try {
        playerRef.current?.destroy?.();
      } catch {
        /* ignore */
      }
      playerRef.current = null;
      readyRef.current = false;
    };
  }, []);

  useEffect(() => {
    pendingVideoRef.current = videoId;
    const player = playerRef.current;
    if (!player || !readyRef.current) return;
    if (videoId) {
      console.log("[SessionPlayer] loadVideoById", videoId);
      player.loadVideoById(videoId);
      armWatchdog(videoId);
    } else {
      console.log("[SessionPlayer] pause (no videoId)");
      clearWatchdog();
      try {
        player.pauseVideo();
      } catch {
        /* ignore */
      }
    }
  }, [videoId]);

  return (
    <div className="yt-frame" aria-hidden="true">
      <div ref={containerRef} />
    </div>
  );
}
