"""YouTube playlist metadata extraction via yt-dlp.

We don't fetch audio server-side — playback is done by an embedded YouTube
IFrame Player on the frontend (avoids CORS, signature, and bot-check pain).
yt-dlp is used purely to enumerate the playlist's video IDs and titles, then
we heuristically split "Artist - Title" out of the YouTube video title.
"""
from __future__ import annotations

import re
from typing import Any

import yt_dlp


class YouTubeError(Exception):
    """Raised when something goes wrong talking to YouTube."""


# Cosmetic suffixes commonly added to YouTube video titles. Stripped before
# we try to split artist/title — otherwise "Daft Punk - Around the World
# (Official Video)" would treat "Around the World (Official Video)" as the
# track name.
_NOISE_RE = re.compile(
    r"\s*[\(\[](?:"
    r"official(?:\s+\w+)*|"
    r"music\s*video|lyrics?(?:\s+video)?|audio|hd|hq|"
    r"\d{3,4}p|4k|"
    r"remaster(?:ed)?(?:\s+\d{4})?|"
    r"explicit|clean|"
    r"feat\.?\s+[^)\]]+|"
    r"prod\.?\s+by\s+[^)\]]+"
    r")[\)\]]\s*",
    re.IGNORECASE,
)

# Separators used by uploaders to delimit "Artist <sep> Title". Order matters:
# we try the more explicit ones first to avoid greedy hyphens inside titles.
_SEPARATORS = (" — ", " – ", " | ", " : ", " - ")


def _clean_title(raw: str) -> str:
    out = raw
    for _ in range(3):
        new = _NOISE_RE.sub("", out).strip()
        if new == out:
            break
        out = new
    return out


def split_artist_title(raw_title: str, fallback_uploader: str = "") -> tuple[str, str]:
    """Heuristic split of a YouTube video title into (artist, track_title)."""
    cleaned = _clean_title(raw_title)
    for sep in _SEPARATORS:
        if sep in cleaned:
            left, right = cleaned.split(sep, 1)
            return left.strip(), right.strip()
    # No separator: use the uploader name as artist if it doesn't already
    # appear in the title (common for "- Topic" YouTube auto-channels).
    uploader = fallback_uploader.removesuffix(" - Topic").strip()
    return uploader, cleaned


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


def fetch_playlist_tracks(url_or_id: str) -> list[dict[str, Any]]:
    """Return a list of {id, name, artists, year, video_id, duration_ms}.

    Uses `extract_flat="in_playlist"` so we do ONE network call per playlist
    instead of one per video — critical for playlists >50 tracks.
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

    return tracks
