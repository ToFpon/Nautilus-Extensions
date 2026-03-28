#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Dual Panel — Nautilus Python Extension
# DESC: Full-featured dual-panel file manager launched from Nautilus
# AUTHOR: Tof
# VERSION: 1.0
# LICENSE: GNU General Public License v3.0
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# NAME: Duration Column — Nautilus Python Extension
# DESC: Adds a Duration column for audio/video files in Nautilus list view
# REQUIRES: python3-nautilus, ffmpeg
# INSTALL:
#   cp duration-column.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q

import os
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote

import gi
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Nautilus

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv",
    ".mp3", ".flac", ".wav", ".ogg", ".m4a", ".opus", ".aac", ".wma",
})

CACHE_FILE        = Path.home() / ".cache" / "nautilus-media-durations.json"
CACHE_EXPIRE_DAYS = 30
CACHE_SAVE_EVERY  = 5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(seconds_str: str) -> str:
    try:
        s = float(seconds_str)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        s = int(s % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return ""


def _probe(file_path: str):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            val = r.stdout.strip()
            float(val)
            return val
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return None

# ---------------------------------------------------------------------------
# Cache disque
# ---------------------------------------------------------------------------

class DiskCache:
    """Cache JSON avec expiration, sauvegarde atomique et nettoyage auto."""

    def __init__(self):
        self._data  = self._load()
        self._dirty = 0
        self._evict_expired()

    def _load(self) -> dict:
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self):
        """Sauvegarde atomique via fichier temporaire."""
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = CACHE_FILE.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(self._data, f, separators=(",", ":"))
            tmp.replace(CACHE_FILE)
            self._dirty = 0
        except OSError:
            pass

    def _evict_expired(self):
        """Supprime les entrées non accédées depuis CACHE_EXPIRE_DAYS."""
        cutoff  = time.time() - CACHE_EXPIRE_DAYS * 86400
        expired = [k for k, v in self._data.items()
                   if v.get("accessed", 0) < cutoff]
        for k in expired:
            del self._data[k]
        if expired:
            self._save()

    def get(self, path: str):
        entry = self._data.get(path)
        if not entry:
            return None
        try:
            if os.path.getmtime(path) != entry.get("mtime", -1):
                return None     # fichier modifié → invalider
            entry["accessed"] = time.time()
            return entry["duration"]
        except OSError:
            return None

    def set(self, path: str, duration: str):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return
        self._data[path] = {
            "duration": duration,
            "mtime":    mtime,
            "accessed": time.time(),
        }
        self._dirty += 1
        if self._dirty >= CACHE_SAVE_EVERY:
            self._save()

    def flush(self):
        if self._dirty:
            self._save()

# ---------------------------------------------------------------------------
# Extension Nautilus — synchrone, simple, fiable
# ---------------------------------------------------------------------------

_cache = DiskCache()

class DurationColumnExtension(
        GObject.GObject,
        Nautilus.ColumnProvider,
        Nautilus.InfoProvider):

    __gtype_name__ = "DurationColumnExtension"

    def get_columns(self):
        return [Nautilus.Column(
            name        = "NautilusPython::duration_column",
            attribute   = "duration",
            label       = "Duration",
            description = "Duration of audio/video files",
        )]

    def update_file_info(self, file_info):
        if file_info.get_uri_scheme() != "file":
            return

        path = unquote(file_info.get_uri()[7:])
        if os.path.splitext(path)[1].lower() not in SUPPORTED_EXTENSIONS:
            return

        # Cache hit — instantané
        cached = _cache.get(path)
        if cached:
            file_info.add_string_attribute("duration", _fmt(cached))
            return

        # Cache miss — ffprobe synchrone
        dur = _probe(path)
        if dur:
            _cache.set(path, dur)
            file_info.add_string_attribute("duration", _fmt(dur))
