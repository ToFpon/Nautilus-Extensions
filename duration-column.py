import os
import subprocess
import time
import json
from pathlib import Path
from urllib.parse import unquote
from gi.repository import GObject, Nautilus
from typing import Dict, Optional

# ===== CONFIGURATION =====
SUPPORTED_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.mp3', '.flac', '.wav', '.ogg', '.m4a', '.m4v', '.wmv', '.opus'}
CACHE_FILE = Path.home() / ".cache" / "nautilus-media-durations.json"
CACHE_EXPIRE_DAYS = 7
FFPROBE_TIMEOUT = 5
# =========================


class DiskCache:
    def __init__(self):
        self.cache = self._load_cache()
        self._prune_old_entries()

    def _load_cache(self) -> Dict:
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_cache(self):
        CACHE_FILE.parent.mkdir(exist_ok=True, parents=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f)

    def _prune_old_entries(self):
        now = time.time()
        self.cache = {
            path: data
            for path, data in self.cache.items()
            if (now - data.get('timestamp', 0)) < (CACHE_EXPIRE_DAYS * 86400)
        }
        self._save_cache()

    def get(self, path: str) -> Optional[Dict]:
        """Retourne le dict complet {duration, timestamp, mtime} ou None."""
        data = self.cache.get(path)
        if data and (time.time() - data.get('timestamp', 0)) < (CACHE_EXPIRE_DAYS * 86400):
            return data
        return None

    def set(self, path: str, duration: str):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        self.cache[path] = {
            'duration': duration,
            'timestamp': time.time(),
            'mtime': mtime,
        }
        self._save_cache()


class DurationColumnExtension(GObject.GObject, Nautilus.ColumnProvider, Nautilus.InfoProvider):

    def __init__(self):
        super().__init__()
        self.cache = DiskCache()

    # ------------------------------------------------------------------
    # ColumnProvider : déclare la colonne à Nautilus
    # ------------------------------------------------------------------
    def get_columns(self):
        column = Nautilus.Column(
            name="NautilusPython::duration_column",
            attribute="duration",
            label="Durée",
            description="Durée du média",
        )
        return [column]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def format_duration(seconds: float) -> str:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @staticmethod
    def get_duration_via_ffprobe(path: str) -> Optional[str]:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=FFPROBE_TIMEOUT,
            )
            data = json.loads(result.stdout)
            seconds = float(data["format"]["duration"])
            return DurationColumnExtension.format_duration(seconds)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # InfoProvider — version asynchrone (Nautilus 43+)
    # ------------------------------------------------------------------
    def update_file_info_full(self, provider, handle, closure, file):
        self._do_update(file)
        # Retourner COMPLETE suffit — ne pas appeler invoke en plus (doublon)
        return Nautilus.OperationResult.COMPLETE

    # ------------------------------------------------------------------
    # InfoProvider — version synchrone (fallback Nautilus < 43)
    # ------------------------------------------------------------------
    def update_file_info(self, file: Nautilus.FileInfo):
        self._do_update(file)

    # ------------------------------------------------------------------
    # Logique commune
    # ------------------------------------------------------------------
    def _do_update(self, file: Nautilus.FileInfo):
        if file.get_uri_scheme() != "file":
            return

        path = unquote(file.get_uri()[7:])
        ext = os.path.splitext(path)[1].lower()

        if ext not in SUPPORTED_EXTENSIONS:
            return

        if not os.path.isfile(path):
            return

        # Vérifie le cache ET le mtime du fichier
        cached = self.cache.get(path)
        if cached:
            try:
                current_mtime = os.path.getmtime(path)
            except OSError:
                current_mtime = 0

            if cached.get('mtime') == current_mtime:
                file.add_string_attribute("duration", cached['duration'])
                return

        # Pas en cache (ou fichier modifié) : appel ffprobe
        duration = self.get_duration_via_ffprobe(path)
        if duration:
            self.cache.set(path, duration)
            file.add_string_attribute("duration", duration)
