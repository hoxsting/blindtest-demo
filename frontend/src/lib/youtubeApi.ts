// Shared loader for the YouTube IFrame Player API. Idempotent: the script
// is injected once, subsequent calls reuse the same promise.

export type YTPlayer = {
  destroy?: () => void;
  loadVideoById: (id: string) => void;
  cueVideoById: (id: string) => void;
  playVideo: () => void;
  pauseVideo: () => void;
  stopVideo?: () => void;
};

type YTGlobal = {
  Player: new (el: Element, opts: unknown) => YTPlayer;
};

declare global {
  interface Window {
    YT?: YTGlobal;
    onYouTubeIframeAPIReady?: () => void;
  }
}

let apiPromise: Promise<YTGlobal> | null = null;

export function loadYouTubeAPI(): Promise<YTGlobal> {
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

// YouTube error codes that mean "this video can never play here".
// 101 & 150 = embedding disabled by uploader; 100 = removed/private; 5 = HTML5 error.
export const FATAL_YT_ERRORS = new Set([5, 100, 101, 150]);

// Human-readable explanations for the YT IFrame error codes — used for logs.
export const YT_ERROR_DESCRIPTIONS: Record<number, string> = {
  2: "request had an invalid parameter (bad video id?)",
  5: "HTML5 player error — content can't be played here",
  100: "video removed, private, or doesn't exist",
  101: "uploader disabled embedding on other sites",
  150: "uploader disabled embedding on other sites (same as 101)",
};

// Player state codes from the YT IFrame API. Logged alongside numeric states
// so they're readable in the console.
export const YT_STATE_NAMES: Record<number, string> = {
  [-1]: "unstarted",
  0: "ended",
  1: "playing",
  2: "paused",
  3: "buffering",
  5: "cued",
};
