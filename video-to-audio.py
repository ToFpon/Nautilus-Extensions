#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Video to Audio — Nautilus Python Extension
# DESC: Extract audio from video files using ffmpeg
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
# INSTALL:
#   cp video-to-audio.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q

import os
import shutil
import subprocess
import threading
import locale
import re

import gi
gi.require_version("Gtk",     "4.0")
gi.require_version("Adw",     "1")
gi.require_version("Nautilus","4.0")
from gi.repository import GObject, Gtk, Adw, GLib, Pango, Nautilus

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":   "Extraire l'audio",
        "title":        "Extraction audio",
        "format":       "Format de sortie :",
        "quality":      "Qualité :",
        "quality_high": "Haute (320 kbps)",
        "quality_med":  "Moyenne (192 kbps)",
        "quality_low":  "Basse (128 kbps)",
        "quality_copy": "Copier le flux (sans réencodage)",
        "convert":      "Extraire",
        "cancel":       "Annuler",
        "close":        "Fermer",
        "processing":   "Extraction en cours…",
        "file_done":    "✓ {name}",
        "file_error":   "✗ {name}",
        "all_done":     "Extraction terminée — {ok} sur {total} réussie(s).",
        "cancelled":    "Extraction annulée.",
        "overwrite":    "Le fichier existe déjà — il sera écrasé.",
    }
elif _lang.startswith("de"):
    T = {
        "menu_label":   "Audio extrahieren",
        "title":        "Audio-Extraktion",
        "format":       "Ausgabeformat:",
        "quality":      "Qualität:",
        "quality_high": "Hoch (320 kbps)",
        "quality_med":  "Mittel (192 kbps)",
        "quality_low":  "Niedrig (128 kbps)",
        "quality_copy": "Stream kopieren (ohne Neukodierung)",
        "convert":      "Extrahieren",
        "cancel":       "Abbrechen",
        "close":        "Schließen",
        "processing":   "Extraktion läuft…",
        "file_done":    "✓ {name}",
        "file_error":   "✗ {name}",
        "all_done":     "Extraktion abgeschlossen — {ok} von {total} erfolgreich.",
        "cancelled":    "Extraktion abgebrochen.",
        "overwrite":    "Datei existiert bereits — wird überschrieben.",
    }
else:
    T = {
        "menu_label":   "Extract audio",
        "title":        "Audio Extraction",
        "format":       "Output format:",
        "quality":      "Quality:",
        "quality_high": "High (320 kbps)",
        "quality_med":  "Medium (192 kbps)",
        "quality_low":  "Low (128 kbps)",
        "quality_copy": "Copy stream (no re-encoding)",
        "convert":      "Extract",
        "cancel":       "Cancel",
        "close":        "Close",
        "processing":   "Extracting…",
        "file_done":    "✓ {name}",
        "file_error":   "✗ {name}",
        "all_done":     "Extraction complete — {ok} of {total} succeeded.",
        "cancelled":    "Extraction cancelled.",
        "overwrite":    "File already exists — will be overwritten.",
    }

# Extensions vidéo supportées
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
              ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".ogv", ".vob"}

# Formats audio disponibles (extension, codec ffmpeg)
AUDIO_FORMATS = [
    ("mp3",  "libmp3lame"),
    ("m4a",  "aac"),
    ("ogg",  "libvorbis"),
    ("opus", "libopus"),
    ("flac", "flac"),
    ("wav",  "pcm_s16le"),
]

QUALITIES = ["high", "medium", "low", "copy"]
QUALITY_BITRATES = {"high": "320k", "medium": "192k", "low": "128k"}


def _nautilus_window():
    app = Gtk.Application.get_default()
    return app.get_active_window() if app else None


def _get_duration(path):
    """Retourne la durée en secondes d'un fichier vidéo via ffprobe."""
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stderr=subprocess.DEVNULL).decode().strip()
        return float(out)
    except Exception:
        return 0.0


def _parse_time(time_str):
    """Parse HH:MM:SS.mm en secondes."""
    try:
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

class VideoToAudioWindow(Adw.Window):
    __gtype_name__ = "VideoToAudioWindow"

    def __init__(self, video_files):
        super().__init__(title=T["title"])
        self.set_default_size(560, 480)
        self.set_resizable(True)
        self.set_transient_for(_nautilus_window())
        self._videos    = video_files
        self._process   = None
        self._cancelled = False
        self._done      = False

        tv  = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_decoration_layout(":close")
        hdr.set_title_widget(Gtk.Label(label=T["title"]))
        tv.add_top_bar(hdr)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ── Options ───────────────────────────────────────────────────────────
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        opts.set_margin_start(16); opts.set_margin_end(16)
        opts.set_margin_top(12); opts.set_margin_bottom(8)

        # Format
        fmt_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fmt_lbl = Gtk.Label(label=T["format"])
        fmt_lbl.set_halign(Gtk.Align.START)
        fmt_lbl.set_size_request(120, -1)
        fmt_row.append(fmt_lbl)
        self._fmt_drop = Gtk.DropDown.new_from_strings(
            [f[0].upper() for f in AUDIO_FORMATS])
        self._fmt_drop.set_selected(0)  # mp3 par défaut
        self._fmt_drop.set_hexpand(True)
        self._fmt_drop.connect("notify::selected", self._on_fmt_changed)
        fmt_row.append(self._fmt_drop)
        opts.append(fmt_row)

        # Qualité
        qual_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        qual_lbl = Gtk.Label(label=T["quality"])
        qual_lbl.set_halign(Gtk.Align.START)
        qual_lbl.set_size_request(120, -1)
        qual_row.append(qual_lbl)
        self._qual_drop = Gtk.DropDown.new_from_strings([
            T["quality_high"], T["quality_med"], T["quality_low"], T["quality_copy"]
        ])
        self._qual_drop.set_selected(0)
        self._qual_drop.set_hexpand(True)
        qual_row.append(self._qual_drop)
        opts.append(qual_row)

        main.append(opts)
        main.append(Gtk.Separator())

        # ── Liste des fichiers ────────────────────────────────────────────────
        files_label = Gtk.Label()
        files_label.set_markup(f"<b>{len(video_files)} fichier(s)</b>" if _lang.startswith("fr")
                               else f"<b>{len(video_files)} file(s)</b>")
        files_label.set_halign(Gtk.Align.START)
        files_label.set_margin_start(16); files_label.set_margin_end(16)
        files_label.set_margin_top(8)
        main.append(files_label)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_start(16); scroll.set_margin_end(16)
        scroll.set_margin_top(4); scroll.set_margin_bottom(8)

        self._files_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._file_labels = []
        for video in video_files:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status = Gtk.Label(label="•")
            status.set_size_request(20, -1)
            status.add_css_class("dim-label")
            row.append(status)
            name = Gtk.Label(label=os.path.basename(video))
            name.set_halign(Gtk.Align.START)
            name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            name.set_hexpand(True)
            row.append(name)
            self._files_box.append(row)
            self._file_labels.append(status)

        scroll.set_child(self._files_box)
        main.append(scroll)

        # ── Progression ───────────────────────────────────────────────────────
        self._progress = Gtk.ProgressBar()
        self._progress.set_margin_start(16); self._progress.set_margin_end(16)
        self._progress.set_margin_bottom(4)
        self._progress.set_visible(False)
        main.append(self._progress)

        main.append(Gtk.Separator())

        # ── Boutons ───────────────────────────────────────────────────────────
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_start(12); bottom.set_margin_end(12)
        bottom.set_margin_top(8); bottom.set_margin_bottom(8)

        self._status = Gtk.Label(label="")
        self._status.set_halign(Gtk.Align.START)
        self._status.set_hexpand(True)
        self._status.set_wrap(True)
        bottom.append(self._status)

        self._btn_cancel = Gtk.Button(label=T["cancel"])
        self._btn_cancel.connect("clicked", self._on_cancel)
        bottom.append(self._btn_cancel)

        self._btn_convert = Gtk.Button(label=T["convert"])
        self._btn_convert.add_css_class("suggested-action")
        self._btn_convert.connect("clicked", self._on_convert)
        bottom.append(self._btn_convert)

        self._btn_close = Gtk.Button(label=T["close"])
        self._btn_close.set_visible(False)
        self._btn_close.connect("clicked", lambda _: self.close())
        bottom.append(self._btn_close)

        main.append(bottom)
        tv.set_content(main)
        self.set_content(tv)

    def _on_fmt_changed(self, drop, _param):
        """FLAC et WAV → forcer 'copy' désactivé car incompatible avec ces codecs."""
        # Pas de restriction stricte, juste informatif
        pass

    def _on_convert(self, _):
        self._btn_convert.set_sensitive(False)
        self._fmt_drop.set_sensitive(False)
        self._qual_drop.set_sensitive(False)
        self._progress.set_visible(True)
        self._status.set_text(T["processing"])
        threading.Thread(target=self._run_conversions, daemon=True).start()

    def _run_conversions(self):
        fmt_idx  = self._fmt_drop.get_selected()
        qual_idx = self._qual_drop.get_selected()
        ext, codec = AUDIO_FORMATS[fmt_idx]
        quality    = QUALITIES[qual_idx]

        total = len(self._videos)
        ok    = 0
        time_re = re.compile(r"time=(\d+:\d+:\d+\.\d+)")

        for i, video in enumerate(self._videos):
            if self._cancelled:
                break

            base, _ = os.path.splitext(video)
            output  = f"{base}.{ext}"
            duration = _get_duration(video)

            cmd = ["ffmpeg", "-y", "-i", video, "-vn", "-progress", "pipe:1",
                   "-nostats"]
            if quality == "copy":
                cmd += ["-acodec", "copy"]
            else:
                cmd += ["-acodec", codec, "-b:a", QUALITY_BITRATES[quality]]
            cmd.append(output)

            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
                # Lire la sortie ligne par ligne pour parser la progression
                for line in self._process.stdout:
                    if self._cancelled:
                        break
                    # ffmpeg avec -progress : lignes "out_time=00:00:12.34"
                    if "out_time=" in line:
                        ts = line.split("=", 1)[1].strip()
                        if ts and ts != "N/A":
                            cur = _parse_time(ts)
                            if duration > 0:
                                file_frac = min(cur / duration, 1.0)
                                overall = (i + file_frac) / total
                                GLib.idle_add(self._update_progress, overall, file_frac)
                self._process.wait()
                rc = self._process.returncode
                success = (rc == 0 and not self._cancelled)
            except Exception:
                success = False

            GLib.idle_add(self._update_file_status, i, success)
            if success:
                ok += 1
            GLib.idle_add(self._update_progress, (i + 1) / total, 1.0)

        GLib.idle_add(self._on_done, ok, total)

    def _update_progress(self, overall, file_frac):
        self._progress.set_fraction(overall)
        self._progress.set_text(f"{int(overall * 100)} %")
        self._progress.set_show_text(True)
        return False

    def _update_file_status(self, idx, success):
        lbl = self._file_labels[idx]
        if success:
            lbl.set_text("✓")
            lbl.add_css_class("success")
        else:
            lbl.set_text("✗")
            lbl.add_css_class("error")
        return False

    def _on_done(self, ok, total):
        self._done = True
        self._progress.set_visible(False)
        self._btn_cancel.set_visible(False)
        self._btn_convert.set_visible(False)
        self._btn_close.set_visible(True)
        if self._cancelled:
            self._status.set_text(T["cancelled"])
        else:
            self._status.set_text(T["all_done"].format(ok=ok, total=total))
        return False

    def _on_cancel(self, _):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                import signal
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        if not self._done:
            self.close()


# ---------------------------------------------------------------------------
# Nautilus Extension
# ---------------------------------------------------------------------------

class VideoToAudioExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "VideoToAudioExtension"

    def get_file_items(self, files):
        if not files:
            return []
        # Filtrer les vidéos
        videos = []
        for f in files:
            if f.get_uri_scheme() != "file":
                return []
            if f.is_directory():
                return []
            path = f.get_location().get_path()
            if not path:
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in VIDEO_EXTS:
                return []
            videos.append(path)

        if not videos:
            return []

        item = Nautilus.MenuItem(
            name  = "VideoToAudio::Extract",
            label = T["menu_label"],
            tip   = "Extract audio track from video files",
            icon  = "audio-x-generic-symbolic",
        )
        item.connect("activate", lambda *_: VideoToAudioWindow(videos).present())
        return [item]

    def get_background_items(self, folder):
        return []
