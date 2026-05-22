import { useEffect, useRef } from "react";
import { FATAL_YT_ERRORS, loadYouTubeAPI, type YTPlayer } from "../lib/youtubeApi";

type Props = {
  videoId: string | null;
};

// YouTube iframe driven entirely by the session's `videoId`. When videoId
// changes, we load + autoplay it. When it becomes null (round ended), we
// stop. The iframe is rendered small but visible — YouTube refuses to play
// in iframes with opacity:0 or display:none. Hide via .yt-offscreen in CSS
// when going to "real blindtest" mode.
export function SessionPlayer({ videoId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const readyRef = useRef(false);
  const pendingVideoRef = useRef<string | null>(videoId);

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
            if (pending) playerRef.current?.loadVideoById(pending);
          },
          onError: (e: { data: number }) => {
            console.warn("[SessionPlayer] YT error code", e.data);
            if (FATAL_YT_ERRORS.has(e.data)) {
              // Can't play this round's song — the host will hear nothing,
              // the round still ticks down on the backend. Future work:
              // notify backend so it skips to the next song.
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
    } else {
      console.log("[SessionPlayer] pause (no videoId)");
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
