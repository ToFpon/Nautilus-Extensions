import os
import subprocess
import time
import json
from pathlib import Path
from urllib.parse import unquote
from gi.repository import GObject, Nautilus

# ===== CONFIGURATION =====
SUPPORTED_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.webm', '.mp3', '.flac', '.wav', '.ogg', '.m4a', '.m4v', '.wmv', '.opus'
}
CACHE_FILE = Path.home() / ".cache" / "nautilus-media-durations.json"
CACHE_EXPIRE_DAYS = 30
# =========================

def format_duration(seconds_str):
    try:
        seconds = float(seconds_str)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except:
        return seconds_str

def get_raw_duration(file_path):
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return None

class DiskCache:
    def __init__(self):
        self.cache = self._load_cache()
        self._unsaved_changes = 0

    def _load_cache(self):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def _save_cache(self):
        CACHE_FILE.parent.mkdir(exist_ok=True, parents=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f)
        self._unsaved_changes = 0

    def get(self, path):
        data = self.cache.get(path)
        if data:
            try:
                if os.path.getmtime(path) == data.get('mtime', 0):
                    return data['duration_seconds']  # Retourne toujours les secondes
            except:
                pass
        return None

    def set(self, path, duration_seconds):
        try:
            mtime = os.path.getmtime(path)
            self.cache[path] = {'duration_seconds': duration_seconds, 'mtime': mtime}
            self._unsaved_changes += 1
            if self._unsaved_changes >= 5:
                self._save_cache()
        except:
            pass

    def save_if_needed(self):
        if self._unsaved_changes > 0:
            self._save_cache()

class DurationColumnExtension(GObject.GObject, Nautilus.ColumnProvider, Nautilus.InfoProvider):
    def __init__(self):
        super().__init__()
        self.cache = DiskCache()

    def update_file_info(self, file_info):
        if file_info.get_uri_scheme() != 'file':
            return

        file_path = unquote(file_info.get_uri()[7:])
        if not any(file_path.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            return

        # 1. Vérifie le cache (en secondes)
        cached_seconds = self.cache.get(file_path)
        if cached_seconds:
            file_info.add_string_attribute('duration', format_duration(cached_seconds))
            return

        # 2. Si pas dans le cache, lance ffprobe
        raw_seconds = get_raw_duration(file_path)
        if raw_seconds:
            self.cache.set(file_path, raw_seconds)
            file_info.add_string_attribute('duration', format_duration(raw_seconds))

    def get_columns(self):
        return (
            Nautilus.Column(
                name='NautilusPython::duration_column',
                attribute='duration',
                label='Duration',
                description='Shows the duration of media files.'
            ),
        )
