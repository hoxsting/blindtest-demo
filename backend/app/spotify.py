"""Spotify integration: resolve a playlist URL to playable 30s previews.

Uses the Client Credentials flow — needs SPOTIPY_CLIENT_ID and
SPOTIPY_CLIENT_SECRET in the environment. No user OAuth required; we only
read public playlist metadata and the public `preview_url` audio clips.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

_PLAYLIST_ID_RE = re.compile(r"playlist[/:]([A-Za-z0-9]+)")


class SpotifyError(Exception):
    """Raised when something goes wrong talking to Spotify."""


def extract_playlist_id(url_or_id: str) -> str:
    s = url_or_id.strip()
    if not s:
        raise SpotifyError("URL de playlist vide")
    match = _PLAYLIST_ID_RE.search(s)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", s):
        return s
    raise SpotifyError("Impossible d'extraire l'ID de la playlist")


@lru_cache(maxsize=1)
def _client() -> spotipy.Spotify:
    try:
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials())
    except Exception as exc:
        raise SpotifyError(
            "Credentials Spotify manquants — définis SPOTIPY_CLIENT_ID et "
            "SPOTIPY_CLIENT_SECRET dans l'environnement avant de lancer le serveur."
        ) from exc


def fetch_playlist_tracks(url_or_id: str) -> list[dict[str, Any]]:
    """Return tracks of a playlist that expose a usable `preview_url`.

    Tracks without `preview_url` (Spotify omits it for some markets/licenses)
    are filtered out — they cannot be played by the blindtest.
    """
    playlist_id = extract_playlist_id(url_or_id)
    sp = _client()

    try:
        page = sp.playlist_items(
            playlist_id,
            additional_types=("track",),
            limit=100,
            market="FR",
        )
    except spotipy.SpotifyException as exc:
        detail = f"Spotify a refusé la requête (HTTP {exc.http_status})"
        if exc.http_status == 404:
            detail = "Playlist introuvable — vérifie qu'elle est publique"
        raise SpotifyError(detail) from exc

    tracks: list[dict[str, Any]] = []
    while page is not None:
        for item in page.get("items") or []:
            track = item.get("track")
            if not track or track.get("is_local"):
                continue
            preview = track.get("preview_url")
            if not preview:
                continue
            artists = ", ".join(
                a.get("name", "") for a in track.get("artists") or [] if a.get("name")
            )
            album = track.get("album") or {}
            year = (album.get("release_date") or "")[:4]
            tracks.append(
                {
                    "id": track.get("id") or "",
                    "name": track.get("name") or "",
                    "artists": artists,
                    "album": album.get("name") or "",
                    "year": year,
                    "preview_url": preview,
                    "duration_ms": track.get("duration_ms") or 0,
                }
            )
        page = sp.next(page) if page.get("next") else None

    return tracks
