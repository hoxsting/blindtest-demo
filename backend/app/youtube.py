"""YouTube playlist metadata extraction via yt-dlp.

We don't fetch audio server-side — playback is done by an embedded YouTube
IFrame Player on the frontend (avoids CORS, signature, and bot-check pain).
yt-dlp is used purely to enumerate the playlist's video IDs and titles, then
we heuristically split "Artist - Title" out of the YouTube video title.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import yt_dlp


class YouTubeError(Exception):
    """Raised when something goes wrong talking to YouTube."""


def _check_embeddable(video_id: str, timeout: float = 3.0) -> bool:
    """Return True iff YouTube's oEmbed endpoint accepts this video.

    oEmbed returns 200 only for videos that are *both* available AND allow
    embedding. 401 = embedding disabled by uploader (error 150 in the IFrame
    player). 404 = removed/private/region-restricted-from-our-IP.

    On a network failure we conservatively return True so a flaky oEmbed
    doesn't wipe out the whole playlist.
    """
    url = (
        "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v="
        f"{video_id}&format=json"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True


def _filter_embeddable(
    tracks: list[dict[str, Any]], max_workers: int = 20
) -> tuple[list[dict[str, Any]], int]:
    """Drop tracks whose YouTube video refuses embedding.

    Returns (kept_tracks, dropped_count). Probes in parallel via a thread
    pool — for a 79-track playlist this completes in roughly 2-5 seconds.
    """
    if not tracks:
        return [], 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        flags = list(ex.map(lambda t: _check_embeddable(t["video_id"]), tracks))
    kept = [t for t, ok in zip(tracks, flags) if ok]
    return kept, len(tracks) - len(kept)


# Title parsing — we get raw YouTube video titles like
#   "PHIFI1 - Eternal Love (Radio Edit) [Official Christmas Video 2025]"
# and we want artist="PHIFI1", title="Eternal Love". Strategy:
#   1. Strip parenthesized/bracketed groups that are upload metadata
#      (anything containing strong markers like "video"/"audio"/"clip"/
#      "official", OR built only of noise words like "remix"/"radio
#      edit"/"hd"/year). Subtitles like "(Are Made Of This)" survive.
#   2. Strip trailing noise tokens (e.g., "~Official Video", "- 1984",
#      "HD 0815007"). Loops until the tail is "real".
#   3. Split on the FIRST occurrence of a strong separator (em-dash, en-dash,
#      pipe, colon, regular ' - '). The " by " connector is a weak fallback
#      used only when no strong separator was found, and it swaps order
#      (e.g., "Say Say Say by Paul McCartney" → artist=Paul..., title=Say...).
#   4. On the right side, peel off trailing " - <noise-only segment>" chains
#      ("Born to Be Alive - Official Video" → "Born to Be Alive").
#   5. Strip quotes around either side ("\"Everybody Wants To Rule...\"").
# Cases the heuristic can't fix (no metadata available): inverted "Title -
# Artist" uploads like "Live is Life - Opus" stay swapped.

# Words inside a parenthetical that, when found, mark it as upload metadata
# regardless of what else is there. "Official Christmas Video 2025" → noise
# because "official" + "video" are present.
_STRONG_NOISE_MARKERS = {
    "official", "officiel", "officielle", "officiale", "ufficiale", "oficial",
    "video", "audio", "clip",
}

# Words that, on their own or combined with year/digits/resolution, make a
# parenthetical noise. "Radio Edit", "Remastered 2010", "99 BPM Version" etc.
_NOISE_WORDS = {
    # English meta
    "music", "musical", "lyric", "lyrics", "karaoke", "hd", "hq", "uhd",
    "remaster", "remastered", "restored", "upscaled", "version", "edit",
    "mix", "remix", "radio", "club", "extended", "shortened", "live",
    "acoustic", "instrumental", "studio", "original", "high", "quality",
    "bpm", "demo", "explicit", "clean", "cover", "widescreen",
    # French meta
    "officiel", "officielle", "officiels", "officielles", "officielle",
    "remasterisé", "remasterise", "remasterisée", "paroles", "version",
    # Italian / Spanish / Portuguese meta
    "ufficiale", "oficial", "testo", "letra",
}

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_RES_RE = re.compile(r"^\d{3,4}p$|^[48]k$", re.IGNORECASE)
_ASPECT_RE = re.compile(r"^\d{1,2}:\d{1,2}$")  # "16:9", "4:3"
_WORD_RE = re.compile(r"[\w']+", re.UNICODE)
# Match a single (...) or [...] group. We don't try to handle nested groups —
# the playlist titles I saw don't nest.
_PAREN_RE = re.compile(r"\s*[\(\[][^\(\)\[\]]*[\)\]]\s*")


def _is_noise_chunk(s: str) -> bool:
    """True if `s` (already trimmed) looks like upload-metadata rather than
    a real subtitle. Used for parenthetical groups and trailing segments."""
    s = re.sub(r"\s+", " ", s.strip().lower())
    if not s:
        return True
    tokens = _WORD_RE.findall(s)
    if not tokens:
        return True
    token_set = set(tokens)
    if token_set & _STRONG_NOISE_MARKERS:
        return True
    # Otherwise: every token must be noise or a year/resolution/plain digit.
    for t in tokens:
        if t in _NOISE_WORDS or t.isdigit():
            continue
        if _YEAR_RE.match(t) or _RES_RE.match(t):
            continue
        return False
    return True


def _is_noise_token(t: str) -> bool:
    """Same predicate as `_is_noise_chunk` but for a single bare token."""
    return (
        t in _NOISE_WORDS
        or t in _STRONG_NOISE_MARKERS
        or t.isdigit()
        or bool(_YEAR_RE.match(t))
        or bool(_RES_RE.match(t))
        or bool(_ASPECT_RE.match(t))
    )


def _strip_noise_parens(s: str) -> str:
    """Drop (...) / [...] groups whose content is upload metadata. Loops so
    that "X (Y) (Z)" gets both groups removed."""
    out = s
    while True:
        replaced = False
        for m in list(_PAREN_RE.finditer(out)):
            inner = m.group(0).strip().strip("()[]").strip()
            if _is_noise_chunk(inner):
                out = (out[: m.start()] + " " + out[m.end():]).strip()
                out = re.sub(r"\s+", " ", out)
                replaced = True
                break
        if not replaced:
            return out


def _strip_trailing_noise(s: str) -> str:
    """Peel off trailing tokens that look like upload metadata.

    "Forever Young ~Official Video" → "Forever Young"
    "Cambodia (1981) HD 0815007"    → "Cambodia (1981)" (parens kept here)
    "Limahl - Never Ending Story - 1984" → "Limahl - Never Ending Story"

    Stops as soon as the last token is "real" content.
    """
    out = s.strip()
    while True:
        m = re.search(r"\s+(\S+)$", out)
        if not m:
            break
        last = m.group(1).strip(",.;:!?")
        toks = _WORD_RE.findall(last.lower())
        # Pure punctuation/junk → strip and continue.
        if not toks:
            out = out[: m.start()].strip()
            continue
        # Also treat "16:9"-style aspect ratios as noise (the whole raw token
        # before tokenisation), even if WORD_RE split it into ["16","9"].
        if _ASPECT_RE.match(last):
            out = out[: m.start()].strip()
            continue
        if all(_is_noise_token(t) for t in toks):
            out = out[: m.start()].strip()
        else:
            break
    return out.rstrip(" -–—|:~,.")


def _strip_leading_noise(s: str) -> str:
    """Mirror of `_strip_trailing_noise` — peel off leading metadata.

    'HQ | Deniece Williams - …' → 'Deniece Williams - …'
    'Clip video Patrick Bruel   Alors …' → 'Patrick Bruel   Alors …'
    """
    out = s.strip()
    while True:
        m = re.match(r"(\S+)\s+", out)
        if not m:
            break
        first = m.group(1).strip(",.;:!?")
        toks = _WORD_RE.findall(first.lower())
        if not toks:
            out = out[m.end():].strip()
            continue
        if _ASPECT_RE.match(first):
            out = out[m.end():].strip()
            continue
        if all(_is_noise_token(t) for t in toks):
            out = out[m.end():].strip()
        else:
            break
    return out.lstrip(" -–—|:~,.")


def _balance_brackets(s: str) -> str:
    """Drop dangling unmatched opening `(` / `[` left behind by trailing-noise
    stripping (e.g. `[Footloose 1984]` → strip `1984]` as a year → leaves
    `[Footloose` → here we trim everything from the dangling `[` onwards)."""
    for opener, closer in (("(", ")"), ("[", "]")):
        while s.count(opener) > s.count(closer):
            idx = s.rfind(opener)
            if idx < 0:
                break
            s = s[:idx].rstrip(" -–—|:~,.")
    return s


def _strip_outer_quotes(s: str) -> str:
    s = s.strip()
    pairs = (('"', '"'), ("'", "'"), ("«", "»"), ("“", "”"), ("‘", "’"))
    for o, c in pairs:
        if len(s) >= 2 and s.startswith(o) and s.endswith(c):
            return s[1:-1].strip()
    return s


# Strong separators tried by position (we pick the earliest occurrence).
_STRONG_SEPARATORS = (" — ", " – ", " ~ ", " | ", " : ", " - ")
# Weak fallback: only used when no strong separator was found.
# " by " is reversed: "Title by Artist" → we swap the two pieces.
_WEAK_BY_RE = re.compile(r"\s+by\s+", re.IGNORECASE)
# A dash glued to words on at least one side: "Catherine Lara-Nuit magique",
# "Milli Vanilli- Girl …". Only considered after strong separators fail.
# Compiled to match the LEFTMOST occurrence.
_WEAK_DASH_RE = re.compile(r"(?<=\w)\s*-\s*(?=\w)")
# Pattern: Artist "Title" with the title quoted at the end.
# Captures both straight-quotes and curly/guillemet variants.
_QUOTED_TITLE_RE = re.compile(
    r'^(?P<artist>.+?)\s+[\"“«]\s*(?P<title>[^"”»]+?)\s*[\"”»]\s*$'
)


def split_artist_title(raw_title: str, fallback_uploader: str = "") -> tuple[str, str]:
    """Best-effort parse of a YouTube video title into (artist, track_title).

    Calibrated against playlist PLun_CS7whKh7hhaUeZnVChGDjdZLYferx and
    similar 80s/90s/pop catalogs. Cases the heuristic can't disambiguate
    without external metadata (e.g., reversed "Title - Artist" uploads,
    titles with no separator at all) fall back to (uploader, full_title).
    """
    cleaned = _strip_noise_parens(raw_title)
    cleaned = _strip_leading_noise(cleaned)
    cleaned = _strip_trailing_noise(cleaned)

    # Find the EARLIEST strong separator (so the leftmost split wins —
    # "Tears For Fears - X - ORIGINAL" splits on the first dash).
    sep, sep_pos = None, -1
    for s in _STRONG_SEPARATORS:
        p = cleaned.find(s)
        if p != -1 and (sep_pos == -1 or p < sep_pos):
            sep_pos, sep = p, s

    if sep is None:
        # Weak fallback 1: "Title by Artist". Swap order.
        m = _WEAK_BY_RE.search(cleaned)
        if m:
            title = _strip_outer_quotes(_strip_trailing_noise(cleaned[: m.start()]))
            artist = _strip_outer_quotes(_strip_trailing_noise(cleaned[m.end():]))
            return artist, title
        # Weak fallback 2: Artist "Title" — quoted song name at the end.
        m = _QUOTED_TITLE_RE.match(cleaned)
        if m:
            return (
                _strip_trailing_noise(m.group("artist")),
                _strip_trailing_noise(m.group("title")),
            )
        # Weak fallback 3: dash glued to words, no whitespace required.
        # Used last because it can misfire on hyphenated words ("Go-Go").
        m = _WEAK_DASH_RE.search(cleaned)
        if m:
            left = _strip_outer_quotes(_strip_trailing_noise(cleaned[: m.start()]))
            right = _strip_outer_quotes(_strip_trailing_noise(cleaned[m.end():]))
            if left and right:
                return left, right
        uploader = fallback_uploader.removesuffix(" - Topic").strip()
        return uploader, _strip_outer_quotes(cleaned)

    left = cleaned[:sep_pos]
    right = cleaned[sep_pos + len(sep):]

    # Peel off trailing " - <noise>" chains on the right side, but keep real
    # subtitles. "Born to Be Alive - Official Video" → "Born to Be Alive".
    while " - " in right:
        head, tail = right.rsplit(" - ", 1)
        if _is_noise_chunk(_strip_outer_quotes(tail)):
            right = head
        else:
            break

    left = _balance_brackets(_strip_outer_quotes(_strip_trailing_noise(left)))
    right = _balance_brackets(_strip_outer_quotes(_strip_trailing_noise(right)))

    if not left:
        left = fallback_uploader.removesuffix(" - Topic").strip()
    return left, right


def extract_year(entry: dict[str, Any]) -> str:
    """Return a 4-digit year string, or empty if unknown.

    yt-dlp gives `release_year`/`release_date` for "- Topic" auto-uploads
    (which are the real song release dates). For regular uploads we fall back
    to the upload date — not the song's release year, but close enough for
    a casual blindtest.
    """
    for key in ("release_year",):
        val = entry.get(key)
        if val:
            return str(val)[:4]
    for key in ("release_date", "upload_date"):
        val = entry.get(key)
        if isinstance(val, str) and len(val) >= 4:
            return val[:4]
    return ""


def _looks_like_youtube_playlist(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url or url.startswith("PL") or url.startswith("OL")


def fetch_playlist_tracks(
    url_or_id: str, filter_embeddable: bool = True
) -> tuple[list[dict[str, Any]], int]:
    """Return (tracks, dropped_count).

    `tracks` is the playable list of {id, name, artists, year, video_id,
    duration_ms} — after dropping deleted/private/unavailable entries and,
    if `filter_embeddable` is True, videos that YouTube refuses to embed.
    `dropped_count` reports how many were dropped by the embeddability check
    only (so the caller can surface "X filtrées" to the user).

    Uses `extract_flat="in_playlist"` so we do ONE network call per playlist
    instead of one per video — critical for playlists >50 tracks. The
    embeddability check then adds one short HTTP probe per surviving video,
    parallelized via a thread pool.
    """
    url = url_or_id.strip()
    if not url:
        raise YouTubeError("URL de playlist vide")
    if not _looks_like_youtube_playlist(url):
        raise YouTubeError(
            "URL non reconnue — colle une URL de playlist YouTube "
            "(https://www.youtube.com/playlist?list=…)"
        )

    ydl_opts = {
        "extract_flat": "in_playlist",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise YouTubeError(f"yt-dlp n'a pas pu lire la playlist : {exc}") from exc

    if not info:
        raise YouTubeError("Réponse vide de yt-dlp")

    entries = info.get("entries") or []
    if not entries:
        raise YouTubeError("Playlist vide ou inaccessible (vérifie qu'elle est publique)")

    tracks: list[dict[str, Any]] = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id")
        if not video_id:
            continue
        raw_title = entry.get("title") or ""
        if raw_title in ("[Deleted video]", "[Private video]", "[Unavailable]"):
            continue
        uploader = entry.get("uploader") or entry.get("channel") or ""
        artist, title = split_artist_title(raw_title, uploader)
        duration_s = entry.get("duration") or 0
        tracks.append(
            {
                "id": video_id,
                "name": title,
                "artists": artist,
                "year": extract_year(entry),
                "video_id": video_id,
                "duration_ms": int(duration_s * 1000) if duration_s else 0,
            }
        )

    if not filter_embeddable:
        return tracks, 0

    playable, dropped = _filter_embeddable(tracks)
    return playable, dropped
